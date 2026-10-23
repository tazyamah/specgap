"""選択肢に収まらない答えを、正本の変更として受ける（試作7）。

「不正な注文を作れるようにする」のような答えは、問いの選択肢では表せない。AI は人と変更の中身を
確かめてから、変更案（操作の並び）を change に渡す。機械はそれを作業中の版に当て、読めるか・
検査でどう変わったかを返し、変更を人の言葉と一緒に判断として残す。

変更案は、次の形の操作の並び（YAML か JSON）：

    - {op: add, path: machines/注文/transitions, value: {from: 発送済み, on: 支払, to: 発送済み}}
    - {op: add, path: operations, value: {id: 不正な支払を記録する, steps: [...]}}
    - {op: replace, path: effects/不正な注文の通知/system, value: 社内通知}
    - {op: remove, path: data/allow/社内通知}

path は「/」で区切る。表や操作のように id を持つものの並びは id で、ほかの並びは番号（0 から）で選ぶ。
add の先が並びなら末尾に足し、対応表なら新しいキーを足す（すでにあれば誤り）。
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from .answer import _yaml, questions
from .checks import ERROR, check
from .diff import diff
from .model import SpecError, load

OPS = ("add", "replace", "remove")


@dataclass
class ChangeResult:
    ok: bool
    text: str  # AI に返す文章
    decision: str = ""
    changes: list[str] = field(default_factory=list)


def _walk(node, seg: str, path: str):
    if isinstance(node, list):
        for x in node:
            if isinstance(x, dict) and str(x.get("id")) == seg:
                return x
        if seg.isdigit() and int(seg) < len(node):
            return node[int(seg)]
        raise SpecError(f"{path} の「{seg}」が見つかりません")
    if isinstance(node, dict):
        if seg not in node:
            raise SpecError(f"{path} の「{seg}」が見つかりません")
        return node[seg]
    raise SpecError(f"{path} の「{seg}」の手前は、並びでも対応表でもありません")


def _styled(v):
    """小さな対応表や並びは、正本の書き方に合わせて1行（flow）で書く。"""
    if isinstance(v, dict):
        m = CommentedMap((k, _styled(x)) for k, x in v.items())
        if all(not isinstance(x, (dict, list)) for x in v.values()) or len(v) == 1:
            m.fa.set_flow_style()
        return m
    if isinstance(v, list):
        s = CommentedSeq(_styled(x) for x in v)
        if all(not isinstance(x, (dict, list)) for x in v):
            s.fa.set_flow_style()
        return s
    return v


def _apply_op(doc, op: dict) -> None:
    kind, path = op.get("op"), str(op.get("path", "")).strip("/")
    if kind not in OPS:
        raise SpecError(f"op は {' / '.join(OPS)} のどれかです（{kind}）")
    segs = [s for s in path.split("/") if s]
    if not segs:
        raise SpecError("path が空です")
    parent = doc
    for seg in segs[:-1]:
        parent = _walk(parent, seg, path)
    last = segs[-1]
    if kind == "add":
        if "value" not in op:
            raise SpecError(f"add には value が要ります（{path}）")
        if isinstance(parent, dict) and last not in parent:
            parent[last] = _styled(op["value"])
            return
        target = _walk(parent, last, path)
        if isinstance(target, list):
            target.append(_styled(op["value"]))
        elif isinstance(target, dict) and isinstance(op["value"], dict):
            for k, v in op["value"].items():
                if k in target:
                    raise SpecError(f"{path} にはすでに「{k}」があります（replace を使ってください）")
                target[k] = _styled(v)
        else:
            raise SpecError(f"{path} にはすでに値があります（replace を使ってください）")
        return
    _walk(parent, last, path)  # 無ければ誤り
    if kind == "replace":
        if "value" not in op:
            raise SpecError(f"replace には value が要ります（{path}）")
        if isinstance(parent, list):
            parent[parent.index(_walk(parent, last, path))] = _styled(op["value"])
        else:
            parent[last] = _styled(op["value"])
    else:
        if isinstance(parent, list):
            parent.remove(_walk(parent, last, path))
        else:
            del parent[last]


def refs(op: dict) -> list[str]:
    """変更が正本のどこに効いたか（判断の applies_to）。分かる形は意味の参照に、ほかは正本の道筋にする。"""
    segs = [s for s in str(op.get("path", "")).strip("/").split("/") if s]
    v = op.get("value")
    if op.get("op") == "remove":
        return [f"正本:{'/'.join(segs)}（削除）"]
    if segs[:1] == ["machines"] and len(segs) == 3 and segs[2] in ("transitions", "rejects") and isinstance(v, dict):
        events = v.get("on") if isinstance(v.get("on"), list) else [v.get("on")]
        srcs = v.get("from") if isinstance(v.get("from"), list) else [v.get("from")]
        return [f"状態機械:{segs[1]}:{s}:{e}" for s in srcs for e in events]
    if segs == ["operations"] and isinstance(v, dict):
        return [f"操作:{v.get('id')}"]
    if segs[:1] == ["operations"] and len(segs) == 3 and segs[2] == "steps" and isinstance(v, dict) and len(v) == 1:
        (k, t), = v.items()
        return [f"操作:{segs[1]}:手順:{k}:{t}"]
    if segs[:1] == ["operations"] and len(segs) >= 3 and segs[2] == "on_failure":
        keys = [segs[3]] if len(segs) > 3 else list(v or {})
        return [f"操作:{segs[1]}:失敗:{k}" for k in keys]
    if segs == ["effects"] and isinstance(v, dict):
        return [f"外部作用:{k}" for k in v]
    if segs[:1] == ["effects"] and len(segs) >= 2:
        return [f"外部作用:{segs[1]}"]
    if segs == ["rules"] and isinstance(v, dict):
        return [f"ルール:{v.get('id')}"]
    if segs[:1] == ["tables"] and len(segs) == 3 and segs[2] == "rows" and isinstance(v, dict):
        return [f"表:{segs[1]}:{v.get('when')}"]
    if segs[:2] == ["data", "items"]:
        return [f"データ:{k}" for k in ([segs[2]] if len(segs) > 2 else list(v or {}))]
    if segs[:2] == ["data", "allow"]:
        return [f"許可:{k}" for k in ([segs[2]] if len(segs) > 2 else list(v or {}))]
    return [f"正本:{'/'.join(segs)}"]


def change(session, ops: list[dict], title: str, said: str = "", question: str = "",
           assumptions: list[str] | None = None) -> ChangeResult:
    """変更案を作業中の版に当て、検査し直して、変わったことを返す。question は答えている問いの識別子（任意）。"""
    from .ask import next_packet, question_id, to_text

    if not title.strip():
        return ChangeResult(False, "title（何を決めたかを一文で）が要ります")
    if not isinstance(ops, list) or not ops:
        return ChangeResult(False, "変更案（操作の並び）が空です")
    src = session.current
    old = load(src)
    before_report = check(old)
    asked = None
    if question:
        asked = next((q for q in questions(before_report) if question_id(q) == question), None)
        if asked is None:
            return ChangeResult(False, f"問い {question} は今の版にありません")
    y = _yaml()
    doc = y.load(src.read_text(encoding="utf-8"))
    try:
        for op in ops:
            _apply_op(doc, op)
    except SpecError as e:
        return ChangeResult(False, f"変更を当てられません：{e}\n正本は変えていません。")

    from .answer import _decide_record

    did = _decide_record(doc, title=title, question=asked.question if asked else "（問いによらない変更）",
                         answer=title, said=said, applies_to=[r for op in ops for r in refs(op)],
                         assumptions=assumptions or [], at=date.today().isoformat())
    out = io.StringIO()
    y.dump(doc, out)
    before = src.read_bytes()
    session.work.write_text(out.getvalue(), encoding="utf-8")
    try:
        new = load(session.work)
    except SpecError as e:
        if src == session.work:
            session.work.write_bytes(before)
        else:
            session.work.unlink()
        return ChangeResult(False, f"変更後の正本を読めません：{e}\n正本は変えていません。")
    d = diff(old, new)
    changes = [f"{c.kind}（{c.area}）：{c.text}" for c in d.changes]
    old_titles = {f.title for f in before_report.findings}
    after = check(new)
    born = [f for f in after.findings if f.severity == ERROR and f.title not in old_titles]
    _log(session, title, ops, said, question, did, src.name)
    p, _ = next_packet(session)
    lines = [f"反映しました：{title}（判断 {did}）"]
    lines += ["変わったこと："] + [f"  ・{c}" for c in changes] if changes else []
    if asked is not None and any(question_id(q) == question for q in questions(after)):
        lines.append(f"問い {question} はまだ残っています。変更で答えになっていないか、人に確かめてください。")
    if born:
        lines.append("変更で新しく出た拒否：" + "".join(f"\n  ・{f.title}" for f in born))
    lines.append(f"今の版（{session.work.name}）：{'受け入れ可' if after.ok else '拒否'}")
    return ChangeResult(True, "\n".join(lines) + "\n\n" + to_text(p, after), did, changes)


def _log(session, title, ops, said, question, did, src):
    from datetime import datetime, timezone

    row = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "id": question or "-",
           "question": "（正本の変更）", "answer": title, "said": said, "from": src, "decision": did, "ops": ops}
    with session.log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
