"""ユースケースごとの保証（使う項目のうち最も弱いもの）。"""
from pathlib import Path

from specgap import WARNING, check, load, parse
from specgap.answer import _yaml
from specgap.guarantee import apply, verify

EXAMPLES = Path(__file__).parent.parent / "examples"


def levels(spec):
    return {u.id: u.level for u in verify(spec).usecases}


def test_ユースケースの保証は使う項目のうち最も弱いもの():
    got = levels(load(EXAMPLES / "shop_v1_interviewed.yaml"))
    assert got["注文する"] == "証明済み"  # 状態機械だけ
    assert got["返品を申し込む"] == "テスト済み"  # 表と状態機械は証明済みでも、操作はテスト済み
    assert set(got.values()) <= {"証明済み", "テスト済み"}


def test_使う表にかかる性質も入る():
    u = next(u for u in verify(load(EXAMPLES / "shop_v1_interviewed.yaml")).usecases if u.id == "返品を申し込む")
    assert "性質「返金は支払額を超えない」" in u.basis


def test_実装のない操作を使うユースケースは保証なしと問う():
    doc = _yaml().load((EXAMPLES / "shop_v1_interviewed.yaml").read_text(encoding="utf-8"))
    del doc["implementation"]["operations"]["不正な支払を記録する"]
    spec = parse(doc, EXAMPLES)
    assert levels(spec)["不正な注文を確かめる"] == "なし"
    report = check(spec)
    apply(report, verify(spec))
    f = next(f for f in report.findings if "ユースケース「不正な注文を確かめる」" in f.title)
    assert f.severity == WARNING and "不正な支払を記録する" in f.detail
