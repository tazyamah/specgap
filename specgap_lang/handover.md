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
- 将来案（メモのみ・2026-10-25 tazyamah）：継続開発のときの差分確認も、同じレビューUIで行う（新旧の画面を両方同時に表示して同時に動かす）。レビューUIは仕様書というより単独のレビュー用UIになる。
- 段階3の試作「ひとり用つぶやき」：台帳 lang_examples/solo_tweet/ledger.json、会話の部分の plan は plan_conversation.md（ユースケース4つ、動かす環境R1〜R7、判断J1〜J33）。聞き終えた（status＝はい）。次は plan 節1〜7（データ・状態・処理・具体例の表）を会話から書き起こしてレビュー→コード。
- 試して分かったこと：選択肢つきの質問は答えやすい。人は直前の答えを後から訂正する（「というか」）ので判断の置き換えが要る。AIの解釈違いは多少ある（例：見るのはつながるときだけ、の誤解釈）。「おまかせ」の扱いは、AIが案を決めて仕様書に出し人がレビュー、とした。保存先の答え（Dropbox・サーバー無し）で最初のAI案が崩れることがある。
- 将来の案（メモのみ、今は実装しない・2026-10-25 tazyamah）：最初の会話で SKILL の動作モードを選ばせる。(a)補完モード：AIがアプリの専門家として先回りして聞く（例：金銭を扱うなら経理担当者のユースケースがあるはず、と仮定して聞く）、(b)非先回りモード：人のほうが要件に詳しいので下手に先回りしない。**ユースケースについてのみ**切り替える。動作要件は、人はIT知識がない前提でAIが主導する（ビジョンはあるがIT知識がない人でも使えるツールを目指す）。
- 台帳 specgap_lang/interview.py と skills/plan-interview/SKILL.md を追加（段階2）。次は段階3：小粒なアプリ（例：メモ・読書記録）を、短い対話の繰り返しで台帳→plan まで作って試す。
- その前に、段階2の完了後に Opus のレビューを依頼する（tazyamah の指示）。
- 調査メモ：/mnt/project-files/notes/spec-elicitation-survey.md（§3 の「土台を先に聞く」は旧案）、spec-runtime-requirements-checklist.md。
- Opus の2回目レビュー（段階2後）の未対応（中・低）：R8〜R15 の置き場、来歴（判断の番号）とのつながり、台帳の usecase の id 重複・拡張の at の検査、render の `|` のエスケープ、plan 節1〜7の表を会話から書き起こす段取りの実装（現状は SKILL の文章のみ）。
- Opus の初回レビューの未対応：状態とトリガの同名、応答の出どころ（外部作用の結果とのつながり）の検査、Update／変数経由の範囲検査、plan の期限の書き方（「現在+30分」か「30分」か）、台帳の J番号の採番。（台帳は plan.py と別モジュール interview.py にした）

## 決めたこと・注意
- 構文は仮。キーワードは日本語。文は1行1つ、ブロックは `{` で行を終え `}` だけの行で閉じる
- 応答＝フローの終端。待ちは「待つ トリガ名」で表し、トリガは要因（応答／期限）ごとの行き先をもつ。期限のないトリガは検査でエラー
- 状態は過去形（受付／決済要求済／完了／キャンセル）。「決済待ち」のような未来形の意味は状態でなくトリガに持たせる（tazyamah、2026-10-25）。期限は「現在 + 30 分」の書き方にそろえた
- 既知の限界: 範囲の検査は、入力をそのまま項目へ入れる形（作成・項目代入）だけ。`項目 = 入力` の更新、変数経由、写像のキーは未検査
- 方針（tazyamah）: キーワードの日本語は仮組み。最終は英語。ツールの Python は暫定で、最終はすべて Rust（Rust の環境だけで動くように）
- cargo はこの環境で使える。Python は 3.13 想定、依存は追加なし
