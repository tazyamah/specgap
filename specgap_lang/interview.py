"""初回の対話で仕様を作るための台帳（ledger）。会話の進め方は skills/plan-interview/SKILL.md。

台帳は JSON。AI が一問ごとに答えを書き込み、`status` が次に聞くことを示し、`render` が plan の仕様書（①）の会話の部分を Markdown にする。
台帳は plan（①）の元で、コードから作らない（突合の独立性を保つ）。暫定の Python 実装（最終は Rust）。

台帳の形:
  title, summary, out_of_scope[]            概要と範囲外
  usecases[]  id, actor, goal, level, main[], extensions[{at, cond, handling}], rules[], examples[{given, when, then}]
  questions[] id, text, usecase(任意), status(open|unspec|answered), answer   未解決の問い（unspec＝意図的に未規定）
  extras[]    id, text, from_usecase, kind(runtime|constraint|quality|other)    返答に混ざっていた付加情報の置き場
  runtime{}   R1..R7 の答え（値と来歴）
  judgments[] id, question, answer, who, when                                 判断の記録
"""
import json
from pathlib import Path

# 必ず聞く動作要件（notes/spec-runtime-requirements-checklist.md の R1〜R7）
RUNTIME = {
    "R1": "動作するプラットフォーム（スマホ／PC／ブラウザ／サーバ／組み込み）",
    "R2": "使う場所と接続（常時オンライン／ときどきオフライン／完全オフライン）",
    "R3": "データを残すか、どこに（残さない／端末内／サーバのDB／既存のDB）",
    "R4": "利用者の数と同時利用",
    "R5": "外部とのつながり（決済、メール、外部API、認証基盤など）",
    "R6": "配る方法（自分だけ／他の人へ配る／サーバに配備）",
    "R7": "画面の有無と種類",
}
LEVELS = ("要約", "利用者目標", "下位機能")


def new_ledger(title: str) -> dict:
    return {"title": title, "summary": "", "out_of_scope": [], "usecases": [], "questions": [], "extras": [], "runtime": {}, "judgments": []}


def load(path) -> dict:
    return json.loads(Path(path).read_text())


def save(path, led: dict):
    Path(path).write_text(json.dumps(led, ensure_ascii=False, indent=2) + "\n")


def usecase_gaps(u: dict) -> list[str]:
    gaps = []
    if not u.get("main"):
        gaps.append("主な流れ（成功の道）が未記入")
    if not u.get("extensions"):
        gaps.append("失敗・例外・分岐（拡張）が未記入")
    if not u.get("examples"):
        gaps.append("具体例が未記入")
    if u.get("level") not in LEVELS:
        gaps.append(f"目標の粒度が未記入（{'／'.join(LEVELS)}）")
    return gaps


def open_questions(led: dict) -> list[dict]:
    return [q for q in led["questions"] if q.get("status", "open") == "open"]


def status(led: dict) -> tuple[list[str], bool]:
    """次に聞くことの一覧と、コードを書き始めてよいか。"""
    todo: list[str] = []
    if not led["summary"]:
        todo.append("作るものの一言（summary）")
    if not led["out_of_scope"]:
        todo.append("範囲外（out_of_scope）。無ければ「なし」と記入")
    if not led["usecases"]:
        todo.append("アクターと目標の一覧（usecases）。「他に使う人は？ 他にやりたいことは？」と聞く")
    for u in led["usecases"]:
        for g in usecase_gaps(u):
            todo.append(f"{u['id']} {u.get('goal', '')}: {g}")
    for q in open_questions(led):
        todo.append(f"未解決の問い {q['id']}: {q['text']}")
    unsorted = [x for x in led["extras"] if x.get("kind") is None]
    for x in unsorted:
        todo.append(f"付加情報 {x['id']} の仕分け: {x['text']}")
    ready_uc = bool(led["usecases"]) and not any(t for t in todo if not t.startswith("付加情報"))
    if ready_uc:
        for k, text in RUNTIME.items():
            if not led["runtime"].get(k, {}).get("value"):
                todo.append(f"動作要件 {k}: {text}")
    ready = ready_uc and all(led["runtime"].get(k, {}).get("value") for k in RUNTIME)
    return todo, ready


def render(led: dict) -> str:
    out = [f"# 仕様書（plan）：{led['title']}", "", "会話で作ったレビュー対象の仕様書（①）の会話の部分。台帳から生成した。決まっていないことは「**未規定**」と書く。", ""]
    out += ["## 0. 概要（文章。突合しない）", "", led["summary"] or "**未規定**", ""]
    out += ["範囲外: " + ("、".join(led["out_of_scope"]) or "**未規定**"), ""]
    out += ["## 1. ユースケース（Cockburn。文章。コードの起こしの元）", ""]
    for u in led["usecases"]:
        out += [f"### {u['id']} {u.get('goal', '')}（アクター: {u.get('actor', '')}／粒度: {u.get('level') or '**未規定**'}）", ""]
        out += ["主な流れ:"] + [f"{i}. {s}" for i, s in enumerate(u.get("main", []), 1)] + [""]
        if u.get("extensions"):
            out += ["拡張（失敗・例外・分岐）:"] + [f"- {e['at']}: {e['cond']} → {e['handling']}" for e in u["extensions"]] + [""]
        if u.get("rules"):
            out += ["ルール:"] + [f"- {r}" for r in u["rules"]] + [""]
        if u.get("examples"):
            out += ["具体例:"] + [f"- 前提 {e['given']} ／ 操作 {e['when']} ／ 期待 {e['then']}" for e in u["examples"]] + [""]
    out += ["## 2. 動作要件", "", "| ID | 聞くこと | 答え | 来歴 |", "|---|---|---|---|"]
    for k, text in RUNTIME.items():
        r = led["runtime"].get(k, {})
        out.append(f"| {k} | {text} | {r.get('value') or '**未規定**（まだ聞いていない）'} | {r.get('from', '')} |")
    out += [""]
    if led["extras"]:
        out += ["## 3. 返答に混ざっていた付加情報（仕分け済みの置き場）", "", "| ID | 内容 | 出どころ | 種別 |", "|---|---|---|---|"]
        out += [f"| {x['id']} | {x['text']} | {x.get('from_usecase', '')} | {x.get('kind') or '未仕分け'} |" for x in led["extras"]]
        out += [""]
    out += ["## 4. 未解決の問い", "", "| ID | 問い | 状態 | 答え |", "|---|---|---|---|"]
    out += [f"| {q['id']} | {q['text']} | {q.get('status', 'open')} | {q.get('answer', '')} |" for q in led["questions"]] or []
    out += ["", "## 5. 判断の記録", "", "| ID | 問い | 答え | 誰が | いつ |", "|---|---|---|---|---|"]
    out += [f"| {j['id']} | {j['question']} | {j['answer']} | {j.get('who', '')} | {j.get('when', '')} |" for j in led["judgments"]]
    return "\n".join(out) + "\n"
