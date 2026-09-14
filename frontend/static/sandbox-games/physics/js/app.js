/* PhysicsGame shell: navigation, HUD, audio (local WebAudio), shared FX.
   Plain script (no modules) so file:// works. Depends on: STORE. */
"use strict";
var APP = (function () {
  var PARENTS = {
    "screen-menu": null,
    "screen-law1": "screen-menu", "screen-law2": "screen-menu",
    "screen-law3": "screen-menu", "screen-inertia": "screen-menu",
    "screen-challenge": "screen-menu", "screen-lab": "screen-menu",
    "screen-g1": "screen-challenge", "screen-g2": "screen-challenge",
    "screen-g3": "screen-challenge", "screen-g4": "screen-challenge"
  };
  var TITLES = {
    "screen-menu": "⚛️ Physics Adventure Lab",
    "screen-law1": "🥌 Newton's 1st Law — Inertia",
    "screen-law2": "🚀 Newton's 2nd Law — F = ma",
    "screen-law3": "🎈 Newton's 3rd Law — Action–Reaction",
    "screen-inertia": "🧭 Inertia Lab",
    "screen-challenge": "🏅 Physics Challenge Arena",
    "screen-lab": "🔬 Free Experiment Lab",
    "screen-g1": "🎯 Game 1 — Force Challenge",
    "screen-g2": "🔍 Game 2 — Inertia Detective",
    "screen-g3": "🍎 Game 3 — Newton's Law Match",
    "screen-g4": "🔮 Game 4 — Predict the Motion"
  };

  var RM = false;
  try { RM = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches); } catch (e) {}
  var muted = false;
  try { muted = localStorage.getItem("physgame_muted") === "1"; } catch (e) {}

  function $(id) { return document.getElementById(id); }

  // ---------- Audio (synthesized locally, zero files) ----------
  var actx = null;
  function ac() {
    if (muted) return null;
    try {
      if (!actx) {
        var AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return null;
        actx = new AC();
      }
      if (actx.state === "suspended") actx.resume();
      return actx;
    } catch (e) { return null; }
  }
  function tone(f, d, type, v, when) {
    var c = ac();
    if (!c) return;
    try {
      var o = c.createOscillator(), g = c.createGain();
      o.type = type || "sine"; o.frequency.value = f;
      var t = c.currentTime + (when || 0);
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(v || 0.2, t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t + d);
      o.connect(g); g.connect(c.destination);
      o.start(t); o.stop(t + d + 0.05);
    } catch (e) {}
  }
  var SFX = {
    click: function () { tone(620, 0.07, "square", 0.07); },
    good: function () { tone(523, 0.12, "sine", 0.22); tone(659, 0.12, "sine", 0.22, 0.1); tone(784, 0.22, "sine", 0.22, 0.2); },
    bad: function () { tone(220, 0.18, "sawtooth", 0.1); tone(165, 0.25, "sawtooth", 0.1, 0.12); },
    win: function () { var n = [523, 659, 784, 1046, 784, 1046]; for (var i = 0; i < n.length; i++) tone(n[i], 0.16, "triangle", 0.2, i * 0.12); },
    level: function () { var n = [523, 659, 784, 1046, 1318]; for (var j = 0; j < n.length; j++) tone(n[j], 0.15, "triangle", 0.22, j * 0.09); },
    tick: function () { tone(950, 0.05, "square", 0.05); },
    pop: function () { tone(880, 0.09, "triangle", 0.18); tone(1174, 0.12, "triangle", 0.18, 0.07); }
  };

  // ---------- Navigation ----------
  var current = "screen-menu";
  function show(id) {
    var secs = document.querySelectorAll(".screen");
    for (var i = 0; i < secs.length; i++) secs[i].classList.remove("active");
    var scr = $(id);
    if (!scr) return;
    scr.classList.add("active");
    current = id;
    $("navTitle").textContent = TITLES[id] || "⚛️ Physics Adventure Lab";
    $("navBack").style.visibility = PARENTS[id] ? "visible" : "hidden";
    if (!RM) {
      var cards = scr.querySelectorAll(".card");
      for (var c = 0; c < cards.length; c++) {
        (function (elm, idx) {
          elm.classList.remove("card-in");
          void elm.offsetWidth;
          elm.style.animationDelay = (idx * 60) + "ms";
          elm.classList.add("card-in");
          setTimeout(function () { elm.classList.remove("card-in"); elm.style.animationDelay = ""; }, 700 + idx * 60);
        })(cards[c], c);
      }
    }
    try { window.scrollTo(0, 0); } catch (e) {}
    var visit = id.replace("screen-", "");
    STORE.visit(visit);
  }
  function back() {
    var p = PARENTS[current];
    show(p || "screen-menu");
  }

  // ---------- HUD ----------
  function hud() {
    var d = STORE.data();
    $("hudXp").textContent = d.xp;
    $("hudLevel").textContent = STORE.level();
    $("hudStreak").textContent = "🔥" + d.streak;
    $("hudLevelFill").style.width = STORE.levelPct() + "%";
  }

  // ---------- FX ----------
  function toast(msg, good) {
    var t = $("toast");
    t.textContent = msg;
    t.className = "toast show " + (good === false ? "bad" : good === true ? "good" : "");
    clearTimeout(t._h);
    t._h = setTimeout(function () { t.className = "toast"; }, 2200);
  }
  function emitEvent(eventType, activityId, detail, score) {
    try { fetch('/api/v1/events', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({event_type:eventType, activity_type:'game', activity_id:activityId, subject_slug:'science', detail:detail, score:score})}).catch(function(){}); } catch (e) {}
  }
  function xpFloat(n) {
    if (RM) return;
    var l = $("floatLayer");
    var s = document.createElement("span");
    s.className = "xp-float";
    s.textContent = "+" + n + " XP";
    l.appendChild(s);
    setTimeout(function () { if (s.parentNode) s.parentNode.removeChild(s); }, 1300);
  }
  function confetti(n) {
    if (RM) return;
    var box = $("confetti");
    box.innerHTML = "";
    var icons = ["⭐", "🎉", "⚛️", "🚀", "🎈", "✅", "🍎"];
    for (var i = 0; i < (n || 50); i++) {
      var s = document.createElement("span");
      s.textContent = icons[Math.floor(Math.random() * icons.length)];
      s.style.left = Math.random() * 100 + "vw";
      s.style.animationDuration = (2 + Math.random() * 2) + "s";
      s.style.fontSize = (15 + Math.random() * 20) + "px";
      box.appendChild(s);
    }
    setTimeout(function () { box.innerHTML = ""; }, 4200);
  }
  function badgePop(badge) {
    SFX.win(); confetti(45);
    var ov = $("badgePop");
    $("badgePopIcon").textContent = badge.icon;
    $("badgePopName").textContent = badge.name + " earned!";
    $("badgePopDesc").textContent = badge.desc;
    ov.classList.remove("hidden");
    var hide = function () { ov.classList.add("hidden"); ov.removeEventListener("click", hide); };
    ov.addEventListener("click", hide);
    setTimeout(hide, 2800);
  }
  function levelUp(n) {
    SFX.level(); confetti(60);
    $("levelUpText").textContent = "You reached Level " + n + "! 🧠";
    var ov = $("levelUpOverlay");
    ov.classList.remove("hidden");
    var hide = function () { ov.classList.add("hidden"); ov.removeEventListener("click", hide); };
    ov.addEventListener("click", hide);
    setTimeout(hide, 2600);
  }
  // Award XP + handle streak/level/badge popups centrally.
  function reward(xp, badgeId) {
    var leveled = STORE.addXP(xp);
    xpFloat(xp);
    hud();
    var nb = null;
    if (badgeId) {
      for (var i = 0; i < STORE.BADGES.length; i++) {
        if (STORE.BADGES[i].id === badgeId && STORE.award(badgeId)) nb = STORE.BADGES[i];
      }
      renderBadges();
    }
    if (leveled) setTimeout(function () { levelUp(leveled); }, 500);
    else if (nb) setTimeout(function () { badgePop(nb); }, 400);
    return leveled;
  }
  // MCQ verdict helper: plays sound, updates streak/XP, returns {ok}.
  function verdict(ok, xpWin) {
    var r = STORE.answer(ok, xpWin);
    hud();
    if (ok) { SFX.good(); xpFloat((xpWin || 20) + Math.min((r.streak - 1) * 5, 25)); }
    else SFX.bad();
    if (r.leveled) setTimeout(function () { levelUp(r.leveled); }, 600);
    return r;
  }

  function renderBadges() {
    var d = STORE.data();
    var html = "";
    for (var i = 0; i < STORE.BADGES.length; i++) {
      var b = STORE.BADGES[i], won = d.badges.indexOf(b.id) !== -1;
      html += '<div class="badge' + (won ? " won" : "") + '" title="' + b.desc + '">' +
        (won ? b.icon + " " + b.name : "🔒 " + b.name) + "</div>";
    }
    var a = $("badgeShelf"), c = $("badgeShelfCh");
    if (a) a.innerHTML = html;
    if (c) c.innerHTML = html;
  }
  function renderBest() {
    var el = $("bestList");
    if (!el) return;
    var names = { g1: "🎯 Force Challenge", g2: "🔍 Inertia Detective", g3: "🍎 Law Match", g4: "🔮 Predict the Motion" };
    var html = "";
    for (var k in names) {
      html += '<div class="best-row"><span>' + names[k] + '</span><b>⭐ ' + (STORE.best(k) || 0) + "</b></div>";
    }
    el.innerHTML = html;
  }

  function setMuted(m) {
    muted = m;
    try { localStorage.setItem("physgame_muted", m ? "1" : "0"); } catch (e) {}
    $("muteBtn").textContent = m ? "🔇" : "🔊";
  }

  function init() {
    setMuted(muted);
    hud(); renderBadges(); renderBest();
    STORE.onChange(function () { hud(); renderBadges(); renderBest(); });
    var cards = document.querySelectorAll("[data-go]");
    for (var i = 0; i < cards.length; i++) {
      (function (elm) {
        elm.addEventListener("click", function () { SFX.click(); show(elm.getAttribute("data-go")); });
      })(cards[i]);
    }
    $("navBack").addEventListener("click", function () { SFX.click(); back(); });
    $("muteBtn").addEventListener("click", function () { setMuted(!muted); if (!muted) SFX.click(); });
    $("helpBtn").addEventListener("click", function () { SFX.click(); $("helpModal").classList.remove("hidden"); });
    $("closeHelp").addEventListener("click", function () { SFX.click(); $("helpModal").classList.add("hidden"); });
    $("helpModal").addEventListener("click", function (e) { if (e.target === this) this.classList.add("hidden"); });
    $("resetBtn").addEventListener("click", function () {
      if (confirm("Erase all XP, badges and best scores on this computer?")) {
        STORE.reset(); toast("Progress erased. Fresh start! 🌱", true);
      }
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "m" || e.key === "M") setMuted(!muted);
      if (e.key === "Escape") {
        if (!$("helpModal").classList.contains("hidden")) $("helpModal").classList.add("hidden");
        else if (PARENTS[current]) back();
      }
    });
    show("screen-menu");
  }

  return {
    $, RM: function () { return RM; }, SFX: SFX,
    show: show, back: back, hud: hud, toast: toast,
    xpFloat: xpFloat, confetti: confetti, badgePop: badgePop,
    levelUp: levelUp, reward: reward, verdict: verdict,
    renderBadges: renderBadges, renderBest: renderBest, emitEvent: emitEvent, init: init
  };
})();
