"""通販の返品（shop_v1_interviewed.yaml）の実装例。表と状態機械で決まることは書き写さず、判断に任せる。

人はこのファイルを読まない。if 文で返金額を書き写していないので、仕様とのずれは構造上起きない。
返金額の理由を知りたいときは refund_amount.why(...) で、当たった行とその判断（D…）を引ける。
"""

from specgap import decide

refund_amount = decide.table("返金額の決定")
next_order_state = decide.machine("注文")
