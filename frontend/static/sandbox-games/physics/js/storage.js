/* PhysicsGame storage — XP, levels, streaks, badges, best scores.
   localStorage only (memory fallback). Node-testable. */
"use strict";
var STORE = (function () {
  var LS = "physgame_profile_v1";
  var mem = {};
  function get(k) {
    try { return localStorage.getItem(k); } catch (e) { return (k in mem) ? mem[k] : null; }
  }
  function set(k, v) {
    try { localStorage.setItem(k, v); } catch (e) { mem[k] = String(v); }
  }

  var BADGES = [
    { id: "inertia-explorer", icon: "🧭", name: "Inertia Explorer", desc: "Aced all 3 inertia lab experiments" },
    { id: "force-master", icon: "💪", name: "Force Master", desc: "Hit the target acceleration in the F=ma challenge" },
    { id: "apprentice", icon: "🍎", name: "Newton's Apprentice", desc: "Matched 5+ real-life situations to the right law" },
    { id: "champion", icon: "🏆", name: "Physics Champion", desc: "Earned all other badges. True physicist!" },
    { id: "sharp", icon: "🎯", name: "Sharp Shooter", desc: "Won a Force Challenge round (landed within 0.5 m)" },
    { id: "detective", icon: "🔍", name: "Inertia Detective", desc: "Solved 4+ detective cases in one game" }
  ];

  function fresh() {
    return {
      xp: 0, gamesPlayed: 0, correct: 0, answered: 0,
      streak: 0, bestStreak: 0,
      badges: [], best: {}, visited: [], inertiaDone: {}
    };
  }
  var p = fresh();
  try {
    var raw = get(LS);
    if (raw) {
      var d = JSON.parse(raw);
      for (var k in p) if (k in d) p[k] = d[k];
    }
  } catch (e) {}

  function save() { try { set(LS, JSON.stringify(p)); } catch (e) {} }
  function level() { return Math.floor(p.xp / 300) + 1; }
  function levelPct() { return Math.round(((p.xp % 300) / 300) * 100); }

  var listeners = [];
  function onChange(fn) { listeners.push(fn); }
  function emit() { for (var i = 0; i < listeners.length; i++) { try { listeners[i](p); } catch (e) {} } }

  function addXP(n) {
    var before = level();
    p.xp += n;
    save(); emit();
    return level() > before ? level() : 0; // new level or 0
  }
  // Call on every answered question/game verdict. Returns {streak, leveled}.
  function answer(correct, xpWin) {
    p.answered++;
    var leveled = 0;
    if (correct) {
      p.correct++;
      p.streak++;
      if (p.streak > p.bestStreak) p.bestStreak = p.streak;
      var bonus = Math.min((p.streak - 1) * 5, 25);
      leveled = addXP((xpWin || 20) + bonus);
    } else {
      p.streak = 0;
      save(); emit();
    }
    return { streak: p.streak, leveled: leveled };
  }
  function hasBadge(id) { return p.badges.indexOf(id) !== -1; }
  // Returns true if newly earned.
  function award(id) {
    if (hasBadge(id)) return false;
    p.badges.push(id);
    if (id !== "champion" && hasBadge("inertia-explorer") && hasBadge("force-master") && hasBadge("apprentice")) {
      if (!hasBadge("champion")) p.badges.push("champion");
    }
    save(); emit();
    return true;
  }
  function best(key, val) {
    if (val === undefined) return p.best[key] || 0;
    if (val > (p.best[key] || 0)) { p.best[key] = val; save(); emit(); return true; }
    return false;
  }
  function visit(id) {
    if (p.visited.indexOf(id) === -1) { p.visited.push(id); save(); emit(); }
  }
  function inertiaOK(kind) {
    p.inertiaDone[kind] = true;
    var n = Object.keys(p.inertiaDone).length;
    save(); emit();
    return n;
  }
  function reset() { p = fresh(); save(); emit(); }

  var api = {
    data: function () { return p; },
    BADGES: BADGES, save: save, onChange: onChange,
    level: level, levelPct: levelPct, addXP: addXP, answer: answer,
    hasBadge: hasBadge, award: award, best: best, visit: visit,
    inertiaOK: inertiaOK, reset: reset
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  return api;
})();
