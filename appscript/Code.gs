/**
 * SamaHealth SWHT-PP-003: pull the CRF export from Supabase into this Google Sheet, and save CSV snapshots to Drive.
 *
 * Setup (once): Extensions > Apps Script, paste this file, then Project Settings > Script properties:
 *   SUPABASE_URL        https://<project>.supabase.co
 *   SUPABASE_ANON_KEY   the project's anon (public) key
 *   EXPORTER_EMAIL      the exporter account (role "exporter": read-only, no identity access)
 *   EXPORTER_PASSWORD   its password
 *   CSV_FOLDER_ID       optional Drive folder id for CSV snapshots (default: My Drive root)
 * Then reload the sheet and use the SamaHealth menu: "Install hourly refresh" once.
 *
 * The hourly refresh also keeps the free Supabase project active (free projects pause after 7 idle days), and the
 * weekly CSV snapshot is the off-site backup the free plan does not provide. Names never come here: the export view
 * has no identity columns and the exporter account cannot read the identity table.
 */

var PAGE_SIZE = 1000;
var SHEET_DATA = 'CRF';
var SHEET_LOG = 'Sync log';
var VIEW = 'crf_export';

function onOpen() {
  SpreadsheetApp.getUi().createMenu('SamaHealth')
    .addItem('Refresh now', 'refreshNow')
    .addItem('Save CSV snapshot to Drive', 'downloadCsv')
    .addSeparator()
    .addItem('Install hourly refresh + weekly CSV', 'installTriggers')
    .addToUi();
}

function config_() {
  var p = PropertiesService.getScriptProperties();
  var cfg = {
    url: (p.getProperty('SUPABASE_URL') || '').replace(/\/+$/, ''),
    key: p.getProperty('SUPABASE_ANON_KEY') || '',
    email: p.getProperty('EXPORTER_EMAIL') || '',
    password: p.getProperty('EXPORTER_PASSWORD') || '',
    folder: p.getProperty('CSV_FOLDER_ID') || ''
  };
  var missing = ['url', 'key', 'email', 'password'].filter(function (k) { return !cfg[k]; });
  if (missing.length) throw new Error('Missing script properties: ' + missing.join(', '));
  return cfg;
}

function signIn_(cfg) {
  var r = UrlFetchApp.fetch(cfg.url + '/auth/v1/token?grant_type=password', {
    method: 'post', contentType: 'application/json', muteHttpExceptions: true,
    headers: { apikey: cfg.key },
    payload: JSON.stringify({ email: cfg.email, password: cfg.password })
  });
  if (r.getResponseCode() !== 200) throw new Error('Supabase sign-in failed: ' + r.getResponseCode() + ' ' + r.getContentText());
  return JSON.parse(r.getContentText()).access_token;
}

/** All rows of the export view, paged with PostgREST Range headers (Supabase returns at most 1000 rows a request). */
function fetchAll_(cfg, token) {
  var rows = [];
  for (var start = 0; ; start += PAGE_SIZE) {
    var r = UrlFetchApp.fetch(cfg.url + '/rest/v1/' + VIEW + '?select=*&order=pid.asc', {
      method: 'get', muteHttpExceptions: true,
      headers: { apikey: cfg.key, Authorization: 'Bearer ' + token, 'Range-Unit': 'items', Range: start + '-' + (start + PAGE_SIZE - 1) }
    });
    var code = r.getResponseCode();
    if (code === 416) break;                                  // range past the end
    if (code !== 200 && code !== 206) throw new Error('Export fetch failed: ' + code + ' ' + r.getContentText());
    var page = JSON.parse(r.getContentText());
    rows = rows.concat(page);
    if (page.length < PAGE_SIZE) break;
  }
  return rows;
}

/** Header = keys in first-seen order across all records; values flattened for a cell. */
function buildTable_(records) {
  var header = [], seen = {};
  records.forEach(function (rec) {
    Object.keys(rec).forEach(function (k) { if (!seen[k]) { seen[k] = true; header.push(k); } });
  });
  var body = records.map(function (rec) {
    return header.map(function (k) { return cell_(rec[k]); });
  });
  return { header: header, body: body };
}

function cell_(v) {
  if (v === null || v === undefined) return '';
  if (typeof v === 'object') return JSON.stringify(v);
  return v;
}

function csvEscape_(v) {
  var s = String(cell_(v));
  if (/[",\r\n]/.test(s) || /^\s|\s$/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
  return s;
}

function toCsv_(table) {
  var lines = [table.header.map(csvEscape_).join(',')];
  table.body.forEach(function (row) { lines.push(row.map(csvEscape_).join(',')); });
  return lines.join('\r\n') + '\r\n';
}

function sheet_(name) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  return ss.getSheetByName(name) || ss.insertSheet(name);
}

function log_(status, n, ms, note) {
  var s = sheet_(SHEET_LOG);
  if (s.getLastRow() === 0) s.appendRow(['time', 'status', 'rows', 'seconds', 'note']);
  s.appendRow([new Date(), status, n, Math.round(ms / 100) / 10, note || '']);
}

function pull_() {
  var cfg = config_();
  var token = signIn_(cfg);
  return { cfg: cfg, table: buildTable_(fetchAll_(cfg, token)) };
}

function refreshNow() {
  var t0 = Date.now();
  try {
    var t = pull_().table;
    var s = sheet_(SHEET_DATA);
    s.clearContents();
    var values = [t.header].concat(t.body);
    if (t.header.length) {
      for (var i = 0; i < values.length; i += 500) {             // chunked writes stay inside Sheets' payload limits
        var chunk = values.slice(i, i + 500);
        s.getRange(i + 1, 1, chunk.length, t.header.length).setValues(chunk);
      }
      s.setFrozenRows(1);
    }
    log_('ok', t.body.length, Date.now() - t0, '');
    return t.body.length;
  } catch (e) {
    log_('error', 0, Date.now() - t0, String(e && e.message || e));
    throw e;
  }
}

function writeCsv_(interactive) {
  var p = pull_();
  var name = 'crf_export_' + Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyy-MM-dd_HHmm') + '.csv';
  var blob = Utilities.newBlob(toCsv_(p.table), 'text/csv', name);
  var file = p.cfg.folder ? DriveApp.getFolderById(p.cfg.folder).createFile(blob) : DriveApp.createFile(blob);
  log_('csv', p.table.body.length, 0, name);
  if (interactive) {
    var html = HtmlService.createHtmlOutput('<p>Saved <a target="_blank" href="' + file.getUrl() + '">' + name + '</a> (' +
      p.table.body.length + ' rows). Open it in Drive and use File &gt; Download.</p>').setWidth(420).setHeight(120);
    SpreadsheetApp.getUi().showModalDialog(html, 'CSV snapshot');
  }
  return file.getUrl();
}

function downloadCsv() { return writeCsv_(true); }

function weeklySnapshot() { return writeCsv_(false); }

function installTriggers() {
  ScriptApp.getProjectTriggers().forEach(function (tr) {
    if (['refreshNow', 'weeklySnapshot'].indexOf(tr.getHandlerFunction()) >= 0) ScriptApp.deleteTrigger(tr);
  });
  ScriptApp.newTrigger('refreshNow').timeBased().everyHours(1).create();
  ScriptApp.newTrigger('weeklySnapshot').timeBased().onWeekDay(ScriptApp.WeekDay.MONDAY).atHour(7).create();
  refreshNow();
}
