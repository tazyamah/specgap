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

mail_rule = decide.table("メールで知らせるか")


def execute_refund(ctx):
    if not ctx.confirm("サポート担当が返金額を確認して承認する"):
        return
    ctx.update("承認した返金額を記録し、注文を返金処理中にする")
    d = ctx.data
    try:
        _pay(ctx)
    except EffectFailure as f:
        ctx.handled(f.key)
        if f.key == "決済API.拒否":
            ctx.update("返金失敗として記録する")
            _notify(ctx, "返金失敗")
            return
        # タイムアウト・通信エラー：照会せずに再試行すると二重に返金しうるので、先に照会する
        kind = "タイムアウト" if f.key == "決済API.タイムアウト" else "通信エラー"
        try:
            got = ctx.call("返金状況の照会", 注文番号=d["注文番号"])
        except EffectFailure as g:
            ctx.handled(g.key)
            ctx.update("返金を保留にする")  # あとで「保留中の返金を照会し直す」が照会する
            return
        ctx.update(f"{kind}と照会の結果をログに残す")
        if got["結果"] == "未返金":
            try:
                _pay(ctx)  # 再試行は1回だけ（D40・D45）
            except EffectFailure:
                if kind == "タイムアウト":
                    ctx.update("返金を保留にする")
                    _notify(ctx, "返金の保留")
                else:
                    ctx.update("返金失敗として記録する")
                    _notify(ctx, "返金失敗")
                return
    _finish(ctx)


def requery_held_refund(ctx):
    """保留中の返金を、時間をおいて照会し直す。照会の再試行は1回だけ（D46）。"""
    d = ctx.data
    for attempt in range(2):
        try:
            got = ctx.call("返金状況の照会", 注文番号=d["注文番号"])
            break
        except EffectFailure as f:
            ctx.handled(f.key)
            if attempt == 1:
                ctx.update("返金を保留のままにする")
                _notify(ctx, "返金状況を照会できない")
                return
    if got["結果"] == "返金済み":
        _finish(ctx)
    else:  # 自動で返金し直すと二重返金になりうるので、担当者の判断を待つ
        ctx.update("返金を保留のまま担当者の判断を待つ")
        _notify(ctx, "返金の保留")


def _pay(ctx):
    d = ctx.data
    ctx.call("決済API", 注文番号=d["注文番号"], 返金額=d["返金額"], 決済ID=d["決済ID"])


def _finish(ctx):
    d = ctx.data
    ctx.update("注文を返金済みにする")
    try:
        ctx.send("返金完了メール", メールアドレス=d["メールアドレス"], 氏名=d["氏名"], 返金額=d["返金額"])
    except EffectFailure as f:
        ctx.handled(f.key)
        ctx.update("返金完了メールを送れなかったことを記録する")


def _notify(ctx, kind):
    d = ctx.data
    ctx.send("担当者への通知", 注文番号=d["注文番号"], 決済ID=d["決済ID"], 通知の件名=d["通知の件名"], 通知の種類=kind)


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
