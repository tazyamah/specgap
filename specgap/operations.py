"""外部とのやりとり（操作）の実装を、模擬の外部の中で動かして確かめる（試作4）。

操作の関数は ctx（Context）だけを受け取り、外部作用は ctx を通してしか使えない。
ctx は仕様の uses にある外部作用しか呼ばせず、仕様の sends にないデータを渡させない
（ケイパビリティ：権限は ctx の形で渡す）。

    def execute_refund(ctx):
        if not ctx.confirm("サポート担当が返金額を確認して承認する"):
            return
        try:
            ctx.call("決済API", 注文番号=ctx.data["注文番号"], ...)
        except EffectFailure as f:
            ctx.handled(f.key)
            return
        ctx.update("注文を返金済みにする")

確かめる筋書き（すべて動かす）：
- 正常：手順が仕様の steps と同じ順か
- 確認を断る：断られたあと、外部作用も状態の更新もしないか
- 失敗：外部作用の失敗の種類ごとに、扱った（ctx.handled）か、失敗した作用が成功しないまま後の手順に進んでいないか
- 途中停止：各手順の直後で止め、もう一度動かしたとき、残りの手順をやり終え、取り消せない作用を二重に実行しないか
どの筋書きでも、使ってよい外部作用だけを使い、仕様どおりのデータだけを渡しているかを確かめる。

失敗の扱いを手順（do）でも書いたものは、失敗のあとの動きが手順どおりかも確かめる（試作9）。
再試行は「再試行で直る」「直らない」の両方、照会の結果で分けるものは結果の種類ごとに筋書きを分ける。
文章だけの扱い（「照会してから再試行する」など）は、扱った記録（ctx.handled）があるかまでしか確かめられない。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .model import Handle, Operation, Spec, _flat


class EffectFailure(Exception):
    """外部作用が失敗した。key は「作用名.失敗名」で、仕様の on_failure のキーと同じ。"""

    def __init__(self, effect: str, kind: str):
        self.effect, self.kind, self.key = effect, kind, f"{effect}.{kind}"
        super().__init__(self.key)


class NotPermitted(BaseException):
    """使ってよい外部作用にない作用を使おうとした、または仕様にないデータを渡そうとした。

    実装の except Exception に握りつぶされないよう、BaseException にしている。
    """


class _Interrupted(BaseException):
    """筋書きの途中停止（プロセスが落ちた想定）。"""


@dataclass
class Scenario:
    name: str
    decline: int | None = None  # 何番目の確認（0始まり）で断るか
    failure: tuple[str, str] | None = None  # (作用名, 失敗名)
    stop_after: int | None = None  # 何手順目の直後で止めるか（1始まり）
    retry_ok: bool | None = None  # 失敗した作用をもう一度行ったとき、直るか
    outcomes: dict[str, str] = field(default_factory=dict)  # 照会などの作用 → 返す結果
    expect: list[tuple[str, str]] | None = None  # 失敗のあと、仕様の手順どおりならこう動く
    lead: tuple[str, str] | None = None  # 失敗の扱いの中でだけ使う作用の失敗は、先にこの失敗を起こして扱いに入る
    data: dict[str, str] = field(default_factory=dict)  # 手元のデータの上書き（条件つきの手順の表の入力）


class Adapter:
    """外部作用の実際の呼び出し先。本番では本物の API を呼ぶものに差し替える。"""

    def confirm(self, text: str) -> bool:
        raise NotImplementedError

    def effect(self, kind: str, effect: str, data: dict) -> dict:
        raise NotImplementedError

    def result(self, effect: str) -> dict:
        raise NotImplementedError

    def update(self, text: str) -> None:
        raise NotImplementedError


class Context:
    """操作の実装に渡す唯一の窓口。権限とデータを毎回確かめてから Adapter に渡す。"""

    def __init__(self, spec: Spec, op: Operation, adapter: Adapter, data: dict[str, str]):
        self._spec, self._op, self._adapter = spec, op, adapter
        self.data = dict(data)
        self.trace: list[tuple[str, str]] = []
        self.handled_keys: list[str] = []

    def _allow(self, effect: str, data: dict | None = None):
        if effect not in self._op.uses:
            raise NotPermitted(f"操作「{self._op.id}」の使ってよい外部作用に {effect} はありません")
        if data is not None:
            want = self._spec.effect_info[effect].sends if effect in self._spec.effect_info else []
            extra = [k for k in data if k not in want]
            missing = [k for k in want if k not in data]
            if extra:
                raise NotPermitted(f"{effect} に仕様にないデータ {'・'.join(extra)} を渡そうとしています")
            if missing:
                raise NotPermitted(f"{effect} に渡すデータ {'・'.join(missing)} が足りません")
            for k, v in data.items():
                var = self._spec.inputs.get(k)
                if var is not None and var.type in self._spec.enums:
                    if v not in self._spec.enums[var.type]:  # 選択肢の項目は、操作がその場で決めてよい
                        raise NotPermitted(f"{effect} に渡す {k} が選択肢 {'・'.join(self._spec.enums[var.type])} にありません（{v}）")
                    continue
                if k in self.data and v != self.data[k]:
                    raise NotPermitted(f"{effect} に渡す {k} が手元の値（{self.data[k]}）と違います（{v}）")

    def confirm(self, text: str) -> bool:
        self.trace.append(("confirm", text))
        return self._adapter.confirm(text)

    def call(self, effect: str, **data) -> dict:
        self._allow(effect, data)
        self.trace.append(("call", effect))
        got = self._adapter.effect("call", effect, data)
        self.data.update(got)
        return got

    def send(self, effect: str, **data) -> None:
        self._allow(effect, data)
        self.trace.append(("send", effect))
        self._adapter.effect("send", effect, data)

    def await_result(self, effect: str) -> dict:
        self._allow(effect)
        self.trace.append(("await", effect))
        got = self._adapter.result(effect)
        self.data.update(got)
        return got

    def update(self, text: str) -> None:
        self.trace.append(("update", text))
        self._adapter.update(text)

    def handled(self, key: str) -> None:
        """失敗を仕様の on_failure のとおりに扱ったことを記録する。"""
        self.handled_keys.append(key)


# ---- 模擬の外部 ----


class World(Adapter):
    """外部のシステムを模したもの。実行の記録は途中停止をまたいで残る。"""

    def __init__(self, spec: Spec, op: Operation, scenario: Scenario):
        self.spec, self.op, self.sc = spec, op, scenario
        self.confirms = 0
        self.steps = 0
        self.failed = False
        self.led = False
        self.executions: list[tuple[str, str | None]] = []  # (作用名, 二重実行を防ぐキーの値)
        self.done: set[tuple[str, str | None]] = set()
        self.sent: dict[str, dict] = {}
        self.updates: list[str] = []
        self.used: dict[str, list[str]] = {}  # 作用名 → 渡したデータ項目

    def _step(self):
        self.steps += 1
        if self.sc.stop_after is not None and self.steps == self.sc.stop_after:
            self.sc = Scenario(self.sc.name, self.sc.decline, self.sc.failure, None, self.sc.retry_ok,
                               self.sc.outcomes, self.sc.expect, self.sc.lead, self.sc.data)  # 止めるのは1回だけ
            raise _Interrupted()

    def _fail(self, effect: str, point: str):
        lead = self.sc.lead
        if lead and lead[0] == effect and (not self.led or self.sc.retry_ok is False) \
                and point == _failure_point(self.spec, self.op, effect):
            self.led = True
            raise EffectFailure(*lead)
        f = self.sc.failure
        if f and f[0] == effect and point == _failure_point(self.spec, self.op, effect):
            if not self.failed or self.sc.retry_ok is False:  # 直らない筋書きでは、何度行っても失敗する
                self.failed = True
                raise EffectFailure(*f)

    def confirm(self, text: str) -> bool:
        i = self.confirms
        self.confirms += 1
        ok = self.sc.decline != i
        self._step()
        return ok

    def effect(self, kind: str, effect: str, data: dict) -> dict:
        info = self.spec.effect_info.get(effect)
        key_item = info.idempotency if info else ""
        key = (effect, str(data[key_item]) if key_item and key_item in data else None)
        self.used[effect] = list(data)
        self._fail(effect, kind)
        if key[1] is None or key not in self.done:  # 同じキーの依頼は外部が1回分として扱う
            self.executions.append(key)
            self.done.add(key)
        self.sent[effect] = data
        got = {} if kind == "send" else _receives(self.spec, effect)
        if info and info.outcomes and kind == "call":
            got["結果"] = self.sc.outcomes.get(effect, info.outcomes[0])
        self._step()
        return got

    def result(self, effect: str) -> dict:
        if effect not in self.sent:
            raise RuntimeError(f"{effect} を送る前に結果を待っています")
        self._fail(effect, "await")
        got = _receives(self.spec, effect)
        self._step()
        return got

    def update(self, text: str) -> None:
        if text not in self.updates:
            self.updates.append(text)
        self._step()


def _receives(spec: Spec, effect: str) -> dict:
    info = spec.effect_info.get(effect)
    return {item: f"{item}-1" for item in (info.receives if info else [])}


def _failure_point(spec: Spec, op: Operation, effect: str) -> str:
    """失敗が実装に届く場所：応答を待つ作用は call、結果を待つ手順があれば await、なければ send。"""
    kinds = [s.kind for s in op.steps if s.target == effect]
    kinds += ["call" if h.kind == "case" else h.kind for h in _handles_of(op) if h.target == effect]
    if "call" in kinds:
        return "call"
    if "await" in kinds:
        return "await"
    return "send"


def sample_data(spec: Spec) -> dict[str, str]:
    """操作に渡す手元のデータ。値は項目ごとに決まった文字列にする。"""
    received = {i for e in spec.effect_info.values() for i in e.receives}
    return {item: f"{item}-0" for item in spec.data_items if item not in received}


# ---- 確かめる ----


@dataclass
class OpResult:
    ok: bool
    scenarios: int = 0
    scenario: str = ""  # 違反した筋書き
    expected: str = ""
    actual: str = ""
    used: dict[str, list[str]] = field(default_factory=dict)  # 実装が使った外部作用 → 渡したデータ


def _conditions(spec: Spec, op: Operation) -> list[dict[str, str]]:
    """条件つきの手順の表について、入力の組み合わせをすべて並べる（選択肢と真偽だけ。数は既定値）。"""
    import itertools
    names = []
    for st in op.steps:
        if st.when:
            t = next((x for x in spec.tables if x.id == st.when.rpartition(".")[0]), None)
            for n, var in spec.inputs.items():
                if t and any(n in r.when for r in t.rows) and n not in names and \
                        (var.type == "bool" or var.type in spec.enums):
                    names.append(n)
    values = [["True", "False"] if spec.inputs[n].type == "bool" else spec.enums[spec.inputs[n].type] for n in names]
    return [dict(zip(names, combo)) for combo in itertools.product(*values)] if names else []


def active(spec: Spec, step, data: dict[str, str]) -> bool:
    """条件つきの手順を、このデータで行うか（表がその出力を True と決めたか）。"""
    if not step.when:
        return True
    from .examples import Examples
    tid, _, out = step.when.rpartition(".")
    t = next((x for x in spec.tables if x.id == tid), None)
    if t is None:
        return False
    ex = Examples(spec).evaluate(t, {k: v for k, v in data.items() if k in spec.inputs})
    return ex.outputs.get(out) == "True"


def scenarios(spec: Spec, op: Operation) -> list[Scenario]:
    combos = _conditions(spec, op)
    if combos:
        # 条件の組み合わせごとに正常の筋書きを動かし、ほかの筋書きはすべての手順を行う組み合わせで動かす
        full = next((c for c in combos if all(active(spec, st, c) for st in op.steps)), combos[0])
        out = [Scenario("正常（" + "・".join(f"{k}={v}" for k, v in c.items()) + "）", data=c) for c in combos]
        rest = _scenarios(spec, op)[1:]
        for sc in rest:
            sc.data = full
        return out + rest
    return _scenarios(spec, op)


def _scenarios(spec: Spec, op: Operation) -> list[Scenario]:
    out = [Scenario("正常")]
    confirms = [s for s in op.steps if s.kind == "confirm"]
    for i, s in enumerate(confirms):
        out.append(Scenario(f"確認を断る（{s.target}）", decline=i))
    for effect in op.uses:
        for kind in spec.effects.get(effect, []):
            key = f"{effect}.{kind}"
            if key in op.handlers:
                for label, choice, seq in expand(spec, op, effect, op.handlers[key]):
                    out.append(Scenario(f"{key}{label}", failure=(effect, kind), expect=seq, **choice))
            else:
                out.append(Scenario(key, failure=(effect, kind), **_lead(spec, op, effect)))
    for k in range(1, len(op.steps)):
        out.append(Scenario(f"{k}番目の手順（{_label(op.steps[k - 1])}）の直後で止まる", stop_after=k))
    return out


def _handles_of(op: Operation):
    for hs in op.handlers.values():
        yield from _flat(hs)


def _lead(spec: Spec, op: Operation, effect: str) -> dict:
    """仕様の手順になく、失敗の扱いの中でだけ使う作用なら、その作用まで届く分かれ道の選び方
    （先に起こす失敗・再試行で直るか・照会の結果）。"""
    if any(s.target == effect for s in op.steps):
        return {}
    for key, hs in op.handlers.items():
        eff, _, kind = key.partition(".")
        for _, choice, seq in expand(spec, op, eff, hs):
            if any(t == effect for _, t in seq):
                return {"lead": (eff, kind), **choice}
    return {}


def _rest(op: Operation, effect: str) -> list[tuple[str, str]]:
    """失敗した手順より後の、仕様の手順。"""
    point = _failure_point(None, op, effect)
    idx = next((i for i, s in enumerate(op.steps) if (s.kind, s.target) == (point, effect)), None)
    return [] if idx is None else [(s.kind, s.target) for s in op.steps[idx + 1:]]


def expand(spec: Spec, op: Operation, failed: str, hs: list[Handle]):
    """手順で書いた扱いを、分かれ道ごとの筋書きにする。(名前, Scenario への選択, 失敗のあとの動き) の並び。"""
    point = _failure_point(spec, op, failed)
    rest = _rest(op, failed)

    def walk(hs, seq, choice, label):
        for i, h in enumerate(hs):
            if h.kind in ("confirm", "call", "send", "await", "update"):
                seq = seq + [(h.kind, h.target)]
            elif h.kind == "resume":
                yield label, choice, seq + rest
                return
            elif h.kind == "retry":
                yield from ([] if choice.get("retry_ok") is False else
                            [(label + "（再試行で直る）", {**choice, "retry_ok": True}, seq + [(point, h.target)] + rest)])
                if choice.get("retry_ok") is True:
                    return
                choice = {**choice, "retry_ok": False}
                label += "（再試行しても直らない）"
                seq = seq + [(point, h.target)] * h.times
            elif h.kind == "case":
                for o, sub in h.cases.items():
                    outs = {**choice.get("outcomes", {}), h.target: o}
                    yield from walk([*sub, *hs[i + 1:]], seq + [("call", h.target)],
                                    {**choice, "outcomes": outs}, label + f"（{h.target}：{o}）")
                return
        yield label, choice, seq

    return list(walk(hs, [], {}, ""))


def verify_operation(spec: Spec, op: Operation, fn: Callable) -> OpResult:
    used: dict[str, list[str]] = {}
    scs = scenarios(spec, op)
    for sc in scs:
        bad = _run(spec, op, fn, sc, used)
        if bad is not None:
            expected, actual = bad
            return OpResult(False, len(scs), sc.name, expected, actual, used)
    return OpResult(True, len(scs), used=used)


def _label(step) -> str:
    return {"confirm": "確認", "call": "呼ぶ", "send": "送る", "await": "待つ", "update": "更新"}[step.kind] + f"「{step.target}」"


def _labels(trace) -> str:
    names = {"confirm": "確認", "call": "呼ぶ", "send": "送る", "await": "待つ", "update": "更新"}
    return " → ".join(f"{names[k]}「{t}」" for k, t in trace) or "（何もしない）"


def _run(spec: Spec, op: Operation, fn: Callable, sc: Scenario, used: dict):
    """筋書きを1つ動かし、仕様と違えば (仕様, 実装) の説明を返す。"""
    world = World(spec, op, sc)
    data = {**sample_data(spec), **sc.data}
    want = [(s.kind, s.target) for s in op.steps if active(spec, s, data)]
    traces = []
    stopped = False
    for attempt in range(2 if sc.stop_after else 1):
        ctx = Context(spec, op, world, data)
        try:
            fn(ctx)
        except _Interrupted:
            stopped = True
            traces.append(ctx.trace)
            continue
        except NotPermitted as e:
            return "使ってよい外部作用に、仕様どおりのデータだけを渡す", str(e)
        except EffectFailure as e:
            return f"失敗 {e.key} を扱う（{op.on_failure.get(e.key, '扱いが書かれていません')}）", f"{e.key} を扱わずに止まった"
        except Exception as e:
            return "最後まで動く", f"例外 {type(e).__name__}: {e}"
        finally:
            for k, v in world.used.items():
                used[k] = v
        traces.append(ctx.trace)
        handled = ctx.handled_keys
        break
    else:
        return "止まったあと、もう一度動かせば残りをやり終える", "2回目も止まった"
    trace = traces[-1]

    if sc.failure is None and sc.decline is None:
        if not stopped and trace != want:
            i = next((i for i, (a, b) in enumerate(zip(want, trace)) if a != b), min(len(want), len(trace)))
            exp = f"{i + 1}番目に{_labels([want[i]])}" if i < len(want) else f"{len(want)}番目の手順で終わる"
            act = f"{i + 1}番目に{_labels([trace[i]])}" if i < len(trace) else f"{len(trace)}番目の手順で終わった"
            return exp, act
        if stopped:
            steps = [s for s in op.steps if active(spec, s, data)]
            missing = [_label(s) for s in steps if s.kind == "update" and s.target not in world.updates]
            missing += [_label(s) for s in steps if s.kind in ("call", "send")
                        and not any(e == s.target for e, _ in world.executions)]
            if missing:
                return "再開して残りの手順をやり終える", f"{'、'.join(missing)} をしないまま終わった"
        dup = _duplicates(spec, world)
        if dup:
            return f"{dup} は1回だけ実行する", f"{dup} を2回実行した"
        return None

    if sc.decline is not None:
        after = [t for t in trace[_nth_confirm(trace, sc.decline) + 1:]]
        if after:
            return "確認で断られたら、外部作用も状態の更新もしない", f"断られたあと {_labels(after)}"
        return None

    effect, kind = sc.failure
    key = f"{effect}.{kind}"
    if key not in handled:
        return f"失敗 {key} を扱う（{op.on_failure.get(key, '扱いが書かれていません')}）", "扱った記録（ctx.handled）がない"
    # 失敗した作用がその後成功していないなら、仕様でそれより後の手順に進んではいけない
    point = _failure_point(spec, op, effect)
    fail_at = next((i for i, t in enumerate(trace) if t == (point, effect)), None)
    idx = next((i for i, s in enumerate(op.steps) if (s.kind, s.target) == (point, effect)), None)
    if fail_at is None or idx is None:
        return None
    if sc.expect is not None:
        after = trace[fail_at + 1:]
        if after != sc.expect:
            i = next((i for i, (a, b) in enumerate(zip(sc.expect, after)) if a != b), min(len(sc.expect), len(after)))
            return (f"{key} のあと、仕様の手順どおり {_labels(sc.expect)}",
                    f"{_labels(after)}（{i + 1}つめから違う）")
        return None
    retried = any(t == (point, effect) for t in trace[fail_at + 1:])
    if not retried:
        later = {(s.kind, s.target) for s in op.steps[idx + 1:]}
        went = [t for t in trace[fail_at + 1:] if t in later]
        if went:
            return f"{effect} が失敗したら、その後の手順には進まない", f"失敗のあと {_labels(went)}"
    return None


def _nth_confirm(trace, n: int) -> int:
    count = -1
    for i, (k, _) in enumerate(trace):
        if k == "confirm":
            count += 1
            if count == n:
                return i
    return len(trace)


def _duplicates(spec: Spec, world: World) -> str:
    for effect, key in world.executions:
        info = spec.effect_info.get(effect)
        if info and info.reversible in ("no", "compensate") and world.executions.count((effect, key)) > 1:
            return effect
    return ""
