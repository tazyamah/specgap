"""実装が仕様に従っていることを確かめ、項目ごとの保証の段階を出す（試作3）。

保証は「事前（なし / テスト済み / 証明済み）× 実行時（監視なし / あり）」で、
単位は「実装の関数 × 仕様の項目（表・状態機械・性質）」。

- 証明：関数の構文木を記号実行して Z3 の式にし、「仕様の条件のもとで実装の値 ≠ 仕様の値」が
  充足不能かを調べる。反例が出たら関数を実際に動かして確かめ、違反の具体例にする
  （変換の誤りを判断の根拠にしないため）。
- 全件確認：状態機械は有限なので、状態 × 出来事 をすべて実行する。
- テスト：記号実行できない書き方（辞書の参照など）は、境界値と乱数の入力で動かして比べる。
- 監視：monitor.watch が付いた関数は、呼ばれるたびに仕様と比べられる。
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import itertools
import random
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import z3

from .checks import ERROR, WARNING, Report
from .examples import LEFT_TO_IMPL, Examples, show, simple_model
from .expr import Env, _Translator, compile_expr
from .model import UNSPECIFIED, Ensure, Machine, Spec, SpecError, Table
from .operations import verify_operation

# 事前の保証の段階（後ろほど強い）。違反は「確かめた結果、仕様と違った」
VIOLATION, NONE, TESTED, PROVED = "違反", "なし", "テスト済み", "証明済み"
LEVELS = [VIOLATION, NONE, TESTED, PROVED]
MONITORED = "監視"

# monitor.watch が関数に付ける印（監視している項目の id）
WATCH_ATTR = "__specgap_watch__"
DELEGATE_ATTR = "__specgap_decide__"  # decide.table / decide.machine で判断に任せた関数

RANDOM_CASES = 300
MAX_GRID = 2000
SEED = 0

REJECTED = "（拒否）"
NOTHING_TO_VERIFY = "保証を確かめられる項目（表・状態機械・操作）を使っていません（画面だけのユースケース）"


@dataclass
class Requirement:
    level: str = TESTED
    monitored: bool = False

    def __str__(self) -> str:
        return self.level + ("＋監視" if self.monitored else "")


def parse_requirement(text: str) -> Requirement:
    """「テスト済み＋監視」のような書き方を読む。"""
    parts = [p.strip() for p in text.replace("+", "＋").split("＋") if p.strip()]
    req = Requirement(level=NONE)
    for p in parts:
        if p == MONITORED:
            req.monitored = True
        elif p in (NONE, TESTED, PROVED):
            req.level = p
        else:
            raise SpecError(f"方針の {text} を読めません（{NONE} / {TESTED} / {PROVED} と ＋{MONITORED}）")
    return req


@dataclass
class Item:
    """仕様の1項目に対する保証。"""
    kind: str  # 表 / 状態機械 / 性質 / 操作
    id: str
    function: str = ""  # 対応する実装の関数（性質は使った関数を「、」でつなぐ）
    level: str = NONE
    monitored: bool = False
    basis: str = ""  # 根拠（証明・N件のテスト・全件確認・対応なし）
    example: dict[str, str] = field(default_factory=dict)  # 違反の具体例の入力
    expected: dict[str, str] = field(default_factory=dict)
    actual: dict[str, str] = field(default_factory=dict)
    required: Requirement = field(default_factory=Requirement)
    before: str | None = None  # 前の版の保証（比べたとき）
    before_rank: tuple[int, int] | None = None
    uses: dict[str, list[str]] = field(default_factory=dict)  # 操作の実装が使った外部作用 → 渡したデータ
    before_uses: dict[str, list[str]] | None = None

    @property
    def label(self) -> str:
        return self.level + ("＋監視" if self.monitored else "")

    def explain(self) -> str:
        """違反の具体例を1文にする。"""
        if self.kind == "操作":
            return (f"筋書き「{self.example['筋書き']}」で、仕様は「{self.expected['仕様']}」ですが、"
                    f"実装は「{self.actual['実装']}」です。")
        return f"{_fmt(self.example)} のとき、仕様は {_fmt(self.expected)}、実装は {_fmt(self.actual)} です。"

    @property
    def meets(self) -> bool:
        if self.level == VIOLATION:
            return False
        return LEVELS.index(self.level) >= LEVELS.index(self.required.level) and \
            (self.monitored or not self.required.monitored)


@dataclass
class Guarantee:
    module: str
    items: list[Item] = field(default_factory=list)
    usecases: list[Item] = field(default_factory=list)  # ユースケースごとの保証（使う項目のうち最も弱いもの）

    def item(self, id_: str) -> Item | None:
        return next((i for i in self.items if i.id == id_), None)


def _rank(item: Item) -> tuple[int, int]:
    return LEVELS.index(item.level), int(item.monitored)


# ---- 入口 ----


def verify(spec: Spec, impl: str | Path | None = None, base: Spec | None = None) -> Guarantee:
    """仕様の項目ごとに、実装がどこまで仕様に従っていると言えるかを調べる。"""
    if spec.implementation is None and impl is None:
        raise SpecError("implementation が書かれていません")
    mapping = spec.implementation
    path = Path(impl) if impl is not None else mapping.module
    module = _load_module(path)
    v = _Verifier(spec, module, mapping.tables if mapping else {}, mapping.machines if mapping else {},
                  mapping.operations if mapping else {})
    from . import decide

    saved = decide._state  # 判断に任せた関数をテストで呼べるよう、確かめている間はこの仕様を使う
    decide.use(spec)
    try:
        g = Guarantee(module=path.name, items=v.run())
    finally:
        decide._state = saved
    g.usecases = usecase_guarantees(spec, g)
    if base is not None and base.implementation is not None:
        try:
            before = verify(base)
        except (SpecError, OSError):
            before = None
        if before is not None:
            for it in g.items:
                b = before.item(it.id)
                if b is not None:
                    it.before, it.before_rank = b.label, _rank(b)
                    if b.kind == "操作" and b.level != VIOLATION:
                        it.before_uses = b.uses
    return g


def usecase_guarantees(spec: Spec, g: Guarantee) -> list[Item]:
    """ユースケースの保証を、使う表・状態機械・操作と、使う表の出力にかかる性質のうち、最も弱いものにする。"""
    import re

    out = []
    for u in spec.usecases:
        parts = [it for name in u.uses if (it := g.item(name)) is not None and it.kind != "性質"]
        outputs = {o for t in spec.tables if t.id in u.uses for r in t.rows for o in r.then}
        for e in spec.ensures:
            if outputs & set(re.findall(r"[^\s()<>=!+\-*/%,]+", e.expr)):
                parts.append(g.item(e.id))
        parts = [p for p in parts if p is not None]
        if not parts:
            out.append(Item("ユースケース", u.id, level=NONE, basis=NOTHING_TO_VERIFY))
            continue
        weakest = min(parts, key=lambda p: (LEVELS.index(p.level) if p.function else LEVELS.index(NONE), p.monitored))
        level = weakest.level if weakest.function else NONE
        basis = "・".join(f"{p.kind}「{p.id}」{p.level if p.function else NONE}" for p in parts)
        out.append(Item("ユースケース", u.id, function="、".join(p.function for p in parts if p.function),
                        level=level, basis=f"最も弱いのは{weakest.kind}「{weakest.id}」。使う項目：{basis}"))
    return out


def apply(report: Report, g: Guarantee) -> None:
    """保証の結果を所見として検査結果に足す。"""
    report.guarantee = g
    for it in g.items:
        name = f"{it.kind}「{it.id}」"
        if it.level == VIOLATION:
            report.add(ERROR, "実装", f"{name}の実装（{it.function}）が仕様と違います", detail=it.explain(),
                       question="実装を直しますか、それとも仕様が間違っていますか", example=it.example, ref=it.id)
        elif not it.function:
            report.add(WARNING, "実装", f"{name}に対応する実装がありません",
                       detail="implementation に関数を書くまで、この項目は保証なしです。", ref=it.id)
        elif not it.meets:
            report.add(ERROR, "実装", f"{name}は方針で「{it.required}」が必要ですが、「{it.label}」までしか確かめられていません",
                       detail=it.basis, ref=it.id)
        if it.before_uses is not None and it.level != VIOLATION:
            added = [f"{e}（{'・'.join(d)}）" for e, d in it.uses.items()
                     if e not in it.before_uses or set(d) - set(it.before_uses[e])]
            if added:
                report.add(WARNING, "実装", f"{name}の実装が使う外部作用やデータが前の版より増えました",
                           detail=f"増えたもの：{'、'.join(added)}", question="この権限の追加を認めますか", ref=it.id)
        if it.before_rank is not None and it.level != VIOLATION and _rank(it) < it.before_rank:
            report.add(WARNING, "実装", f"{name}の保証が前の版より下がりました（{it.before} → {it.label}）",
                       detail="方針の範囲内でも、下がったことは人が確かめます。", ref=it.id)
    for u in g.usecases:
        if u.level in (VIOLATION, NONE) and u.basis != NOTHING_TO_VERIFY:
            report.add(WARNING, "実装", f"ユースケース「{u.id}」は保証がありません（{u.level}）", detail=u.basis,
                       question="使う項目の実装を書くか、確かめ方を足しますか", ref=f"ユースケース:{u.id}")
    if not any(f.check == "実装" and f.severity in (ERROR, WARNING) for f in report.findings):
        report.passed.append("実装と仕様の一致")


def _load_module(path: Path):
    if not path.exists():
        raise SpecError(f"実装ファイル {path} がありません")
    name = f"specgap_impl_{abs(hash(str(path.resolve())))}"
    mod_spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(mod_spec)
    # 実装ファイルが同じフォルダの別ファイルを import できるようにする
    folder = str(path.resolve().parent)
    sys.path.insert(0, folder)
    try:
        mod_spec.loader.exec_module(module)
    finally:
        sys.path.remove(folder)
    return module


# ---- 実装の値と仕様の値を比べる（monitor からも使う） ----


def to_text(value: Any) -> str:
    if value is None:
        return "（なし）"
    return str(value)


def table_outputs(t: Table, result: Any) -> dict[str, str]:
    """関数の戻り値を「出力名 → 表示」にする。出力が1つなら値そのものを返してよい。"""
    if len(t.outputs) == 1 and not isinstance(result, dict):
        return {t.outputs[0]: to_text(result)}
    if not isinstance(result, dict):
        return {o: to_text(result) for o in t.outputs}
    return {o: to_text(result.get(o)) for o in t.outputs}


def _valid(spec: Spec, out: str, text: str) -> bool:
    """実装に任せた出力でも、出力の型と範囲には収まっている必要がある。"""
    var = spec.outputs[out]
    if var.type == "int":
        try:
            n = int(text)
        except ValueError:
            return False
        return (var.min is None or n >= var.min) and (var.max is None or n <= var.max)
    if var.type == "bool":
        return text in ("True", "False")
    return text in spec.enums[var.type]


def table_mismatch(x: Examples, t: Table, inputs: dict[str, str], result: Any):
    """仕様と違えば (仕様の出力, 実装の出力) を返す。仕様が決めていない入力や一致なら None。"""
    exp = x.evaluate(t, inputs)
    if exp.row is None:
        return None
    got = table_outputs(t, result)
    for out in t.outputs:
        e = exp.outputs.get(out)
        if e == LEFT_TO_IMPL:
            if not _valid(x.spec, out, got[out]):
                return {out: f"{LEFT_TO_IMPL}（{_range(x.spec, out)}）"}, {out: got[out]}
        elif got[out] != e:
            return dict(exp.outputs), got
    return None


def _range(spec: Spec, out: str) -> str:
    var = spec.outputs[out]
    if var.type in spec.enums:
        return "・".join(spec.enums[var.type]) + " のどれか"
    lo = "" if var.min is None else var.min
    hi = "" if var.max is None else var.max
    return f"{lo}〜{hi}"


def machine_expected(m: Machine, state: str, event: str) -> str:
    for t in m.transitions:
        if t.src == state and t.event == event:
            return t.dst
    return REJECTED


def call_machine(fn: Callable, state: str, event: str) -> str:
    try:
        r = fn(state, event)
    except Exception:
        return REJECTED
    return REJECTED if r is None else to_text(r)


def call_table(fn: Callable, inputs: dict[str, str], spec: Spec) -> Any:
    """仕様の表記（文字列）の入力を Python の値にして、関数が受け取る引数だけを渡す。"""
    params = inspect.signature(fn).parameters
    kwargs = {}
    for name in params:
        if name in inputs:
            kwargs[name] = _value(spec, name, inputs[name])
    return fn(**kwargs)


def _value(spec: Spec, name: str, text: str) -> Any:
    typ = spec.inputs[name].type
    if typ == "int":
        return int(text)
    if typ == "bool":
        return text == "True"
    return text


def _fmt(d: dict[str, str]) -> str:
    return "、".join(f"{k}={v}" for k, v in d.items())


# ---- 項目ごとの確認 ----


class _Verifier:
    def __init__(self, spec: Spec, module, tables: dict[str, str], machines: dict[str, str],
                 operations: dict[str, str]):
        self.spec = spec
        self.module = module
        self.tables = tables
        self.machines = machines
        self.operations = operations
        self.env = Env(spec)
        self.x = Examples(spec, self.env)
        self.dom = self.env.domain(spec)
        self.policy = {k: parse_requirement(v) for k, v in spec.policy.items()}
        self.default = self.policy.get("default", Requirement(TESTED))
        self.paths: dict[str, list | None] = {}  # 表の id → 記号実行の結果（できなければ None）

    def required(self, id_: str) -> Requirement:
        return self.policy.get(id_, self.default)

    def function(self, name: str) -> Callable | None:
        fn = getattr(self.module, name, None)
        return fn if callable(fn) else None

    def run(self) -> list[Item]:
        items = [self.table(t) for t in self.spec.tables]
        items += [self.machine(m) for m in self.spec.machines]
        owner = {o: t for t in self.spec.tables for o in t.outputs}
        for e in self.spec.ensures:
            names = compile_expr(e.expr, self.env).names
            outs = [n for n in names if n in self.spec.outputs]
            if outs:
                items.append(self.ensure(e, outs, owner))
        items += [self.operation(op) for op in self.spec.operations if op.steps]
        return items

    # ---- 操作（外部とのやりとり） ----

    def operation(self, op) -> Item:
        item = Item("操作", op.id, required=self.required(op.id))
        name = self.operations.get(op.id)
        if not name:
            item.basis = "対応する実装なし"
            return item
        item.function = name
        fn = self.function(name)
        if fn is None:
            item.level, item.basis = VIOLATION, f"関数 {name} が実装ファイルにありません"
            return item
        r = verify_operation(self.spec, op, fn)
        item.uses = r.used
        if not r.ok:
            item.level = VIOLATION
            item.example = {"筋書き": r.scenario}
            item.expected, item.actual = {"仕様": r.expected}, {"実装": r.actual}
            item.basis = "違反の具体例あり"
            return item
        # 筋書きはすべて動かすが、データの値や2回目の失敗までは尽くしていないので証明とは呼ばない
        item.level = TESTED
        item.basis = f"{r.scenarios} 通りの筋書きをすべて確認（正常・確認を断る・失敗の種類ごと・各手順の直後で停止）"
        text_only = [k for k in op.on_failure if k not in op.handlers]
        if op.handlers:
            item.basis += f"。失敗の扱いのうち {len(op.handlers)} 件は、手順どおりに動くかまで確認"
        if text_only:
            item.basis += f"。文章だけの扱い {len(text_only)} 件は、扱った記録があるかだけを確認"
        return item

    # ---- 表 ----

    def table(self, t: Table) -> Item:
        item = Item("表", t.id, required=self.required(t.id))
        name = self.tables.get(t.id)
        if not name:
            item.basis = "対応する実装なし"
            return item
        item.function = name
        fn = self.function(name)
        if fn is None:
            item.level, item.basis = VIOLATION, f"関数 {name} が実装ファイルにありません"
            return item
        item.monitored = getattr(fn, WATCH_ATTR, None) == t.id
        if getattr(fn, DELEGATE_ATTR, None) == t.id and not any(v == UNSPECIFIED for r in t.rows for v in r.then.values()):
            item.level, item.basis = PROVED, "判断に任せている（表をそのまま実行するので、構造上一致）"
            return item
        raw = inspect.unwrap(fn)

        notes = []
        try:
            paths = _symbolic(raw, self.spec, self.env)
        except _Unsupported as e:
            paths = None
            notes.append(f"証明できない書き方（{e}）")
        self.paths[t.id] = paths
        if paths is not None:
            cex = self._prove_table(t, paths)
            if cex is None:
                item.level = PROVED
                item.basis = f"証明（{len(t.rows)} 行 × 実装の {len(paths)} 通りの道筋）"
                return item
            bad = table_mismatch(self.x, t, cex, _safe_call(raw, cex, self.spec))
            if bad is not None:
                return self._violation(item, t, cex, bad)
            notes.append("証明の反例を実行すると仕様どおりだったため、テストで確かめました")

        cases, exhaustive = self._cases(sum(self.x.table_names(t), []), _constants_of(t, raw))
        for inputs in cases:
            bad = table_mismatch(self.x, t, inputs, _safe_call(raw, inputs, self.spec))
            if bad is not None:
                return self._violation(item, t, inputs, bad)
        return self._passed(item, cases, exhaustive, notes)

    def _passed(self, item: Item, cases: list, exhaustive: bool, notes: list[str]) -> Item:
        if exhaustive:
            # 入力の組み合わせが有限で、すべて動かしたなら、それは証明と同じ
            item.level = PROVED
            item.basis = f"全件確認（入力の全 {len(cases)} 通り）"
        else:
            item.level = TESTED
            item.basis = "。".join([f"{len(cases)} 件のテスト", *notes])
        return item

    def _violation(self, item: Item, t: Table, inputs: dict[str, str], bad) -> Item:
        used = set(sum(self.x.table_names(t), []))
        names = [n for n in self.spec.inputs if n in used]
        item.level = VIOLATION
        item.example = {n: inputs[n] for n in names}
        item.expected, item.actual = bad
        item.basis = "違反の具体例あり"
        return item

    def _prove_table(self, t: Table, paths: list) -> dict[str, str] | None:
        for r in t.rows:
            when = compile_expr(r.when, self.env).expr
            for cond, value in paths:
                region = z3.And(self.dom, when, cond)
                bad = self._bad(t, r, value)
                if bad is None:
                    continue
                cex = self._model(t, z3.And(region, bad))
                if cex is not None:
                    return cex
        return None

    def _bad(self, t: Table, r, value):
        """この道筋で実装の値が仕様と違う条件。比べようがない形なら常に真。"""
        if not isinstance(value, dict):
            if len(t.outputs) != 1 or isinstance(value, str):  # 印（return しない・例外・None）
                return z3.BoolVal(True)
            value = {t.outputs[0]: value}
        diffs = []
        for out in t.outputs:
            got = value.get(out)
            if got is None or not isinstance(got, z3.ExprRef):
                return z3.BoolVal(True)
            spec_v = r.then.get(out, UNSPECIFIED)
            if spec_v == UNSPECIFIED:
                diffs.append(z3.Not(self._in_range(out, got)))
                continue
            want = compile_expr(spec_v, self.env).expr
            if want.sort() != got.sort():
                return z3.BoolVal(True)
            diffs.append(got != want)
        return z3.Or(diffs) if diffs else None

    def _in_range(self, out: str, v) -> z3.BoolRef:
        var = self.spec.outputs[out]
        if v.sort() != self.env.vars[out].sort():
            return z3.BoolVal(False)
        cs = []
        if var.min is not None:
            cs.append(v >= var.min)
        if var.max is not None:
            cs.append(v <= var.max)
        return z3.And(cs) if cs else z3.BoolVal(True)

    def _model(self, t: Table | None, formula, names: list[str] | None = None) -> dict[str, str] | None:
        """反例を、人が読みやすい値（0に近い数・代表値）で取り出す。"""
        if names is None:
            cond, res = self.x.table_names(t)
            names = cond + res
            typical = self.x._typical(res)
        else:
            typical = []
        names = [n for n in self.spec.inputs if n in names] or list(self.spec.inputs)
        model = simple_model(self.env, z3.And(formula, *typical), names) if typical else None
        if model is None:
            model = simple_model(self.env, formula, names)
        if model is None:
            return None
        return {n: show(model.eval(self.env.vars[n], model_completion=True)) for n in self.spec.inputs}

    # ---- テストの入力 ----

    def _cases(self, names: list[str], constants: set[int]) -> tuple[list[dict[str, str]], bool]:
        """テストの入力と、それが入力の全組み合わせかどうか。

        組み合わせが MAX_GRID 以下ならすべて、そうでなければ境界値（定数の ±1、範囲の端、
        代表値）の組み合わせと乱数の入力を使う。
        """
        names = [n for n in self.spec.inputs if n in names]
        rng = random.Random(SEED)
        full = [self._all_values(n) for n in names]
        if all(v is not None for v in full) and _product(len(v) for v in full) <= MAX_GRID:
            return self._fill([dict(zip(names, c)) for c in itertools.product(*full)]), True
        grid = []
        for n in names:
            var = self.spec.inputs[n]
            if var.type == "int":
                lo = var.min if var.min is not None else -1000
                hi = var.max if var.max is not None else 1000
                vals = {lo, hi, 0, 1, -1}
                if var.example is not None:
                    vals.add(int(var.example))
                for c in constants:
                    vals |= {c - 1, c, c + 1}
                grid.append(sorted(str(v) for v in vals if lo <= v <= hi))
            elif var.type == "bool":
                grid.append(["False", "True"])
            else:
                grid.append(list(self.spec.enums[var.type]))
        combos = list(itertools.product(*grid))
        if len(combos) > MAX_GRID:
            combos = rng.sample(combos, MAX_GRID)
        cases = [dict(zip(names, c)) for c in combos]
        for _ in range(RANDOM_CASES):
            case = {}
            for n in names:
                var = self.spec.inputs[n]
                if var.type == "int":
                    lo = var.min if var.min is not None else -1000
                    hi = var.max if var.max is not None else 1000
                    case[n] = str(rng.randint(lo, hi))
                elif var.type == "bool":
                    case[n] = rng.choice(["False", "True"])
                else:
                    case[n] = rng.choice(self.spec.enums[var.type])
            cases.append(case)
        return self._fill(list({tuple(c.items()): c for c in cases}.values())), False

    def _fill(self, cases: list[dict[str, str]]) -> list[dict[str, str]]:
        for c in cases:
            for n in self.spec.inputs:
                c.setdefault(n, self.x.default(n))
        return cases

    def _all_values(self, name: str) -> list[str] | None:
        var = self.spec.inputs[name]
        if var.type == "bool":
            return ["False", "True"]
        if var.type in self.spec.enums:
            return list(self.spec.enums[var.type])
        if var.min is None or var.max is None or var.max - var.min >= MAX_GRID:
            return None
        return [str(v) for v in range(var.min, var.max + 1)]

    # ---- 状態機械 ----

    def machine(self, m: Machine) -> Item:
        item = Item("状態機械", m.id, required=self.required(m.id))
        name = self.machines.get(m.id)
        if not name:
            item.basis = "対応する実装なし"
            return item
        item.function = name
        fn = self.function(name)
        if fn is None:
            item.level, item.basis = VIOLATION, f"関数 {name} が実装ファイルにありません"
            return item
        item.monitored = getattr(fn, WATCH_ATTR, None) == m.id
        if getattr(fn, DELEGATE_ATTR, None) == m.id:
            item.level, item.basis = PROVED, "判断に任せている（状態機械をそのまま実行するので、構造上一致）"
            return item
        raw = inspect.unwrap(fn)
        for s in m.states:
            for ev in m.events:
                want, got = machine_expected(m, s, ev), call_machine(raw, s, ev)
                if want != got:
                    item.level = VIOLATION
                    item.example = {"状態": s, "出来事": ev}
                    item.expected, item.actual = {"次の状態": want}, {"次の状態": got}
                    item.basis = "違反の具体例あり"
                    return item
        item.level = PROVED
        item.basis = f"全件確認（状態 {len(m.states)} × 出来事 {len(m.events)} = {len(m.states) * len(m.events)} 組）"
        return item

    # ---- 性質 ----

    def ensure(self, e: Ensure, outs: list[str], owner: dict[str, Table]) -> Item:
        """性質は、出力を決める表の実装を組み合わせて確かめる。"""
        item = Item("性質", e.id, required=self.required(e.id))
        tables = list({owner[o].id: owner[o] for o in outs if o in owner}.values())
        if any(o not in owner for o in outs):
            item.basis = "出力を決める表がなく、実装の関数を対応づけられません"
            return item
        fns = []
        for t in tables:
            name = self.tables.get(t.id)
            fn = self.function(name) if name else None
            if fn is None:
                item.basis = f"表「{t.id}」に対応する実装なし"
                return item
            fns.append((t, inspect.unwrap(fn), getattr(fn, WATCH_ATTR, None) == t.id))
        item.function = "、".join(self.tables[t.id] for t in tables)
        item.monitored = all(w for _, _, w in fns)
        delegated = all(getattr(self.function(self.tables[t.id]), DELEGATE_ATTR, None) == t.id
                        and not any(v == UNSPECIFIED for r in t.rows for v in r.then.values()) for t in tables)
        if delegated:
            from .checks import check

            broken = [f for f in check(self.spec).findings if f.check == "整合" and f"性質「{e.id}」" in f.title]
            if not broken:
                item.level = PROVED
                item.basis = "判断に任せた表がこの性質を満たすことを、表の検査で証明済み"
                return item
        compiled = compile_expr(e.expr, self.env)

        def holds(inputs: dict[str, str]):
            subs = []
            for n, var in self.spec.inputs.items():
                subs.append((self.env.vars[n], _z3_value(self.env, var.type, inputs[n])))
            actual = {}
            for t, fn, _ in fns:
                got = table_outputs(t, _safe_call(fn, inputs, self.spec))
                actual.update(got)
                for out, text in got.items():
                    try:
                        subs.append((self.env.vars[out], _z3_value(self.env, self.spec.outputs[out].type, text)))
                    except (ValueError, KeyError):
                        return False, actual
            return z3.is_true(z3.simplify(z3.substitute(compiled.expr, *subs))), actual

        all_paths = [self.paths.get(t.id) for t, _, _ in fns]
        notes = []
        if all(p is not None for p in all_paths):
            cex = None
            for combo in itertools.product(*all_paths):
                cs = [self.dom]
                ok = True
                for (t, _, _), (cond, value) in zip(fns, combo):
                    if not isinstance(value, dict):
                        value = {t.outputs[0]: value} if len(t.outputs) == 1 else None
                    if value is None or any(not isinstance(value.get(o), z3.ExprRef) for o in t.outputs):
                        ok = False
                        break
                    cs.append(cond)
                    for o in t.outputs:
                        if value[o].sort() != self.env.vars[o].sort():
                            ok = False
                            break
                        cs.append(self.env.vars[o] == value[o])
                if not ok:
                    cex = None
                    notes.append("戻り値の形を式にできない道筋があります")
                    break
                names = sorted(compiled.names & set(self.spec.inputs) |
                               {n for t, _, _ in fns for n in sum(self.x.table_names(t), [])})
                cex = self._model(None, z3.And(*cs, z3.Not(compiled.expr)), names)
                if cex is not None:
                    break
            if cex is None and not notes:
                item.level = PROVED
                item.basis = f"証明（{item.function} の実装を組み合わせて）"
                return item
            if cex is not None:
                ok_, actual = holds(cex)
                if not ok_:
                    return self._ensure_violation(item, e, cex, actual)
                notes.append("証明の反例を実行すると性質を満たしたため、テストで確かめました")
        else:
            notes.append("証明できない書き方の実装を含みます")

        names = list(dict.fromkeys(n for t, _, _ in fns for n in sum(self.x.table_names(t), [])))
        names += [n for n in compiled.names if n in self.spec.inputs and n not in names]
        consts = set()
        for t, fn, _ in fns:
            consts |= _constants_of(t, fn)
        cases, exhaustive = self._cases(names, consts)
        for inputs in cases:
            ok_, actual = holds(inputs)
            if not ok_:
                return self._ensure_violation(item, e, inputs, actual)
        return self._passed(item, cases, exhaustive, notes)

    def _ensure_violation(self, item: Item, e: Ensure, inputs: dict[str, str], actual: dict[str, str]) -> Item:
        item.level = VIOLATION
        item.example = {n: v for n, v in inputs.items() if n in self.spec.inputs}
        item.expected = {"性質": e.expr}
        item.actual = actual
        item.basis = "違反の具体例あり"
        return item


def _product(xs) -> int:
    n = 1
    for x in xs:
        n *= x
    return n


def _z3_value(env: Env, typ: str, text: str):
    if typ == "int":
        return z3.IntVal(int(text))
    if typ == "bool":
        return z3.BoolVal(text == "True")
    return env.members[text]


def _safe_call(fn: Callable, inputs: dict[str, str], spec: Spec) -> Any:
    try:
        return call_table(fn, inputs, spec)
    except Exception as e:  # 例外も「仕様と違う結果」として扱う
        return f"例外 {type(e).__name__}"


def _constants_of(t: Table, fn: Callable) -> set[int]:
    """表の条件と実装に出てくる整数の定数。境界になりやすいのでテストの値に使う。"""
    out: set[int] = set()
    sources = [r.when for r in t.rows]
    for src in sources:
        for node in ast.walk(ast.parse(src.strip(), mode="eval")):
            if isinstance(node, ast.Constant) and type(node.value) is int:
                out.add(node.value)
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    except (OSError, TypeError, SyntaxError):
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and type(node.value) is int:
            out.add(node.value)
    return out


# ---- 記号実行 ----


class _Unsupported(Exception):
    """記号実行できない書き方。"""


# 値の代わりに道筋の終わり方を表す印
_FALLOFF, _RAISE, _NONE = "最後まで return しない", "例外", "None"


class _ImplTranslator(_Translator):
    """関数の中の式を Z3 に変換する。名前は引数と局所変数、文字列の定数は列挙値として読む。"""

    def __init__(self, env: Env, scope: dict[str, Any]):
        super().__init__(env, [], set(), "")
        self.scope = scope

    def fail(self, msg: str):
        raise _Unsupported(msg)

    def visit_Name(self, node: ast.Name):
        if node.id in self.scope:
            return self.scope[node.id]
        if node.id in ("True", "False"):
            return z3.BoolVal(node.id == "True")
        self.fail(f"{node.id} を式にできません")

    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, str):
            if node.value in self.env.members:
                return self.env.members[node.value]
            self.fail(f"文字列 {node.value!r} は列挙値ではありません")
        return super().visit_Constant(node)


def _symbolic(fn: Callable, spec: Spec, env: Env) -> list[tuple[z3.BoolRef, Any]]:
    """関数のすべての道筋を (道筋の条件, 戻り値) の一覧にする。"""
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    except (OSError, TypeError, SyntaxError) as e:
        raise _Unsupported("ソースを読めません") from e
    node = next((n for n in tree.body if isinstance(n, ast.FunctionDef)), None)
    if node is None:
        raise _Unsupported("関数の定義が見つかりません")
    a = node.args
    if a.vararg or a.kwarg or a.posonlyargs or a.kwonlyargs:
        raise _Unsupported("可変長・キーワード専用の引数")
    scope = {}
    for arg in a.args:
        if arg.arg not in spec.inputs:
            raise _Unsupported(f"引数 {arg.arg} が仕様の入力にありません")
        scope[arg.arg] = env.vars[arg.arg]
    return _exec(node.body, z3.BoolVal(True), scope, env)


def _exec(stmts: list[ast.stmt], cond, scope: dict, env: Env) -> list:
    if not stmts:
        return [(cond, _FALLOFF)]
    s, rest = stmts[0], stmts[1:]
    tr = _ImplTranslator(env, scope)
    if isinstance(s, ast.Pass) or (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)):
        return _exec(rest, cond, scope, env)
    if isinstance(s, (ast.Assign, ast.AnnAssign)):
        targets = s.targets if isinstance(s, ast.Assign) else [s.target]
        if len(targets) != 1 or not isinstance(targets[0], ast.Name) or s.value is None:
            raise _Unsupported("1つの名前への代入だけ扱えます")
        return _exec(rest, cond, {**scope, targets[0].id: tr.visit(s.value)}, env)
    if isinstance(s, ast.AugAssign):
        if not isinstance(s.target, ast.Name):
            raise _Unsupported("1つの名前への代入だけ扱えます")
        value = tr.visit(ast.BinOp(left=ast.Name(s.target.id, ast.Load()), op=s.op, right=s.value))
        return _exec(rest, cond, {**scope, s.target.id: value}, env)
    if isinstance(s, ast.If):
        c = tr._bool(s.test)
        out = []
        for branch, guard in ((s.body, c), (s.orelse, z3.Not(c))):
            sub = z3.And(cond, guard)
            if z3.Solver().check(sub) == z3.unsat:
                continue
            out += _exec(branch + rest, sub, scope, env)
        return out
    if isinstance(s, ast.Return):
        return [(cond, _return_value(s.value, tr))]
    if isinstance(s, ast.Raise):
        return [(cond, _RAISE)]
    raise _Unsupported(f"{type(s).__name__} 文")


def _return_value(node: ast.expr | None, tr: _ImplTranslator):
    if node is None or (isinstance(node, ast.Constant) and node.value is None):
        return _NONE
    if isinstance(node, ast.Dict):
        out = {}
        for k, v in zip(node.keys, node.values):
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                raise _Unsupported("辞書のキーは出力名の文字列にしてください")
            out[k.value] = tr.visit(v)
        return out
    return tr.visit(node)
