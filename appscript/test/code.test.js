// Unit tests for appscript/Code.gs with mocked Google services. Run: node --test appscript/test
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function load(env) {
  const ctx = vm.createContext({ console, JSON, Date, Math, ...env });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'Code.gs'), 'utf8'), ctx);
  return ctx;
}

function fakeServer(nRows) {
  const rows = Array.from({ length: nRows }, (_, i) => ({ pid: 'SWHT-PP-003-' + String(i + 1).padStart(4, '0'), status: 'submitted',
    flags: 'none', bp1_sbp: 120 + (i % 30), notes: i === 0 ? 'said "hi", left early\nnext line' : null }));
  const calls = [];
  const UrlFetchApp = {
    fetch(url, opt) {
      calls.push({ url, opt });
      if (url.includes('/auth/v1/token')) {
        const body = JSON.parse(opt.payload);
        if (body.password !== 'pw') return resp(400, { error: 'invalid_grant' });
        return resp(200, { access_token: 'jwt' });
      }
      assert.equal(opt.headers.Authorization, 'Bearer jwt');
      const [a, b] = opt.headers.Range.split('-').map(Number);
      if (a >= rows.length && rows.length > 0) return resp(416, {});
      return resp(a === 0 && b >= rows.length - 1 ? 200 : 206, rows.slice(a, b + 1));
    }
  };
  return { rows, calls, UrlFetchApp };
}

function resp(code, body) { return { getResponseCode: () => code, getContentText: () => JSON.stringify(body) }; }

function props(over = {}) {
  const p = { SUPABASE_URL: 'https://x.supabase.co/', SUPABASE_ANON_KEY: 'anon', EXPORTER_EMAIL: 'exp@x.org', EXPORTER_PASSWORD: 'pw', ...over };
  return { getScriptProperties: () => ({ getProperty: (k) => (k in p ? p[k] : null) }) };
}

function fakeSheets() {
  const sheets = {};
  const mk = (name) => {
    const s = { name, cells: [], appended: [], frozen: 0,
      clearContents() { this.cells = []; }, getLastRow() { return this.appended.length; },
      appendRow(r) { this.appended.push(r); }, setFrozenRows(n) { this.frozen = n; },
      getRange(r, c, nr, nc) { const self = this; return { setValues(v) { assert.equal(v.length, nr); v.forEach((row, i) => { assert.equal(row.length, nc); self.cells[r - 1 + i] = row; }); } }; } };
    sheets[name] = s; return s;
  };
  return { sheets, SpreadsheetApp: { getActiveSpreadsheet: () => ({ getSheetByName: (n) => sheets[n] || null, insertSheet: mk }), getUi: () => ({}) } };
}

test('pages through 2,500 rows with Range headers and writes one sheet row per visit', () => {
  const srv = fakeServer(2500);
  const sh = fakeSheets();
  const ctx = load({ UrlFetchApp: srv.UrlFetchApp, PropertiesService: props(), SpreadsheetApp: sh.SpreadsheetApp });
  assert.equal(ctx.refreshNow(), 2500);
  const ranges = srv.calls.filter((c) => c.opt.headers.Range).map((c) => c.opt.headers.Range);
  assert.deepEqual(ranges, ['0-999', '1000-1999', '2000-2999']);
  assert.equal(srv.calls[0].url, 'https://x.supabase.co/auth/v1/token?grant_type=password');
  const data = sh.sheets.CRF.cells;
  assert.equal(data.length, 2501);
  assert.deepEqual(Array.from(data[0]), ['pid', 'status', 'flags', 'bp1_sbp', 'notes']);   // arrays from the VM realm
  assert.equal(data[2500][0], 'SWHT-PP-003-2500');
  assert.equal(data[2][4], '');                                   // null becomes an empty cell
  assert.equal(sh.sheets['Sync log'].appended[1][1], 'ok');
});

test('an exact multiple of the page size ends on the 416 response', () => {
  const srv = fakeServer(1000);
  const ctx = load({ UrlFetchApp: srv.UrlFetchApp, PropertiesService: props(), SpreadsheetApp: fakeSheets().SpreadsheetApp });
  assert.equal(ctx.refreshNow(), 1000);
});

test('CSV escaping follows RFC 4180', () => {
  const ctx = load({});
  const csv = ctx.toCsv_({ header: ['a', 'b'], body: [['x,y', 'say "hi"'], ['line1\nline2', 3], [null, { k: 1 }]] });
  assert.equal(csv, 'a,b\r\n"x,y","say ""hi"""\r\n"line1\nline2",3\r\n,"{""k"":1}"\r\n');
});

test('missing configuration and bad credentials fail loudly and are logged', () => {
  const sh = fakeSheets();
  let ctx = load({ UrlFetchApp: fakeServer(1).UrlFetchApp, PropertiesService: props({ EXPORTER_PASSWORD: null }), SpreadsheetApp: sh.SpreadsheetApp });
  assert.throws(() => ctx.refreshNow(), /Missing script properties: password/);
  ctx = load({ UrlFetchApp: fakeServer(1).UrlFetchApp, PropertiesService: props({ EXPORTER_PASSWORD: 'wrong' }), SpreadsheetApp: sh.SpreadsheetApp });
  assert.throws(() => ctx.refreshNow(), /sign-in failed: 400/);
  assert.equal(sh.sheets['Sync log'].appended.at(-1)[1], 'error');
});
