// Deterministic sandbox observers. Each subject can register an observe(state) rule set.
(function () {
  const observers = {};

  function registerSandbox(id, observer) {
    observers[id] = observer;
  }

  function observeSandbox(id, state) {
    const observer = observers[id];
    if (!observer) return null;
    return observer(state);
  }

  window.LearnCraftSandbox = { registerSandbox, observeSandbox };
})();
