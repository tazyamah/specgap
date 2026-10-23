from pathlib import Path

from specgap import WARNING, check, load, parse
from specgap.guarantee import TESTED, VIOLATION, Guarantee, Item, apply, verify
from specgap.operations import EffectFailure, verify_operation

EXAMPLES = Path(__file__).parent.parent / "examples"
SHOP = load(EXAMPLES / "shop_v2.yaml")
REFUND = next(o for o in SHOP.operations if o.id == "返金を実行")
CONFIRM = "サポート担当が返金額を確認して承認する"


def pay(ctx, **extra):
    d = ctx.data
    ctx.call("決済API", 注文番号=d["注文番号"], 返金額=d["返金額"], 決済ID=d["決済ID"], **extra)


def mail(ctx):
    d = ctx.data
    ctx.send("返金完了メール", メールアドレス=d["メールアドレス"], 氏名=d["氏名"], 返金額=d["返金額"])


def good(ctx):
    if not ctx.confirm(CONFIRM):
        return
    try:
        pay(ctx)
    except EffectFailure as f:
        ctx.handled(f.key)
        return
    ctx.update("注文を返金済みにする")
    try:
        mail(ctx)
    except EffectFailure as f:
        ctx.handled(f.key)


def test_正しい実装はすべての筋書きを通る():
    r = verify_operation(SHOP, REFUND, good)
    assert r.ok
    # 正常・確認を断る・決済APIの失敗3種・メールの失敗1種・3か所での停止
    assert r.scenarios == 9
    assert set(r.used) == {"決済API", "返金完了メール"}


def test_手順の順序が違えば最初に違う手順を示す():
    def f(ctx):
        if not ctx.confirm(CONFIRM):
            return
        ctx.update("注文を返金済みにする")
        pay(ctx)
        mail(ctx)
    r = verify_operation(SHOP, REFUND, f)
    assert not r.ok and r.scenario == "正常"
    assert r.expected == "2番目に呼ぶ「決済API」"
    assert r.actual == "2番目に更新「注文を返金済みにする」"


def test_仕様にないデータは渡せない():
    def f(ctx):
        ctx.confirm(CONFIRM)
        pay(ctx, 氏名=ctx.data["氏名"])
    r = verify_operation(SHOP, REFUND, f)
    assert "仕様にないデータ 氏名" in r.actual


def test_手元と違う値は渡せない():
    def f(ctx):
        ctx.confirm(CONFIRM)
        ctx.call("決済API", 注文番号="別の注文", 返金額=ctx.data["返金額"], 決済ID=ctx.data["決済ID"])
    assert "注文番号 が手元の値" in verify_operation(SHOP, REFUND, f).actual


def test_使ってよい外部作用にない作用は使えない():
    def f(ctx):
        good(ctx)
        ctx.call("集荷の取消", 集荷番号="集荷番号-1")
    r = verify_operation(SHOP, REFUND, f)
    assert "使ってよい外部作用に 集荷の取消 はありません" in r.actual


def test_確認で断られたら何もしない():
    def f(ctx):
        ctx.confirm(CONFIRM)  # 答えを見ていない
        try:
            pay(ctx)
        except EffectFailure as e:
            ctx.handled(e.key)
            return
        ctx.update("注文を返金済みにする")
        mail(ctx)
    r = verify_operation(SHOP, REFUND, f)
    assert r.scenario.startswith("確認を断る")
    assert "呼ぶ「決済API」" in r.actual


def test_扱わない失敗を見つける():
    def f(ctx):
        if not ctx.confirm(CONFIRM):
            return
        pay(ctx)
        ctx.update("注文を返金済みにする")
        mail(ctx)
    r = verify_operation(SHOP, REFUND, f)
    assert r.scenario == "決済API.タイムアウト"
    assert r.actual == "決済API.タイムアウト を扱わずに止まった"


def test_失敗したのに先へ進むのを見つける():
    def f(ctx):
        if not ctx.confirm(CONFIRM):
            return
        try:
            pay(ctx)
        except EffectFailure as e:
            ctx.handled(e.key)  # return し忘れ
        ctx.update("注文を返金済みにする")
        try:
            mail(ctx)
        except EffectFailure as e:
            ctx.handled(e.key)
    r = verify_operation(SHOP, REFUND, f)
    assert r.expected == "決済API が失敗したら、その後の手順には進まない"
    assert "更新「注文を返金済みにする」" in r.actual


def test_再試行して成功したら先へ進んでよい():
    def f(ctx):
        if not ctx.confirm(CONFIRM):
            return
        try:
            pay(ctx)
        except EffectFailure as e:
            ctx.handled(e.key)
            if e.kind != "タイムアウト":
                return
            pay(ctx)  # 同じ注文番号で再試行（外部は1回分として扱う）
        ctx.update("注文を返金済みにする")
        try:
            mail(ctx)
        except EffectFailure as e:
            ctx.handled(e.key)
    assert verify_operation(SHOP, REFUND, f).ok


def test_途中で止まったあと再開しないのを見つける():
    state = {"finished": True}

    def f(ctx):
        if not state["finished"]:  # 前回が途中で終わっていたら、続きをせずに終える
            state["finished"] = True
            return
        state["finished"] = False
        good(ctx)
        state["finished"] = True
    r = verify_operation(SHOP, REFUND, f)
    assert "直後で止まる" in r.scenario
    assert "をしないまま終わった" in r.actual


def test_二重実行を防ぐキーがなければ再開で二重に実行する():
    s = parse({
        "spec": "x",
        "data": {"classes": ["一般"], "items": {"額": "一般"}},
        "effects": {"送金": {"sends": ["額"], "reversible": "no", "failures": []}},
        "operations": [{"id": "払う", "steps": [{"call": "送金"}, {"update": "払い済みにする"}]}],
    })
    op = s.operations[0]

    def f(ctx):
        ctx.call("送金", 額=ctx.data["額"])
        ctx.update("払い済みにする")
    r = verify_operation(s, op, f)
    assert r.actual == "送金 を2回実行した"


def test_例のバグ入り実装の操作は拒否する():
    g = verify(SHOP, EXAMPLES / "impl" / "shop_impl_bug.py")
    assert g.item("返品を受け付ける").level == VIOLATION
    assert g.item("返品を受け付ける").actual == {"実装": "3番目に更新「注文を返品待ちにする」"}
    assert "氏名" in g.item("返金を実行").actual["実装"]
    ok = verify(SHOP)
    assert ok.item("返金を実行").level == TESTED


def test_使う外部作用やデータが増えたら確認に回す():
    r = check(SHOP)
    it = Item("操作", "返金を実行", function="f", level=TESTED,
              uses={"決済API": ["注文番号", "返金額"], "返金完了メール": ["返金額"]},
              before_uses={"決済API": ["注文番号"]})
    apply(r, Guarantee("m.py", [it]))
    ws = [f for f in r.findings if f.severity == WARNING and f.check == "実装"]
    assert any("前の版より増えました" in f.title for f in ws)
    assert "決済API（注文番号・返金額）" in ws[0].detail and "返金完了メール" in ws[0].detail
