import argparse
import sys
import tempfile
from pathlib import Path

from .check import ERROR, check
from .examples import ExampleError, compare_examples, run_crate, runner_source, write_crate
from .parser import ParseError, parse
from .plan import EXAMPLE, UNSPEC, Finding, compare_static, read_plan
from .lexer import LexError
from .rustgen import generate
from .spec import build, render


def load(path):
    try:
        return check(parse(Path(path).read_text()))
    except (ParseError, LexError) as e:
        print(f"構文エラー: {e}", file=sys.stderr)
        sys.exit(2)


def report(findings) -> str:
    if not findings:
        return "突合の結果: 計画とコードに食い違いはありません。\n"
    out = ["突合の結果", "", "| 種別 | 場所 | 内容 |", "|---|---|---|"]
    out += [f"| {f.kind} | {f.where} | {f.msg} |" for f in findings]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="specgap_lang", description="独自構文の検査・Rust生成・plan突合（試作）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="コードを検査する")
    c.add_argument("code")
    s = sub.add_parser("spec", help="コードから仕様書（③）を生成する")
    s.add_argument("code")
    s.add_argument("-o")
    r = sub.add_parser("rust", help="Rust の crate を生成する")
    r.add_argument("code")
    r.add_argument("-o", required=True)
    r.add_argument("--plan", help="具体例の実行用 bin も生成する")
    m = sub.add_parser("compare", help="plan の仕様書（①）とコードの突合。具体例も実行する")
    m.add_argument("code")
    m.add_argument("plan")
    m.add_argument("--no-run", action="store_true", help="具体例を実行しない（静的な突合だけ）")
    m.add_argument("-o", help="結果を Markdown で書き出す")
    a = ap.parse_args(argv)

    ck = load(a.code)
    if a.cmd == "check":
        for d in ck.diags:
            print(d)
        print("検査: " + ("通りました" if ck.ok else "エラーがあります"))
        return 0 if ck.ok else 1
    if a.cmd == "spec":
        text = render(ck, build(ck), f"（{Path(a.code).name}）")
        Path(a.o).write_text(text) if a.o else print(text)
        return 0 if ck.ok else 1
    if not ck.ok:
        for d in ck.diags:
            print(d)
        print("検査にエラーがあるので、続けません。", file=sys.stderr)
        return 1
    lib = generate(ck)
    if a.cmd == "rust":
        rows = read_plan(Path(a.plan).read_text()).get("具体例", []) if a.plan else []
        src, problems = runner_source(ck, rows)
        for p in problems:
            print(f"{p.kind}: {p.where}: {p.msg}")
        write_crate(ck, lib, src, Path(a.o))
        print(f"生成しました: {a.o}")
        return 0
    plan = read_plan(Path(a.plan).read_text())
    findings = compare_static(build(ck), plan)
    rows = plan.get("具体例", [])
    src, problems = runner_source(ck, rows)
    findings += problems
    if not a.no_run and rows:
        with tempfile.TemporaryDirectory() as tmp:
            write_crate(ck, lib, src, Path(tmp))
            try:
                findings += compare_examples(rows, run_crate(Path(tmp)))
            except ExampleError as e:
                findings.append(Finding(EXAMPLE, "具体例の実行", str(e)))
    text = report(findings)
    print(text)
    if a.o:
        Path(a.o).write_text(text)
    return 1 if any(f.kind != UNSPEC for f in findings) else 0
