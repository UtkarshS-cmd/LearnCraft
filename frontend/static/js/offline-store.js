// LearnCraft Local-First Runtime & Offline Queue
// Core work persists locally first and syncs to SQLite /api/local/state with retry safety.
(function () {
  'use strict';

  const DB_NAME = 'learncraft_offline_db';
  const STORE_NAME = 'sync_queue';
  const LS_BACKUP_KEY = 'learncraft_browser_queue';

  const status = {
    mode: 'OFFLINE',
    online: typeof navigator !== 'undefined' ? navigator.onLine : true,
    server_reachable: false,
    browser_queued: 0,
    server_queued: 0,
    pending: 0
  };

  let isDraining = false;
  let idbPromise = null;

  // --- IndexedDB & LocalStorage Fallback Storage Layer ---
  function openDatabase() {
    if (idbPromise) return idbPromise;
    if (typeof indexedDB === 'undefined') {
      idbPromise = Promise.resolve(null);
      return idbPromise;
    }
    idbPromise = new Promise(function (resolve) {
      try {
        var req = indexedDB.open(DB_NAME, 1);
        req.onupgradeneeded = function (e) {
          var db = e.target.result;
          if (!db.objectStoreNames.contains(STORE_NAME)) {
            db.createObjectStore(STORE_NAME, { keyPath: 'event_id' });
          }
        };
        req.onsuccess = function (e) {
          resolve(e.target.result);
        };
        req.onerror = function () {
          resolve(null);
        };
      } catch (err) {
        resolve(null);
      }
    });
    return idbPromise;
  }

  function getBackupQueue() {
    try {
      var raw = localStorage.getItem(LS_BACKUP_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  }

  function saveBackupQueue(items) {
    try {
      localStorage.setItem(LS_BACKUP_KEY, JSON.stringify(items));
    } catch (e) {}
  }

  function getPendingQueue() {
    return openDatabase().then(function (db) {
      if (!db) return getBackupQueue();
      return new Promise(function (resolve) {
        try {
          var tx = db.transaction(STORE_NAME, 'readonly');
          var store = tx.objectStore(STORE_NAME);
          var req = store.getAll();
          req.onsuccess = function () {
            var idbItems = req.result || [];
            var lsItems = getBackupQueue();
            // Merge deduplicated by event_id, sort by created_at ascending
            var map = {};
            idbItems.concat(lsItems).forEach(function (item) {
              if (item && item.event_id && !map[item.event_id]) {
                map[item.event_id] = item;
              }
            });
            var combined = Object.values(map);
            combined.sort(function (a, b) {
              return (a.seq || 0) - (b.seq || 0) || (a.created_at || '').localeCompare(b.created_at || '');
            });
            resolve(combined);
          };
          req.onerror = function () {
            resolve(getBackupQueue());
          };
        } catch (e) {
          resolve(getBackupQueue());
        }
      });
    });
  }

  function enqueueEvent(event) {
    // Always mirror to localStorage for instantaneous persistence
    var lsQueue = getBackupQueue();
    var existsInLs = lsQueue.some(function (it) { return it.event_id === event.event_id; });
    if (!existsInLs) {
      lsQueue.push(event);
      saveBackupQueue(lsQueue);
    }

    return openDatabase().then(function (db) {
      if (!db) return event;
      return new Promise(function (resolve) {
        try {
          var tx = db.transaction(STORE_NAME, 'readwrite');
          var store = tx.objectStore(STORE_NAME);
          store.put(event);
          tx.oncomplete = function () { resolve(event); };
          tx.onerror = function () { resolve(event); };
        } catch (e) {
          resolve(event);
        }
      });
    });
  }

  function removeEvent(eventId) {
    var lsQueue = getBackupQueue().filter(function (it) { return it.event_id !== eventId; });
    saveBackupQueue(lsQueue);

    return openDatabase().then(function (db) {
      if (!db) return true;
      return new Promise(function (resolve) {
        try {
          var tx = db.transaction(STORE_NAME, 'readwrite');
          var store = tx.objectStore(STORE_NAME);
          store.delete(eventId);
          tx.oncomplete = function () { resolve(true); };
          tx.onerror = function () { resolve(true); };
        } catch (e) {
          resolve(true);
        }
      });
    });
  }

  function updateEvent(event) {
    var lsQueue = getBackupQueue().map(function (it) {
      return it.event_id === event.event_id ? event : it;
    });
    saveBackupQueue(lsQueue);

    return openDatabase().then(function (db) {
      if (!db) return event;
      return new Promise(function (resolve) {
        try {
          var tx = db.transaction(STORE_NAME, 'readwrite');
          var store = tx.objectStore(STORE_NAME);
          store.put(event);
          tx.oncomplete = function () { resolve(event); };
          tx.onerror = function () { resolve(event); };
        } catch (e) {
          resolve(event);
        }
      });
    });
  }

  // --- UI Update Helper ---
  function updateUI() {
    var pill = document.querySelector('[data-network-pill]');
    if (!pill) return;
    var labelEl = pill.querySelector('span:last-child');
    if (!labelEl) return;

    if (!status.online) {
      labelEl.textContent = 'Offline Mode · Local';
      pill.classList.remove('network-ready');
    } else if (status.server_reachable) {
      labelEl.textContent = status.mode === 'LOCAL_NETWORK'
        ? 'Local Network · Ready'
        : 'Offline Mode · Local';
      pill.classList.toggle('network-ready', status.mode === 'LOCAL_NETWORK');
    } else {
      labelEl.textContent = 'Server Unreachable · Local';
      pill.classList.remove('network-ready');
    }
  }

  // --- System Status Probe ---
  function refreshStatus() {
    status.online = typeof navigator !== 'undefined' ? navigator.onLine : true;
    if (!status.online) {
      status.server_reachable = false;
      return getPendingQueue().then(function (q) {
        status.browser_queued = q.length;
        status.pending = q.length + status.server_queued;
        updateUI();
        return status;
      });
    }

    return fetch('/api/system/status', { cache: 'no-store' })
      .then(function (response) {
        if (!response.ok) throw new Error('Status request failed');
        return response.json();
      })
      .then(function (data) {
        status.server_reachable = true;
        status.mode = data.mode || 'OFFLINE';
        status.server_queued = data.queued_sync || 0;
        return getPendingQueue().then(function (q) {
          status.browser_queued = q.length;
          status.pending = q.length + status.server_queued;
          updateUI();
          return data;
        });
      })
      .catch(function () {
        status.server_reachable = false;
        return getPendingQueue().then(function (q) {
          status.browser_queued = q.length;
          status.pending = q.length + status.server_queued;
          updateUI();
          return status;
        });
      });
  }

  // --- Queue Drain & Synchronization ---
  function drainQueue() {
    if (isDraining) return Promise.resolve();
    isDraining = true;

    return getPendingQueue().then(function (events) {
      if (!events || events.length === 0) {
        isDraining = false;
        return refreshStatus();
      }

      // Process pending queue sequentially to preserve ordering
      function processNext(index) {
        if (index >= events.length) {
          isDraining = false;
          return refreshStatus();
        }

        var evt = events[index];
        return fetch('/api/local/state', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            event_id: evt.event_id,
            kind: evt.kind,
            record_id: evt.record_id,
            payload: evt.payload,
            status: evt.status
          })
        })
        .then(function (response) {
          if (response.ok) {
            // Marked SYNCHRONIZED, remove from local browser queue
            return removeEvent(evt.event_id).then(function () {
              return processNext(index + 1);
            });
          } else if (response.status === 401) {
            // Unauthenticated: pause drain, do not discard events
            isDraining = false;
            return refreshStatus();
          } else {
            // Validation or server 4xx/5xx: record retry and move forward
            evt.retry_count = (evt.retry_count || 0) + 1;
            evt.last_error = 'HTTP ' + response.status;
            return updateEvent(evt).then(function () {
              return processNext(index + 1);
            });
          }
        })
        .catch(function (err) {
          // Network connection error: halt drain until next reconnect
          status.server_reachable = false;
          updateUI();
          isDraining = false;
        });
      }

      return processNext(0);
    }).catch(function () {
      isDraining = false;
    });
  }

  // --- Public API: persist() ---
  // Guaranteed local persistence first; never loses user work on network error.
  function persist(kind, recordId, payload, state) {
    var eventId = 'evt_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9);
    var event = {
      event_id: eventId,
      kind: kind,
      record_id: recordId,
      payload: payload,
      status: state || 'local',
      created_at: new Date().toISOString(),
      seq: Date.now(),
      sync_status: 'LOCAL_BROWSER_QUEUE',
      retry_count: 0
    };

    return enqueueEvent(event).then(function () {
      status.browser_queued += 1;
      status.pending = status.browser_queued + status.server_queued;
      updateUI();
      // Attempt background drain if reachable or online
      if (status.online !== false) {
        drainQueue();
      }
      return { success: true, event_id: eventId, status: 'LOCAL_BROWSER_QUEUE' };
    });
  }

  // --- Network Event Listeners ---
  window.addEventListener('online', function () {
    status.online = true;
    refreshStatus().then(function () {
      drainQueue();
    });
  });

  window.addEventListener('offline', function () {
    status.online = false;
    status.server_reachable = false;
    updateUI();
  });

  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') {
      refreshStatus().then(function () {
        if (status.server_reachable) drainQueue();
      });
    }
  });

  document.addEventListener('DOMContentLoaded', function () {
    refreshStatus().then(function () {
      if (status.server_reachable) drainQueue();
    });
  });

  // Expose LearnCraftOffline on window
  window.LearnCraftOffline = {
    status: status,
    persist: persist,
    refreshStatus: refreshStatus,
    drainQueue: drainQueue,
    getPendingQueue: getPendingQueue,
    queueStatus: function () {
      return fetch('/api/sync/queue').then(function (r) { return r.json(); }).catch(function () { return []; });
    }
  };
})();
