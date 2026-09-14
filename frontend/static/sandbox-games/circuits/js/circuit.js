"use strict";
(function () {
  var STORAGE_KEY = "learncraft_circuit_lab_v1";
  var defaults = { closed: false };
  var state = loadState();

  function byId(id) { return document.getElementById(id); }
  function loadState() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      var saved = raw ? JSON.parse(raw) : defaults;
      return { closed: saved && saved.closed === true };
    } catch (error) {
      return { closed: defaults.closed };
    }
  }
  function saveState() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (error) {}
  }
  function render() {
    var live = state.closed;
    var board = byId("board");
    board.dataset.live = String(live);
    byId("switchBtn").classList.toggle("closed", live);
    byId("switchBtn").setAttribute("aria-pressed", String(live));
    byId("switchState").textContent = live ? "Closed" : "Open";
    byId("switchSymbol").textContent = live ? "⏻" : "⭘";
    byId("boardNote").textContent = live ? "Complete circuit: current is flowing through the bulb." : "The switch is open, so the path is broken.";
    byId("status").textContent = live ? "Closed circuit · Current flowing" : "Open circuit";
    byId("status").className = "status " + (live ? "live" : "neutral");
    byId("explanation").textContent = live
      ? "The closed path allows current to flow. Using Ohm's law, I = 9 V / 10 Ω = 0.90 A."
      : "Electric current needs a continuous path from the source, through the load, and back to the source.";
    byId("current").textContent = live ? "0.90 A" : "0.00 A";
    byId("power").textContent = live ? "8.10 W" : "0.00 W";
    byId("switchCheck").className = "check" + (live ? " done" : "");
    byId("switchCheck").firstElementChild.textContent = live ? "✓" : "○";
    saveState();
  }
  byId("switchBtn").addEventListener("click", function () {
    state.closed = !state.closed;
    render();
  });
  byId("resetBtn").addEventListener("click", function () {
    state.closed = false;
    render();
  });
  render();
})();
