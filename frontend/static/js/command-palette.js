// LearnCraft Command Palette (Ctrl/Cmd+K)
// Every command maps to a REAL route or API action - no decorative entries.
(function () {
  'use strict';

  var COMMANDS = [
    { label: 'Home', hint: 'Dashboard', href: '/home', group: 'Navigate' },
    { label: 'Missions', hint: 'Generated from your learning state', href: '/missions', group: 'Navigate' },
    { label: 'My Learning', hint: 'Progress by subject', href: '/my-learning', group: 'Navigate' },
    { label: 'Subjects', hint: 'Curriculum', href: '/subjects', group: 'Navigate' },
    { label: 'Mastery Map', hint: 'Concept graph + states', href: '/mastery', group: 'Navigate' },
    { label: 'Resources', hint: 'External learning resources', href: '/resources', group: 'Navigate' },
    { label: 'Tests', hint: 'Practice quizzes', href: '/tests', group: 'Learn' },
    { label: 'Practical Lab', hint: 'Code workspace', href: '/practical', group: 'Learn' },
    { label: 'Sandbox', hint: 'Simulations and games', href: '/sandbox', group: 'Learn' },
    { label: 'Assignments', hint: 'Teacher work', href: '/assignments', group: 'Learn' },
    { label: 'Notes', hint: 'Smart Notes', href: '/notes', group: 'Create' },
    { label: 'Ask AI', hint: 'Copilot', href: '/ask-ai', group: 'Create' },
    { label: 'Progress', hint: 'Mastery breakdown', href: '/progress', group: 'Navigate' },
    { label: 'Profile', hint: 'XP, level, goals', href: '/profile', group: 'Navigate' },
    { label: 'Settings', hint: 'Account preferences', href: '/settings', group: 'Navigate' },
    { label: 'Mark all notifications read', hint: 'Notification centre',
      action: 'read-notifications', group: 'Action' }
  ];

  var overlay, input, results, cursor = 0, items = [], debounce = null;

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/[&<>"]/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
      });
  }

  function build() {
    if (overlay) return;
    overlay = document.createElement('div');
    overlay.id = 'lcPalette';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Command palette');
    overlay.innerHTML =
      '<div class="lc-palette-card">' +
      '<input id="lcPaletteInput" type="text" placeholder="Search concepts, lessons, notes…" ' +
      'autocomplete="off" role="combobox" aria-expanded="true" aria-controls="lcPaletteResults" />' +
      '<div id="lcPaletteResults" role="listbox" aria-label="Results"></div>' +
      '<div class="lc-palette-foot">↑↓ navigate · Enter open · Esc close</div></div>';
    document.body.appendChild(overlay);
    input = overlay.querySelector('#lcPaletteInput');
    results = overlay.querySelector('#lcPaletteResults');
    input.addEventListener('input', function () {
      window.clearTimeout(debounce);
      debounce = window.setTimeout(search, 140);
    });
    input.addEventListener('keydown', onKey);
    overlay.addEventListener('click', function (event) {
      if (event.target === overlay) close();
    });
  }

  function open() {
    build();
    overlay.classList.add('open');
    input.value = '';
    render(COMMANDS.slice(), 'Commands');
    input.focus();
  }

  function close() {
    if (overlay) overlay.classList.remove('open');
  }

  function onKey(event) {
    if (event.key === 'Escape') { event.preventDefault(); close(); return; }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      cursor = Math.max(0, Math.min(items.length - 1,
        cursor + (event.key === 'ArrowDown' ? 1 : -1)));
      highlight();
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      if (items[cursor]) run(items[cursor]);
    }
  }

  function render(list, label) {
    items = list;
    cursor = 0;
    if (!list.length) {
      results.innerHTML = '<div class="lc-palette-empty">No matches. Press Esc to close.</div>';
      return;
    }
    results.innerHTML = '<div class="lc-palette-label">' + esc(label) + '</div>' +
      list.map(function (item, index) {
        return '<button class="lc-palette-item" role="option" aria-selected="' +
          (index === 0) + '" data-index="' + index + '">' +
          '<span class="lc-palette-title">' + esc(item.label) + '</span>' +
          '<span class="lc-palette-hint">' + esc(item.hint || '') + '</span></button>';
      }).join('');
    results.querySelectorAll('[data-index]').forEach(function (button) {
      button.addEventListener('click', function () {
        run(items[Number(button.dataset.index)]);
      });
    });
    highlight();
  }

  function highlight() {
    results.querySelectorAll('.lc-palette-item').forEach(function (button, index) {
      var active = index === cursor;
      button.classList.toggle('active', active);
      button.setAttribute('aria-selected', String(active));
      if (active) button.scrollIntoView({ block: 'nearest' });
    });
  }

  function run(item) {
    close();
    if (item.href) { window.location.href = item.href; return; }
    if (item.action === 'read-notifications') {
      fetch('/api/v1/notifications/read', { method: 'POST' })
        .then(function () { window.location.reload(); });
    }
  }
function search() {
    var query = input.value.trim();
    if (!query) { render(COMMANDS.slice(), 'Commands'); return; }
    var term = query.toLowerCase();
    var local = COMMANDS.filter(function (command) {
      return (command.label + ' ' + command.hint).toLowerCase().indexOf(term) !== -1;
    });
    render(local, 'Commands & pages');
    if (query.length < 2) return;
    fetch('/api/v1/search?q=' + encodeURIComponent(query) + '&limit=6')
      .then(function (response) { return response.json(); })
      .then(function (data) {
        var found = [];
        Object.keys(data.groups || {}).forEach(function (group) {
          (data.groups[group] || []).forEach(function (row) {
            found.push({ label: row.title || row.id, hint: group, href: row.href });
          });
        });
        if (found.length) render(local.concat(found), 'Commands & pages');
      })
      .catch(function () { /* offline: keep local commands */ });
  }

  document.addEventListener('keydown', function (event) {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      if (overlay && overlay.classList.contains('open')) close(); else open();
    }
  });

  document.addEventListener('DOMContentLoaded', function () {
    var button = document.getElementById('openPalette');
    if (button) button.addEventListener('click', open);
  });

  window.LearnCraftPalette = { open: open, close: close };
})();