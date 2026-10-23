"""shop_impl.py の refund_amount を、規則の一覧をループで調べる書き方にした版（実演用）。

結果は仕様どおりだが、ループは記号実行できないので証明できず、テスト済みまでにとどまる。
方針は「返金額の決定」に証明済みを求めているので、正しくても受け入れられない。
python -m specgap check examples/shop_v2.yaml --impl examples/impl/shop_impl_loop.py で確かめられる。
"""

from shop_impl import next_order_state, refund_method  # noqa: F401  （返金方法と注文は同じ実装）

# (経過日数の下限, 上限, 商品状態, 支払額を割る数)
_RULES = [(0, 14, "未開封", 1), (0, 30, "開封済み", 2), (15, 30, "未開封", 2)]


def refund_amount(経過日数, 商品状態, 支払額):
    for lo, hi, state, div in _RULES:
        if lo <= 経過日数 <= hi and 商品状態 == state:
            return 支払額 // div
    return 0
