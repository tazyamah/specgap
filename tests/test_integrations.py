from pathlib import Path

import pytest

from specgap import ERROR, WARNING, SpecError, check, load, parse
from specgap.diff import CHANGED, diff
from specgap.view import render

EXAMPLES = Path(__file__).parent.parent / "examples"


def base(**kw):
    s = {
        "spec": "連携",
        "systems": {"決済": {"description": "外部の決済"}, "メール": {}},
        "data": {"classes": ["一般", "個人情報"], "items": {"注文番号": "一般", "氏名": "個人情報"},
                 "allow": {"決済": ["一般"], "メール": ["一般", "個人情報"]}},
        "effects": {
            "返金": {"system": "決済", "mode": "sync", "sends": ["注文番号"], "reversible": "no",
                     "idempotency": "注文番号", "failures": ["拒否"]},
            "通知": {"system": "メール", "mode": "async", "sends": ["氏名"], "reversible": "yes", "failures": []},
        },
        "operations": [{"id": "返金する", "steps": [{"confirm": "担当者が確認する"}, {"call": "返金"}, {"update": "返金済みにする"}],
                        "on_interrupt": "照会して再開する", "on_failure": {"返金.拒否": "記録する"}}],
    }
    s.update(kw)
    return check(parse(s))


def titles(report, severity):
    return [f.title for f in report.findings if f.severity == severity]


def effects(**override):
    e = {
        "返金": {"system": "決済", "mode": "sync", "sends": ["注文番号"], "reversible": "no",
                 "idempotency": "注文番号", "failures": ["拒否"]},
        "通知": {"system": "メール", "mode": "async", "sends": ["氏名"], "reversible": "yes", "failures": []},
    }
    for k, v in override.items():
        e[k].update(v)
    return e


def test_整った連携は合格():
    r = base()
    assert r.ok, [f.title for f in r.findings]
    assert "システム間の連携" in r.passed


def test_渡してはいけない区分のデータを拒否する():
    r = base(effects=effects(返金={"sends": ["注文番号", "氏名"]}))
    assert any("個人情報（氏名）を 決済 に渡しています" in t for t in titles(r, ERROR))


def test_区分の決まっていないデータを拒否する():
    r = base(effects=effects(返金={"sends": ["注文番号", "電話番号"]}))
    assert any("データ項目 電話番号 の区分が決まっていません" in t for t in titles(r, ERROR))


def test_取り消せない作用に二重実行の防止がなければ拒否する():
    r = base(effects=effects(返金={"idempotency": ""}))
    assert any("二重実行を防ぐ仕組みがありません" in t for t in titles(r, ERROR))


def test_取り消せるかが未定なら拒否する():
    r = base(effects=effects(通知={"reversible": ""}))
    assert any("通知 を取り消せるかどうかが決まっていません" in t for t in titles(r, ERROR))


def test_yamlのnoは文字列として読む(tmp_path):
    f = tmp_path / "s.yaml"
    f.write_text("spec: x\nsystems: {A: {}}\neffects:\n  e: {system: A, reversible: no, idempotency: k}\n", encoding="utf-8")
    assert load(f).effect_info["e"].reversible == "no"


def test_結果を待たずに状態を進めると拒否する():
    ops = [{"id": "知らせる", "steps": [{"send": "通知"}, {"update": "通知済みにする"}]}]
    r = base(operations=ops)
    bad = [f for f in r.findings if "結果を待たずに状態を進めています" in f.title]
    assert bad and bad[0].ref == "知らせる#2"


def test_送って待てば状態を進めてよい():
    ops = [{"id": "知らせる", "steps": [{"send": "通知"}, {"await": "通知"}, {"update": "通知済みにする"}]}]
    assert not any("結果を待たずに" in t for t in titles(base(operations=ops), ERROR))


def test_確認なしの取り消せない作用は確認に回す():
    ops = [{"id": "返金する", "steps": [{"call": "返金"}], "on_failure": {"返金.拒否": "記録する"}}]
    assert any("取り消せない 返金 の前に確認の手順がありません" in t for t in titles(base(operations=ops), WARNING))


def test_途中で止まったときの扱いがなければ拒否する():
    ops = [{"id": "返金する", "steps": [{"confirm": "確認"}, {"call": "返金"}, {"update": "返金済みにする"}],
            "on_failure": {"返金.拒否": "記録する"}}]
    assert any("返金 の後で止まったときの扱いがありません" in t for t in titles(base(operations=ops), ERROR))


def test_呼び方と作用の待ち方が合わなければ拒否する():
    ops = [{"id": "x", "steps": [{"call": "通知"}]}]
    assert any("call ではなく send です" in t for t in titles(base(operations=ops), ERROR))


def test_使われていないシステムを確認に回す():
    r = base(systems={"決済": {}, "メール": {}, "倉庫": {}},
             data={"classes": ["一般", "個人情報"], "items": {"注文番号": "一般", "氏名": "個人情報"},
                   "allow": {"決済": ["一般"], "メール": ["一般", "個人情報"]}})
    assert any("システム 倉庫 とやりとりする外部作用がありません" in t for t in titles(r, WARNING))


def test_手順の種類を間違えると読み込みで止める():
    with pytest.raises(SpecError):
        base(operations=[{"id": "x", "steps": [{"jump": "返金"}]}])


def test_通販の例の連携の漏れ():
    r = check(load(EXAMPLES / "shop_v1.yaml"))
    errs = titles(r, ERROR)
    assert any("個人情報（氏名）を 決済代行 に渡しています" in t for t in errs)
    assert any("決済API に、二重実行を防ぐ仕組みがありません" in t for t in errs)
    assert any("集荷依頼 の結果を待たずに状態を進めています" in t for t in errs)


def test_差分と画面に連携が出る():
    b, h = load(EXAMPLES / "shop_v1.yaml"), load(EXAMPLES / "shop_v2.yaml")
    d = diff(b, h)
    assert any(c.kind == CHANGED and c.text.startswith("決済API で渡すデータ") for c in d.changes)
    html = render(h, check(h), base=b, change=d)
    for text in ["システムのつながり", "外に出ていくデータ", "取り消せるか", "処理の流れ：返金を実行"]:
        assert text in html
