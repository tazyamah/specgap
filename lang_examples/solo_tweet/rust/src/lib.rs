// 自動生成。手で編集しない（コードから specgap_lang が毎回生成する）。
#![allow(non_snake_case, non_camel_case_types, non_upper_case_globals, dead_code, unused_variables, unused_mut)]
#![allow(uncommon_codepoints, mixed_script_confusables, unused_parens)]
use std::collections::{BTreeMap, BTreeSet};
use std::fmt::Display;

/// 端数の出る値（分子/分母）。丸めの指定が無いと整数にできない。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct 有理 {
    pub 分子: i128,
    pub 分母: i128,
}
impl Display for 有理 {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        write!(f, "{}/{}", self.分子, self.分母)
    }
}
pub fn 積(x: i128, r: 有理) -> 有理 {
    有理 { 分子: x * r.分子, 分母: r.分母 }
}
pub fn 切り捨て(x: 有理) -> i128 {
    x.分子.div_euclid(x.分母)
}
pub fn 切り上げ(x: 有理) -> i128 {
    -((-x.分子).div_euclid(x.分母))
}
pub fn 四捨五入(x: 有理) -> i128 {
    (2 * x.分子 + x.分母).div_euclid(2 * x.分母)
}
pub fn 範囲検査(名: &str, x: i128, lo: Option<i128>, hi: Option<i128>) -> Result<(), String> {
    if lo.map_or(false, |l| x < l) || hi.map_or(false, |h| x > h) {
        return Err(format!("{}={} は範囲外", 名, x));
    }
    Ok(())
}
pub fn 範囲内(名: &str, x: i128, lo: Option<i128>, hi: Option<i128>) -> i128 {
    範囲検査(名, x, lo, hi).expect("範囲の宣言に反する値を書こうとした");
    x
}
pub fn 集合表示(s: &BTreeSet<String>) -> String {
    format!("{{{}}}", s.iter().cloned().collect::<Vec<_>>().join(","))
}
pub fn 写像表示<V: Display>(m: &BTreeMap<String, V>) -> String {
    format!("{{{}}}", m.iter().map(|(k, v)| format!("{}:{}", k, v)).collect::<Vec<_>>().join(","))
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum 行き先 {
    処理(&'static str),
    待つ(&'static str),
    応答,
}
pub struct トリガ定義 {
    pub 名前: &'static str,
    /// (種別, 要因, 行き先の処理)。期限の要因は秒数。先に起きた要因が勝つ（実行は基盤）。
    pub 要因: &'static [(&'static str, &'static str, &'static str)],
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum 投稿状態 { 投稿済, 削除済, 完全削除済 }
impl 投稿状態 {
    pub fn 名前(&self) -> &'static str {
        match self {
            投稿状態::投稿済 => "投稿済",
            投稿状態::削除済 => "削除済",
            投稿状態::完全削除済 => "完全削除済",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum 記録状態 { 端末保存済, 記録済 }
impl 記録状態 {
    pub fn 名前(&self) -> &'static str {
        match self {
            記録状態::端末保存済 => "端末保存済",
            記録状態::記録済 => "記録済",
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct 投稿 {
    pub 投稿ID: String,
    pub 本文: String,
    pub 添付: BTreeSet<String>,
    pub リンク: BTreeSet<String>,
    pub 書いた日時: i64,
    pub 最後に操作した日時: i64,
    pub 状態: 投稿状態,
    pub 記録: 記録状態,
}

#[derive(Clone, Debug, Default)]
pub struct 保存 {
    pub 投稿: BTreeMap<String, 投稿>,
}

impl 保存 {
    pub fn 適用(&mut self, 書込列: Vec<書込>) {
        for w in 書込列 {
            match w {
                書込::投稿_新規(r) => { self.投稿.insert(r.投稿ID.clone(), r); }
                書込::投稿_記録(id, v) => { self.投稿.get_mut(&id).expect("書込先が無い").記録 = v; }
                書込::投稿_リンク(id, v) => { self.投稿.get_mut(&id).expect("書込先が無い").リンク = v; }
                書込::投稿_最後に操作した日時(id, v) => { self.投稿.get_mut(&id).expect("書込先が無い").最後に操作した日時 = v; }
                書込::投稿_本文(id, v) => { self.投稿.get_mut(&id).expect("書込先が無い").本文 = v; }
                書込::投稿_添付(id, v) => { self.投稿.get_mut(&id).expect("書込先が無い").添付 = v; }
                書込::投稿_状態(id, v) => { self.投稿.get_mut(&id).expect("書込先が無い").状態 = v; }
            }
        }
    }
    pub fn 差分(&self, 後: &保存) -> Vec<String> {
        let mut out: Vec<String> = Vec::new();
        for (id, r) in &後.投稿 {
            match self.投稿.get(id) {
                None => out.push(format!("投稿({})新規(本文={}, 添付={}, リンク={}, 書いた日時={}, 最後に操作した日時={}, 状態={}, 記録={})", id, r.本文, 集合表示(&r.添付), 集合表示(&r.リンク), r.書いた日時, r.最後に操作した日時, r.状態.名前(), r.記録.名前())),
                Some(b) => {
                    if b.本文 != r.本文 { out.push(format!("投稿({}).本文:{}→{}", id, b.本文, r.本文)); }
                    if b.添付 != r.添付 { out.push(format!("投稿({}).添付:{}→{}", id, 集合表示(&b.添付), 集合表示(&r.添付))); }
                    if b.リンク != r.リンク { out.push(format!("投稿({}).リンク:{}→{}", id, 集合表示(&b.リンク), 集合表示(&r.リンク))); }
                    if b.書いた日時 != r.書いた日時 { out.push(format!("投稿({}).書いた日時:{}→{}", id, b.書いた日時, r.書いた日時)); }
                    if b.最後に操作した日時 != r.最後に操作した日時 { out.push(format!("投稿({}).最後に操作した日時:{}→{}", id, b.最後に操作した日時, r.最後に操作した日時)); }
                    if b.状態 != r.状態 { out.push(format!("投稿({}).状態:{}→{}", id, b.状態.名前(), r.状態.名前())); }
                    if b.記録 != r.記録 { out.push(format!("投稿({}).記録:{}→{}", id, b.記録.名前(), r.記録.名前())); }
                }
            }
        }
        for id in self.投稿.keys() { if !後.投稿.contains_key(id) { out.push(format!("投稿({})削除", id)); } }
        out.sort();
        out
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum 書込 {
    投稿_新規(投稿),
    投稿_記録(String, 記録状態),
    投稿_リンク(String, BTreeSet<String>),
    投稿_最後に操作した日時(String, i64),
    投稿_本文(String, String),
    投稿_添付(String, BTreeSet<String>),
    投稿_状態(String, 投稿状態),
}

#[derive(Clone, Debug, PartialEq)]
pub enum 外部作用 {
    Dropbox_書く { 投稿ID: String, 本文: String, 冪等キー: String },
    Dropbox_消す { 投稿ID: String, 冪等キー: String },
}
impl 外部作用 {
    pub fn 表示(&self) -> String {
        match self {
            外部作用::Dropbox_書く { 投稿ID, 本文, 冪等キー } => format!("Dropbox.書く({}, {}, 冪等キー={})", 投稿ID, 本文, 冪等キー),
            外部作用::Dropbox_消す { 投稿ID, 冪等キー } => format!("Dropbox.消す({}, 冪等キー={})", 投稿ID, 冪等キー),
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum 投稿結果 {
    端末保存済(String),
    空,
}
impl 投稿結果 {
    pub fn 表示(&self) -> String {
        match self {
            投稿結果::端末保存済(a0) => format!("端末保存済({})", a0),
            投稿結果::空 => "空".to_string(),
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum 要求結果 {
    要求済,
    投稿なし,
    状態違い,
}
impl 要求結果 {
    pub fn 表示(&self) -> String {
        match self {
            要求結果::要求済 => "要求済".to_string(),
            要求結果::投稿なし => "投稿なし".to_string(),
            要求結果::状態違い => "状態違い".to_string(),
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum 確定結果 {
    確定済,
    投稿なし,
    状態違い,
}
impl 確定結果 {
    pub fn 表示(&self) -> String {
        match self {
            確定結果::確定済 => "確定済".to_string(),
            確定結果::投稿なし => "投稿なし".to_string(),
            確定結果::状態違い => "状態違い".to_string(),
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum 失敗表示結果 {
    表示した,
    投稿なし,
}
impl 失敗表示結果 {
    pub fn 表示(&self) -> String {
        match self {
            失敗表示結果::表示した => "表示した".to_string(),
            失敗表示結果::投稿なし => "投稿なし".to_string(),
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum 通知結果 {
    通知済,
    投稿なし,
    状態違い,
}
impl 通知結果 {
    pub fn 表示(&self) -> String {
        match self {
            通知結果::通知済 => "通知済".to_string(),
            通知結果::投稿なし => "投稿なし".to_string(),
            通知結果::状態違い => "状態違い".to_string(),
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum 直す結果 {
    直した,
    投稿なし,
    空,
    状態違い,
}
impl 直す結果 {
    pub fn 表示(&self) -> String {
        match self {
            直す結果::直した => "直した".to_string(),
            直す結果::投稿なし => "投稿なし".to_string(),
            直す結果::空 => "空".to_string(),
            直す結果::状態違い => "状態違い".to_string(),
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum 取り込み結果 {
    取り込んだ,
    古い,
    投稿なし,
}
impl 取り込み結果 {
    pub fn 表示(&self) -> String {
        match self {
            取り込み結果::取り込んだ => "取り込んだ".to_string(),
            取り込み結果::古い => "古い".to_string(),
            取り込み結果::投稿なし => "投稿なし".to_string(),
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum 消し取り込み結果 {
    取り込んだ,
    古い,
    状態違い,
    投稿なし,
}
impl 消し取り込み結果 {
    pub fn 表示(&self) -> String {
        match self {
            消し取り込み結果::取り込んだ => "取り込んだ".to_string(),
            消し取り込み結果::古い => "古い".to_string(),
            消し取り込み結果::状態違い => "状態違い".to_string(),
            消し取り込み結果::投稿なし => "投稿なし".to_string(),
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum 消す結果 {
    削除済,
    投稿なし,
    状態違い,
}
impl 消す結果 {
    pub fn 表示(&self) -> String {
        match self {
            消す結果::削除済 => "削除済".to_string(),
            消す結果::投稿なし => "投稿なし".to_string(),
            消す結果::状態違い => "状態違い".to_string(),
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum 戻す結果 {
    戻した,
    投稿なし,
    状態違い,
}
impl 戻す結果 {
    pub fn 表示(&self) -> String {
        match self {
            戻す結果::戻した => "戻した".to_string(),
            戻す結果::投稿なし => "投稿なし".to_string(),
            戻す結果::状態違い => "状態違い".to_string(),
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum 完全削除結果 {
    消した,
    投稿なし,
    状態違い,
}
impl 完全削除結果 {
    pub fn 表示(&self) -> String {
        match self {
            完全削除結果::消した => "消した".to_string(),
            完全削除結果::投稿なし => "投稿なし".to_string(),
            完全削除結果::状態違い => "状態違い".to_string(),
        }
    }
}

// ---- 処理 投稿する ----
pub struct 投稿する入力 {
    pub 本文: String,
    pub 添付: BTreeSet<String>,
    pub リンク: BTreeSet<String>,
}
impl 投稿する入力 {
    /// 外部から取り込むときの、範囲の宣言の検査
    pub fn 検査(&self) -> Result<(), String> {
        Ok(())
    }
}
/// 文脈：【参照】（配備時に埋まる）と、採番（実行のたびに基盤が代入）
pub struct 投稿する文脈 {
    pub 現在: i64,
    pub 新投稿ID: String,
}
pub struct 投稿する出力 {
    pub 結果: 投稿結果,
    pub 書込: Vec<書込>,
    pub 外部: Vec<外部作用>,
}
pub fn 投稿する(ctx: &投稿する文脈, 保存: &保存, 入力: &投稿する入力) -> 投稿する出力 {
    let mut 書込列: Vec<書込> = Vec::new();
    let mut 外部列: Vec<外部作用> = Vec::new();
    if ((入力.本文.is_empty() && 入力.添付.is_empty()) && 入力.リンク.is_empty()) {
        return 投稿する出力 { 結果: 投稿結果::空, 書込: 書込列, 外部: 外部列 };
    }
    let 投稿 = 投稿 {
        投稿ID: ctx.新投稿ID.clone(),
        本文: 入力.本文.clone(),
        添付: 入力.添付.clone(),
        リンク: 入力.リンク.clone(),
        書いた日時: ctx.現在,
        最後に操作した日時: ctx.現在,
        状態: 投稿状態::投稿済,
        記録: 記録状態::端末保存済,
    };
    書込列.push(書込::投稿_新規(投稿.clone()));
    return 投稿する出力 { 結果: 投稿結果::端末保存済(投稿.投稿ID.clone()), 書込: 書込列, 外部: 外部列 };
}

// ---- 処理 反映の要求 ----
pub struct 反映の要求入力 {
    pub 投稿ID: String,
}
impl 反映の要求入力 {
    /// 外部から取り込むときの、範囲の宣言の検査
    pub fn 検査(&self) -> Result<(), String> {
        Ok(())
    }
}
/// 文脈：【参照】（配備時に埋まる）と、採番（実行のたびに基盤が代入）
pub struct 反映の要求文脈 {
}
pub struct 反映の要求出力 {
    pub 結果: 要求結果,
    pub 書込: Vec<書込>,
    pub 外部: Vec<外部作用>,
}
pub fn 反映の要求(ctx: &反映の要求文脈, 保存: &保存, 入力: &反映の要求入力) -> 反映の要求出力 {
    let mut 書込列: Vec<書込> = Vec::new();
    let mut 外部列: Vec<外部作用> = Vec::new();
    let 投稿 = match 保存.投稿.get(&(入力.投稿ID.clone())) {
        Some(r) => r,
        None => return 反映の要求出力 { 結果: 要求結果::投稿なし, 書込: 書込列, 外部: 外部列 },
    };
    if (投稿.状態 == 投稿状態::削除済) {
        return 反映の要求出力 { 結果: 要求結果::状態違い, 書込: 書込列, 外部: 外部列 };
    }
    外部列.push(外部作用::Dropbox_書く { 投稿ID: 入力.投稿ID.clone(), 本文: 投稿.本文.clone(), 冪等キー: 入力.投稿ID.clone() });
    return 反映の要求出力 { 結果: 要求結果::要求済, 書込: 書込列, 外部: 外部列 };
}

// ---- 処理 記録の確定 ----
pub struct 記録の確定入力 {
    pub 投稿ID: String,
}
impl 記録の確定入力 {
    /// 外部から取り込むときの、範囲の宣言の検査
    pub fn 検査(&self) -> Result<(), String> {
        Ok(())
    }
}
/// 文脈：【参照】（配備時に埋まる）と、採番（実行のたびに基盤が代入）
pub struct 記録の確定文脈 {
}
pub struct 記録の確定出力 {
    pub 結果: 確定結果,
    pub 書込: Vec<書込>,
    pub 外部: Vec<外部作用>,
}
pub fn 記録の確定(ctx: &記録の確定文脈, 保存: &保存, 入力: &記録の確定入力) -> 記録の確定出力 {
    let mut 書込列: Vec<書込> = Vec::new();
    let mut 外部列: Vec<外部作用> = Vec::new();
    let 投稿 = match 保存.投稿.get(&(入力.投稿ID.clone())) {
        Some(r) => r,
        None => return 記録の確定出力 { 結果: 確定結果::投稿なし, 書込: 書込列, 外部: 外部列 },
    };
    if (投稿.記録 != 記録状態::端末保存済) {
        return 記録の確定出力 { 結果: 確定結果::状態違い, 書込: 書込列, 外部: 外部列 };
    }
    書込列.push(書込::投稿_記録(投稿.投稿ID.clone(), 記録状態::記録済));
    return 記録の確定出力 { 結果: 確定結果::確定済, 書込: 書込列, 外部: 外部列 };
}

// ---- 処理 記録失敗の表示 ----
pub struct 記録失敗の表示入力 {
    pub 投稿ID: String,
}
impl 記録失敗の表示入力 {
    /// 外部から取り込むときの、範囲の宣言の検査
    pub fn 検査(&self) -> Result<(), String> {
        Ok(())
    }
}
/// 文脈：【参照】（配備時に埋まる）と、採番（実行のたびに基盤が代入）
pub struct 記録失敗の表示文脈 {
}
pub struct 記録失敗の表示出力 {
    pub 結果: 失敗表示結果,
    pub 書込: Vec<書込>,
    pub 外部: Vec<外部作用>,
}
pub fn 記録失敗の表示(ctx: &記録失敗の表示文脈, 保存: &保存, 入力: &記録失敗の表示入力) -> 記録失敗の表示出力 {
    let mut 書込列: Vec<書込> = Vec::new();
    let mut 外部列: Vec<外部作用> = Vec::new();
    let 投稿 = match 保存.投稿.get(&(入力.投稿ID.clone())) {
        Some(r) => r,
        None => return 記録失敗の表示出力 { 結果: 失敗表示結果::投稿なし, 書込: 書込列, 外部: 外部列 },
    };
    return 記録失敗の表示出力 { 結果: 失敗表示結果::表示した, 書込: 書込列, 外部: 外部列 };
}

// ---- 処理 未反映の通知 ----
pub struct 未反映の通知入力 {
    pub 投稿ID: String,
}
impl 未反映の通知入力 {
    /// 外部から取り込むときの、範囲の宣言の検査
    pub fn 検査(&self) -> Result<(), String> {
        Ok(())
    }
}
/// 文脈：【参照】（配備時に埋まる）と、採番（実行のたびに基盤が代入）
pub struct 未反映の通知文脈 {
}
pub struct 未反映の通知出力 {
    pub 結果: 通知結果,
    pub 書込: Vec<書込>,
    pub 外部: Vec<外部作用>,
}
pub fn 未反映の通知(ctx: &未反映の通知文脈, 保存: &保存, 入力: &未反映の通知入力) -> 未反映の通知出力 {
    let mut 書込列: Vec<書込> = Vec::new();
    let mut 外部列: Vec<外部作用> = Vec::new();
    let 投稿 = match 保存.投稿.get(&(入力.投稿ID.clone())) {
        Some(r) => r,
        None => return 未反映の通知出力 { 結果: 通知結果::投稿なし, 書込: 書込列, 外部: 外部列 },
    };
    if (投稿.記録 != 記録状態::端末保存済) {
        return 未反映の通知出力 { 結果: 通知結果::状態違い, 書込: 書込列, 外部: 外部列 };
    }
    return 未反映の通知出力 { 結果: 通知結果::通知済, 書込: 書込列, 外部: 外部列 };
}

// ---- 処理 直す ----
pub struct 直す入力 {
    pub 投稿ID: String,
    pub 本文: String,
    pub 添付: BTreeSet<String>,
    pub リンク: BTreeSet<String>,
}
impl 直す入力 {
    /// 外部から取り込むときの、範囲の宣言の検査
    pub fn 検査(&self) -> Result<(), String> {
        Ok(())
    }
}
/// 文脈：【参照】（配備時に埋まる）と、採番（実行のたびに基盤が代入）
pub struct 直す文脈 {
    pub 現在: i64,
}
pub struct 直す出力 {
    pub 結果: 直す結果,
    pub 書込: Vec<書込>,
    pub 外部: Vec<外部作用>,
}
pub fn 直す(ctx: &直す文脈, 保存: &保存, 入力: &直す入力) -> 直す出力 {
    let mut 書込列: Vec<書込> = Vec::new();
    let mut 外部列: Vec<外部作用> = Vec::new();
    let 投稿 = match 保存.投稿.get(&(入力.投稿ID.clone())) {
        Some(r) => r,
        None => return 直す出力 { 結果: 直す結果::投稿なし, 書込: 書込列, 外部: 外部列 },
    };
    if ((入力.本文.is_empty() && 入力.添付.is_empty()) && 入力.リンク.is_empty()) {
        return 直す出力 { 結果: 直す結果::空, 書込: 書込列, 外部: 外部列 };
    }
    if (投稿.状態 == 投稿状態::削除済) {
        return 直す出力 { 結果: 直す結果::状態違い, 書込: 書込列, 外部: 外部列 };
    }
    書込列.push(書込::投稿_本文(投稿.投稿ID.clone(), 入力.本文.clone()));
    書込列.push(書込::投稿_添付(投稿.投稿ID.clone(), 入力.添付.clone()));
    書込列.push(書込::投稿_リンク(投稿.投稿ID.clone(), 入力.リンク.clone()));
    書込列.push(書込::投稿_最後に操作した日時(投稿.投稿ID.clone(), ctx.現在));
    return 直す出力 { 結果: 直す結果::直した, 書込: 書込列, 外部: 外部列 };
}

// ---- 処理 直しの取り込み ----
pub struct 直しの取り込み入力 {
    pub 投稿ID: String,
    pub 直し日時: i64,
    pub 本文: String,
}
impl 直しの取り込み入力 {
    /// 外部から取り込むときの、範囲の宣言の検査
    pub fn 検査(&self) -> Result<(), String> {
        Ok(())
    }
}
/// 文脈：【参照】（配備時に埋まる）と、採番（実行のたびに基盤が代入）
pub struct 直しの取り込み文脈 {
}
pub struct 直しの取り込み出力 {
    pub 結果: 取り込み結果,
    pub 書込: Vec<書込>,
    pub 外部: Vec<外部作用>,
}
pub fn 直しの取り込み(ctx: &直しの取り込み文脈, 保存: &保存, 入力: &直しの取り込み入力) -> 直しの取り込み出力 {
    let mut 書込列: Vec<書込> = Vec::new();
    let mut 外部列: Vec<外部作用> = Vec::new();
    let 投稿 = match 保存.投稿.get(&(入力.投稿ID.clone())) {
        Some(r) => r,
        None => return 直しの取り込み出力 { 結果: 取り込み結果::投稿なし, 書込: 書込列, 外部: 外部列 },
    };
    if (入力.直し日時 <= 投稿.最後に操作した日時) {
        return 直しの取り込み出力 { 結果: 取り込み結果::古い, 書込: 書込列, 外部: 外部列 };
    }
    書込列.push(書込::投稿_本文(投稿.投稿ID.clone(), 入力.本文.clone()));
    書込列.push(書込::投稿_最後に操作した日時(投稿.投稿ID.clone(), 入力.直し日時));
    return 直しの取り込み出力 { 結果: 取り込み結果::取り込んだ, 書込: 書込列, 外部: 外部列 };
}

// ---- 処理 消す ----
pub struct 消す入力 {
    pub 投稿ID: String,
}
impl 消す入力 {
    /// 外部から取り込むときの、範囲の宣言の検査
    pub fn 検査(&self) -> Result<(), String> {
        Ok(())
    }
}
/// 文脈：【参照】（配備時に埋まる）と、採番（実行のたびに基盤が代入）
pub struct 消す文脈 {
    pub 現在: i64,
}
pub struct 消す出力 {
    pub 結果: 消す結果,
    pub 書込: Vec<書込>,
    pub 外部: Vec<外部作用>,
}
pub fn 消す(ctx: &消す文脈, 保存: &保存, 入力: &消す入力) -> 消す出力 {
    let mut 書込列: Vec<書込> = Vec::new();
    let mut 外部列: Vec<外部作用> = Vec::new();
    let 投稿 = match 保存.投稿.get(&(入力.投稿ID.clone())) {
        Some(r) => r,
        None => return 消す出力 { 結果: 消す結果::投稿なし, 書込: 書込列, 外部: 外部列 },
    };
    if (投稿.状態 != 投稿状態::投稿済) {
        return 消す出力 { 結果: 消す結果::状態違い, 書込: 書込列, 外部: 外部列 };
    }
    書込列.push(書込::投稿_状態(投稿.投稿ID.clone(), 投稿状態::削除済));
    書込列.push(書込::投稿_最後に操作した日時(投稿.投稿ID.clone(), ctx.現在));
    return 消す出力 { 結果: 消す結果::削除済, 書込: 書込列, 外部: 外部列 };
}

// ---- 処理 消しの取り込み ----
pub struct 消しの取り込み入力 {
    pub 投稿ID: String,
    pub 操作日時: i64,
}
impl 消しの取り込み入力 {
    /// 外部から取り込むときの、範囲の宣言の検査
    pub fn 検査(&self) -> Result<(), String> {
        Ok(())
    }
}
/// 文脈：【参照】（配備時に埋まる）と、採番（実行のたびに基盤が代入）
pub struct 消しの取り込み文脈 {
}
pub struct 消しの取り込み出力 {
    pub 結果: 消し取り込み結果,
    pub 書込: Vec<書込>,
    pub 外部: Vec<外部作用>,
}
pub fn 消しの取り込み(ctx: &消しの取り込み文脈, 保存: &保存, 入力: &消しの取り込み入力) -> 消しの取り込み出力 {
    let mut 書込列: Vec<書込> = Vec::new();
    let mut 外部列: Vec<外部作用> = Vec::new();
    let 投稿 = match 保存.投稿.get(&(入力.投稿ID.clone())) {
        Some(r) => r,
        None => return 消しの取り込み出力 { 結果: 消し取り込み結果::投稿なし, 書込: 書込列, 外部: 外部列 },
    };
    if (入力.操作日時 <= 投稿.最後に操作した日時) {
        return 消しの取り込み出力 { 結果: 消し取り込み結果::古い, 書込: 書込列, 外部: 外部列 };
    }
    if (投稿.状態 != 投稿状態::投稿済) {
        return 消しの取り込み出力 { 結果: 消し取り込み結果::状態違い, 書込: 書込列, 外部: 外部列 };
    }
    書込列.push(書込::投稿_状態(投稿.投稿ID.clone(), 投稿状態::削除済));
    書込列.push(書込::投稿_最後に操作した日時(投稿.投稿ID.clone(), 入力.操作日時));
    return 消しの取り込み出力 { 結果: 消し取り込み結果::取り込んだ, 書込: 書込列, 外部: 外部列 };
}

// ---- 処理 元に戻す ----
pub struct 元に戻す入力 {
    pub 投稿ID: String,
}
impl 元に戻す入力 {
    /// 外部から取り込むときの、範囲の宣言の検査
    pub fn 検査(&self) -> Result<(), String> {
        Ok(())
    }
}
/// 文脈：【参照】（配備時に埋まる）と、採番（実行のたびに基盤が代入）
pub struct 元に戻す文脈 {
    pub 現在: i64,
}
pub struct 元に戻す出力 {
    pub 結果: 戻す結果,
    pub 書込: Vec<書込>,
    pub 外部: Vec<外部作用>,
}
pub fn 元に戻す(ctx: &元に戻す文脈, 保存: &保存, 入力: &元に戻す入力) -> 元に戻す出力 {
    let mut 書込列: Vec<書込> = Vec::new();
    let mut 外部列: Vec<外部作用> = Vec::new();
    let 投稿 = match 保存.投稿.get(&(入力.投稿ID.clone())) {
        Some(r) => r,
        None => return 元に戻す出力 { 結果: 戻す結果::投稿なし, 書込: 書込列, 外部: 外部列 },
    };
    if (投稿.状態 != 投稿状態::削除済) {
        return 元に戻す出力 { 結果: 戻す結果::状態違い, 書込: 書込列, 外部: 外部列 };
    }
    書込列.push(書込::投稿_状態(投稿.投稿ID.clone(), 投稿状態::投稿済));
    書込列.push(書込::投稿_最後に操作した日時(投稿.投稿ID.clone(), ctx.現在));
    return 元に戻す出力 { 結果: 戻す結果::戻した, 書込: 書込列, 外部: 外部列 };
}

// ---- 処理 完全に消す ----
pub struct 完全に消す入力 {
    pub 投稿ID: String,
}
impl 完全に消す入力 {
    /// 外部から取り込むときの、範囲の宣言の検査
    pub fn 検査(&self) -> Result<(), String> {
        Ok(())
    }
}
/// 文脈：【参照】（配備時に埋まる）と、採番（実行のたびに基盤が代入）
pub struct 完全に消す文脈 {
}
pub struct 完全に消す出力 {
    pub 結果: 完全削除結果,
    pub 書込: Vec<書込>,
    pub 外部: Vec<外部作用>,
}
pub fn 完全に消す(ctx: &完全に消す文脈, 保存: &保存, 入力: &完全に消す入力) -> 完全に消す出力 {
    let mut 書込列: Vec<書込> = Vec::new();
    let mut 外部列: Vec<外部作用> = Vec::new();
    let 投稿 = match 保存.投稿.get(&(入力.投稿ID.clone())) {
        Some(r) => r,
        None => return 完全に消す出力 { 結果: 完全削除結果::投稿なし, 書込: 書込列, 外部: 外部列 },
    };
    if (投稿.状態 != 投稿状態::削除済) {
        return 完全に消す出力 { 結果: 完全削除結果::状態違い, 書込: 書込列, 外部: 外部列 };
    }
    書込列.push(書込::投稿_状態(投稿.投稿ID.clone(), 投稿状態::完全削除済));
    外部列.push(外部作用::Dropbox_消す { 投稿ID: 入力.投稿ID.clone(), 冪等キー: 入力.投稿ID.clone() });
    return 完全に消す出力 { 結果: 完全削除結果::消した, 書込: 書込列, 外部: 外部列 };
}

// 【フロー】：結果の種類ごとの行き先。match の網羅は Rust が検査する。
pub fn 投稿_投稿する(r: &投稿結果) -> 行き先 {
    match r {
        投稿結果::端末保存済(..) => 行き先::処理("反映の要求"),
        投稿結果::空 => 行き先::応答,
    }
}

pub fn 投稿_反映の要求(r: &要求結果) -> 行き先 {
    match r {
        要求結果::要求済 => 行き先::待つ("書込待ち"),
        要求結果::投稿なし => 行き先::応答,
        要求結果::状態違い => 行き先::応答,
    }
}

pub fn 反映の結果_記録の確定(r: &確定結果) -> 行き先 {
    match r {
        確定結果::確定済 => 行き先::応答,
        確定結果::投稿なし => 行き先::応答,
        確定結果::状態違い => 行き先::応答,
    }
}

pub fn 反映の結果_記録失敗の表示(r: &失敗表示結果) -> 行き先 {
    match r {
        失敗表示結果::表示した => 行き先::応答,
        失敗表示結果::投稿なし => 行き先::応答,
    }
}

pub fn 反映の結果_未反映の通知(r: &通知結果) -> 行き先 {
    match r {
        通知結果::通知済 => 行き先::待つ("書込待ち"),
        通知結果::投稿なし => 行き先::応答,
        通知結果::状態違い => 行き先::応答,
    }
}

pub fn 直す_直す(r: &直す結果) -> 行き先 {
    match r {
        直す結果::直した => 行き先::処理("反映の要求"),
        直す結果::投稿なし => 行き先::応答,
        直す結果::空 => 行き先::応答,
        直す結果::状態違い => 行き先::応答,
    }
}

pub fn 別端末の操作_直しの取り込み(r: &取り込み結果) -> 行き先 {
    match r {
        取り込み結果::取り込んだ => 行き先::応答,
        取り込み結果::古い => 行き先::応答,
        取り込み結果::投稿なし => 行き先::応答,
    }
}

pub fn 別端末の操作_消しの取り込み(r: &消し取り込み結果) -> 行き先 {
    match r {
        消し取り込み結果::取り込んだ => 行き先::応答,
        消し取り込み結果::古い => 行き先::応答,
        消し取り込み結果::状態違い => 行き先::応答,
        消し取り込み結果::投稿なし => 行き先::応答,
    }
}

pub fn 消す_消す(r: &消す結果) -> 行き先 {
    match r {
        消す結果::削除済 => 行き先::待つ("削除猶予"),
        消す結果::投稿なし => 行き先::応答,
        消す結果::状態違い => 行き先::応答,
    }
}

pub fn 削除の結果_元に戻す(r: &戻す結果) -> 行き先 {
    match r {
        戻す結果::戻した => 行き先::応答,
        戻す結果::投稿なし => 行き先::応答,
        戻す結果::状態違い => 行き先::応答,
    }
}

pub fn 削除の結果_完全に消す(r: &完全削除結果) -> 行き先 {
    match r {
        完全削除結果::消した => 行き先::応答,
        完全削除結果::投稿なし => 行き先::応答,
        完全削除結果::状態違い => 行き先::応答,
    }
}

// 【トリガ】：待ちの宣言。要因ごとの行き先。作成・発火・期限の監視は基盤の仕事。
pub const トリガ一覧: &[トリガ定義] = &[
    トリガ定義 { 名前: "書込待ち", 要因: &[("応答", "書込成功", "記録の確定"), ("応答", "書込失敗", "記録失敗の表示"), ("期限", "86400", "未反映の通知")] },
    トリガ定義 { 名前: "削除猶予", 要因: &[("応答", "元に戻す", "元に戻す"), ("期限", "30", "完全に消す")] },
];

