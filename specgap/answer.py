"""検査器の問いへの答えを、正本の変更にする（試作5）。

人は正本（YAML）を書かない。問いに答えると、その答えが正本のどこに入るかは機械が決め、
新しい版の正本を書き出す。新しい版はもう一度検査され、残った問いや答えから生じた問い
（たとえば性質に反する答え）がまた人に返る。

答えのファイル（answers.yaml）の書き方：

    name: 返金（答えた版）         # 新しい版の名前（省略すると元のまま）
    answers:
      1: {返金額: 支払額 // 2}     # どの行にも当たらない入力 → 出力の値か式（決めないなら unspecified）
      2: 1                         # 2つの行の両方に当たる入力 → 使う行の番号
      3: 返品待ち                  # 状態と出来事 → 次の状態、または「拒否：理由」
      4: タイムアウトと同じ扱いにする  # 外部作用の失敗 → 扱い（文章）
      5: 個人情報                  # データ項目 → 区分
      6: 注文番号                  # 二重実行を防ぐ仕組み → 見分けるデータ項目
      7: 渡さない                  # 渡してよい区分を超えるデータ → 渡さない / 許可する
      8: 待つ                      # 結果を待たずに状態を進める → 待つ
      9: サポート担当が内容を確認する  # 取り消せない作用の前の確認 → 確認の内容（文章）
      10: 照会してから再開する      # 途中で止まったとき → 扱い（文章）

問いの番号は `python -m specgap questions <仕様>` で見られる。番号は同じ版の正本に対してだけ意味を持つ。
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from .checks import Report
from .expr import Env, compile_expr
from .model import UNSPECIFIED, Spec, SpecError

REJECT_WORD = "拒否"


@dataclass
class Question:
    no: int
    title: str
    question: str
    example: dict[str, str]
    slot: dict
    how: str  # 答え方
    effect: str  # 答えると正本のどこが変わるか


@dataclass
class Result:
    text: str  # 新しい版の正本（YAML）
    applied: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def questions(report: Report) -> list[Question]:
    """答えると正本を機械的に直せる問いに番号を付けて並べる（同じ場所への問いは1つにまとめる）。"""
    out: list[Question] = []
    seen = set()
    for f in report.findings:
        if not f.slot:
            continue
        key = json.dumps(_place(f.slot), ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        how, effect = describe(f.slot)
        out.append(Question(len(out) + 1, f.title, f.question, f.example, f.slot, how, effect))
    return out


def _place(slot: dict) -> dict:
    return {k: v for k, v in slot.items() if k not in ("outputs", "states", "classes", "items")}


def describe(slot: dict) -> tuple[str, str]:
    """(答え方, 答えると正本のどこが変わるか)。"""
    t = slot["type"]
    if t == "gap":
        return (f"{'・'.join(slot['outputs'])} の値か式（決めないなら unspecified）",
                f"表「{slot['table']}」に、条件「{slot['when']}」の行が加わります")
    if t == "overlap":
        a, b = slot["rows"]
        return (f"使う行の番号（{a} か {b}）",
                "選ばなかった行の条件から、選んだ行の条件を除きます")
    if t == "state":
        return (f"次の状態（{'・'.join(slot['states'])} のどれか）か「{REJECT_WORD}：理由」",
                f"状態機械「{slot['machine']}」に、{slot['state']} で「{slot['event']}」が来たときの扱いが加わります")
    if t == "failure":
        return ("扱いを文章で", f"操作「{slot['operation']}」の失敗の扱いに {slot['key']} が加わります")
    if t == "data_class":
        return (f"{'・'.join(slot['classes'])} のどれか", f"データ項目 {slot['item']} の区分が決まります")
    if t == "idempotency":
        return (f"見分けるのに使うデータ項目（{'・'.join(slot['items'])} など）",
                f"外部作用 {slot['effect']} に二重実行を防ぐキーが加わります")
    if t == "data_over":
        return ("「渡さない」か「許可する」",
                f"渡さないなら {slot['effect']} の渡すデータから {slot['item']} を除き、"
                f"許可するなら {slot['system']} に渡してよい区分に {slot['class']} を加えます")
    if t == "await":
        return ("「待つ」", f"操作「{slot['operation']}」の「{slot['update']}」の前に、{'・'.join(slot['effects'])} の結果を待つ手順が入ります")
    if t == "confirm":
        return ("確認の内容を文章で（誰が何を確かめるか）",
                f"操作「{slot['operation']}」の {slot['effect']} の前に、確認の手順が入ります")
    if t == "interrupt":
        return ("扱いを文章で", f"操作「{slot['operation']}」に、途中で止まったときの扱いが加わります")
    raise ValueError(t)


def load_answers(path: str | Path) -> tuple[str | None, dict[int, object]]:
    data = YAML(typ="safe").load(Path(path).read_text(encoding="utf-8")) or {}
    raw = data.get("answers") or {}
    return data.get("name"), {int(k): v for k, v in raw.items()}


def apply(spec_path: str | Path, spec: Spec, report: Report, answers: dict[int, object],
          name: str | None = None) -> Result:
    """答えを正本に書き込んだ新しい版を返す。元のファイルの書式とコメントは保つ。"""
    yaml = _yaml()
    doc = yaml.load(Path(spec_path).read_text(encoding="utf-8"))
    qs = {q.no: q for q in questions(report)}
    env = Env(spec)
    res = Result(text="")
    if name:
        doc["spec"] = name
    for no, ans in sorted(answers.items()):
        q = qs.get(no)
        if q is None:
            res.errors.append(f"問い {no} はありません")
            continue
        try:
            res.applied.append(f"問い {no}：{_apply_one(doc, spec, env, q.slot, ans)}")
        except SpecError as e:
            res.errors.append(f"問い {no}：{e}")
    out = io.StringIO()
    yaml.dump(doc, out)
    res.text = out.getvalue()
    return res


def _yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def _flow(d: dict) -> CommentedMap:
    m = CommentedMap(d)
    m.fa.set_flow_style()
    return m


def _find(items, id_: str, what: str):
    for x in items or []:
        if str(x.get("id")) == id_:
            return x
    raise SpecError(f"{what}「{id_}」が正本にありません")


def _apply_one(doc, spec: Spec, env: Env, slot: dict, ans) -> str:
    t = slot["type"]
    if t == "gap":
        if not isinstance(ans, dict):
            raise SpecError(f"{'・'.join(slot['outputs'])} の値を {{出力名: 値}} の形で答えてください")
        missing = [o for o in slot["outputs"] if o not in ans]
        extra = [o for o in ans if o not in slot["outputs"]]
        if missing or extra:
            raise SpecError(f"答える出力は {'・'.join(slot['outputs'])} です" +
                            (f"（足りない：{'・'.join(missing)}）" if missing else "") +
                            (f"（この表が決めない：{'・'.join(map(str, extra))}）" if extra else ""))
        then = {}
        for o in slot["outputs"]:
            v = str(ans[o])
            if v != UNSPECIFIED:
                compile_expr(v, env)  # 読めない式はここで止める
            # 会話やコマンドから来た答えは文字列のことがあるので、整数と真偽値は値に戻して正本に書く
            then[o] = int(v) if v.lstrip("-").isdigit() else {"True": True, "False": False}.get(v, v)
        table = _find(doc.get("tables"), slot["table"], "表")
        table["rows"].append(CommentedMap({"when": slot["when"], "then": _flow(then)}))
        return f"表「{slot['table']}」に行を追加（{slot['when']} → {', '.join(f'{k}={v}' for k, v in then.items())}）"
    if t == "overlap":
        a, b = slot["rows"]
        try:
            keep = int(ans)
        except (TypeError, ValueError):
            raise SpecError(f"使う行の番号（{a} か {b}）で答えてください") from None
        if keep not in (a, b):
            raise SpecError(f"使う行は {a} か {b} です")
        other = b if keep == a else a
        rows = _find(doc.get("tables"), slot["table"], "表")["rows"]
        kept, narrowed = rows[keep - 1], rows[other - 1]
        narrowed["when"] = f"({narrowed['when']}) and not ({kept['when']})"
        return f"表「{slot['table']}」の{other}行目を、{keep}行目に当たる入力を除くように狭めた"
    if t == "state":
        text = str(ans).strip()
        m = _find(doc.get("machines"), slot["machine"], "状態機械")
        if text.startswith(REJECT_WORD):
            reason = text[len(REJECT_WORD):].lstrip("：: ")
            m.setdefault("rejects", []).append(_flow({"from": slot["state"], "on": slot["event"], "reason": reason}))
            return f"状態機械「{slot['machine']}」：{slot['state']} で「{slot['event']}」は拒否（{reason}）"
        if text not in slot["states"]:
            raise SpecError(f"{text} は状態にありません（{'・'.join(slot['states'])} か「{REJECT_WORD}：理由」）")
        m.setdefault("transitions", []).append(_flow({"from": slot["state"], "on": slot["event"], "to": text}))
        return f"状態機械「{slot['machine']}」：{slot['state']} →「{slot['event']}」→ {text}"
    if t == "failure":
        text = str(ans).strip()
        if not text:
            raise SpecError("扱いを文章で答えてください")
        op = _find(doc.get("operations"), slot["operation"], "操作")
        if op.get("on_failure") is None:
            op["on_failure"] = CommentedMap()
        op["on_failure"][slot["key"]] = text
        return f"操作「{slot['operation']}」：{slot['key']} は「{text}」"
    if t == "data_class":
        text = str(ans).strip()
        if slot["classes"] and text not in slot["classes"]:
            raise SpecError(f"区分は {'・'.join(slot['classes'])} のどれかです")
        doc.setdefault("data", CommentedMap()).setdefault("items", CommentedMap())[slot["item"]] = text
        return f"データ項目 {slot['item']} の区分は {text}"
    if t == "idempotency":
        text = str(ans).strip()
        effect = doc["effects"][slot["effect"]]
        effect["idempotency"] = text
        return f"外部作用 {slot['effect']} の二重実行を防ぐキーは {text}"
    if t == "data_over":
        text = str(ans).strip()
        if text == "渡さない":
            sends = doc["effects"][slot["effect"]]["sends"]
            sends.remove(slot["item"])
            return f"{slot['effect']} で {slot['item']} を渡さない"
        if text == "許可する":
            allow = doc["data"]["allow"]
            allow.setdefault(slot["system"], []).append(slot["class"])
            return f"{slot['system']} に {slot['class']} を渡してよい"
        raise SpecError("「渡さない」か「許可する」で答えてください")
    if t in ("await", "confirm"):
        steps = _find(doc.get("operations"), slot["operation"], "操作")["steps"]
        if t == "await":
            if str(ans).strip() != "待つ":
                raise SpecError("結果を待たずに進めると漏れが残ります。「待つ」で答えるか、手順を見直してください")
            at = _step_index(steps, "update", slot["update"])
            for i, e in enumerate(slot["effects"]):
                steps.insert(at + i, _flow({"await": e}))
            return f"操作「{slot['operation']}」の「{slot['update']}」の前で {'・'.join(slot['effects'])} の結果を待つ"
        text = str(ans).strip()
        if not text:
            raise SpecError("確認の内容を文章で答えてください")
        steps.insert(_step_index(steps, slot["kind"], slot["effect"]), _flow({"confirm": text}))
        return f"操作「{slot['operation']}」の {slot['effect']} の前に確認「{text}」"
    if t == "interrupt":
        text = str(ans).strip()
        if not text:
            raise SpecError("扱いを文章で答えてください")
        _find(doc.get("operations"), slot["operation"], "操作")["on_interrupt"] = text
        return f"操作「{slot['operation']}」が途中で止まったら「{text}」"
    raise SpecError(f"この問い（{t}）にはまだ答えられません")


def _step_index(steps, kind: str, target: str) -> int:
    for i, st in enumerate(steps):
        if kind in st and str(st[kind]) == target:
            return i
    raise SpecError(f"手順 {kind}: {target} が正本にありません")
