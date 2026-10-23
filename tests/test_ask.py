import json
import shutil
from pathlib import Path

import pytest

from specgap import ask, check, load
from specgap.cli import main

EXAMPLES = Path(__file__).parent.parent / "examples"


@pytest.fixture
def shop(tmp_path):
    p = tmp_path / "shop_v1.yaml"
    shutil.copy(EXAMPLES / "shop_v1.yaml", p)
    return p


def first(packet):
    """どの種類の問いにも、とりあえず通る答えを返す。"""
    t = packet_slot(packet)["type"]
    if t == "gap":
        return "0"
    if t == "data_over":
        return "渡さない"
    if packet.choices:
        return packet.choices[0]
    return "サポート担当が確認する"


def packet_slot(packet):
    return packet._slot


@pytest.fixture(autouse=True)
def keep_slot(monkeypatch):
    real = ask.packet

    def wrapped(spec, q, remaining):
        p = real(spec, q, remaining)
        p._slot = q.slot
        return p

    monkeypatch.setattr(ask, "packet", wrapped)


def test_包みには1問に必要なものがそろう(shop):
    p, _ = ask.next_packet(ask.session(shop))
    assert p.id.startswith("Q") and p.remaining == 16
    assert p.question == "経過日数=30、商品状態=開封済み のとき、どうしますか"
    assert p.context[0] == "表「返金額の決定」（今ある行）"
    assert "答えると加わる行の条件：経過日数 == 30 and 商品状態 == 開封済み" in p.context
    text = ask.to_text(p)
    assert text.startswith("[AI への指示] この問いを1つだけ")
    assert "具体例：" not in text  # 問いの中に出ているので繰り返さない


def test_状態の問いには選択肢と今の遷移が付く(shop):
    s = ask.session(shop)
    for _ in range(30):
        p, _ = ask.next_packet(s)
        if packet_slot(p)["type"] == "state":
            break
        ask.reply(s, p.id, first(p))
    assert p.choices[-1] == "拒否：理由"
    assert p.context[0].startswith("状態機械「注文」の")


def test_答えるたびに作業中の版が変わり元の仕様は変わらない(shop):
    original = shop.read_text(encoding="utf-8")
    s = ask.session(shop)
    p, _ = ask.next_packet(s)
    text, ok = ask.reply(s, p.id, ask.parse_answer("支払額 // 2"), said="半額で")
    assert ok
    assert text.startswith("反映しました：表「返金額の決定」に行を追加")
    assert shop.read_text(encoding="utf-8") == original
    assert s.work == shop.with_name("shop_v1.work.yaml")
    row = json.loads(s.log.read_text(encoding="utf-8").splitlines()[0])
    assert (row["id"], row["answer"], row["said"], row["from"]) == (p.id, {"返金額": "支払額 // 2"}, "半額で", "shop_v1.yaml")
    q, _ = ask.next_packet(s)
    assert q.id != p.id and q.remaining == 15


def test_もう無い問いや読めない答えは反映しない(shop):
    s = ask.session(shop)
    p, _ = ask.next_packet(s)
    ask.reply(s, p.id, "0")
    text, ok = ask.reply(s, p.id, "0")
    assert not ok and "今の版にありません" in text
    q, _ = ask.next_packet(s)
    before = s.work.read_text(encoding="utf-8")
    text, ok = ask.reply(s, q.id, "支払額 +")
    assert not ok and "人に聞き直してください" in text and q.id in text
    assert s.work.read_text(encoding="utf-8") == before
    assert len(s.log.read_text(encoding="utf-8").splitlines()) == 1


def test_1問ずつ答えていくと問いがなくなる(shop):
    s = ask.session(shop)
    for n in range(40):
        p, _ = ask.next_packet(s)
        if p is None:
            break
        _, ok = ask.reply(s, p.id, ask.parse_answer(first(p)))
        assert ok, p
    assert p is None
    assert n >= 15  # 1つの答えで消える問いもある
    assert check(load(s.work)).ok
    assert "問いは残っていません" in ask.to_text(None, check(load(s.work)))


def test_cli_の_ask_と_reply(shop, capsys):
    assert main(["ask", str(shop)]) == 0
    qid = capsys.readouterr().out.split("問い ", 1)[1].split("（", 1)[0]
    assert main(["reply", str(shop), qid, "支払額", "--said", "全額"]) == 0
    assert "反映しました" in capsys.readouterr().out
    assert main(["reply", str(shop), qid, "支払額"]) == 1


def test_mcp_の道具は2つ():
    pytest.importorskip("mcp")
    import asyncio

    from specgap.mcp_server import build

    tools = asyncio.run(build().list_tools())
    assert sorted(t.name for t in tools) == ["answer_question", "next_question"]


def test_数の穴にはほかの行の値が候補として付く(shop):
    p, _ = ask.next_packet(ask.session(shop))
    assert p.choices == ["支払額", "支払額 // 2", "0", "unspecified"]
    assert "1. 支払額 ／ 2. 支払額 // 2" in ask.to_text(p)
