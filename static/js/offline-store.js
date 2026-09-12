// Local-first runtime boundary. Core work never waits on a remote service.
(function () {
  const status = { mode: 'OFFLINE', pending: 0 };

  function persist(kind, recordId, payload, state) {
    return fetch('/api/local/state', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({kind, record_id: recordId, payload, status: state || 'local'})
    }).catch(() => null);
  }

  function refreshStatus() {
    return fetch('/api/system/status')
      .then(response => response.json())
      .then(data => {
        status.mode = data.mode || 'OFFLINE';
        status.pending = data.queued_sync || 0;
        const pill = document.querySelector('[data-network-pill]');
        if (pill) {
          pill.querySelector('span:last-child').textContent = status.mode === 'LOCAL_NETWORK'
            ? 'Local Network · Ready'
            : 'Offline Mode · Local';
          pill.classList.toggle('network-ready', status.mode === 'LOCAL_NETWORK');
        }
        return data;
      })
      .catch(() => status);
  }

  window.LearnCraftOffline = {
    status,
    persist,
    refreshStatus,
    queueStatus: () => fetch('/api/sync/queue').then(response => response.json()).catch(() => [])
  };

  document.addEventListener('DOMContentLoaded', refreshStatus);
})();
