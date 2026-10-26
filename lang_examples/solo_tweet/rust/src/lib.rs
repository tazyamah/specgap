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
pub fn バイト列表示(b: &[u8]) -> String { format!("0x{}", b.iter().map(|x| format!("{:02x}", x)).collect::<String>()) }
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
    pub fn 名前から(s: &str) -> Option<Self> {
        match s {
            "投稿済" => Some(投稿状態::投稿済),
            "削除済" => Some(投稿状態::削除済),
            "完全削除済" => Some(投稿状態::完全削除済),
            _ => None,
        }
    }
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
    pub fn 名前から(s: &str) -> Option<Self> {
        match s {
            "端末保存済" => Some(記録状態::端末保存済),
            "記録済" => Some(記録状態::記録済),
            _ => None,
        }
    }
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

#[derive(Clone, Debug, PartialEq)]
pub struct 添付ファイル {
    pub 添付ID: String,
    pub 名前: String,
    pub 種類: String,
    pub 中身: Vec<u8>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct 添付リンク {
    pub リンクID: String,
    pub 先: String,
}

#[derive(Clone, Debug, Default)]
pub struct 保存 {
    pub 投稿: BTreeMap<String, 投稿>,
    pub 添付ファイル: BTreeMap<String, 添付ファイル>,
    pub 添付リンク: BTreeMap<String, 添付リンク>,
}

impl 保存 {
    pub fn 適用(&mut self, 書込列: Vec<書込>) {
        for w in 書込列 {
            match w {
                書込::投稿_新規(r) => { self.投稿.insert(r.投稿ID.clone(), r); }
                書込::添付ファイル_新規(r) => { self.添付ファイル.insert(r.添付ID.clone(), r); }
                書込::添付リンク_新規(r) => { self.添付リンク.insert(r.リンクID.clone(), r); }
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
        for (id, r) in &後.添付ファイル {
            match self.添付ファイル.get(id) {
                None => out.push(format!("添付ファイル({})新規(名前={}, 種類={}, 中身={})", id, r.名前, r.種類, バイト列表示(&r.中身))),
                Some(b) => {
                    if b.名前 != r.名前 { out.push(format!("添付ファイル({}).名前:{}→{}", id, b.名前, r.名前)); }
                    if b.種類 != r.種類 { out.push(format!("添付ファイル({}).種類:{}→{}", id, b.種類, r.種類)); }
                    if b.中身 != r.中身 { out.push(format!("添付ファイル({}).中身:{}→{}", id, バイト列表示(&b.中身), バイト列表示(&r.中身))); }
                }
            }
        }
        for id in self.添付ファイル.keys() { if !後.添付ファイル.contains_key(id) { out.push(format!("添付ファイル({})削除", id)); } }
        for (id, r) in &後.添付リンク {
            match self.添付リンク.get(id) {
                None => out.push(format!("添付リンク({})新規(先={})", id, r.先)),
                Some(b) => {
                    if b.先 != r.先 { out.push(format!("添付リンク({}).先:{}→{}", id, b.先, r.先)); }
                }
            }
        }
        for id in self.添付リンク.keys() { if !後.添付リンク.contains_key(id) { out.push(format!("添付リンク({})削除", id)); } }
        out.sort();
        out
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum 書込 {
    投稿_新規(投稿),
    添付ファイル_新規(添付ファイル),
    添付リンク_新規(添付リンク),
    投稿_記録(String, 記録状態),
    投稿_リンク(String, BTreeSet<String>),
    投稿_最後に操作した日時(String, i64),
    投稿_本文(String, String),
    投稿_添付(String, BTreeSet<String>),
    投稿_状態(String, 投稿状態),
}

#[derive(Clone, Debug, PartialEq)]
pub enum 外部作用 {
    Dropbox_書く { 投稿ID: String, 本文: String, 添付: BTreeSet<String>, リンク: BTreeSet<String>, 書いた日時: i64, 最後に操作した日時: i64, 冪等キー: String },
    Dropbox_消す { 投稿ID: String, 冪等キー: String },
    Dropbox_ファイルを書く { 添付ID: String, 名前: String, 種類: String, 中身: Vec<u8>, 冪等キー: String },
    Dropbox_リンクを書く { リンクID: String, 先: String, 冪等キー: String },
}
impl 外部作用 {
    pub fn 表示(&self) -> String {
        match self {
            外部作用::Dropbox_書く { 投稿ID, 本文, 添付, リンク, 書いた日時, 最後に操作した日時, 冪等キー } => format!("Dropbox.書く({}, {}, {}, {}, {}, {}, 冪等キー={})", 投稿ID, 本文, 集合表示(&添付), 集合表示(&リンク), 書いた日時, 最後に操作した日時, 冪等キー),
            外部作用::Dropbox_消す { 投稿ID, 冪等キー } => format!("Dropbox.消す({}, 冪等キー={})", 投稿ID, 冪等キー),
            外部作用::Dropbox_ファイルを書く { 添付ID, 名前, 種類, 中身, 冪等キー } => format!("Dropbox.ファイルを書く({}, {}, {}, {}, 冪等キー={})", 添付ID, 名前, 種類, バイト列表示(&中身), 冪等キー),
            外部作用::Dropbox_リンクを書く { リンクID, 先, 冪等キー } => format!("Dropbox.リンクを書く({}, {}, 冪等キー={})", リンクID, 先, 冪等キー),
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
    pub fn 名前(&self) -> &'static str {
        match self {
            投稿結果::端末保存済(..) => "端末保存済",
            投稿結果::空 => "空",
        }
    }
    pub fn 引数(&self) -> Vec<String> {
        match self {
            投稿結果::端末保存済(a0) => vec![format!("{}", a0)],
            投稿結果::空 => vec![],
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum 添付結果 {
    添付済(String),
}
impl 添付結果 {
    pub fn 表示(&self) -> String {
        match self {
            添付結果::添付済(a0) => format!("添付済({})", a0),
        }
    }
    pub fn 名前(&self) -> &'static str {
        match self {
            添付結果::添付済(..) => "添付済",
        }
    }
    pub fn 引数(&self) -> Vec<String> {
        match self {
            添付結果::添付済(a0) => vec![format!("{}", a0)],
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum リンク結果 {
    付けた(String),
}
impl リンク結果 {
    pub fn 表示(&self) -> String {
        match self {
            リンク結果::付けた(a0) => format!("付けた({})", a0),
        }
    }
    pub fn 名前(&self) -> &'static str {
        match self {
            リンク結果::付けた(..) => "付けた",
        }
    }
    pub fn 引数(&self) -> Vec<String> {
        match self {
            リンク結果::付けた(a0) => vec![format!("{}", a0)],
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
    pub fn 名前(&self) -> &'static str {
        match self {
            要求結果::要求済 => "要求済",
            要求結果::投稿なし => "投稿なし",
            要求結果::状態違い => "状態違い",
        }
    }
    pub fn 引数(&self) -> Vec<String> {
        match self {
            要求結果::要求済 => vec![],
            要求結果::投稿なし => vec![],
            要求結果::状態違い => vec![],
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
    pub fn 名前(&self) -> &'static str {
        match self {
            確定結果::確定済 => "確定済",
            確定結果::投稿なし => "投稿なし",
            確定結果::状態違い => "状態違い",
        }
    }
    pub fn 引数(&self) -> Vec<String> {
        match self {
            確定結果::確定済 => vec![],
            確定結果::投稿なし => vec![],
            確定結果::状態違い => vec![],
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
    pub fn 名前(&self) -> &'static str {
        match self {
            失敗表示結果::表示した => "表示した",
            失敗表示結果::投稿なし => "投稿なし",
        }
    }
    pub fn 引数(&self) -> Vec<String> {
        match self {
            失敗表示結果::表示した => vec![],
            失敗表示結果::投稿なし => vec![],
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
    pub fn 名前(&self) -> &'static str {
        match self {
            通知結果::通知済 => "通知済",
            通知結果::投稿なし => "投稿なし",
            通知結果::状態違い => "状態違い",
        }
    }
    pub fn 引数(&self) -> Vec<String> {
        match self {
            通知結果::通知済 => vec![],
            通知結果::投稿なし => vec![],
            通知結果::状態違い => vec![],
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
    pub fn 名前(&self) -> &'static str {
        match self {
            直す結果::直した => "直した",
            直す結果::投稿なし => "投稿なし",
            直す結果::空 => "空",
            直す結果::状態違い => "状態違い",
        }
    }
    pub fn 引数(&self) -> Vec<String> {
        match self {
            直す結果::直した => vec![],
            直す結果::投稿なし => vec![],
            直す結果::空 => vec![],
            直す結果::状態違い => vec![],
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum 巻き戻し結果 {
    巻き戻した,
    不要,
    投稿なし,
}
impl 巻き戻し結果 {
    pub fn 表示(&self) -> String {
        match self {
            巻き戻し結果::巻き戻した => "巻き戻した".to_string(),
            巻き戻し結果::不要 => "不要".to_string(),
            巻き戻し結果::投稿なし => "投稿なし".to_string(),
        }
    }
    pub fn 名前(&self) -> &'static str {
        match self {
            巻き戻し結果::巻き戻した => "巻き戻した",
            巻き戻し結果::不要 => "不要",
            巻き戻し結果::投稿なし => "投稿なし",
        }
    }
    pub fn 引数(&self) -> Vec<String> {
        match self {
            巻き戻し結果::巻き戻した => vec![],
            巻き戻し結果::不要 => vec![],
            巻き戻し結果::投稿なし => vec![],
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum 実体の取り込み結果 {
    取り込んだ,
}
impl 実体の取り込み結果 {
    pub fn 表示(&self) -> String {
        match self {
            実体の取り込み結果::取り込んだ => "取り込んだ".to_string(),
        }
    }
    pub fn 名前(&self) -> &'static str {
        match self {
            実体の取り込み結果::取り込んだ => "取り込んだ",
        }
    }
    pub fn 引数(&self) -> Vec<String> {
        match self {
            実体の取り込み結果::取り込んだ => vec![],
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum 新規取り込み結果 {
    取り込んだ,
}
impl 新規取り込み結果 {
    pub fn 表示(&self) -> String {
        match self {
            新規取り込み結果::取り込んだ => "取り込んだ".to_string(),
        }
    }
    pub fn 名前(&self) -> &'static str {
        match self {
            新規取り込み結果::取り込んだ => "取り込んだ",
        }
    }
    pub fn 引数(&self) -> Vec<String> {
        match self {
            新規取り込み結果::取り込んだ => vec![],
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum 取り込み結果 {
    取り込んだ,
    古い,
    削除済,
    投稿なし,
}
impl 取り込み結果 {
    pub fn 表示(&self) -> String {
        match self {
            取り込み結果::取り込んだ => "取り込んだ".to_string(),
            取り込み結果::古い => "古い".to_string(),
            取り込み結果::削除済 => "削除済".to_string(),
            取り込み結果::投稿なし => "投稿なし".to_string(),
        }
    }
    pub fn 名前(&self) -> &'static str {
        match self {
            取り込み結果::取り込んだ => "取り込んだ",
            取り込み結果::古い => "古い",
            取り込み結果::削除済 => "削除済",
            取り込み結果::投稿なし => "投稿なし",
        }
    }
    pub fn 引数(&self) -> Vec<String> {
        match self {
            取り込み結果::取り込んだ => vec![],
            取り込み結果::古い => vec![],
            取り込み結果::削除済 => vec![],
            取り込み結果::投稿なし => vec![],
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum 戻す取り込み結果 {
    取り込んだ,
    古い,
    状態違い,
    投稿なし,
}
impl 戻す取り込み結果 {
    pub fn 表示(&self) -> String {
        match self {
            戻す取り込み結果::取り込んだ => "取り込んだ".to_string(),
            戻す取り込み結果::古い => "古い".to_string(),
            戻す取り込み結果::状態違い => "状態違い".to_string(),
            戻す取り込み結果::投稿なし => "投稿なし".to_string(),
        }
    }
    pub fn 名前(&self) -> &'static str {
        match self {
            戻す取り込み結果::取り込んだ => "取り込んだ",
            戻す取り込み結果::古い => "古い",
            戻す取り込み結果::状態違い => "状態違い",
            戻す取り込み結果::投稿なし => "投稿なし",
        }
    }
    pub fn 引数(&self) -> Vec<String> {
        match self {
            戻す取り込み結果::取り込んだ => vec![],
            戻す取り込み結果::古い => vec![],
            戻す取り込み結果::状態違い => vec![],
            戻す取り込み結果::投稿なし => vec![],
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
    pub fn 名前(&self) -> &'static str {
        match self {
            消し取り込み結果::取り込んだ => "取り込んだ",
            消し取り込み結果::古い => "古い",
            消し取り込み結果::状態違い => "状態違い",
            消し取り込み結果::投稿なし => "投稿なし",
        }
    }
    pub fn 引数(&self) -> Vec<String> {
        match self {
            消し取り込み結果::取り込んだ => vec![],
            消し取り込み結果::古い => vec![],
            消し取り込み結果::状態違い => vec![],
            消し取り込み結果::投稿なし => vec![],
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
    pub fn 名前(&self) -> &'static str {
        match self {
            消す結果::削除済 => "削除済",
            消す結果::投稿なし => "投稿なし",
            消す結果::状態違い => "状態違い",
        }
    }
    pub fn 引数(&self) -> Vec<String> {
        match self {
            消す結果::削除済 => vec![],
            消す結果::投稿なし => vec![],
            消す結果::状態違い => vec![],
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
    pub fn 名前(&self) -> &'static str {
        match self {
            戻す結果::戻した => "戻した",
            戻す結果::投稿なし => "投稿なし",
            戻す結果::状態違い => "状態違い",
        }
    }
    pub fn 引数(&self) -> Vec<String> {
        match self {
            戻す結果::戻した => vec![],
            戻す結果::投稿なし => vec![],
            戻す結果::状態違い => vec![],
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
    pub fn 名前(&self) -> &'static str {
        match self {
            完全削除結果::消した => "消した",
            完全削除結果::投稿なし => "投稿なし",
            完全削除結果::状態違い => "状態違い",
        }
    }
    pub fn 引数(&self) -> Vec<String> {
        match self {
            完全削除結果::消した => vec![],
            完全削除結果::投稿なし => vec![],
            完全削除結果::状態違い => vec![],
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

// ---- 処理 添付する ----
pub struct 添付する入力 {
    pub 名前: String,
    pub 種類: String,
    pub 中身: Vec<u8>,
}
impl 添付する入力 {
    /// 外部から取り込むときの、範囲の宣言の検査
    pub fn 検査(&self) -> Result<(), String> {
        範囲検査("中身の長さ", self.中身.len() as i128, Some(1), Some(20000000))?;
        Ok(())
    }
}
/// 文脈：【参照】（配備時に埋まる）と、採番（実行のたびに基盤が代入）
pub struct 添付する文脈 {
    pub 新添付ファイルID: String,
}
pub struct 添付する出力 {
    pub 結果: 添付結果,
    pub 書込: Vec<書込>,
    pub 外部: Vec<外部作用>,
}
pub fn 添付する(ctx: &添付する文脈, 保存: &保存, 入力: &添付する入力) -> 添付する出力 {
    let mut 書込列: Vec<書込> = Vec::new();
    let mut 外部列: Vec<外部作用> = Vec::new();
    let 添付 = 添付ファイル {
        添付ID: ctx.新添付ファイルID.clone(),
        名前: 入力.名前.clone(),
        種類: 入力.種類.clone(),
        中身: 入力.中身.clone(),
    };
    書込列.push(書込::添付ファイル_新規(添付.clone()));
    return 添付する出力 { 結果: 添付結果::添付済(添付.添付ID.clone()), 書込: 書込列, 外部: 外部列 };
}

// ---- 処理 リンクを付ける ----
pub struct リンクを付ける入力 {
    pub 先: String,
}
impl リンクを付ける入力 {
    /// 外部から取り込むときの、範囲の宣言の検査
    pub fn 検査(&self) -> Result<(), String> {
        Ok(())
    }
}
/// 文脈：【参照】（配備時に埋まる）と、採番（実行のたびに基盤が代入）
pub struct リンクを付ける文脈 {
    pub 新添付リンクID: String,
}
pub struct リンクを付ける出力 {
    pub 結果: リンク結果,
    pub 書込: Vec<書込>,
    pub 外部: Vec<外部作用>,
}
pub fn リンクを付ける(ctx: &リンクを付ける文脈, 保存: &保存, 入力: &リンクを付ける入力) -> リンクを付ける出力 {
    let mut 書込列: Vec<書込> = Vec::new();
    let mut 外部列: Vec<外部作用> = Vec::new();
    let 付け先 = 添付リンク {
        リンクID: ctx.新添付リンクID.clone(),
        先: 入力.先.clone(),
    };
    書込列.push(書込::添付リンク_新規(付け先.clone()));
    return リンクを付ける出力 { 結果: リンク結果::付けた(付け先.リンクID.clone()), 書込: 書込列, 外部: 外部列 };
}

// ---- 処理 添付の取り込み ----
pub struct 添付の取り込み入力 {
    pub 名前: String,
    pub 種類: String,
    pub 中身: Vec<u8>,
}
impl 添付の取り込み入力 {
    /// 外部から取り込むときの、範囲の宣言の検査
    pub fn 検査(&self) -> Result<(), String> {
        範囲検査("中身の長さ", self.中身.len() as i128, Some(1), Some(20000000))?;
        Ok(())
    }
}
/// 文脈：【参照】（配備時に埋まる）と、採番（実行のたびに基盤が代入）
pub struct 添付の取り込み文脈 {
    pub 新添付ファイルID: String,
}
pub struct 添付の取り込み出力 {
    pub 結果: 実体の取り込み結果,
    pub 書込: Vec<書込>,
    pub 外部: Vec<外部作用>,
}
pub fn 添付の取り込み(ctx: &添付の取り込み文脈, 保存: &保存, 入力: &添付の取り込み入力) -> 添付の取り込み出力 {
    let mut 書込列: Vec<書込> = Vec::new();
    let mut 外部列: Vec<外部作用> = Vec::new();
    let 添付 = 添付ファイル {
        添付ID: ctx.新添付ファイルID.clone(),
        名前: 入力.名前.clone(),
        種類: 入力.種類.clone(),
        中身: 入力.中身.clone(),
    };
    書込列.push(書込::添付ファイル_新規(添付.clone()));
    return 添付の取り込み出力 { 結果: 実体の取り込み結果::取り込んだ, 書込: 書込列, 外部: 外部列 };
}

// ---- 処理 リンクの取り込み ----
pub struct リンクの取り込み入力 {
    pub 先: String,
}
impl リンクの取り込み入力 {
    /// 外部から取り込むときの、範囲の宣言の検査
    pub fn 検査(&self) -> Result<(), String> {
        Ok(())
    }
}
/// 文脈：【参照】（配備時に埋まる）と、採番（実行のたびに基盤が代入）
pub struct リンクの取り込み文脈 {
    pub 新添付リンクID: String,
}
pub struct リンクの取り込み出力 {
    pub 結果: 実体の取り込み結果,
    pub 書込: Vec<書込>,
    pub 外部: Vec<外部作用>,
}
pub fn リンクの取り込み(ctx: &リンクの取り込み文脈, 保存: &保存, 入力: &リンクの取り込み入力) -> リンクの取り込み出力 {
    let mut 書込列: Vec<書込> = Vec::new();
    let mut 外部列: Vec<外部作用> = Vec::new();
    let 付け先 = 添付リンク {
        リンクID: ctx.新添付リンクID.clone(),
        先: 入力.先.clone(),
    };
    書込列.push(書込::添付リンク_新規(付け先.clone()));
    return リンクの取り込み出力 { 結果: 実体の取り込み結果::取り込んだ, 書込: 書込列, 外部: 外部列 };
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
    let 束の始め = 外部列.len();
    for k_ in 投稿.添付.iter() {
        let 添付ID: String = k_.clone();
    let 添付 = match 保存.添付ファイル.get(&(添付ID.clone())) {
        Some(r) => r,
        None => { 外部列.truncate(束の始め); return 反映の要求出力 { 結果: 要求結果::投稿なし, 書込: 書込列, 外部: 外部列 }; }
    };
    外部列.push(外部作用::Dropbox_ファイルを書く { 添付ID: 添付ID.clone(), 名前: 添付.名前.clone(), 種類: 添付.種類.clone(), 中身: 添付.中身.clone(), 冪等キー: 添付ID.clone() });
    }
    let 束の始め = 外部列.len();
    for k_ in 投稿.リンク.iter() {
        let リンクID: String = k_.clone();
    let 付け先 = match 保存.添付リンク.get(&(リンクID.clone())) {
        Some(r) => r,
        None => { 外部列.truncate(束の始め); return 反映の要求出力 { 結果: 要求結果::投稿なし, 書込: 書込列, 外部: 外部列 }; }
    };
    外部列.push(外部作用::Dropbox_リンクを書く { リンクID: リンクID.clone(), 先: 付け先.先.clone(), 冪等キー: リンクID.clone() });
    }
    外部列.push(外部作用::Dropbox_書く { 投稿ID: 入力.投稿ID.clone(), 本文: 投稿.本文.clone(), 添付: 投稿.添付.clone(), リンク: 投稿.リンク.clone(), 書いた日時: 投稿.書いた日時, 最後に操作した日時: 投稿.最後に操作した日時, 冪等キー: 入力.投稿ID.clone() });
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

// ---- 処理 未反映に戻す ----
pub struct 未反映に戻す入力 {
    pub 投稿ID: String,
}
impl 未反映に戻す入力 {
    /// 外部から取り込むときの、範囲の宣言の検査
    pub fn 検査(&self) -> Result<(), String> {
        Ok(())
    }
}
/// 文脈：【参照】（配備時に埋まる）と、採番（実行のたびに基盤が代入）
pub struct 未反映に戻す文脈 {
}
pub struct 未反映に戻す出力 {
    pub 結果: 巻き戻し結果,
    pub 書込: Vec<書込>,
    pub 外部: Vec<外部作用>,
}
pub fn 未反映に戻す(ctx: &未反映に戻す文脈, 保存: &保存, 入力: &未反映に戻す入力) -> 未反映に戻す出力 {
    let mut 書込列: Vec<書込> = Vec::new();
    let mut 外部列: Vec<外部作用> = Vec::new();
    let 投稿 = match 保存.投稿.get(&(入力.投稿ID.clone())) {
        Some(r) => r,
        None => return 未反映に戻す出力 { 結果: 巻き戻し結果::投稿なし, 書込: 書込列, 外部: 外部列 },
    };
    if (投稿.記録 != 記録状態::記録済) {
        return 未反映に戻す出力 { 結果: 巻き戻し結果::不要, 書込: 書込列, 外部: 外部列 };
    }
    書込列.push(書込::投稿_記録(投稿.投稿ID.clone(), 記録状態::端末保存済));
    return 未反映に戻す出力 { 結果: 巻き戻し結果::巻き戻した, 書込: 書込列, 外部: 外部列 };
}

// ---- 処理 投稿の取り込み ----
pub struct 投稿の取り込み入力 {
    pub 本文: String,
    pub 添付: BTreeSet<String>,
    pub リンク: BTreeSet<String>,
    pub 書いた日時: i64,
    pub 操作日時: i64,
}
impl 投稿の取り込み入力 {
    /// 外部から取り込むときの、範囲の宣言の検査
    pub fn 検査(&self) -> Result<(), String> {
        Ok(())
    }
}
/// 文脈：【参照】（配備時に埋まる）と、採番（実行のたびに基盤が代入）
pub struct 投稿の取り込み文脈 {
    pub 新投稿ID: String,
}
pub struct 投稿の取り込み出力 {
    pub 結果: 新規取り込み結果,
    pub 書込: Vec<書込>,
    pub 外部: Vec<外部作用>,
}
pub fn 投稿の取り込み(ctx: &投稿の取り込み文脈, 保存: &保存, 入力: &投稿の取り込み入力) -> 投稿の取り込み出力 {
    let mut 書込列: Vec<書込> = Vec::new();
    let mut 外部列: Vec<外部作用> = Vec::new();
    let 投稿 = 投稿 {
        投稿ID: ctx.新投稿ID.clone(),
        本文: 入力.本文.clone(),
        添付: 入力.添付.clone(),
        リンク: 入力.リンク.clone(),
        書いた日時: 入力.書いた日時,
        最後に操作した日時: 入力.操作日時,
        状態: 投稿状態::投稿済,
        記録: 記録状態::記録済,
    };
    書込列.push(書込::投稿_新規(投稿.clone()));
    return 投稿の取り込み出力 { 結果: 新規取り込み結果::取り込んだ, 書込: 書込列, 外部: 外部列 };
}

// ---- 処理 直しの取り込み ----
pub struct 直しの取り込み入力 {
    pub 投稿ID: String,
    pub 直し日時: i64,
    pub 本文: String,
    pub 添付: BTreeSet<String>,
    pub リンク: BTreeSet<String>,
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
    if (投稿.状態 == 投稿状態::削除済) {
        return 直しの取り込み出力 { 結果: 取り込み結果::削除済, 書込: 書込列, 外部: 外部列 };
    }
    書込列.push(書込::投稿_本文(投稿.投稿ID.clone(), 入力.本文.clone()));
    書込列.push(書込::投稿_添付(投稿.投稿ID.clone(), 入力.添付.clone()));
    書込列.push(書込::投稿_リンク(投稿.投稿ID.clone(), 入力.リンク.clone()));
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

// ---- 処理 直しで戻す ----
pub struct 直しで戻す入力 {
    pub 投稿ID: String,
    pub 直し日時: i64,
    pub 本文: String,
    pub 添付: BTreeSet<String>,
    pub リンク: BTreeSet<String>,
}
impl 直しで戻す入力 {
    /// 外部から取り込むときの、範囲の宣言の検査
    pub fn 検査(&self) -> Result<(), String> {
        Ok(())
    }
}
/// 文脈：【参照】（配備時に埋まる）と、採番（実行のたびに基盤が代入）
pub struct 直しで戻す文脈 {
}
pub struct 直しで戻す出力 {
    pub 結果: 戻す取り込み結果,
    pub 書込: Vec<書込>,
    pub 外部: Vec<外部作用>,
}
pub fn 直しで戻す(ctx: &直しで戻す文脈, 保存: &保存, 入力: &直しで戻す入力) -> 直しで戻す出力 {
    let mut 書込列: Vec<書込> = Vec::new();
    let mut 外部列: Vec<外部作用> = Vec::new();
    let 投稿 = match 保存.投稿.get(&(入力.投稿ID.clone())) {
        Some(r) => r,
        None => return 直しで戻す出力 { 結果: 戻す取り込み結果::投稿なし, 書込: 書込列, 外部: 外部列 },
    };
    if (入力.直し日時 <= 投稿.最後に操作した日時) {
        return 直しで戻す出力 { 結果: 戻す取り込み結果::古い, 書込: 書込列, 外部: 外部列 };
    }
    if (投稿.状態 != 投稿状態::削除済) {
        return 直しで戻す出力 { 結果: 戻す取り込み結果::状態違い, 書込: 書込列, 外部: 外部列 };
    }
    書込列.push(書込::投稿_状態(投稿.投稿ID.clone(), 投稿状態::投稿済));
    書込列.push(書込::投稿_本文(投稿.投稿ID.clone(), 入力.本文.clone()));
    書込列.push(書込::投稿_添付(投稿.投稿ID.clone(), 入力.添付.clone()));
    書込列.push(書込::投稿_リンク(投稿.投稿ID.clone(), 入力.リンク.clone()));
    書込列.push(書込::投稿_最後に操作した日時(投稿.投稿ID.clone(), 入力.直し日時));
    return 直しで戻す出力 { 結果: 戻す取り込み結果::取り込んだ, 書込: 書込列, 外部: 外部列 };
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

// ---- 問い合わせ 一覧を見る（読むだけ） ----
pub struct 一覧を見る入力 {
    pub 件数: u64,
}
impl 一覧を見る入力 {
    pub fn 検査(&self) -> Result<(), String> {
        範囲検査("件数", self.件数 as i128, Some(1), None)?;
        Ok(())
    }
}
pub struct 一覧を見る文脈 {
}
pub fn 一覧を見る(ctx: &一覧を見る文脈, 保存: &保存, 入力: &一覧を見る入力) -> Vec<String> {
    let mut 行: Vec<&投稿> = 保存.投稿.values().filter(|r| {
        if !(r.状態 == 投稿状態::投稿済) { return false; }
        true
    }).collect();
    行.sort_by(|a, b| b.書いた日時.cmp(&a.書いた日時).then(b.投稿ID.cmp(&a.投稿ID)));
    行.truncate(入力.件数 as usize);
    行.into_iter().map(|r| r.投稿ID.clone()).collect()
}

// ---- 問い合わせ 探す（読むだけ） ----
pub struct 探す入力 {
    pub 始め: Option<i64>,
    pub 終わり: Option<i64>,
    pub 単語: Option<String>,
}
impl 探す入力 {
    pub fn 検査(&self) -> Result<(), String> {
        Ok(())
    }
}
pub struct 探す文脈 {
}
pub fn 探す(ctx: &探す文脈, 保存: &保存, 入力: &探す入力) -> Vec<String> {
    let mut 行: Vec<&投稿> = 保存.投稿.values().filter(|r| {
        if !(r.状態 == 投稿状態::投稿済) { return false; }
        if let Some(x) = &入力.始め { if !(r.書いた日時 >= *x) { return false; } }
        if let Some(x) = &入力.終わり { if !(r.書いた日時 <= *x) { return false; } }
        if let Some(x) = &入力.単語 { if !(r.本文.contains(x.as_str())) { return false; } }
        true
    }).collect();
    行.sort_by(|a, b| b.書いた日時.cmp(&a.書いた日時).then(b.投稿ID.cmp(&a.投稿ID)));
    行.into_iter().map(|r| r.投稿ID.clone()).collect()
}

// ---- 問い合わせ 圏外で見る（読むだけ） ----
pub struct 圏外で見る入力 {
    pub 件数: u64,
}
impl 圏外で見る入力 {
    pub fn 検査(&self) -> Result<(), String> {
        範囲検査("件数", self.件数 as i128, Some(1), None)?;
        Ok(())
    }
}
pub struct 圏外で見る文脈 {
    pub 現在: i64,
}
pub fn 圏外で見る(ctx: &圏外で見る文脈, 保存: &保存, 入力: &圏外で見る入力) -> Vec<String> {
    let mut 行: Vec<&投稿> = 保存.投稿.values().filter(|r| {
        if !(r.状態 == 投稿状態::投稿済) { return false; }
        if !(r.書いた日時 >= ctx.現在 - 86400) { return false; }
        true
    }).collect();
    行.sort_by(|a, b| b.書いた日時.cmp(&a.書いた日時).then(b.投稿ID.cmp(&a.投稿ID)));
    行.truncate(入力.件数 as usize);
    行.into_iter().map(|r| r.投稿ID.clone()).collect()
}

// ---- 問い合わせ 未反映の投稿（読むだけ） ----
pub struct 未反映の投稿入力 {
}
impl 未反映の投稿入力 {
    pub fn 検査(&self) -> Result<(), String> {
        Ok(())
    }
}
pub struct 未反映の投稿文脈 {
}
pub fn 未反映の投稿(ctx: &未反映の投稿文脈, 保存: &保存, 入力: &未反映の投稿入力) -> Vec<String> {
    let mut 行: Vec<&投稿> = 保存.投稿.values().filter(|r| {
        if !(r.状態 == 投稿状態::投稿済) { return false; }
        if !(r.記録 == 記録状態::端末保存済) { return false; }
        true
    }).collect();
    行.sort_by(|a, b| a.書いた日時.cmp(&b.書いた日時).then(a.投稿ID.cmp(&b.投稿ID)));
    行.into_iter().map(|r| r.投稿ID.clone()).collect()
}

// 【フロー】：結果の種類ごとの行き先。match の網羅は Rust が検査する。
pub fn 実体_添付する(r: &添付結果) -> 行き先 {
    match r {
        添付結果::添付済(..) => 行き先::応答,
    }
}

pub fn 実体_リンクを付ける(r: &リンク結果) -> 行き先 {
    match r {
        リンク結果::付けた(..) => 行き先::応答,
    }
}

pub fn 実体_添付の取り込み(r: &実体の取り込み結果) -> 行き先 {
    match r {
        実体の取り込み結果::取り込んだ => 行き先::応答,
    }
}

pub fn 実体_リンクの取り込み(r: &実体の取り込み結果) -> 行き先 {
    match r {
        実体の取り込み結果::取り込んだ => 行き先::応答,
    }
}

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
        直す結果::直した => 行き先::処理("未反映に戻す"),
        直す結果::投稿なし => 行き先::応答,
        直す結果::空 => 行き先::応答,
        直す結果::状態違い => 行き先::応答,
    }
}

pub fn 直す_未反映に戻す(r: &巻き戻し結果) -> 行き先 {
    match r {
        巻き戻し結果::巻き戻した => 行き先::処理("反映の要求"),
        巻き戻し結果::不要 => 行き先::処理("反映の要求"),
        巻き戻し結果::投稿なし => 行き先::応答,
    }
}

pub fn 別端末の操作_投稿の取り込み(r: &新規取り込み結果) -> 行き先 {
    match r {
        新規取り込み結果::取り込んだ => 行き先::応答,
    }
}

pub fn 別端末の操作_直しの取り込み(r: &取り込み結果) -> 行き先 {
    match r {
        取り込み結果::取り込んだ => 行き先::応答,
        取り込み結果::古い => 行き先::応答,
        取り込み結果::削除済 => 行き先::処理("直しで戻す"),
        取り込み結果::投稿なし => 行き先::応答,
    }
}

pub fn 別端末の操作_直しで戻す(r: &戻す取り込み結果) -> 行き先 {
    match r {
        戻す取り込み結果::取り込んだ => 行き先::応答,
        戻す取り込み結果::古い => 行き先::応答,
        戻す取り込み結果::状態違い => 行き先::応答,
        戻す取り込み結果::投稿なし => 行き先::応答,
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


pub mod host;
