"""検査結果を人が読む形（Markdown）と機械が読む形（JSON）に整える。"""

from __future__ import annotations

import json
from dataclasses import asdict

from .checks import ERROR, INFO, WARNING, Report

_SECTIONS = [
    (ERROR, "拒否：直さないと受け入れられない漏れ"),
    (WARNING, "確認：人が判断する項目"),
    (INFO, "記録：意図的に決めていない箇所"),
]


def to_markdown(report: Report) -> str:
    lines = [f"# 仕様の漏れ検査：{report.spec}", ""]
    counts = {s: sum(1 for f in report.findings if f.severity == s) for s, _ in _SECTIONS}
    verdict = "受け入れ可" if report.ok else "拒否"
    lines.append(f"判定：**{verdict}**（拒否 {counts[ERROR]} 件・確認 {counts[WARNING]} 件・記録 {counts[INFO]} 件）")
    lines.append("")
    for severity, heading in _SECTIONS:
        items = [f for f in report.findings if f.severity == severity]
        if not items:
            continue
        lines += [f"## {heading}", ""]
        for i, f in enumerate(items, start=1):
            lines.append(f"{i}. **{f.title}**")
            if f.detail:
                lines.append(f"    - {f.detail}")
            if f.question:
                lines.append(f"    - 問い：{f.question}")
        lines.append("")
    g = report.guarantee
    if g is not None:
        lines += [f"## 実装が仕様どおりか（{g.module}）", "",
                  "| 仕様の項目 | 実装 | 事前の保証 | 実行時 | 根拠 | 方針 |", "| --- | --- | --- | --- | --- | --- |"]
        for it in g.items:
            basis = it.basis
            if it.example:
                basis = it.explain()
            before = f"（前の版：{it.before}）" if it.before and it.before != it.label else ""
            lines.append(
                f"| {it.kind}「{it.id}」 | {it.function or '—'} | {it.level}{before} | {'監視あり' if it.monitored else '—'} "
                f"| {basis} | {it.required}{'' if it.meets else ' ✗'} |"
            )
        lines.append("")
        ops = [it for it in g.items if it.kind == "操作" and it.uses]
        if ops:
            lines += ["### 操作の実装が使う外部作用（実行して確かめた権限）", "",
                      "| 操作 | 外部作用 | 渡したデータ |", "| --- | --- | --- |"]
            for it in ops:
                for e, d in it.uses.items():
                    lines.append(f"| {it.id} | {e} | {'・'.join(d) or '—'} |")
            lines.append("")
    if report.passed:
        lines += ["## 問題がなかった検査", ""]
        lines += [f"- {name}" for name in report.passed]
        lines.append("")
    return "\n".join(lines)


def _kv(d: dict[str, str]) -> str:
    return "、".join(f"{k}={v}" for k, v in d.items())


def to_json(report: Report) -> str:
    data = {
        "spec": report.spec,
        "ok": report.ok,
        "findings": [asdict(f) for f in report.findings],
        "passed": report.passed,
    }
    if report.guarantee is not None:
        data["guarantee"] = asdict(report.guarantee)
    return json.dumps(data, ensure_ascii=False, indent=2)
