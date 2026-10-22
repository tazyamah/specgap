"""コマンドライン：python -m specgap <仕様ファイル> [--json]"""

from __future__ import annotations

import argparse
import sys

from .checks import check
from .model import SpecError, load
from .report import to_json, to_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="specgap", description="仕様の漏れを検査します")
    parser.add_argument("spec", help="仕様ファイル（YAML）")
    parser.add_argument("--json", action="store_true", help="JSON で出力する")
    args = parser.parse_args(argv)
    try:
        report = check(load(args.spec))
    except SpecError as e:
        print(f"仕様ファイルを読めません：{e}", file=sys.stderr)
        return 2
    print(to_json(report) if args.json else to_markdown(report))
    return 0 if report.ok else 1
