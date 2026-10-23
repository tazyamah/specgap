"""実行時の監視。@watch("項目の id") を付けた関数は、呼ばれるたびに仕様と比べられる。

    from specgap import monitor
    monitor.use(load("shop_v2.yaml"))     # 起動時に一度、比べる仕様を決める

    @monitor.watch("返金方法の決定")
    def refund_method(支払方法): ...

仕様と違う結果を返そうとしたら、呼び出し元に返す前に SpecViolation を投げる。
比べる仕様が決まっていないまま呼ばれたときも止める（監視なしで動かさない）。
"""

from __future__ import annotations

import functools
import inspect
from typing import Callable

from .examples import Examples
from .guarantee import REJECTED, WATCH_ATTR, machine_expected, table_mismatch, to_text
from .model import Spec


class SpecViolation(Exception):
    """実装が仕様と違う結果を返そうとした。"""

    def __init__(self, item: str, inputs: dict[str, str], expected: dict[str, str], actual: dict[str, str]):
        self.item, self.inputs, self.expected, self.actual = item, inputs, expected, actual
        fmt = lambda d: "、".join(f"{k}={v}" for k, v in d.items())
        super().__init__(f"「{item}」：{fmt(inputs)} のとき、仕様は {fmt(expected)}、実装は {fmt(actual)}")


class _State:
    def __init__(self, spec: Spec):
        self.spec = spec
        self.x = Examples(spec)
        self.tables = {t.id: t for t in spec.tables}
        self.machines = {m.id: m for m in spec.machines}


_state: _State | None = None


def use(spec: Spec | None) -> None:
    """監視で比べる仕様を決める。None で解除する。"""
    global _state
    _state = None if spec is None else _State(spec)


def watch(item: str) -> Callable:
    def deco(fn: Callable) -> Callable:
        sig = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if _state is None:
                raise RuntimeError(f"「{item}」を監視する仕様が決まっていません（monitor.use を先に呼んでください）")
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            if item in _state.machines:
                return _machine(_state.machines[item], fn, bound)
            if item in _state.tables:
                return _table(_state, _state.tables[item], fn, bound)
            raise RuntimeError(f"仕様に「{item}」という表も状態機械もありません")

        setattr(wrapper, WATCH_ATTR, item)
        return wrapper

    return deco


def _table(st: _State, t, fn, bound):
    inputs = {k: to_text(v) for k, v in bound.arguments.items() if k in st.spec.inputs}
    for name in st.spec.inputs:
        inputs.setdefault(name, st.x.default(name))
    try:
        result = fn(*bound.args, **bound.kwargs)
    except Exception as e:
        raise SpecViolation(t.id, _shown(inputs, bound), {"結果": "仕様の出力"}, {"結果": f"例外 {type(e).__name__}"}) from e
    bad = table_mismatch(st.x, t, inputs, result)
    if bad is not None:
        raise SpecViolation(t.id, _shown(inputs, bound), *bad)
    return result


def _machine(m, fn, bound):
    state, event = list(bound.arguments.values())[:2]
    want = machine_expected(m, state, event)
    try:
        result = fn(*bound.args, **bound.kwargs)
    except Exception:
        if want == REJECTED:
            raise
        raise SpecViolation(m.id, {"状態": state, "出来事": event}, {"次の状態": want}, {"次の状態": REJECTED})
    got = REJECTED if result is None else to_text(result)
    if got != want:
        raise SpecViolation(m.id, {"状態": state, "出来事": event}, {"次の状態": want}, {"次の状態": got})
    return result


def _shown(inputs: dict[str, str], bound) -> dict[str, str]:
    return {k: v for k, v in inputs.items() if k in bound.arguments}
