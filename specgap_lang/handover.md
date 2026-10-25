# 引き継ぎメモ（最小の試作：独自構文 → Rust 生成と plan 突合）

更新: 2026-10-25。ブランチ `claude/project-thread-ljg1nb`（PR #18）（tazyamah/specgap）。置き場所は specgap リポジトリ内（tazyamah が選択）。
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
残りは PR のレビューとマージ。トリガ（宣言・検査・Rust生成・plan突合）は実装済み。次の候補: ソルバでの不変条件の検査、部品の実現の対応表、
plan のドラフトを会話で作る SKILL、①の来歴（判断の番号）の扱い（plan を会話で作る SKILL は済み）。

## 初回の対話（このスレッド）
- 台帳 specgap_lang/interview.py と skills/plan-interview/SKILL.md を追加（段階2）。次は段階3：小粒なアプリ（例：メモ・読書記録）を、短い対話の繰り返しで台帳→plan まで作って試す。
- その前に、段階2の完了後に Opus のレビューを依頼する（tazyamah の指示）。
- 調査メモ：/mnt/project-files/notes/spec-elicitation-survey.md（§3 の「土台を先に聞く」は旧案）、spec-runtime-requirements-checklist.md。
- Opus の2回目レビュー（段階2後）の未対応（中・低）：R8〜R15 の置き場、来歴（判断の番号）とのつながり、台帳の usecase の id 重複・拡張の at の検査、render の `|` のエスケープ、plan 節1〜7の表を会話から書き起こす段取りの実装（現状は SKILL の文章のみ）。
- Opus の初回レビューの未対応：状態とトリガの同名、応答の出どころ（外部作用の結果とのつながり）の検査、Update／変数経由の範囲検査、plan の期限の書き方（「現在+30分」か「30分」か）、台帳の J番号の採番。（台帳は plan.py と別モジュール interview.py にした）

## 決めたこと・注意
- 構文は仮。キーワードは日本語。文は1行1つ、ブロックは `{` で行を終え `}` だけの行で閉じる
- 応答＝フローの終端。待ちは「待つ トリガ名」で表し、トリガは要因（応答／期限）ごとの行き先をもつ。期限のないトリガは検査でエラー
- 状態「決済待ち」とトリガ「決済待ち」が同名。トリガ案では状態に待ちを持たせない方針なので、状態名を業務上の区分に改めるか要判断
- 既知の限界: 範囲の検査は、入力をそのまま項目へ入れる形（作成・項目代入）だけ。`項目 = 入力` の更新、変数経由、写像のキーは未検査
- 方針（tazyamah）: キーワードの日本語は仮組み。最終は英語。ツールの Python は暫定で、最終はすべて Rust（Rust の環境だけで動くように）
- cargo はこの環境で使える。Python は 3.13 想定、依存は追加なし
