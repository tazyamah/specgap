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
class Operation:
    id: str
    uses: list[str]
    on_failure: dict[str, str]  # "効果名.失敗名" → 扱い


@dataclass
class Spec:
    name: str
    enums: dict[str, list[str]] = field(default_factory=dict)
    inputs: dict[str, Var] = field(default_factory=dict)
    outputs: dict[str, Var] = field(default_factory=dict)
    tables: list[Table] = field(default_factory=list)
    ensures: list[Ensure] = field(default_factory=list)
    machines: list[Machine] = field(default_factory=list)
    effects: dict[str, list[str]] = field(default_factory=dict)  # 効果名 → 失敗の種類
    operations: list[Operation] = field(default_factory=list)


def load(path: str | Path) -> Spec:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return parse(_fix_keys(data))


def _fix_keys(data: Any) -> Any:
    """YAML 1.1 では on: が真偽値のキーになるので、文字列に戻す。"""
    if isinstance(data, dict):
        return {("on" if k is True else "off" if k is False else k): _fix_keys(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_fix_keys(v) for v in data]
    return data


def parse(data: Any) -> Spec:
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
        spec.tables.append(Table(id=str(t["id"]), rows=rows, description=str(t.get("description", ""))))

    for e in data.get("ensures") or []:
        spec.ensures.append(Ensure(id=str(e["id"]), expr=str(e["expr"])))

    for m in data.get("machines") or []:
        spec.machines.append(_machine(m))

    for name, e in (data.get("effects") or {}).items():
        spec.effects[str(name)] = [str(x) for x in (e or {}).get("failures") or []]

    for o in data.get("operations") or []:
        spec.operations.append(
            Operation(
                id=str(o["id"]),
                uses=[str(u) for u in o.get("uses") or []],
                on_failure={str(k): str(v) for k, v in (o.get("on_failure") or {}).items()},
            )
        )
    return spec


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
