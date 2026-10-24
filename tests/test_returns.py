"""返品を受け付ける・処理中の返品を照会し直す（D50〜D53）の実装の確かめ。"""
from pathlib import Path

import pytest

from specgap import load
from specgap.operations import EffectFailure, scenarios, verify_operation

EXAMPLES = Path(__file__).parent.parent / "examples"
SHOP = load(EXAMPLES / "shop_v1_interviewed.yaml")
ACCEPT = next(o for o in SHOP.operations if o.id == "返品を受け付ける")
REQUERY = next(o for o in SHOP.operations if o.id == "処理中の返品を照会し直す")


def notify(ctx, kind):
    d = ctx.data
    ctx.send("担当者への通知", 注文番号=d["注文番号"], 決済ID=d["決済ID"], 通知の件名=d["通知の件名"], 通知の種類=kind)


def pickup(ctx, *, report=True):
    d = ctx.data
    try:
        ctx.send("集荷依頼", 注文番号=d["注文番号"], 氏名=d["氏名"], 住所=d["住所"])
        ctx.await_result("集荷依頼")
    except EffectFailure as f:
        ctx.handled(f.key)
        if report:
            ctx.update("集荷依頼が通らなかったと記録する")
            notify(ctx, "集荷依頼の受付拒否")
        return
    ctx.update("注文を返品待ちにする")


def requery(ctx, *, always_request=False, retries=1):
    for attempt in range(retries + 1):
        try:
            got = ctx.call("集荷依頼の照会", 注文番号=ctx.data["注文番号"])
            break
        except EffectFailure as f:
            ctx.handled(f.key)
            if attempt == retries:
                ctx.update("返品を保留にする")
                notify(ctx, "集荷依頼を照会できない")
                return
    if got["結果"] == "依頼済み" and not always_request:
        ctx.update("注文を返品待ちにする")
    else:
        pickup(ctx)


def test_照会し直して直ったときも_照会の結果ごとに筋書きを分ける():
    names = [sc.name for sc in scenarios(SHOP, REQUERY)]
    assert "集荷依頼の照会.タイムアウト（再試行で直る）（集荷依頼の照会：依頼済み）" in names
    assert "集荷依頼の照会.タイムアウト（再試行で直る）（集荷依頼の照会：未依頼）" in names


def test_手順どおりの実装は通る():
    assert verify_operation(SHOP, REQUERY, requery).ok
    accept = lambda ctx: ctx.confirm("購入者が返品の内容を確認する") and (ctx.update("注文を返品処理中にする") or pickup(ctx))
    assert verify_operation(SHOP, ACCEPT, accept).ok


@pytest.mark.parametrize("bug, scenario", [
    ({"always_request": True}, "依頼済み"),  # 依頼済みなのに出し直すと、二重に集荷を頼む
    ({"retries": 2}, "再試行しても直らない"),  # 照会の再試行は1回だけ
])
def test_手順と違う実装を見つける(bug, scenario):
    r = verify_operation(SHOP, REQUERY, lambda ctx: requery(ctx, **bug))
    assert not r.ok and scenario in r.scenario, (r.scenario, r.actual)


def test_受付拒否を知らせない実装を見つける():
    accept = lambda ctx: ctx.confirm("購入者が返品の内容を確認する") and (ctx.update("注文を返品処理中にする") or pickup(ctx, report=False))
    r = verify_operation(SHOP, ACCEPT, accept)
    assert not r.ok and "集荷依頼.受付拒否" in r.scenario
