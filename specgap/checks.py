"""仕様の漏れ検査。

検査は「確実」に答えが出るものだけを扱う。見つかった漏れは、人がそのまま
答えられる問い（この場合はどうしますか）と具体的な入力の例を添えて返す。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import z3

from .expr import Compiled, Env, compile_expr
from .model import UNSPECIFIED, Machine, Spec, SpecError, Table

ERROR = "error"  # 拒否する
WARNING = "warning"  # 人が確認する
INFO = "info"  # 記録だけする

# 1つの表で報告する穴の最大数
MAX_GAPS = 10


@dataclass
class Finding:
    severity: str
    check: str
    title: str
    detail: str = ""
    question: str = ""
    example: dict[str, str] = field(default_factory=dict)
    ref: str = ""  # 関係する表・状態機械・操作の id


@dataclass
class Report:
    spec: str
    findings: list[Finding] = field(default_factory=list)
    passed: list[str] = field(default_factory=list)
    guarantee: object = None  # 実装の保証（guarantee.Guarantee）。実装を確かめたときだけ

    @property
    def ok(self) -> bool:
        return not any(f.severity == ERROR for f in self.findings)

    def add(self, *args, **kwargs):
        self.findings.append(Finding(*args, **kwargs))


def check(spec: Spec) -> Report:
    report = Report(spec=spec.name)
    env = Env(spec)
    checker = _Checker(spec, env, report)
    checker.run()
    return report


class _Checker:
    def __init__(self, spec: Spec, env: Env, report: Report):
        self.spec = spec
        self.env = env
        self.report = report
        self.dom_in = env.domain(spec)
        self.dom_all = env.domain(spec, include_outputs=True)
        self.used_names: set[str] = set()

    def run(self):
        steps = [
            ("出力の割り当て", self.check_outputs),
            ("決定表の網羅と排他", self.check_tables),
            ("性質の矛盾と決定表との整合", self.check_ensures),
            ("状態と出来事の網羅", self.check_machines),
            ("失敗の扱いの網羅", self.check_failures),
            ("ユースケースと画面の整合", self.check_usecases),
            ("システム間の連携", self.check_integrations),
            ("入力項目の使用", self.check_unused_inputs),
        ]
        for name, step in steps:
            before = len([f for f in self.report.findings if f.severity != INFO])
            step()
            after = len([f for f in self.report.findings if f.severity != INFO])
            if after == before:
                self.report.passed.append(name)

    # ---- 出力 ----

    def check_outputs(self):
        owner: dict[str, list[str]] = {}
        for t in self.spec.tables:
            for out in t.outputs:
                if out not in self.spec.outputs:
                    self.report.add(ERROR, "出力", f"表「{t.id}」が未定義の出力 {out} を決めています")
                owner.setdefault(out, []).append(t.id)
            for row in t.rows:
                for out in t.outputs:
                    if out not in row.then:
                        self.report.add(
                            ERROR, "出力", f"表「{t.id}」の{row.index}行目が出力 {out} を決めていません",
                            question=f"この行に当たるとき、{out} はどうなりますか（決めない場合は unspecified と書きます）",
                        )
        ensured = set()
        for e in self.spec.ensures:
            ensured |= self._compile(e.expr).names
        for out in self.spec.outputs:
            tables = owner.get(out, [])
            if len(tables) > 1:
                self.report.add(ERROR, "出力", f"出力 {out} を複数の表（{'、'.join(tables)}）が決めています")
            elif not tables and out in ensured:
                self.report.add(
                    WARNING, "出力", f"出力 {out} は性質だけで縛られていて、値は実装が選びます",
                    detail="意図的なら問題ありません。値を1つに決めたい場合は決定表を書いてください。",
                )
            elif not tables:
                self.report.add(
                    ERROR, "出力", f"出力 {out} を決める表も性質もありません",
                    question=f"{out} はどう決まりますか",
                )

    # ---- 決定表 ----

    def check_tables(self):
        for t in self.spec.tables:
            conds = [self._compile(r.when) for r in t.rows]
            for c in conds:
                self.used_names |= c.names
            for r in t.rows:
                for v in r.then.values():
                    if v != UNSPECIFIED:
                        self.used_names |= self._compile(v).names
            self._unreachable_rows(t, conds)
            self._gaps(t, conds)
            self._overlaps(t, conds)
            for r in t.rows:
                for out, v in r.then.items():
                    if v == UNSPECIFIED:
                        self.report.add(
                            INFO, "未規定", f"表「{t.id}」の{r.index}行目で {out} を意図的に決めていません",
                            detail=f"条件: {r.when}",
                        )

    def _unreachable_rows(self, t: Table, conds: list[Compiled]):
        for r, c in zip(t.rows, conds):
            s = z3.Solver()
            s.add(self.dom_in, c.expr)
            if s.check() == z3.unsat:
                self.report.add(
                    WARNING, "到達不能", f"表「{t.id}」の{r.index}行目には、どんな入力も当たりません",
                    detail=f"条件: {r.when}",
                )

    def _gaps(self, t: Table, conds: list[Compiled]):
        uncovered = z3.And(self.dom_in, z3.Not(z3.Or([c.expr for c in conds]) if conds else z3.BoolVal(False)))
        atoms = [a for c in conds for a in c.atoms]
        names = sorted({n for c in conds for n in c.names}, key=self._input_order)
        for model in self._cells(uncovered, atoms, names):
            ex = self._example(model, names)
            self.report.add(
                ERROR, "網羅", f"表「{t.id}」のどの行にも当たらない入力があります",
                question=f"{self._fmt(ex)} のとき、どうしますか",
                example=ex, ref=t.id,
            )

    def _overlaps(self, t: Table, conds: list[Compiled]):
        names = sorted({n for c in conds for n in c.names}, key=self._input_order)
        for i in range(len(t.rows)):
            for j in range(i + 1, len(t.rows)):
                both = z3.And(self.dom_in, conds[i].expr, conds[j].expr)
                model = self._simple_model(both, names)
                if model is None:
                    continue
                ex = self._example(model, names)
                ri, rj = t.rows[i], t.rows[j]
                same = self._same_results(t, ri, rj, both)
                note = "両行の結果は同じなので、どちらかの条件を狭めれば済みます。" if same else \
                    f"結果が違います（{ri.index}行目: {self._fmt(ri.then)} / {rj.index}行目: {self._fmt(rj.then)}）。"
                self.report.add(
                    ERROR, "排他", f"表「{t.id}」の{ri.index}行目と{rj.index}行目の両方に当たる入力があります",
                    detail=note,
                    question=f"{self._fmt(ex)} のとき、どちらの行を使いますか",
                    example=ex, ref=t.id,
                )

    def _same_results(self, t: Table, a, b, region) -> bool:
        diffs = []
        for out in t.outputs:
            va, vb = a.then.get(out), b.then.get(out)
            if va == UNSPECIFIED or vb == UNSPECIFIED or va is None or vb is None:
                if va != vb:
                    return False
                continue
            diffs.append(self._compile(va).expr != self._compile(vb).expr)
        if not diffs:
            return True
        s = z3.Solver()
        s.add(region, z3.Or(diffs))
        return s.check() == z3.unsat

    # ---- 性質 ----

    def check_ensures(self):
        if not self.spec.ensures:
            return
        compiled = [(e, self._compile(e.expr)) for e in self.spec.ensures]
        for _, c in compiled:
            self.used_names |= c.names

        s = z3.Solver()
        s.add(self.dom_all, *[c.expr for _, c in compiled])
        if s.check() == z3.unsat:
            self.report.add(
                ERROR, "矛盾", "性質どうしが矛盾していて、同時に満たす値がありません",
                detail="矛盾した仕様からは何でも証明できてしまうため、受け入れられません。",
            )
            return

        for e, c in compiled:
            s = z3.Solver()
            s.add(self.dom_all, z3.Not(c.expr))
            if s.check() == z3.unsat:
                self.report.add(
                    WARNING, "自明", f"性質「{e.id}」は入出力の範囲だけで常に成り立ち、何も縛っていません",
                    detail=f"式: {e.expr}",
                )

        for t in self.spec.tables:
            outs = set(t.outputs)
            for e, c in compiled:
                if not (c.names & outs):
                    continue
                for r in t.rows:
                    self._row_vs_ensure(t, r, e, c)

    def _row_vs_ensure(self, t: Table, r, e, c: Compiled):
        cond = self._compile(r.when).expr
        fixed = []
        free = []
        for out, v in r.then.items():
            if v == UNSPECIFIED:
                free.append(self.env.vars[out])
            else:
                fixed.append(self.env.vars[out] == self._compile(v).expr)
        names = sorted(self._compile(r.when).names | (c.names & set(self.spec.inputs)), key=self._input_order)
        if free:
            # 未規定の出力について、性質を満たす値が1つもない入力があれば漏れ
            out_dom = [self._out_bounds(v) for v in free]
            body = z3.Not(z3.And(*out_dom, c.expr)) if out_dom else z3.Not(c.expr)
            claim = z3.And(self.dom_in, cond, *fixed, z3.ForAll(free, body))
            model = self._simple_model(claim, names)
            if model is not None:
                ex = self._example(model, names)
                self.report.add(
                    ERROR, "整合", f"表「{t.id}」の{r.index}行目は結果を実装に任せていますが、性質「{e.id}」を満たす値がありません",
                    question=f"{self._fmt(ex)} のとき、どうしますか",
                    example=ex,
                )
            return
        claim = z3.And(self.dom_in, cond, *fixed, z3.Not(c.expr))
        model = self._simple_model(claim, names)
        if model is not None:
            ex = self._example(model, names)
            got = {out: _show(model.eval(self.env.vars[out], model_completion=True)) for out in r.then}
            self.report.add(
                ERROR, "整合", f"表「{t.id}」の{r.index}行目の結果が性質「{e.id}」に違反します",
                detail=f"{self._fmt(ex)} のとき {self._fmt(got)} になり、{e.expr} を満たしません。",
                question="表と性質のどちらが正しいですか",
                example=ex,
            )

    def _out_bounds(self, v) -> z3.BoolRef:
        var = self.spec.outputs[str(v)]
        cs = []
        if var.min is not None:
            cs.append(v >= var.min)
        if var.max is not None:
            cs.append(v <= var.max)
        return z3.And(cs) if cs else z3.BoolVal(True)

    # ---- 状態機械 ----

    def check_machines(self):
        for m in self.spec.machines:
            self._machine(m)

    def _machine(self, m: Machine):
        states, events = set(m.states), set(m.events)
        refs = [(t.src, t.event, "遷移元") for t in m.transitions] + [(r.src, r.event, "拒否") for r in m.rejects]
        for src, ev, _ in refs:
            if src not in states:
                self.report.add(ERROR, "状態", f"状態機械「{m.id}」に未定義の状態 {src} があります")
            if ev not in events:
                self.report.add(ERROR, "状態", f"状態機械「{m.id}」に未定義の出来事 {ev} があります")
        for t in m.transitions:
            if t.dst not in states:
                self.report.add(ERROR, "状態", f"状態機械「{m.id}」の遷移先 {t.dst} が未定義です")
        for s in [m.initial, *m.final]:
            if s not in states:
                self.report.add(ERROR, "状態", f"状態機械「{m.id}」の初期・終了状態 {s} が未定義です")

        for s in m.states:
            for ev in m.events:
                ts = [t for t in m.transitions if t.src == s and t.event == ev]
                rs = [r for r in m.rejects if r.src == s and r.event == ev]
                if not ts and not rs:
                    self.report.add(
                        ERROR, "状態", f"状態機械「{m.id}」で、状態 {s} に出来事 {ev} が来たときの扱いがありません",
                        question=f"{s} のときに {ev} が来たら、どの状態にしますか。それとも拒否しますか",
                        example={"状態": s, "出来事": ev},
                    )
                elif len(ts) + len(rs) > 1:
                    targets = [t.dst for t in ts] + (["拒否"] if rs else [])
                    self.report.add(
                        ERROR, "状態", f"状態機械「{m.id}」で、状態 {s} に出来事 {ev} が来たときの扱いが複数あります",
                        detail=f"候補: {'、'.join(targets)}",
                        question="どれにしますか",
                        example={"状態": s, "出来事": ev},
                    )

        reach, frontier = {m.initial}, [m.initial]
        while frontier:
            s = frontier.pop()
            for t in m.transitions:
                if t.src == s and t.dst not in reach:
                    reach.add(t.dst)
                    frontier.append(t.dst)
        for s in m.states:
            if s not in reach:
                self.report.add(WARNING, "状態", f"状態機械「{m.id}」の状態 {s} には初期状態から到達できません")
            if s not in m.final and not any(t.src == s and t.dst != s for t in m.transitions):
                self.report.add(
                    WARNING, "状態", f"状態機械「{m.id}」の状態 {s} は終了状態ではないのに、抜け出す遷移がありません",
                    question=f"{s} は終了状態ですか",
                )

    # ---- 失敗 ----

    def check_failures(self):
        for op in self.spec.operations:
            expected = {}
            for eff in op.uses:
                if eff not in self.spec.effects:
                    self.report.add(ERROR, "失敗", f"操作「{op.id}」が未定義の外部作用 {eff} を使っています")
                    continue
                for fail in self.spec.effects[eff]:
                    expected[f"{eff}.{fail}"] = (eff, fail)
            for key, (eff, fail) in expected.items():
                if key not in op.on_failure:
                    self.report.add(
                        ERROR, "失敗", f"操作「{op.id}」で {eff} の「{fail}」が起きたときの扱いがありません",
                        question=f"{op.id} の途中で {eff} が「{fail}」になったら、どうしますか",
                    )
            for key in op.on_failure:
                if key not in expected:
                    self.report.add(
                        WARNING, "失敗", f"操作「{op.id}」の失敗の扱い {key} は、起こり得ない失敗に対するものです",
                    )

    # ---- ユースケースと画面 ----

    def check_usecases(self):
        spec = self.spec
        known = {t.id for t in spec.tables} | {m.id for m in spec.machines} | {o.id for o in spec.operations}
        ucs = {u.id for u in spec.usecases}
        for u in spec.usecases:
            if u.actor not in spec.actors:
                self.report.add(ERROR, "ユースケース", f"ユースケース「{u.id}」のアクター {u.actor or '（なし）'} が定義されていません",
                                question=f"「{u.id}」は誰が行いますか")
            for ref in u.uses:
                if ref not in known:
                    self.report.add(ERROR, "ユースケース", f"ユースケース「{u.id}」が未定義の {ref} を参照しています")
        for actor in spec.actors:
            if not any(u.actor == actor for u in spec.usecases):
                self.report.add(WARNING, "ユースケース", f"アクター {actor} が行うユースケースがありません",
                                question=f"{actor} は何をする人ですか。不要なら消してよいですか")
        if spec.usecases:
            used = {r for u in spec.usecases for r in u.uses}
            for op in spec.operations:
                if op.id not in used:
                    self.report.add(WARNING, "ユースケース", f"操作「{op.id}」を行うユースケースがありません",
                                    question=f"「{op.id}」は誰がどの場面で行いますか")

        reached_ucs = set()
        for f in spec.screen_flows:
            for st in f.steps:
                if st.usecase:
                    reached_ucs.add(st.usecase)
                    if st.usecase not in ucs:
                        self.report.add(ERROR, "画面", f"画面の流れ「{f.id}」の操作「{st.action}」が未定義のユースケース {st.usecase} を指しています")
            seen = set()
            for st in f.steps:
                key = (st.src, st.action)
                if key in seen:
                    self.report.add(ERROR, "画面", f"画面の流れ「{f.id}」で、{st.src} の「{st.action}」の行き先が複数あります",
                                    question="どの画面に進みますか")
                seen.add(key)
            reach, frontier = {f.start}, [f.start]
            while frontier:
                cur = frontier.pop()
                for st in f.steps:
                    if st.src == cur and st.dst not in reach:
                        reach.add(st.dst)
                        frontier.append(st.dst)
            for name in f.screens:
                if name not in reach:
                    self.report.add(WARNING, "画面", f"画面の流れ「{f.id}」の画面 {name} には、最初の画面からたどり着けません")
                if name not in f.final and not any(st.src == name for st in f.steps):
                    self.report.add(WARNING, "画面", f"画面の流れ「{f.id}」の画面 {name} から先へ進む操作も戻る操作もありません",
                                    question=f"{name} を見たあと、利用者はどこへ行けますか")
        if spec.screen_flows:
            for u in spec.usecases:
                if u.id not in reached_ucs:
                    self.report.add(WARNING, "画面", f"ユースケース「{u.id}」を始める画面上の操作がありません",
                                    question=f"「{u.id}」はどの画面から始めますか（画面を持たない処理なら、その旨を確認してください）")

    # ---- システム間の連携 ----

    def check_integrations(self):
        spec = self.spec
        if not spec.systems:
            return
        used_systems = set()
        for name, e in spec.effect_info.items():
            if not e.system:
                self.report.add(WARNING, "連携", f"外部作用 {name} がどのシステムとのやりとりか書かれていません",
                                question=f"{name} はどのシステムとやりとりしますか", ref=name)
                continue
            if e.system not in spec.systems:
                self.report.add(ERROR, "連携", f"外部作用 {name} のやりとり先 {e.system} が定義されていません", ref=name)
                continue
            used_systems.add(e.system)
            if e.mode not in ("sync", "async"):
                self.report.add(ERROR, "連携", f"外部作用 {name} の mode は sync か async です（{e.mode}）", ref=name)
            if e.reversible not in ("yes", "no", "compensate"):
                self.report.add(ERROR, "取り消し", f"外部作用 {name} を取り消せるかどうかが決まっていません",
                                question=f"{e.system} への {name} は、取り消せますか。取り消せないなら、後から埋め合わせる手段はありますか",
                                ref=name)
            if e.reversible in ("no", "compensate") and not e.idempotency:
                self.report.add(ERROR, "取り消し", f"取り消せない外部作用 {name} に、二重実行を防ぐ仕組みがありません",
                                detail="通信の失敗で再試行したとき、同じ依頼が2回届く可能性があります。",
                                question=f"同じ {name} が2回届いても1回分しか実行されないよう、何で見分けますか（注文番号など）",
                                ref=name)
            if e.reversible == "compensate" and e.compensate not in spec.effect_info:
                self.report.add(ERROR, "取り消し", f"外部作用 {name} を埋め合わせる手段 {e.compensate or '（なし）'} が定義されていません",
                                question=f"{name} を取り消したいときは、何をしますか", ref=name)
            self._data_flow(name, e)
        for sys_name in spec.systems:
            if sys_name not in used_systems:
                self.report.add(WARNING, "連携", f"システム {sys_name} とやりとりする外部作用がありません",
                                question=f"{sys_name} は今も使いますか")
        for op in spec.operations:
            self._steps(op)

    def _data_flow(self, name, e):
        spec = self.spec
        for item in e.sends + e.receives:
            cls = spec.data_items.get(item)
            if cls is None:
                self.report.add(ERROR, "データ", f"データ項目 {item} の区分が決まっていません",
                                question=f"{item} は {'・'.join(spec.data_classes) or '何'} のどれにあたりますか", ref=name)
            elif spec.data_classes and cls not in spec.data_classes:
                self.report.add(ERROR, "データ", f"データ項目 {item} の区分 {cls} が定義されていません", ref=name)
        allowed = spec.data_allow.get(e.system)
        if allowed is None:
            if e.sends:
                self.report.add(ERROR, "データ", f"{e.system} に渡してよいデータの区分が決まっていません",
                                question=f"{e.system} に渡してよいのは、{'・'.join(spec.data_classes)} のどれですか", ref=name)
            return
        for item in e.sends:
            cls = spec.data_items.get(item)
            if cls is not None and cls not in allowed:
                self.report.add(ERROR, "データ", f"{name} で {cls}（{item}）を {e.system} に渡しています",
                                detail=f"{e.system} に渡してよい区分は {'・'.join(allowed) or 'ありません'} です。",
                                question=f"{item} を {e.system} に渡す必要はありますか。渡すなら、許可する区分を変えますか",
                                ref=name)

    def _steps(self, op):
        spec = self.spec
        pending: list[str] = []
        confirmed = False
        external_done: list[str] = []
        interrupt_reported = False  # 途中停止の問いは操作ごとに1回だけ出す
        for i, st in enumerate(op.steps, start=1):
            ref = f"{op.id}#{i}"
            e = spec.effect_info.get(st.target) if st.kind in ("call", "send", "await") else None
            if st.kind in ("call", "send", "await") and e is None:
                self.report.add(ERROR, "手順", f"操作「{op.id}」の手順{i}が未定義の外部作用 {st.target} を使っています", ref=ref)
                continue
            if st.kind == "confirm":
                confirmed = True
            elif st.kind == "call" and e.mode != "sync":
                self.report.add(ERROR, "手順", f"操作「{op.id}」の手順{i}：{st.target} は応答を待たない作用なので call ではなく send です", ref=ref)
            elif st.kind == "send" and e.mode != "async":
                self.report.add(ERROR, "手順", f"操作「{op.id}」の手順{i}：{st.target} は応答を待つ作用なので send ではなく call です", ref=ref)
            elif st.kind == "await":
                if st.target not in pending:
                    self.report.add(ERROR, "手順", f"操作「{op.id}」の手順{i}：送っていない {st.target} の結果を待っています", ref=ref)
                else:
                    pending.remove(st.target)
            elif st.kind == "update" and pending:
                self.report.add(
                    ERROR, "手順", f"操作「{op.id}」の手順{i}で、{'・'.join(pending)} の結果を待たずに状態を進めています",
                    detail=f"手順{i}：{st.target}",
                    question=f"{'・'.join(pending)} が失敗しても「{st.target}」のままでよいですか。結果を待ちますか",
                    ref=ref,
                )
            if st.kind in ("call", "send"):
                if e.reversible in ("no", "compensate") and not confirmed:
                    self.report.add(
                        WARNING, "手順", f"操作「{op.id}」で、取り消せない {st.target} の前に確認の手順がありません",
                        question=f"{st.target} を実行する前に、内容を確認する手順を挟みますか", ref=ref,
                    )
                if st.kind == "send":
                    pending.append(st.target)
                if e.reversible in ("no", "compensate"):
                    external_done.append(st.target)
            if external_done and i < len(op.steps) and not op.on_interrupt and not interrupt_reported \
                    and st.kind in ("call", "send"):
                self.report.add(
                    ERROR, "手順", f"操作「{op.id}」が {st.target} の後で止まったときの扱いがありません",
                    detail="外部ではすでに作用が起きているので、やり直すと二重になり、放っておくと途中の状態が残ります。",
                    question=f"「{op.id}」が {st.target} の直後で止まったら、再開したときにどうしますか", ref=ref,
                )
                interrupt_reported = True
        # 失敗の扱いがすべて書かれていれば、失敗に気づく手段はあるとみなす
        pending = [p for p in pending
                   if not all(f"{p}.{f}" in op.on_failure for f in spec.effects.get(p, []))]
        if pending:
            self.report.add(
                WARNING, "手順", f"操作「{op.id}」は {'・'.join(pending)} の結果を待たずに終わります",
                question="結果が失敗だったと後で分かったら、誰がどう気づきますか", ref=op.id,
            )

    # ---- 入力の使用 ----

    def check_unused_inputs(self):
        for name in self.spec.inputs:
            if name not in self.used_names:
                self.report.add(
                    WARNING, "未使用", f"入力 {name} はどの表にも性質にも使われていません",
                    question=f"{name} によって結果は変わらない、で正しいですか",
                )

    # ---- 補助 ----

    def _compile(self, src: str) -> Compiled:
        return compile_expr(src, self.env)

    def _input_order(self, name: str) -> int:
        keys = list(self.spec.inputs) + list(self.spec.outputs)
        return keys.index(name) if name in keys else len(keys)

    def _simple_model(self, formula, names: list[str]):
        """formula を満たす例のうち、整数がなるべく0に近いものを返す。"""
        opt = z3.Optimize()
        opt.add(formula)
        for n in names:
            v = self.env.vars.get(n)
            if v is not None and z3.is_int(v):
                opt.minimize(z3.If(v >= 0, v, -v))
        if opt.check() != z3.sat:
            return None
        return opt.model()

    def _cells(self, formula, atoms, names):
        """formula の解を、原子条件の真偽の組み合わせ（セル）ごとに1つずつ返す。"""
        blocks = []
        for _ in range(MAX_GAPS):
            model = self._simple_model(z3.And(formula, *blocks), names)
            if model is None:
                return
            yield model
            sig = [a == model.eval(a, model_completion=True) for a in atoms]
            if not sig:
                return
            blocks.append(z3.Not(z3.And(sig)))

    def _example(self, model, names: list[str]) -> dict[str, str]:
        return {n: _show(model.eval(self.env.vars[n], model_completion=True)) for n in names}

    @staticmethod
    def _fmt(d: dict[str, str]) -> str:
        return "、".join(f"{k}={v}" for k, v in d.items()) if d else "（入力によらず）"


def _show(value) -> str:
    """Z3 の値を表示用の文字列にする（列挙値に付けた内部の番号は外す）。"""
    return str(value).split("#")[0]


__all__ = ["check", "Report", "Finding", "ERROR", "WARNING", "INFO", "SpecError"]
