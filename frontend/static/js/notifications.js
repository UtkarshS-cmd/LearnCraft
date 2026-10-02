// Notification centre bell: server-authoritative, per-user, persistent.
// Replaces the previous localStorage "seen" approach, which lost unread state
// on another device and never distinguished empty from failed states.
(function () {
  'use strict';

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/[&<>"]/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
      });
  }

  function init() {
    var bell = document.getElementById('notifBell');
    if (!bell) return;
    var count = document.getElementById('notifCount');
    var menu = document.getElementById('notifMenu');
    var list = document.getElementById('notifList');
    var payload = null;

    function loading() {
      list.innerHTML = '<div class="notif-state">Loading notifications…</div>';
    }
    function errorState(message) {
      list.innerHTML =
        '<div class="notif-state notif-error"><b>Could not load notifications</b>' +
        '<span>' + esc(message || 'Check your connection and retry.') + '</span>' +
        '<button class="btn btn-secondary btn-sm" type="button" data-retry>Retry</button></div>';
      list.querySelector('[data-retry]').addEventListener('click', load);
    }
    function emptyState() {
      list.innerHTML =
        '<div class="notif-state"><b>You are all caught up</b>' +
        '<span>Assignments, announcements and achievements appear here.</span></div>';
    }
    function render(data) {
      var items = (data && data.items) || [];
      if (!items.length) { emptyState(); return; }
      list.innerHTML = items.slice(0, 8).map(function (item) {
        var kind = String(item.kind || '').replace(/_/g, ' ');
        var tone = kind.indexOf('assignment') >= 0 ? 'warn' : 'info';
        return '<a class="notif-item' + (item.read ? '' : ' unread') + '" href="' +
          esc(item.href || '/assignments') + '" data-id="' + esc(item.id) + '">' +
          '<span class="badge ' + tone + '">' + esc(kind) + '</span>' +
          '<b style="margin-top:4px">' + esc(item.title) + '</b>' +
          (item.body ? '<div class="caption">' + esc(item.body) + '</div>' : '') +
          '<div class="caption">' + esc(item.created_at || '') + '</div></a>';
      }).join('');
      list.querySelectorAll('.notif-item').forEach(function (node) {
        node.addEventListener('click', function () {
          fetch('/api/v1/notifications/' + node.dataset.id + '/read', { method: 'POST' })
            .catch(function () {});
        });
      });
    }
    function load() {
      return fetch('/api/v1/notifications?limit=15')
        .then(function (response) {
          return response.json().then(function (data) {
            return { ok: response.ok, data: data };
          });
        })
        .then(function (result) {
          if (!result.ok) throw new Error(result.data.message || 'Request failed');
          payload = result.data;
          var unread = result.data.unread || 0;
          if (unread > 0) {
            count.hidden = false;
            count.textContent = unread > 9 ? '9+' : String(unread);
          } else {
            count.hidden = true;
          }
          if (menu && !menu.hidden) render(result.data);
          return result.data;
        })
        .catch(function (error) {
          // Offline: keep whatever was last rendered instead of blanking it.
          if (menu && !menu.hidden && !payload) errorState(error.message);
          return null;
        });
    }

    bell.addEventListener('click', function (event) {
      event.stopPropagation();
      var open = menu.hidden;
      menu.hidden = !open;
      bell.setAttribute('aria-expanded', String(open));
      if (open) { loading(); load().then(function (data) { render(data || {}); }); }
    });
    document.addEventListener('click', function (event) {
      if (!menu.hidden && !event.target.closest('.notif-wrap')) {
        menu.hidden = true;
        bell.setAttribute('aria-expanded', 'false');
      }
    });
    load();
    setInterval(load, 30000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();