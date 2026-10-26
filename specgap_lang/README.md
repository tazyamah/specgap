# specgap_lang：独自構文の最小の試作

> **後継は [Geas](https://github.com/tazyamah/geas) です。** 言語の処理系は geas へ移りました（`specgap_lang` → `geas`、`.sgl` → `.geas`）。ここは試作として残し、「ひとり用つぶやき」の例（`lang_examples/solo_tweet`）の置き場所です。

設計スレッド「振り返りと言語設計への落とし込み」で決めた設計の、最小の実装です。
**独自構文 → 構文解析 → 検査器 → Rust 生成**と、**plan の仕様書（①）とコードから生成した仕様書（③）の突合**が、お店の例（受注・決済要求）で通ります。
構文は仮です。概念が表せているか、検査と突合が回るかを見るためのものです。

## 流れ

```
会話で作る plan の仕様書（①, Markdown）──────────────┐
言語のコード（.sgl）→ 構文解析 → 検査 → 仕様書（③）──┼→ 突合（◆の欄）
                              └→ Rust 生成 → cargo → 具体例を実際に動かして①と突合
```

①はコードから独立しています（コードから①は作りません）。だから「計画どおりに実装されたか」が機械で確かめられます。

## 使い方

```
python -m specgap_lang check   lang_examples/shop.sgl                       # 検査
python -m specgap_lang spec    lang_examples/shop.sgl                       # 生成した仕様書（③）
python -m specgap_lang rust    lang_examples/shop.sgl -o lang_examples/shop_rust --plan lang_examples/shop_plan.md
python -m specgap_lang compare lang_examples/shop.sgl lang_examples/shop_plan.md      # 突合（具体例も実行）
python -m specgap_lang compare ... --no-run                                           # 静的な突合だけ
```

終了コード: 検査にエラー／突合に食い違いがあれば 1。「未規定」は食い違いに数えず、問いとして表示します。

## 出典

初回の対話で要件をまとめる部分（`interview` と `skills/plan-interview/`）は、Cockburn が提唱したユースケース手法に基づいています。
Alistair Cockburn, *Writing Effective Use Cases*, Addison-Wesley, 2000（日本語訳『ユースケース実践ガイド』ウイングス）。
「範囲 → アクターとユースケースの一覧 → 主な流れ → 拡張（失敗・例外）」と、ユースケースの粒度（要約／利用者目標／下位機能）の考え方を使っています。
具体例とルールの聞き分けは Example Mapping、動作要件の聞き取りは Volere・arc42・ISO/IEC 25010 を参考にしています（notes/spec-runtime-requirements-checklist.md）。

## 初回の対話の台帳（interview）

```
python -m specgap_lang interview init 台帳.json --title 題名   # 台帳を作る
python -m specgap_lang interview status 台帳.json             # 次に聞くこと。揃うまで「コードを書き始めてよい: いいえ」
python -m specgap_lang interview render 台帳.json -o plan.md  # plan（①）の会話の部分を Markdown に
```

会話の進め方は `skills/plan-interview/SKILL.md`（Cockburn のユースケースを一問一答で聞く。付加情報は仕分け、コードを書く前に動作要件 R1〜R7 を聞く）。台帳は plan の元で、コードから作らない。暫定の Python 実装。

## 会話から起こした2つ目の例（ひとり用つぶやき）

`lang_examples/solo_tweet/`：会話の台帳（ledger.json、判断J1〜J65）→ 計画書の節1〜7（plan_spec.md）→ コード（solo_tweet.sgl）→ 検査・突合・Rust生成（rust/）。
計画書とコードは機械で突合し、具体例を生成した Rust で実行して一致を確かめています（`python -m specgap_lang compare lang_examples/solo_tweet/solo_tweet.sgl lang_examples/solo_tweet/plan_spec.md`）。
この例のために、型に「文字列」「日時」、条件に「かつ」、読むだけの処理に「問い合わせ」（対象・条件・絞り込み・並び・先頭）を足しました。具体例は45件。さらに、外の出来事（アプリを開いた・つながりが戻った・画面を引っぱった）をきっかけに処理を起こす「出来事」を、トリガの仲間として足しました（`各 問い合わせ → 処理`：問い合わせが返す投稿1件ずつに起こす／`外から 処理`：外から届く内容で起こす）。画面の実行部は、この宣言にしたがって処理を起こします。

### 型と、外へ出す内容

型は論理（言語が述べる）・物理（宣言から自動で選ぶ）・入出力（外との境界。人の要求のみで決まる）の3層で整理しています（/mnt/project-files/solo_tweet/types-three-layers.md）。試作では、バイト列（長さの範囲つき。`バイト列 1..20000000`）を足し、添付ファイル・リンクをデータにしました。外部作用は、外へ出す内容を宣言し（`外部作用 Dropbox.書く(投稿ID: ID, 本文: 文字列, …)`）、計画書の「外部作用」の表と突き合わせます。さらに、投稿・添付・リンクのように複数の外部作用を1つの記録として扱うため、集合の要素ごとに要求する `各 添付ID in 投稿.添付 { … 要求 … }` を足しました（部品を先、本文を最後に出す1つの束。1つでも失敗すれば束ぜんたいが失敗）。データの宣言に保存先を書く（`データ 投稿 保存先 Dropbox { … }`）と、未同期かどうかの状態「記録」（端末保存済 ⇄ 記録済）を言語が足します（人は宣言しません）。また、外部作用を要求する処理は、結果を待つ経路（フローの「待つ」）を持つか、外部作用の宣言に `待たない "人が決めた理由"` を書かないと、検査がエラーにします。

### 画面（ブラウザで動く形）

`rust --host` で、画面から呼ぶ窓口（host.rs。JSONを渡すとJSONで答える）つきの crate を作り、WASM にします。`lang_examples/solo_tweet/app/` の画面は、判断（投稿・直す・消す・取り込みなど）をすべてこの WASM に任せ、画面側は待ち（期限・応答）の管理、Dropbox への書き込み、端末への保存だけを受け持ちます。

- `python lang_examples/solo_tweet/app/build.py` → `dist/solo_tweet.html`（1ファイル。お試しは模擬のDropbox、設定でトークンを入れると本物のDropbox）
- `node lang_examples/solo_tweet/app/check.js` → ブラウザを自動で動かして26件を確認（Dropboxは模擬の応答）
- 本物のDropboxとの接続は、この環境から届かないため未確認です。

## 検査が見つけるもの

| 書き方 | 検査の結果 |
|---|---|
| 端数の出る計算に丸めの指定がない | 問い「端数をどう丸めますか」 |
| 結果の種類に行き先がない／未定義の処理へ送る | エラー |
| 外部作用に冪等キーがない | エラー |
| 外部作用の失敗の扱い（待つ／待たない＋理由）がない | エラー |
| 宣言（遷移）にない状態の変更、元の状態の確認がない | エラー |
| 拒否された遷移（完了 → キャンセル）を行う | エラー |
| 宣言した「読む／書く／外部」と本体がずれる | エラー |
| 存在を確かめずにデータを引く | 問い |
| トリガに期限がない／行き先が未定義／引数と行き先の入力が合わない／待つ先が未定義 | エラー |
| 不変条件（在庫 >= 0、決済要求済なら合計 > 0）を守る確認が本体にない | エラー（反例つき） |

不変条件の検査は、試作では「項目 >= 0」と「状態 == X なら 項目 > n」の形だけ、書き方のパターンで証明します（ソルバは未導入）。

## Rust 生成

- 【処理】は純粋な関数 `(文脈, 保存, 入力) → (結果, 書込の列, 外部作用の列)`。実行は基盤の仕事
- 結果の種類は `enum`。【フロー】の行き先は `match`（網羅は Rust が検査）
- 物理数は範囲から自動で選ぶ（1..99 → u8、0.. → u64、金額 → i64）。式の途中は i128
- 範囲の宣言は、入力の取り込み（`検査()`）と書込の直前で検査する
- 生成した crate は `lang_examples/shop_rust/`（コミット済み。テストが、コードから作り直した結果と一致することを確かめる）

## 試作の範囲外・既知の限界

- トリガの実行（作成・発火・期限の監視は基盤の仕事。宣言と検査と生成まで）、補償、無停止更新、基盤（SQLite／PostgreSQL への永続化）
- 文字列・日時、部品の実現の対応表（丸めだけ組み込み）
- 範囲の検査は、入力をそのまま項目へ入れる形だけ（`項目 = 入力` の更新や、いったん変数に入れてからの代入は未検査。写像のキーの範囲も未検査）

## 構成

lexer.py / parser.py / ast.py（構文）、check.py（検査器）、spec.py（③の生成）、rustgen.py（Rust 生成）、
plan.py（①の読み取りと静的な突合）、examples.py（具体例の実行）、cli.py。
