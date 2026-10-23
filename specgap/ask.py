"""問いを1つずつ会話で聞く（試作5の続き）。

人は問いの一覧に向き合わない。AI は会話で1問だけ聞き、人の答えを1つ反映するたびに
正本を更新して検査し直し、次の1問を出す。1問ぶんの包み（問い・具体例・選択肢・答えると
どこが変わるか・関係する部分の抜き出し）は機械が決まった形で作り、AI は聞き方を整えるだけにする。

    python -m specgap ask   examples/shop_v1.yaml -o work.yaml            # 次の1問
    python -m specgap reply examples/shop_v1.yaml -o work.yaml Q1a2b3c "返品待ち" --said "返品待ちに戻して"

`-o` の作業中の版（省略時は `<仕様>.work.yaml`）がまだ無ければ元の仕様から始める。元の仕様は書き換えない。
作業中の版は元の仕様と同じフォルダに置く（実装ファイルなどの相対パスがそのまま通るように）。
答えは作業中の版の隣の `<作業中の版>.answers.jsonl` に追記だけで残す（人が言った言葉もそのまま）。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ruamel.yaml import YAML

from .answer import REJECT_WORD, Question, _place, apply, questions
from .checks import ERROR, Report, check
from .model import UNSPECIFIED, Spec, SpecError, load

INSTRUCTION = ("この問いを1つだけ、人に会話で聞いてください。具体例と選択肢はそのまま見せ、"
               "答えを推測で埋めないでください。人が答えたら、その答えを reply に渡し、said には人の言葉をそのまま入れてください。"
               "答えがはっきりしないときは、聞き直してください。")


@dataclass
class Packet:
    """1問ぶんの包み。"""
    id: str  # 問いの場所から決まる識別子（版が変わっても同じ場所への問いなら同じ）
    remaining: int  # この問いを含めて残っている問いの数
    title: str
    question: str
    example: dict[str, str]
    choices: list[str]
    how: str
    effect: str
    context: list[str] = field(default_factory=list)  # 正本の関係する部分（人が読める形）
    instruction: str = INSTRUCTION


@dataclass
class Session:
    spec: Path  # 元の仕様
    work: Path  # 作業中の版

    @property
    def log(self) -> Path:
        return self.work.with_name(self.work.name + ".answers.jsonl")

    @property
    def current(self) -> Path:
        return self.work if self.work.exists() else self.spec


def session(spec: str | Path, work: str | Path | None = None) -> Session:
    spec = Path(spec)
    return Session(spec, Path(work) if work else spec.with_name(spec.stem + ".work.yaml"))


def question_id(q: Question) -> str:
    key = json.dumps(_place(q.slot), ensure_ascii=False, sort_keys=True)
    return "Q" + hashlib.sha256(key.encode()).hexdigest()[:6]


def next_packet(session: Session) -> tuple[Packet | None, Report]:
    spec = load(session.current)
    report = check(spec)
    qs = questions(report)
    return (packet(spec, qs[0], len(qs)) if qs else None), report


def packet(spec: Spec, q: Question, remaining: int) -> Packet:
    return Packet(question_id(q), remaining, q.title, q.question, q.example,
                  choices(spec, q.slot), q.how, q.effect, context(spec, q.slot))


def choices(spec: Spec, slot: dict) -> list[str]:
    t = slot["type"]
    if t == "gap":
        if len(slot["outputs"]) == 1:
            var = spec.outputs.get(slot["outputs"][0])
            if var is not None and var.type in spec.enums:
                return spec.enums[var.type] + [UNSPECIFIED]
            if var is not None and var.type == "bool":
                return ["True", "False", UNSPECIFIED]
            # 数の出力は、同じ表のほかの行で使っている値を候補にする（ほかの値や式も答えられる）
            table = next(x for x in spec.tables if x.id == slot["table"])
            seen = [str(r.then[slot["outputs"][0]]) for r in table.rows if slot["outputs"][0] in r.then]
            return list(dict.fromkeys(v for v in seen if v != UNSPECIFIED)) + [UNSPECIFIED]
        return []
    if t == "overlap":
        return [str(r) for r in slot["rows"]]
    if t == "state":
        return list(slot["states"]) + [f"{REJECT_WORD}：理由"]
    if t == "data_class":
        return list(slot["classes"])
    if t == "idempotency":
        return list(slot["items"])
    if t == "data_over":
        return ["渡さない", "許可する"]
    if t == "await":
        return ["待つ"]
    return []


def context(spec: Spec, slot: dict) -> list[str]:
    t = slot["type"]
    if t in ("gap", "overlap"):
        table = next(x for x in spec.tables if x.id == slot["table"])
        lines = [f"表「{table.id}」（今ある行）"]
        for r in table.rows:
            then = "、".join(f"{k}={'実装に任せる' if v == UNSPECIFIED else v}" for k, v in r.then.items())
            lines.append(f"  {r.index}. {r.when} → {then}")
        if t == "gap":
            lines.append(f"答えると加わる行の条件：{slot['when']}")
        return lines
    if t == "state":
        m = next(x for x in spec.machines if x.id == slot["machine"])
        lines = [f"状態機械「{m.id}」の {slot['state']} からの扱い（今あるもの）"]
        lines += [f"  「{x.event}」→ {x.dst}" for x in m.transitions if x.src == slot["state"]]
        lines += [f"  「{x.event}」→ 拒否（{x.reason}）" for x in m.rejects if x.src == slot["state"]]
        if len(lines) == 1:
            lines.append("  （まだありません）")
        return lines
    if t in ("failure", "interrupt", "await", "confirm"):
        op = next(x for x in spec.operations if x.id == slot["operation"])
        lines = [f"操作「{op.id}」の手順"]
        lines += [f"  {i}. {s.kind}: {s.target}" for i, s in enumerate(op.steps, start=1)]
        if t == "failure":
            done = [f"  {k}：{v}" for k, v in op.on_failure.items()]
            lines += ["決まっている失敗の扱い"] + (done or ["  （まだありません）"])
        return lines
    if t in ("data_class", "idempotency", "data_over"):
        lines = []
        for name, e in spec.effect_info.items():
            if (t == "data_class" and slot["item"] in e.sends + e.receives) or name == slot.get("effect"):
                lines.append(f"外部作用 {name}（{e.system}）：渡す {'・'.join(e.sends) or 'なし'}、"
                             f"受け取る {'・'.join(e.receives) or 'なし'}")
        if t == "data_over":
            lines.append(f"{slot['system']} に渡してよい区分：{'・'.join(spec.data_allow.get(slot['system'], [])) or 'なし'}")
        return lines
    return []


def to_text(p: Packet | None, report: Report | None = None) -> str:
    """AI が読む形。最初の行は AI への指示。"""
    if p is None:
        state = "受け入れ可" if report is None or report.ok else "拒否"
        errors = 0 if report is None else sum(f.severity == ERROR for f in report.findings)
        tail = "" if errors == 0 else f"（問いの形にできない拒否が {errors} 件あります。check で見てください）"
        return f"答えると正本を直せる問いは残っていません。今の版は{state}です{tail}。"
    out = [f"[AI への指示] {p.instruction}", "",
           f"問い {p.id}（残り {p.remaining} 問）：{p.title}", f"聞くこと：{p.question}"]
    shown = "、".join(f"{k}={v}" for k, v in p.example.items())
    if p.example and shown not in p.question:
        out.append("具体例：" + "、".join(f"{k}={v}" for k, v in p.example.items()))
    if p.choices:
        out.append("選択肢（番号で聞き、答えは選択肢の文字列で渡す）：" + " ／ ".join(f"{i}. {c}" for i, c in enumerate(p.choices, 1)))
    out += [f"答え方：{p.how}", f"答えると：{p.effect}"]
    if p.context:
        out += ["", "関係する部分："] + p.context
    return "\n".join(out)


def parse_answer(text: str):
    """コマンドや会話から来た答えの文字列を、answer.apply が受け取る形にする。"""
    try:
        v = YAML(typ="safe").load(text)
    except Exception:
        return text
    return text if v is None else v


def reply(session: Session, qid: str, ans, said: str = "") -> tuple[str, bool]:
    """答えを1つ反映し、作業中の版を書き、検査し直して次の1問を返す。(AI に返す文章, 反映できたか)。"""
    spec = load(session.current)
    report = check(spec)
    qs = questions(report)
    q = next((x for x in qs if question_id(x) == qid), None)
    if q is None:
        p, _ = next_packet(session)
        return (f"問い {qid} は今の版にありません（もう答えたか、前の答えで変わりました）。\n\n" + to_text(p, report)), False
    if q.slot["type"] == "gap" and not isinstance(ans, dict) and len(q.slot["outputs"]) == 1:
        ans = {q.slot["outputs"][0]: ans}
    res = apply(session.current, spec, report, {q.no: ans})
    if res.errors:
        msg = "\n".join(f"反映できません：{e.split('：', 1)[-1]}" for e in res.errors)
        return f"{msg}\n人に聞き直してください。\n\n{to_text(packet(spec, q, len(qs)))}", False
    src = session.current
    before = src.read_bytes()
    session.work.write_text(res.text, encoding="utf-8")
    try:
        load(session.work)
    except SpecError as e:  # 書き出した版が読めなければ元に戻す
        if src == session.work:
            session.work.write_bytes(before)
        else:
            session.work.unlink()
        return f"新しい版を読めません：{e}", False
    _record(session, q, ans, said, src.name, hashlib.sha256(before).hexdigest()[:12], res.applied)
    p, after = next_packet(session)
    applied = res.applied[0].split("：", 1)[-1]
    head = (f"反映しました：{applied}\n"
            f"今の版（{session.work.name}）：{'受け入れ可' if after.ok else '拒否'}、残りの問い {p.remaining if p else 0} 問")
    return head + "\n\n" + to_text(p, after), True


def _record(session: Session, q: Question, ans, said: str, src: str, before: str, applied: list[str]) -> None:
    row = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "id": question_id(q),
           "question": q.question, "answer": ans, "said": said, "from": src,
           "before": before, "applied": applied}
    with session.log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
