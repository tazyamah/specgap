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


@pytest.fixture
def cells(tmp_path):
    """穴を1つずつ聞く（ルールから聞かない）版。"""
    p = tmp_path / "shop_v1.yaml"
    text = (EXAMPLES / "shop_v1.yaml").read_text(encoding="utf-8")
    p.write_text(text.replace("  - id: 返金額の決定\n", "  - id: 返金額の決定\n    by_cells: true\n"), encoding="utf-8")
    return p


def first(packet):
    """どの種類の問いにも、とりあえず通る答えを返す。"""
    t = packet_slot(packet)["type"]
    if t == "open":
        return "このままでよい"
    if t == "rule_trend":
        return packet_slot(packet)["fits"][0].replace("減る", "減る（か同じ）") if packet_slot(packet)["fits"] else "場合による"
    if t == "rule_relate":
        fits = packet_slot(packet)["fits"]
        return {"同じ": "同じ", "0": "0"}.get(fits[0], "半分") if fits else "決めない"
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


def test_包みには1問に必要なものがそろう(cells):
    p, _ = ask.next_packet(ask.session(cells))
    assert p.id.startswith("Q") and p.remaining == 18  # 機械的に直せる 16 問と、正本の形を変える答えが要る確認 2 問
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


def test_答えるたびに作業中の版が変わり元の仕様は変わらない(cells):
    original = cells.read_text(encoding="utf-8")
    s = ask.session(cells)
    p, _ = ask.next_packet(s)
    text, ok = ask.reply(s, p.id, ask.parse_answer("支払額 // 2"), said="半額で")
    assert ok
    assert text.startswith("反映しました：表「返金額の決定」に行を追加")
    assert cells.read_text(encoding="utf-8") == original
    assert s.work == cells.with_name("shop_v1.work.yaml")
    row = json.loads(s.log.read_text(encoding="utf-8").splitlines()[0])
    assert (row["id"], row["answer"], row["said"], row["from"]) == (p.id, {"返金額": "支払額 // 2"}, "半額で", "shop_v1.yaml")
    q, _ = ask.next_packet(s)
    assert q.id != p.id and q.remaining == 17


def test_もう無い問いや読めない答えは反映しない(cells):
    s = ask.session(cells)
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
    assert main(["reply", str(shop), qid, "減る", "--said", "日がたつほど減る"]) == 0
    assert "反映しました：ルール「経過日数が増えると返金額は増えない」" in capsys.readouterr().out
    assert main(["reply", str(shop), qid, "減る"]) == 1


# ---- ルールから聞く ----


def test_穴のある表では先にルールを聞き_組み立てた表を確かめる(shop):
    s = ask.session(shop)
    p, _ = ask.next_packet(s)
    assert p.question == "経過日数が増えると、返金額はどうなりますか"
    assert "| 30       | ？     | ？          |" in p.context
    assert "今の行に合うのは：減る" in p.context
    for ans in ["減る", "減る"]:
        assert ask.reply(s, p.id, ans)[1]
        p, _ = ask.next_packet(s)
    assert p.question == "商品状態が開封済みのときの返金額は、未開封のときと比べてどうなりますか"
    assert "今の行に合うのは：半分" in p.context
    ask.reply(s, p.id, "半分")
    p, _ = ask.next_packet(s)
    assert p.question == "経過日数が 30 のときは、29 以下と 31 以上のどちらと同じ扱いですか"  # 2つの列をまとめて1問
    ask.reply(s, p.id, "29 以下と同じ")
    p, _ = ask.next_packet(s)
    assert p.question == "ルールを合わせると、表はこうなります。これで正しいですか"
    assert "| 30       | 支払額 * | 支払額 // 2 * |" in p.context
    assert "| 31〜3650 | 0        | 0 *           |" in p.context
    ask.reply(s, p.id, "正しい")
    spec = load(s.work)
    assert [r.id for r in spec.rules] == ["経過日数が増えると返金額は増えない", "商品状態が進むと返金額は増えない",
                                          "開封済みの返金額は未開封のときの半分", "経過日数が30のときは29と同じ扱い"]
    r = check(spec)
    assert not [f for f in r.findings if f.ref == "返金額の決定" and f.severity == "error"]
    assert "ルールと決定表の整合" in r.passed


def test_今の表と合わないルールの答えは反映しない(shop):
    s = ask.session(shop)
    p, _ = ask.next_packet(s)
    text, ok = ask.reply(s, p.id, "増える")
    assert not ok and "このルールは今の表と合いません" in text
    assert not s.work.exists()


def test_ルールに反する行は拒否する(tmp_path):
    from specgap import parse
    data = {"spec": "t", "enums": {"状態": ["未開封", "開封済み"]},
            "inputs": {"日数": {"type": "int", "min": 0, "max": 100}, "状態": {"type": "状態"}},
            "outputs": {"額": {"type": "int", "min": 0}},
            "tables": [{"id": "表", "rows": [
                {"when": "日数 <= 30 and 状態 == 未開封", "then": {"額": 100}},
                {"when": "日数 <= 30 and 状態 == 開封済み", "then": {"額": 80}},
                {"when": "日数 > 30", "then": {"額": 120}}]}],
            "rules": [{"id": "日がたつほど減る", "output": "額", "by": "日数", "trend": "減る"},
                      {"id": "開封済みは半分", "output": "額", "by": "状態", "from": "未開封", "to": "開封済み", "then": "額 // 2"}]}
    r = check(parse(data))
    errs = {f.title: f.detail for f in r.findings if f.check == "ルール"}
    detail = errs["表「表」がルール「日がたつほど減る」に反しています"]
    assert detail.startswith("日数=30、") and "日数=31、" in detail and detail.endswith("額=120 です。")
    assert "表「表」がルール「開封済みは半分」に反しています" in errs


def test_mcp_の道具は3つ():
    pytest.importorskip("mcp")
    import asyncio

    from specgap.mcp_server import build

    tools = asyncio.run(build().list_tools())
    assert sorted(t.name for t in tools) == ["answer_question", "change_spec", "next_question"]


def test_数の穴にはほかの行の値が候補として付く(cells):
    p, _ = ask.next_packet(ask.session(cells))
    assert p.choices == ["支払額", "支払額 // 2", "0", "unspecified"]
    assert "1. 支払額 ／ 2. 支払額 // 2" in ask.to_text(p)
