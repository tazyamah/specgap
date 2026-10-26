// 自動生成。手で編集しない。
#![allow(non_snake_case, non_camel_case_types, dead_code, unused_variables, unused_mut)]
use crate::*;
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Debug)]
pub enum J { Null, Bool(bool), Num(i128), Str(String), Arr(Vec<J>), Obj(BTreeMap<String, J>) }

impl J {
    pub fn get(&self, k: &str) -> Result<&J, String> {
        match self { J::Obj(m) => m.get(k).ok_or_else(|| format!("項目「{}」がありません", k)), _ => Err("オブジェクトではありません".into()) }
    }
    pub fn get_opt(&self, k: &str) -> Option<&J> {
        match self { J::Obj(m) => match m.get(k) { Some(J::Null) | None => None, Some(x) => Some(x) }, _ => None }
    }
    pub fn as_str(&self) -> Result<&str, String> { match self { J::Str(s) => Ok(s), _ => Err("文字列のはずです".into()) } }
    pub fn as_int(&self) -> Result<i128, String> { match self { J::Num(n) => Ok(*n), _ => Err("整数のはずです".into()) } }
    pub fn as_obj(&self) -> Result<&BTreeMap<String, J>, String> { match self { J::Obj(m) => Ok(m), _ => Err("オブジェクトのはずです".into()) } }
    pub fn as_set(&self) -> Result<BTreeSet<String>, String> {
        match self { J::Arr(a) => a.iter().map(|x| x.as_str().map(|s| s.to_string())).collect(), _ => Err("配列のはずです".into()) }
    }
}

struct P<'a> { s: &'a [u8], i: usize }
impl<'a> P<'a> {
    fn ws(&mut self) { while self.i < self.s.len() && (self.s[self.i] as char).is_whitespace() { self.i += 1; } }
    fn eat(&mut self, c: u8) -> Result<(), String> { self.ws(); if self.i < self.s.len() && self.s[self.i] == c { self.i += 1; Ok(()) } else { Err(format!("JSON: '{}' が必要です（{}文字目）", c as char, self.i)) } }
    fn value(&mut self) -> Result<J, String> {
        self.ws();
        if self.i >= self.s.len() { return Err("JSON: 途中で終わっています".into()); }
        match self.s[self.i] {
            b'{' => { self.i += 1; let mut m = BTreeMap::new(); self.ws();
                if self.s[self.i] == b'}' { self.i += 1; return Ok(J::Obj(m)); }
                loop { let k = match self.value()? { J::Str(s) => s, _ => return Err("JSON: キーは文字列です".into()) }; self.eat(b':')?; let v = self.value()?; m.insert(k, v); self.ws();
                    if self.s[self.i] == b',' { self.i += 1; } else { self.eat(b'}')?; return Ok(J::Obj(m)); } } }
            b'[' => { self.i += 1; let mut a = Vec::new(); self.ws();
                if self.s[self.i] == b']' { self.i += 1; return Ok(J::Arr(a)); }
                loop { a.push(self.value()?); self.ws(); if self.s[self.i] == b',' { self.i += 1; } else { self.eat(b']')?; return Ok(J::Arr(a)); } } }
            b'"' => { self.i += 1; let mut out: Vec<u8> = Vec::new();
                loop { if self.i >= self.s.len() { return Err("JSON: 文字列が閉じていません".into()); } let c = self.s[self.i]; self.i += 1;
                    match c { b'"' => break, b'\\' => { let e = self.s[self.i]; self.i += 1;
                        match e { b'n' => out.push(b'\n'), b't' => out.push(b'\t'), b'r' => out.push(b'\r'), b'b' => out.push(8), b'f' => out.push(12),
                            b'u' => { let h = std::str::from_utf8(&self.s[self.i..self.i + 4]).map_err(|_| "JSON: \\u".to_string())?; let mut cp = u32::from_str_radix(h, 16).map_err(|_| "JSON: \\u".to_string())?; self.i += 4;
                                if (0xD800..0xDC00).contains(&cp) && self.s.get(self.i) == Some(&b'\\') && self.s.get(self.i + 1) == Some(&b'u') {
                                    let h2 = std::str::from_utf8(&self.s[self.i + 2..self.i + 6]).map_err(|_| "JSON: \\u".to_string())?; let lo = u32::from_str_radix(h2, 16).map_err(|_| "JSON: \\u".to_string())?; self.i += 6;
                                    cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00); }
                                let ch = char::from_u32(cp).unwrap_or('\u{FFFD}'); let mut b = [0u8; 4]; out.extend_from_slice(ch.encode_utf8(&mut b).as_bytes()); }
                            x => out.push(x) } }
                        x => out.push(x) } }
                Ok(J::Str(String::from_utf8(out).map_err(|_| "JSON: UTF-8 でありません".to_string())?)) }
            b't' => { self.i += 4; Ok(J::Bool(true)) }
            b'f' => { self.i += 5; Ok(J::Bool(false)) }
            b'n' => { self.i += 4; Ok(J::Null) }
            _ => { let st = self.i; if self.s[self.i] == b'-' { self.i += 1; } while self.i < self.s.len() && (self.s[self.i] as char).is_ascii_digit() { self.i += 1; }
                std::str::from_utf8(&self.s[st..self.i]).unwrap().parse::<i128>().map(J::Num).map_err(|_| format!("JSON: 数が読めません（{}文字目）", st)) }
        }
    }
}
pub fn parse(s: &str) -> Result<J, String> { let mut p = P { s: s.as_bytes(), i: 0 }; let v = p.value()?; Ok(v) }

pub fn js_str(s: &str) -> String {
    let mut o = String::from("\"");
    for c in s.chars() { match c { '"' => o.push_str("\\\""), '\\' => o.push_str("\\\\"), '\n' => o.push_str("\\n"), '\r' => o.push_str("\\r"), '\t' => o.push_str("\\t"),
        c if (c as u32) < 0x20 => o.push_str(&format!("\\u{:04x}", c as u32)), c => o.push(c) } }
    o.push('"'); o
}
pub fn js_set(s: &BTreeSet<String>) -> String { format!("[{}]", s.iter().map(|x| js_str(x)).collect::<Vec<_>>().join(",")) }
pub fn js_arr(v: &[String]) -> String { format!("[{}]", v.iter().map(|x| js_str(x)).collect::<Vec<_>>().join(",")) }

fn 投稿_から(j: &J) -> Result<投稿, String> {
    Ok(投稿 {
        投稿ID: j.get("投稿ID")?.as_str()?.to_string(),
        本文: j.get("本文")?.as_str()?.to_string(),
        添付: j.get("添付")?.as_set()?,
        リンク: j.get("リンク")?.as_set()?,
        書いた日時: (j.get("書いた日時")?.as_int()? as i64),
        最後に操作した日時: (j.get("最後に操作した日時")?.as_int()? as i64),
        状態: 投稿状態::名前から(j.get("状態")?.as_str()?).ok_or_else(|| "未知の状態です".to_string())?,
        記録: 記録状態::名前から(j.get("記録")?.as_str()?).ok_or_else(|| "未知の状態です".to_string())?,
    })
}
fn 投稿_へ(r: &投稿) -> String {
    let mut v: Vec<String> = Vec::new();
    v.push(format!("{}:{}", js_str("投稿ID"), js_str(&r.投稿ID)));
    v.push(format!("{}:{}", js_str("本文"), js_str(&r.本文)));
    v.push(format!("{}:{}", js_str("添付"), js_set(&r.添付)));
    v.push(format!("{}:{}", js_str("リンク"), js_set(&r.リンク)));
    v.push(format!("{}:{}", js_str("書いた日時"), r.書いた日時.to_string()));
    v.push(format!("{}:{}", js_str("最後に操作した日時"), r.最後に操作した日時.to_string()));
    v.push(format!("{}:{}", js_str("状態"), js_str(r.状態.名前())));
    v.push(format!("{}:{}", js_str("記録"), js_str(r.記録.名前())));
    format!("{{{}}}", v.join(","))
}
pub fn 保存を読む(j: &J) -> Result<保存, String> {
    let mut s = 保存::default();
    if let Some(m) = j.get_opt("投稿") { for (k, v) in m.as_obj()? { s.投稿.insert(k.clone(), 投稿_から(v)?); } }
    Ok(s)
}
pub fn 保存を書く(s: &保存) -> String {
    let mut v: Vec<String> = Vec::new();
    v.push(format!("{}:{{{}}}", js_str("投稿"), s.投稿.iter().map(|(k, r)| format!("{}:{}", js_str(k), 投稿_へ(r))).collect::<Vec<_>>().join(",")));
    format!("{{{}}}", v.join(","))
}
fn 外部を書く(e: &外部作用) -> String {
    match e {
        外部作用::Dropbox_書く { 投稿ID, 本文, 冪等キー } => format!("{{\"名前\":{},\"引数\":{{{}:{},{}:{}}},\"冪等キー\":{}}}", js_str("Dropbox.書く"), js_str("投稿ID"), js_str(&投稿ID), js_str("本文"), js_str(&本文), js_str(冪等キー)),
        外部作用::Dropbox_消す { 投稿ID, 冪等キー } => format!("{{\"名前\":{},\"引数\":{{{}:{}}},\"冪等キー\":{}}}", js_str("Dropbox.消す"), js_str("投稿ID"), js_str(&投稿ID), js_str(冪等キー)),
    }
}
fn 結果を書く(名前: &str, 引数: Vec<String>, 外部: Vec<String>, 保存: &保存) -> String {
    format!("{{\"結果\":{},\"引数\":{},\"外部\":[{}],\"保存\":{}}}", js_str(名前), js_arr(&引数), 外部.join(","), 保存を書く(保存))
}
fn 呼ぶ内部(名前: &str, ctx: &J, 入力: &J, 保存: &mut 保存) -> Result<String, String> {
    match 名前 {
        "投稿する" => {
            let c = 投稿する文脈 { 現在: (ctx.get("現在")?.as_int()? as i64), 新投稿ID: ctx.get("新投稿ID")?.as_str()?.to_string() };
            let i = 投稿する入力 { 本文: 入力.get("本文")?.as_str()?.to_string(), 添付: 入力.get("添付")?.as_set()?, リンク: 入力.get("リンク")?.as_set()? };
            i.検査()?;
            let o = 投稿する(&c, 保存, &i);
            保存.適用(o.書込.clone());
            Ok(結果を書く(o.結果.名前(), o.結果.引数(), o.外部.iter().map(外部を書く).collect(), 保存))
        }
        "反映の要求" => {
            let c = 反映の要求文脈 {  };
            let i = 反映の要求入力 { 投稿ID: 入力.get("投稿ID")?.as_str()?.to_string() };
            i.検査()?;
            let o = 反映の要求(&c, 保存, &i);
            保存.適用(o.書込.clone());
            Ok(結果を書く(o.結果.名前(), o.結果.引数(), o.外部.iter().map(外部を書く).collect(), 保存))
        }
        "記録の確定" => {
            let c = 記録の確定文脈 {  };
            let i = 記録の確定入力 { 投稿ID: 入力.get("投稿ID")?.as_str()?.to_string() };
            i.検査()?;
            let o = 記録の確定(&c, 保存, &i);
            保存.適用(o.書込.clone());
            Ok(結果を書く(o.結果.名前(), o.結果.引数(), o.外部.iter().map(外部を書く).collect(), 保存))
        }
        "記録失敗の表示" => {
            let c = 記録失敗の表示文脈 {  };
            let i = 記録失敗の表示入力 { 投稿ID: 入力.get("投稿ID")?.as_str()?.to_string() };
            i.検査()?;
            let o = 記録失敗の表示(&c, 保存, &i);
            保存.適用(o.書込.clone());
            Ok(結果を書く(o.結果.名前(), o.結果.引数(), o.外部.iter().map(外部を書く).collect(), 保存))
        }
        "未反映の通知" => {
            let c = 未反映の通知文脈 {  };
            let i = 未反映の通知入力 { 投稿ID: 入力.get("投稿ID")?.as_str()?.to_string() };
            i.検査()?;
            let o = 未反映の通知(&c, 保存, &i);
            保存.適用(o.書込.clone());
            Ok(結果を書く(o.結果.名前(), o.結果.引数(), o.外部.iter().map(外部を書く).collect(), 保存))
        }
        "直す" => {
            let c = 直す文脈 { 現在: (ctx.get("現在")?.as_int()? as i64) };
            let i = 直す入力 { 投稿ID: 入力.get("投稿ID")?.as_str()?.to_string(), 本文: 入力.get("本文")?.as_str()?.to_string(), 添付: 入力.get("添付")?.as_set()?, リンク: 入力.get("リンク")?.as_set()? };
            i.検査()?;
            let o = 直す(&c, 保存, &i);
            保存.適用(o.書込.clone());
            Ok(結果を書く(o.結果.名前(), o.結果.引数(), o.外部.iter().map(外部を書く).collect(), 保存))
        }
        "投稿の取り込み" => {
            let c = 投稿の取り込み文脈 { 新投稿ID: ctx.get("新投稿ID")?.as_str()?.to_string() };
            let i = 投稿の取り込み入力 { 本文: 入力.get("本文")?.as_str()?.to_string(), 添付: 入力.get("添付")?.as_set()?, リンク: 入力.get("リンク")?.as_set()?, 書いた日時: (入力.get("書いた日時")?.as_int()? as i64), 操作日時: (入力.get("操作日時")?.as_int()? as i64) };
            i.検査()?;
            let o = 投稿の取り込み(&c, 保存, &i);
            保存.適用(o.書込.clone());
            Ok(結果を書く(o.結果.名前(), o.結果.引数(), o.外部.iter().map(外部を書く).collect(), 保存))
        }
        "直しの取り込み" => {
            let c = 直しの取り込み文脈 {  };
            let i = 直しの取り込み入力 { 投稿ID: 入力.get("投稿ID")?.as_str()?.to_string(), 直し日時: (入力.get("直し日時")?.as_int()? as i64), 本文: 入力.get("本文")?.as_str()?.to_string() };
            i.検査()?;
            let o = 直しの取り込み(&c, 保存, &i);
            保存.適用(o.書込.clone());
            Ok(結果を書く(o.結果.名前(), o.結果.引数(), o.外部.iter().map(外部を書く).collect(), 保存))
        }
        "消す" => {
            let c = 消す文脈 { 現在: (ctx.get("現在")?.as_int()? as i64) };
            let i = 消す入力 { 投稿ID: 入力.get("投稿ID")?.as_str()?.to_string() };
            i.検査()?;
            let o = 消す(&c, 保存, &i);
            保存.適用(o.書込.clone());
            Ok(結果を書く(o.結果.名前(), o.結果.引数(), o.外部.iter().map(外部を書く).collect(), 保存))
        }
        "直しで戻す" => {
            let c = 直しで戻す文脈 {  };
            let i = 直しで戻す入力 { 投稿ID: 入力.get("投稿ID")?.as_str()?.to_string(), 直し日時: (入力.get("直し日時")?.as_int()? as i64), 本文: 入力.get("本文")?.as_str()?.to_string() };
            i.検査()?;
            let o = 直しで戻す(&c, 保存, &i);
            保存.適用(o.書込.clone());
            Ok(結果を書く(o.結果.名前(), o.結果.引数(), o.外部.iter().map(外部を書く).collect(), 保存))
        }
        "消しの取り込み" => {
            let c = 消しの取り込み文脈 {  };
            let i = 消しの取り込み入力 { 投稿ID: 入力.get("投稿ID")?.as_str()?.to_string(), 操作日時: (入力.get("操作日時")?.as_int()? as i64) };
            i.検査()?;
            let o = 消しの取り込み(&c, 保存, &i);
            保存.適用(o.書込.clone());
            Ok(結果を書く(o.結果.名前(), o.結果.引数(), o.外部.iter().map(外部を書く).collect(), 保存))
        }
        "元に戻す" => {
            let c = 元に戻す文脈 { 現在: (ctx.get("現在")?.as_int()? as i64) };
            let i = 元に戻す入力 { 投稿ID: 入力.get("投稿ID")?.as_str()?.to_string() };
            i.検査()?;
            let o = 元に戻す(&c, 保存, &i);
            保存.適用(o.書込.clone());
            Ok(結果を書く(o.結果.名前(), o.結果.引数(), o.外部.iter().map(外部を書く).collect(), 保存))
        }
        "完全に消す" => {
            let c = 完全に消す文脈 {  };
            let i = 完全に消す入力 { 投稿ID: 入力.get("投稿ID")?.as_str()?.to_string() };
            i.検査()?;
            let o = 完全に消す(&c, 保存, &i);
            保存.適用(o.書込.clone());
            Ok(結果を書く(o.結果.名前(), o.結果.引数(), o.外部.iter().map(外部を書く).collect(), 保存))
        }
        "一覧を見る" => {
            let c = 一覧を見る文脈 {  };
            let i = 一覧を見る入力 { 件数: u64::try_from(入力.get("件数")?.as_int()?).map_err(|_| "範囲外の数です".to_string())? };
            i.検査()?;
            Ok(結果を書く("一覧", 一覧を見る(&c, 保存, &i), vec![], 保存))
        }
        "探す" => {
            let c = 探す文脈 {  };
            let i = 探す入力 { 始め: match 入力.get_opt("始め") { Some(v) => Some((v.as_int()? as i64)), None => None }, 終わり: match 入力.get_opt("終わり") { Some(v) => Some((v.as_int()? as i64)), None => None }, 単語: match 入力.get_opt("単語") { Some(v) => Some(v.as_str()?.to_string()), None => None } };
            i.検査()?;
            Ok(結果を書く("一覧", 探す(&c, 保存, &i), vec![], 保存))
        }
        "圏外で見る" => {
            let c = 圏外で見る文脈 { 現在: (ctx.get("現在")?.as_int()? as i64) };
            let i = 圏外で見る入力 { 件数: u64::try_from(入力.get("件数")?.as_int()?).map_err(|_| "範囲外の数です".to_string())? };
            i.検査()?;
            Ok(結果を書く("一覧", 圏外で見る(&c, 保存, &i), vec![], 保存))
        }
        _ => Err(format!("処理「{}」はありません", 名前)),
    }
}
pub fn 呼ぶ(要求: &str) -> Result<String, String> {
    let r = parse(要求)?;
    let mut s = 保存を読む(r.get("保存")?)?;
    呼ぶ内部(r.get("名前")?.as_str()?, r.get("文脈")?, r.get("入力")?, &mut s)
}
pub const 定義JSON: &str = r####"{"処理":{"投稿する":{"入力":["本文","添付","リンク"],"参照":["現在"],"採番":["投稿"]},"反映の要求":{"入力":["投稿ID"],"参照":[],"採番":[]},"記録の確定":{"入力":["投稿ID"],"参照":[],"採番":[]},"記録失敗の表示":{"入力":["投稿ID"],"参照":[],"採番":[]},"未反映の通知":{"入力":["投稿ID"],"参照":[],"採番":[]},"直す":{"入力":["投稿ID","本文","添付","リンク"],"参照":["現在"],"採番":[]},"投稿の取り込み":{"入力":["本文","添付","リンク","書いた日時","操作日時"],"参照":[],"採番":["投稿"]},"直しの取り込み":{"入力":["投稿ID","直し日時","本文"],"参照":[],"採番":[]},"消す":{"入力":["投稿ID"],"参照":["現在"],"採番":[]},"直しで戻す":{"入力":["投稿ID","直し日時","本文"],"参照":[],"採番":[]},"消しの取り込み":{"入力":["投稿ID","操作日時"],"参照":[],"採番":[]},"元に戻す":{"入力":["投稿ID"],"参照":["現在"],"採番":[]},"完全に消す":{"入力":["投稿ID"],"参照":[],"採番":[]}},"問い合わせ":{"一覧を見る":{"入力":["件数"],"参照":[]},"探す":{"入力":["始め","終わり","単語"],"参照":[]},"圏外で見る":{"入力":["件数"],"参照":["現在"]}},"フロー":{"投稿する":{"端末保存済":"反映の要求","空":"応答"},"反映の要求":{"要求済":"待つ 書込待ち","投稿なし":"応答","状態違い":"応答"},"記録の確定":{"確定済":"応答","投稿なし":"応答","状態違い":"応答"},"記録失敗の表示":{"表示した":"応答","投稿なし":"応答"},"未反映の通知":{"通知済":"待つ 書込待ち","投稿なし":"応答","状態違い":"応答"},"直す":{"直した":"反映の要求","投稿なし":"応答","空":"応答","状態違い":"応答"},"投稿の取り込み":{"取り込んだ":"応答"},"直しの取り込み":{"取り込んだ":"応答","古い":"応答","削除済":"直しで戻す","投稿なし":"応答"},"直しで戻す":{"取り込んだ":"応答","古い":"応答","状態違い":"応答","投稿なし":"応答"},"消しの取り込み":{"取り込んだ":"応答","古い":"応答","状態違い":"応答","投稿なし":"応答"},"消す":{"削除済":"待つ 削除猶予","投稿なし":"応答","状態違い":"応答"},"元に戻す":{"戻した":"応答","投稿なし":"応答","状態違い":"応答"},"完全に消す":{"消した":"応答","投稿なし":"応答","状態違い":"応答"}},"トリガ":[{"名前":"書込待ち","引数":["投稿ID"],"要因":[{"種別":"応答","キー":"書込成功","秒":null,"行き先":"記録の確定"},{"種別":"応答","キー":"書込失敗","秒":null,"行き先":"記録失敗の表示"},{"種別":"期限","キー":"86400","秒":86400,"行き先":"未反映の通知"}]},{"名前":"削除猶予","引数":["投稿ID"],"要因":[{"種別":"応答","キー":"元に戻す","秒":null,"行き先":"元に戻す"},{"種別":"期限","キー":"30","秒":30,"行き先":"完全に消す"}]}]}"####;

fn 返す(s: String) -> u64 {
    let b = s.into_bytes().into_boxed_slice();
    let l = b.len();
    let p = Box::into_raw(b) as *mut u8;
    ((p as u64) << 32) | (l as u64)
}
#[no_mangle]
pub extern "C" fn alloc(n: usize) -> *mut u8 { let mut v = Vec::<u8>::with_capacity(n); let p = v.as_mut_ptr(); std::mem::forget(v); p }
#[no_mangle]
pub extern "C" fn dealloc(p: *mut u8, n: usize) { unsafe { drop(Vec::from_raw_parts(p, 0, n)); } }
#[no_mangle]
pub extern "C" fn specgap_call(ptr: *const u8, len: usize) -> u64 {
    let s = unsafe { std::str::from_utf8_unchecked(std::slice::from_raw_parts(ptr, len)) };
    返す(match 呼ぶ(s) { Ok(x) => x, Err(e) => format!("{{\"エラー\":{}}}", js_str(&e)) })
}
#[no_mangle]
pub extern "C" fn specgap_defs() -> u64 { 返す(定義JSON.to_string()) }

