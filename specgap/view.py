"""正本から、人が判断するためのレビュー画面（HTML）を生成する。

人は正本（YAML）を読まない。この画面に出るのは、正本から機械的に導いたもの
（図、表、具体例、検査器の問い、前の版との差分）だけで、AI の要約は含めない。
"""

from __future__ import annotations

import json
import re
from html import escape

from . import svg
from .answer import questions
from .checks import ERROR, INFO, WARNING, Report
from .diff import ADDED, CHANGED, REMOVED, SpecDiff
from .examples import Examples
from .model import UNSPECIFIED, Spec

_SEVERITY = {ERROR: ("拒否", "reject"), WARNING: ("確認", "ask")}


def prettify(expr: str) -> str:
    """条件式を読みやすい記号と言葉に置き換える。"""
    s = expr.strip()
    if s == "True":
        return "いつでも"
    if s == UNSPECIFIED:
        return "実装に任せる"
    for a, b in ((" and ", " かつ "), (" or ", " または "), ("<=", "≤"), (">=", "≥"), ("!=", "≠"),
                 ("==", "＝"), ("//", "÷")):
        s = s.replace(a, b)
    s = re.sub(r"\bnot\s+", "否定 ", s)
    s = re.sub(r"\bin\s*\[", "が次のどれか [", s)
    return s


def _kv(d: dict[str, str]) -> str:
    return "".join(f'<span class="kv"><span class="k">{escape(k)}</span><span class="v">{escape(v)}</span></span>' for k, v in d.items())


def render(spec: Spec, report: Report, *, base: Spec | None = None, change: SpecDiff | None = None,
           fragment: bool = False, sources: list[tuple[str, str]] = ()) -> str:
    x = Examples(spec)
    errors = [f for f in report.findings if f.severity == ERROR]
    warns = [f for f in report.findings if f.severity == WARNING]
    infos = [f for f in report.findings if f.severity == INFO]

    sections: list[tuple[str, str, str]] = []  # (アンカー, 見出し, 本文)

    # ---- 答えてほしいこと ----
    if errors or warns:
        cards = []
        numbered = {json.dumps(q.slot, ensure_ascii=False, sort_keys=True): q for q in questions(report)}
        for f in errors + warns:
            label, cls = _SEVERITY[f.severity]
            q = f'<p class="q">{escape(f.question)}</p>' if f.question else ""
            ex = f'<div class="kvs">{_kv(f.example)}</div>' if f.example else ""
            detail = f'<p class="detail">{escape(f.detail)}</p>' if f.detail else ""
            qn = numbered.get(json.dumps(f.slot, ensure_ascii=False, sort_keys=True)) if f.slot else None
            no = f'<span class="qno">問い {qn.no}</span>' if qn else ""
            how = (f'<dl class="how"><dt>答え方</dt><dd>{escape(qn.how)}</dd>'
                   f'<dt>答えると</dt><dd>{escape(prettify(qn.effect))}</dd></dl>') if qn else ""
            cards.append(
                f'<article class="card {cls}"><div class="chips"><span class="chip {cls}">{label}</span>{no}</div>'
                f'<p class="ctx">{escape(f.title)}</p>{q}{ex}{detail}{how}</article>'
            )
        gaps = [f for f in errors if f.check != "実装"]
        impl_errors = len(errors) - len(gaps)
        parts = []
        if gaps:
            parts.append(f"検査器が仕様の中に {len(gaps)} 件の漏れを見つけました。答えると正本が更新され、もう一度検査されます。")
        if impl_errors:
            parts.append(f"実装が仕様どおりでない、または方針の保証に届かない項目が {impl_errors} 件あります。")
        lead = "".join(parts) or "漏れはありませんが、人が判断したほうがよい点があります。"
        sections.append(("questions", "答えてほしいこと", f'<p class="lead">{lead}</p><div class="cards">{"".join(cards)}</div>'))

    # ---- 変更点 ----
    if change is not None:
        sections.append(("changes", "前の版からの変更", _changes(change)))

    # ---- ユースケース ----
    if spec.usecases or (base and base.usecases):
        sections.append(("usecases", "誰が何をするか", _usecases(spec, base)))

    # ---- 画面 ----
    for f in spec.screen_flows:
        bf = next((b for b in base.screen_flows if b.id == f.id), None) if base else None
        sections.append((f"screens-{f.id}", f"画面の流れ：{f.id}", _screens(f, bf)))

    # ---- 決まりごと ----
    if spec.tables or spec.ensures:
        sections.append(("rules", "決まりごと", _rules(spec, report, x, base)))

    # ---- 状態 ----
    for m in spec.machines:
        bm = next((b for b in base.machines if b.id == m.id), None) if base else None
        sections.append((f"states-{m.id}", f"状態の移り変わり：{m.id}", _machine(m, bm)))

    # ---- 実装 ----
    if report.guarantee is not None:
        sections.append(("impl", "実装が仕様どおりか", _guarantee(report.guarantee)))

    # ---- システム間の連携 ----
    if spec.systems:
        sections.append(("systems", "システムのつながり", _integrations(spec, report, base)))
        for op in spec.operations:
            if op.steps:
                sections.append((f"flow-{op.id}", f"処理の流れ：{op.id}", _sequence(spec, op, report)))

    # ---- 失敗 ----
    if spec.operations:
        sections.append(("failures", "外部とのやりとりが失敗したとき", _failures(spec)))

    # ---- 決めていないこと ----
    if infos:
        items = "".join(f"<li>{escape(f.title)}<span class='muted'>（{escape(prettify(f.detail.removeprefix('条件: ')))}）</span></li>" for f in infos)
        sections.append(("open", "意図的に決めていないこと", f'<p class="lead">実装が自由に選んでよい箇所です。書き忘れとは区別して記録しています。</p><ul class="plain">{items}</ul>'))

    verdict = "受け入れ可" if report.ok else "拒否"
    vcls = "ok" if report.ok else "reject"
    meta = [f'<span class="chip {vcls}">{verdict}</span>',
            f"<span>拒否 {len(errors)} 件 ・ 確認 {len(warns)} 件 ・ 記録 {len(infos)} 件</span>"]
    if base is not None:
        meta.append(f"<span>比較元：{escape(base.name)}</span>")
    nav = "".join(f'<a href="#{escape(a)}">{escape(h.split("：")[0] if "：" in h else h)}</a>' for a, h, _ in sections)
    body = "".join(
        f'<section id="{escape(a)}"><h2>{escape(h)}</h2>{content}</section>' for a, h, content in sections
    )
    src = "".join(f"<li>{escape(n)} <code>{escape(h[:12])}</code></li>" for n, h in sources)
    footer = (
        '<footer><p>この画面は正本（仕様ファイル）から自動で生成しています。図・表・具体例・問いはすべて正本と検査器から導いたもので、AI による要約は含みません。'
        "数式の ÷ は切り捨ての割り算です。</p>"
        + (f'<ul class="plain sources">{src}</ul>' if src else "") + "</footer>"
    )
    head = (
        f"<title>{escape(spec.name)} 仕様レビュー</title>\n"
        '<meta name="claude:viewport-fit-sides" content="cover">\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+JP:wght@400;500;600&family=Zen+Kaku+Gothic+New:wght@700&display=swap">\n'
        f"<style>{CSS}</style>\n"
    )
    content = (
        f'<div class="page"><header class="top"><p class="eyebrow">仕様レビュー</p><h1>{escape(spec.name)}</h1>'
        f'<div class="meta">{"".join(meta)}</div><nav>{nav}</nav></header>{body}{footer}</div>'
    )
    if fragment:
        return head + content
    return (
        '<!doctype html>\n<html lang="ja"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        f"{head}</head><body>{content}</body></html>\n"
    )


# ---- 各節 ----


def _changes(d: SpecDiff) -> str:
    out = []
    if d.behavior:
        names = list(dict.fromkeys(n for b in d.behavior for n in b.inputs))
        head = "".join(f"<th>{escape(n)}</th>" for n in names)
        rows = []
        for b in d.behavior:
            cells = "".join(f"<td>{escape(b.inputs.get(n, ''))}</td>" for n in names)
            before = "、".join(f"{k}={v}" for k, v in b.before.items())
            after = "、".join(f"{k}={v}" for k, v in b.after.items())
            rows.append(f'<tr><td class="muted">{escape(b.table)}</td>{cells}<td class="was">{escape(before)}</td><td class="now">{escape(after)}</td></tr>')
        out.append(
            "<h3>結果が変わる具体例</h3>"
            '<p class="lead">同じ入力を前の版と今の版の両方で計算し、結果が違うものだけを並べています。意図した変更かどうかを確かめてください。</p>'
            f'<div class="scroll"><table class="grid"><thead><tr><th>決まりごと</th>{head}<th>前の版</th><th>今の版</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        )
    if d.changes:
        groups: dict[str, list] = {}
        for c in d.changes:
            groups.setdefault(c.area, []).append(c)
        mark = {ADDED: ("＋", "added"), REMOVED: ("−", "removed"), CHANGED: ("±", "changed")}
        blocks = []
        for area, cs in groups.items():
            items = "".join(
                f'<li class="{mark[c.kind][1]}"><span class="sign">{mark[c.kind][0]}</span>{escape(prettify(c.text) if area == "決定表" else c.text)}</li>'
                for c in cs
            )
            blocks.append(f'<div class="cgroup"><h4>{escape(area)}</h4><ul class="clist">{items}</ul></div>')
        out.append(f'<h3>書き換わった箇所</h3><div class="cgroups">{"".join(blocks)}</div>')
    if not out:
        out.append('<p class="lead">前の版との違いはありません。</p>')
    return "".join(out)


def _usecases(spec: Spec, base: Spec | None) -> str:
    now = {(u.actor, u.id) for u in spec.usecases}
    was = {(u.actor, u.id) for u in base.usecases} if base else now
    cases = [(u.actor, u.id, svg.ADDED if (u.actor, u.id) not in was else svg.SAME) for u in spec.usecases]
    if base:
        cases += [(u.actor, u.id, svg.REMOVED) for u in base.usecases if (u.actor, u.id) not in now]
    actors = list(spec.actors) + [a for a, _, _ in cases if a not in spec.actors]
    actors = list(dict.fromkeys(actors))
    diagram = svg.usecases(actors, cases, "ユースケース図")
    rows = []
    for u in spec.usecases:
        cls = ' class="added"' if (u.actor, u.id) not in was else ""
        rows.append(
            f"<tr{cls}><td>{escape(u.actor)}</td><td>{escape(u.id)}</td><td>{escape(u.description)}</td>"
            f'<td class="muted">{escape("、".join(u.uses))}</td></tr>'
        )
    desc = "".join(f"<li><b>{escape(a)}</b>：{escape(d)}</li>" for a, d in spec.actors.items() if d)
    return (
        '<p class="lead">アクター（人）と、その人が行うユースケースです。ユースケースが参照する決まりごとや操作は、正本の中でつながっています。</p>'
        f'<div class="scroll figure">{diagram}</div>'
        + (f'<ul class="plain actors">{desc}</ul>' if desc else "")
        + f'<div class="scroll"><table class="grid"><thead><tr><th>アクター</th><th>ユースケース</th><th>説明</th><th>関係する決まり</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def _screens(f, bf) -> str:
    base_steps = {(s.src, s.action, s.dst) for s in bf.steps} if bf else None
    edges = [svg.Edge(s.src, s.action, s.dst, svg.ADDED if base_steps is not None and (s.src, s.action, s.dst) not in base_steps else svg.SAME)
             for s in f.steps]
    nodes = list(f.screens)
    kinds = {}
    if bf:
        now = {(s.src, s.action, s.dst) for s in f.steps}
        for s in bf.steps:
            if (s.src, s.action, s.dst) not in now:
                edges.append(svg.Edge(s.src, s.action, s.dst, svg.REMOVED))
                for n in (s.src, s.dst):
                    if n not in nodes:
                        nodes.append(n)
                        kinds[n] = svg.REMOVED
        for n in f.screens:
            if n not in bf.screens:
                kinds[n] = svg.ADDED
    diagram = svg.flow(nodes, edges, f.start, f.final, kinds, f"画面の流れ {f.id}")
    ucs = [s for s in f.steps if s.usecase]
    note = "".join(f"<li>「{escape(s.action)}」で、ユースケース「{escape(s.usecase)}」が始まります</li>" for s in ucs)
    return (
        '<p class="lead">画面と、画面を移る操作です。左端の矢印が最初の画面、二重枠が終わりの画面です。</p>'
        f'<div class="scroll figure">{diagram}</div>'
        + (f'<ul class="plain">{note}</ul>' if note else "")
    )


def _rules(spec: Spec, report: Report, x: Examples, base: Spec | None) -> str:
    out = ['<p class="lead">条件ごとに結果を決める表です。表の下には、各行から作った具体例を並べています。</p>']
    base_rows = {(t.id, r.when, tuple(r.then.items())) for t in base.tables for r in t.rows} if base else None
    for t in spec.tables:
        outs = t.outputs
        head = "".join(f"<th>{escape(o)}</th>" for o in outs)
        rows = []
        for r in t.rows:
            added = base_rows is not None and (t.id, r.when, tuple(r.then.items())) not in base_rows
            cls = ' class="added"' if added else ""
            cells = "".join(
                f'<td class="{"muted" if r.then.get(o) == UNSPECIFIED else ""}">{escape(prettify(r.then.get(o, "")))}</td>' for o in outs
            )
            rows.append(f'<tr{cls}><td class="num">{r.index}</td><td>{escape(prettify(r.when))}</td>{cells}</tr>')
        for f in report.findings:
            if f.check == "網羅" and f.ref == t.id:
                cond = "、".join(f"{k}＝{v}" for k, v in f.example.items())
                cells = "".join('<td class="ask">どうしますか</td>' for _ in outs)
                rows.append(f'<tr class="gap"><td class="num">？</td><td>{escape(cond)} <span class="muted">（どの行にも当たらない）</span></td>{cells}</tr>')
        overlaps = [f for f in report.findings if f.check == "排他" and f.ref == t.id]
        warn = "".join(f'<p class="note reject">{escape(f.title)}：{escape(f.question)}</p>' for f in overlaps)
        out.append(
            f"<h3>{escape(t.id)}</h3>"
            f'<div class="scroll"><table class="grid rules"><thead><tr><th class="num">行</th><th>条件</th>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>{warn}'
        )
        out.append(_table_rules(spec, report, t))
        exs = x.for_table(t)
        if exs:
            names = list(exs[0].inputs)
            eh = "".join(f"<th>{escape(n)}</th>" for n in names) + "".join(f'<th class="out">{escape(o)}</th>' for o in outs)
            er = "".join(
                "<tr>" + "".join(f"<td>{escape(e.inputs[n])}</td>" for n in names)
                + "".join(f'<td class="out">{escape(e.outputs.get(o, ""))}</td>' for o in outs)
                + f'<td class="num muted">{e.row}</td></tr>'
                for e in exs
            )
            out.append(
                f'<details open><summary>具体例 {len(exs)} 件</summary><div class="scroll"><table class="grid examples"><thead><tr>{eh}<th class="num">行</th></tr></thead><tbody>{er}</tbody></table></div></details>'
            )
    if spec.ensures:
        items = "".join(f"<li><b>{escape(e.id)}</b><span class='formula'>{escape(prettify(e.expr))}</span></li>" for e in spec.ensures)
        out.append(f"<h3>いつでも成り立つこと</h3><ul class='plain ensures'>{items}</ul>")
    return "".join(out)


def _table_rules(spec: Spec, report: Report, t) -> str:
    """表の根底にあるルールと、表を格子にしたもの（ルールと見比べて振り返るため）。"""
    from . import rules as rulebook
    from .expr import Env

    out = []
    mine = [r for r in spec.rules if t in rulebook.tables_for(spec, r)]
    if mine:
        broken = {f.title for f in report.findings if f.check == "ルール" and f.severity == "error"}
        items = []
        for r in mine:
            bad = f"表「{t.id}」がルール「{r.id}」に反しています" in broken
            mark = '<span class="reject">反している</span>' if bad else '<span class="muted">表と合っている</span>'
            items.append(f"<li><b>{escape(r.id)}</b> {mark}</li>")
        out.append(f"<h4>この表の根底にあるルール</h4><ul class='plain ensures'>{''.join(items)}</ul>")
    g = rulebook.grid(spec, Env(spec), t)
    if g is not None and (g.num or len(g.cols) > 1):
        head = f"<th>{escape(g.num or '')}</th>" + "".join(f"<th>{escape(rulebook.Grid.col_label(c))}</th>" for c in g.cols)
        body = []
        for si in range(len(g.segs)):
            cells = []
            for ci in range(len(g.cols)):
                r = g.rows[(si, ci)]
                if r is None:
                    cells.append('<td class="ask">？</td>')
                else:
                    v = "、".join(str(r.then.get(o, "")) for o in t.outputs)
                    cells.append(f"<td>{escape(prettify(v))}</td>")
            body.append(f"<tr><td>{escape(g.label(si))}</td>{''.join(cells)}</tr>")
        out.append(f'<details open><summary>格子で見る</summary><div class="scroll"><table class="grid"><thead><tr>{head}</tr></thead>'
                   f'<tbody>{"".join(body)}</tbody></table></div></details>')
    return "".join(out)


def _machine(m, bm) -> str:
    base_t = {(t.src, t.event, t.dst) for t in bm.transitions} if bm else None
    edges = [svg.Edge(t.src, t.event, t.dst, svg.ADDED if base_t is not None and (t.src, t.event, t.dst) not in base_t else svg.SAME)
             for t in m.transitions]
    kinds = {}
    if bm:
        now = {(t.src, t.event, t.dst) for t in m.transitions}
        edges += [svg.Edge(t.src, t.event, t.dst, svg.REMOVED) for t in bm.transitions if (t.src, t.event, t.dst) not in now]
        kinds = {s: svg.ADDED for s in m.states if s not in bm.states}
    diagram = svg.flow(list(m.states), edges, m.initial, m.final, kinds, f"状態の移り変わり {m.id}")

    def cell(machine, s, ev):
        ts = [t.dst for t in machine.transitions if t.src == s and t.event == ev]
        rs = [r for r in machine.rejects if r.src == s and r.event == ev]
        if len(ts) + len(rs) > 1:
            return "重複", "reject"
        if ts:
            return "→ " + ts[0], "go"
        if rs:
            return "拒否", "muted"
        return "どうしますか", "ask"

    head = "".join(f"<th>{escape(e)}</th>" for e in m.events)
    rows = []
    for s in m.states:
        tds = []
        for ev in m.events:
            text, cls = cell(m, s, ev)
            if bm and s in bm.states and ev in bm.events and cell(bm, s, ev)[0] != text and cls != "ask":
                cls += " added"
            elif bm and s not in bm.states and cls != "ask":
                cls += " added"
            tds.append(f'<td class="{cls}">{escape(text)}</td>')
        tag = "（終わり）" if s in m.final else ("（最初）" if s == m.initial else "")
        rows.append(f'<tr><th scope="row">{escape(s)}<span class="muted">{tag}</span></th>{"".join(tds)}</tr>')
    return (
        '<p class="lead">図は状態が移る道筋、表はすべての「状態 × 出来事」の扱いです。表に空欄がないことが、扱いの漏れがないことを示します。</p>'
        f'<div class="scroll figure">{diagram}</div>'
        f'<div class="scroll"><table class="grid matrix"><thead><tr><th>状態 ＼ 出来事</th>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


_LEVEL_CLASS = {"違反": "reject", "なし": "ask", "テスト済み": "tested", "証明済み": "ok"}


def _guarantee(g) -> str:
    has_before = any(it.before for it in g.items)
    rows = []
    for it in g.items:
        chip = f'<span class="chip {_LEVEL_CLASS[it.level]}">{escape(it.level)}</span>'
        if it.example and it.kind == "操作":
            basis = (f'<div class="kvs">{_kv(it.example)}</div>'
                     f'<div class="vs"><span class="muted">仕様</span> {escape(it.expected["仕様"])}</div>'
                     f'<div class="vs"><span class="bad">実装</span> {escape(it.actual["実装"])}</div>')
        elif it.example:
            basis = (f'<div class="kvs">{_kv(it.example)}</div>'
                     f'<div class="vs"><span class="muted">仕様</span> {_kv(it.expected)}</div>'
                     f'<div class="vs"><span class="bad">実装</span> {_kv(it.actual)}</div>')
        else:
            basis = escape(it.basis)
        policy = escape(str(it.required))
        if not it.meets and it.level != "違反":
            policy = f'<span class="bad">{policy}（届いていない）</span>'
        before = ""
        if has_before:
            changed = it.before and it.before != it.label
            before = f'<td class="{"ask" if changed else "muted"}">{escape(it.before or "—")}</td>'
        rows.append(
            f'<tr><td>{escape(it.kind)}「{escape(it.id)}」</td><td><code>{escape(it.function or "—")}</code></td>'
            f'<td>{chip}</td><td>{"監視あり" if it.monitored else "<span class=muted>—</span>"}</td>'
            f"<td>{basis}</td><td>{policy}</td>{before}</tr>"
        )
    head = "<th>仕様の項目</th><th>実装の関数</th><th>事前の保証</th><th>実行時</th><th>根拠</th><th>方針</th>"
    if has_before:
        head += "<th>前の版</th>"
    return (
        f'<p class="lead">実装（<code>{escape(g.module)}</code>）を仕様の項目ごとに確かめた結果です。'
        "証明は実装をソルバで調べたもの、全件確認は有限の入力をすべて動かしたもの、テストは境界値と乱数で動かしたものです。"
        "操作（外部とのやりとり）は、模擬の外部の中で正常・確認を断る・失敗・途中停止の筋書きをすべて動かしています。"
        "違反は実際に動かして確かめた具体例を出しています。監視ありの項目は、本番でも呼ばれるたびに仕様と比べます。</p>"
        f'<div class="scroll"><table class="grid"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        + _uses(g)
    )


def _uses(g) -> str:
    ops = [it for it in g.items if it.kind == "操作" and it.uses]
    if not ops:
        return ""
    rows = []
    for it in ops:
        before = it.before_uses
        for e, d in it.uses.items():
            added = before is not None and (e not in before or set(d) - set(before[e]))
            rows.append(f'<tr{" class=added" if added else ""}><td>{escape(it.id)}</td><td>{escape(e)}</td>'
                        f'<td>{escape("・".join(d) or "—")}</td></tr>')
    return (
        "<h3>操作の実装が使う外部作用</h3>"
        '<p class="lead">実装を筋書きごとに動かして、実際に使った外部作用と渡したデータを集めたものです。'
        "実装は仕様に書かれた外部作用しか使えない窓口（ctx）を通して動くので、これがそのまま実装の権限の一覧になります。前の版より増えたものは緑で示します。</p>"
        f'<div class="scroll"><table class="grid"><thead><tr><th>操作</th><th>外部作用</th><th>渡したデータ</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


_REVERSIBLE = {"yes": "できる", "no": "できない", "compensate": "埋め合わせる"}
_MODE = {"sync": "応答を待つ", "async": "送るだけ（結果は後で届く）"}


def _integrations(spec: Spec, report: Report, base: Spec | None) -> str:
    def lines(sp, sys_name):
        return [f"{n}（{_MODE.get(e.mode, e.mode)}）" for n, e in sp.effect_info.items() if e.system == sys_name]

    systems = []
    for name, sy in spec.systems.items():
        kind = svg.SAME
        if base is not None:
            if name not in base.systems:
                kind = svg.ADDED
            elif lines(base, name) != lines(spec, name):
                kind = svg.ADDED
        systems.append((name, sy.kind, lines(spec, name), kind))
    if base is not None:
        systems += [(n, b.kind, lines(base, n), svg.REMOVED) for n, b in base.systems.items() if n not in spec.systems]
    diagram = svg.context("このシステム", systems, "システム構成図")

    bad = {(f.ref, item) for f in report.findings if f.check == "データ"
           for item in spec.data_items if f"（{item}）" in f.title}
    data_rows = []
    for n, e in spec.effect_info.items():
        sends = "、".join(
            f'<span class="{"bad" if (n, it) in bad else ""}">{escape(it)}<span class="muted">（{escape(spec.data_items.get(it, "？"))}）</span></span>'
            for it in e.sends
        )
        recv = "、".join(escape(it) for it in e.receives)
        allowed = "・".join(spec.data_allow.get(e.system, [])) or "（決まっていない）"
        data_rows.append(f"<tr><td>{escape(e.system)}</td><td>{escape(n)}</td><td>{sends}</td><td>{recv}</td><td class='muted'>{escape(allowed)}</td></tr>")

    rev_rows = []
    for n, e in spec.effect_info.items():
        rev = _REVERSIBLE.get(e.reversible)
        if e.reversible == "compensate":
            rev = f"埋め合わせる（{e.compensate}）"
        rev_td = f"<td>{escape(rev)}</td>" if rev else '<td class="ask">どうしますか</td>'
        if e.reversible in ("no", "compensate"):
            idem = f"<td>{escape(e.idempotency)}</td>" if e.idempotency else '<td class="ask">どうしますか</td>'
        else:
            idem = '<td class="muted">不要</td>'
        rev_rows.append(f"<tr><td>{escape(n)}</td><td>{escape(e.system)}</td><td>{escape(_MODE.get(e.mode, e.mode))}</td>{rev_td}{idem}</tr>")
    return (
        '<p class="lead">このシステムがやりとりする外部のシステムです。外部への作用は取り消しにくく、データが外に出るので、ここが人の判断の要になります。</p>'
        f'<div class="scroll figure">{diagram}</div>'
        "<h3>外に出ていくデータ</h3>"
        '<p class="lead">赤字は、その相手に渡してよい区分を超えているデータです。</p>'
        f'<div class="scroll"><table class="grid"><thead><tr><th>相手</th><th>作用</th><th>渡すデータ（区分）</th><th>受け取るデータ</th><th>渡してよい区分</th></tr></thead><tbody>{"".join(data_rows)}</tbody></table></div>'
        "<h3>取り消せるか</h3>"
        '<p class="lead">取り消せない作用は、再試行で二重に実行されないよう、見分けるためのキーが要ります。</p>'
        f'<div class="scroll"><table class="grid"><thead><tr><th>作用</th><th>相手</th><th>待ち方</th><th>取り消し</th><th>二重実行を防ぐキー</th></tr></thead><tbody>{"".join(rev_rows)}</tbody></table></div>'
    )


def _sequence(spec: Spec, op, report: Report) -> str:
    me = "このシステム"
    actor = next((u.actor for u in spec.usecases if op.id in u.uses), None)
    parts = ([actor] if actor else []) + [me]
    for st in op.steps:
        e = spec.effect_info.get(st.target)
        if e and e.system and e.system not in parts:
            parts.append(e.system)
    flags = {}
    for f in report.findings:
        if f.ref.startswith(op.id + "#"):
            i = int(f.ref.split("#")[1])
            flags[i] = "reject" if f.severity == ERROR or flags.get(i) == "reject" else "ask"
    msgs = []
    for i, st in enumerate(op.steps, start=1):
        e = spec.effect_info.get(st.target)
        fl = flags.get(i, "")
        if st.kind == "confirm":
            msgs.append(svg.Message(actor or me, actor or me, f"確認：{st.target}", flag=fl))
        elif st.kind == "update":
            msgs.append(svg.Message(me, me, st.target, flag=fl))
        elif e is None:
            msgs.append(svg.Message(me, me, f"？ {st.target}", flag="reject"))
        elif st.kind == "call":
            items = "・".join(e.sends)
            msgs.append(svg.Message(me, e.system, f"{st.target}（{items}）", flag=fl))
            back = "・".join(e.receives) or "結果"
            msgs.append(svg.Message(e.system, me, back, "dashed"))
        elif st.kind == "send":
            msgs.append(svg.Message(me, e.system, f"{st.target}（{'・'.join(e.sends)}）を送る", flag=fl))
        elif st.kind == "await":
            msgs.append(svg.Message(e.system, me, f"{st.target} の結果{('（' + '・'.join(e.receives) + '）') if e.receives else ''}", "dashed", flag=fl))
    diagram = svg.sequence(parts, msgs, f"処理の流れ {op.id}")
    interrupt = (f'<p class="lead">途中で止まったとき：{escape(op.on_interrupt)}</p>' if op.on_interrupt
                 else '<p class="note reject">途中で止まったときの扱いが決まっていません。</p>')
    return (
        '<p class="lead">上から順に処理が進みます。実線の矢印は依頼、破線は応答や後から届く結果です。赤や黄色の箇所は検査器が問いを出している手順です。</p>'
        f'<div class="scroll figure">{diagram}</div>{interrupt}'
    )


def _failures(spec: Spec) -> str:
    rows = []
    for op in spec.operations:
        for eff in op.uses:
            for fail in spec.effects.get(eff, []):
                h = op.on_failure.get(f"{eff}.{fail}")
                td = f"<td>{escape(h)}</td>" if h else '<td class="ask">どうしますか</td>'
                rows.append(f"<tr><td>{escape(op.id)}</td><td>{escape(eff)}</td><td>{escape(fail)}</td>{td}</tr>")
    return (
        '<p class="lead">外部のサービスを使う操作ごとに、起こり得る失敗とその扱いを並べています。失敗の種類は正本の外部作用の定義から導いています。</p>'
        f'<div class="scroll"><table class="grid"><thead><tr><th>操作</th><th>外部</th><th>失敗</th><th>扱い</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


CSS = """
/* レイアウト：一段組みの読み物。上から「問い → 変更 → 全体像（図）→ 詳細（表）」の順に降りていく */
:root {
  --bg: #f4f6f6; --surface: #ffffff; --ink: #18252a; --muted: #5a6b71; --line: #d3dcde;
  --accent: #0d6870; --accent-soft: #dff0f1;
  --add: #1d7a3c; --add-soft: #e2f3e6; --remove: #b42a20; --remove-soft: #fbe6e3; --ask: #8a5800; --ask-soft: #fbefd5;
  --font-display: "Zen Kaku Gothic New", "Hiragino Sans", "Noto Sans JP", sans-serif;
  --font-body: "IBM Plex Sans JP", "Hiragino Sans", "Noto Sans JP", "Yu Gothic", sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #101618; --surface: #172024; --ink: #e2eaec; --muted: #98a9ae; --line: #2b393d;
  --accent: #5cc0c8; --accent-soft: #15353a;
  --add: #6fcf8e; --add-soft: #163322; --remove: #ff8b80; --remove-soft: #3c1c1a; --ask: #efbe5c; --ask-soft: #382a10;
  color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #101618; --surface: #172024; --ink: #e2eaec; --muted: #98a9ae; --line: #2b393d;
  --accent: #5cc0c8; --accent-soft: #15353a;
  --add: #6fcf8e; --add-soft: #163322; --remove: #ff8b80; --remove-soft: #3c1c1a; --ask: #efbe5c; --ask-soft: #382a10;
  color-scheme: dark; }
body { background: var(--bg); color: var(--ink); font-family: var(--font-body); font-size: 15px; line-height: 1.7; margin: 0; }
.page { max-width: 1080px; margin: 0 auto; padding-block: 32px 64px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: flex; flex-direction: column; gap: 40px; }
h1, h2, h3 { font-family: var(--font-display); text-wrap: balance; line-height: 1.35; margin: 0; }
h1 { font-size: 2rem; }
h2 { font-size: 1.35rem; padding-bottom: 8px; border-bottom: 2px solid var(--ink); }
h3 { font-size: 1.05rem; margin-top: 8px; }
h4 { font-size: .85rem; margin: 0 0 6px; color: var(--muted); letter-spacing: .06em; }
section { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.top { display: flex; flex-direction: column; gap: 10px; }
.eyebrow { margin: 0; font-size: .78rem; letter-spacing: .14em; color: var(--accent); font-weight: 600; }
.meta { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; color: var(--muted); font-variant-numeric: tabular-nums; }
nav { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
nav a { font-size: .85rem; color: var(--accent); text-decoration: none; padding: 3px 10px; border: 1px solid var(--line); border-radius: 999px; background: var(--surface); }
nav a:hover, nav a:focus-visible { border-color: var(--accent); outline: none; }
.lead { margin: 0; color: var(--muted); max-width: 46em; }
.muted { color: var(--muted); }
.chip { display: inline-block; font-size: .75rem; font-weight: 600; letter-spacing: .06em; padding: 1px 10px; border-radius: 999px; }
.chip.ok { background: var(--add-soft); color: var(--add); }
.chip.reject { background: var(--remove-soft); color: var(--remove); }
.chip.ask { background: var(--ask-soft); color: var(--ask); }
.chip.tested { background: var(--accent-soft); color: var(--accent); }
.vs { font-size: .82rem; margin-top: 4px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; }
.card { background: var(--surface); border: 1px solid var(--line); border-left: 4px solid var(--line); border-radius: 6px; padding: 14px 16px;
  display: flex; flex-direction: column; gap: 8px; align-items: flex-start; min-width: 0; }
.card.reject { border-left-color: var(--remove); }
.card.ask { border-left-color: var(--ask); }
.card .ctx { margin: 0; font-size: .82rem; color: var(--muted); }
.card .q { margin: 0; font-size: 1.05rem; font-weight: 600; }
.card .detail { margin: 0; font-size: .85rem; color: var(--muted); }
.chips { display: flex; gap: 8px; align-items: center; }
.qno { font-size: .75rem; color: var(--muted); font-variant-numeric: tabular-nums; }
.how { margin: 4px 0 0; display: grid; grid-template-columns: auto 1fr; gap: 2px 10px; font-size: .8rem; border-top: 1px dashed var(--line); padding-top: 8px; width: 100%; }
.how dt { color: var(--muted); white-space: nowrap; }
.how dd { margin: 0; }
.kvs { display: flex; flex-wrap: wrap; gap: 6px; }
.kv { display: inline-flex; font-size: .8rem; border: 1px solid var(--line); border-radius: 4px; overflow: hidden; }
.kv .k { padding: 1px 6px; background: var(--bg); color: var(--muted); }
.kv .v { padding: 1px 8px; font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
.scroll { overflow-x: auto; max-width: 100%; }
.figure { background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: 8px; }
table.grid { border-collapse: collapse; width: 100%; background: var(--surface); font-size: .88rem; font-variant-numeric: tabular-nums; }
table.grid th, table.grid td { border: 1px solid var(--line); padding: 6px 10px; text-align: left; vertical-align: top; }
table.grid thead th { background: var(--bg); font-weight: 600; font-size: .8rem; color: var(--muted); white-space: nowrap; }
table.grid td.num, table.grid th.num { width: 3em; text-align: center; color: var(--muted); }
table.grid tr.added td, table.grid td.added { background: var(--add-soft); }
table.grid tr.gap td { background: var(--ask-soft); }
table.grid td.ask { background: var(--ask-soft); color: var(--ask); font-weight: 600; }
table.grid td.reject { background: var(--remove-soft); color: var(--remove); font-weight: 600; }
table.grid td.go { color: var(--accent); }
table.grid td.out, table.grid th.out { border-left: 2px solid var(--ink); }
table.grid td.was { color: var(--remove); }
table.grid td.now { color: var(--add); font-weight: 600; }
table.matrix th[scope=row] { white-space: nowrap; background: var(--bg); }
details summary { cursor: pointer; color: var(--muted); font-size: .85rem; margin: 2px 0 6px; }
.note { margin: 0; font-size: .85rem; padding: 6px 10px; border-radius: 4px; }
.note.reject { background: var(--remove-soft); color: var(--remove); }
ul.plain { margin: 0; padding-left: 1.2em; }
ul.plain li { margin: 2px 0; }
.ensures .formula { font-family: var(--font-mono); margin-left: 12px; }
.cgroups { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
.cgroup { min-width: 0; }
.clist { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; font-size: .88rem; }
.clist li { display: flex; gap: 8px; padding: 4px 8px; border-radius: 4px; overflow-wrap: anywhere; }
.clist li.added { background: var(--add-soft); }
.clist li.removed { background: var(--remove-soft); text-decoration: line-through; text-decoration-color: var(--remove); }
.clist li.changed { background: var(--ask-soft); }
.clist .sign { font-family: var(--font-mono); font-weight: 600; width: 1em; flex: none; }
.clist li.added .sign { color: var(--add); }
.clist li.removed .sign { color: var(--remove); }
footer { border-top: 1px solid var(--line); padding-top: 16px; font-size: .8rem; color: var(--muted); }
footer p { margin: 0 0 6px; max-width: 60em; }
code { font-family: var(--font-mono); font-size: .85em; }
svg.diagram { display: block; font-family: var(--font-body); font-size: 13px; }
svg.diagram text { fill: var(--ink); }
svg.diagram .node rect { fill: var(--surface); stroke: var(--muted); stroke-width: 1.25; }
svg.diagram .node rect.inner { fill: none; stroke-width: 1; }
svg.diagram .node.start rect { stroke: var(--accent); stroke-width: 2; }
svg.diagram .node.added rect { fill: var(--add-soft); stroke: var(--add); }
svg.diagram .node.removed rect { fill: var(--remove-soft); stroke: var(--remove); stroke-dasharray: 4 3; }
svg.diagram .edge { fill: none; stroke: var(--muted); stroke-width: 1.25; }
svg.diagram .edge.added { stroke: var(--add); stroke-width: 2; }
svg.diagram .edge.removed { stroke: var(--remove); stroke-dasharray: 5 4; }
svg.diagram .arrowhead { fill: var(--muted); }
svg.diagram .arrowhead.added { fill: var(--add); }
svg.diagram .arrowhead.removed { fill: var(--remove); }
svg.diagram .elabel rect { fill: var(--surface); }
svg.diagram .elabel text { font-size: 11.5px; fill: var(--muted); }
svg.diagram .elabel.added text { fill: var(--add); font-weight: 600; }
svg.diagram .elabel.removed text { fill: var(--remove); text-decoration: line-through; }
svg.diagram .usecase ellipse { fill: var(--accent-soft); stroke: var(--accent); stroke-width: 1.25; }
svg.diagram .usecase.added ellipse { fill: var(--add-soft); stroke: var(--add); stroke-width: 2; }
svg.diagram .usecase.removed ellipse { fill: var(--remove-soft); stroke: var(--remove); stroke-dasharray: 4 3; }
svg.diagram .actor circle, svg.diagram .actor path { fill: none; stroke: var(--ink); stroke-width: 1.5; }
svg.diagram .actor text { font-weight: 600; }
svg.diagram text.sub { font-size: 11px; fill: var(--muted); }
svg.diagram .lifeline { fill: none; stroke: var(--line); stroke-width: 1.25; stroke-dasharray: 3 4; }
svg.diagram .msg { fill: none; stroke: var(--muted); stroke-width: 1.25; }
svg.diagram .msg.reject { stroke: var(--remove); stroke-width: 2; }
svg.diagram .msg.ask { stroke: var(--ask); stroke-width: 2; }
svg.diagram .mlabel text { font-size: 11.5px; }
svg.diagram .mlabel.reject text { fill: var(--remove); font-weight: 600; }
svg.diagram .mlabel.ask text { fill: var(--ask); font-weight: 600; }
svg.diagram .note rect { fill: var(--accent-soft); stroke: var(--accent); stroke-width: 1; }
svg.diagram .note text { font-size: 11.5px; }
svg.diagram .note.reject rect { fill: var(--remove-soft); stroke: var(--remove); stroke-width: 2; }
svg.diagram .note.ask rect { fill: var(--ask-soft); stroke: var(--ask); stroke-width: 2; }
.bad { color: var(--remove); font-weight: 600; }
@media (max-width: 480px) { h1 { font-size: 1.55rem; } .cards { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; } }
"""
