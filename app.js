'use strict';
const $=id=>document.getElementById(id), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const TASKS=['營外加油','營外裝備載運','救護待命','彈藥載運','人員載運'];
const STATUS=['正常派車','不派','臨時不派','另有任務','待命','故障維修','空車'];
const TYPES={'1':'輕戰','2':'悍馬','3':'中戰','8':'野救'}; const ORDER=['保','營','補','指','連','衛','空車'];
const KEY='dispatch-mobile-v5-local'; const clone=o=>JSON.parse(JSON.stringify(o));
const dateNow=()=>new Date(Date.now()+8*3600000).toISOString().slice(0,10); const dow=d=>new Date(d+'T00:00:00Z').getUTCDay();
const idNorm=s=>String(s).normalize('NFKC').toUpperCase().replace(/[－—–−]/g,'-').replace(/\s/g,''); const valid=id=>/^軍[A-Z0-9]+-\d+$/.test(id); const excluded=id=>/^軍9-/.test(id);
const raw=``;
function parse(text){let unit='未分組', rows=[], issues=[], ignored=[], rule=[];let seen=new Set();const lines=text.split(/\r?\n/); for(let i=0;i<lines.length;i++){let line=lines[i].normalize('NFKC').trim();if(!line)continue;const m=line.match(/軍\s*[A-Za-z0-9]+\s*[-－—–−]\s*\d+/i);if(!m){if(/^(左.{0,5}車長|左車長|日期|派車確認|北測派車|列管|應派)/.test(line))continue;if(/^(註|備註|注)[:：]/.test(line)){rule.push(line);continue}let h=line.split(/[｜|]/)[0].replace(/^[🔵🟢🔶●◆■#*\s]+/u,'').replace(/[:：\s]+$/,'').replace(/\s*\(\d+\s*(台|輛).*?\)$/,'').trim();if(ORDER.includes(h)||/^(?:[一二三四五六七八九十\d]+排|.{1,8}(?:排|組|班|連|營))$/.test(h)){unit=h;continue}issues.push(`第${i+1}行未辨識：${line}`);continue}const id=idNorm(m[0]);if(excluded(id)){ignored.push(id);continue}if(seen.has(id)){issues.push(`第${i+1}行重複車號：${id}（保留第一筆）`);continue}seen.add(id);let tail=line.slice(m.index+m[0].length).trim().replace(/^[:：\s]+/,'');let status=unit==='空車'?'空車':'正常派車',note='',task='',captain='',driver='';const nm=tail.match(/(?:備註|任務)[:：]\s*(.*)$/);if(nm){const fields=tail.slice(nm.index);for(const f of fields.matchAll(/(備註|任務)[:：]\s*(.*?)(?=\s*(?:備註|任務)[:：]|$)/g)){if(f[1]==='任務')task=f[2].trim();else note=f[2].trim()}tail=tail.slice(0,nm.index).trim()}const sm=tail.match(/(?:[（(【[]\s*)?(臨時不派|另有任務|故障維修|正常派車|不派|待命|空車)(?:\s*[）)】\]])?/);if(sm){status=sm[1];tail=(tail.slice(0,sm.index)+tail.slice(sm.index+sm[0].length)).trim()}const extra=tail.match(/[（(]([^）)]+)[）)]\s*$/);if(extra){note=[note,extra[1]].filter(Boolean).join('；');tail=tail.slice(0,extra.index).trim()}const names=tail.split(/\s*[、，,／/]\s*/).filter(Boolean);if(names.length>=2){captain=names[0];driver=names[1];if(names.length>2){note=[note,names.slice(2).join('、')].filter(Boolean).join('；');issues.push(`${id}：多於兩個欄位，已放入備註`)}}else if(tail){const parts=tail.split(/\s+/);captain=parts[0];driver=parts[1]||'';if(parts.length>2)note=[note,parts.slice(2).join(' ')].filter(Boolean).join('；')}if(status==='正常派車'&&(!captain||!driver))issues.push(`${id}：車長或駕駛未填`);rows.push({id,unit,status,captain,driver,note,task,checked:/^\s*(?:☑|✅|\[x\])/i.test(line)})}for(const r of rule){const m=r.match(/(?:註|備註|注)[:：]\s*(軍[A-Z0-9]+-\d+|\d+)\s*(?:禮拜|星期|週)一車長派([^、，,]+)[、，,]\s*二[～~至-]五派(.+)$/i);const matches=m?rows.filter(c=>/^軍/i.test(m[1])?c.id===idNorm(m[1]):c.id.endsWith(m[1])):[];if(matches.length===1){matches[0].rule={mon:m[2].trim(),week:m[3].trim()}}else issues.push('未自動套用的規則：'+r)}if(rows.some(c=>c.unit==='未分組'))issues.push('部分車輛未分組，請確認排組標題。');return {rows,issues,ignored}}
function fixed(rows){return rows.map(c=>({...c,checked:false}))}function dayRows(base,date){return fixed(base).map(c=>({...c,captain:c.rule?(dow(date)===1?c.rule.mon:dow(date)>=2&&dow(date)<=5?c.rule.week:'待確認'):c.captain}))}
function initial(){const base=fixed(parse(raw).rows),date=dateNow();return {version:5,base,date,rows:dayRows(base,date),history:{}}}
function validRows(rows){return Array.isArray(rows)&&rows.every(c=>c&&valid(c.id)&&!excluded(c.id)&&typeof c.unit==='string'&&STATUS.includes(c.status)&&['captain','driver','note'].every(k=>typeof c[k]==='string')&&typeof c.checked==='boolean'&&(c.task===undefined||typeof c.task==='string')&&(!c.rule||(typeof c.rule.mon==='string'&&typeof c.rule.week==='string')))&&new Set(rows.map(c=>c.id)).size===rows.length}function validState(s){return s&&s.version===5&&validDate(s.date)&&validRows(s.base)&&validRows(s.rows)&&s.history&&typeof s.history==='object'&&!Array.isArray(s.history)&&Object.entries(s.history).every(([d,r])=>validDate(d)&&validRows(r))}
function migrate(s){if(s.lastUpdate&&!s.updateByDate){s.updateByDate={[s.lastUpdate.date||s.date]:{...s.lastUpdate,date:s.lastUpdate.date||s.date}}}for(const rows of [s.base,s.rows,...Object.values(s.history)])for(const c of rows){if(c.task===undefined){c.task=''}}return s}
const storageMessages = {
  recovery: '安全復原模式：本機資料格式異常，原始內容已保留。可下載原始內容，或匯入有效的備份。',
  unreadable: '安全復原模式：無法讀取本機資料。原始資料未被變更，請確認瀏覽器允許本機儲存後重新載入，再視需要匯入備份。',
  failure: '本機儲存失敗，本次異動未儲存。請確認瀏覽器儲存權限或剩餘空間後重試。',
  conflict: '另一個分頁已變更本機資料。本頁已停止寫入，請重新載入後再操作。',
  unsupported: '此瀏覽器無法安全處理多分頁寫入。請使用支援 Web Locks 的瀏覽器開啟本網站。'
};
let state = initial();
let storedText;
let storageProblem = '';
let writing = false;
let restoreFailed = false;

try {
  storedText = localStorage.getItem(KEY);
  if (storedText !== null) {
    const loaded = JSON.parse(storedText);
    if (!validState(loaded)) throw new Error('Invalid dispatch data');
    state = migrate(loaded);
  }
} catch {
  storageProblem = storedText === undefined ? 'unreadable' : 'recovery';
}
if (!navigator.locks && !storageProblem) storageProblem = 'unsupported';

function showStorageStatus() {
  const message = (storageMessages[storageProblem] || '') + (storageProblem === 'recovery' && restoreFailed
    ? ' 備份還原未能儲存，請檢查瀏覽器權限或剩餘空間後重試。' : '');
  $('storageBanner').hidden = !message;
  if ($('storageMessage').textContent !== message) $('storageMessage').textContent = message;
  if ($('editorStorage').textContent !== message) $('editorStorage').textContent = message;
  $('editorStorage').hidden = !message;
  $('reloadStorage').hidden = !['unreadable', 'conflict'].includes(storageProblem);
  $('recoverStorage').hidden = storageProblem !== 'recovery';
  $('downloadRaw').hidden = storageProblem !== 'recovery';
  $('storage').textContent = message || '資料保存在此瀏覽器。';
}

function setStorageProblem(problem) {
  storageProblem = problem;
  showStorageStatus();
}

function canWrite(restore = false) {
  return !storageProblem || storageProblem === 'failure' || (restore && storageProblem === 'recovery');
}

async function commitChange(change, {restore = false} = {}) {
  if (writing || !canWrite(restore)) return false;
  if (!navigator.locks) {
    if (storageProblem === 'recovery') toast(storageMessages.unsupported);
    else setStorageProblem('unsupported');
    return false;
  }
  writing = true;
  try {
    // Serialize writers in this origin. Compare the raw snapshot inside the lock,
    // so a tab holding an older view cannot replace the latest saved records.
    return await navigator.locks.request(KEY, () => {
      if (!canWrite(restore)) return false;
      if (localStorage.getItem(KEY) !== storedText) {
        setStorageProblem('conflict');
        return false;
      }
      const draft = change(clone(state));
      const nextText = JSON.stringify(draft);
      localStorage.setItem(KEY, nextText);
      storedText = nextText;
      state = draft;
      setStorageProblem('');
      return true;
    });
  } catch {
    if (storageProblem === 'recovery') {
      restoreFailed = true;
      showStorageStatus();
    } else {
      setStorageProblem('failure');
    }
    return false;
  } finally {
    writing = false;
  }
}

window.addEventListener('storage', event => {
  if (event.key !== KEY && event.key !== null) return;
  if (storedText === undefined) return;
  try {
    if (event.storageArea === localStorage && localStorage.getItem(KEY) !== storedText) {
      setStorageProblem('conflict');
    }
  } catch {
    if (canWrite()) setStorageProblem('failure');
  }
});
function validDate(d){return typeof d==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(d)&&!Number.isNaN(Date.parse(d+'T00:00:00Z'))&&new Date(d+'T00:00:00Z').toISOString().slice(0,10)===d&&d>='1900-01-01'&&d<='9999-12-31'}
let followingToday=true;
function moveDate(draft, date) {
  if (draft.date === date) return draft;
  draft.history[draft.date] = draft.rows;
  draft.rows = Object.prototype.hasOwnProperty.call(draft.history, date)
    ? draft.history[date] : dayRows(draft.base, date);
  delete draft.history[date];
  draft.date = date;
  return draft;
}

function clearDrafts(){if($('editor').open)$('editor').close();editing=null;pendingImport=null;$('preview').hidden=true;$('source').value='';previewDate='';$('historyText').hidden=true}

async function chooseDate(date) {
  if (!validDate(date)) {
    toast('請輸入有效日期');
    renderDateControls();
    return;
  }
  if (date !== state.date) {
    if (!await commitChange(draft => moveDate(draft, date))) {
      renderDateControls();
      return;
    }
    clearDrafts();
  }
  setFollowingDate(date);
  render();
}

function setFollowingDate(date) {
  followingToday = date === dateNow();
  preferences.pinnedDate = followingToday ? null : date;
  savePreferences();
}

function needsRollover() {
  return followingToday && state.date !== dateNow();
}

async function rollover() {
  if (!needsRollover() || writing || storageProblem) return;
  if (await commitChange(draft => moveDate(draft, dateNow()))) {
    clearDrafts();
    render();
  }
}

function guardDay() {
  if (!needsRollover()) return false;
  if (storageProblem === 'failure' && !writing) {
    // An explicit retry can probe storage again after the browser recovers.
    commitChange(draft => moveDate(draft, dateNow())).then(saved => {
      if (saved) {
        clearDrafts();
        render();
      }
    });
  } else {
    rollover();
  }
  toast('日期已跨日，請確認作業日期後再操作。');
  return true;
}

let filter='all',pendingImport=null,editing=null,toastTimer;
function toast(s){if($('editor').open){$('editorMessage').textContent=s;return}$('toast').textContent=s;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>{$('toast').hidden=true},3200)}function normal(c){return c.status==='正常派車'}function type(c){const k=c.id.match(/^軍([A-Z0-9]+)-/)[1];return TYPES[k]||'軍'+k}function groups(rows){return [...new Set(rows.map(c=>c.unit))].sort((a,b)=>(ORDER.includes(a)?ORDER.indexOf(a):99)-(ORDER.includes(b)?ORDER.indexOf(b):99))}function selectedRows(){const mode=$('statMode').value;return state.rows.filter(c=>mode==='all'||mode==='normal'&&normal(c)||mode==='done'&&normal(c)&&c.checked||mode==='pending'&&normal(c)&&!c.checked||mode==='other'&&c.status==='另有任務')}
const TYPES_IN_ORDER = ['輕戰', '悍馬', '中戰', '野救'];
const UI_KEY = 'dispatch-mobile-v92-ui';
const settingsDefaults = {theme: 'system', fontSize: 'normal', pinnedDate: null};
let preferences = {...settingsDefaults};
try {
  const saved = JSON.parse(localStorage.getItem(UI_KEY));
  if (saved && typeof saved === 'object') preferences = {...preferences, ...saved};
} catch {
  // Display preferences are optional.
}
followingToday = preferences.pinnedDate !== state.date;
let selectedView = 'overview';
let previewDate = '';
const collapsedUnits = new Set();

function savePreferences() {
  try {
    localStorage.setItem(UI_KEY, JSON.stringify(preferences));
  } catch {
    // Keep the current display settings for this session.
  }
}

function applyDisplay() {
  const systemTheme = window.matchMedia('(prefers-color-scheme: dark)');
  const theme = $('theme');
  const font = $('fontSize');
  theme.value = preferences.theme;
  font.value = preferences.fontSize;
  if (!theme.value) theme.value = settingsDefaults.theme;
  if (!font.value) font.value = settingsDefaults.fontSize;
  const update = () => {
    document.documentElement.dataset.theme = theme.value === 'system'
      ? (systemTheme.matches ? 'dark' : 'light') : theme.value;
    document.documentElement.dataset.font = font.value;
  };
  theme.onchange = font.onchange = () => {
    preferences.theme = theme.value;
    preferences.fontSize = font.value;
    update();
    savePreferences();
  };
  if (systemTheme.addEventListener) systemTheme.addEventListener('change', update);
  else systemTheme.addListener(update);
  update();
}

function showPage(view) {
  if (view === selectedView) return;
  document.getElementById(selectedView).hidden = true;
  document.getElementById(view).hidden = false;
  const active = $('navigation').querySelector('[aria-current]');
  active.removeAttribute('aria-current');
  $('navigation').querySelector('[data-view="' + view + '"]').setAttribute('aria-current', 'page');
  selectedView = view;
  window.scrollTo(0, 0);
}

function dateLabel(date) {
  return date === dateNow() ? '今天' : date < dateNow() ? '過去日期' : '未來日期';
}

function counts(rows) {
  const required = rows.filter(normal);
  return {total: rows.length, required: required.length, done: required.filter(c => c.checked).length};
}

function typeOrder(rows) {
  return [...new Set([...TYPES_IN_ORDER, ...rows.map(type).sort()])];
}

function vehicleCounts(rows, types) {
  const counts = new Map(types.map(t => [t, 0]));
  for (const car of rows) {
    const name = type(car);
    counts.set(name, counts.get(name) + 1);
  }
  return counts;
}

function chart(target, items) {
  const max = Math.max(1, ...items.map(([, count]) => count));
  $(target).innerHTML = items.map(([label, count]) =>
    `<div class="chart-row"><div class="row between"><span>${esc(label)}</span><b>${count} 輛</b></div><progress value="${count}" max="${max}" aria-label="${esc(label)}：${count} 輛"></progress></div>`
  ).join('');
}

function renderStats() {
  const rows = selectedRows();
  const types = typeOrder(state.rows);
  const totals = vehicleCounts(rows, types);
  const cells = values => types.map(t => `<td>${values.get(t)}</td>`).join('');
  const units = groups(state.rows).map(unit => {
    const matching = rows.filter(c => c.unit === unit);
    return `<tr><th scope="row">${esc(unit)}</th>${cells(vehicleCounts(matching, types))}<td>${matching.length}</td></tr>`;
  });
  $('stats').innerHTML = `<table><thead><tr><th scope="col">排組</th>${types.map(t => `<th scope="col">${esc(t)}</th>`).join('')}<th scope="col">合計</th></tr></thead><tbody>${units.join('')}</tbody><tfoot><tr><th scope="row">合計</th>${cells(totals)}<td>${rows.length}</td></tr></tfoot></table>`;
  chart('typeChart', [...totals]);
  const tasks = taskCounts(rows);
  tasks.push(['未指定任務', rows.filter(c => !c.task).length]);
  chart('taskStats', tasks);
}

function renderOverview(rows, units) {
  const {total, required, done} = counts(rows);
  const percentage = required ? Math.round(done / required * 100) : 0;
  $('completionRing').style.setProperty('--progress', percentage + '%');
  $('completionRing').setAttribute('aria-label', required ? `完成率 ${percentage}%` : '沒有應派車輛');
  $('completionValue').textContent = required ? percentage + '%' : '—';
  $('completionLabel').textContent = required ? `已派 ${done} 輛，共 ${required} 輛應派` : '目前沒有應派車輛';
  const metric = ([name, count]) => `<div class="metric"><b>${count}</b><span>${name}</span></div>`;
  const countStatus = (...statuses) => rows.filter(c => statuses.includes(c.status)).length;
  $('metrics').innerHTML = [['列管', total], ['應派', required], ['已派', done], ['未確認', required - done]].map(metric).join('');
  $('secondaryMetrics').innerHTML = [
    ['另有任務', countStatus('另有任務')], ['空車', countStatus('空車')],
    ['不派', countStatus('不派', '臨時不派')], ['待命', countStatus('待命')],
    ['維修', countStatus('故障維修')]
  ].map(metric).join('');
  $('groupProgress').innerHTML = units.map(unit => {
    const group = counts(rows.filter(c => c.unit === unit));
    return `<button class="unit-progress" type="button" data-unit="${esc(unit)}"><span class="row between"><strong>${esc(unit)}</strong><small>已派 ${group.done} / ${group.required}・列管 ${group.total}</small></span><progress value="${group.done}" max="${group.required || 1}" aria-label="排組派車進度"></progress></button>`;
  }).join('') || '<p class="muted">尚無排組。可匯入名單或新增車輛。</p>';

  const people = new Map();
  for (const car of rows.filter(c => normal(c) || c.status === '另有任務')) {
    for (const name of [car.captain, car.driver].map(x => x.replace(/⚠️?/g, '').trim())) {
      if (!name || name === '待確認') continue;
      if (!people.has(name)) people.set(name, []);
      people.get(name).push(car.id);
    }
  }
  const warnings = [...people].filter(([, ids]) => ids.length > 1)
    .map(([name, ids]) => `${name} 重複編組：${ids.join('、')}`);
  const missing = rows.filter(c => normal(c) && (!c.captain || !c.driver || c.captain === '待確認'));
  if (missing.length) warnings.push('人員未確認：' + missing.map(c => c.id).join('、'));
  $('warnings').hidden = !warnings.length;
  $('warningTitle').textContent = `編組警示（${warnings.length}）`;
  $('warning').innerHTML = warnings.map(w => `<li>${esc(w)}</li>`).join('');
}

function renderHistory() {
  const dates = [...new Set([state.date, ...Object.keys(state.history)])].sort().reverse();
  $('historyList').innerHTML = dates.map(date => {
    const current = date === state.date;
    const {total, done} = counts(current ? state.rows : state.history[date]);
    return `<div class="history-item"><button type="button" data-date="${date}" ${current ? 'aria-current="date"' : ''}><strong>${date}</strong> <span class="badge">${current ? '操作中' : dateLabel(date)}</span><br><small>列管 ${total}・已派 ${done}</small></button><button type="button" data-preview-date="${date}" aria-expanded="${previewDate === date}">預覽</button></div>`;
  }).join('');
  const preview = previewDate === state.date ? state.rows : state.history[previewDate];
  $('historyText').hidden = !preview;
  $('historyText').textContent = preview ? report(previewDate, preview) : '';
}

function render() {
  const rows = state.rows;
  const units = groups(rows);
  const oldUnit = $('unit').value;
  $('unit').innerHTML = '<option value="">全部排組</option>' + units.map(u => `<option>${esc(u)}</option>`).join('');
  $('unit').value = units.includes(oldUnit) ? oldUnit : '';
  $('unitOptions').innerHTML = [...new Set([...ORDER, ...units])].map(u => `<option value="${esc(u)}">`).join('');
  renderDateControls();
  renderOverview(rows, units);
  renderStats();
  renderList();
  renderHistory();
  showStorageStatus();
}

const filters = {
  all: () => true,
  pending: c => normal(c) && !c.checked,
  done: c => normal(c) && c.checked,
  special: c => !normal(c),
  empty: c => c.status === '空車'
};

function renderVehicle(car) {
  const id = esc(car.id);
  const status = normal(car) ? (car.checked ? '已確認' : '未確認') : car.status;
  const details = [car.task && '任務：' + car.task, car.note && '備註：' + car.note];
  return `<div class="car ${car.checked ? 'done' : ''}"><label><input type="checkbox" data-check="${id}" ${car.checked ? 'checked' : ''} aria-label="確認 ${id}"><span><b>${id}</b><span class="badge ${normal(car) ? '' : 'special'}">${esc(status)}</span><small>${esc(car.captain || '未指定')}、${esc(car.driver || '未指定')}</small>${details.filter(Boolean).map(d => `<small>${esc(d)}</small>`).join('')}</span></label><button type="button" class="edit" data-edit="${id}" aria-label="修改 ${id}">修改</button></div>`;
}

function renderList() {
  const query = $('search').value.trim();
  const unit = $('unit').value;
  const matching = state.rows.filter(c => (!unit || c.unit === unit) && filters[filter](c) &&
    (!query || [c.id, c.captain, c.driver, c.task, c.note, c.status, type(c), c.checked ? '已確認' : '未確認'].join(' ').includes(query)));
  $('list').innerHTML = groups(matching).map(group => {
    const full = state.rows.filter(c => c.unit === group);
    const {total, required, done} = counts(full);
    const chips = [...vehicleCounts(full, typeOrder(full))].map(([name, value]) =>
      `<span class="badge">${esc(name)} ${value}</span>`).join('');
    return `<details class="panel unit-card" data-group="${esc(group)}" ${collapsedUnits.has(group) ? '' : 'open'}><summary>${esc(group)} <small>已派 ${done}/${required}・列管 ${total}</small></summary><div class="chips">${chips}</div>${matching.filter(c => c.unit === group).map(renderVehicle).join('')}</details>`;
  }).join('') || '<section class="panel muted">沒有符合條件的車輛。</section>';
}

function selectFilter(value) {
  filter = value;
  for (const button of $('filters').querySelectorAll('button')) {
    button.setAttribute('aria-pressed', button.dataset.filter === filter);
  }
  renderList();
}

function bindInterface() {
  $('navigation').onclick = event => {
    const button = event.target.closest('[data-view]');
    if (button) showPage(button.dataset.view);
  };
  $('overview').onclick = event => {
    const unit = event.target.closest('[data-unit]');
    if (unit) {
      $('unit').value = unit.dataset.unit;
      $('search').value = '';
      collapsedUnits.delete(unit.dataset.unit);
      selectFilter('all');
      showPage('dispatch');
      return;
    }
    const quick = event.target.closest('[data-quick]')?.dataset.quick;
    if (quick === 'export') $('export').click();
    if (quick === 'new') {
      $('unit').value = '';
      renderList();
      showPage('dispatch');
      edit(null);
    }
    if (quick === 'import') {
      showPage('dispatch');
      $('importPanel').open = true;
      $('importPanel').scrollIntoView({block: 'start'});
    }
  };
  $('historyList').onclick = event => {
    const button = event.target.closest('button');
    if (button?.dataset.date) chooseDate(button.dataset.date);
    if (button?.dataset.previewDate) {
      const date = button.dataset.previewDate;
      previewDate = previewDate === date ? '' : date;
      renderHistory();
      $('historyList').querySelector(`[data-preview-date="${date}"]`).focus();
    }
  };
  const viewport = window.visualViewport;
  if (viewport) {
    const resizeEditor = () => {
      const editor = $('editor');
      editor.style.setProperty('--editor-height', viewport.height + 'px');
      editor.style.bottom = Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop) + 'px';
    };
    viewport.addEventListener('resize', resizeEditor);
    viewport.addEventListener('scroll', resizeEditor);
    resizeEditor();
  }
}
async function changeCheck(id, checked) {
  if (guardDay() || !canWrite()) {
    renderList();
    return;
  }
  await commitChange(draft => {
    draft.rows.find(car => car.id === id).checked = checked;
    return draft;
  });
  render();
}
function edit(id){if(guardDay()||!canWrite())return;editing=id;$('editorMessage').textContent='';const c=state.rows.find(c=>c.id===id)||{id:'',unit:$('unit').value||'保',status:'正常派車',captain:'',driver:'',note:''};$('editTitle').textContent=(id?'修改 '+id:'新增車輛')+'｜'+state.date;for(const [k,v] of Object.entries({eId:c.id,eUnit:c.unit,eStatus:c.status,eCaptain:c.captain,eDriver:c.driver,eTask:c.note}))$(k).value=v;$('eTaskChoice').value=TASKS.includes(c.task)?c.task:c.task?'custom':'';$('eTaskCustom').value=c.task&&!TASKS.includes(c.task)?c.task:'';$('eTaskCustom').hidden=$('eTaskChoice').value!=='custom';$('eFixed').checked=false;$('eFixed').disabled=state.date!==dateNow();$('deleteCar').hidden=!id;$('restoreCar').hidden=!id||!state.base.some(x=>x.id===id);$('editor').showModal()}
function merge(old,rows){const m=new Map(old.map(c=>[c.id,c]));for(const c of rows)m.set(c.id,c);return [...m.values()]}
$('eTaskChoice').onchange=()=>{$('eTaskCustom').hidden=$('eTaskChoice').value!=='custom'};$('eStatus').innerHTML=STATUS.map(s=>`<option>${s}</option>`).join('');$('list').addEventListener('change',e=>{if(e.target.dataset.check)changeCheck(e.target.dataset.check,e.target.checked)});$('list').onclick = event => {
  const summary = event.target.closest('summary');
  if (summary) {
    const group = summary.parentElement;
    if (group.open) collapsedUnits.add(group.dataset.group);
    else collapsedUnits.delete(group.dataset.group);
    return;
  }
  const button = event.target.closest('[data-edit]');
  if (button) edit(button.dataset.edit);
};
$('newCar').onclick = () => edit(null);
$('closeEditor').onclick = () => $('editor').close();
$('editForm').onsubmit = async event => {
  event.preventDefault();
  if (guardDay() || !canWrite()) return;
  const id = idNorm($('eId').value);
  const fixedEdit = $('eFixed').checked && state.date === dateNow();
  if (!valid(id) || excluded(id)) {
    toast('車號格式錯誤，或為已排除的軍9');
    return;
  }
  if (state.rows.some(c => c.id === id && id !== editing) ||
      (fixedEdit && state.base.some(c => c.id === id && id !== editing))) {
    toast('車號已存在');
    return;
  }
  const old = state.rows.find(c => c.id === editing);
  const choice = $('eTaskChoice').value;
  const car = {
    id, unit: $('eUnit').value.trim(), status: $('eStatus').value,
    captain: $('eCaptain').value.trim(), driver: $('eDriver').value.trim(),
    task: choice === 'custom' ? $('eTaskCustom').value.trim() : choice,
    note: $('eTask').value.trim(), checked: false
  };
  if (!car.unit || (choice === 'custom' && !car.task)) {
    toast(!car.unit ? '請填排組' : '請填自訂任務');
    return;
  }
  if (old?.rule) car.rule = old.rule;
  const editingId = editing;
  if (!await commitChange(draft => {
    draft.rows = old ? draft.rows.map(c => c.id === editingId ? car : c) : [...draft.rows, car];
    if (fixedEdit) {
      const baseCar = {...car};
      if (baseCar.rule && old?.captain !== car.captain) delete baseCar.rule;
      draft.base = merge(draft.base.filter(c => c.id !== editingId), [baseCar]);
    }
    return draft;
  })) return;
  $('editor').close();
  render();
  toast('已儲存異動');
};

$('restoreCar').onclick = async () => {
  if (guardDay() || !canWrite()) return;
  const id = editing;
  const baseCar = dayRows(state.base, state.date).find(c => c.id === id);
  if (!baseCar || !await commitChange(draft => {
    draft.rows = draft.rows.map(c => c.id === id ? baseCar : c);
    return draft;
  })) return;
  $('editor').close();
  render();
};

$('deleteCar').onclick = async () => {
  if (guardDay() || !canWrite()) return;
  const permanent = $('eFixed').checked;
  const id = editing;
  const date = state.date;
  if (!confirm(permanent ? `從固定名單及 ${date} 刪除？` : `只從 ${date} 刪除？`)) return;
  if (!await commitChange(draft => {
    draft.rows = draft.rows.filter(c => c.id !== id);
    if (permanent) draft.base = draft.base.filter(c => c.id !== id);
    return draft;
  })) return;
  $('editor').close();
  render();
};
$('filters').onclick = event => {
  const button = event.target.closest('[data-filter]');
  if (button) selectFilter(button.dataset.filter);
};
$('search').oninput=renderList;$('unit').onchange=renderList;$('statMode').onchange=renderStats;
function rosterText(rows){return groups(rows).map(u=>u+'\n'+rows.filter(c=>c.unit===u).map(c=>`${c.id} ${[c.captain,c.driver].filter(Boolean).join('、')}${normal(c)?'':'（'+c.status+'）'}${c.task?' 任務：'+c.task:''}${c.note?' 備註：'+c.note:''}`).join('\n')).join('\n\n')+rows.filter(c=>c.rule).map(c=>'\n註：'+c.id+' 星期一車長派'+c.rule.mon+'、二～五派'+c.rule.week).join('')}
$('sample').onclick=()=>{$('source').value=rosterText(state.base);$('preview').hidden=true;pendingImport=null};$('source').oninput=()=>{$('preview').hidden=true;pendingImport=null};$('parse').onclick=()=>{pendingImport=parse($('source').value);const p=pendingImport;$('parseResult').textContent=`辨識 ${p.rows.length} 輛｜排除軍9 ${p.ignored.length} 輛\n`+groups(p.rows).map(g=>`${g}：${p.rows.filter(c=>c.unit===g).length} 輛`).join('\n')+(p.ignored.length?'\n排除：'+p.ignored.join('、'):'')+(p.issues.length?'\n⚠ 請核對：\n'+p.issues.join('\n'):'')+'\n\n'+rosterText(p.rows);$('apply').disabled=!p.rows.length;$('preview').hidden=false};$('apply').onclick = async () => {
  if (guardDay() || !canWrite() || !pendingImport?.rows.length) return;
  const mode = $('importMode').value;
  const date = state.date;
  if (date !== dateNow() && mode !== 'today') {
    toast('其他日期只可修改該日名單');
    return;
  }
  if (!confirm(`套用至 ${date}？` + (mode === 'merge'
    ? '同車號所選日期的勾選與異動將重置。' : '所選日期現有名單與異動會被替換，建議先備份。'))) return;
  const rows = clone(pendingImport.rows);
  const checked = new Map(rows.map(c => [c.id, c.checked]));
  const daily = dayRows(rows, date).map(c => ({...c, checked: checked.get(c.id)}));
  if (!await commitChange(draft => {
    if (mode === 'merge') {
      draft.base = merge(draft.base, fixed(rows));
      draft.rows = merge(draft.rows, daily);
    } else {
      if (mode === 'replace') draft.base = fixed(rows);
      draft.rows = daily;
    }
    return draft;
  })) return;
  pendingImport = null;
  $('preview').hidden = true;
  $('source').value = '';
  $('importPanel').open = false;
  render();
  toast('已套用名單');
};
function report(date,rows,pending=false){const rr=pending?rows.filter(c=>normal(c)&&!c.checked):rows,n=rows.filter(normal);return [`${date} 派車確認表`,`列管${rows.length}輛／應派${n.length}輛／已派${n.filter(c=>c.checked).length}輛／未確認${n.filter(c=>!c.checked).length}輛`,...STATUS.slice(1).map(s=>`${s}：${rows.filter(c=>c.status===s).length}輛`),...taskCounts(rows).map(([t,n])=>`任務 ${t}：${n}輛`),'左車長、右駕駛',...groups(rr).flatMap(g=>{const a=rr.filter(c=>c.unit===g);return ['',g+'｜'+[...new Set(a.map(type))].map(t=>`${t} ${a.filter(c=>type(c)===t).length}`).join('、'),...a.map(c=>`${c.checked?'☑':'☐'} ${c.id} ${[c.captain,c.driver].filter(Boolean).join('、')}${normal(c)?'':'（'+c.status+'）'}${c.task?' 任務：'+c.task:''}${c.note?' 備註：'+c.note:''}`)]})].join('\n')}
async function copyText(text){try{await navigator.clipboard.writeText(text);toast('已複製')}catch(e){const t=$('copyFallback');t.hidden=false;t.value=text;t.focus();t.select();try{if(document.execCommand('copy')){toast('已複製');return}}catch(e){}toast('請長按文字自行複製')}}function download(name,text,mime){const a=document.createElement('a'),url=URL.createObjectURL(new Blob([text],{type:mime}));a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000)}$('copy').onclick = () => { if (!guardDay() && storedText !== undefined && storageProblem !== 'recovery') copyText(report(state.date, state.rows)); };
$('copyPending').onclick = () => { if (!guardDay() && storedText !== undefined && storageProblem !== 'recovery') copyText(report(state.date, state.rows, true)); };
$('export').onclick = () => {
  if (guardDay() || storedText === undefined || storageProblem === 'recovery') return;
  download('派車-' + state.date + '.txt', '\ufeff' + report(state.date, state.rows), 'text/plain;charset=utf-8');
};
$('backup').onclick = () => {
  if (storedText === undefined || storageProblem === 'recovery') return;
  download('派車備份-' + state.date + '.json', JSON.stringify(state, null, 2), 'application/json');
};
$('restore').onclick = $('recoverStorage').onclick = () => $('backupFile').click();
$('reloadStorage').onclick = () => location.reload();
$('downloadRaw').onclick = () => {
  if (storageProblem === 'recovery') download('派車原始資料.txt', storedText, 'text/plain;charset=utf-8');
};
$('backupFile').onchange = async event => {
  const input = event.target;
  try {
    const file = input.files[0];
    if (!file || !canWrite(true)) return;
    const restored = JSON.parse(await file.text());
    if (!validState(restored)) throw new Error('備份格式不符');
    const recovering = storageProblem === 'recovery';
    if (!confirm(recovering
      ? '以備份取代異常資料？如需保留異常內容，請先取消並下載原始資料。'
      : '以備份取代現有資料？')) return;
    if (!await commitChange(() => moveDate(migrate(restored), dateNow()), {restore: true})) return;
    clearDrafts();
    setFollowingDate(state.date);
    render();
    toast('已還原備份');
  } catch (error) {
    toast('無法還原：' + error.message);
  } finally {
    input.value = '';
  }
};
$('reset').onclick = async () => {
  if (guardDay() || !canWrite()) return;
  if (!confirm(`只清除 ${state.date} 的全部勾選及異動，恢復固定編組？其他日期不受影響。`)) return;
  if (await commitChange(draft => {
    draft.rows = dayRows(draft.base, draft.date);
    return draft;
  })) render();
};
setInterval(refreshDate, 1000);
function taskCounts(rows){const m=new Map(TASKS.map(t=>[t,0]));for(const c of rows)if(c.task)m.set(c.task,(m.get(c.task)||0)+1);return [...m]}
function renderDateControls() {
  const date = state.date;
  const today = date === dateNow();
  $('date').textContent = date + ' 週' + '日一二三四五六'[dow(date)];
  $('workDate').value = date;
  $('dateHint').textContent = dateLabel(date);
  $('goToday').disabled = today;
  const mode = $('importMode');
  for (const option of mode.options) option.disabled = !today && option.value !== 'today';
  if (!today) mode.value = 'today';
}

function refreshDate() {
  rollover();
  if ($('dateHint').textContent !== dateLabel(state.date)) {
    renderDateControls();
    renderHistory();
  }
}
function adjacentDate(delta){const d=new Date(state.date+'T00:00:00Z');d.setUTCDate(d.getUTCDate()+delta);chooseDate(d.toISOString().slice(0,10))}
$('workDate').onchange = () => chooseDate($('workDate').value);
$('prevDate').onclick = () => adjacentDate(-1);
$('nextDate').onclick = () => adjacentDate(1);
$('goToday').onclick = () => chooseDate(dateNow());
applyDisplay();
bindInterface();
render();
refreshDate();

// Update only static application assets; records are not transmitted.
let reg=null, updating=false, waitingWorker=null;
const versionMsg=s=>{$('versionStatus').textContent=s};
function safeToUpdate(){return !writing&&!$('editor').open&&!pendingImport&&!$('source').value.trim()&&!document.hidden;}
let reloadPending = false;
function applyWaiting() {
  if (!safeToUpdate()) return;
  if (reloadPending) {
    location.reload();
    return;
  }
  if (!waitingWorker || updating) return;
  updating = true;
  versionMsg('正在更新程式，保留本機資料…');
  waitingWorker.postMessage({type: 'ACTIVATE'});
}
function offerWorker(w){if(!w)return;waitingWorker=w;versionMsg('新版本已下載，編輯完成後自動更新。');applyWaiting();}
async function checkVersion(manual=false){if(!reg){if(manual)versionMsg('自動更新需使用 HTTPS 網站及支援 Service Worker 的瀏覽器。');return;}try{await reg.update();if(reg.waiting&&navigator.serviceWorker.controller)offerWorker(reg.waiting);else if(manual&&!updating)versionMsg('已檢查更新；如有新版將自動套用。');}catch(e){if(manual)versionMsg('目前無法連線檢查，仍可使用本機資料。');}}
$('checkVersion').onclick=()=>checkVersion(true);
if('serviceWorker' in navigator&&window.isSecureContext){let hadController=!!navigator.serviceWorker.controller;navigator.serviceWorker.addEventListener('controllerchange',()=>{if(hadController||updating){reloadPending=true;applyWaiting();}else{hadController=true;versionMsg('V9.2｜離線程式已啟用');}});navigator.serviceWorker.register('./sw.js',{updateViaCache:'none'}).then(r=>{reg=r;if(r.waiting&&navigator.serviceWorker.controller)offerWorker(r.waiting);r.addEventListener('updatefound',()=>{const w=r.installing;if(w)w.addEventListener('statechange',()=>{if(w.state==='installed'&&navigator.serviceWorker.controller)offerWorker(w);});});checkVersion();}).catch(()=>versionMsg('V9.2｜離線快取未啟用，請使用 HTTPS 網站'));setInterval(()=>checkVersion(),900000);setInterval(applyWaiting,1500);}else versionMsg('V9.2｜目前環境不支援自動更新');

window.addEventListener('focus', () => {
  refreshDate();
  checkVersion();
});
document.addEventListener('visibilitychange', () => {
  if (document.hidden) return;
  refreshDate();
  checkVersion();
  applyWaiting();
});
