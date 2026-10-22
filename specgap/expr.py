"""仕様に書かれた条件式を Z3 の式に変換する。

使える構文は Python の式の一部だけに限る（and / or / not、比較、in [...]、
四則演算、整数・真偽値の定数、名前）。それ以外は SpecError にする。
"""

from __future__ import annotations

import ast
import itertools

import z3

from .model import Spec, SpecError


# Z3 は列挙型の名前を全体で1つしか登録できないので、読み込みごとに番号を付ける
_serial = itertools.count()


class Env:
    """名前から Z3 の値を引く表。入力・出力変数と列挙型の値を持つ。"""

    def __init__(self, spec: Spec):
        self.sorts: dict[str, z3.DatatypeSortRef] = {}
        self.members: dict[str, z3.ExprRef] = {}  # 列挙値の名前 → 定数
        self.member_type: dict[str, str] = {}
        serial = next(_serial)
        for name, values in spec.enums.items():
            sort, consts = z3.EnumSort(f"{name}#{serial}", [f"{v}#{serial}" for v in values])
            self.sorts[name] = sort
            for v, c in zip(values, consts):
                if v in self.member_type:
                    raise SpecError(f"列挙値 {v} が {self.member_type[v]} と {name} の両方にあります")
                self.members[v] = c
                self.member_type[v] = name

        self.vars: dict[str, z3.ExprRef] = {}
        self.var_type: dict[str, str] = {}
        for group in (spec.inputs, spec.outputs):
            for name, var in group.items():
                if name in self.members:
                    raise SpecError(f"変数名 {name} が列挙値の名前と重なっています")
                if var.type == "int":
                    self.vars[name] = z3.Int(name)
                elif var.type == "bool":
                    self.vars[name] = z3.Bool(name)
                else:
                    self.vars[name] = z3.Const(name, self.sorts[var.type])
                self.var_type[name] = var.type

    def domain(self, spec: Spec, include_outputs: bool = False) -> z3.BoolRef:
        """入力（と出力）の範囲制約。"""
        cs = []
        groups = [spec.inputs] + ([spec.outputs] if include_outputs else [])
        for group in groups:
            for name, var in group.items():
                if var.min is not None:
                    cs.append(self.vars[name] >= var.min)
                if var.max is not None:
                    cs.append(self.vars[name] <= var.max)
        return z3.And(cs) if cs else z3.BoolVal(True)


class Compiled:
    """変換結果。式そのものと、式に含まれる原子的な条件と参照した名前を持つ。"""

    def __init__(self, expr: z3.ExprRef, atoms: list[z3.BoolRef], names: set[str]):
        self.expr = expr
        self.atoms = atoms
        self.names = names


def compile_expr(source: str, env: Env) -> Compiled:
    try:
        tree = ast.parse(source.strip(), mode="eval")
    except SyntaxError as e:
        raise SpecError(f"式を読めません: {source}（{e.msg}）") from e
    atoms: list[z3.BoolRef] = []
    names: set[str] = set()
    expr = _Translator(env, atoms, names, source).visit(tree.body)
    return Compiled(expr, atoms, names)


class _Translator:
    def __init__(self, env: Env, atoms: list, names: set, source: str):
        self.env = env
        self.atoms = atoms
        self.names = names
        self.source = source

    def fail(self, msg: str):
        raise SpecError(f"{msg}: {self.source}")

    def visit(self, node: ast.AST) -> z3.ExprRef:
        method = getattr(self, "visit_" + type(node).__name__, None)
        if method is None:
            self.fail(f"使えない構文 {type(node).__name__} です")
        return method(node)

    def visit_BoolOp(self, node: ast.BoolOp):
        parts = [self._bool(v) for v in node.values]
        return z3.And(parts) if isinstance(node.op, ast.And) else z3.Or(parts)

    def visit_UnaryOp(self, node: ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return z3.Not(self._bool(node.operand))
        if isinstance(node.op, ast.USub):
            return -self._int(node.operand)
        self.fail("使えない単項演算子です")

    def visit_BinOp(self, node: ast.BinOp):
        a, b = self._int(node.left), self._int(node.right)
        ops = {ast.Add: lambda: a + b, ast.Sub: lambda: a - b, ast.Mult: lambda: a * b,
               ast.FloorDiv: lambda: a / b, ast.Mod: lambda: a % b}
        for k, f in ops.items():
            if isinstance(node.op, k):
                return f()
        self.fail("使えない演算子です（+ - * // % のみ）")

    def visit_Compare(self, node: ast.Compare):
        parts = []
        left = self.visit(node.left)
        for op, right_node in zip(node.ops, node.comparators):
            if isinstance(op, (ast.In, ast.NotIn)):
                if not isinstance(right_node, (ast.List, ast.Tuple, ast.Set)):
                    self.fail("in の右側は [a, b, ...] の形にしてください")
                choices = [self.visit(e) for e in right_node.elts]
                for c in choices:
                    self._same_kind(left, c)
                atom = z3.Or([left == c for c in choices])
                if isinstance(op, ast.NotIn):
                    atom = z3.Not(atom)
                parts.append(atom)
                self.atoms.extend(left == c for c in choices)
                left = None
                continue
            right = self.visit(right_node)
            self._same_kind(left, right)
            if isinstance(op, ast.Eq):
                atom = left == right
            elif isinstance(op, ast.NotEq):
                atom = left != right
            else:
                if not (z3.is_int(left) and z3.is_int(right)):
                    self.fail("大小比較は整数どうしでしかできません")
                atom = {ast.Lt: left < right, ast.LtE: left <= right,
                        ast.Gt: left > right, ast.GtE: left >= right}[type(op)]
            parts.append(atom)
            self.atoms.append(atom)
            left = right
        return z3.And(parts) if len(parts) > 1 else parts[0]

    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, bool):
            return z3.BoolVal(node.value)
        if isinstance(node.value, int):
            return z3.IntVal(node.value)
        self.fail("定数は整数か True / False だけです")

    def visit_Name(self, node: ast.Name):
        name = node.id
        if name in ("True", "False"):
            return z3.BoolVal(name == "True")
        if name in self.env.vars:
            self.names.add(name)
            v = self.env.vars[name]
            if z3.is_bool(v):
                self.atoms.append(v)
            return v
        if name in self.env.members:
            return self.env.members[name]
        self.fail(f"{name} は入力・出力・列挙値のどれでもありません")

    def visit_IfExp(self, node: ast.IfExp):
        return z3.If(self._bool(node.test), self.visit(node.body), self.visit(node.orelse))

    def _bool(self, node):
        v = self.visit(node)
        if not z3.is_bool(v):
            self.fail("ここには条件（真偽値）が必要です")
        return v

    def _int(self, node):
        v = self.visit(node)
        if not z3.is_int(v):
            self.fail("ここには整数が必要です")
        return v

    def _same_kind(self, a, b):
        if a.sort() != b.sort():
            self.fail(f"{str(a.sort()).split('#')[0]} と {str(b.sort()).split('#')[0]} は比べられません")
