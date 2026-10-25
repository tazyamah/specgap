# 引き継ぎメモ（最小の試作：独自構文 → Rust 生成と plan 突合）

更新: 2026-10-25。ブランチ `claude/project-thread-pyf38o`（tazyamah/specgap）。置き場所は specgap リポジトリ内（tazyamah が選択）。
返答・コメントはすべて日本語。PR はためず、小さく出して早めにマージしてもらう。

## ゴール
独自構文の「構文解析 → 検査器 → Rust 生成 → plan の仕様書（①）との突合」を最小で通す。範囲はお店の例の受注と決済要求。
設計の根拠は /mnt/project-files/notes/ の language-syntax-sketch.md、language-generated-spec-sketch.md、language-plan-document-template.md、language-rust-transpile.md。

## できていること（specgap_lang/）
- lexer.py / parser.py / ast.py: 構文解析。例は lang_examples/shop.sgl
- check.py: 検査器（型推論、宣言と本体の読み書き・遷移・外部のずれ、行き先の漏れ、丸め漏れ、冪等キー漏れ、不変条件の簡易証明）
- spec.py: コードから仕様書（③）を生成
- rustgen.py: Rust 生成。shop.sgl から生成した crate が cargo build を通ることを確認済み
- plan.py: ①（Markdown の表）を読み、③と静的に突合（compare_static）

## 状態
上の未了の 1〜5 は完了（examples.py、cli.py、lang_examples/shop_plan.md、tests/test_lang.py、README、生成した crate）。
残りは PR のレビューとマージ。次の候補: トリガ（決済結果の反映・期限切れ）、ソルバでの不変条件の検査、部品の実現の対応表、
plan のドラフトを会話で作る SKILL、①の来歴（判断の番号）の扱い。

## 決めたこと・注意
- 構文は仮。キーワードは日本語。文は1行1つ、ブロックは `{` で行を終え `}` だけの行で閉じる
- 応答＝フローの終端。トリガは範囲外（待つ は検査でエラー）
- 状態が終了へ進まない警告は、決済結果の反映などが範囲外のため出る（意図どおり）
- 既知の限界: 写像項目へ入力の写像を代入するとき、範囲の違いは検査していない（Rust 側で型エラーになりうる）
- cargo はこの環境で使える。Python は 3.13 想定、依存は追加なし
