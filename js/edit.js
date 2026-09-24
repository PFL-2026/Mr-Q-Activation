/* ===================================================================
   PFL × MrQ — in-deck text editing (opt-in)
   -------------------------------------------------------------------
   The partner-facing link is untouched. Edit tools appear only when the
   deck is opened with "?edit" (or "#edit") in the URL, or after pressing
   Ctrl/Cmd+Shift+E once in that browser.

   Every editable text block carries a data-e="N" attribute written by the
   build. Edits autosave to this browser as drafts; "Export" downloads an
   updated index.html in which ONLY the edited blocks change — everything
   else is byte-identical to the live file. Upload that index.html to
   GitHub to publish.
   =================================================================== */
(function () {
  'use strict';

  const FLAG_KEY = 'pfl-mrq-edit-tools';
  const DRAFT_KEY = 'pfl-mrq-text-drafts';

  const url = new URL(window.location.href);
  const asked = url.searchParams.has('edit') || url.hash === '#edit';
  let available = false;
  try { available = asked || localStorage.getItem(FLAG_KEY) === '1'; } catch (e) {}
  if (asked) { try { localStorage.setItem(FLAG_KEY, '1'); } catch (e) {} }

  const els = Array.from(document.querySelectorAll('[data-e]'));
  if (!els.length) return;

  // Snapshot the published text before any draft is applied
  const orig = {};
  els.forEach(el => { orig[el.dataset.e] = el.innerHTML; });

  // ---- drafts ---------------------------------------------------------
  function loadDrafts() {
    try { return JSON.parse(localStorage.getItem(DRAFT_KEY) || '{}'); } catch (e) { return {}; }
  }
  function saveDrafts(d) {
    try { localStorage.setItem(DRAFT_KEY, JSON.stringify(d)); } catch (e) {}
  }
  let drafts = loadDrafts();

  // A draft only applies to the exact text it was made against. If the live
  // file already contains the edit (exported + uploaded) or the block has
  // since been changed on GitHub, the draft is dropped.
  let draftsApplied = false;
  function applyDrafts() {
    if (draftsApplied) return;
    draftsApplied = true;
    Object.keys(drafts).forEach(id => {
      const d = drafts[id];
      const el = document.querySelector('[data-e="' + id + '"]');
      if (!el || !d || el.innerHTML === d.html || el.innerHTML !== d.orig) {
        delete drafts[id];
        return;
      }
      el.innerHTML = d.html;
    });
    saveDrafts(drafts);
  }

  // ---- toolbar ----------------------------------------------------------
  const bar = document.createElement('div');
  bar.className = 'edit-bar';
  bar.setAttribute('role', 'toolbar');
  bar.innerHTML =
    '<button type="button" class="edit-bar-btn" data-act="toggle" aria-pressed="false">Edit text</button>' +
    '<button type="button" class="edit-bar-btn" data-act="export">Export index.html</button>' +
    '<button type="button" class="edit-bar-btn edit-bar-ghost" data-act="discard">Discard</button>' +
    '<span class="edit-bar-status" aria-live="polite"></span>';
  document.body.appendChild(bar);
  const btnToggle = bar.querySelector('[data-act="toggle"]');
  const status = bar.querySelector('.edit-bar-status');

  function changedIds() {
    return els.filter(el => el.innerHTML !== orig[el.dataset.e]).map(el => el.dataset.e);
  }
  function refreshStatus(msg) {
    const n = changedIds().length;
    status.textContent = msg || (n ? n + ' edit' + (n === 1 ? '' : 's') + ' saved in this browser · Export to publish'
                                   : 'No edits');
    document.body.classList.toggle('edit-dirty', n > 0);
  }

  function setAvailable(on) {
    available = on;
    if (on) applyDrafts();
    document.body.classList.toggle('edit-available', on);
    try { localStorage.setItem(FLAG_KEY, on ? '1' : '0'); } catch (e) {}
    if (!on) setEditing(false);
    refreshStatus();
  }

  let editing = false;
  function setEditing(on) {
    editing = on;
    document.body.classList.toggle('is-text-editing', on);
    btnToggle.setAttribute('aria-pressed', String(on));
    btnToggle.textContent = on ? 'Done editing' : 'Edit text';
    els.forEach(el => {
      if (on) { el.setAttribute('contenteditable', 'true'); el.setAttribute('spellcheck', 'true'); }
      else { el.removeAttribute('contenteditable'); el.removeAttribute('spellcheck'); }
    });
    if (!on && document.activeElement && document.activeElement.blur) document.activeElement.blur();
  }

  // ---- editing behaviour ---------------------------------------------
  let t = null;
  document.addEventListener('input', e => {
    if (!e.target.closest || !e.target.closest('[data-e]')) return;
    clearTimeout(t);
    t = setTimeout(syncDrafts, 250);
  });
  function syncDrafts() {
    els.forEach(el => {
      const id = el.dataset.e;
      if (el.innerHTML === orig[id]) delete drafts[id];
      else drafts[id] = { orig: orig[id], html: el.innerHTML };
    });
    saveDrafts(drafts);
    refreshStatus();
  }

  // Plain-text paste only — no stray fonts/colours from Word or email
  document.addEventListener('paste', e => {
    if (!editing || !e.target.closest || !e.target.closest('[data-e]')) return;
    e.preventDefault();
    const text = (e.clipboardData || window.clipboardData).getData('text/plain');
    document.execCommand('insertText', false, text.replace(/\s*\n\s*/g, ' '));
  });

  // Keys typed into text must not drive the deck (arrows, space, etc.).
  // Enter = line break (<br>), not a new <div>. Escape leaves the block.
  window.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'E' || e.key === 'e')) {
      e.preventDefault();
      setAvailable(!available);
      return;
    }
    const el = e.target && e.target.closest && e.target.closest('[data-e][contenteditable]');
    if (!el) return;
    if (e.key === 'Escape') { el.blur(); e.stopImmediatePropagation(); e.preventDefault(); return; }
    if (e.key === 'Enter') { e.preventDefault(); document.execCommand('insertLineBreak'); }
    e.stopImmediatePropagation();
  }, true);

  // Clicking text to edit must not open cards / modals / players behind it
  window.addEventListener('click', e => {
    if (editing && e.target.closest && e.target.closest('[data-e]')) e.stopPropagation();
  }, true);

  // ---- export -------------------------------------------------------------
  function download(name, text) {
    const blob = new Blob([text], { type: 'text/html;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  // Replace the inner content of the element tagged data-e="id" in the raw
  // source, leaving every other byte alone.
  function spliceBlock(src, id, html) {
    const open = new RegExp('<([a-zA-Z][a-zA-Z0-9]*)\\b[^>]*\\sdata-e="' + id + '"[^>]*>');
    const m = open.exec(src);
    if (!m) throw new Error('block ' + id + ' not found in source');
    const tag = m[1].toLowerCase();
    const start = m.index + m[0].length;
    const re = new RegExp('<(/?)' + tag + '\\b[^>]*>', 'gi');
    re.lastIndex = start;
    let depth = 1, mm;
    while ((mm = re.exec(src))) {
      depth += mm[1] ? -1 : 1;
      if (depth === 0) return src.slice(0, start) + html + src.slice(mm.index);
    }
    throw new Error('block ' + id + ' has no closing tag');
  }

  async function exportHTML() {
    clearTimeout(t); syncDrafts();
    const ids = changedIds();
    if (!ids.length) { refreshStatus('Nothing to export yet'); return; }
    let src;
    try {
      const res = await fetch(window.location.pathname, { cache: 'no-store' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      src = await res.text();
    } catch (err) {
      refreshStatus('Export needs the deck served over the web (GitHub Pages link), not opened as a file');
      return;
    }
    try {
      ids.forEach(id => {
        const el = document.querySelector('[data-e="' + id + '"]');
        src = spliceBlock(src, id, el.innerHTML);
      });
    } catch (err) {
      refreshStatus('Export failed: ' + err.message);
      return;
    }
    download('index.html', src);
    refreshStatus(ids.length + ' edit' + (ids.length === 1 ? '' : 's') + ' exported · upload index.html to GitHub');
  }

  bar.addEventListener('click', e => {
    const b = e.target.closest('[data-act]');
    if (!b) return;
    e.stopPropagation();
    if (b.dataset.act === 'toggle') setEditing(!editing);
    if (b.dataset.act === 'export') exportHTML();
    if (b.dataset.act === 'discard') {
      if (!changedIds().length) return;
      if (!window.confirm('Discard all text edits made in this browser?')) return;
      els.forEach(el => { el.innerHTML = orig[el.dataset.e]; });
      drafts = {};
      saveDrafts(drafts);
      refreshStatus();
    }
  });

  window.addEventListener('pagehide', () => { clearTimeout(t); syncDrafts(); });

  setAvailable(available);
})();
