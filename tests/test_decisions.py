import importlib.util
import shutil
from pathlib import Path

import pytest

from specgap import ask, check, decide, load
from specgap.cli import main
from specgap.decisions import current, exists
from specgap.guarantee import PROVED, apply, verify

EXAMPLES = Path(__file__).parent.parent / "examples"
INTERVIEWED = EXAMPLES / "shop_v1_interviewed.yaml"


@pytest.fixture
def shop(tmp_path):
    p = tmp_path / "shop_v1.yaml"
    shutil.copy(EXAMPLES / "shop_v1.yaml", p)
    return p


def test_答えるたびに判断が正本に残る(shop):
    s = ask.session(shop)
    for ans, said in [("減る", "はい。減ります。"), ("減る", ""), ("半分", "半分でいいよ"), ("29 以下と同じ", "1"), ("正しい", "1")]:
        p, _ = ask.next_packet(s)
        text, ok = ask.reply(s, p.id, ans, said)
        assert ok and "（判断 D" in text
    spec = load(s.work)
    assert [d.id for d in spec.decisions] == ["D1", "D2", "D3", "D4", "D5"]
    d1 = spec.decisions[0]
    assert (d1.title, d1.answer, d1.said) == ("経過日数が増えると返金額は増えない", "減る", "はい。減ります。")
    assert d1.applies_to == ["ルール:経過日数が増えると返金額は増えない"]
    assert spec.decisions[4].applies_to == [
        "表:返金額の決定:経過日数 == 30 and 商品状態 == 未開封",
        "表:返金額の決定:経過日数 == 30 and 商品状態 == 開封済み",
        "表:返金額の決定:経過日数 >= 31 and 商品状態 == 開封済み"]
    assert all(exists(spec, r) for d in spec.decisions for r in d.applies_to)


def test_置き換えた判断は有効な判断に数えない():
    spec = load(INTERVIEWED)
    live = {d.id for d in current(spec)}
    assert {"D1", "D2", "D3"}.isdisjoint(live) and "D9" in live


def test_効いていた場所が消えた判断は確認に回す(tmp_path):
    text = INTERVIEWED.read_text(encoding="utf-8").replace("ルール:経過日数が増えると返金額は増えない", "ルール:消えたルール")
    p = tmp_path / "s.yaml"
    p.write_text(text, encoding="utf-8")
    shutil.copytree(EXAMPLES / "impl", tmp_path / "impl")
    r = check(load(p))
    assert any(f.check == "判断" and "判断 D5" in f.title for f in r.findings)


def test_判断を_ADR_として書き出す(tmp_path, capsys):
    assert main(["decisions", str(INTERVIEWED), "-o", str(tmp_path)]) == 0
    assert "37 件の判断" in capsys.readouterr().out
    d22 = (tmp_path / "D22.md").read_text(encoding="utf-8")
    assert d22.startswith("# D22: 外への依頼の前に処理中と記録し")
    assert "> そうだね。それでいいや。6は担当者で。" in d22
    assert "- 1つの注文につき集荷と返金は1回まで" in d22
    assert "- 状態: 置き換え済み（D9）" in (tmp_path / "D1.md").read_text(encoding="utf-8")
    assert "| [D9](D9.md) |" in (tmp_path / "README.md").read_text(encoding="utf-8")


def _impl():
    spec = importlib.util.spec_from_file_location("shop_v1_impl", EXAMPLES / "impl" / "shop_v1_impl.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_判断に任せた実装は値と理由を返す():
    m = _impl()
    decide.use(None)
    with pytest.raises(RuntimeError):
        m.refund_amount(経過日数=1, 商品状態="未開封", 支払額=100)
    decide.use(load(INTERVIEWED))
    try:
        assert m.refund_amount(経過日数=30, 商品状態="開封済み", 支払額=10000) == 5000
        why = m.refund_amount.why(経過日数=30, 商品状態="開封済み", 支払額=10000)
        assert why.row == 5 and [i for i, _ in why.because][:1] == ["D9"]
        assert "D8「経過日数が30のときは29と同じ扱い」" in why.reason()
        assert m.next_order_state("発送済み", "キャンセル") is None
        assert m.next_order_state.why("発送済み", "支払").because[0][0] == "D4"
    finally:
        decide.use(None)


def test_判断に任せた実装は構造上証明済み():
    spec = load(INTERVIEWED)
    g = verify(spec)
    assert g.item("返金額の決定").level == PROVED and "構造上一致" in g.item("返金額の決定").basis
    assert g.item("注文").level == PROVED
    assert g.item("返金は支払額を超えない").level == PROVED
    r = check(spec)
    apply(r, g)
    assert r.ok


def test_実装に任せた行は_otherwise_が決める(tmp_path):
    from specgap import parse
    s = parse({"spec": "t", "inputs": {"日数": {"type": "int", "min": 0, "max": 10}}, "outputs": {"額": {"type": "int"}},
               "tables": [{"id": "表", "rows": [{"when": "日数 <= 5", "then": {"額": 1}},
                                                {"when": "日数 > 5", "then": {"額": "unspecified"}}]}]})
    decide.use(s)
    try:
        f = decide.table("表")
        assert f(日数=1) == 1
        with pytest.raises(decide.Undecided):
            f(日数=7)
        assert decide.table("表", otherwise=lambda 日数: 日数 * 10)(日数=7) == 70
    finally:
        decide.use(None)
