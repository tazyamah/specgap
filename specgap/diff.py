"""2つの版の仕様を比べ、人が判断すべき変化（構造の差分と振る舞いの差分）を取り出す。"""

from __future__ import annotations

from dataclasses import dataclass, field

from .examples import Examples
from .model import Spec, describe_handles

ADDED, REMOVED, CHANGED = "追加", "削除", "変更"


@dataclass
class Change:
    kind: str  # 追加 / 削除 / 変更
    area: str  # 方針 / ユースケース / 画面 / 状態 / 決定表 / 性質 / 失敗の扱い / 項目
    text: str


@dataclass
class BehaviorChange:
    table: str
    inputs: dict[str, str]
    before: dict[str, str]
    after: dict[str, str]
    before_row: int | None
    after_row: int | None


@dataclass
class SpecDiff:
    base: str
    head: str
    changes: list[Change] = field(default_factory=list)
    behavior: list[BehaviorChange] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.changes and not self.behavior


def diff(base: Spec, head: Spec) -> SpecDiff:
    d = SpecDiff(base=base.name, head=head.name)

    def keyed(area, old: dict, new: dict, describe):
        for k in new.keys() - old.keys():
            d.changes.append(Change(ADDED, area, describe(k, new[k])))
        for k in old.keys() - new.keys():
            d.changes.append(Change(REMOVED, area, describe(k, old[k])))
        for k in old.keys() & new.keys():
            if old[k] != new[k]:
                d.changes.append(Change(CHANGED, area, f"{k}：{old[k] or '（なし）'}　⇒　{new[k] or '（なし）'}"))

    keyed("項目", {f"入力 {k}": _var(v) for k, v in base.inputs.items()},
          {f"入力 {k}": _var(v) for k, v in head.inputs.items()}, lambda k, v: f"{k}（{v}）")
    keyed("項目", {f"出力 {k}": _var(v) for k, v in base.outputs.items()},
          {f"出力 {k}": _var(v) for k, v in head.outputs.items()}, lambda k, v: f"{k}（{v}）")
    keyed("項目", {f"選択肢 {k}": "・".join(v) for k, v in base.enums.items()},
          {f"選択肢 {k}": "・".join(v) for k, v in head.enums.items()}, lambda k, v: f"{k}：{v}")
    keyed("ユースケース", {f"{u.actor}が「{u.id}」": u.description for u in base.usecases},
          {f"{u.actor}が「{u.id}」": u.description for u in head.usecases}, lambda k, v: k)
    keyed("性質", {e.id: e.expr for e in base.ensures}, {e.id: e.expr for e in head.ensures},
          lambda k, v: f"「{k}」{v}")

    # 画面と状態遷移は、矢印1本ずつを比べる
    def arrows_screens(spec):
        a = {f"{f.id}：{s.src} →「{s.action}」→ {s.dst}": "" for f in spec.screen_flows for s in f.steps}
        a.update({f"{f.id}：最初の画面は {f.start}": "" for f in spec.screen_flows})
        a.update({f"{f.id}：{n} で終わる": "" for f in spec.screen_flows for n in f.final})
        a.update({f"{f.id}：{e.via} のリンク{f'（{e.link}）' if e.link else ''} → {e.dst}": "" for f in spec.screen_flows for e in f.entries})
        return a

    def arrows_machine(spec):
        a = {f"{m.id}：{t.src} →「{t.event}」→ {t.dst}": "" for m in spec.machines for t in m.transitions}
        a.update({f"{m.id}：{r.src} で「{r.event}」は拒否": "" for m in spec.machines for r in m.rejects})
        return a

    keyed("画面", arrows_screens(base), arrows_screens(head), lambda k, v: k)
    keyed("状態", arrows_machine(base), arrows_machine(head), lambda k, v: k)

    def handlers(spec):
        return {f"{o.id}：{k}": v + (f"（手順：{describe_handles(o.handlers[k])}）" if k in o.handlers else "")
                for o in spec.operations for k, v in o.on_failure.items()}

    keyed("失敗の扱い", handlers(base), handlers(head), lambda k, v: f"{k} は「{v}」")

    def links(spec):
        out = {}
        for n, e in spec.effect_info.items():
            if not e.system:
                continue
            out[f"{n} の相手"] = e.system
            out[f"{n} の待ち方"] = "応答を待つ" if e.mode == "sync" else "送るだけ"
            out[f"{n} の取り消し"] = {"yes": "できる", "no": "できない", "compensate": f"埋め合わせる（{e.compensate}）"}.get(e.reversible, "未定")
            out[f"{n} の二重実行を防ぐキー"] = e.idempotency
            out[f"{n} で渡すデータ"] = "・".join(e.sends)
            if e.outcomes:
                out[f"{n} の結果の種類"] = "・".join(e.outcomes)
        return out

    keyed("連携", {f"システム {k}": v.kind for k, v in base.systems.items()},
          {f"システム {k}": v.kind for k, v in head.systems.items()}, lambda k, v: f"{k}（{v}）")
    lb, lh = links(base), links(head)
    names_b = {k.split(" ")[0] for k in lb}
    names_h = {k.split(" ")[0] for k in lh}
    # 作用そのものの追加・削除は1行にまとめ、残ったものは項目ごとに比べる
    keyed("連携", {n: lb[f"{n} の相手"] for n in names_b}, {n: lh[f"{n} の相手"] for n in names_h},
          lambda k, v: f"{k}（相手：{v}）")
    both = names_b & names_h
    keyed("連携", {k: v for k, v in lb.items() if k.split(" ")[0] in both},
          {k: v for k, v in lh.items() if k.split(" ")[0] in both}, lambda k, v: f"{k}：{v}")
    keyed("連携", {f"{k} に渡してよい区分": "・".join(v) for k, v in base.data_allow.items()},
          {f"{k} に渡してよい区分": "・".join(v) for k, v in head.data_allow.items()}, lambda k, v: f"{k}：{v}")

    def steps(spec):
        label = {"confirm": "確認", "call": "呼ぶ", "send": "送る", "await": "待つ", "update": "更新"}
        return {f"{o.id} の手順": " → ".join(f"{label[s.kind]}「{s.target}」" for s in o.steps)
                for o in spec.operations if o.steps}

    keyed("手順", steps(base), steps(head), lambda k, v: f"{k}：{v}")
    keyed("手順", {f"{o.id} が途中で止まったとき": o.on_interrupt for o in base.operations if o.on_interrupt},
          {f"{o.id} が途中で止まったとき": o.on_interrupt for o in head.operations if o.on_interrupt},
          lambda k, v: f"{k}：{v}")

    def rows(spec):
        return {f"{t.id}：{r.when} → {_then(r.then)}": "" for t in spec.tables for r in t.rows}

    keyed("決定表", rows(base), rows(head), lambda k, v: k)
    def policy(spec):
        return {f"{'指定のない項目' if k == 'default' else k} に必要な保証": v for k, v in spec.policy.items()}

    keyed("方針", policy(base), policy(head), lambda k, v: f"{k}：{v}")

    d.changes.sort(key=lambda c: (_AREA_ORDER.index(c.area), [ADDED, CHANGED, REMOVED].index(c.kind), c.text))
    d.behavior = _behavior(base, head)
    return d


_AREA_ORDER = ["方針", "ユースケース", "画面", "連携", "手順", "状態", "決定表", "性質", "失敗の扱い", "項目"]


def _behavior(base: Spec, head: Spec) -> list[BehaviorChange]:
    """両方の版の具体例を、もう一方の版でも計算して、結果が変わるものを集める。"""
    bx, hx = Examples(base), Examples(head)
    out: list[BehaviorChange] = []
    head_tables = {t.id: t for t in head.tables}
    for bt in base.tables:
        ht = head_tables.get(bt.id)
        if ht is None:
            continue
        names = []
        for x, t in ((bx, bt), (hx, ht)):
            c, r = x.table_names(t)
            names += [n for n in c + r if n not in names]
        seen = set()
        for ex in bx.for_table(bt) + hx.for_table(ht):
            inputs = dict(ex.inputs)
            for n in names:
                if n not in inputs:
                    src = hx if n in head.inputs else bx
                    inputs[n] = src.default(n)
            key = tuple(sorted(inputs.items()))
            if key in seen:
                continue
            seen.add(key)
            a, b = bx.evaluate(bt, inputs), hx.evaluate(ht, inputs)
            if a.outputs != b.outputs:
                ordered = {n: inputs[n] for n in names}
                out.append(BehaviorChange(bt.id, ordered, a.outputs, b.outputs, a.row, b.row))
    return out


def _var(v) -> str:
    rng = ""
    if v.min is not None or v.max is not None:
        rng = f" {'' if v.min is None else v.min}〜{'' if v.max is None else v.max}"
    return f"{v.type}{rng}"


def _then(then: dict[str, str]) -> str:
    return "、".join(f"{k}={v}" for k, v in then.items())
