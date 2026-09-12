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

  registerSandbox('circuit', function observeCircuit(state) {
    const hasBattery = state.components.includes('battery');
    const hasBulb = state.components.includes('bulb');
    const hasSwitch = state.components.includes('switch');
    const hasWire = state.components.includes('wire');

    if (!hasBattery || !hasBulb || !hasSwitch || !hasWire) {
      return {
        key: 'incomplete',
        status: 'Ready to build',
        title: 'Your circuit needs a complete path',
        happened: 'The bulb cannot respond yet because one or more circuit parts are missing.',
        why: 'Electric current needs a source, a load, and an unbroken conducting path.',
        concept: 'A circuit is a closed path for charge to move through.',
        formula: 'Current flows only when the path is complete.',
        action: 'Add the missing part, then try the switch again.',
        tone: 'neutral'
      };
    }

    if (!state.switchClosed) {
      return {
        key: 'open',
        status: 'Open circuit',
        title: 'The bulb stays dark',
        happened: 'The battery, bulb, switch, and wire are connected, but the switch is open.',
        why: 'The gap stops charge from moving all the way around the circuit.',
        concept: 'Open circuits interrupt current.',
        formula: 'Open path -> I = 0 A',
        action: 'Close the switch and observe what changes.',
        tone: 'observe'
      };
    }

    return {
      key: 'closed',
      status: 'Closed circuit',
      title: 'The bulb lights',
      happened: 'The switch completes the path, so the bulb receives energy from the battery.',
      why: 'A continuous conducting loop lets charge move through the bulb.',
      concept: 'Closed circuits allow current to flow.',
      formula: 'V = I x R',
      action: 'Open the switch or remove a wire to compare the two states.',
      tone: 'success'
    };
  });

  window.LearnCraftSandbox = { registerSandbox, observeSandbox };
})();
