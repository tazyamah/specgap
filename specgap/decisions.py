"""判断（decisions）を扱う。正本のどこに効いているかを引き、ADR 形式の Markdown に書き出す。"""

from __future__ import annotations

from pathlib import Path

from .model import Decision, Spec


def exists(spec: Spec, ref: str) -> bool:
    """applies_to の1つが、今の正本にまだあるか。"""
    kind, _, rest = ref.partition(":")
    parts = rest.split(":")
    if kind == "表":
        t = next((x for x in spec.tables if x.id == parts[0]), None)
        if t is None:
            return False
        when = ":".join(parts[1:])
        return t.by_cells if when == "by_cells" else any(r.when == when for r in t.rows)
    if kind == "ルール":
        return any(r.id == rest for r in spec.rules)
    if kind == "状態機械":
        m = next((x for x in spec.machines if x.id == parts[0]), None)
        return m is not None and len(parts) == 3 and any(
            x.src == parts[1] and x.event == parts[2] for x in [*m.transitions, *m.rejects])
    if kind == "操作":
        op = next((x for x in spec.operations if x.id == parts[0]), None)
        if op is None:
            return False
        if len(parts) == 1:
            return True
        if parts[1] == "失敗":
            return ":".join(parts[2:]) in op.on_failure
        if parts[1] == "途中停止":
            return bool(op.on_interrupt)
        if parts[1] == "手順" and len(parts) >= 4:
            return any(st.kind == parts[2] and st.target == ":".join(parts[3:]) for st in op.steps)
        return False
    if kind == "正本":
        return True  # 道筋で書いた参照は、ここでは確かめない
    if kind == "確認":
        return True  # 確認の項目は検査の結果なので、ここでは確かめない
    if kind == "データ":
        return rest in spec.data_items
    if kind == "外部作用":
        return parts[0] in spec.effect_info
    if kind == "許可":
        return rest in spec.data_allow
    return False


def current(spec: Spec) -> list[Decision]:
    """置き換えられていない判断。"""
    replaced = {x for d in spec.decisions for x in d.supersedes}
    return [d for d in spec.decisions if d.id not in replaced]


def for_ref(spec: Spec, prefix: str) -> list[Decision]:
    """applies_to が prefix で始まる、今も有効な判断。"""
    return [d for d in current(spec) if any(r == prefix or r.startswith(prefix + ":") for r in d.applies_to)]


def for_table_row(spec: Spec, table: str, when: str) -> list[Decision]:
    """表の行と、その表に効くルールの判断（行の値の理由）。"""
    from .rules import tables_for

    out = [d for d in current(spec) if f"表:{table}:{when}" in d.applies_to]
    t = next(x for x in spec.tables if x.id == table)
    for r in spec.rules:
        if t in tables_for(spec, r):
            out += [d for d in current(spec) if f"ルール:{r.id}" in d.applies_to and d not in out]
    return out


def to_markdown(spec: Spec, d: Decision) -> str:
    replaced_by = [x.id for x in spec.decisions if d.id in x.supersedes]
    state = f"置き換え済み（{'・'.join(replaced_by)}）" if replaced_by else "有効"
    lines = [f"# {d.id}: {d.title or d.answer}", "", f"- 状態: {state}", f"- 日付: {d.at or '不明'}"]
    if d.supersedes:
        lines.append("- 置き換えた判断: " + "、".join(f"[{x}]({x}.md)" for x in d.supersedes))
    lines += ["", "## 問い", "", d.question, "", "## 決めたこと", "", d.answer]
    if d.said:
        lines += ["", "## 人の言葉", ""] + [f"> {x}" for x in d.said.splitlines()]
    if d.assumptions:
        lines += ["", "## 前提", ""] + [f"- {x}" for x in d.assumptions]
    lines += ["", "## 正本で効いている場所", ""]
    for ref in d.applies_to:
        lines.append(f"- `{ref}`" + ("" if exists(spec, ref) else "（今の正本にはありません）"))
    return "\n".join(lines) + "\n"


def export(spec: Spec, out_dir: str | Path) -> list[Path]:
    """判断ごとの Markdown と一覧（README.md）を書き出す。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for d in spec.decisions:
        p = out / f"{d.id}.md"
        p.write_text(to_markdown(spec, d), encoding="utf-8")
        paths.append(p)
    live = {d.id for d in current(spec)}
    index = [f"# 判断の記録：{spec.name}", "", "問いに答えて決めたことの一覧です。正本（仕様ファイル）から生成しています。", "",
             "| 判断 | 決めたこと | 日付 | 状態 |", "|---|---|---|---|"]
    for d in spec.decisions:
        title = (d.title or d.answer).replace("|", "｜")
        index.append(f"| [{d.id}]({d.id}.md) | {title} | {d.at} | {'有効' if d.id in live else '置き換え済み'} |")
    readme = out / "README.md"
    readme.write_text("\n".join(index) + "\n", encoding="utf-8")
    return [readme, *paths]
