"""構文木。"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Range:
    lo: Optional[int] = None
    hi: Optional[int] = None


@dataclass
class Type:
    kind: str  # ID 整数 金額 割合 参照 名前 写像 集合
    range: Optional[Range] = None
    target: Optional[str] = None  # 参照先／状態の名前
    key: Optional[str] = None  # 写像のキーのデータ名
    value: Optional["Type"] = None
    unit: Optional[str] = None


@dataclass
class Field:
    name: str
    type: Type
    unique: bool = False
    optional: bool = False


@dataclass
class Data:
    name: str
    fields: list[Field]
    line: int = 0


@dataclass
class State:
    name: str
    initial: str = ""
    middle: list[str] = field(default_factory=list)
    final: list[str] = field(default_factory=list)
    rejects: list[tuple[str, str, str]] = field(default_factory=list)
    line: int = 0


@dataclass
class ResultDef:
    name: str
    variants: list[tuple[str, list[Type]]]
    line: int = 0


@dataclass
class EffectDecl:
    name: str  # 決済.請求
    params: list[tuple[str, Type]]
    line: int = 0


@dataclass
class Part:
    name: str
    raw: str
    line: int = 0


@dataclass
class Invariant:
    data: str
    cond: object
    line: int = 0


@dataclass
class Flow:
    name: str
    entries: list[tuple[str, list[tuple[str, str]]]]
    line: int = 0


@dataclass
class Trigger:
    """待ちの宣言。要因（応答／期限）ごとに行き先の処理を持つ。先に起きた要因が勝つ。"""
    name: str
    params: list[tuple[str, Type]]
    causes: list[tuple[str, str, str]]  # (種別 応答／期限, 要因 応答名／秒数, 行き先の処理)
    line: int = 0


@dataclass
class Process:
    name: str
    inputs: list[tuple[str, Type]] = field(default_factory=list)
    refs: list[tuple[str, Type]] = field(default_factory=list)
    reads: list[str] = field(default_factory=list)
    writes: list[str] = field(default_factory=list)
    transitions: list[tuple[str, str, str]] = field(default_factory=list)  # (データ, 元 or "(新規)", 先)
    result: str = ""
    effects: list[str] = field(default_factory=list)
    body: list = field(default_factory=list)
    line: int = 0


@dataclass
class Program:
    data: list[Data] = field(default_factory=list)
    states: list[State] = field(default_factory=list)
    results: list[ResultDef] = field(default_factory=list)
    effects: list[EffectDecl] = field(default_factory=list)
    parts: list[Part] = field(default_factory=list)
    invariants: list[Invariant] = field(default_factory=list)
    processes: list[Process] = field(default_factory=list)
    flows: list[Flow] = field(default_factory=list)
    triggers: list[Trigger] = field(default_factory=list)


# ---- 式 ----
@dataclass
class Num:
    v: int


@dataclass
class Name:
    n: str


@dataclass
class Attr:
    e: object
    n: str


@dataclass
class Index:
    d: str
    e: object


@dataclass
class Call:
    n: str
    args: list


@dataclass
class Bin:
    op: str
    l: object
    r: object


@dataclass
class Binder:
    names: list[str]
    src: object


@dataclass
class SetB:
    elem: object
    binder: Binder
    cond: Optional[object] = None


@dataclass
class SumE:
    elem: object
    binder: Binder
    cond: Optional[object] = None


@dataclass
class Pred:
    e: object
    kind: str  # 空 空でない ある ない


@dataclass
class Implies:
    l: object
    r: object


# ---- 文 ----
@dataclass
class Return:
    variant: str
    args: list
    line: int = 0


@dataclass
class Assign:
    name: str
    e: object
    absent: Optional[Return] = None
    line: int = 0


@dataclass
class Create:
    name: str
    data: str
    fields: list[tuple[str, object]]
    line: int = 0


@dataclass
class If:
    cond: object
    ret: Return
    line: int = 0


@dataclass
class Update:
    target: object  # Attr(Index(D, k), f)
    op: str
    value: object
    binder: Binder
    cond: Optional[object] = None
    line: int = 0


@dataclass
class SetField:
    var: str
    f: str
    e: object
    line: int = 0


@dataclass
class Request:
    effect: str
    args: list
    idem: Optional[object] = None
    line: int = 0


def show_range(r: Optional[Range]) -> str:
    if r is None:
        return ""
    return f" {'' if r.lo is None else r.lo}..{'' if r.hi is None else r.hi}"


def show_type(t: Type) -> str:
    k = t.kind
    if k in ("ID", "文字列", "日時"):
        return k
    if k == "整数":
        return "整数" + show_range(t.range)
    if k == "割合":
        return "割合" + show_range(t.range)
    if k == "金額":
        return f"金額({t.unit or '円'})" + show_range(t.range)
    if k == "参照":
        return f"{t.target} を参照"
    if k == "名前":
        return t.target
    if k == "写像":
        return f"{t.key} → {show_type(t.value)}"
    if k == "集合":
        return f"{show_type(t.value)} の集合"
    raise ValueError(k)


def show(e) -> str:
    if isinstance(e, Num):
        return str(e.v)
    if isinstance(e, Name):
        return e.n
    if isinstance(e, Attr):
        return f"{show(e.e)}.{e.n}"
    if isinstance(e, Index):
        return f"{e.d}[{show(e.e)}]"
    if isinstance(e, Call):
        return f"{e.n}({', '.join(show(a) for a in e.args)})"
    if isinstance(e, Bin):
        return f"{show(e.l)} {e.op} {show(e.r)}"
    if isinstance(e, Pred):
        return f"{show(e.e)} が {e.kind}"
    if isinstance(e, Implies):
        return f"{show(e.l)} なら {show(e.r)}"
    if isinstance(e, (SetB, SumE)):
        b = e.binder
        names = b.names[0] if len(b.names) == 1 else f"({', '.join(b.names)})"
        head = "Σ " if isinstance(e, SumE) else ""
        cond = f", {show(e.cond)}" if e.cond is not None else ""
        return f"{head}{{ {show(e.elem)} | {names} in {show(b.src)}{cond} }}"
    raise ValueError(e)
