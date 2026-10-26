use specgap_app::*;
use std::collections::{BTreeMap, BTreeSet};

#[allow(unused_mut, non_snake_case, unused_variables)]
fn main() {
    {
        let mut 保存 = 保存::default();
        let ctx = 投稿する文脈 { 現在: 1000i64, 新投稿ID: "N1".to_string() };
        let 入力 = 投稿する入力 { 本文: "図書館で本を借りた".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]) };
        match 入力.検査() {
            Err(e) => println!("EX1\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 投稿する(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX1\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        let ctx = 投稿する文脈 { 現在: 1000i64, 新投稿ID: "N1".to_string() };
        let 入力 = 投稿する入力 { 本文: "夕焼けの写真".to_string(), 添付: BTreeSet::from(["画像1".to_string()]), リンク: BTreeSet::from([]) };
        match 入力.検査() {
            Err(e) => println!("EX2\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 投稿する(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX2\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        let ctx = 投稿する文脈 { 現在: 1000i64, 新投稿ID: "N1".to_string() };
        let 入力 = 投稿する入力 { 本文: "".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]) };
        match 入力.検査() {
            Err(e) => println!("EX3\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 投稿する(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX3\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "図書館で本を借りた".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::端末保存済 });
        let ctx = 反映の要求文脈 {  };
        let 入力 = 反映の要求入力 { 投稿ID: "N1".to_string() };
        match 入力.検査() {
            Err(e) => println!("EX4\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 反映の要求(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX4\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "消した投稿".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::削除済, 記録: 記録状態::端末保存済 });
        let ctx = 反映の要求文脈 {  };
        let 入力 = 反映の要求入力 { 投稿ID: "N1".to_string() };
        match 入力.検査() {
            Err(e) => println!("EX5\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 反映の要求(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX5\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "図書館で本を借りた".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::端末保存済 });
        let ctx = 記録の確定文脈 {  };
        let 入力 = 記録の確定入力 { 投稿ID: "N1".to_string() };
        match 入力.検査() {
            Err(e) => println!("EX6\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 記録の確定(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX6\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "直した後の確定".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1100i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        let ctx = 記録の確定文脈 {  };
        let 入力 = 記録の確定入力 { 投稿ID: "N1".to_string() };
        match 入力.検査() {
            Err(e) => println!("EX7\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 記録の確定(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX7\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "保存できない".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::端末保存済 });
        let ctx = 記録失敗の表示文脈 {  };
        let 入力 = 記録失敗の表示入力 { 投稿ID: "N1".to_string() };
        match 入力.検査() {
            Err(e) => println!("EX8\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 記録失敗の表示(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX8\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "電車で書いた".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::端末保存済 });
        let ctx = 未反映の通知文脈 {  };
        let 入力 = 未反映の通知入力 { 投稿ID: "N1".to_string() };
        match 入力.検査() {
            Err(e) => println!("EX9\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 未反映の通知(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX9\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "もう記録済".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        let ctx = 未反映の通知文脈 {  };
        let 入力 = 未反映の通知入力 { 投稿ID: "N1".to_string() };
        match 入力.検査() {
            Err(e) => println!("EX10\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 未反映の通知(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX10\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "ばなな".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        let ctx = 直す文脈 { 現在: 2000i64 };
        let 入力 = 直す入力 { 投稿ID: "N1".to_string(), 本文: "バナナ".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]) };
        match 入力.検査() {
            Err(e) => println!("EX11\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 直す(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX11\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "ばなな".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        let ctx = 直す文脈 { 現在: 2000i64 };
        let 入力 = 直す入力 { 投稿ID: "N1".to_string(), 本文: "".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]) };
        match 入力.検査() {
            Err(e) => println!("EX12\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 直す(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX12\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "消した投稿".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::削除済, 記録: 記録状態::記録済 });
        let ctx = 直す文脈 { 現在: 2000i64 };
        let 入力 = 直す入力 { 投稿ID: "N1".to_string(), 本文: "直したい".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]) };
        match 入力.検査() {
            Err(e) => println!("EX13\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 直す(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX13\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "B".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        let ctx = 直しの取り込み文脈 {  };
        let 入力 = 直しの取り込み入力 { 投稿ID: "N1".to_string(), 直し日時: 1300i64, 本文: "C".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]) };
        match 入力.検査() {
            Err(e) => println!("EX14\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 直しの取り込み(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX14\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "C".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1300i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        let ctx = 直しの取り込み文脈 {  };
        let 入力 = 直しの取り込み入力 { 投稿ID: "N1".to_string(), 直し日時: 1200i64, 本文: "B".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]) };
        match 入力.検査() {
            Err(e) => println!("EX15\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 直しの取り込み(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX15\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "書いた".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        let ctx = 消す文脈 { 現在: 3000i64 };
        let 入力 = 消す入力 { 投稿ID: "N1".to_string() };
        match 入力.検査() {
            Err(e) => println!("EX16\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 消す(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX16\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "書いた".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::端末保存済 });
        let ctx = 消す文脈 { 現在: 3000i64 };
        let 入力 = 消す入力 { 投稿ID: "N1".to_string() };
        match 入力.検査() {
            Err(e) => println!("EX17\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 消す(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX17\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "書いた".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::削除済, 記録: 記録状態::記録済 });
        let ctx = 元に戻す文脈 { 現在: 3000i64 };
        let 入力 = 元に戻す入力 { 投稿ID: "N1".to_string() };
        match 入力.検査() {
            Err(e) => println!("EX18\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 元に戻す(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX18\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "書いた".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::完全削除済, 記録: 記録状態::記録済 });
        let ctx = 元に戻す文脈 { 現在: 3000i64 };
        let 入力 = 元に戻す入力 { 投稿ID: "N1".to_string() };
        match 入力.検査() {
            Err(e) => println!("EX19\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 元に戻す(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX19\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "書いた".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::削除済, 記録: 記録状態::記録済 });
        let ctx = 完全に消す文脈 {  };
        let 入力 = 完全に消す入力 { 投稿ID: "N1".to_string() };
        match 入力.検査() {
            Err(e) => println!("EX20\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 完全に消す(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX20\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "書いた".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        let ctx = 消しの取り込み文脈 {  };
        let 入力 = 消しの取り込み入力 { 投稿ID: "N1".to_string(), 操作日時: 1400i64 };
        match 入力.検査() {
            Err(e) => println!("EX21\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 消しの取り込み(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX21\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "直した".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1500i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        let ctx = 消しの取り込み文脈 {  };
        let 入力 = 消しの取り込み入力 { 投稿ID: "N1".to_string(), 操作日時: 1400i64 };
        match 入力.検査() {
            Err(e) => println!("EX22\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 消しの取り込み(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX22\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "書いた".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::削除済, 記録: 記録状態::記録済 });
        let ctx = 消しの取り込み文脈 {  };
        let 入力 = 消しの取り込み入力 { 投稿ID: "N1".to_string(), 操作日時: 1400i64 };
        match 入力.検査() {
            Err(e) => println!("EX23\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 消しの取り込み(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX23\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "書いた".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::削除済, 記録: 記録状態::記録済 });
        let ctx = 直しの取り込み文脈 {  };
        let 入力 = 直しの取り込み入力 { 投稿ID: "N1".to_string(), 直し日時: 1600i64, 本文: "直した".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]) };
        match 入力.検査() {
            Err(e) => println!("EX24\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 直しの取り込み(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX24\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "書いた".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::削除済, 記録: 記録状態::記録済 });
        let ctx = 直しで戻す文脈 {  };
        let 入力 = 直しで戻す入力 { 投稿ID: "N1".to_string(), 直し日時: 1600i64, 本文: "直した".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]) };
        match 入力.検査() {
            Err(e) => println!("EX25\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 直しで戻す(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX25\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "書いた".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1800i64, 状態: 投稿状態::削除済, 記録: 記録状態::記録済 });
        let ctx = 直しで戻す文脈 {  };
        let 入力 = 直しで戻す入力 { 投稿ID: "N1".to_string(), 直し日時: 1600i64, 本文: "直した".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]) };
        match 入力.検査() {
            Err(e) => println!("EX26\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 直しで戻す(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX26\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "投稿1".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N2".to_string(), 投稿 { 投稿ID: "N2".to_string(), 本文: "投稿2".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 2000i64, 最後に操作した日時: 2000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N3".to_string(), 投稿 { 投稿ID: "N3".to_string(), 本文: "投稿3".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 3000i64, 最後に操作した日時: 3000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N4".to_string(), 投稿 { 投稿ID: "N4".to_string(), 本文: "投稿4".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 4000i64, 最後に操作した日時: 4000i64, 状態: 投稿状態::削除済, 記録: 記録状態::記録済 });
        let ctx = 一覧を見る文脈 {  };
        let 入力 = 一覧を見る入力 { 件数: 2u64 };
        match 入力.検査() {
            Err(e) => println!("EX27\t入力不正({})\t\t", e),
            Ok(()) => println!("EX27\t一覧({})\t\t", 一覧を見る(&ctx, &保存, &入力).join(",")),
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "投稿1".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N2".to_string(), 投稿 { 投稿ID: "N2".to_string(), 本文: "投稿2".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 2000i64, 最後に操作した日時: 2000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N3".to_string(), 投稿 { 投稿ID: "N3".to_string(), 本文: "投稿3".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 3000i64, 最後に操作した日時: 3000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N4".to_string(), 投稿 { 投稿ID: "N4".to_string(), 本文: "投稿4".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 4000i64, 最後に操作した日時: 4000i64, 状態: 投稿状態::削除済, 記録: 記録状態::記録済 });
        let ctx = 一覧を見る文脈 {  };
        let 入力 = 一覧を見る入力 { 件数: 5u64 };
        match 入力.検査() {
            Err(e) => println!("EX28\t入力不正({})\t\t", e),
            Ok(()) => println!("EX28\t一覧({})\t\t", 一覧を見る(&ctx, &保存, &入力).join(",")),
        }
    }
    {
        let mut 保存 = 保存::default();
        let ctx = 一覧を見る文脈 {  };
        let 入力 = 一覧を見る入力 { 件数: 5u64 };
        match 入力.検査() {
            Err(e) => println!("EX29\t入力不正({})\t\t", e),
            Ok(()) => println!("EX29\t一覧({})\t\t", 一覧を見る(&ctx, &保存, &入力).join(",")),
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "xxxを買った".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N2".to_string(), 投稿 { 投稿ID: "N2".to_string(), 本文: "病院".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 2000i64, 最後に操作した日時: 2000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N3".to_string(), 投稿 { 投稿ID: "N3".to_string(), 本文: "xxxの件".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 3000i64, 最後に操作した日時: 3000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N4".to_string(), 投稿 { 投稿ID: "N4".to_string(), 本文: "xxx消した".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 4000i64, 最後に操作した日時: 4000i64, 状態: 投稿状態::削除済, 記録: 記録状態::記録済 });
        let ctx = 探す文脈 {  };
        let 入力 = 探す入力 { 始め: None, 終わり: None, 単語: Some("xxx".to_string()) };
        match 入力.検査() {
            Err(e) => println!("EX30\t入力不正({})\t\t", e),
            Ok(()) => println!("EX30\t一覧({})\t\t", 探す(&ctx, &保存, &入力).join(",")),
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "xxxを買った".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N2".to_string(), 投稿 { 投稿ID: "N2".to_string(), 本文: "病院".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 2000i64, 最後に操作した日時: 2000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N3".to_string(), 投稿 { 投稿ID: "N3".to_string(), 本文: "xxxの件".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 3000i64, 最後に操作した日時: 3000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N4".to_string(), 投稿 { 投稿ID: "N4".to_string(), 本文: "xxx消した".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 4000i64, 最後に操作した日時: 4000i64, 状態: 投稿状態::削除済, 記録: 記録状態::記録済 });
        let ctx = 探す文脈 {  };
        let 入力 = 探す入力 { 始め: Some(1500i64), 終わり: None, 単語: None };
        match 入力.検査() {
            Err(e) => println!("EX31\t入力不正({})\t\t", e),
            Ok(()) => println!("EX31\t一覧({})\t\t", 探す(&ctx, &保存, &入力).join(",")),
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "xxxを買った".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N2".to_string(), 投稿 { 投稿ID: "N2".to_string(), 本文: "病院".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 2000i64, 最後に操作した日時: 2000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N3".to_string(), 投稿 { 投稿ID: "N3".to_string(), 本文: "xxxの件".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 3000i64, 最後に操作した日時: 3000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N4".to_string(), 投稿 { 投稿ID: "N4".to_string(), 本文: "xxx消した".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 4000i64, 最後に操作した日時: 4000i64, 状態: 投稿状態::削除済, 記録: 記録状態::記録済 });
        let ctx = 探す文脈 {  };
        let 入力 = 探す入力 { 始め: Some(1500i64), 終わり: Some(2500i64), 単語: None };
        match 入力.検査() {
            Err(e) => println!("EX32\t入力不正({})\t\t", e),
            Ok(()) => println!("EX32\t一覧({})\t\t", 探す(&ctx, &保存, &入力).join(",")),
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "xxxを買った".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N2".to_string(), 投稿 { 投稿ID: "N2".to_string(), 本文: "病院".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 2000i64, 最後に操作した日時: 2000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N3".to_string(), 投稿 { 投稿ID: "N3".to_string(), 本文: "xxxの件".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 3000i64, 最後に操作した日時: 3000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N4".to_string(), 投稿 { 投稿ID: "N4".to_string(), 本文: "xxx消した".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 4000i64, 最後に操作した日時: 4000i64, 状態: 投稿状態::削除済, 記録: 記録状態::記録済 });
        let ctx = 探す文脈 {  };
        let 入力 = 探す入力 { 始め: Some(1500i64), 終わり: None, 単語: Some("病院".to_string()) };
        match 入力.検査() {
            Err(e) => println!("EX33\t入力不正({})\t\t", e),
            Ok(()) => println!("EX33\t一覧({})\t\t", 探す(&ctx, &保存, &入力).join(",")),
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "xxxを買った".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N2".to_string(), 投稿 { 投稿ID: "N2".to_string(), 本文: "病院".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 2000i64, 最後に操作した日時: 2000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N3".to_string(), 投稿 { 投稿ID: "N3".to_string(), 本文: "xxxの件".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 3000i64, 最後に操作した日時: 3000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N4".to_string(), 投稿 { 投稿ID: "N4".to_string(), 本文: "xxx消した".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 4000i64, 最後に操作した日時: 4000i64, 状態: 投稿状態::削除済, 記録: 記録状態::記録済 });
        let ctx = 探す文脈 {  };
        let 入力 = 探す入力 { 始め: None, 終わり: None, 単語: Some("旅行".to_string()) };
        match 入力.検査() {
            Err(e) => println!("EX34\t入力不正({})\t\t", e),
            Ok(()) => println!("EX34\t一覧({})\t\t", 探す(&ctx, &保存, &入力).join(",")),
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "投稿1".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: -8000i64, 最後に操作した日時: -8000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N2".to_string(), 投稿 { 投稿ID: "N2".to_string(), 本文: "投稿2".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 96400i64, 最後に操作した日時: 96400i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N3".to_string(), 投稿 { 投稿ID: "N3".to_string(), 本文: "投稿3".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 99940i64, 最後に操作した日時: 99940i64, 状態: 投稿状態::削除済, 記録: 記録状態::記録済 });
        let ctx = 圏外で見る文脈 { 現在: 100000i64 };
        let 入力 = 圏外で見る入力 { 件数: 10u64 };
        match 入力.検査() {
            Err(e) => println!("EX35\t入力不正({})\t\t", e),
            Ok(()) => println!("EX35\t一覧({})\t\t", 圏外で見る(&ctx, &保存, &入力).join(",")),
        }
    }
    {
        let mut 保存 = 保存::default();
        let ctx = 投稿の取り込み文脈 { 新投稿ID: "N9".to_string() };
        let 入力 = 投稿の取り込み入力 { 本文: "PCで書いた".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 900i64, 操作日時: 950i64 };
        match 入力.検査() {
            Err(e) => println!("EX36\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 投稿の取り込み(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX36\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "メモ".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        let ctx = 未反映に戻す文脈 {  };
        let 入力 = 未反映に戻す入力 { 投稿ID: "N1".to_string() };
        match 入力.検査() {
            Err(e) => println!("EX37\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 未反映に戻す(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX37\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "メモ".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::端末保存済 });
        let ctx = 未反映に戻す文脈 {  };
        let 入力 = 未反映に戻す入力 { 投稿ID: "N1".to_string() };
        match 入力.検査() {
            Err(e) => println!("EX38\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 未反映に戻す(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX38\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "同じ秒の1".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        保存.投稿.insert("N2".to_string(), 投稿 { 投稿ID: "N2".to_string(), 本文: "同じ秒の2".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        let ctx = 一覧を見る文脈 {  };
        let 入力 = 一覧を見る入力 { 件数: 5u64 };
        match 入力.検査() {
            Err(e) => println!("EX39\t入力不正({})\t\t", e),
            Ok(()) => println!("EX39\t一覧({})\t\t", 一覧を見る(&ctx, &保存, &入力).join(",")),
        }
    }
    {
        let mut 保存 = 保存::default();
        保存.投稿.insert("N1".to_string(), 投稿 { 投稿ID: "N1".to_string(), 本文: "B".to_string(), 添付: BTreeSet::from([]), リンク: BTreeSet::from([]), 書いた日時: 1000i64, 最後に操作した日時: 1000i64, 状態: 投稿状態::投稿済, 記録: 記録状態::記録済 });
        let ctx = 直しの取り込み文脈 {  };
        let 入力 = 直しの取り込み入力 { 投稿ID: "N1".to_string(), 直し日時: 1300i64, 本文: "B".to_string(), 添付: BTreeSet::from(["F1".to_string()]), リンク: BTreeSet::from(["L1".to_string()]) };
        match 入力.検査() {
            Err(e) => println!("EX40\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 直しの取り込み(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX40\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        let ctx = 添付する文脈 { 新添付ファイルID: "F1".to_string() };
        let 入力 = 添付する入力 { 名前: "a.png".to_string(), 種類: "image/png".to_string(), 中身: vec![0x89u8, 0x50u8, 0x4eu8, 0x47u8] };
        match 入力.検査() {
            Err(e) => println!("EX41\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = 添付する(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX41\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
    {
        let mut 保存 = 保存::default();
        let ctx = リンクを付ける文脈 { 新添付リンクID: "L1".to_string() };
        let 入力 = リンクを付ける入力 { 先: "https://example.com".to_string() };
        match 入力.検査() {
            Err(e) => println!("EX42\t入力不正({})\t\t", e),
            Ok(()) => {
                let 出力 = リンクを付ける(&ctx, &保存, &入力);
                let 前 = 保存.clone();
                保存.適用(出力.書込.clone());
                println!("EX42\t{}\t{}\t{}", 出力.結果.表示(), 前.差分(&保存).join(";"), 出力.外部.iter().map(|e| e.表示()).collect::<Vec<_>>().join(";"));
            }
        }
    }
}
