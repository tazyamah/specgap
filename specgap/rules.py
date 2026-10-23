"""表の根底にあるルールを先に聞き、ルールを合わせた表を機械が組み立てる。

穴を1つずつ聞くと、似た条件の問いが続き、答えの奥にある考え方（「日がたつほど返金は減る」など）が
どこにも残らない。そこで穴のある表では、先に次のルールを聞く。

- 傾向：経過日数が増えると返金額は？（減る・増える・関係ない・場合による）
- 列どうしの関係：開封済みのときの返金額は、未開封のときと比べて？（同じ・半分・0 など）
- 境界：30日ちょうどは、29日以下と31日以上のどちらと同じ扱い？（列をまとめて1問）

答えたルールは正本の rules に残り、機械が表と照らし合わせる（反する行は拒否）。
ルールが出そろったら、ルールから穴を埋めた表を格子で見せ、「これで正しいですか」と確かめる。
"""

from __future__ import annotations

import ast
import itertools
import re
from dataclasses import dataclass, field

import z3

from .expr import Env, compile_expr
from .model import SAME, UNDECIDED, UNSPECIFIED, Rule, Spec, SpecError, Table

MAX_COLUMNS = 12


@dataclass
class Grid:
    """表を「整数の入力1つの区間 × 列挙・真偽の入力の組」の格子にしたもの。"""
    table: Table
    num: str | None  # 区間に分ける整数の入力（なければ None）
    segs: list[tuple[int, int] | None]
    cols: list[dict[str, str]]
    rows: dict[tuple[int, int], object] = field(default_factory=dict)  # (区間, 列) → 当たる行（なければ None）

    def label(self, si: int) -> str:
        seg = self.segs[si]
        if seg is None:
            return "（すべて）"
        lo, hi = seg
        return str(lo) if lo == hi else f"{lo}〜{hi}"

    @staticmethod
    def col_label(col: dict[str, str]) -> str:
        return "・".join(col.values()) or "（すべて）"

    def cond(self, spec: Spec, si: int, ci: int) -> str:
        """格子の1マスを表の行の条件として書いたもの。"""
        parts = []
        seg = self.segs[si]
        if seg is not None:
            lo, hi = seg
            v = spec.inputs[self.num]
            if lo == hi:
                parts.append(f"{self.num} == {lo}")
            elif lo == v.min and hi == v.max:
                pass
            elif lo == v.min:
                parts.append(f"{self.num} <= {hi}")
            elif hi == v.max:
                parts.append(f"{self.num} >= {lo}")
            else:
                parts.append(f"{lo} <= {self.num} <= {hi}")
        for n, val in self.cols[ci].items():
            if spec.inputs[n].type == "bool":
                parts.append(n if val == "True" else f"not {n}")
            else:
                parts.append(f"{n} == {val}")
        return " and ".join(parts) or "True"


def grid(spec: Spec, env: Env, t: Table) -> Grid | None:
    """格子にできない表（整数の入力が2つ以上、列が多すぎるなど）は None。"""
    names: list[str] = []
    conds = []
    for r in t.rows:
        c = compile_expr(r.when, env)
        conds.append(c.expr)
        names += [n for n in c.names if n in spec.inputs and n not in names]
    names.sort(key=list(spec.inputs).index)
    ints = [n for n in names if spec.inputs[n].type == "int"]
    others = [n for n in names if n not in ints]
    if len(ints) > 1:
        return None
    values = []
    for n in others:
        typ = spec.inputs[n].type
        values.append(["True", "False"] if typ == "bool" else spec.enums[typ])
    cols = [dict(zip(others, combo)) for combo in itertools.product(*values)]
    if len(cols) > MAX_COLUMNS:
        return None
    num = ints[0] if ints else None
    if num is None:
        segs: list = [None]
    else:
        v = spec.inputs[num]
        if v.min is None or v.max is None:
            return None
        consts = {int(x) for r in t.rows for x in re.findall(r"(?<![\w.])-?\d+(?![\w.])", r.when)}
        points = sorted({v.min} | {p for c in consts for p in (c, c + 1) if v.min <= p <= v.max})
        segs = [(p, (points[i + 1] - 1) if i + 1 < len(points) else v.max) for i, p in enumerate(points)]
    g = Grid(t, num, segs, cols)

    def at(si, ci):
        subs = [(env.vars[n], _const(spec, env, n, val)) for n, val in cols[ci].items()]
        if num is not None:
            subs.append((env.vars[num], z3.IntVal(segs[si][0])))
        for r, c in zip(t.rows, conds):
            if z3.is_true(z3.simplify(z3.substitute(c, *subs) if subs else c)):
                return r
        return None

    raw = {(si, ci): at(si, ci) for si in range(len(segs)) for ci in range(len(cols))}
    # 当たる行が列ごとに同じ区間はまとめる
    merged: list = []
    merged_rows: dict = {}
    for si, seg in enumerate(segs):
        key = [raw[(si, ci)] for ci in range(len(cols))]
        if merged and seg is not None and [merged_rows[(len(merged) - 1, ci)] for ci in range(len(cols))] == key:
            merged[-1] = (merged[-1][0], seg[1])
            continue
        merged.append(seg)
        for ci in range(len(cols)):
            merged_rows[(len(merged) - 1, ci)] = key[ci]
    g.segs, g.rows = merged, merged_rows
    return g


def _const(spec: Spec, env: Env, name: str, val: str):
    typ = spec.inputs[name].type
    if typ == "bool":
        return z3.BoolVal(val == "True")
    if typ == "int":
        return z3.IntVal(int(val))
    return env.members[val]


# ---- ルールを表と照らし合わせる ----


def _value(spec: Spec, env: Env, t: Table, out: str):
    """(表がその出力に決める値の式, 値が決まっている入力の条件)。"""
    defined = []
    value = z3.IntVal(0) if spec.outputs[out].type == "int" else env.vars[out]
    for r in reversed(t.rows):
        v = r.then.get(out)
        if v is None or v == UNSPECIFIED:
            continue
        cond = compile_expr(r.when, env).expr
        value = z3.If(cond, compile_expr(v, env).expr, value)
        defined.append(cond)
    return value, (z3.Or(defined) if defined else z3.BoolVal(False))


def _dst_range(spec: Spec, rule: Rule) -> tuple[int, int]:
    lo, _, hi = rule.dst.partition("..")
    return int(lo), int(hi or lo)


def violation(spec: Spec, env: Env, t: Table, rule: Rule, trend: str | None = None):
    """表がルールに反する入力の組（2点）を探す。反しなければ None。

    trend を渡すと、ルールの向きの代わりにその向きで調べる（今の行に合う向きを示すため）。
    返す値は [(入力, 値), (入力, 値)] で、どちらも {名前: 文字列}。
    """
    trend = trend or rule.trend
    if trend in ("", "場合による") and (not rule.then or rule.then == UNDECIDED):
        return None
    dom = env.domain(spec)
    by = env.vars[rule.by]
    other = z3.FreshConst(by.sort(), "比べる")
    names = [n for n in spec.inputs]
    for out in rule.outputs:
        if out not in t.outputs:
            continue
        val, ok = _value(spec, env, t, out)
        pairs = []
        if trend:
            if spec.inputs[rule.by].type == "int":
                v = spec.inputs[rule.by]
                # 穴をはさんでも比べられるよう、隣どうしでなく大小の組すべてを比べる
                pairs.append(z3.And(other > by, *([other <= v.max] if v.max is not None else [])))
            else:
                order = spec.enums.get(spec.inputs[rule.by].type, ["True", "False"])
                for i, a in enumerate(order):
                    for b in order[i + 1:]:
                        pairs.append(z3.And(by == _const(spec, env, rule.by, a), other == _const(spec, env, rule.by, b)))
        else:
            if spec.inputs[rule.by].type == "int":
                lo, hi = _dst_range(spec, rule)
                pairs.append(z3.And(by == int(rule.src), other >= lo, other <= hi))
            else:
                pairs.append(z3.And(by == _const(spec, env, rule.by, rule.src),
                                    other == _const(spec, env, rule.by, rule.dst)))
        val2 = z3.substitute(val, (by, other))
        ok2 = z3.substitute(ok, (by, other))
        if trend == "減る":
            rel = val2 <= val
        elif trend == "増える":
            rel = val2 >= val
        elif trend == "関係ない":
            rel = val2 == val
        else:
            then = out if rule.then == SAME else rule.then
            rel = val2 == z3.substitute(compile_expr(then, env).expr, (env.vars[out], val))
        for pair in pairs:
            s = z3.Optimize()
            s.add(dom, pair, ok, ok2, z3.Not(rel))
            if z3.is_int(by):
                s.minimize(z3.If(other >= by, other - by, by - other))  # なるべく近い2点で示す
            for n in names:
                x = env.vars[n]
                if z3.is_int(x):
                    s.minimize(z3.If(x >= 0, x, -x))
            if s.check() != z3.sat:
                continue
            m = s.model()
            used = [n for n in names if n == rule.by or n in _names(t, env)]
            show = lambda e: _show(m.eval(e, model_completion=True))
            a = {n: show(env.vars[n]) for n in used}
            b = dict(a, **{rule.by: show(other)})
            return [(a, {out: show(val)}), (b, {out: show(val2)})]
    return None


def _names(t: Table, env: Env) -> set[str]:
    return {n for r in t.rows for n in compile_expr(r.when, env).names} | \
           {n for r in t.rows for v in r.then.values() if v != UNSPECIFIED for n in compile_expr(v, env).names}


def _show(v) -> str:
    s = str(v)
    return s.split("#", 1)[0]


def tables_for(spec: Spec, rule: Rule) -> list[Table]:
    return [t for t in spec.tables if set(rule.outputs) & set(t.outputs)]


# ---- ルールの問い ----


def pending(spec: Spec, env: Env, t: Table, g: Grid) -> list[dict]:
    """穴のある表について、まだ聞いていないルールの問い（slot）を、傾向・関係・境界の順に返す。"""
    out: list[dict] = []
    decided = spec.rules
    nums = [o for o in t.outputs if spec.outputs.get(o) is not None and spec.outputs[o].type == "int"]
    inputs = ([g.num] if g.num else []) + [n for n in (g.cols[0] if g.cols else {})]
    for o in nums:
        for n in inputs:
            if spec.inputs[n].type == "bool":
                continue
            if any(r.trend and o in r.outputs and r.by == n for r in decided):
                continue
            fits = [d for d in ("減る", "増える", "関係ない")
                    if violation(spec, env, t, Rule("", [o], n, trend=d)) is None]
            out.append({"type": "rule_trend", "table": t.id, "output": o, "by": n, "fits": fits,
                        "numeric": spec.inputs[n].type == "int"})
    for o in nums:
        for n in [n for n in inputs if spec.inputs[n].type not in ("int", "bool")]:
            order = spec.enums[spec.inputs[n].type]
            for a, b in zip(order, order[1:]):
                if any(not r.trend and o in r.outputs and r.by == n and r.src == a and r.dst == b for r in decided):
                    continue
                cands = [SAME, f"{o} // 2", "0"]
                fits = [c for c in cands if violation(spec, env, t, Rule("", [o], n, src=a, dst=b, then=c)) is None]
                out.append({"type": "rule_relate", "table": t.id, "output": o, "by": n, "from": a, "to": b,
                            "candidates": cands, "fits": fits})
    if g.num:
        for si, seg in enumerate(g.segs):
            if any(g.rows[(si, ci)] is not None for ci in range(len(g.cols))):
                continue
            lo, hi = seg
            dst = str(lo) if lo == hi else f"{lo}..{hi}"
            if any(not r.trend and r.by == g.num and r.dst == dst for r in decided):
                continue
            below = si > 0 and any(g.rows[(si - 1, ci)] is not None for ci in range(len(g.cols)))
            above = si + 1 < len(g.segs) and any(g.rows[(si + 1, ci)] is not None for ci in range(len(g.cols)))
            if not (below or above):
                continue
            out.append({"type": "rule_boundary", "table": t.id, "by": g.num, "lo": lo, "hi": hi,
                        "below": lo - 1 if below else None, "above": hi + 1 if above else None,
                        "outputs": t.outputs})
    return out


# ---- ルールから表を組み立てる ----


def derive(spec: Spec, env: Env, t: Table, g: Grid) -> dict[tuple[int, int], dict[str, tuple[str, str]]]:
    """穴のマスごとに、ルールから決まる値を返す。{(区間, 列): {出力: (値, 使ったルール)}}。"""
    known: dict[tuple[int, int], dict[str, str]] = {}
    for key, r in g.rows.items():
        if r is not None:
            known[key] = dict(r.then)
    made: dict[tuple[int, int], dict[str, tuple[str, str]]] = {}
    rules = [r for r in spec.rules if not r.trend and r.then != UNDECIDED]
    changed = True
    while changed:
        changed = False
        for (si, ci) in g.rows:
            for rule in rules:
                src = _source(spec, g, rule, si, ci)
                if src is None or src not in known:
                    continue
                for o in rule.outputs:
                    if o not in t.outputs or o in known.get((si, ci), {}) or o not in known[src]:
                        continue
                    v = known[src][o]
                    if v == UNSPECIFIED:
                        continue
                    value = v if rule.then == SAME else _subst(rule.then, o, v)
                    known.setdefault((si, ci), {})[o] = value
                    made.setdefault((si, ci), {})[o] = (value, rule.id)
                    changed = True
    return made


def _source(spec: Spec, g: Grid, rule: Rule, si: int, ci: int):
    """ルールでマス (si, ci) の値を決めるとき、元にするマス。"""
    if rule.by == g.num:
        seg = g.segs[si]
        lo, hi = _dst_range(spec, rule)
        if not (lo <= seg[0] and seg[1] <= hi):
            return None
        x = int(rule.src)
        for sj, s in enumerate(g.segs):
            if s[0] <= x <= s[1]:
                return (sj, ci)
        return None
    col = g.cols[ci]
    if rule.by not in col or col[rule.by] != rule.dst:
        return None
    want = dict(col, **{rule.by: rule.src})
    for cj, c in enumerate(g.cols):
        if c == want:
            return (si, cj)
    return None


def _subst(then: str, out: str, value: str) -> str:
    """then の中の出力名を、元のマスの値で置き換える。定数だけになれば計算する。"""
    tree = ast.parse(then, mode="eval")
    repl = ast.parse(str(value), mode="eval").body

    class T(ast.NodeTransformer):
        def visit_Name(self, node):
            return repl if node.id == out else node

    tree = ast.fix_missing_locations(T().visit(tree))
    if not any(isinstance(n, ast.Name) for n in ast.walk(tree)):
        try:
            return str(eval(compile(tree, "<rule>", "eval"), {"__builtins__": {}}))
        except Exception:
            pass
    return ast.unparse(tree)


def render(spec: Spec, g: Grid, made: dict | None = None, out: str | None = None) -> list[str]:
    """格子を会話に貼れる文字の表にする。ルールから決めたマスには * を付ける。"""
    made = made or {}
    outs = [out] if out else g.table.outputs
    head = [g.num or ""] + [Grid.col_label(c) for c in g.cols]
    lines = []
    for si in range(len(g.segs)):
        cells = [g.label(si)]
        for ci in range(len(g.cols)):
            r = g.rows[(si, ci)]
            if r is not None:
                vals = [str(r.then.get(o, "")) for o in outs]
            elif (si, ci) in made:
                vals = [made[(si, ci)][o][0] + " *" if o in made[(si, ci)] else "？" for o in outs]
            else:
                vals = ["？" for _ in outs]
            cells.append("、".join("実装に任せる" if v == UNSPECIFIED else v for v in vals))
        lines.append(cells)
    table = [head] + lines
    width = [max(_w(row[i]) for row in table) for i in range(len(head))]
    fmt = lambda row: "| " + " | ".join(c + " " * (width[i] - _w(c)) for i, c in enumerate(row)) + " |"
    return [fmt(head), "|" + "|".join("-" * (w + 2) for w in width) + "|"] + [fmt(r) for r in lines]


def _w(s: str) -> int:
    return sum(2 if ord(ch) > 0x2E7F else 1 for ch in s)
