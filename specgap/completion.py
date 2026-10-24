"""完成の判定。正本と検査だけでアプリを作り切ったと言えるかを、決めた条件で判定する。

条件（2026-10-24 に決めたゴール）：
- 拒否と確認が 0 件
- 表・状態機械・性質・操作がすべてテスト済み以上
- どのユースケースもテスト済み以上の保証を持つ
範囲外：画面そのものの実装と、途中で止まったときの担当者の作業手順（文章のまま）。
"""

from __future__ import annotations

from .checks import ERROR, WARNING, Report
from .guarantee import LEVELS, TESTED


def unmet(report: Report) -> list[str]:
    """完成に足りないこと。空なら完成。"""
    out = []
    errors = sum(1 for f in report.findings if f.severity == ERROR)
    warns = sum(1 for f in report.findings if f.severity == WARNING)
    if errors:
        out.append(f"拒否が {errors} 件あります")
    if warns:
        out.append(f"確認が {warns} 件あります")
    g = report.guarantee
    if g is None:
        out.append("実装が書かれていないので、保証を確かめていません")
        return out
    weak = [f"{it.kind}「{it.id}」（{it.level if it.function else '実装なし'}）" for it in g.items
            if not it.function or LEVELS.index(it.level) < LEVELS.index(TESTED)]
    if weak:
        out.append("テスト済みに届かない項目：" + "、".join(weak))
    weak = [f"「{u.id}」（{u.level}）" for u in g.usecases if LEVELS.index(u.level) < LEVELS.index(TESTED)]
    if weak:
        out.append("保証のないユースケース：" + "、".join(weak))
    return out


def summary(report: Report) -> str:
    rest = unmet(report)
    if not rest:
        return "完成（拒否・確認 0 件、項目とユースケースはすべてテスト済み以上）"
    return "未完成（" + "。".join(rest) + "）"
