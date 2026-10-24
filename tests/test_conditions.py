from pathlib import Path

from specgap import ERROR, check, decide, load, parse
from specgap.answer import _yaml
from specgap.operations import EffectFailure, verify_operation

EXAMPLES = Path(__file__).parent.parent / "examples"
SHOP = load(EXAMPLES / "shop_v1_interviewed.yaml")
NOTIFY = next(o for o in SHOP.operations if o.id == "担当者に知らせる")


def notify(ctx, *, always=False, skip_board=False):
    d = ctx.data
    if not skip_board:
        ctx.update("通知欄に載せる")
    decide.use(SHOP)
    if not always and not decide.table("メールで知らせるか")(通知の種類=d["通知の種類"])["メールで送る"]:
        return
    try:
        ctx.send("担当者へのメール", 注文番号=d["注文番号"], 通知の件名=d["通知の件名"])
    except EffectFailure as f:
        ctx.handled(f.key)
        ctx.update("通知欄に未送信と出す")


def test_条件つきの手順は表の入力の組み合わせごとに確かめる():
    r = verify_operation(SHOP, NOTIFY, notify)
    assert r.ok, (r.scenario, r.expected, r.actual)
    assert r.scenarios == len(SHOP.enums["通知の種類"]) + 2  # 組み合わせごとの正常＋送信失敗＋途中停止


def test_表に従わずに送る実装を見つける():
    r = verify_operation(SHOP, NOTIFY, lambda ctx: notify(ctx, always=True))
    assert not r.ok and r.scenario == "正常（通知の種類=重複した発送）"
    assert (r.expected, r.actual) == ("1番目の手順で終わる", "2番目に送る「担当者へのメール」")


def test_通知欄に載せない実装を見つける():
    r = verify_operation(SHOP, NOTIFY, lambda ctx: notify(ctx, skip_board=True))
    assert not r.ok and "通知欄に載せる" in r.expected


def test_指針に反する行は性質の違反になる():
    doc = _yaml().load((EXAMPLES / "shop_v1_interviewed.yaml").read_text(encoding="utf-8"))
    t = next(t for t in doc["tables"] if t["id"] == "メールで知らせるか")
    t["rows"][0]["then"]["メールで送る"] = False  # 返金失敗をメールで送らない
    titles = [f.title for f in check(parse(doc, EXAMPLES)).findings if f.severity == ERROR]
    assert any("顧客に早く伝えるものはメールで送る" in x for x in titles), titles


def test_条件の表や出力が無ければ拒否する():
    doc = _yaml().load((EXAMPLES / "shop_v1_interviewed.yaml").read_text(encoding="utf-8"))
    op = next(o for o in doc["operations"] if o["id"] == "担当者に知らせる")
    op["steps"][1]["when"] = "メールで知らせるか.無い出力"
    assert any("が指す表または出力がありません" in f.title for f in check(parse(doc, EXAMPLES)).findings)
