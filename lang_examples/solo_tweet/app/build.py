"""画面を1つの HTML にまとめる（実行部・Dropbox窓口・WASM を中に埋め込む）。
使い方: python build.py   → dist/solo_tweet.html
WASM は ../rust を cargo でビルドして作る（rustup target add wasm32-unknown-unknown が必要）。"""
import base64
import subprocess
import sys
from pathlib import Path

here = Path(__file__).parent
rust = here.parent / "rust"
wasm = rust / "target" / "wasm32-unknown-unknown" / "release" / "specgap_app.wasm"

r = subprocess.run(["cargo", "build", "--release", "--lib", "--target", "wasm32-unknown-unknown", "--offline"], cwd=rust)
if r.returncode != 0 or not wasm.exists():
    sys.exit("WASM をビルドできませんでした")

html = (here / "index.html").read_text()
for name in ("runtime.js", "dropbox.js"):
    tag = f'<script src="{name}"></script>'
    assert tag in html, tag
    html = html.replace(tag, "<script>\n" + (here / name).read_text() + "\n</script>")
b64 = base64.b64encode(wasm.read_bytes()).decode()
html = html.replace("<script>\n(async function", f'<script>window.SPECGAP_WASM_B64="{b64}";</script>\n<script>\n(async function', 1)
(here / "dist").mkdir(exist_ok=True)
(here / "dist" / "solo_tweet.html").write_text(html)
print(f"できました: {here / 'dist' / 'solo_tweet.html'}（{len(html) // 1024} KB）")
