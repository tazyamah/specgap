// 画面の動作確認（ブラウザを自動で動かす）。使い方: node check.js
// 先に python build.py で dist/solo_tweet.html を作っておく。Dropbox は本物に触らず、模擬の応答で確かめる。
const { chromium } = require('playwright');
const path = require('path');
const assert = require('assert');

const URL = 'file://' + path.join(__dirname, 'dist', 'solo_tweet.html');
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64');
let n = 0;
const ok = (m) => console.log(`  ✓ ${++n}. ${m}`);

async function open(browser, opts = {}) {
  const ctx = await browser.newContext(opts);
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(URL);
  await page.waitForFunction(() => window.appReady);
  await page.evaluate(() => { const d = document.querySelector('#demo'); if (d) d.open = true; });
  return { ctx, page, errors };
}
const texts = (page) => page.$$eval('#list .post .body', (a) => a.map((x) => x.textContent));
const post = async (page, t) => {
  await page.evaluate(() => { window.engine.skew += 2; }); // 秒単位の時刻が同じだと並びが決まらないので、時計を少し進める
  await page.fill('#text', t);
  await page.click('#btn-send');
  await page.evaluate(() => window.engine.idle());
};

(async () => {
  const browser = await chromium.launch();

  // ---- 書く・見る・直す・消す（PC） ----
  {
    const { ctx, page, errors } = await open(browser, { viewport: { width: 1100, height: 800 } });
    assert.strictEqual(await page.textContent('#list .empty'), '空です'); ok('投稿が無いとき「空です」');
    await page.click('#btn-send', { force: true }); // 押せない見た目でも押そうとする
    assert.ok(await page.isVisible('#send-hint')); ok('空のまま押すと「投稿を入力してから押してください」');
    assert.strictEqual(await page.getAttribute('#btn-send', 'aria-disabled'), 'true');
    await post(page, 'はじめての投稿');
    assert.deepStrictEqual(await texts(page), ['はじめての投稿']);
    assert.strictEqual(await page.locator('.badge').count(), 0); ok('書くと一覧に出て、Dropboxに記録されると「反映前」が消える');
    assert.strictEqual(await page.evaluate(() => window.mock.posts.size), 1);

    await page.click('#d-off');
    await post(page, '圏外で書いた');
    assert.ok(await page.isVisible('#offline-banner'));
    assert.strictEqual(await page.locator('.badge').count(), 1);
    assert.strictEqual(await page.locator('.notice.error').count(), 0); ok('圏外で書くと、すぐ一覧に出て「反映前」の印が付く（エラーは出ない）');
    await page.click('#d-off');
    await page.evaluate(() => window.engine.idle());
    await page.waitForFunction(() => !document.querySelector('.badge'));
    assert.strictEqual(await page.evaluate(() => window.mock.posts.size), 2); ok('つなぐと自動で反映され、印が消える');

    await page.click('.post:first-child [data-act="edit"]');
    await page.fill('.post.editing [data-e="text"]', '');
    await page.click('[data-act="e-save"]');
    assert.ok(await page.isVisible('[data-e="hint"]')); ok('直すとき空のままでは保存できない');
    await page.fill('.post.editing [data-e="text"]', '直した文');
    await page.click('[data-act="e-save"]');
    await page.evaluate(() => window.engine.idle());
    assert.deepStrictEqual(await texts(page), ['直した文', 'はじめての投稿']); ok('投稿を直せる（位置は変わらない）');

    await page.click('.post:first-child [data-act="del"]');
    assert.deepStrictEqual(await texts(page), ['はじめての投稿']);
    assert.ok(await page.isVisible('#undo .u'));
    await page.click('[data-undo]');
    assert.deepStrictEqual(await texts(page), ['直した文', 'はじめての投稿']); ok('消すとすぐ隠れ、30秒のあいだ「元に戻す」で戻せる');
    await page.click('.post:first-child [data-act="del"]');
    await page.click('#d-30');
    await page.evaluate(() => window.engine.idle());
    assert.strictEqual(await page.locator('#undo .u').count(), 0);
    assert.strictEqual(await page.evaluate(() => window.mock.posts.size), 1); ok('30秒たつと削除が確定し、Dropboxからも消える');

    // 別の端末
    await page.click('#d-other-write');
    await page.click('#btn-refresh');
    await page.evaluate(() => window.engine.idle());
    await page.waitForFunction(() => document.querySelectorAll('#list .post').length === 2);
    assert.ok((await texts(page))[0].includes('別の端末のふり')); ok('別の端末が書いた投稿を更新で取り込む');
    await page.click('#d-other-edit');
    await page.waitForTimeout(1100); // 秒単位の時刻で「新しい」と言えるように
    await page.click('#d-other-edit');
    await page.click('#btn-refresh');
    await page.waitForFunction(() => document.querySelector('#list .post .body').textContent.includes('別の端末で直した'));
    ok('別の端末の直しを取り込む');
    await page.click('#d-other-del');
    await page.waitForTimeout(1100); // 消えたことに気づく時刻が、直しの時刻より後になるように
    await page.click('#btn-refresh');
    await page.waitForFunction(() => document.querySelectorAll('#list .post').length === 1);
    ok('別の端末の消しを取り込む');

    // 書き込みの失敗は原因つきですぐ表示
    await page.click('#d-fail');
    await post(page, '失敗する書き込み');
    await page.waitForSelector('.notice.error');
    assert.ok((await page.textContent('.notice.error')).includes('容量がいっぱいです'));
    assert.strictEqual(await page.locator('.badge').count(), 1);
    ok('Dropboxへの書き込みが失敗したら、原因をすぐ表示し、投稿は端末に残る');
    await page.click('#btn-refresh');
    await page.evaluate(() => window.engine.idle());
    await page.waitForFunction(() => !document.querySelector('.badge'));
    ok('失敗した書き込みは次の更新でやり直される');

    // 24時間たっても記録できていない
    await page.click('#d-off');
    await post(page, '24時間たつ投稿');
    await page.click('#d-24h');
    await page.waitForSelector('.notice.warn');
    ok('圏外のまま24時間たつと本人に知らせる');
    await page.click('#d-off');
    await page.evaluate(() => window.engine.idle());

    // 探す
    await page.click('#tab-search');
    await page.fill('#s-word', 'はじめて');
    await page.click('#btn-search');
    assert.strictEqual(await page.locator('#s-result .post').count(), 1);
    await page.fill('#s-word', 'ありえない言葉');
    await page.click('#btn-search');
    assert.strictEqual(await page.textContent('#s-result .empty'), '1件もありませんでした'); ok('探す：単語で絞り込み、無いときは「1件もありませんでした」');
    await page.fill('#s-word', '');
    await page.fill('#s-from', '2999-01-01');
    await page.click('#btn-search');
    assert.strictEqual(await page.locator('#s-result .post').count(), 0);
    await page.fill('#s-from', '2000-01-01');
    await page.click('#btn-search');
    assert.ok((await page.locator('#s-result .post').count()) >= 1); ok('探す：日付の期間（始めだけでもよい）');
    await page.click('#tab-main');

    // 添付とリンク
    await page.setInputFiles('#file', { name: 'あ.png', mimeType: 'image/png', buffer: PNG });
    await page.waitForSelector('#draft-parts .c');
    await page.click('#btn-link');
    await page.fill('#link-url', 'https://example.com/a');
    await page.click('#btn-link-add');
    await post(page, '');
    await page.waitForSelector('#list .post .thumbs img');
    assert.ok(await page.isVisible('#list .post .links a'));
    assert.ok(await page.evaluate(() => [...window.mock.files.keys()].length === 1)); ok('文字なしでも画像とリンクだけで投稿でき、サムネイルが出てDropboxへ画像も上がる');

    assert.deepStrictEqual(errors, []); ok('画面のエラーは出ていない');
    await ctx.close();
  }

  // ---- 一覧が長いとき：トップへ戻るボタン（PCとスマホ） ----
  for (const [name, vp] of [['PC', { width: 1100, height: 700 }], ['スマホ', { width: 390, height: 700, isMobile: true, hasTouch: true }]]) {
    const { ctx, page } = await open(browser, { viewport: vp });
    await page.evaluate(async () => { for (let i = 0; i < 30; i++) await window.engine.投稿する('投稿' + i, [], []); await window.engine.idle(); });
    await page.waitForSelector('#list .post');
    assert.ok(await page.isHidden('#top'));
    await page.mouse.wheel(0, 1500);
    await page.waitForFunction(() => window.scrollY > 300);
    assert.ok(await page.isVisible('#top'));
    await page.click('#top');
    await page.waitForFunction(() => window.scrollY === 0);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)); ok(`${name}：下へ行くとトップへ戻るボタンが出て、押すと一番上へ戻る（横にはみ出さない）`);
    await ctx.close();
  }

  // ---- 本物の Dropbox 窓口（模擬の応答に向けて） ----
  {
    const { ctx, page } = await open(browser, { viewport: { width: 900, height: 700 } });
    await page.evaluate(() => { localStorage.setItem('solo_tweet_mode', 'dropbox'); localStorage.setItem('solo_tweet_token', 'TESTTOKEN'); });
    const files = new Map(); let rev = 0; const seen = [];
    await ctx.route(/dropboxapi\.com/, async (route) => {
      const req = route.request(), u = req.url(), h = req.headers();
      seen.push(u.split('/2/')[1] + ' ' + h.authorization);
      const arg = h['dropbox-api-arg'] ? JSON.parse(h['dropbox-api-arg']) : req.postData() ? JSON.parse(req.postData()) : {};
      const cors = { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*' };
      if (req.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: cors });
      if (u.endsWith('files/upload')) { files.set(arg.path, { body: req.postDataBuffer(), rev: 'v' + ++rev }); return route.fulfill({ headers: cors, contentType: 'application/json', body: JSON.stringify({ rev: 'v' + rev }) }); }
      if (u.endsWith('files/download')) { const f = files.get(arg.path); return f ? route.fulfill({ headers: cors, body: f.body }) : route.fulfill({ status: 409, headers: cors, body: 'path/not_found' }); }
      if (u.endsWith('files/delete_v2')) { const had = files.delete(arg.path); return had ? route.fulfill({ headers: cors, contentType: 'application/json', body: '{}' }) : route.fulfill({ status: 409, headers: cors, body: 'path_lookup/not_found' }); }
      if (u.endsWith('files/list_folder')) {
        const ents = [...files].filter(([p]) => p.startsWith(arg.path + '/')).map(([p, f]) => ({ '.tag': 'file', name: p.split('/').pop(), rev: f.rev }));
        if (!ents.length && !files.size) return route.fulfill({ status: 409, headers: cors, body: 'path/not_found' });
        return route.fulfill({ headers: cors, contentType: 'application/json', body: JSON.stringify({ entries: ents, has_more: false, cursor: 'c' }) });
      }
      return route.fulfill({ status: 500, headers: cors, body: 'unknown' });
    });
    await page.reload();
    await page.waitForFunction(() => window.appReady);
    assert.ok(await page.isHidden('#demo'));
    await post(page, 'Dropboxへ');
    await page.waitForFunction(() => !document.querySelector('.badge'));
    const paths = [...files.keys()];
    assert.deepStrictEqual(paths.length, 1);
    assert.ok(paths[0].startsWith('/solo_tweet/posts/') && paths[0].endsWith('.json'));
    const saved = JSON.parse(files.get(paths[0]).body.toString());
    assert.strictEqual(saved.本文, 'Dropboxへ');
    assert.ok(seen.every((s) => s.endsWith('Bearer TESTTOKEN')));
    ok('Dropbox（模擬の応答）：記録は /solo_tweet/posts/<ID>.json に置かれ、トークン付きで呼ばれる');

    // 別の端末が書いたファイルを取り込む
    files.set('/solo_tweet/posts/zz1.json', { rev: 'v' + ++rev, body: Buffer.from(JSON.stringify({ 投稿ID: 'zz1', 本文: 'スマホで書いた', 添付: [], リンク: [], 書いた日時: 100, 最後に操作した日時: 100 })) });
    await page.click('#btn-refresh');
    await page.waitForFunction(() => document.querySelectorAll('#list .post').length === 2);
    ok('Dropbox（模擬の応答）：別の端末のファイルを取り込む');
    // 消す：30秒後にファイルが消える
    await page.click('.post:first-child [data-act="del"]');
    await page.evaluate(() => { window.engine.skew += 31; return window.engine.tick(); });
    await page.evaluate(() => window.engine.idle());
    assert.strictEqual([...files.keys()].filter((p) => p.endsWith('.json')).length, 1);
    ok('Dropbox（模擬の応答）：削除が確定するとファイルを消す');
    // 認証エラー
    await page.evaluate(() => { window.engine.dropbox.token = 'BAD'; });
    await ctx.unroute(/dropboxapi\.com/);
    await ctx.route(/dropboxapi\.com/, (r) => r.fulfill({ status: 401, headers: { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*' }, body: 'invalid_access_token' }));
    await post(page, '認証が通らない');
    await page.waitForSelector('.notice.error');
    assert.ok((await page.textContent('.notice.error')).includes('認証'));
    ok('Dropbox（模擬の応答）：認証が通らないときは原因を表示する');
    await ctx.close();
  }

  await browser.close();
  console.log(`\n${n} 件すべて通りました`);
})().catch((e) => { console.error('\n失敗:', e.message); process.exit(1); });
