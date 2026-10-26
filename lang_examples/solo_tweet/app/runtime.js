// ひとり用つぶやき：画面の下で動く「実行部」。
// 仕様の判断（投稿・直す・消す・取り込みなど）はすべて、コードから生成した WASM が行う。
// ここがするのは、WASM の外側の仕事だけ：
//   待ち（期限・応答）の管理、外部作用（Dropbox）の実行、端末への保存、別端末の取り込みの呼び出し。
(function (root) {
  'use strict';
  const enc = new TextEncoder();
  const dec = new TextDecoder();

  class MemStorage {
    constructor() { this.m = new Map(); }
    getItem(k) { return this.m.has(k) ? this.m.get(k) : null; }
    setItem(k, v) { this.m.set(k, String(v)); }
  }

  const 新しい状態 = () => ({ 保存: {}, 待ち: [], 再送書く: [], 再送消す: [], 部品: {}, 改訂: {}, 通知: [] });

  class Engine {
    static async create(opts) {
      const { instance } = await WebAssembly.instantiate(opts.wasmBytes, {});
      return new Engine(instance.exports, opts);
    }

    constructor(x, o) {
      this.x = x;
      this.defs = JSON.parse(this.窓口の文字列(x.specgap_defs()));
      this.storage = o.storage || new MemStorage();
      this.key = o.key || 'solo_tweet';
      this.dropbox = o.dropbox;
      this.skew = 0; // 確認用：時計を進めた秒数
      this.online = o.online !== false;
      this.loading = false;
      this.listeners = [];
      this.inflight = new Set();
      this.lastError = {};
      this.state = this.読む();
    }

    // ---- WASM 窓口（JSON を渡して JSON を受ける） ----
    窓口の文字列(r) {
      const v = BigInt.asUintN(64, r);
      const ptr = Number(v >> 32n), len = Number(v & 0xffffffffn);
      const s = dec.decode(new Uint8Array(this.x.memory.buffer, ptr, len).slice());
      this.x.dealloc(ptr, len);
      return s;
    }
    窓口(obj) {
      const b = enc.encode(JSON.stringify(obj));
      const p = this.x.alloc(b.length);
      new Uint8Array(this.x.memory.buffer, p, b.length).set(b);
      const r = JSON.parse(this.窓口の文字列(this.x.specgap_call(p, b.length)));
      if (r.エラー) throw new Error(r.エラー);
      return r;
    }

    // ---- 時計・ID ----
    now() { return Math.floor(Date.now() / 1000) + this.skew; }
    newId(prefix) { return prefix + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }

    // ---- 端末への保存 ----
    読む() {
      try {
        const s = this.storage.getItem(this.key);
        if (s) return Object.assign(新しい状態(), JSON.parse(s));
      } catch (e) { /* 壊れていれば空から */ }
      return 新しい状態();
    }
    書く() {
      try { this.storage.setItem(this.key, JSON.stringify(this.state)); } catch (e) { /* 容量超過など */ }
    }
    on(fn) { this.listeners.push(fn); }
    emit(ev) { for (const f of this.listeners) f(ev); }
    変わった() { this.書く(); this.emit({ type: 'changed' }); }
    お知らせ(kind, text, id) { this.emit({ type: 'notice', kind, text, id }); }

    // ---- 処理・問い合わせの呼び出し ----
    文脈(name, idOverride) {
      const d = this.defs.処理[name] || this.defs.問い合わせ[name];
      const ctx = {};
      for (const r of d.参照) if (r === '現在') ctx.現在 = this.now();
      for (const n of (d.採番 || [])) ctx['新' + n + 'ID'] = idOverride || this.newId('p');
      return ctx;
    }
    入力(name, given) {
      const d = this.defs.処理[name] || this.defs.問い合わせ[name];
      const inp = {};
      for (const k of d.入力) if (given[k] !== undefined && given[k] !== null) inp[k] = given[k];
      return inp;
    }
    呼ぶ(name, given, idOverride) {
      const r = this.窓口({ 名前: name, 文脈: this.文脈(name, idOverride), 保存: this.state.保存, 入力: this.入力(name, given) });
      this.state.保存 = r.保存;
      return r;
    }
    問い合わせ(name, given) {
      return this.窓口({ 名前: name, 文脈: this.文脈(name), 保存: this.state.保存, 入力: this.入力(name, given) }).引数;
    }

    // ---- フロー：結果ごとの行き先をたどる ----
    async run(name, given, idOverride) {
      let cur = name, inp = Object.assign({}, given), first;
      const effects = [];
      for (let i = 0; i < 12; i++) {
        const r = this.呼ぶ(cur, inp, cur === name ? idOverride : undefined);
        this.emit({ type: 'process', 処理: cur, 結果: r.結果 });
        if (!first) first = r;
        for (const e of r.外部) effects.push(e);
        const route = (this.defs.フロー[cur] || {})[r.結果];
        if (!route || route === '応答') break;
        if (route.startsWith('待つ ')) { this.待ちに入る(route.slice(3), inp, r); break; }
        // 次の処理へ：結果がIDを1つ運んでくれば投稿IDとして渡す（投稿する → 反映の要求）
        if (r.引数.length === 1 && typeof r.引数[0] === 'string') inp.投稿ID = r.引数[0];
        cur = route;
      }
      this.変わった();
      for (const e of effects) this.追跡(this.外部を実行(e));
      return first;
    }
    追跡(p) {
      this.inflight.add(p);
      p.finally(() => this.inflight.delete(p));
    }
    async idle() { while (this.inflight.size) await Promise.all([...this.inflight]); }

    // ---- 待ち（トリガ） ----
    待ちに入る(trigger, inp) {
      const def = this.defs.トリガ.find((t) => t.名前 === trigger);
      const args = {};
      for (const a of def.引数) args[a] = inp[a];
      const deadlines = def.要因.filter((c) => c.種別 === '期限').map((c) => c.秒);
      this.state.待ち = this.state.待ち.filter((w) => !(w.名前 === trigger && JSON.stringify(w.引数) === JSON.stringify(args)));
      this.state.待ち.push({ 名前: trigger, 引数: args, 期限: deadlines.length ? this.now() + Math.min(...deadlines) : null });
    }
    待っている(trigger, 投稿ID) {
      return this.state.待ち.find((w) => w.名前 === trigger && w.引数.投稿ID === 投稿ID);
    }
    async 応答する(trigger, 応答名, 投稿ID) {
      const w = this.待っている(trigger, 投稿ID);
      if (!w) return false;
      const def = this.defs.トリガ.find((t) => t.名前 === trigger);
      const c = def.要因.find((x) => x.種別 === '応答' && x.キー === 応答名);
      if (!c) return false;
      this.state.待ち = this.state.待ち.filter((x) => x !== w);
      await this.run(c.行き先, w.引数);
      return true;
    }
    async tick() {
      const now = this.now();
      for (let guard = 0; guard < 50; guard++) {
        const w = this.state.待ち.find((x) => x.期限 !== null && x.期限 <= now);
        if (!w) break;
        const def = this.defs.トリガ.find((t) => t.名前 === w.名前);
        const c = def.要因.find((x) => x.種別 === '期限');
        this.state.待ち = this.state.待ち.filter((x) => x !== w);
        await this.run(c.行き先, w.引数);
      }
    }
    start() {
      if (this.timer) return;
      this.timer = setInterval(() => { this.tick().catch(() => {}); this.emit({ type: 'tick' }); }, 1000);
    }

    // ---- 外部作用（Dropbox） ----
    ネットワークの結果(ok, err) {
      const before = this.online;
      if (ok) this.online = true;
      else if (err && err.network) this.online = false;
      if (before !== this.online) this.emit({ type: 'online' });
    }
    async 外部を実行(e) {
      const id = e.引数.投稿ID;
      if (e.名前 === 'Dropbox.書く') {
        const p = this.state.保存.投稿 && this.state.保存.投稿[id];
        if (!p || p.状態 === '完全削除済') return;
        try {
          await this.書き出す(p);
          this.ネットワークの結果(true);
          this.state.再送書く = this.state.再送書く.filter((x) => x !== id);
          delete this.lastError[id];
          this.変わった();
          await this.応答する('書込待ち', '書込成功', id);
        } catch (err) {
          this.ネットワークの結果(false, err);
          if (!this.state.再送書く.includes(id)) this.state.再送書く.push(id);
          this.lastError[id] = err.message || String(err);
          this.変わった();
          // 圏外は失敗ではなく「あとで反映」（J28）。つながったとき再送する。原因が別にあるときだけ、すぐ表示する（J37）
          if (err.network) return;
          await this.応答する('書込待ち', '書込失敗', id);
          this.お知らせ('error', '記録できませんでした（投稿は端末に残しています）。原因：' + this.lastError[id], id);
        }
      } else if (e.名前 === 'Dropbox.消す') {
        try {
          await this.dropbox.deletePost(id);
          this.ネットワークの結果(true);
          this.state.再送消す = this.state.再送消す.filter((x) => x !== id);
          delete this.state.改訂[id];
        } catch (err) {
          this.ネットワークの結果(false, err);
          if (!this.state.再送消す.includes(id)) this.state.再送消す.push(id);
        }
        this.変わった();
      }
    }
    async 書き出す(p) {
      const links = {};
      for (const l of p.リンク) links[l] = (this.state.部品[l] || {}).url || '';
      for (const f of p.添付) {
        const part = this.state.部品[f];
        if (part && !part.上げた) { await this.dropbox.putFile(f, part.名前, part.dataURL); part.上げた = true; }
      }
      const names = {};
      for (const f of p.添付) names[f] = (this.state.部品[f] || {}).名前 || '';
      const rev = await this.dropbox.putPost(p.投稿ID, {
        投稿ID: p.投稿ID, 本文: p.本文, 添付: p.添付, 添付名: names, リンク: p.リンク, リンク先: links,
        書いた日時: p.書いた日時, 最後に操作した日時: p.最後に操作した日時,
      });
      this.state.改訂[p.投稿ID] = rev;
    }

    // ---- 画面からの操作 ----
    部品を足す(part) {
      const id = this.newId(part.種類 === 'file' ? 'f' : 'l');
      this.state.部品[id] = Object.assign({ 上げた: false }, part);
      this.変わった();
      return id;
    }
    投稿する(本文, 添付, リンク) { return this.run('投稿する', { 本文, 添付, リンク }); }
    直す(投稿ID, 本文, 添付, リンク) { return this.run('直す', { 投稿ID, 本文, 添付, リンク }); }
    消す(投稿ID) { return this.run('消す', { 投稿ID }); }
    元に戻す(投稿ID) {
      const w = this.待っている('削除猶予', 投稿ID);
      if (!w) return Promise.resolve(false);
      return this.応答する('削除猶予', '元に戻す', 投稿ID);
    }

    // ---- 一覧・探す ----
    一覧(件数) {
      const ids = this.online ? this.問い合わせ('一覧を見る', { 件数 }) : this.問い合わせ('圏外で見る', { 件数 });
      return ids.map((id) => this.state.保存.投稿[id]);
    }
    探す(始め, 終わり, 単語) {
      const given = {};
      if (始め != null) given.始め = 始め;
      if (終わり != null) given.終わり = 終わり;
      if (単語) given.単語 = 単語;
      return this.問い合わせ('探す', given).map((id) => this.state.保存.投稿[id]);
    }

    // ---- つながったときの同期 ----
    // 外の出来事（アプリを開いた・画面を引っぱった・つながりが戻った）。起こす処理は、コードの「出来事」の宣言にしたがう
    async 同期する(出来事 = 'アプリを開いた') {
      if (this.syncing) return;
      this.syncing = true;
      this.loading = true;
      this.emit({ type: 'changed' });
      try {
        await this.tick();
        await this.出来事を起こす(出来事);
      } finally {
        this.loading = false;
        this.syncing = false;
        this.変わった();
      }
    }
    async 出来事を起こす(名前) {
      const steps = this.defs.出来事[名前] || [];
      const posts = () => this.state.保存.投稿 || {};
      for (const st of steps) {
        if (st.種別 !== '各') continue;
        const key = this.defs.処理[st.処理].入力[0];
        for (const id of this.問い合わせ(st.問い合わせ, {})) {
          if (this.待っている('書込待ち', id)) continue; // もう待っている投稿は、24時間の数え直しになるので起こさない
          await this.run(st.処理, { [key]: id });
        }
      }
      // 直した投稿の書き込みが失敗したまま残っているもの（記録の状態では見分けられない。計画の穴）
      for (const id of [...this.state.再送書く]) {
        const p = posts()[id];
        if (!p || p.状態 !== '投稿済') this.state.再送書く = this.state.再送書く.filter((x) => x !== id);
        else if (this.待っている('書込待ち', id)) await this.外部を実行({ 名前: 'Dropbox.書く', 引数: { 投稿ID: id } }); // 待ちは残っているので、書き込みだけやり直す
        else await this.run('反映の要求', { 投稿ID: id });
      }
      for (const id of [...this.state.再送消す]) await this.外部を実行({ 名前: 'Dropbox.消す', 引数: { 投稿ID: id } });
      await this.idle();
      const 取り込む処理 = new Set(steps.filter((s) => s.種別 === '外から').map((s) => s.処理));
      if (取り込む処理.size) await this.取り込む(取り込む処理);
    }
    async 取り込む(許す) {
      let list;
      const 記録済み = new Set(Object.values(this.state.保存.投稿 || {}).filter((p) => p.記録 === '記録済').map((p) => p.投稿ID));
      try {
        list = await this.dropbox.listPosts();
        this.ネットワークの結果(true);
      } catch (err) {
        this.ネットワークの結果(false, err);
        if (!err.network) this.お知らせ('error', '別の端末の内容を取り込めませんでした。原因：' + (err.message || err));
        return;
      }
      const remoteIds = new Set(list.map((x) => x.id));
      for (const { id, rev } of list) {
        if (this.state.改訂[id] === rev) continue;
        let r;
        try { r = await this.dropbox.getPost(id); } catch (err) { this.ネットワークの結果(false, err); return; }
        const local = (this.state.保存.投稿 || {})[id];
        for (const f of r.添付 || []) {
          if (!this.state.部品[f]) {
            try { this.state.部品[f] = { 種類: 'file', 名前: (r.添付名 || {})[f] || f, dataURL: await this.dropbox.getFile(f), 上げた: true }; } catch (err) { /* 画像は次回 */ }
          }
        }
        for (const l of r.リンク || []) if (!this.state.部品[l]) this.state.部品[l] = { 種類: 'link', url: (r.リンク先 || {})[l] || '' };
        if (!local) {
          if (許す.has('投稿の取り込み')) await this.run('投稿の取り込み', { 本文: r.本文, 添付: r.添付 || [], リンク: r.リンク || [], 書いた日時: r.書いた日時, 操作日時: r.最後に操作した日時 }, id);
        } else if (許す.has('直しの取り込み') && (local.状態 === '投稿済' || local.状態 === '削除済') && r.最後に操作した日時 > local.最後に操作した日時) {
          await this.run('直しの取り込み', { 投稿ID: id, 直し日時: r.最後に操作した日時, 本文: r.本文 });
        }
        this.state.改訂[id] = rev;
      }
      // 別の端末で消えた（Dropboxから無くなった）投稿を取り込む。確かに記録済みだったものだけ見る
      for (const id of 記録済み) {
        const p = this.state.保存.投稿[id];
        if (許す.has('消しの取り込み') && !remoteIds.has(id) && p && p.状態 === '投稿済' && p.記録 === '記録済') {
          await this.run('消しの取り込み', { 投稿ID: id, 操作日時: this.now() });
        }
      }
    }
  }

  const api = { Engine, MemStorage };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.SoloRuntime = api;
})(typeof window !== 'undefined' ? window : globalThis);
