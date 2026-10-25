import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from specgap_lang.check import ERROR, QUESTION, check
from specgap_lang.examples import compare_examples, run_crate, runner_source, write_crate
from specgap_lang.parser import ParseError, parse
from specgap_lang.plan import A_ONLY, B_ONLY, DIFF, compare_static, read_plan
from specgap_lang.rustgen import generate
from specgap_lang.spec import build

ROOT = Path(__file__).parent.parent
EX = ROOT / "lang_examples"
CODE = (EX / "shop.sgl").read_text()
PLAN = (EX / "shop_plan.md").read_text()
needs_cargo = pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo が無い")


def chk(src):
    return check(parse(src))


def msgs(ck, level):
    return [d.msg for d in ck.diags if d.level == level]


def mutate(src, old, new):
    assert old in src, old
    return src.replace(old, new, 1)


# ---- 正常系 ----
def test_お店の例は検査を通る():
    ck = chk(CODE)
    assert ck.ok, ck.diags
    assert not msgs(ck, QUESTION)


def test_不変条件は証明済みと出る():
    ck = chk(CODE)
    text = " ".join(s for _, rows in ck.invariant_status for _, s in rows)
    assert "証明できない" not in text and "減算の前に不足を確認" in text


def test_仕様書は読み書きと遷移をコードから取り出す():
    spec = build(chk(CODE))
    shop = {x["処理"]: x for x in spec["処理"]}
    assert shop["受注"]["書く"] == ["商品.在庫", "注文"]
    assert ("注文", "受付", "決済待ち", "決済要求") in spec["遷移"]
    assert shop["決済要求"]["外部"] == ["決済.請求(冪等キー=注文ID)"]


def test_物理数は範囲から選ばれる():
    spec = build(chk(CODE))
    assert dict(spec["実現"])["商品.在庫"] == "u64"
    assert ("明細.値", "u8") in next(x for x in spec["処理"] if x["処理"] == "受注")["物理数"]


# ---- 検査が止める例（構文のスケッチ §3 の表） ----
def test_丸めの指定が無いと問いになる():
    ck = chk(mutate(CODE, "合計 = 小計 + 丸め(小計 * 税率, 切り捨て, 円)", "合計 = 小計 + 小計 * 税率"))
    assert any("端数をどう丸めますか" in m for m in msgs(ck, QUESTION))


def test_結果に行き先が無いと止まる():
    ck = chk(mutate(CODE, ", 顧客なし → 応答\n", "\n"))
    assert any("顧客なし" in m and "行き先" in m for m in msgs(ck, ERROR))


def test_冪等キーが無いと止まる():
    ck = chk(mutate(CODE, ", 冪等キー = 注文ID)", ")"))
    assert any("冪等キー" in m for m in msgs(ck, ERROR))


def test_宣言に無い遷移は止まる():
    ck = chk(mutate(CODE, "    注文.状態 = 決済待ち", "    注文.状態 = 完了"))
    assert any("遷移" in d.code and "完了" in d.msg for d in ck.diags if d.level == ERROR)


def test_元の状態の確認が無いと止まる():
    ck = chk(mutate(CODE, "    もし 注文.状態 != 受付 なら 返す 状態違い\n", ""))
    assert any("確認" in m for m in msgs(ck, ERROR))


def test_在庫不足の判定を削ると不変条件が示せない():
    ck = chk(mutate(CODE, "    もし 不足 が 空でない なら 返す 在庫不足(不足)\n", ""))
    assert any("反例" in m for m in msgs(ck, ERROR))


def test_書く項目の宣言漏れは止まる():
    ck = chk(mutate(CODE, "  書く 商品.在庫, 注文\n", "  書く 注文\n"))
    assert any("商品.在庫" in m for m in msgs(ck, ERROR))


def test_合計ゼロの確認を削ると不変条件が示せない():
    ck = chk(mutate(CODE, "    もし 注文.合計 <= 0 なら 返す 合計ゼロ\n", ""))
    assert any("合計 > 0" in m for m in msgs(ck, ERROR))


def test_存在を確かめない参照は問いになる():
    ck = chk(mutate(CODE, "    顧客 = 顧客[顧客ID] なければ 返す 顧客なし", "    顧客 = 顧客[顧客ID]"))
    assert any("存在しない" in m for m in msgs(ck, QUESTION))


def test_構文エラーは行番号つき():
    with pytest.raises(ParseError, match="行目"):
        parse("データ 商品 {\n  在庫 整数\n}\n")


# ---- Rust 生成 ----
def test_エラーのあるコードからは生成しない():
    with pytest.raises(AssertionError):
        generate(chk(mutate(CODE, ", 冪等キー = 注文ID)", ")")))


def test_生成は決定的で_コミットした生成物と一致する():
    ck = chk(CODE)
    assert generate(ck) == generate(chk(CODE))
    committed = EX / "shop_rust" / "src" / "lib.rs"
    assert committed.read_text() == generate(ck), "python -m specgap_lang rust で生成物を作り直してください"


# ---- 突合 ----
def static(plan_text):
    return compare_static(build(chk(CODE)), read_plan(plan_text))


def test_お店の例は計画と静的に一致する():
    assert [f for f in static(PLAN) if f.kind != "未規定"] == []


def test_計画にある遷移がコードに無いと検出する():
    plan = mutate(PLAN, "| TR2 |", "| TR3 | 注文 | 決済待ち | 完了 | 決済結果の反映 | 仮 |\n| TR2 |")
    fs = static(plan)
    assert any(f.kind == A_ONLY and "決済待ち→完了" in f.where for f in fs)


def test_コードが計画に無いものを書き込むと検出する():
    plan = mutate(PLAN, "| 商品.在庫, 注文 |", "| 商品.在庫 |")
    fs = static(plan)
    assert any(f.kind == DIFF and "書く" in f.where and "注文" in f.msg for f in fs)


def test_範囲の食い違いを検出する():
    fs = static(mutate(PLAN, "| 在庫 | 整数 0.. |", "| 在庫 | 整数 1.. |"))
    assert any(f.kind == DIFF and "商品.在庫" in f.where for f in fs)


def test_計画に無い項目がコードにあると検出する():
    fs = static(mutate(PLAN, "| DA3 | 商品 | 単価 | 金額(円) 0.. | ○ |  | 仮 |\n", ""))
    assert any(f.kind == B_ONLY and "商品.単価" in f.where for f in fs)


@needs_cargo
def test_具体例を実際に動かして計画と一致する(tmp_path):
    ck = chk(CODE)
    rows = read_plan(PLAN)["具体例"]
    src, problems = runner_source(ck, rows)
    assert [p for p in problems if p.kind != "未規定"] == []
    write_crate(ck, generate(ck), src, tmp_path)
    actual = run_crate(tmp_path)
    assert actual["EX1"][0] == "受付(N1)"
    assert compare_examples(rows, actual) == []


@needs_cargo
def test_具体例が計画と違えば検出する(tmp_path):
    ck = chk(CODE)
    rows = read_plan(mutate(PLAN, "| 在庫不足({A}) | なし |", "| 受付(N1) | なし |"))["具体例"]
    src, _ = runner_source(ck, rows)
    write_crate(ck, generate(ck), src, tmp_path)
    fs = compare_examples(rows, run_crate(tmp_path))
    assert any("EX2" in f.where and "結果" in f.where for f in fs)


def test_cli_compare(tmp_path):
    r = subprocess.run([sys.executable, "-m", "specgap_lang", "compare", str(EX / "shop.sgl"), str(EX / "shop_plan.md"), "--no-run"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
