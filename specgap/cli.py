"""コマンドライン

  python -m specgap check <仕様> [--json] [--impl <実装>]   漏れを検査し、実装が仕様どおりかを確かめる
  python -m specgap view <仕様> [--base <前の版>] [--impl <実装>] -o out.html  人向けのレビュー画面を作る
  python -m specgap questions <仕様>                       答えると正本を直せる問いに番号を付けて並べる
  python -m specgap answer <仕様> <答え> -o <新しい版>      答えを正本に書き込み、新しい版を検査する
  python -m specgap ask <仕様> [-o <作業中の版>]            次の1問を、会話で聞くための包みにして出す
  python -m specgap reply <仕様> [-o <作業中の版>] <問い> <答え> [--said <人の言葉>]
                                                           答えを1つ反映して検査し直し、次の1問を出す
  python -m specgap mcp                                    AI から ask・reply を使う MCP サーバー
  python -m specgap <仕様>                                 check と同じ
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from . import answer as answering
from . import ask as asking
from .checks import check
from .diff import diff
from .guarantee import apply, verify
from .model import SpecError, load
from .report import to_json, to_markdown
from .view import render


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in ("check", "view", "questions", "answer", "ask", "reply", "mcp", "-h", "--help"):
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
    q = sub.add_parser("questions", help="答えると正本を直せる問いを、番号と答え方つきで並べる")
    q.add_argument("spec", help="仕様ファイル（YAML）")
    a = sub.add_parser("answer", help="問いへの答えを正本に書き込み、新しい版を作って検査する")
    a.add_argument("spec", help="仕様ファイル（YAML）")
    a.add_argument("answers", help="答えのファイル（YAML）")
    a.add_argument("-o", "--output", required=True, help="新しい版の書き出し先")
    for name, help_ in (("ask", "次の1問を、会話で聞くための包みにして出す"),
                        ("reply", "答えを1つ反映して検査し直し、次の1問を出す")):
        k = sub.add_parser(name, help=help_)
        k.add_argument("spec", help="元の仕様ファイル（書き換えない）")
        k.add_argument("-o", "--work", help="作業中の版（省略時は <仕様>.work.yaml。無ければ元の仕様から始める）")
        if name == "reply":
            k.add_argument("question", help="問いの識別子（Q で始まる）")
            k.add_argument("answer", help="答え（値・式・選択肢。{出力名: 値} の形も可）")
            k.add_argument("--said", default="", help="人が会話で言った言葉（記録に残す）")
    sub.add_parser("mcp", help="AI から ask・reply を使う MCP サーバー（標準入出力）")
    args = parser.parse_args(argv)
    if args.cmd in ("questions", "answer"):
        return _answering(args)
    if args.cmd in ("ask", "reply"):
        return _asking(args)
    if args.cmd == "mcp":
        from .mcp_server import serve
        serve()
        return 0

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


def _answering(args) -> int:
    try:
        spec = load(args.spec)
    except SpecError as e:
        print(f"仕様ファイルを読めません：{e}", file=sys.stderr)
        return 2
    report = check(spec)
    qs = answering.questions(report)
    if args.cmd == "questions":
        if not qs:
            print("答えると正本を直せる問いはありません。")
        for x in qs:
            print(f"{x.no}. {x.question}")
            print(f"   答え方：{x.how}")
            print(f"   答えると：{x.effect}")
        return 0
    name, answers = answering.load_answers(args.answers)
    res = answering.apply(args.spec, spec, report, answers, name=name)
    for line in res.applied:
        print(f"反映：{line}")
    for line in res.errors:
        print(f"反映できません：{line}", file=sys.stderr)
    if res.errors:
        return 2
    Path(args.output).write_text(res.text, encoding="utf-8")
    try:
        new = load(args.output)
    except SpecError as e:
        print(f"新しい版を読めません：{e}", file=sys.stderr)
        return 2
    after = check(new)
    left = answering.questions(after)
    errors = [f for f in after.findings if f.severity == "error"]
    print(f"新しい版：{args.output}（{'受け入れ可' if after.ok else '拒否'}、拒否 {len(errors)} 件・残りの問い {len(left)} 件）")
    for x in left:
        print(f"  {x.no}. {x.question}")
    return 0 if after.ok else 1


def _asking(args) -> int:
    session = asking.session(args.spec, args.work)
    try:
        if args.cmd == "ask":
            p, report = asking.next_packet(session)
            print(asking.to_text(p, report))
            return 0
        text, ok = asking.reply(session, args.question, asking.parse_answer(args.answer), args.said)
    except SpecError as e:
        print(f"仕様ファイルを読めません：{e}", file=sys.stderr)
        return 2
    print(text)
    return 0 if ok else 1
