"""通販の返品（shop_v1_interviewed.yaml）の実装例。表と状態機械で決まることは書き写さず、判断に任せる。

人はこのファイルを読まない。if 文で返金額を書き写していないので、仕様とのずれは構造上起きない。
返金額の理由を知りたいときは refund_amount.why(...) で、当たった行とその判断（D…）を引ける。
"""

from specgap import decide

refund_amount = decide.table("返金額の決定")
next_order_state = decide.machine("注文")


# ---- 外部とのやりとり ----
# 失敗の扱いを手順で書いたもの（決済API の通信エラー）は、手順どおりに動くかまで機械が確かめる。
# 文章だけの扱いは、扱った記録（ctx.handled）を残し、中身は担当者の作業や別の処理に任せる。

from specgap.operations import EffectFailure  # noqa: E402

LOG = "通信エラーと照会の結果をログに残す"
mail_rule = decide.table("メールで知らせるか")


def execute_refund(ctx):
    if not ctx.confirm("サポート担当が返金額を確認して承認する"):
        return
    ctx.update("承認した返金額を記録し、注文を返金処理中にする")
    d = ctx.data

    def pay():
        ctx.call("決済API", 注文番号=d["注文番号"], 返金額=d["返金額"], 決済ID=d["決済ID"])

    try:
        pay()
    except EffectFailure as f:
        ctx.handled(f.key)
        if f.key != "決済API.通信エラー":
            return  # タイムアウト・拒否は文章の扱い（照会して保留、返金失敗として通知）
        try:
            got = ctx.call("返金状況の照会", 注文番号=d["注文番号"])  # 照会せずに再試行すると二重に返金しうる
        except EffectFailure as g:
            ctx.handled(g.key)  # 保留にして時間をおいて照会し直す
            return
        ctx.update(LOG)
        if got["結果"] == "未返金":
            try:
                pay()  # 再試行は1回だけ（D40）
            except EffectFailure:
                ctx.update("返金失敗として記録する")
                try:
                    ctx.send("担当者への通知", 注文番号=d["注文番号"], 決済ID=d["決済ID"], 通知の件名=d["通知の件名"],
                             通知の種類="返金失敗")
                except EffectFailure as n:
                    ctx.handled(n.key)
                return
    ctx.update("注文を返金済みにする")
    try:
        ctx.send("返金完了メール", メールアドレス=d["メールアドレス"], 氏名=d["氏名"], 返金額=d["返金額"])
    except EffectFailure as f:
        ctx.handled(f.key)  # 送れなかったことを記録するだけ


def notify_staff(ctx):
    """担当者への知らせ。通知欄には必ず載せ、メールは統一ルールの表（判断）に任せる。"""
    d = ctx.data
    ctx.update("通知欄に載せる")
    if not mail_rule(通知の種類=d["通知の種類"])["メールで送る"]:
        return
    try:
        ctx.send("担当者へのメール", 注文番号=d["注文番号"], 通知の件名=d["通知の件名"])
    except EffectFailure as f:
        ctx.handled(f.key)
        ctx.update("通知欄に未送信と出す")
