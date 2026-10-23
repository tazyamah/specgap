import textwrap
from pathlib import Path

import pytest

from specgap import ERROR, WARNING, SpecError, check, load, parse
from specgap import monitor
from specgap.cli import main
from specgap.guarantee import NONE, PROVED, TESTED, VIOLATION, apply, parse_requirement, verify

EXAMPLES = Path(__file__).parent.parent / "examples"
SHOP = EXAMPLES / "shop_v2.yaml"


def titles(report, severity):
    return [f.title for f in report.findings if f.severity == severity and f.check == "実装"]


def run(spec, impl=None, base=None):
    r = check(spec)
    g = verify(spec, impl, base=base)
    apply(r, g)
    return r, g


def mini(tmp_path, code, *, rows=None, policy=None, ensures=None, outputs=None, name="impl.py", tables=None):
    """小さな仕様と実装を tmp_path に作る。"""
    (tmp_path / name).write_text(textwrap.dedent(code), encoding="utf-8")
    data = {
        "spec": "テスト",
        "enums": {"状態": ["未開封", "開封済み"], "方法": ["現金", "ポイント"]},
        "inputs": {"日数": {"type": "int", "min": 0, "max": 100000}, "状態": {"type": "状態"},
                   "額面": {"type": "int", "min": 1, "max": 1000, "example": 100}},
        "outputs": outputs or {"額": {"type": "int", "min": 0}},
        "tables": [{"id": "表", "rows": rows or [
            {"when": "日数 <= 30 and 状態 == 未開封", "then": {"額": "額面"}},
            {"when": "日数 <= 30 and 状態 == 開封済み", "then": {"額": "額面 // 2"}},
            {"when": "日数 > 30", "then": {"額": "0"}},
        ]}],
        "implementation": {"module": name, "tables": tables if tables is not None else {"表": "f"}},
        "policy": policy or {"default": "テスト済み"},
    }
    if ensures:
        data["ensures"] = ensures
    return parse(data, base_dir=tmp_path)


# ---- 例の実装 ----


def test_正しい実装はすべて証明済みになる():
    r, g = run(load(SHOP))
    assert r.ok
    assert {i.id: i.level for i in g.items} == {
        "返金額の決定": PROVED, "返金方法の決定": PROVED, "注文": PROVED, "返金は支払額を超えない": PROVED}
    assert g.item("返金額の決定").basis.startswith("証明")
    assert g.item("返金方法の決定").basis.startswith("全件確認")  # 辞書でも入力が有限なら全件動かせる
    assert g.item("返金方法の決定").monitored
    assert "実装と仕様の一致" in r.passed


def test_バグ入りの実装は具体例つきで拒否する():
    r, g = run(load(SHOP), EXAMPLES / "impl" / "shop_impl_bug.py")
    assert not r.ok
    amount = g.item("返金額の決定")
    assert amount.level == VIOLATION
    assert amount.example == {"経過日数": "14", "商品状態": "未開封", "支払額": "10000"}
    assert (amount.expected, amount.actual) == ({"返金額": "10000"}, {"返金額": "5000"})
    order = g.item("注文")
    assert order.example == {"状態": "返品待ち", "出来事": "到着"}
    assert order.actual == {"次の状態": "完了"}
    assert len(titles(r, ERROR)) == 2


def test_正しくても証明できない書き方は方針に届かず拒否する():
    r, g = run(load(SHOP), EXAMPLES / "impl" / "shop_impl_loop.py")
    assert g.item("返金額の決定").level == TESTED
    assert "For 文" in g.item("返金額の決定").basis
    assert g.item("返金は支払額を超えない").level == TESTED
    errs = titles(r, ERROR)
    assert any("返金額の決定」は方針で「証明済み」が必要ですが、「テスト済み」まで" in t for t in errs)


# ---- テスト ----


def test_テストは仕様の境界のずれを見つける(tmp_path):
    s = mini(tmp_path, """
        def f(日数, 状態, 額面):
            for lo, hi in [(0, 29)]:  # 30日ちょうどが抜けている
                if lo <= 日数 <= hi:
                    return 額面 if 状態 == "未開封" else 額面 // 2
            return 0
    """)
    _, g = run(s)
    it = g.item("表")
    assert it.level == VIOLATION
    assert it.example["日数"] == "30"


def test_テストは実装だけにある境界も調べる(tmp_path):
    s = mini(tmp_path, """
        def f(日数, 状態, 額面):
            for _ in [0]:
                if 日数 == 54321:
                    return 1
            if 日数 > 30:
                return 0
            return 額面 if 状態 == "未開封" else 額面 // 2
    """)
    it = run(s)[1].item("表")
    assert it.level == VIOLATION
    assert it.example["日数"] == "54321"


def test_例外は違反として扱う(tmp_path):
    s = mini(tmp_path, """
        def f(日数, 状態, 額面):
            if 日数 > 30:
                raise ValueError("期限切れ")
            if 状態 == "未開封":
                return 額面
            return 額面 // 2
    """)
    it = run(s)[1].item("表")
    assert it.level == VIOLATION
    assert it.actual == {"額": "例外 ValueError"}


# ---- 証明 ----


def test_代入と複数の出力も証明できる(tmp_path):
    s = mini(tmp_path, """
        def f(日数, 状態, 額面):
            半額 = 額面 // 2
            if 日数 > 30:
                return {"額": 0, "方法": "現金"}
            elif 状態 == "未開封":
                return {"額": 額面, "方法": "現金"}
            else:
                return {"額": 半額, "方法": "ポイント"}
    """, outputs={"額": {"type": "int", "min": 0}, "方法": {"type": "方法"}}, rows=[
        {"when": "日数 <= 30 and 状態 == 未開封", "then": {"額": "額面", "方法": "現金"}},
        {"when": "日数 <= 30 and 状態 == 開封済み", "then": {"額": "額面 // 2", "方法": "ポイント"}},
        {"when": "日数 > 30", "then": {"額": "0", "方法": "unspecified"}},
    ])
    it = run(s)[1].item("表")
    assert it.level == PROVED, it.basis


def test_実装に任せた出力でも範囲外の値は違反(tmp_path):
    s = mini(tmp_path, """
        def f(日数, 状態, 額面):
            if 日数 > 30:
                return -1
            if 状態 == "未開封":
                return 額面
            return 額面 // 2
    """, rows=[
        {"when": "日数 <= 30 and 状態 == 未開封", "then": {"額": "額面"}},
        {"when": "日数 <= 30 and 状態 == 開封済み", "then": {"額": "額面 // 2"}},
        {"when": "日数 > 30", "then": {"額": "unspecified"}},
    ])
    it = run(s)[1].item("表")
    assert it.level == VIOLATION
    assert it.example["日数"] == "31"


def test_性質は表の実装を組み合わせて確かめる(tmp_path):
    rows = [{"when": "日数 <= 30", "then": {"額": "額面"}}, {"when": "日数 > 30", "then": {"額": "unspecified"}}]
    ensures = [{"id": "額面を超えない", "expr": "額 <= 額面"}]
    ok = mini(tmp_path, """
        def f(日数, 額面):
            return 額面 if 日数 <= 30 else 0
    """, rows=rows, ensures=ensures)
    assert run(ok)[1].item("額面を超えない").level == PROVED
    bad = mini(tmp_path, """
        def f(日数, 額面):
            if 日数 <= 30:
                return 額面
            return 額面 + 1
    """, rows=rows, ensures=ensures, name="bad.py")
    _, g = run(bad)
    assert g.item("表").level == PROVED  # 表の上では実装に任せた範囲
    it = g.item("額面を超えない")
    assert it.level == VIOLATION
    assert it.example["日数"] == "31"


# ---- 対応と方針 ----


def test_実装が対応づけられていない項目は確認に回す(tmp_path):
    s = mini(tmp_path, "x = 1\n", tables={})
    r, g = run(s)
    assert g.item("表").level == NONE
    assert any("対応する実装がありません" in t for t in titles(r, WARNING))


def test_無い関数は拒否する(tmp_path):
    s = mini(tmp_path, "x = 1\n")
    r, g = run(s)
    assert g.item("表").level == VIOLATION
    assert "関数 f が実装ファイルにありません" in g.item("表").basis


def test_前の版より保証が下がったら確認に回す(tmp_path):
    proved = """
        def f(日数, 状態, 額面):
            if 日数 > 30:
                return 0
            return 額面 if 状態 == "未開封" else 額面 // 2
    """
    looped = """
        def f(日数, 状態, 額面):
            for _ in [0]:
                pass
            if 日数 > 30:
                return 0
            return 額面 if 状態 == "未開封" else 額面 // 2
    """
    base = mini(tmp_path, proved, name="a.py")
    head = mini(tmp_path, looped, name="b.py")
    r, g = run(head, base=base)
    assert g.item("表").before == PROVED
    assert any("前の版より下がりました（証明済み → テスト済み）" in t for t in titles(r, WARNING))
    assert r.ok  # 方針（テスト済み）の範囲内なので拒否はしない


def test_方針の書き方():
    r = parse_requirement("テスト済み＋監視")
    assert (r.level, r.monitored) == (TESTED, True)
    assert parse_requirement("証明済み").monitored is False
    with pytest.raises(SpecError):
        parse_requirement("たぶん大丈夫")


def test_監視が方針で必要なら監視なしは拒否する(tmp_path):
    s = mini(tmp_path, """
        def f(日数, 状態, 額面):
            if 日数 > 30:
                return 0
            return 額面 if 状態 == "未開封" else 額面 // 2
    """, policy={"default": "テスト済み＋監視"})
    r, g = run(s)
    assert g.item("表").level == PROVED and not g.item("表").monitored
    assert any("「テスト済み＋監視」が必要" in t for t in titles(r, ERROR))


# ---- 実行時の監視 ----


def test_監視は仕様と違う結果を止める(tmp_path):
    spec = load(SHOP)

    @monitor.watch("返金額の決定")
    def wrong(経過日数, 商品状態, 支払額):
        return 支払額

    @monitor.watch("注文")
    def order(状態, 出来事):
        return "完了"

    monitor.use(None)
    with pytest.raises(RuntimeError):
        wrong(経過日数=1, 商品状態="未開封", 支払額=100)
    monitor.use(spec)
    try:
        assert wrong(経過日数=1, 商品状態="未開封", 支払額=100) == 100
        with pytest.raises(monitor.SpecViolation) as e:
            wrong(経過日数=20, 商品状態="未開封", 支払額=100)
        assert e.value.expected == {"返金額": "50"}
        assert order("発送済み", "到着") == "完了"
        with pytest.raises(monitor.SpecViolation):
            order("返品待ち", "到着")
    finally:
        monitor.use(None)


def test_監視つきの関数も保証の対象は元の関数():
    _, g = run(load(SHOP))
    assert g.item("返金方法の決定").monitored
    assert not g.item("返金額の決定").monitored


# ---- コマンドライン ----


def test_cli_の_impl_で実装を差し替える(capsys):
    assert main(["check", str(SHOP)]) == 0
    assert main(["check", str(SHOP), "--impl", str(EXAMPLES / "impl" / "shop_impl_bug.py")]) == 1
    out = capsys.readouterr().out
    assert "実装が仕様どおりか（shop_impl_bug.py）" in out
    assert "経過日数=14、商品状態=未開封、支払額=10000" in out


def test_画面に実装の節が出る(tmp_path):
    out = tmp_path / "v.html"
    assert main(["view", str(SHOP), "--impl", str(EXAMPLES / "impl" / "shop_impl_bug.py"), "-o", str(out)]) == 0
    html = out.read_text(encoding="utf-8")
    assert "実装が仕様どおりか" in html
    assert "shop_impl_bug.py" in html
    assert "実装が仕様どおりでない、または方針の保証に届かない項目が 2 件あります" in html
