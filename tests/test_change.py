import json
import shutil
from pathlib import Path

import pytest

from specgap import ask, check, load
from specgap.answer import questions
from specgap.change import change
from specgap.cli import main

EXAMPLES = Path(__file__).parent.parent / "examples"

FRAUD = [
    {"op": "add", "path": "actors", "value": {"管理者": "不正な注文を確かめ、処理する社員"}},
    {"op": "add", "path": "machines/注文/transitions", "value": {"from": "発送済み", "on": "支払", "to": "発送済み"}},
    {"op": "add", "path": "systems", "value": {"社内通知": {"description": "管理者や担当者に知らせを送る", "kind": "社内"}}},
    {"op": "add", "path": "effects", "value": {"不正な注文の通知": {
        "system": "社内通知", "mode": "async", "sends": ["注文番号"], "reversible": "no",
        "idempotency": "注文番号", "failures": ["送信失敗"]}}},
    {"op": "add", "path": "operations", "value": {"id": "不正な支払を記録する", "steps": [
        {"update": "不正な注文を作り、届いた支払をその注文に登録する"}, {"send": "不正な注文の通知"}]}},
]
SAID = "伝票と同じイメージの管理をしたいので、不正な注文というものを作れるようにして、それに対する支払いとして登録する。"


@pytest.fixture
def shop(tmp_path):
    p = tmp_path / "shop_v1.yaml"
    shutil.copy(EXAMPLES / "shop_v1.yaml", p)
    return p


def qid_of(s, text):
    q = next(q for q in questions(check(load(s.current))) if text in q.question)
    return ask.question_id(q)


def test_選択肢の外の答えを正本の変更として当てる(shop):
    s = ask.session(shop)
    q = qid_of(s, "発送済み のときに 支払 が来たら")
    res = change(s, FRAUD, "発送済みの注文に支払が届いたら、不正な注文を作って支払を登録し、管理者に通知する", SAID, q)
    assert res.ok, res.text
    assert res.text.startswith("反映しました：発送済みの注文に支払が届いたら")
    assert any("不正な支払を記録する" in c for c in res.changes)
    assert "変更で新しく出た拒否" in res.text and "社内通知 に渡してよいデータの区分" in res.text
    spec = load(s.work)
    assert any(t.src == "発送済み" and t.event == "支払" for t in spec.machines[0].transitions)
    d = spec.decisions[-1]
    assert (d.id, d.said) == (res.decision, SAID)
    assert d.question.startswith("発送済み のときに 支払 が来たら")
    assert "状態機械:注文:発送済み:支払" in d.applies_to and "操作:不正な支払を記録する" in d.applies_to
    assert not any(ask.question_id(x) == q for x in questions(check(spec)))
    assert "{from: 発送済み, on: 支払, to: 発送済み}" in s.work.read_text(encoding="utf-8")  # 正本の書き方に合わせる
    row = json.loads(s.log.read_text(encoding="utf-8").splitlines()[-1])
    assert row["decision"] == res.decision and row["ops"][1]["path"] == "machines/注文/transitions"


def test_当てられない変更は正本を変えない(shop):
    s = ask.session(shop)
    res = change(s, [{"op": "add", "path": "machines/無い機械/transitions", "value": {}}], "x")
    assert not res.ok and "「無い機械」が見つかりません" in res.text
    assert not s.work.exists()
    res = change(s, [{"op": "add", "path": "operations/返品を受け付ける/steps", "value": {"jump": "x"}}], "x")
    assert not res.ok and "変更後の正本を読めません" in res.text  # 読めない正本になる変更は当てない
    assert not s.work.exists()
    assert not change(s, FRAUD, "").ok


def test_確認の問いにはこのままでよいと答えられる(shop):
    s = ask.session(shop)
    q = qid_of(s, "申込完了 を見たあと")
    text, ok = ask.reply(s, q, "このままでよい", "申込完了で終わりでいい")
    assert ok and "（判断 D1）" in text
    r = check(load(s.work))
    f = next(f for f in r.findings if "申込完了" in f.title)
    assert f.severity == "info" and f.detail.startswith("判断 D1 で、このままでよいと確認済み")
    assert not any("申込完了" in x.question for x in questions(r))


def test_拒否の問いはこのままでよいにできない(shop):
    s = ask.session(shop)
    q = qid_of(s, "経過日数が増えると")
    p, _ = ask.next_packet(s)
    assert "このままでよい" in p.choices  # ルールの問いは確認（warning）
    q = qid_of(s, "発送済み のときに 支払 が来たら")
    text, ok = ask.reply(s, q, "このままでよい")
    assert not ok and "拒否の問いは「このままでよい」にできません" in text


def test_正本の形を変える答えが要る問いは_change_を促す(shop):
    s = ask.session(shop)
    q = qid_of(s, "誰がどう気づきますか")
    text, ok = ask.reply(s, q, "担当者が毎朝見る")
    assert not ok and "change で出してください" in text


def test_cli_の_change(shop, tmp_path, capsys):
    ops = tmp_path / "ops.yaml"
    ops.write_text(json.dumps(FRAUD, ensure_ascii=False), encoding="utf-8")
    assert main(["change", str(shop), str(ops), "--title", "不正な注文を作る", "--said", SAID,
                 "--assume", "1注文1返金"]) == 0
    assert "反映しました：不正な注文を作る（判断 D1）" in capsys.readouterr().out
    assert load(shop.with_name("shop_v1.work.yaml")).decisions[0].assumptions == ["1注文1返金"]
