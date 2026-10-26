import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from specgap_lang.ast import show_type
from specgap_lang.check import ERROR, QUESTION, check
from specgap_lang.examples import HOST_MOD, compare_examples, run_crate, runner_source, write_crate
from specgap_lang.hostgen import host_source
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
    assert ("注文", "受付", "決済要求済", "決済要求") in spec["遷移"]
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
    ck = chk(mutate(CODE, "    注文.状態 = 決済要求済", "    注文.状態 = 完了"))
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
    plan = mutate(PLAN, "| TR2 |", "| TR9 | 注文 | 受付 | 完了 | 即時完了 | 仮 |\n| TR2 |")
    fs = static(plan)
    assert any(f.kind == A_ONLY and "受付→完了" in f.where for f in fs)


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


# ---- トリガ ----
def test_トリガの要因が仕様書に出る():
    spec = build(chk(CODE))
    assert ("決済待ち", "応答 決済成功", "決済結果の反映") in spec["トリガ"]
    assert ("決済待ち", "期限 現在+30分", "決済の期限切れ") in spec["トリガ"]


def test_期限の無いトリガは止まる():
    ck = chk(mutate(CODE, "  期限 現在 + 30 分 → 決済の期限切れ\n", ""))
    assert any("期限がありません" in m for m in msgs(ck, ERROR))


def test_待つ先のトリガが未定義だと止まる():
    ck = chk(mutate(CODE, "要求済 → 待つ 決済待ち", "要求済 → 待つ 承認待ち"))
    assert any("承認待ち" in m for m in msgs(ck, ERROR))


def test_トリガの行き先が未定義の処理だと止まる():
    ck = chk(mutate(CODE, "→ 決済の期限切れ\n}", "→ 期限切れ処理\n}"))
    assert any("期限切れ処理" in m for m in msgs(ck, ERROR))


def test_トリガの引数と処理の入力が合わないと止まる():
    ck = chk(mutate(CODE, "トリガ 決済待ち(注文ID: ID)", "トリガ 決済待ち(注文: ID)"))
    assert any("合いません" in m or "入力にもっていません" in m for m in msgs(ck, ERROR))


def test_計画にあるトリガの行き先がコードと違えば検出する():
    plan = mutate(PLAN, "| 期限 現在+30分 | 決済の期限切れ |", "| 期限 現在+30分 | 決済結果の反映 |")
    fs = compare_static(build(chk(CODE)), read_plan(plan))
    assert any(f.kind == DIFF and "トリガ" in f.where for f in fs)


def test_入力の範囲が項目より広いと止まる():
    ck = chk(mutate(CODE, "入力 顧客ID: ID, 明細: 商品 → 整数 1..99", "入力 顧客ID: ID, 明細: 商品 → 整数 1..200"))
    assert any("範囲の広い入力" in m for m in msgs(ck, ERROR))


def test_トリガの型の食い違いと期限の誤りは止まる():
    assert any("型" in m for m in msgs(chk(mutate(CODE, "トリガ 決済待ち(注文ID: ID)", "トリガ 決済待ち(注文ID: 整数)")), ERROR))
    assert any("期限が複数" in m for m in msgs(chk(mutate(CODE, "  期限 現在 + 30 分 → 決済の期限切れ", "  期限 現在 + 30 分 → 決済の期限切れ\n  期限 現在 + 1 時間 → 決済の期限切れ")), ERROR))
    assert any("0より長く" in m for m in msgs(chk(mutate(CODE, "期限 現在 + 30 分", "期限 現在 + 0 分")), ERROR))


# ---- 初回の対話の台帳 ----
def test_台帳は次に聞くことを示し_揃うまで開始不可():
    from specgap_lang import interview as iv

    led = iv.new_ledger("メモ")
    todo, ready = iv.status(led)
    assert not ready and any("一言" in t for t in todo)
    led.update(summary="メモを残す", out_of_scope=["共有"])
    led["usecases"].append({"id": "UC1", "actor": "本人", "goal": "メモを書く", "level": "利用者目標",
                            "main": ["書く", "保存する"], "extensions": [{"at": "2", "cond": "容量不足", "handling": "エラー表示"}],
                            "examples": [{"given": "空", "when": "書く", "then": "1件"}]})
    todo, ready = iv.status(led)
    assert not ready and any("R1" in t for t in todo)
    led["runtime"] = {k: {"value": "x"} for k in iv.RUNTIME}
    assert iv.status(led) == ([], True)


def test_未解決の問いと未仕分けの付加情報は開始を止める():
    from specgap_lang import interview as iv

    led = iv.new_ledger("メモ")
    led.update(summary="a", out_of_scope=["b"], runtime={k: {"value": "x"} for k in iv.RUNTIME})
    led["usecases"].append({"id": "UC1", "level": "利用者目標", "main": ["a"], "extensions": [{"at": "1", "cond": "c", "handling": "h"}], "examples": [{"given": "g", "when": "w", "then": "t"}]})
    led["questions"].append({"id": "Q1", "text": "空のとき", "status": "open"})
    assert not iv.status(led)[1]
    led["questions"][0]["status"] = "unspec"
    led["extras"].append({"id": "X1", "text": "スマホで使いたい"})
    todo, ready = iv.status(led)
    assert any("仕分け" in t for t in todo) and not ready


def test_台帳の状態の打ち間違いと_R1の未規定は止まる():
    from specgap_lang import interview as iv

    led = iv.new_ledger("メモ")
    led.update(summary="a", out_of_scope=["b"])
    led["usecases"].append({"id": "UC1", "level": "利用者目標", "main": ["a"], "extensions": [{"at": "1", "cond": "c", "handling": "h"}], "examples": [{"given": "g", "when": "w", "then": "t"}]})
    led["questions"].append({"id": "Q1", "text": "x", "status": "Open"})
    assert any("不正" in t for t in iv.status(led)[0])
    led["questions"][0].update(status="unspec", answer="結果に影響しないため")
    led["runtime"] = {k: {"status": "answered", "value": "x"} for k in iv.RUNTIME}
    led["runtime"]["R1"] = {"status": "unspec", "value": "決めない"}
    todo, ready = iv.status(led)
    assert not ready and any("R1" in t and "未規定にできません" in t for t in todo)
    led["runtime"]["R1"] = {"status": "answered", "value": "ブラウザ"}
    led["runtime"]["R4"] = {"status": "unspec", "value": "決めない"}
    assert iv.status(led) == ([], True)


def test_台帳から出したplanの表は突合の対象にならない():
    from specgap_lang import interview as iv

    led = iv.new_ledger("メモ")
    led["usecases"].append({"id": "UC1", "goal": "書く", "main": ["書く"]})
    assert read_plan(iv.render(led)) == {}


# ---- ひとり用つぶやき（会話から起こした計画書とコード） ----
TW = EX / "solo_tweet"
TW_CODE = (TW / "solo_tweet.sgl").read_text()
TW_PLAN = (TW / "plan_spec.md").read_text()


def test_つぶやきの検査は通り_計画と静的に一致する():
    ck = chk(TW_CODE)
    assert ck.ok, [str(d) for d in ck.diags]
    fs = compare_static(build(ck), read_plan(TW_PLAN))
    assert [f for f in fs if f.kind != "未規定"] == []


def test_つぶやきの生成物はコミットしたものと一致する():
    ck = chk(TW_CODE)
    committed = TW / "rust" / "src"
    assert (committed / "lib.rs").read_text() == generate(ck) + HOST_MOD, "python -m specgap_lang rust --host で作り直してください"
    assert (committed / "host.rs").read_text() == host_source(ck)


@needs_cargo
def test_つぶやきの具体例を動かすと計画と一致する(tmp_path):
    ck = chk(TW_CODE)
    rows = read_plan(TW_PLAN)["具体例"]
    src, problems = runner_source(ck, rows)
    assert [p for p in problems if p.kind != "未規定"] == []
    write_crate(ck, generate(ck), src, tmp_path)
    assert compare_examples(rows, run_crate(tmp_path)) == []


def test_つぶやきの削除猶予は30秒で_書込待ちは24時間():
    spec = build(chk(TW_CODE))
    assert ("削除猶予", "期限 現在+30秒", "完全に消す") in spec["トリガ"]
    assert ("書込待ち", "期限 現在+24時間", "未反映の通知") in spec["トリガ"]



# ---- 問い合わせ（読むだけの処理） ----
def test_問い合わせの宣言と本体のずれを検出する():
    ck = chk(mutate(TW_CODE, "  読む 投稿.状態, 投稿.書いた日時, 投稿.本文\n}", "  読む 投稿.状態, 投稿.書いた日時\n}"))
    assert any("投稿.本文" in m for m in msgs(ck, ERROR))


def test_問い合わせの絞り込みの入力が無いと止まる():
    ck = chk(mutate(TW_CODE, "絞り込み 本文 含む 単語", "絞り込み 本文 含む 語句"))
    assert any("語句" in m for m in msgs(ck, ERROR))


def test_問い合わせの条件が計画と違うと突合で見つかる():
    code = mutate(TW_CODE, "  条件 状態 == 投稿済\n  並び 書いた日時 新しい順\n  先頭 件数\n  読む 投稿.状態, 投稿.書いた日時\n}\n\n// 日付は", "  条件 状態 != 削除済\n  並び 書いた日時 新しい順\n  先頭 件数\n  読む 投稿.状態, 投稿.書いた日時\n}\n\n// 日付は")
    fs = compare_static(build(chk(code)), read_plan(TW_PLAN))
    assert any(f.kind == DIFF and "一覧を見る" in f.where for f in fs)


def test_圏外の一覧は直近24時間だけ():
    spec = build(chk(TW_CODE))
    q = next(x for x in spec["問い合わせ"] if x["問い合わせ"] == "圏外で見る")
    assert "書いた日時 直近 24時間" in q["条件"]


# ---- 画面（ブラウザで動く形）----
def test_画面は生成したWASMの上で動く():
    """画面の実行部・Dropbox窓口・WASM を1つにまとめ、ブラウザで操作して確かめる。ツールが揃っていなければ飛ばす。"""
    import shutil
    import subprocess
    app = TW / "app"
    have = shutil.which("node") and shutil.which("cargo") and subprocess.run(
        ["node", "-e", "require('playwright')"], capture_output=True).returncode == 0
    targets = subprocess.run(["rustup", "target", "list", "--installed"], capture_output=True, text=True).stdout if shutil.which("rustup") else ""
    if not have or "wasm32-unknown-unknown" not in targets:
        pytest.skip("node・playwright・wasm32 の cargo が揃っていません")
    assert subprocess.run(["python", str(app / "build.py")], capture_output=True, text=True).returncode == 0
    r = subprocess.run(["node", str(app / "check.js")], capture_output=True, text=True, cwd=app)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]


# ---- 出来事（外の出来事をきっかけに処理を起こす）----
def test_出来事の宣言は検査され_計画と突合される():
    spec = build(chk(TW_CODE))
    assert ("つながりが戻った", "各 未反映の投稿", "反映の要求") in spec["出来事"]
    assert ("アプリを開いた", "外から", "投稿の取り込み") in spec["出来事"]
    # 起こす処理の入力が「投稿ID だけ」でないと止まる
    ck = chk(mutate(TW_CODE, "各 未反映の投稿 → 反映の要求\n  外から 投稿の取り込み\n  外から 直しの取り込み\n  外から 消しの取り込み\n}\n", "各 未反映の投稿 → 直す\n  外から 投稿の取り込み\n}\n"))
    assert any("入力は" in m for m in msgs(ck, ERROR))
    # 未定義の問い合わせ
    ck = chk(mutate(TW_CODE, "各 未反映の投稿 → 反映の要求\n  外から 投稿の取り込み\n  外から 直しの取り込み\n  外から 消しの取り込み\n}\n", "各 ない問い合わせ → 反映の要求\n}\n"))
    assert any("ない問い合わせ" in m for m in msgs(ck, ERROR))
    # 計画と違う起こし方
    plan = TW_PLAN.replace("| 画面を引っぱった | 外から | 消しの取り込み |", "| 画面を引っぱった | 外から | 元に戻す |")
    fs = compare_static(spec, read_plan(plan))
    assert any(f.kind in (A_ONLY, B_ONLY) and "出来事" in f.where for f in fs)


def test_行き来を繰り返す状態は_終了なし_と書く():
    assert chk(TW_CODE).ok
    ck = chk(mutate(TW_CODE, "  終了 完全削除済\n", ""))
    assert any("終了" in m for m in msgs(ck, ERROR))


# ---- バイト列と、外部作用が外へ出す内容 ----
def test_バイト列は長さの範囲を持ち_入力の検査で範囲外を止める(tmp_path):
    ck = chk(TW_CODE)
    assert ck.ok
    assert "バイト列 1..20000000" in "\n".join(f"{f.name}: {show_type(f.type)}" for f in ck.data["添付ファイル"].fields)
    lib = generate(ck)
    assert "pub 中身: Vec<u8>" in lib
    assert '範囲検査("中身の長さ"' in lib


def test_外部作用の出す内容が計画とずれたら見つかる():
    spec = build(chk(TW_CODE))
    assert ("Dropbox.ファイルを書く", "添付ID: ID, 名前: 文字列, 種類: 文字列, 中身: バイト列") in spec["外部作用"]
    plan = TW_PLAN.replace("| EF4 | Dropbox.リンクを書く | リンクID: ID, 先: 文字列 |", "| EF4 | Dropbox.リンクを書く | リンクID: ID |")
    assert plan != TW_PLAN
    fs = compare_static(spec, read_plan(plan))
    assert any("外部作用" in f.where for f in fs)
    # コードの側で項目を足したのに計画が古いと、具体例の実行でも見つかる
    ck = chk(mutate(TW_CODE, "外部作用 Dropbox.消す(投稿ID: ID)", "外部作用 Dropbox.消す(投稿ID: ID, 理由: 文字列)"))
    assert any("Dropbox.消す" in f.where for f in compare_static(build(ck), read_plan(TW_PLAN)))


# ---- 束（集合の要素ごとの要求）と、外部作用の失敗の扱い ----
def test_集合の要素ごとの要求は部品が先で本文が最後の束になる():
    ck = chk(TW_CODE)
    assert ck.ok
    lib = generate(ck)
    assert "let 束の始め = 外部列.len();" in lib
    assert "外部列.truncate(束の始め)" in lib
    effs = [e for e, _ in ck.infos["反映の要求"].effects]
    assert effs == ["Dropbox.ファイルを書く", "Dropbox.リンクを書く", "Dropbox.書く"]


def test_各の中には引くことと要求しか書けない():
    ck = chk(mutate(TW_CODE, "      添付 = 添付ファイル[添付ID] なければ 返す 投稿なし\n", "      添付 = 1\n"))
    assert any("各" in m for m in msgs(ck, ERROR))


def test_外部作用の失敗の扱いが決まっていないと止まる():
    # 待たない理由を消す（消すは結果を待つ経路もない）
    ck = chk(mutate(TW_CODE, ' 待たない "消えるのは30秒の猶予のあとで、失敗しても本人は困らない。出せなかったらつながったときにやり直す（J62）"', ""))
    assert any("失敗の扱い" in m and "Dropbox.消す" in m for m in msgs(ck, ERROR))
    # 結果を待つ経路をフローから外す
    ck2 = chk(mutate(TW_CODE, "反映の要求: 要求済 → 待つ 書込待ち,", "反映の要求: 要求済 → 応答,"))
    assert any("失敗の扱い" in m and "Dropbox.書く" in m for m in msgs(ck2, ERROR))


def test_保存先の宣言から未同期の状態を言語が足す():
    ck = chk(TW_CODE)
    assert ck.ok
    assert "記録状態" in ck.states and "記録" in [f.name for f in ck.data["投稿"].fields]
    # 人が書くとエラー（二重の宣言）
    with pytest.raises(ParseError):
        chk(mutate(TW_CODE, "  状態: 投稿状態\n}", "  状態: 投稿状態\n  記録: 記録状態\n}"))
