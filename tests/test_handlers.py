from pathlib import Path

import pytest

from specgap import ERROR, WARNING, check, parse
from specgap.answer import _yaml
from specgap.operations import EffectFailure, expand, verify_operation

EXAMPLES = Path(__file__).parent.parent / "examples"
NETWORK = "決済API.通信エラー"
LOG = "通信エラーと照会の結果をログに残す"


def spec_with(do, outcomes=("返金済み", "未返金")):
    """会話で答えた例の「返金を実行」の通信エラーの扱いを、手順 do に差し替えた版。"""
    doc = _yaml().load((EXAMPLES / "shop_v1_interviewed.yaml").read_text(encoding="utf-8"))
    doc["effects"]["返金状況の照会"]["outcomes"] = list(outcomes)
    op = next(o for o in doc["operations"] if o["id"] == "返金を実行")
    for k, v in op["on_failure"].items():  # ほかの扱いは文章だけに戻し、通信エラーだけを見る
        if isinstance(v, dict):
            op["on_failure"][k] = v["text"]
    op["on_failure"][NETWORK] = {"text": "照会して、返金済みなら進め、まだなら再試行する", "do": do}
    doc.pop("implementation", None)
    spec = parse(doc, EXAMPLES)
    return spec, next(o for o in spec.operations if o.id == "返金を実行")


DO = [
    {"case": "返金状況の照会",
     "返金済み": [{"update": LOG}, "resume"],
     "未返金": [{"update": LOG}, {"retry": "決済API", "times": 2}, {"update": "返金を保留にして担当者に知らせる"}]},
]


def refund(ctx, *, skip_query=False, retries=2, give_up="返金を保留にして担当者に知らせる"):
    """仕様どおりの実装。引数で、ありがちな誤りを入れられる。"""
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
        if f.key != NETWORK:
            return
        if skip_query:
            got = {"結果": "未返金"}
        else:
            try:
                got = ctx.call("返金状況の照会", 注文番号=d["注文番号"])
            except EffectFailure as g:
                ctx.handled(g.key)
                return
        ctx.update(LOG)
        if got["結果"] == "未返金":
            for _ in range(retries):
                try:
                    pay()
                    break
                except EffectFailure:
                    continue
            else:
                if give_up:
                    ctx.update(give_up)
                return
    ctx.update("注文を返金済みにする")
    try:
        ctx.send("返金完了メール", メールアドレス=d["メールアドレス"], 氏名=d["氏名"], 返金額=d["返金額"])
    except EffectFailure as f:
        ctx.handled(f.key)


def test_手順で書いた扱いは分かれ道ごとの筋書きになる():
    spec, op = spec_with(DO)
    names = [label for label, _, _ in expand(spec, op, "決済API", op.handlers[NETWORK])]
    assert names == ["（返金状況の照会：返金済み）",
                     "（返金状況の照会：未返金）（再試行で直る）",
                     "（返金状況の照会：未返金）（再試行しても直らない）"]
    assert op.on_failure[NETWORK].startswith("照会して")  # 人の言葉は残る
    assert "返金状況の照会" in op.uses


def test_手順どおりの実装は通る():
    spec, op = spec_with(DO)
    r = verify_operation(spec, op, refund)
    assert r.ok, (r.scenario, r.expected, r.actual)


@pytest.mark.parametrize("bug, scenario, actual", [
    ({"skip_query": True}, "返金状況の照会", ""),  # 照会せずに再試行すると、二重に返金しうる
    ({"retries": 3}, "（再試行しても直らない）", "呼ぶ「決済API」 → 呼ぶ「決済API」 → 呼ぶ「決済API」"),
    ({"give_up": None}, "（再試行しても直らない）", "呼ぶ「決済API」 → 呼ぶ「決済API」（5つめから違う）"),
])
def test_手順と違う実装を見つける(bug, scenario, actual):
    spec, op = spec_with(DO)
    r = verify_operation(spec, op, lambda ctx: refund(ctx, **bug))
    assert not r.ok and scenario in r.scenario and actual in r.actual, (r.scenario, r.actual)


def test_照会の結果の漏れと_直らないときの扱いの漏れを問う():
    spec, _ = spec_with([{"case": "返金状況の照会", "返金済み": ["resume"]},])
    titles = [f.title for f in check(spec).findings if f.severity == ERROR]
    assert any("返金状況の照会 の結果が「未返金」のときの手順がありません" in t for t in titles)

    spec, _ = spec_with([{"retry": "決済API", "times": 3}])
    f = next(f for f in check(spec).findings if "再試行しても直らないときの扱いがありません" in f.title)
    assert f.severity == WARNING and f.question == "決済API を3回再試行しても直らなければ、どうしますか"

    spec, _ = spec_with([{"retry": "返金状況の照会"}, {"update": "x"}])
    assert any("再試行する 返金状況の照会 は、失敗した 決済API ではありません" in f.title for f in check(spec).findings)

    spec, _ = spec_with([{"case": "返金状況の照会", "返金済み": ["resume"], "未返金": ["resume"]}], outcomes=())
    assert any("結果の種類が決まっていません" in f.title for f in check(spec).findings)
