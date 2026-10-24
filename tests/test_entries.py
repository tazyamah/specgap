from pathlib import Path

import pytest

from specgap import ERROR, WARNING, ask, check, load
from specgap.answer import _yaml
from specgap.change import change
from specgap.decisions import exists
from specgap.diff import diff
from specgap.view import render

EXAMPLES = Path(__file__).parent.parent / "examples"

ENTRY = {"via": "担当者への通知", "to": "不正な注文の詳細", "link": "詳細画面のリンク"}
PATH = "screens/管理者の画面/entries"


@pytest.fixture
def shop(tmp_path):
    """会話で答えた例から、入口（D54・D55）を除いた版。"""
    y = _yaml()
    doc = y.load((EXAMPLES / "shop_v1_interviewed.yaml").read_text(encoding="utf-8"))
    for f in doc["screens"]:
        f.pop("entries", None)
    p = tmp_path / "shop.yaml"
    with p.open("w", encoding="utf-8") as fh:
        y.dump(doc, fh)
    return ask.session(p)


def titles(spec, severity):
    return [f.title for f in check(spec).findings if f.severity == severity]


def test_リンクを渡しているのに開く画面がないと確認に回す(shop):
    spec = load(shop.spec)
    assert "担当者への通知 で渡す 詳細画面のリンク から、どの画面を開くかが決まっていません" in titles(spec, WARNING)


def test_入口を足すと確認が消え_判断は入口を指す(shop):
    res = change(shop, [{"op": "add", "path": PATH, "value": ENTRY}], "通知メールのリンクから不正な注文の詳細を開く")
    assert res.ok, res.text
    spec = load(shop.work)
    flow = next(f for f in spec.screen_flows if f.id == "管理者の画面")
    assert [(e.via, e.dst, e.link) for e in flow.entries] == [tuple(ENTRY.values())]
    assert not any("担当者への通知 で渡す" in t for t in titles(spec, WARNING))
    assert spec.decisions[-1].applies_to == ["画面:管理者の画面:入口:担当者への通知"]
    assert exists(spec, "画面:管理者の画面:入口:担当者への通知")
    assert any("担当者への通知 のリンク（詳細画面のリンク） → 不正な注文の詳細" in c for c in res.changes)


def test_入口からだけ入れる画面は_たどり着ける(shop):
    ops = [
        {"op": "add", "path": PATH, "value": {**ENTRY, "to": "不正な注文の要約"}},
        {"op": "add", "path": "screens/管理者の画面/transitions", "value": {"from": "不正な注文の要約", "action": "詳しく見る", "to": "不正な注文の詳細"}},
    ]
    assert change(shop, ops, "x").ok
    assert not any("不正な注文の要約 には" in t for t in titles(load(shop.work), WARNING))


@pytest.mark.parametrize("entry, severity, text", [
    ({"via": "無い通知", "to": "不正な注文の詳細"}, ERROR, "定義されていない連携 無い通知"),
    ({**ENTRY, "link": "住所"}, ERROR, "を、担当者への通知 で渡していません"),
    ({"via": "担当者への通知", "to": "不正な注文の詳細"}, WARNING, "開くリンクにあたるデータが決まっていません"),
])
def test_入口の誤り(shop, entry, severity, text):
    assert change(shop, [{"op": "add", "path": PATH, "value": entry}], "x").ok
    assert any(text in t for t in titles(load(shop.work), severity))


def test_入口は図と差分に出る(shop):
    base = load(shop.spec)
    assert change(shop, [{"op": "add", "path": PATH, "value": ENTRY}], "x").ok
    head = load(shop.work)
    html = render(head, check(head), base=base)
    assert "✉ 担当者への通知" in html and "最初の画面を通らずに 不正な注文の詳細 を開きます" in html
    assert any(c.area == "画面" and "担当者への通知 のリンク" in c.text for c in diff(base, head).changes)


def test_最初の画面を変えると差分に出て_判断は画面の流れを指す(shop):
    res = change(shop, [{"op": "replace", "path": "screens/購入者の画面/start", "value": "商品一覧"}], "商品一覧から始まる")
    assert res.ok, res.text
    assert any("購入者の画面：最初の画面は 商品一覧" in c for c in res.changes)
    spec = load(shop.work)
    assert spec.decisions[-1].applies_to == ["画面:購入者の画面"] and exists(spec, "画面:購入者の画面")
