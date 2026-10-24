"""完成の判定（拒否・確認 0、項目とユースケースがテスト済み以上）。"""
from pathlib import Path

from specgap import check, load, parse
from specgap.answer import _yaml
from specgap.completion import summary, unmet
from specgap.guarantee import apply, verify

EXAMPLES = Path(__file__).parent.parent / "examples"


def report_of(spec):
    r = check(spec)
    apply(r, verify(spec))
    return r


def test_お店の例は完成している():
    r = report_of(load(EXAMPLES / "shop_v1_interviewed.yaml"))
    assert unmet(r) == [] and summary(r).startswith("完成")


def test_実装を1つ外すと未完成になり_理由を挙げる():
    doc = _yaml().load((EXAMPLES / "shop_v1_interviewed.yaml").read_text(encoding="utf-8"))
    del doc["implementation"]["operations"]["重複した発送を記録する"]
    rest = unmet(report_of(parse(doc, EXAMPLES)))
    assert any(x.startswith("確認が") for x in rest)
    assert any("操作「重複した発送を記録する」（実装なし）" in x for x in rest)
    assert any("「重複した発送を確かめる」（なし）" in x for x in rest)


def test_画面だけのユースケースがあると未完成():
    assert "返金状況を確認する" in summary(report_of(load(EXAMPLES / "shop_v2.yaml")))


def test_実装がなければ未完成():
    r = check(load(EXAMPLES / "shop_v1.yaml"))
    assert any("実装が書かれていない" in x for x in unmet(r))
