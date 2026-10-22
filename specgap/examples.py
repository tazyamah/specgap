"""決定表から、人が読める具体例を作る。仕様の差分で振る舞いを比べるときにも使う。"""

from __future__ import annotations

from dataclasses import dataclass, field

import z3

from .expr import Env, compile_expr
from .model import UNSPECIFIED, Spec, Table

# 具体例の出力に使う表記
LEFT_TO_IMPL = "（実装に任せる）"
NO_ROW = "（決まっていない）"
NOT_IN_SPEC = "（この仕様には無い）"


@dataclass
class Example:
    table: str
    row: int | None  # 当たった行（1始まり）。どの行にも当たらなければ None
    inputs: dict[str, str]
    outputs: dict[str, str] = field(default_factory=dict)


def show(value) -> str:
    """Z3 の値を表示用の文字列にする（列挙値に付けた内部の番号は外す）。"""
    return str(value).split("#")[0]


def simple_model(env: Env, formula, minimize: list[str], maximize: list[str] = ()):
    """formula を満たす例のうち、整数がなるべく0に近いもの（maximize は大きいもの）を返す。"""
    opt = z3.Optimize()
    opt.add(formula)
    for n in maximize:
        v = env.vars.get(n)
        if v is not None and z3.is_int(v):
            opt.maximize(v)
    for n in minimize:
        v = env.vars.get(n)
        if v is not None and z3.is_int(v) and n not in maximize:
            opt.minimize(z3.If(v >= 0, v, -v))
    if opt.check() != z3.sat:
        return None
    return opt.model()


class Examples:
    def __init__(self, spec: Spec, env: Env | None = None):
        self.spec = spec
        self.env = env or Env(spec)
        self.dom = self.env.domain(spec)
        self.order = list(spec.inputs)

    def _c(self, src: str):
        return compile_expr(src, self.env)

    def table_names(self, t: Table) -> tuple[list[str], list[str]]:
        """表の条件に出てくる入力と、結果の式にだけ出てくる入力を返す。"""
        cond, res = set(), set()
        for r in t.rows:
            cond |= self._c(r.when).names
            for v in r.then.values():
                if v != UNSPECIFIED:
                    res |= self._c(v).names
        cond &= set(self.spec.inputs)
        res = (res & set(self.spec.inputs)) - cond
        key = self.order.index
        return sorted(cond, key=key), sorted(res, key=key)

    def _typical(self, names: list[str]):
        """結果にだけ使う入力は、仕様に書かれた代表値で固定する。"""
        cs = []
        for n in names:
            var = self.spec.inputs[n]
            if var.example is None:
                continue
            if var.type == "int":
                cs.append(self.env.vars[n] == int(var.example))
            elif var.type == "bool":
                cs.append(self.env.vars[n] == (var.example == "True"))
            elif var.example in self.env.members:
                cs.append(self.env.vars[n] == self.env.members[var.example])
        return cs

    def for_table(self, t: Table) -> list[Example]:
        """各行について、最小値寄りの例と、条件に出る整数の上端寄りの例を作る。"""
        cond_names, res_names = self.table_names(t)
        shown = cond_names + res_names
        ints = [n for n in cond_names if self.spec.inputs[n].type == "int"]
        out: list[Example] = []
        seen = set()
        for r in t.rows:
            base = z3.And(self.dom, self._c(r.when).expr, *self._typical(res_names))
            variants = [[]] + [[n] for n in ints[:1]]
            for mx in variants:
                model = simple_model(self.env, base, shown, mx)
                if model is None:
                    continue
                inputs = {n: show(model.eval(self.env.vars[n], model_completion=True)) for n in shown}
                key = tuple(inputs.items())
                if key in seen:
                    continue
                seen.add(key)
                out.append(Example(t.id, r.index, inputs, self._outputs(r, model)))
        return out

    def _outputs(self, r, model) -> dict[str, str]:
        result = {}
        for out, v in r.then.items():
            result[out] = LEFT_TO_IMPL if v == UNSPECIFIED else show(model.eval(self._c(v).expr, model_completion=True))
        return result

    def evaluate(self, t: Table, inputs: dict[str, str]) -> Example:
        """具体的な入力に対して、表のどの行が当たり、何が出力されるかを計算する。"""
        subs = []
        for name, var in self.spec.inputs.items():
            raw = inputs.get(name)
            if raw is None:
                raw = self.default(name)
            if var.type == "int":
                subs.append((self.env.vars[name], z3.IntVal(int(raw))))
            elif var.type == "bool":
                subs.append((self.env.vars[name], z3.BoolVal(raw == "True")))
            else:
                if raw not in self.env.members:
                    return Example(t.id, None, inputs, {o: NOT_IN_SPEC for o in t.outputs})
                subs.append((self.env.vars[name], self.env.members[raw]))
        for r in t.rows:
            if z3.is_true(z3.simplify(z3.substitute(self._c(r.when).expr, *subs))):
                outs = {}
                for out, v in r.then.items():
                    outs[out] = LEFT_TO_IMPL if v == UNSPECIFIED else \
                        show(z3.simplify(z3.substitute(self._c(v).expr, *subs)))
                return Example(t.id, r.index, inputs, outs)
        return Example(t.id, None, inputs, {o: NO_ROW for o in t.outputs})

    def default(self, name: str) -> str:
        var = self.spec.inputs[name]
        if var.example is not None:
            return var.example
        if var.type == "int":
            return str(var.min if var.min is not None else 0)
        if var.type == "bool":
            return "False"
        return self.spec.enums[var.type][0]
