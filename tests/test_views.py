from pathlib import Path

from specgap import ERROR, WARNING, check, load, parse
from specgap.cli import main
from specgap.diff import ADDED, REMOVED, diff
from specgap.examples import NO_ROW, Examples
from specgap.view import prettify, render

EXAMPLES = Path(__file__).parent.parent / "examples"


def titles(report, severity):
    return [f.title for f in report.findings if f.severity == severity]


# ---- ユースケースと画面の検査 ----


def test_通販の修正後は受け入れ可():
    assert check(load(EXAMPLES / "shop_v2.yaml")).ok


def test_行き止まりの画面を確認に回す():
    r = check(load(EXAMPLES / "shop_v1.yaml"))
    assert any("申込完了 から先へ進む操作も戻る操作もありません" in t for t in titles(r, WARNING))


def test_未定義のアクターとユースケースを拒否する():
    s = {"spec": "x", "actors": {"客": ""}, "usecases": [{"id": "買う", "actor": "店員"}],
         "screens": [{"id": "画面", "start": "A", "final": ["B"],
                      "transitions": [{"from": "A", "action": "押す", "to": "B", "usecase": "売る"}]}]}
    r = check(parse(s))
    errs = titles(r, ERROR)
    assert any("アクター 店員 が定義されていません" in t for t in errs)
    assert any("未定義のユースケース 売る" in t for t in errs)
    ws = titles(r, WARNING)
    assert any("アクター 客 が行うユースケースがありません" in t for t in ws)
    assert any("「買う」を始める画面上の操作がありません" in t for t in ws)


def test_同じ操作で行き先が複数ある画面を拒否する():
    s = {"spec": "x", "screens": [{"id": "画面", "start": "A", "final": ["B", "C"], "transitions": [
        {"from": "A", "action": "押す", "to": "B"}, {"from": "A", "action": "押す", "to": "C"}]}]}
    assert any("行き先が複数あります" in t for t in titles(check(parse(s)), ERROR))


def test_誰も行わない操作を確認に回す():
    s = {"spec": "x", "actors": {"客": ""}, "usecases": [{"id": "買う", "actor": "客"}],
         "operations": [{"id": "返金", "uses": []}]}
    assert any("操作「返金」を行うユースケースがありません" in t for t in titles(check(parse(s)), WARNING))


# ---- 具体例 ----


def test_具体例は各行の境界と代表値を使う():
    spec = load(EXAMPLES / "shop_v2.yaml")
    x = Examples(spec)
    exs = x.for_table(spec.tables[0])
    days = {(e.row, e.inputs["経過日数"]) for e in exs}
    assert {(1, "0"), (1, "14"), (3, "15"), (3, "30"), (4, "31")} <= days
    assert all(e.inputs["支払額"] == "10000" for e in exs)  # example: 10000 を使う
    assert any(e.outputs["返金額"] == "5000" for e in exs)


def test_どの行にも当たらない入力を計算できる():
    spec = load(EXAMPLES / "shop_v1.yaml")
    e = Examples(spec).evaluate(spec.tables[0], {"経過日数": "30", "商品状態": "未開封"})
    assert e.row is None and e.outputs["返金額"] == NO_ROW


# ---- 差分 ----


def test_差分は構造の変化と結果の変化を出す():
    d = diff(load(EXAMPLES / "shop_v1.yaml"), load(EXAMPLES / "shop_v2.yaml"))
    texts = {(c.kind, c.area, c.text) for c in d.changes}
    assert (ADDED, "ユースケース", "購入者が「返金状況を確認する」") in texts
    assert (ADDED, "状態", "注文：発送済み →「キャンセル」→ 返品待ち") in texts
    assert any(k == REMOVED and a == "決定表" for k, a, _ in texts)
    changed = {(b.inputs["経過日数"], b.inputs["商品状態"]): (b.before["返金額"], b.after["返金額"]) for b in d.behavior}
    assert changed[("15", "未開封")] == ("10000", "5000")  # 全額返金の期間を14日に短くした
    assert changed[("30", "未開封")] == (NO_ROW, "5000")  # 前は決まっていなかった


def test_同じ版どうしの差分は空():
    s = load(EXAMPLES / "shop_v2.yaml")
    assert diff(s, load(EXAMPLES / "shop_v2.yaml")).empty


# ---- 画面の生成 ----


def test_画面には問い_図_表が入る():
    spec = load(EXAMPLES / "shop_v1.yaml")
    html = render(spec, check(spec))
    assert html.startswith("<!doctype html>")
    for text in ["答えてほしいこと", "誰が何をするか", "画面の流れ：購入者の画面", "状態の移り変わり：注文",
                 "外部とのやりとりが失敗したとき", "どの行にも当たらない", "<svg"]:
        assert text in html
    assert "前の版からの変更" not in html


def test_差分付きの画面には変更点が入る():
    base, head = load(EXAMPLES / "shop_v1.yaml"), load(EXAMPLES / "shop_v2.yaml")
    html = render(head, check(head), base=base, change=diff(base, head), fragment=True)
    assert not html.startswith("<!doctype")
    assert "結果が変わる具体例" in html and "書き換わった箇所" in html


def test_文字はエスケープする():
    s = {"spec": "<b>x</b>", "actors": {"<i>客</i>": ""}, "usecases": [{"id": "a&b", "actor": "<i>客</i>"}]}
    spec = parse(s)
    html = render(spec, check(spec))
    assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt;" in html
    assert "a&amp;b" in html


def test_条件式を読みやすくする():
    assert prettify("14 < 経過日数 <= 30 and 商品状態 == 未開封") == "14 < 経過日数 ≤ 30 かつ 商品状態 ＝ 未開封"
    assert prettify("支払額 // 2") == "支払額 ÷ 2"
    assert prettify("True") == "いつでも"


def test_コマンドで画面を書き出す(tmp_path):
    out = tmp_path / "v.html"
    code = main(["view", str(EXAMPLES / "shop_v2.yaml"), "--base", str(EXAMPLES / "shop_v1.yaml"), "-o", str(out)])
    assert code == 0 and "仕様レビュー" in out.read_text(encoding="utf-8")


def test_従来の書き方でも検査できる(capsys):
    assert main([str(EXAMPLES / "refund_v2.yaml")]) == 0
    assert "受け入れ可" in capsys.readouterr().out
