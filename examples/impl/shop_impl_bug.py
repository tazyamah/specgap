"""shop_impl.py にバグを2つ入れた版（実演用）。

- refund_amount：全額返金の境界が「14日以内」ではなく「14日未満」になっている
- next_order_state：返品待ちで商品が届いたとき、キャンセル済みではなく完了にしている

python -m specgap check examples/shop_v2.yaml --impl examples/impl/shop_impl_bug.py で、
違反が具体例つきで拒否されるのを確かめられる。それ以外は shop_impl.py と同じ。

書き方の違いで保証の段階が変わる様子を見せるため、関数ごとに書き方を変えている。
- refund_amount：if の連鎖。記号実行できるので証明できる
- refund_method：辞書の参照。証明できないのでテストし、実行時にも監視する
- next_order_state：辞書の参照。状態機械は有限なので全件を確認できる
"""

from specgap.monitor import watch


def refund_amount(経過日数, 商品状態, 支払額):
    if 経過日数 > 30:
        return 0
    if 商品状態 == "未開封" and 経過日数 < 14:
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
    ("返品待ち", "到着"): "完了",
}


def next_order_state(状態, 出来事):
    return _NEXT.get((状態, 出来事))  # 表に無い組は None（拒否）
