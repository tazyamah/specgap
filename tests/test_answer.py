from pathlib import Path

import yaml

from specgap import ERROR, check, load
from specgap.answer import apply, questions
from specgap.cli import main

EXAMPLES = Path(__file__).parent.parent / "examples"


def write(tmp_path, data, name="spec.yaml"):
    p = tmp_path / name
    p.write_text("# 元のコメント\n" + yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p


def answered(path, answers):
    spec = load(path)
    report = check(spec)
    res = apply(path, spec, report, answers)
    out = Path(path).with_name("new.yaml")
    out.write_text(res.text, encoding="utf-8")
    return res, out


BASE = {
    "spec": "テスト",
    "enums": {"状態": ["未開封", "開封済み"]},
    "inputs": {"日数": {"type": "int", "min": 0, "max": 100}, "状態": {"type": "状態"},
               "額面": {"type": "int", "min": 1, "max": 1000}},
    "outputs": {"額": {"type": "int", "min": 0}},
}


def test_穴の問いは条件つきの行として答えられる():
    qs = questions(check(load(EXAMPLES / "refund_v1.yaml")))
    assert [q.slot["when"] for q in qs] == [
        "経過日数 == 30 and 商品状態 == 開封済み",
        "経過日数 == 30 and 商品状態 == 未開封",
        "経過日数 >= 31 and 商品状態 == 開封済み",
    ]
    assert qs[0].how.startswith("返金額 の値か式")


def test_答えると漏れが埋まりコメントは残る(tmp_path):
    src = tmp_path / "refund.yaml"
    src.write_text((EXAMPLES / "refund_v1.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    res, out = answered(src, {1: {"返金額": "支払額 // 2"}, 2: {"返金額": "支払額"}, 3: {"返金額": 0}})
    assert not res.errors and len(res.applied) == 3
    assert res.text.startswith("# 返金の仕様（修正前）")
    r = check(load(out))
    assert not [f for f in r.findings if f.severity == ERROR]


def test_重なりは選ばなかった行を狭める(tmp_path):
    p = write(tmp_path, {**BASE, "tables": [{"id": "表", "rows": [
        {"when": "日数 <= 30", "then": {"額": "額面"}},
        {"when": "日数 >= 30", "then": {"額": "0"}},
    ]}]})
    qs = questions(check(load(p)))
    assert qs[0].slot["type"] == "overlap"
    res, out = answered(p, {1: 1})
    assert "(日数 >= 30) and not (日数 <= 30)" in res.text
    assert check(load(out)).ok


def test_状態の問いには遷移か拒否で答える(tmp_path):
    p = write(tmp_path, {"spec": "x", "machines": [{
        "id": "機", "states": ["A", "B"], "events": ["押す"], "initial": "A", "final": ["B"],
        "transitions": [{"from": "A", "on": "押す", "to": "B"}]}]})
    res, out = answered(p, {1: "拒否：終わっている"})
    assert check(load(out)).ok
    res, _ = answered(p, {1: "C"})
    assert res.errors and "C は状態にありません" in res.errors[0]


def test_答えが新しい漏れを生めば次の問いになる(tmp_path):
    p = write(tmp_path, {**BASE, "tables": [{"id": "表", "rows": [{"when": "日数 <= 30", "then": {"額": "額面"}}]}],
                         "ensures": [{"id": "額面を超えない", "expr": "額 <= 額面"}]})
    res, out = answered(p, {1: {"額": "額面 + 1"}})
    assert not res.errors
    r = check(load(out))
    assert any(f.check == "整合" and f.severity == ERROR for f in r.findings)


def test_答えの形が違えば反映しない(tmp_path):
    p = write(tmp_path, {**BASE, "tables": [{"id": "表", "rows": [{"when": "日数 <= 30", "then": {"額": "額面"}}]}]})
    res, _ = answered(p, {1: {"返金": 0}})
    assert "答える出力は 額 です" in res.errors[0]
    res, _ = answered(p, {1: {"額": "額面 +"}})
    assert res.errors
    res, _ = answered(p, {9: "x"})
    assert res.errors == ["問い 9 はありません"]


def test_通販の修正前に答えると受け入れ可になる(tmp_path, capsys):
    out = tmp_path / "answered.yaml"
    code = main(["answer", str(EXAMPLES / "shop_v1.yaml"), str(EXAMPLES / "answers" / "shop_v1.yaml"), "-o", str(out)])
    assert code == 0
    text = capsys.readouterr().out
    assert "受け入れ可、拒否 0 件" in text
    spec = load(out)
    assert spec.name == "通販の返品（問いに答えた版）"
    pay = spec.effect_info["決済API"]
    assert pay.idempotency == "注文番号" and "氏名" not in pay.sends
    steps = [(s.kind, s.target) for s in next(o for o in spec.operations if o.id == "返品を受け付ける").steps]
    assert steps[0][0] == "confirm" and ("await", "集荷依頼") in steps


def test_問いの一覧(capsys):
    assert main(["questions", str(EXAMPLES / "order_v1.yaml")]) == 0
    out = capsys.readouterr().out
    assert "1. 発送済み のときに 支払 が来たら" in out
    assert "答え方：次の状態" in out
