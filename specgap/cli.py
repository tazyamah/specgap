"""コマンドライン

  python -m specgap check <仕様> [--json] [--impl <実装>]   漏れを検査し、実装が仕様どおりかを確かめる
  python -m specgap view <仕様> [--base <前の版>] [--impl <実装>] -o out.html  人向けのレビュー画面を作る
  python -m specgap <仕様>                                 check と同じ
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from .checks import check
from .diff import diff
from .guarantee import apply, verify
from .model import SpecError, load
from .report import to_json, to_markdown
from .view import render


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in ("check", "view", "-h", "--help"):
        argv.insert(0, "check")
    parser = argparse.ArgumentParser(prog="specgap", description="仕様の漏れを検査し、人向けのレビュー画面を作ります")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="仕様の漏れを検査する")
    c.add_argument("spec", help="仕様ファイル（YAML）")
    c.add_argument("--json", action="store_true", help="JSON で出力する")
    c.add_argument("--impl", help="implementation の実装ファイルの代わりに確かめるファイル")
    v = sub.add_parser("view", help="人向けのレビュー画面（HTML）を作る")
    v.add_argument("spec", help="仕様ファイル（YAML）")
    v.add_argument("--base", help="比較する前の版の仕様ファイル")
    v.add_argument("--impl", help="implementation の実装ファイルの代わりに確かめるファイル")
    v.add_argument("-o", "--output", help="出力先（省略時は標準出力）")
    v.add_argument("--fragment", action="store_true", help="html/head/body を付けずに出力する（Artifact 用）")
    args = parser.parse_args(argv)

    try:
        spec = load(args.spec)
        base = load(args.base) if getattr(args, "base", None) else None
    except SpecError as e:
        print(f"仕様ファイルを読めません：{e}", file=sys.stderr)
        return 2
    report = check(spec)
    if spec.implementation is not None or args.impl:
        try:
            apply(report, verify(spec, args.impl, base=base))
        except SpecError as e:
            print(f"実装を確かめられません：{e}", file=sys.stderr)
            return 2

    if args.cmd == "check":
        print(to_json(report) if args.json else to_markdown(report))
        return 0 if report.ok else 1

    files = [args.spec] + ([args.base] if args.base else [])
    impl = args.impl or (spec.implementation.module if spec.implementation else None)
    files += [impl] if impl else []
    sources = [(Path(f).name, hashlib.sha256(Path(f).read_bytes()).hexdigest()) for f in files]
    html = render(spec, report, base=base, change=diff(base, spec) if base else None,
                  fragment=args.fragment, sources=sources)
    if args.output:
        Path(args.output).write_text(html, encoding="utf-8")
    else:
        print(html)
    return 0
