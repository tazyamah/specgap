"""仕様ファイル（YAML）を読み込み、検査用のデータ構造に変換する。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# 結果に書くと「意図的に決めない」を表す値
UNSPECIFIED = "unspecified"


class SpecError(Exception):
    """仕様ファイルの書式が正しくないときの例外。"""


@dataclass
class Var:
    name: str
    type: str  # "int" / "bool" / 列挙型の名前
    min: int | None = None
    max: int | None = None
    description: str = ""
    example: str | None = None  # 具体例を作るときに使う代表値


@dataclass
class Row:
    index: int  # 表の中での行番号（1始まり）
    when: str
    then: dict[str, str]  # 出力名 → 式、または UNSPECIFIED


@dataclass
class Table:
    id: str
    rows: list[Row]
    description: str = ""
    by_cells: bool = False  # ルールから組み立てず、穴を1つずつ聞く

    @property
    def outputs(self) -> list[str]:
        names: list[str] = []
        for row in self.rows:
            for name in row.then:
                if name not in names:
                    names.append(name)
        return names


@dataclass
class Ensure:
    id: str
    expr: str


@dataclass
class Rule:
    """表の根底にあるルール。表の2つの入力を比べる形で書き、機械が表と照らし合わせる。

    傾向：by が増える（列挙なら定義の順に進む）と、outputs は trend の向きに動く（減る・増える・関係ない・場合による）
    関係：by が src のときの値から、by が dst のときの値が then で決まる（then の中の出力名は src のときの値。「同じ」も可）
    """
    id: str
    outputs: list[str]
    by: str
    trend: str = ""
    src: str = ""
    dst: str = ""  # 整数なら「30」か「30..45」
    then: str = ""


TRENDS = ("減る", "増える", "関係ない", "場合による")
UNDECIDED = "決めない"
SAME = "同じ"


@dataclass
class Transition:
    src: str
    event: str
    dst: str


@dataclass
class Reject:
    src: str
    event: str
    reason: str


@dataclass
class Machine:
    id: str
    states: list[str]
    events: list[str]
    initial: str
    final: list[str]
    transitions: list[Transition]
    rejects: list[Reject]


@dataclass
class Step:
    kind: str  # confirm / call / send / await / update
    target: str  # call・send・await は外部作用の名前、confirm・update は説明文


STEP_KINDS = ("confirm", "call", "send", "await", "update")


@dataclass
class Operation:
    id: str
    uses: list[str]
    on_failure: dict[str, str]  # "効果名.失敗名" → 扱い
    steps: list[Step] = field(default_factory=list)
    on_interrupt: str = ""  # 途中で止まったときの扱い


@dataclass
class System:
    name: str
    description: str = ""
    kind: str = "外部"  # 外部 / 社内


@dataclass
class EffectInfo:
    """外部作用の連携情報。"""
    name: str
    system: str = ""
    mode: str = "sync"  # sync（応答を待つ）/ async（送るだけ。結果は後で届く）
    sends: list[str] = field(default_factory=list)
    receives: list[str] = field(default_factory=list)
    reversible: str = ""  # yes / no / compensate
    compensate: str = ""  # reversible が compensate のときの取り消し用の外部作用
    idempotency: str = ""  # 二重実行を防ぐキー


@dataclass
class UseCase:
    id: str
    actor: str
    description: str = ""
    uses: list[str] = field(default_factory=list)  # 関係する表・状態機械・操作の id


@dataclass
class ScreenStep:
    src: str
    action: str
    dst: str
    usecase: str | None = None


@dataclass
class ScreenFlow:
    id: str
    start: str
    screens: list[str]
    final: list[str]
    steps: list[ScreenStep]


@dataclass
class Implementation:
    """仕様の項目と、それを実装した関数の対応。"""
    module: Path  # 実装ファイル（仕様ファイルからの相対パスを解決したもの）
    tables: dict[str, str] = field(default_factory=dict)  # 表の id → 関数名
    machines: dict[str, str] = field(default_factory=dict)  # 状態機械の id → 関数名
    operations: dict[str, str] = field(default_factory=dict)  # 操作の id → 関数名


@dataclass
class Spec:
    name: str
    enums: dict[str, list[str]] = field(default_factory=dict)
    inputs: dict[str, Var] = field(default_factory=dict)
    outputs: dict[str, Var] = field(default_factory=dict)
    tables: list[Table] = field(default_factory=list)
    ensures: list[Ensure] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    machines: list[Machine] = field(default_factory=list)
    effects: dict[str, list[str]] = field(default_factory=dict)  # 効果名 → 失敗の種類
    operations: list[Operation] = field(default_factory=list)
    actors: dict[str, str] = field(default_factory=dict)  # アクター名 → 説明
    usecases: list[UseCase] = field(default_factory=list)
    screen_flows: list[ScreenFlow] = field(default_factory=list)
    systems: dict[str, System] = field(default_factory=dict)
    effect_info: dict[str, EffectInfo] = field(default_factory=dict)
    data_classes: list[str] = field(default_factory=list)
    data_items: dict[str, str] = field(default_factory=dict)  # データ項目 → 区分
    data_allow: dict[str, list[str]] = field(default_factory=dict)  # システム → 渡してよい区分
    implementation: Implementation | None = None
    policy: dict[str, str] = field(default_factory=dict)  # 項目（または default）→ 必要な保証


def load(path: str | Path) -> Spec:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return parse(_fix_keys(data), base_dir=Path(path).parent)


def _fix_keys(data: Any) -> Any:
    """YAML 1.1 では on: が真偽値のキーになるので、文字列に戻す。"""
    if isinstance(data, dict):
        return {("on" if k is True else "off" if k is False else k): _fix_keys(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_fix_keys(v) for v in data]
    return data


def parse(data: Any, base_dir: str | Path = ".") -> Spec:
    if not isinstance(data, dict) or "spec" not in data:
        raise SpecError("先頭に spec: <仕様名> が必要です")
    spec = Spec(name=str(data["spec"]))

    for name, members in (data.get("enums") or {}).items():
        if not isinstance(members, list) or not members:
            raise SpecError(f"列挙型 {name} には1つ以上の値が必要です")
        spec.enums[str(name)] = [str(m) for m in members]

    spec.inputs = _vars(data.get("inputs") or {}, spec, "入力")
    spec.outputs = _vars(data.get("outputs") or {}, spec, "出力")

    for t in data.get("tables") or []:
        rows = []
        for i, r in enumerate(t.get("rows") or [], start=1):
            if "when" not in r or "then" not in r:
                raise SpecError(f"表 {t.get('id')} の {i} 行目には when と then が必要です")
            then = {str(k): str(v) for k, v in (r["then"] or {}).items()}
            rows.append(Row(index=i, when=str(r["when"]), then=then))
        spec.tables.append(Table(id=str(t["id"]), rows=rows, description=str(t.get("description", "")),
                                 by_cells=bool(t.get("by_cells", False))))

    for e in data.get("ensures") or []:
        spec.ensures.append(Ensure(id=str(e["id"]), expr=str(e["expr"])))

    for r in data.get("rules") or []:
        spec.rules.append(_rule(r, spec))

    for m in data.get("machines") or []:
        spec.machines.append(_machine(m))

    for name, sys_ in (data.get("systems") or {}).items():
        sys_ = sys_ or {}
        if isinstance(sys_, str):
            sys_ = {"description": sys_}
        spec.systems[str(name)] = System(str(name), str(sys_.get("description", "")), str(sys_.get("kind", "外部")))

    d = data.get("data") or {}
    spec.data_classes = [str(c) for c in d.get("classes") or []]
    spec.data_items = {str(k): str(v) for k, v in (d.get("items") or {}).items()}
    spec.data_allow = {str(k): [str(c) for c in v or []] for k, v in (d.get("allow") or {}).items()}

    for name, e in (data.get("effects") or {}).items():
        e = e or {}
        spec.effects[str(name)] = [str(x) for x in e.get("failures") or []]
        spec.effect_info[str(name)] = EffectInfo(
            name=str(name),
            system=str(e.get("system", "")),
            mode=str(e.get("mode", "sync")),
            sends=[str(x) for x in e.get("sends") or []],
            receives=[str(x) for x in e.get("receives") or []],
            reversible=_yes_no(e.get("reversible", "")),
            compensate=str(e.get("compensate", "")),
            idempotency=str(e.get("idempotency", "")),
        )

    for o in data.get("operations") or []:
        steps = []
        for i, st in enumerate(o.get("steps") or [], start=1):
            if not isinstance(st, dict) or len(st) != 1:
                raise SpecError(f"操作 {o['id']} の手順 {i} は「種類: 対象」の1組で書いてください")
            (kind, target), = st.items()
            if kind not in STEP_KINDS:
                raise SpecError(f"操作 {o['id']} の手順 {i} の種類 {kind} は使えません（{' / '.join(STEP_KINDS)}）")
            steps.append(Step(str(kind), str(target)))
        uses = [str(u) for u in o.get("uses") or []]
        for st in steps:
            if st.kind in ("call", "send", "await") and st.target not in uses:
                uses.append(st.target)
        spec.operations.append(
            Operation(
                id=str(o["id"]),
                uses=uses,
                on_failure={str(k): str(v) for k, v in (o.get("on_failure") or {}).items()},
                steps=steps,
                on_interrupt=str(o.get("on_interrupt", "")),
            )
        )
    for name, desc in (data.get("actors") or {}).items():
        spec.actors[str(name)] = "" if desc is None else str(desc)

    for u in data.get("usecases") or []:
        spec.usecases.append(
            UseCase(
                id=str(u["id"]),
                actor=str(u.get("actor", "")),
                description=str(u.get("description", "")),
                uses=[str(x) for x in u.get("uses") or []],
            )
        )

    for f in data.get("screens") or []:
        steps = [
            ScreenStep(src=str(t["from"]), action=str(t["action"]), dst=str(t["to"]),
                       usecase=str(t["usecase"]) if t.get("usecase") else None)
            for t in f.get("transitions") or []
        ]
        names = [str(f["start"])]
        for n in [*(f.get("screens") or []), *[x for st in steps for x in (st.src, st.dst)]]:
            if str(n) not in names:
                names.append(str(n))
        spec.screen_flows.append(
            ScreenFlow(id=str(f["id"]), start=str(f["start"]), screens=names,
                       final=[str(x) for x in f.get("final") or []], steps=steps)
        )

    impl = data.get("implementation")
    if impl:
        if "module" not in impl:
            raise SpecError("implementation には module（実装ファイル）が必要です")
        spec.implementation = Implementation(
            module=Path(base_dir) / str(impl["module"]),
            tables={str(k): str(v) for k, v in (impl.get("tables") or {}).items()},
            machines={str(k): str(v) for k, v in (impl.get("machines") or {}).items()},
            operations={str(k): str(v) for k, v in (impl.get("operations") or {}).items()},
        )
    spec.policy = {str(k): str(v) for k, v in (data.get("policy") or {}).items()}
    return spec


def _rule(r: dict, spec: Spec) -> Rule:
    rid = str(r.get("id", ""))
    outs = r.get("output")
    outs = [str(x) for x in outs] if isinstance(outs, list) else [str(outs)]
    for o in outs:
        if o not in spec.outputs:
            raise SpecError(f"ルール「{rid}」の出力 {o} が定義されていません")
    by = str(r.get("by", ""))
    if by not in spec.inputs:
        raise SpecError(f"ルール「{rid}」の by（{by}）が入力にありません")
    rule = Rule(rid, outs, by, trend=str(r.get("trend", "")), src=str(r.get("from", "")),
                dst=str(r.get("to", "")), then=str(r.get("then", "")))
    if rule.trend:
        if rule.trend not in TRENDS:
            raise SpecError(f"ルール「{rid}」の trend は {'・'.join(TRENDS)} のどれかです")
    elif not (rule.src and rule.dst and rule.then):
        raise SpecError(f"ルール「{rid}」には trend か、from・to・then が必要です")
    return rule


def _yes_no(v: Any) -> str:
    """YAML 1.1 は yes / no を真偽値として読むので、文字列に戻す。"""
    if v is True:
        return "yes"
    if v is False:
        return "no"
    return str(v)


def _vars(raw: dict, spec: Spec, label: str) -> dict[str, Var]:
    result: dict[str, Var] = {}
    for name, v in raw.items():
        if isinstance(v, str):
            v = {"type": v}
        typ = str(v.get("type", "int"))
        if typ not in ("int", "bool") and typ not in spec.enums:
            raise SpecError(f"{label} {name} の型 {typ} が定義されていません")
        result[str(name)] = Var(
            name=str(name),
            type=typ,
            min=v.get("min"),
            max=v.get("max"),
            description=str(v.get("description", "")),
            example=None if v.get("example") is None else str(v.get("example")),
        )
    return result


def _machine(m: dict) -> Machine:
    def as_list(x: Any) -> list[str]:
        return [str(i) for i in x] if isinstance(x, list) else [str(x)]

    transitions = [
        Transition(src=str(t["from"]), event=str(t["on"]), dst=str(t["to"])) for t in m.get("transitions") or []
    ]
    rejects = []
    for r in m.get("rejects") or []:
        for src in as_list(r["from"]):
            for ev in as_list(r["on"]):
                rejects.append(Reject(src=src, event=ev, reason=str(r.get("reason", ""))))
    return Machine(
        id=str(m["id"]),
        states=as_list(m["states"]),
        events=as_list(m["events"]),
        initial=str(m["initial"]),
        final=as_list(m.get("final") or []),
        transitions=transitions,
        rejects=rejects,
    )
