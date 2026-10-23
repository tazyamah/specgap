"""AI から問いを1つずつ聞くための MCP サーバー（標準入出力）。

道具は2つだけにする（AI の文脈を小さく保つ）。
  next_question(spec, work)                    次の1問の包み
  answer_question(spec, id, answer, said, work) 答えを1つ反映し、検査し直して次の1問
"""

from __future__ import annotations

from . import ask


def build():
    try:
        from mcp.server.mcpserver import MCPServer as Server  # mcp 2.x
    except ImportError:
        from mcp.server.fastmcp import FastMCP as Server  # mcp 1.x

    server = Server("specgap", instructions=(
        "仕様の問いを人に1つずつ聞くための道具です。next_question で1問を受け取り、会話でその1問だけを聞き、"
        "人が答えたら answer_question に渡してください。正本（YAML）を直接書き換えないでください。"))

    @server.tool()
    def next_question(spec: str, work: str = "") -> str:
        """次の1問。spec は元の仕様ファイル、work は作業中の版（省略時は <仕様>.work.yaml）。"""
        p, report = ask.next_packet(ask.session(spec, work or None))
        return ask.to_text(p, report)

    @server.tool()
    def answer_question(spec: str, id: str, answer: str, said: str, work: str = "") -> str:
        """人の答えを1つ反映する。id は問いの識別子、answer は値・式・選択肢（{出力名: 値} も可）、said は人の言葉そのまま。"""
        text, _ = ask.reply(ask.session(spec, work or None), id, ask.parse_answer(answer), said)
        return text

    return server


def serve() -> None:
    build().run()
