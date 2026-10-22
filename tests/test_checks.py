from pathlib import Path

import pytest

from specgap import ERROR, INFO, WARNING, SpecError, check, load, parse

EXAMPLES = Path(__file__).parent.parent / "examples"


def spec(**kw):
    base = {
        "spec": "テスト",
        "enums": {"状態": ["未開封", "開封済み"]},
        "inputs": {"日数": {"type": "int", "min": 0, "max": 100}, "状態": {"type": "状態"}},
        "outputs": {"額": {"type": "int", "min": 0}},
    }
    base.update(kw)
    return check(parse(base))


def table(*rows):
    return [{"id": "表", "rows": [{"when": w, "then": {"額": t}} for w, t in rows]}]


def titles(report, severity):
    return [f.title for f in report.findings if f.severity == severity]


# ---- 決定表 ----


def test_網羅されていれば合格():
    r = spec(tables=table(("日数 <= 30", "100"), ("日数 > 30", "0")))
    assert r.ok
    assert "決定表の網羅と排他" in r.passed


def test_境界の穴を具体例で示す():
    r = spec(tables=table(("日数 < 30", "100"), ("日数 > 30", "0")))
    gaps = [f for f in r.findings if f.check == "網羅"]
    assert len(gaps) == 1
    assert gaps[0].example["日数"] == "30"
    assert "どうしますか" in gaps[0].question


def test_列挙値の組み合わせの穴を全部挙げる():
    r = spec(tables=table(("日数 < 50 and 状態 == 未開封", "100"), ("日数 >= 50 and 状態 == 開封済み", "0")))
    examples = sorted((f.example["日数"], f.example["状態"]) for f in r.findings if f.check == "網羅")
    assert examples == [("0", "開封済み"), ("50", "未開封")]


def test_重なりと結果の食い違いを示す():
    r = spec(tables=table(("日数 <= 30", "100"), ("日数 >= 30", "0")))
    over = [f for f in r.findings if f.check == "排他"]
    assert len(over) == 1
    assert over[0].example["日数"] == "30"
    assert "結果が違います" in over[0].detail


def test_重なっても結果が同じならそう伝える():
    r = spec(tables=table(("日数 <= 30", "0"), ("日数 >= 30", "0")))
    over = [f for f in r.findings if f.check == "排他"]
    assert "結果は同じ" in over[0].detail


def test_どの入力も当たらない行を警告する():
    r = spec(tables=table(("日数 > 200", "1"), ("True", "0")))
    assert any("どんな入力も当たりません" in t for t in titles(r, WARNING))


def test_出力を決めていない行を拒否する():
    s = {"spec": "x", "inputs": {"a": "bool"}, "outputs": {"b": "int", "c": "int"},
         "tables": [{"id": "表", "rows": [{"when": "a", "then": {"b": "1", "c": "2"}},
                                          {"when": "not a", "then": {"b": "0"}}]}]}
    r = check(parse(s))
    assert any("2行目が出力 c を決めていません" in t for t in titles(r, ERROR))


def test_未規定は記録として残す():
    r = spec(tables=table(("日数 <= 30", "100"), ("日数 > 30", "unspecified")))
    assert r.ok
    assert any("意図的に決めていません" in t for t in titles(r, INFO))


# ---- 性質 ----


def test_表の結果が性質に違反すると拒否する():
    r = spec(tables=table(("日数 <= 30", "100"), ("日数 > 30", "0")), ensures=[{"id": "上限", "expr": "額 <= 50"}])
    bad = [f for f in r.findings if f.check == "整合"]
    assert len(bad) == 1
    assert "1行目" in bad[0].title


def test_矛盾した性質を拒否する():
    r = spec(ensures=[{"id": "a", "expr": "額 > 10"}, {"id": "b", "expr": "額 < 5"}])
    assert any(f.check == "矛盾" for f in r.findings)


def test_何も縛らない性質を警告する():
    r = spec(tables=table(("True", "0")), ensures=[{"id": "自明", "expr": "額 >= 0"}])
    assert any(f.check == "自明" for f in r.findings)


def test_未規定でも性質を満たせない入力があれば拒否する():
    s = {"spec": "x", "inputs": {"支払": {"type": "int", "min": 0, "max": 10}},
         "outputs": {"額": {"type": "int", "min": 5}},
         "tables": [{"id": "表", "rows": [{"when": "True", "then": {"額": "unspecified"}}]}],
         "ensures": [{"id": "上限", "expr": "額 <= 支払"}]}
    r = check(parse(s))
    bad = [f for f in r.findings if f.check == "整合"]
    assert bad and bad[0].example["支払"] == "0"


def test_性質だけで縛られた出力は確認に回す():
    r = spec(ensures=[{"id": "範囲", "expr": "額 <= 日数"}])
    assert any("性質だけで縛られて" in t for t in titles(r, WARNING))


# ---- 状態機械・失敗・未使用 ----


def machine(**kw):
    m = {"id": "M", "states": ["A", "B"], "events": ["x"], "initial": "A", "final": ["B"],
         "transitions": [{"from": "A", "on": "x", "to": "B"}], "rejects": [{"from": "B", "on": "x"}]}
    m.update(kw)
    return check(parse({"spec": "m", "machines": [m]}))


def test_状態機械が網羅されていれば合格():
    assert machine().ok


def test_扱いが重複した組を拒否する():
    r = machine(rejects=[{"from": ["A", "B"], "on": "x"}])
    assert any("扱いが複数あります" in t for t in titles(r, ERROR))


def test_到達できない状態と抜け出せない状態を警告する():
    r = machine(states=["A", "B", "C"], rejects=[{"from": ["B", "C"], "on": "x"}])
    ws = titles(r, WARNING)
    assert any("C には初期状態から到達できません" in t for t in ws)
    assert any("C は終了状態ではないのに" in t for t in ws)


def test_未定義の外部作用を拒否する():
    r = check(parse({"spec": "x", "operations": [{"id": "op", "uses": ["DB"]}]}))
    assert any("未定義の外部作用 DB" in t for t in titles(r, ERROR))


def test_使われていない入力を警告する():
    r = spec(tables=table(("日数 <= 30", "1"), ("日数 > 30", "0")))
    assert any("入力 状態 は" in t for t in titles(r, WARNING))


# ---- 書式 ----


@pytest.mark.parametrize("expr", ["日数 < 'a'", "日数 < 状態", "未知 > 1", "日数(1)", "日数 in 3"])
def test_書式の誤りは読み込み時に止める(expr):
    with pytest.raises(SpecError):
        spec(tables=table((expr, "0")))


# ---- 例のファイル ----


@pytest.mark.parametrize("name,ok,errors", [
    ("refund_v1.yaml", False, 3), ("refund_v2.yaml", True, 0),
    ("order_v1.yaml", False, 4), ("order_v2.yaml", True, 0),
])
def test_例のファイル(name, ok, errors):
    r = check(load(EXAMPLES / name))
    assert r.ok is ok
    assert len([f for f in r.findings if f.severity == ERROR]) == errors
