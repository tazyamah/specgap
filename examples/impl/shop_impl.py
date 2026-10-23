"""通販の返品（shop_v2.yaml）の実装例。AI が書いた想定で、人はこのファイルを読まない。

書き方の違いで保証の段階が変わる様子を見せるため、関数ごとに書き方を変えている。
- refund_amount：if の連鎖。記号実行できるので証明できる
- refund_method：辞書の参照。証明できないのでテストし、実行時にも監視する
- next_order_state：辞書の参照。状態機械は有限なので全件を確認できる
- accept_return / execute_refund：外部とのやりとり。ctx を通してしか外部作用を使えない
"""

from specgap.monitor import watch
from specgap.operations import EffectFailure


def refund_amount(経過日数, 商品状態, 支払額):
    if 経過日数 > 30:
        return 0
    if 商品状態 == "未開封" and 経過日数 <= 14:
        return 支払額
    return 支払額 // 2


_METHOD = {"カード": "元の支払方法", "ポイント": "ポイント付与", "銀行振込": "ポイント付与"}


@watch("返金方法の決定")
def refund_method(支払方法):
    return _METHOD[支払方法]


_NEXT = {
    ("受付", "支払"): "支払済み",
    ("受付", "キャンセル"): "キャンセル済み",
    ("支払済み", "発送"): "発送済み",
    ("支払済み", "キャンセル"): "キャンセル済み",
    ("発送済み", "到着"): "完了",
    ("発送済み", "キャンセル"): "返品待ち",
    ("返品待ち", "到着"): "キャンセル済み",
}


def next_order_state(状態, 出来事):
    return _NEXT.get((状態, 出来事))  # 表に無い組は None（拒否）


def accept_return(ctx):
    if not ctx.confirm("購入者が返品の内容と返金額の見込みを確認する"):
        return
    d = ctx.data
    ctx.send("集荷依頼", 注文番号=d["注文番号"], 氏名=d["氏名"], 住所=d["住所"])
    try:
        ctx.await_result("集荷依頼")
    except EffectFailure as f:
        ctx.handled(f.key)  # 申込を差し戻し、購入者に理由を表示する
        return
    ctx.update("注文を返品待ちにする")


def execute_refund(ctx):
    if not ctx.confirm("サポート担当が返金額を確認して承認する"):
        return
    d = ctx.data
    try:
        ctx.call("決済API", 注文番号=d["注文番号"], 返金額=d["返金額"], 決済ID=d["決済ID"])
    except EffectFailure as f:
        ctx.handled(f.key)  # 照会して再試行・記録して通知（中身は別の処理）
        return
    ctx.update("注文を返金済みにする")
    try:
        ctx.send("返金完了メール", メールアドレス=d["メールアドレス"], 氏名=d["氏名"], 返金額=d["返金額"])
    except EffectFailure as f:
        ctx.handled(f.key)  # 1時間後に再送する
