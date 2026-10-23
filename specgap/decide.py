"""実装は、表と状態機械で決まることを書き写さず、判断に任せる。

    from specgap import decide
    decide.use(load("shop.yaml"))                 # 起動時に一度、判断の元になる正本を決める

    refund_amount = decide.table("返金額の決定")    # 呼ぶと表の値を返す
    next_state = decide.machine("注文")             # 呼ぶと次の状態を返す（拒否なら None）

    refund_amount.why(経過日数=30, 商品状態="未開封", 支払額=10000)
    # → 値と、当たった行と、その理由になった判断（D4「30日ちょうどは29日と同じ扱い」など）

表が値を決めずに実装に任せている（unspecified）ところは、otherwise に渡した関数が決める。
otherwise が無いまま、そこに当たる入力で呼ばれたら Undecided を投げる。
実装が if 文で書き写さないので、仕様と実装のずれは構造上起きない（保証は「証明済み」として扱う）。
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from typing import Callable

from . import decisions as records
from .examples import LEFT_TO_IMPL, NO_ROW, Examples
from .guarantee import DELEGATE_ATTR, REJECTED, machine_expected, to_text
from .model import Spec


class Undecided(Exception):
    """仕様が決めていない入力で判断を求められた。"""


@dataclass
class Decided:
    values: dict[str, object]
    row: int | None = None  # 表の何行目（状態機械なら None）
    because: list[tuple[str, str]] = field(default_factory=list)  # (判断の id, 決めたこと)

    def reason(self) -> str:
        return "、".join(f"{i}「{t}」" for i, t in self.because) or "（判断の記録なし）"


class _State:
    def __init__(self, spec: Spec):
        self.spec = spec
        self.x = Examples(spec)


_state: _State | None = None


def use(spec: Spec | None) -> None:
    """判断の元になる正本を決める。None で解除する。"""
    global _state
    _state = None if spec is None else _State(spec)


def _need() -> _State:
    if _state is None:
        raise RuntimeError("判断の元になる仕様が決まっていません（decide.use を先に呼んでください）")
    return _state


def _python(spec: Spec, out: str, text: str):
    var = spec.outputs.get(out)
    if var is not None and var.type == "int":
        return int(text)
    if var is not None and var.type == "bool":
        return text == "True"
    return text


def table(id_: str, otherwise: Callable | None = None) -> Callable:
    def why(**inputs) -> Decided:
        st = _need()
        t = next((x for x in st.spec.tables if x.id == id_), None)
        if t is None:
            raise RuntimeError(f"仕様に表「{id_}」がありません")
        texts = {k: to_text(v) for k, v in inputs.items() if k in st.spec.inputs}
        ex = st.x.evaluate(t, texts)
        if ex.row is None:
            raise Undecided(f"表「{id_}」のどの行にも当たりません：{texts}")
        values = {}
        for out, v in ex.outputs.items():
            if v == LEFT_TO_IMPL:
                if otherwise is None:
                    raise Undecided(f"表「{id_}」の{ex.row}行目は {out} を実装に任せていますが、otherwise がありません")
                got = otherwise(**inputs)
                values[out] = got[out] if isinstance(got, dict) else got
            elif v == NO_ROW:
                raise Undecided(f"表「{id_}」が {out} を決めていません")
            else:
                values[out] = _python(st.spec, out, v)
        row = t.rows[ex.row - 1]
        because = [(d.id, d.title or d.answer) for d in records.for_table_row(st.spec, t.id, row.when)]
        return Decided(values, ex.row, because)

    @functools.wraps(why)
    def call(**inputs):
        values = why(**inputs).values
        return next(iter(values.values())) if len(values) == 1 else values

    call.why = why
    call.__name__ = f"decide_{id_}"
    setattr(call, DELEGATE_ATTR, id_)
    return call


def machine(id_: str) -> Callable:
    def why(state, event) -> Decided:
        st = _need()
        m = next((x for x in st.spec.machines if x.id == id_), None)
        if m is None:
            raise RuntimeError(f"仕様に状態機械「{id_}」がありません")
        nxt = machine_expected(m, to_text(state), to_text(event))
        because = [(d.id, d.title or d.answer) for d in records.for_ref(st.spec, f"状態機械:{id_}:{state}:{event}")]
        return Decided({"次の状態": None if nxt == REJECTED else nxt}, None, because)

    def call(state, event):
        return why(state, event).values["次の状態"]

    call.why = why
    call.__name__ = f"decide_{id_}"
    setattr(call, DELEGATE_ATTR, id_)
    return call
