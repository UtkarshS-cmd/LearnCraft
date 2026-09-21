/* LearnCraft external learning links.
 *
 * LearnCraft stays the hub: it owns curriculum, mastery and activity records.
 * Provider platforms (Notion, Obsidian, PW, Khan Academy, Anki, GitHub,
 * YouTube, Drive) are opened as external links - never scraped, never framed.
 *
 * Privacy rule: the Obsidian vault name and note template are stored in this
 * browser's localStorage ONLY. They are never sent to the LearnCraft server, so
 * the obsidian:// deep link is assembled here in the client.
 */
(function (global) {
  'use strict';

  var OFFLINE = 'Requires Internet';

  /** Read the user's local Obsidian settings (empty when never configured). */
  function vaultSettings() {
    var vault = '', template = '';
    try {
      vault = (localStorage.getItem('lc_obsidian_vault') || '').trim();
      template = (localStorage.getItem('lc_obsidian_template') || '').trim();
    } catch (e) { /* private mode / storage disabled */ }
    return { vault: vault, template: template };
  }

  /** Build an obsidian://open URI, or "" when no vault is configured. */
  function obsidianUri(el, action) {
    var settings = vaultSettings();
    if (!settings.vault) { return ''; }
    var read = function (name) { return (el && el.getAttribute && el.getAttribute(name)) || ''; };
    var map = { subject: read('data-subject'), chapter: read('data-chapter'),
                topic: read('data-topic'), title: read('data-title') };
    var note = (settings.template || '{subject}/{chapter}/{title}')
      .replace(/\{(subject|chapter|topic|title)\}/g, function (m, key) { return map[key] || ''; })
      .replace(/\/{2,}/g, '/')
      .replace(/^\/+|\/+$/g, '');
    var base = action === 'new' ? 'obsidian://new' : 'obsidian://open';
    var query = 'vault=' + encodeURIComponent(settings.vault);
    return note ? base + '?' + query + '&file=' + encodeURIComponent(note) : base + '?' + query;
  }

  /**
   * Open an external resource link, recording a lightweight "opened" event.
   * @param {Element} el  Anchor carrying data-provider / data-url / data-* context.
   * @param {string} id   LearnCraft resource id.
   * @returns {boolean}   Always false, so callers can `return lcOpenExternal(...)`.
   */
  function openExternal(el, id, options) {
    options = options || {};
    var target = (el && el.getAttribute('data-url')) || '';
    var provider = (el && el.getAttribute('data-provider')) || '';
    if (provider === 'obsidian') {
      var uri = obsidianUri(el, options.action);
      if (uri) {
        target = uri;
      } else {
        // Graceful fallback: official website, and tell the user how to enable deep links.
        target = target || 'https://obsidian.md/';
        if (global.toast) { toast('Set your Obsidian vault in Settings to open notes directly', false); }
      }
    }
    if (!target) { return false; }
    if (id) {
      // Best-effort activity ping; launches must work offline, so failures are ignored.
      try { fetch('/api/v1/resources/' + encodeURIComponent(id) + '/open?format=json').catch(function () {}); } catch (e) {}
    }
    global.open(target, '_blank', 'noopener');
    return false;
  }

  /** Tag online-only resource cards when the browser reports being offline. */
  function markOfflineOnly(root) {
    if (typeof navigator !== 'undefined' && navigator.onLine) { return; }
    (root || document).querySelectorAll('[data-online-only]').forEach(function (el) {
      if (el.querySelector('.off-badge')) { return; }
      var badge = document.createElement('span');
      badge.className = 'off-badge';
      badge.textContent = OFFLINE;
      el.insertAdjacentElement('afterend', badge);
    });
  }

  global.lcObsidianUri = obsidianUri;
  global.lcOpenExternal = openExternal;
  global.lcMarkOfflineOnly = markOfflineOnly;
  global.lcVaultSettings = vaultSettings;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { markOfflineOnly(document); });
  } else {
    markOfflineOnly(document);
  }
})(window);
