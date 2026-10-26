// Dropbox との窓口。実物（RealDropbox）と、確認用の模擬（MockDropbox）の2つ。
// どちらも同じ6つの操作だけを持つ：list／getPost／putPost／deletePost／putFile／getFile。
// 置き場所は /solo_tweet/posts/<投稿ID>.json と /solo_tweet/files/<部品ID>（AIにはこの場所を1回教える）。
(function (root) {
  'use strict';

  const ネット切れ = (msg) => Object.assign(new Error(msg || '電波がつながりません'), { network: true });

  // ---- 模擬：ブラウザの中だけで動く Dropbox のふり ----
  class MockDropbox {
    constructor() {
      this.posts = new Map(); // id -> {rev, json}
      this.files = new Map(); // id -> {名前, 種類, 中身(base64)}
      this.links = new Map(); // id -> {先}
      this.rev = 0;
      this.offline = false; // 圏外のふり
      this.failNext = 0; // 次の書き込みを失敗させる回数（原因つき）
      this.failReason = '容量がいっぱいです（模擬）';
      this.failFiles = false; // 添付の書き込みだけ失敗させる（束の確認用）
    }
    確かめる() { if (this.offline) throw ネット切れ(); }
    async listPosts() { this.確かめる(); return [...this.posts].map(([id, v]) => ({ id, rev: v.rev })); }
    async getPost(id) { this.確かめる(); const v = this.posts.get(id); if (!v) throw new Error('見つかりません'); return JSON.parse(v.json); }
    async putPost(id, obj) {
      this.確かめる();
      if (this.failNext > 0) { this.failNext--; throw Object.assign(new Error(this.failReason), { reason: /容量/.test(this.failReason) ? '容量不足' : undefined }); }
      const rev = 'r' + (++this.rev);
      this.posts.set(id, { rev, json: JSON.stringify(obj) });
      return rev;
    }
    async deletePost(id) { this.確かめる(); this.posts.delete(id); }
    async putFile(id, 名前, 種類, 中身) { this.確かめる(); if (this.failFiles) throw new Error(this.failReason); this.files.set(id, { 名前, 種類, 中身 }); }
    async getFile(id) { this.確かめる(); const f = this.files.get(id); if (!f) throw new Error('見つかりません'); return f; }
    async putLink(id, 先) { this.確かめる(); this.links.set(id, { 先 }); }
    async getLink(id) { this.確かめる(); const l = this.links.get(id); if (!l) throw new Error('見つかりません'); return l; }

    // 別の端末のふり（確認用）
    他端末で書く(obj) {
      const rev = 'r' + (++this.rev);
      this.posts.set(obj.投稿ID, { rev, json: JSON.stringify(obj) });
    }
    他端末で直す(id, 本文, 時刻, 追加 = {}) {
      const v = this.posts.get(id);
      if (!v) return false;
      const o = JSON.parse(v.json);
      o.本文 = 本文; o.最後に操作した日時 = 時刻; Object.assign(o, 追加);
      this.posts.set(id, { rev: 'r' + (++this.rev), json: JSON.stringify(o) });
      return true;
    }
    他端末でリンクを足す(id, 先) { this.links.set(id, { 先 }); }
    他端末で消す(id) { return this.posts.delete(id); }
  }

  // ---- 実物：Dropbox の HTTP API をトークンで呼ぶ ----
  class RealDropbox {
    constructor(token, fetchFn) {
      this.token = token;
      this.fetch = fetchFn || ((...a) => root.fetch(...a));
      this.base = '/solo_tweet';
    }
    // Dropbox-API-Arg ヘッダは ASCII のみ。日本語は \uXXXX にする
    arg(o) { return JSON.stringify(o).replace(/[\u007f-￿]/g, (c) => '\\u' + ('0000' + c.charCodeAt(0).toString(16)).slice(-4)); }
    async 呼ぶ(url, init, 欲しいもの) {
      let res;
      try { res = await this.fetch(url, init); } catch (e) { throw ネット切れ(); }
      if (res.ok) return res;
      let text = '';
      try { text = await res.text(); } catch (e) { /* そのまま */ }
      if (res.status === 401) throw Object.assign(new Error('Dropbox の認証が通りません（トークンを確かめてください）'), { reason: '認証切れ' });
      if (res.status === 409 && /insufficient_space/.test(text)) throw Object.assign(new Error('Dropbox の容量がいっぱいです'), { reason: '容量不足' });
      if (res.status === 409 && 欲しいもの === '無くてよい' && /not_found/.test(text)) return null;
      if (res.status === 429) throw new Error('Dropbox が混み合っています。少し待ってやり直します');
      throw new Error('Dropbox のエラー（' + res.status + '）' + text.slice(0, 120));
    }
    json(url, body, 欲しいもの) {
      return this.呼ぶ('https://api.dropboxapi.com/2/' + url, {
        method: 'POST', headers: { Authorization: 'Bearer ' + this.token, 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      }, 欲しいもの);
    }
    async upload(path, bytes) {
      const res = await this.呼ぶ('https://content.dropboxapi.com/2/files/upload', {
        method: 'POST',
        headers: { Authorization: 'Bearer ' + this.token, 'Dropbox-API-Arg': this.arg({ path, mode: 'overwrite', mute: true }), 'Content-Type': 'application/octet-stream' },
        body: bytes,
      });
      return (await res.json()).rev;
    }
    async download(path) {
      return this.呼ぶ('https://content.dropboxapi.com/2/files/download', {
        method: 'POST', headers: { Authorization: 'Bearer ' + this.token, 'Dropbox-API-Arg': this.arg({ path }) },
      });
    }
    async listPosts() {
      let res = await this.json('files/list_folder', { path: this.base + '/posts' }, '無くてよい');
      if (!res) return []; // まだ何も書いていない
      let j = await res.json();
      const out = [];
      for (;;) {
        for (const e of j.entries) if (e['.tag'] === 'file' && /\.json$/.test(e.name)) out.push({ id: e.name.replace(/\.json$/, ''), rev: e.rev });
        if (!j.has_more) break;
        j = await (await this.json('files/list_folder/continue', { cursor: j.cursor })).json();
      }
      return out;
    }
    async getPost(id) { return JSON.parse(await (await this.download(this.base + '/posts/' + id + '.json')).text()); }
    async putPost(id, obj) { return this.upload(this.base + '/posts/' + id + '.json', new TextEncoder().encode(JSON.stringify(obj, null, 1))); }
    async deletePost(id) { await this.json('files/delete_v2', { path: this.base + '/posts/' + id + '.json' }, '無くてよい'); }
    async putFile(id, 名前, 種類, 中身) {
      const bin = atob(中身);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      await this.upload(this.base + '/files/' + id, bytes);
      await this.upload(this.base + '/files/' + id + '.meta', new TextEncoder().encode(JSON.stringify({ 名前, 種類 })));
    }
    async getFile(id) {
      const meta = JSON.parse(await (await this.download(this.base + '/files/' + id + '.meta')).text());
      const buf = new Uint8Array(await (await this.download(this.base + '/files/' + id)).arrayBuffer());
      let s = '';
      for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
      return { 名前: meta.名前, 種類: meta.種類, 中身: btoa(s) };
    }
    async putLink(id, 先) { await this.upload(this.base + '/links/' + id + '.json', new TextEncoder().encode(JSON.stringify({ 先 }))); }
    async getLink(id) { return JSON.parse(await (await this.download(this.base + '/links/' + id + '.json')).text()); }
  }

  const api = { MockDropbox, RealDropbox };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.SoloDropbox = api;
})(typeof window !== 'undefined' ? window : globalThis);
