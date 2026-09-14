/* Math Adventure! - 100% OFFLINE game logic (Animated Edition).
   No fetch, no network, no CDN, no modules. Works via file://
   Storage: localStorage only. Sounds: WebAudio synthesized locally (no files).
   Animations: pure CSS keyframes + vanilla JS, reflecting the REAL question/answer. */
(function () {
  "use strict";

  // ---------- Helpers ----------
  function $(id) { return document.getElementById(id); }
  function randInt(min, max) { return Math.floor(Math.random() * (max - min + 1)) + min; }
  function shuffle(arr) {
    for (var i = arr.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = arr[i]; arr[i] = arr[j]; arr[j] = t;
    }
    return arr;
  }
  function clamp(n, a, b) { return Math.max(a, Math.min(b, n)); }
  function el(tag, cls, html) {
    var d = document.createElement(tag || "div");
    if (cls) d.className = cls;
    if (html != null) d.innerHTML = html;
    return d;
  }

  // Reduced motion: users who prefer it get instant, static visuals.
  var RM = false;
  try { RM = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches); } catch (e) { RM = false; }

  // ---------- Config ----------
  var BASE_SCORE = { easy: 10, medium: 20, hard: 30 };
  var TIME_PER_Q = { easy: 30, medium: 20, hard: 15 };
  var OP_LABEL = { addition: "➕ Addition", subtraction: "➖ Subtraction", multiplication: "✖️ Multiplication", division: "➗ Division", mixed: "🎲 Mixed" };
  var DIFF_LABEL = { easy: "🌱 Easy", medium: "🌟 Medium", hard: "🔥 Hard" };
  var OP_SYMBOL = { addition: "+", subtraction: "−", multiplication: "×", division: "÷" };

  var BADGES = [
    { id: "first_steps",  icon: "👣", name: "First Steps",   desc: "Finish your first game" },
    { id: "streak5",      icon: "🔥", name: "Hot Streak",    desc: "5 correct in a row" },
    { id: "streak8",      icon: "🚀", name: "Unstoppable",   desc: "8 correct in a row" },
    { id: "streak10",     icon: "⚡", name: "Lightning Mind",desc: "10 correct in a row" },
    { id: "perfect",      icon: "💯", name: "Perfect!",      desc: "100% accuracy in a round (5+ Qs)" },
    { id: "speed",        icon: "⏱", name: "Speed Star",    desc: "Answer correctly in 3 sec or less" },
    { id: "survivor",     icon: "❤️", name: "Survivor",      desc: "Finish with only 1 life left" },
    { id: "high300",      icon: "🌟", name: "Super Scorer",  desc: "Score 300+ in one round" },
    { id: "explorer",     icon: "🗺", name: "Explorer",      desc: "Play all 5 mission types" },
    { id: "persistent",   icon: "🎮", name: "Persistent",    desc: "Play 5 games" }
  ];

  // ---------- Storage ----------
  var LS_BEST = "mlg_best_v1";
  var LS_PROFILE = "mlg_profile_v1";
  var LS_MUTED = "mlg_muted_v1";

  function loadJSON(key, fallback) {
    try {
      var raw = localStorage.getItem(key);
      if (!raw) return fallback;
      return JSON.parse(raw);
    } catch (e) { return fallback; }
  }
  function saveJSON(key, val) {
    try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) {}
  }
  var bestScores = loadJSON(LS_BEST, {});
  var profile = loadJSON(LS_PROFILE, { xp: 0, gamesPlayed: 0, totalCorrect: 0, totalAnswered: 0, bestStreakEver: 0, badges: [], modesPlayed: [] });
  if (!profile.badges) profile.badges = [];
  if (!profile.modesPlayed) profile.modesPlayed = [];
  var muted = false;
  try { muted = localStorage.getItem(LS_MUTED) === "1"; } catch (e) {}

  function getLevel() { return Math.floor((profile.xp || 0) / 500) + 1; }
  function levelProgress() {
    var xp = profile.xp || 0;
    var into = xp % 500;
    return Math.round((into / 500) * 100);
  }

  // ---------- Sound (WebAudio, fully offline, stored locally in this file) ----------
  var audioCtx = null;
  function ctx() {
    if (muted) return null;
    try {
      if (!audioCtx) {
        var AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return null;
        audioCtx = new AC();
      }
      if (audioCtx.state === "suspended") audioCtx.resume();
      return audioCtx;
    } catch (e) { return null; }
  }
  function tone(freq, dur, type, vol, when) {
    var c = ctx();
    if (!c) return;
    try {
      var o = c.createOscillator();
      var g = c.createGain();
      o.type = type || "sine";
      o.frequency.value = freq;
      var t = c.currentTime + (when || 0);
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(vol || 0.2, t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      o.connect(g); g.connect(c.destination);
      o.start(t); o.stop(t + dur + 0.05);
    } catch (e) {}
  }
  var SFX = {
    click: function () { tone(600, 0.08, "square", 0.08); },
    correct: function () { tone(523, 0.12, "sine", 0.22); tone(659, 0.12, "sine", 0.22, 0.1); tone(784, 0.2, "sine", 0.22, 0.2); },
    wrong: function () { tone(220, 0.2, "sawtooth", 0.12); tone(165, 0.3, "sawtooth", 0.12, 0.15); },
    streak: function () { tone(880, 0.1, "triangle", 0.2); tone(1174, 0.15, "triangle", 0.2, 0.08); },
    win: function () { var n = [523, 659, 784, 1046, 784, 1046]; for (var i = 0; i < n.length; i++) tone(n[i], 0.18, "triangle", 0.2, i * 0.13); },
    levelup: function () { var n = [523, 659, 784, 1046, 1318]; for (var i = 0; i < n.length; i++) tone(n[i], 0.16, "triangle", 0.22, i * 0.09); },
    tick: function () { tone(1000, 0.05, "square", 0.05); }
  };

  function updateMuteUI() {
    var icon = muted ? "🔇" : "🔊";
    $("muteBtn").textContent = icon;
    $("muteBtn2").textContent = icon + " Sound";
  }
  function toggleMute() {
    muted = !muted;
    try { localStorage.setItem(LS_MUTED, muted ? "1" : "0"); } catch (e) {}
    updateMuteUI();
    if (!muted) SFX.click();
  }

  // ---------- Game state ----------
  var state = {
    op: "mixed", diff: "easy", total: 10,
    index: 0, score: 0, lives: 3, streak: 0, maxStreak: 0,
    correct: 0, wrong: 0,
    current: null, timeLeft: 0, timerId: null,
    locked: false, fastAnswers: 0, roundBadges: []
  };

  // ---------- Question generation (dynamic, local, whole-number division) ----------
  function pickOp() {
    if (state.op !== "mixed") return state.op;
    var ops = ["addition", "subtraction", "multiplication", "division"];
    return ops[randInt(0, 3)];
  }

  function ranges(op, progress) {
    // progress 0..1 -> numbers grow through the round (increasing difficulty)
    var d = state.diff, lo, hi, mlo, mhi, dlo, dhi, qlo, qhi;
    if (d === "easy") {
      if (op === "addition") { lo = 1; hi = Math.round(10 + progress * 10); }
      if (op === "subtraction") { lo = 1; hi = Math.round(10 + progress * 10); }
      if (op === "multiplication") { mlo = 2; mhi = Math.round(5 + progress * 2); }
      if (op === "division") { dlo = 2; dhi = Math.round(5 + progress * 2); qlo = 2; qhi = Math.round(5 + progress * 2); }
    } else if (d === "medium") {
      if (op === "addition") { lo = 5; hi = Math.round(30 + progress * 40); }
      if (op === "subtraction") { lo = 5; hi = Math.round(30 + progress * 40); }
      if (op === "multiplication") { mlo = 3; mhi = Math.round(8 + progress * 4); }
      if (op === "division") { dlo = 2; dhi = Math.round(8 + progress * 3); qlo = 2; qhi = Math.round(8 + progress * 3); }
    } else {
      if (op === "addition") { lo = 15; hi = Math.round(99 + progress * 150); }
      if (op === "subtraction") { lo = 15; hi = Math.round(99 + progress * 150); }
      if (op === "multiplication") { mlo = 4; mhi = Math.round(12 + progress * 3); }
      if (op === "division") { dlo = 3; dhi = Math.round(11 + progress * 3); qlo = 3; qhi = Math.round(11 + progress * 3); }
    }
    return { lo: lo, hi: hi, mlo: mlo, mhi: mhi, dlo: dlo, dhi: dhi, qlo: qlo, qhi: qhi };
  }

  function makeQuestion() {
    var op = pickOp();
    var progress = state.total <= 1 ? 1 : state.index / (state.total - 1);
    var r = ranges(op, progress);
    var a, b, ans, text;
    if (op === "addition") {
      a = randInt(r.lo, r.hi); b = randInt(r.lo, r.hi);
      ans = a + b; text = a + " + " + b + " = ?";
    } else if (op === "subtraction") {
      a = randInt(r.lo, r.hi); b = randInt(r.lo, r.hi);
      if (b > a) { var t = a; a = b; b = t; } // keep child-friendly: no negative answers
      ans = a - b; text = a + " − " + b + " = ?";
    } else if (op === "multiplication") {
      a = randInt(r.mlo, r.mhi); b = randInt(r.mlo, r.mhi);
      ans = a * b; text = a + " × " + b + " = ?";
    } else {
      // Division with guaranteed whole-number answer: pick divisor & quotient, multiply
      var div = randInt(r.dlo, r.dhi);
      var quo = randInt(r.qlo, r.qhi);
      div = Math.max(2, div); quo = Math.max(2, quo);
      a = div * quo; b = div; ans = quo;
      text = a + " ÷ " + b + " = ?";
    }
    var options = makeOptions(ans, op);
    return { op: op, a: a, b: b, ans: ans, text: text, options: options };
  }

  function makeOptions(ans, op) {
    var set = {};
    set[ans] = true;
    var out = [ans];
    var tries = 0;
    while (out.length < 4 && tries < 200) {
      tries++;
      var cand;
      var mode = Math.random();
      if (op === "multiplication" || op === "division") {
        if (mode < 0.4) cand = ans + randInt(-3, 3);
        else if (mode < 0.6) cand = ans + randInt(-10, 10);
        else if (mode < 0.75) cand = ans * 2 - randInt(0, 2);
        else cand = ans + (Math.random() < 0.5 ? -1 : 1) * randInt(1, 5);
      } else {
        if (mode < 0.5) cand = ans + randInt(-5, 5);
        else if (mode < 0.75) cand = ans + randInt(-12, 12);
        else cand = ans + (Math.random() < 0.5 ? -10 : 10);
      }
      if (cand === ans) continue;
      if (cand < 0) cand = ans + Math.abs(cand) + 1; // keep non-negative for kids
      if (set[cand]) continue;
      set[cand] = true;
      out.push(cand);
    }
    // Fallback (should never happen): fill sequentially
    var f = 1;
    while (out.length < 4) { if (!set[ans + f]) { set[ans + f] = true; out.push(ans + f); } f++; }
    return shuffle(out);
  }

  // ---------- Animation helpers ----------
  function tweenNumber(node, from, to, dur) {
    if (!node) return;
    if (RM || from === to) { node.textContent = to; return; }
    var t0 = null, D = dur || 600;
    function step(t) {
      if (t0 === null) t0 = t;
      var p = Math.min(1, (t - t0) / D);
      node.textContent = Math.round(from + (to - from) * p);
      if (p < 1) requestAnimationFrame(step);
    }
    try { requestAnimationFrame(step); } catch (e) { node.textContent = to; }
  }
  function pulse(node, cls) {
    if (!node || RM) return;
    cls = cls || "pulse";
    try {
      node.classList.remove(cls);
      void node.offsetWidth;
      node.classList.add(cls);
    } catch (e) {}
  }
  function floatPoints(text, kind) {
    var layer = $("floatLayer");
    if (!layer) return;
    var s = el("span", "float-pts " + (kind || "good"), text);
    layer.appendChild(s);
    setTimeout(function () { if (s.parentNode) s.parentNode.removeChild(s); }, RM ? 2200 : 1250);
  }
  function burst(x, y, n) {
    if (RM) return;
    try {
      var icons = ["⭐", "✨", "🎉", "💛", "💚"];
      for (var i = 0; i < (n || 10); i++) {
        (function (i) {
          var s = document.createElement("span");
          s.className = "burst-bit";
          s.textContent = icons[randInt(0, icons.length - 1)];
          s.style.left = x + "px";
          s.style.top = y + "px";
          s.style.setProperty("--bx", randInt(-70, 70) + "px");
          s.style.setProperty("--by", randInt(-95, -35) + "px");
          document.body.appendChild(s);
          setTimeout(function () { if (s.parentNode) s.parentNode.removeChild(s); }, 750);
        })(i);
      }
    } catch (e) {}
  }

  function streakTier(s) {
    if (s >= 10) return { cls: "tier10", msg: "⚡ STREAK x" + s + "! Lightning Mind!" };
    if (s >= 8) return { cls: "tier8", msg: "🚀 STREAK x" + s + "! Unstoppable!" };
    if (s >= 5) return { cls: "tier5", msg: "🔥 STREAK x" + s + "! Hot Streak!" };
    if (s >= 3) return { cls: "", msg: "🔥 Streak x" + s + "! Warming up!" };
    return null;
  }

  // ---------- Operation visualizer ----------
  // Pure planner: decides what to draw from the REAL question (capped for speed on big numbers,
  // with true counts always shown in labels/captions so the math stays honest).
  var VGROUP_DOT_MAX = 15;
  var VSUB_DOT_MAX = 30;
  var VMUL_G_MAX = 6;
  var VMUL_P_MAX = 6;
  var VDIV_DOT_MAX = 24;

  function planVisual(q) {
    var plan = { kind: q.op, answer: q.ans, capped: false, shown: 0, total: 0, caption: "" };
    if (q.op === "addition") {
      plan.total = q.a + q.b;
      plan.aShow = Math.min(q.a, VGROUP_DOT_MAX);
      plan.bShow = Math.min(q.b, VGROUP_DOT_MAX);
      plan.capped = (q.a > VGROUP_DOT_MAX || q.b > VGROUP_DOT_MAX);
      plan.shown = plan.aShow + plan.bShow;
    } else if (q.op === "subtraction") {
      plan.total = q.a; plan.take = q.b; plan.keep = q.ans;
      plan.aShow = Math.min(q.a, VSUB_DOT_MAX);
      plan.takeShow = (q.a === 0) ? 0 : Math.min(plan.aShow, Math.round(plan.aShow * (q.b / q.a)));
      plan.capped = (q.a > VSUB_DOT_MAX);
      plan.shown = plan.aShow;
    } else if (q.op === "multiplication") {
      plan.groups = q.a; plan.per = q.b; plan.total = q.ans;
      plan.gShow = Math.min(q.a, VMUL_G_MAX);
      plan.perShow = Math.min(q.b, VMUL_P_MAX);
      plan.capped = (q.a > VMUL_G_MAX || q.b > VMUL_P_MAX);
      plan.shown = plan.gShow * plan.perShow;
    } else {
      plan.boxes = q.b; plan.per = q.ans; plan.total = q.a;
      plan.dots = Math.min(q.a, VDIV_DOT_MAX);
      plan.capped = (q.a > VDIV_DOT_MAX);
      plan.shown = plan.dots;
    }
    return plan;
  }
  // Exposed for offline verification (pure function, no game state).
  try { window.__mlg = { planVisual: planVisual, version: "anim-2.0" }; } catch (e) {}

  function mkdot(cls, delayMs) {
    var d = el("span", "vdot " + cls);
    if (!RM && delayMs) d.style.animationDelay = delayMs + "ms";
    return d;
  }
  function fillDots(parent, n, cls, baseIdx) {
    for (var i = 0; i < n; i++) parent.appendChild(mkdot(cls, (baseIdx + i) * 22));
  }
  function makeTotal() {
    var t = el("div", "vtotal hidden", "= ?");
    return t;
  }

  function renderVisual(q) {
    var box = $("visual"), cap = $("visualCaption");
    if (!box || !cap) return;
    box.className = "visual";
    box.innerHTML = "";
    cap.textContent = "";
    var plan = planVisual(q);
    var i, g;

    if (q.op === "addition") {
      // Two groups slide in from the sides, "+" beats between them.
      var row = el("div", "vrow");
      var gA = el("div", "vgroup ga", '<div class="vlabel">🍎 ' + q.a + "</div>");
      var dA = el("div", "vdots");
      fillDots(dA, plan.aShow, "da", 0);
      gA.appendChild(dA);
      var plus = el("div", "vplus", "+");
      var gB = el("div", "vgroup gb", '<div class="vlabel">🫐 ' + q.b + "</div>");
      var dB = el("div", "vdots");
      fillDots(dB, plan.bShow, "db", plan.aShow);
      gB.appendChild(dB);
      row.appendChild(gA); row.appendChild(plus); row.appendChild(gB);
      box.appendChild(row);
      box.appendChild(makeTotal());
      cap.textContent = plan.capped
        ? q.a + " + " + q.b + ": groups slide together! (showing " + plan.shown + " of " + plan.total + " — counting the real total!) 🤝"
        : q.a + " + " + q.b + ": the groups slide together! Count them all! 🤝";
    } else if (q.op === "subtraction") {
      // One group; the "take" dots fly away on solve, the rest pop.
      g = el("div", "vgroup", '<div class="vlabel">🍪 ' + q.a + " in all</div>");
      var dd = el("div", "vdots");
      for (i = 0; i < plan.aShow; i++) {
        var isTake = i >= plan.aShow - plan.takeShow;
        dd.appendChild(mkdot(isTake ? "take" : "dn", i * 20));
      }
      g.appendChild(dd);
      box.appendChild(g);
      box.appendChild(makeTotal());
      cap.textContent = q.a + " − " + q.b + ": " + q.b + (q.b === 1 ? " flies" : " fly") + " away, " + q.ans + " stay" +
        (plan.capped ? " (showing " + plan.shown + " of " + q.a + ")" : "") + "! 👋";
    } else if (q.op === "multiplication") {
      // Repeated groups cascade in one by one: a groups of b.
      var wrap = el("div", "vboxes");
      for (i = 0; i < plan.gShow; i++) {
        var vb = el("div", "vbox");
        if (!RM) vb.style.animationDelay = (i * 110) + "ms";
        vb.appendChild(el("div", "vblabel", "Group " + (i + 1)));
        var vd = el("div", "vdots");
        fillDots(vd, plan.perShow, "ds", i * plan.perShow);
        vb.appendChild(vd);
        wrap.appendChild(vb);
      }
      box.appendChild(wrap);
      box.appendChild(makeTotal());
      cap.textContent = plan.capped
        ? q.a + " × " + q.b + ": " + q.a + " groups of " + q.b + "! (showing " + plan.gShow + " groups — counting the real total!) 📦"
        : q.a + " × " + q.b + ": " + q.a + " groups of " + q.b + "! Watch them pop in! 📦";
    } else {
      // Equal sharing: dividend dots hop one-by-one into divisor boxes.
      var boxes = el("div", "vboxes");
      var holders = [];
      for (i = 0; i < plan.boxes; i++) {
        var sb = el("div", "vbox share hop");
        if (!RM) sb.style.animationDelay = (i * 70) + "ms";
        sb.appendChild(el("div", "vblabel", "Box " + (i + 1)));
        var hd = el("div", "vdots");
        sb.appendChild(hd);
        boxes.appendChild(sb);
        holders.push(hd);
      }
      var hop = plan.dots > 0 ? Math.min(50, Math.floor(900 / plan.dots)) : 0;
      for (var d = 0; d < plan.dots; d++) {
        var dot = el("span", "vdot dn hopdot");
        if (!RM) dot.style.animationDelay = (d * hop) + "ms";
        holders[d % holders.length].appendChild(dot);
      }
      box.appendChild(boxes);
      box.appendChild(makeTotal());
      cap.textContent = plan.capped
        ? q.a + " ÷ " + q.b + ": sharing into " + q.b + " equal boxes! (showing " + plan.shown + " of " + q.a + " ⭐ — each box really gets " + q.ans + ") ⚖️"
        : q.a + " ÷ " + q.b + ": sharing into " + q.b + " equal boxes! Watch them hop! ⚖️";
    }
  }

  function celebrateVisual() {
    var box = $("visual");
    if (!box || !state.current) return;
    var q = state.current;
    box.classList.add("solved");
    if (q.op === "addition") box.classList.add("solved-add");
    if (q.op === "subtraction") box.classList.add("takeoff");
    var nodes = box.getElementsByClassName("vtotal");
    if (nodes.length > 0) {
      var t = nodes[0];
      t.textContent = "= " + q.ans + " 🎉";
      t.classList.remove("hidden");
      // retrigger pop
      try { t.classList.remove("show"); void t.offsetWidth; t.classList.add("show"); } catch (e) { t.classList.add("show"); }
    }
    pulse($("questionText"), "ans-pop");
  }

  // ---------- Round flow ----------
  function showScreen(name) {
    $("homeScreen").classList.remove("active");
    $("gameScreen").classList.remove("active");
    $("resultsScreen").classList.remove("active");
    var scr = $(name);
    scr.classList.add("active");
    // Staggered card entrance (menu transition)
    if (!RM) {
      try {
        var cards = scr.querySelectorAll(".card");
        for (var i = 0; i < cards.length; i++) {
          (function (c, idx) {
            c.classList.remove("card-in");
            void c.offsetWidth;
            c.style.animationDelay = (idx * 70) + "ms";
            c.classList.add("card-in");
            setTimeout(function () { c.classList.remove("card-in"); c.style.animationDelay = ""; }, 800 + idx * 70);
          })(cards[i], i);
        }
      } catch (e) {}
    }
    window.scrollTo(0, 0);
  }

  function startRound() {
    try { fetch('/api/v1/events', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({event_type:'GAME_STARTED', activity_type:'game', activity_id:'maths-explorer', subject_slug:'mathematics', detail:'Maths Explorer started'})}).catch(function(){}); } catch (e) {}
    state.index = 0; state.score = 0; state.lives = 3;
    state.streak = 0; state.maxStreak = 0;
    state.correct = 0; state.wrong = 0;
    state.fastAnswers = 0; state.roundBadges = [];
    state.locked = false;
    $("modeLabel").textContent = OP_LABEL[state.op] + " • " + DIFF_LABEL[state.diff];
    $("levelVal").textContent = getLevel();
    try { $("againBtn").classList.remove("replay"); } catch (e) {}
    showScreen("gameScreen");
    nextQuestion();
  }

  function nextQuestion() {
    if (state.lives <= 0) return endRound("No lives left! 💔");
    if (state.index >= state.total) return endRound("Round complete! 🎉");
    state.current = makeQuestion();
    state.locked = false;
    transitionQuestion(function () {
      renderQuestion();
      renderVisual(state.current);
      startTimer();
    });
  }

  // Smooth slide/fade/scale: old question out, new question in (<300ms total).
  function transitionQuestion(fn) {
    var qa = $("qAnim");
    if (RM || !qa) { fn(); return; }
    qa.classList.remove("q-enter");
    qa.classList.add("q-exit");
    setTimeout(function () {
      fn();
      qa.classList.remove("q-exit");
      qa.classList.add("q-enter");
      setTimeout(function () { qa.classList.remove("q-enter"); }, 300);
    }, 150);
  }

  function renderQuestion() {
    var q = state.current;
    $("questionText").textContent = q.text;
    $("questionText").classList.remove("ans-pop");
    $("qProgressText").textContent = "Question " + (state.index + 1) + " / " + state.total;
    $("progressFill").style.width = Math.round((state.index / state.total) * 100) + "%";
    $("scoreVal").textContent = state.score;
    $("streakVal").textContent = state.streak;
    $("livesVal").textContent = "❤️".repeat(state.lives) + "🤍".repeat(Math.max(0, 3 - state.lives));
    var fb = $("feedback");
    fb.className = "feedback hidden"; fb.textContent = "";
    $("streakPop").classList.add("hidden");
    var box = $("answers");
    box.innerHTML = "";
    var symbols = ["🅰️", "🅱️", "🅲", "🅳"];
    q.options.forEach(function (val, i) {
      var b = document.createElement("button");
      b.className = "answer" + (RM ? "" : " ans-in");
      if (!RM) b.style.animationDelay = (i * 60) + "ms";
      b.innerHTML = "<div style='font-size:15px'>" + symbols[i] + " (" + (i + 1) + ")</div><div>" + val + "</div>";
      b.setAttribute("data-val", val);
      b.addEventListener("click", function () { answer(i); });
      box.appendChild(b);
    });
  }

  function startTimer() {
    stopTimer();
    state.timeLeft = TIME_PER_Q[state.diff];
    paintTimer();
    state.timerId = setInterval(function () {
      state.timeLeft--;
      paintTimer();
      if (state.timeLeft <= 5 && state.timeLeft > 0) SFX.tick();
      if (state.timeLeft <= 0) {
        stopTimer();
        onTimeout();
      }
    }, 1000);
  }
  function stopTimer() {
    if (state.timerId) { clearInterval(state.timerId); state.timerId = null; }
  }
  function paintTimer() {
    var total = TIME_PER_Q[state.diff];
    $("timeVal").textContent = Math.max(0, state.timeLeft);
    var pct = clamp((state.timeLeft / total) * 100, 0, 100);
    var fill = $("timerFill");
    fill.style.width = pct + "%";
    fill.style.background = state.timeLeft <= 5 ? "#d63031" : (state.timeLeft <= total / 2 ? "#fdcb6e" : "#00b894");
    // Subtle warning animation on the bar only (never flashy full-screen).
    try { $("timerBar").classList.toggle("warn", state.timeLeft <= 5 && state.timeLeft > 0); } catch (e) {}
  }

  function answer(i) {
    if (state.locked) return;
    state.locked = true;
    stopTimer();
    var q = state.current;
    var picked = q.options[i];
    var btns = $("answers").children;
    var timeUsed = TIME_PER_Q[state.diff] - state.timeLeft;
    if (picked === q.ans) {
      var base = BASE_SCORE[state.diff];
      var timeBonus = Math.max(0, Math.round(state.timeLeft * 0.5));
      var newStreak = state.streak + 1;
      var streakBonus = newStreak >= 3 ? Math.min(newStreak * 5, 30) : 0;
      var gained = base + timeBonus + streakBonus;
      var oldScore = state.score;
      state.score += gained;
      state.streak = newStreak;
      state.maxStreak = Math.max(state.maxStreak, state.streak);
      state.correct++;
      if (timeUsed <= 3) state.fastAnswers++;
      btns[i].classList.add("correct");
      for (var k = 0; k < btns.length; k++) if (k !== i) btns[k].classList.add("dim");
      showFeedback(true, "✅ Correct! +" + gained + " (⭐" + base + " + ⏱" + timeBonus + (streakBonus ? " + 🔥" + streakBonus : "") + ")");
      // Celebrations: visual merge, glow handled by CSS, mini-burst, count-up, floats.
      celebrateVisual();
      try {
        var r = btns[i].getBoundingClientRect();
        burst(r.left + r.width / 2, r.top + r.height / 2, 10);
      } catch (e) {}
      tweenNumber($("scoreVal"), oldScore, state.score, 500);
      pulse($("scorePill"));
      $("streakVal").textContent = state.streak;
      pulse($("streakPill"));
      floatPoints("+" + gained, "good");
      var tier = streakTier(newStreak);
      if (tier) {
        var pop = $("streakPop");
        pop.className = "streak-pop " + tier.cls;
        pop.textContent = tier.msg + " Bonus +" + streakBonus + "!";
        SFX.streak();
      }
      SFX.correct();
      if (newStreak > 0 && newStreak % 5 === 0 && !RM) confetti(25);
    } else {
      state.wrong++;
      state.streak = 0;
      state.lives--;
      btns[i].classList.add("wrong");
      for (var m = 0; m < btns.length; m++) {
        if (q.options[m] === q.ans) btns[m].classList.add("correct");
        else if (m !== i) btns[m].classList.add("dim");
        btns[m].disabled = true;
      }
      showFeedback(false, "❌ Oops! " + q.text.replace("?", q.ans) + "  (−1 ❤️)");
      celebrateVisual(); // reveal the true grouping as a learning aid
      SFX.wrong();
      $("streakVal").textContent = state.streak;
      $("livesVal").textContent = "❤️".repeat(Math.max(0, state.lives)) + "🤍".repeat(Math.max(0, 3 - state.lives));
      pulse($("livesPill"), "life-hit");
      floatPoints("−1 ❤️", "bad");
      setTimeout(advance, 1400);
      return;
    }
    for (var n = 0; n < btns.length; n++) btns[n].disabled = true;
    setTimeout(advance, 1150);
  }

  function onTimeout() {
    if (state.locked) return;
    state.locked = true;
    state.wrong++;
    state.streak = 0;
    state.lives--;
    var q = state.current;
    var btns = $("answers").children;
    for (var m = 0; m < btns.length; m++) {
      if (q.options[m] === q.ans) btns[m].classList.add("correct");
      else btns[m].classList.add("dim");
      btns[m].disabled = true;
    }
    showFeedback(false, "⏰ Time's up! Answer was " + q.ans + "  (−1 ❤️)");
    celebrateVisual();
    SFX.wrong();
    $("streakVal").textContent = state.streak;
    $("livesVal").textContent = "❤️".repeat(Math.max(0, state.lives)) + "🤍".repeat(Math.max(0, 3 - state.lives));
    pulse($("livesPill"), "life-hit");
    floatPoints("−1 ❤️", "bad");
    setTimeout(advance, 1400);
  }

  function showFeedback(good, msg) {
    var fb = $("feedback");
    fb.className = "feedback " + (good ? "good" : "bad");
    fb.textContent = msg;
  }

  function advance() {
    state.index++;
    $("progressFill").style.width = Math.round((state.index / state.total) * 100) + "%";
    nextQuestion();
  }

  // ---------- End of round ----------
  function key(op, diff) { return op + "__" + diff; }

  function awardBadge(id) {
    if (profile.badges.indexOf(id) === -1) {
      profile.badges.push(id);
      state.roundBadges.push(id);
      return true;
    }
    return false;
  }

  function maybeLevelUp(oldL, newL) {
    if (newL <= oldL) return;
    try {
      $("levelUpText").textContent = "You are now Level " + newL + "! 🏆";
      $("levelUpHint").textContent = newL >= 3 ? "Brain power rising! Dare to try 🔥 Hard?" : "New level, new brain power! 🧠";
      var ov = $("levelUpOverlay");
      setTimeout(function () {
        ov.classList.remove("hidden");
        SFX.levelup();
        if (!RM) confetti(40);
        var done = false;
        var hide = function () {
          if (done) return; done = true;
          ov.classList.add("hidden");
          try { ov.removeEventListener("click", hide); } catch (e) {}
        };
        ov.addEventListener("click", hide);
        setTimeout(hide, 2600);
      }, RM ? 100 : 900);
    } catch (e) {}
  }

  function endRound(reason) {
    stopTimer();
    var oldLevel = getLevel(); // before XP is added
    var totalQ = state.correct + state.wrong;
    var acc = totalQ === 0 ? 0 : Math.round((state.correct / totalQ) * 100);
    try { fetch('/api/v1/events', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({event_type:'GAME_COMPLETED', activity_type:'game', activity_id:'maths-explorer', subject_slug:'mathematics', detail:'Maths Explorer round completed', score:state.score, metadata:{operation:state.op, difficulty:state.diff, accuracy:acc}})}).catch(function(){}); } catch (e) {}
    var k = key(state.op, state.diff);
    var prevBest = bestScores[k] || 0;
    var isNewBest = state.score > prevBest;
    if (isNewBest) { bestScores[k] = state.score; saveJSON(LS_BEST, bestScores); }

    // Profile updates (real, no fake scores)
    profile.gamesPlayed = (profile.gamesPlayed || 0) + 1;
    profile.totalCorrect = (profile.totalCorrect || 0) + state.correct;
    profile.totalAnswered = (profile.totalAnswered || 0) + totalQ;
    profile.bestStreakEver = Math.max(profile.bestStreakEver || 0, state.maxStreak);
    profile.xp = (profile.xp || 0) + state.score;
    if (profile.modesPlayed.indexOf(state.op) === -1) profile.modesPlayed.push(state.op);

    // Badges (earned from actual play)
    if (profile.gamesPlayed >= 1) awardBadge("first_steps");
    if (state.maxStreak >= 5) awardBadge("streak5");
    if (state.maxStreak >= 8) awardBadge("streak8");
    if (state.maxStreak >= 10) awardBadge("streak10");
    if (acc === 100 && totalQ >= 5) awardBadge("perfect");
    if (state.fastAnswers >= 1) awardBadge("speed");
    if (state.lives === 1 && state.correct > 0) awardBadge("survivor");
    if (state.score >= 300) awardBadge("high300");
    if (profile.modesPlayed.length >= 5) awardBadge("explorer");
    if (profile.gamesPlayed >= 5) awardBadge("persistent");
    saveJSON(LS_PROFILE, profile);
    var newLevel = getLevel();

    // Results UI — animated: count-up score, staggered stats, accuracy bar, badges one-by-one.
    showScreen("resultsScreen");
    $("rCorrect").textContent = state.correct;
    $("rWrong").textContent = state.wrong;
    $("rAcc").textContent = acc + "%";
    $("rStreak").textContent = "x" + state.maxStreak;
    $("rBest").textContent = bestScores[k] || 0;
    $("rXp").textContent = "+" + state.score + " (Lv " + newLevel + ")";
    try {
      var stats = document.querySelectorAll("#statsGrid .stat");
      for (var si = 0; si < stats.length; si++) {
        (function (c, idx) {
          c.classList.remove("stat-in");
          if (!RM) {
            void c.offsetWidth;
            c.style.animationDelay = (idx * 90) + "ms";
            c.classList.add("stat-in");
            setTimeout(function () { c.classList.remove("stat-in"); c.style.animationDelay = ""; }, 900 + idx * 90);
          }
        })(stats[si], si);
      }
    } catch (e) {}
    $("finalScore").textContent = "0";
    tweenNumber($("finalScore"), 0, state.score, 900);
    try {
      var af = $("accFill");
      af.style.width = "0%";
      setTimeout(function () { af.style.width = acc + "%"; }, RM ? 0 : 200);
    } catch (e) {}
    $("newBestBadge").classList.toggle("hidden", !isNewBest);
    var stars = acc === 100 ? "⭐⭐⭐" : (acc >= 70 ? "⭐⭐" : (acc >= 40 ? "⭐" : "💪"));
    try {
      var sc = $("stars");
      sc.className = "stars star-pop";
      sc.innerHTML = "";
      var chars = Array.from(stars);
      for (var ci = 0; ci < chars.length; ci++) {
        var sp = document.createElement("span");
        sp.textContent = chars[ci];
        if (!RM) sp.style.animationDelay = (300 + ci * 220) + "ms";
        sc.appendChild(sp);
      }
    } catch (e) { $("stars").textContent = stars; }
    var emoji = "🏆", title = "Great Job!";
    if (acc === 100 && totalQ > 0) { emoji = "🌟"; title = "PERFECT! Amazing!"; }
    else if (acc >= 70) { emoji = "🏆"; title = "Great Job!"; }
    else if (acc >= 40) { emoji = "👍"; title = "Good Try! Keep Going!"; }
    else { emoji = "💪"; title = "Don't Give Up!"; }
    if (state.lives <= 0 && state.index < state.total) title += " (Out of lives)";
    $("resultEmoji").textContent = emoji;
    pulse($("resultEmoji"), "celebrate");
    $("resultTitle").textContent = title + " — " + reason;

    var eb = $("earnedBadges");
    eb.innerHTML = "";
    if (state.roundBadges.length === 0) {
      eb.innerHTML = "<span class='small muted'>No new badges this time — keep trying! 💪</span>";
    } else {
      state.roundBadges.forEach(function (id, idx) {
        var b = badgeById(id);
        var d = document.createElement("span");
        d.className = "badge won" + (RM ? "" : " badge-in");
        if (!RM) d.style.animationDelay = (500 + idx * 180) + "ms";
        d.textContent = b.icon + " " + b.name + " — NEW!";
        eb.appendChild(d);
      });
    }
    try { $("againBtn").classList.add("replay"); } catch (e) {}

    renderHome(); // refresh home stats behind
    renderBadgeShelves(false);
    if (acc >= 70) { SFX.win(); confetti(60); } else if (isNewBest) { SFX.win(); confetti(60); }
    maybeLevelUp(oldLevel, newLevel);
  }

  function badgeById(id) {
    for (var i = 0; i < BADGES.length; i++) if (BADGES[i].id === id) return BADGES[i];
    return { icon: "🎖", name: id, desc: "" };
  }

  function confetti(n) {
    if (RM) return;
    try {
      var box = $("confetti");
      box.innerHTML = "";
      var icons = ["⭐", "🎉", "🎊", "🌟", "🎈", "✅", "🏆"];
      var count = n || 60;
      for (var i = 0; i < count; i++) {
        var s = document.createElement("span");
        s.textContent = icons[randInt(0, icons.length - 1)];
        s.style.left = Math.random() * 100 + "vw";
        s.style.animationDuration = (2 + Math.random() * 2) + "s";
        s.style.fontSize = (16 + Math.random() * 22) + "px";
        box.appendChild(s);
      }
      setTimeout(function () { box.innerHTML = ""; }, 4500);
    } catch (e) {}
  }

  // ---------- Home rendering ----------
  function renderHome() {
    $("homeLevel").textContent = getLevel();
    $("homeXp").textContent = profile.xp || 0;
    $("homeBestStreak").textContent = profile.bestStreakEver || 0;
    $("homeGames").textContent = profile.gamesPlayed || 0;
    $("homeLevelFill").style.width = levelProgress() + "%";
    $("homeLevelText").textContent = levelProgress() + "% to Level " + (getLevel() + 1) + " (earn XP by scoring points!)";
    var box = $("bestScores");
    box.innerHTML = "";
    var ops = ["addition", "subtraction", "multiplication", "division", "mixed"];
    var diffs = ["easy", "medium", "hard"];
    var any = false;
    ops.forEach(function (op) {
      diffs.forEach(function (df) {
        var v = bestScores[key(op, df)] || 0;
        if (v > 0) {
          any = true;
          var row = document.createElement("div");
          row.className = "best-row";
          row.innerHTML = "<span>" + OP_LABEL[op] + " • " + DIFF_LABEL[df] + "</span><b>⭐ " + v + "</b>";
          box.appendChild(row);
        }
      });
    });
    if (!any) box.innerHTML = "<span class='small muted'>No scores yet — play your first game! 🎮</span>";
  }

  function renderBadgeShelves(stagger) {
    var shelves = ["badgeShelf", "badgeShelf2"];
    for (var s = 0; s < shelves.length; s++) {
      var box = $(shelves[s]);
      if (!box) continue;
      box.innerHTML = "";
      for (var bi = 0; bi < BADGES.length; bi++) {
        var b = BADGES[bi];
        var won = profile.badges.indexOf(b.id) !== -1;
        var d = document.createElement("div");
        d.className = "badge" + (won ? " won" : "") + ((stagger && won && !RM) ? " badge-in" : "");
        if (stagger && won && !RM) d.style.animationDelay = (bi * 90) + "ms";
        d.title = b.desc;
        d.textContent = (won ? b.icon + " " + b.name : "🔒 " + b.name);
        box.appendChild(d);
      }
    }
  }

  // ---------- Selectors ----------
  function selectOnly(selector, btn) {
    var all = document.querySelectorAll(selector);
    for (var i = 0; i < all.length; i++) all[i].classList.remove("selected");
    btn.classList.add("selected");
  }

  function bindSelectors() {
    var ops = document.querySelectorAll(".op-btn");
    for (var i = 0; i < ops.length; i++) {
      ops[i].addEventListener("click", function () {
        selectOnly(".op-btn", this);
        state.op = this.getAttribute("data-op");
        SFX.click();
      });
    }
    var diffs = document.querySelectorAll(".diff-btn");
    for (var j = 0; j < diffs.length; j++) {
      diffs[j].addEventListener("click", function () {
        selectOnly(".diff-btn", this);
        state.diff = this.getAttribute("data-diff");
        SFX.click();
      });
    }
    var counts = document.querySelectorAll(".count-btn");
    for (var c = 0; c < counts.length; c++) {
      counts[c].addEventListener("click", function () {
        selectOnly(".count-btn", this);
        state.total = parseInt(this.getAttribute("data-count"), 10) || 10;
        SFX.click();
      });
    }
  }

  // ---------- Events ----------
  function bindEvents() {
    $("startBtn").addEventListener("click", function () { SFX.click(); startRound(); });
    $("againBtn").addEventListener("click", function () { SFX.click(); startRound(); });
    $("homeBtn").addEventListener("click", function () { SFX.click(); showScreen("homeScreen"); });
    $("quitBtn").addEventListener("click", function () {
      SFX.click(); stopTimer();
      if (state.correct + state.wrong === 0) showScreen("homeScreen");
      else endRound("You quit early. 🏳");
    });
    $("muteBtn").addEventListener("click", toggleMute);
    $("muteBtn2").addEventListener("click", toggleMute);
    $("helpBtn").addEventListener("click", function () { SFX.click(); $("helpModal").classList.remove("hidden"); });
    $("closeHelp").addEventListener("click", function () { SFX.click(); $("helpModal").classList.add("hidden"); });
    $("helpModal").addEventListener("click", function (e) { if (e.target === this) this.classList.add("hidden"); });
    $("resetScoresBtn").addEventListener("click", function () {
      if (confirm("Clear all saved scores, XP and badges on this computer?")) {
        bestScores = {};
        profile = { xp: 0, gamesPlayed: 0, totalCorrect: 0, totalAnswered: 0, bestStreakEver: 0, badges: [], modesPlayed: [] };
        saveJSON(LS_BEST, bestScores);
        saveJSON(LS_PROFILE, profile);
        renderHome(); renderBadgeShelves(false);
      }
    });
    document.addEventListener("keydown", function (e) {
      if ($("helpModal") && !$("helpModal").classList.contains("hidden")) {
        if (e.key === "Escape" || e.key === "Enter") $("helpModal").classList.add("hidden");
        return;
      }
      if (!$("gameScreen").classList.contains("active")) return;
      if (e.key >= "1" && e.key <= "4") {
        var idx = parseInt(e.key, 10) - 1;
        var btns = $("answers").children;
        if (btns[idx] && !btns[idx].disabled) answer(idx);
      }
    });
  }

  // ---------- Init (offline self-test, logs to console only) ----------
  function selfTest() {
    try {
      // Verify division always yields whole numbers & 4 unique options
      for (var i = 0; i < 50; i++) {
        var keepOp = state.op, keepDiff = state.diff, keepIdx = state.index, keepTotal = state.total;
        state.op = ["addition", "subtraction", "multiplication", "division", "mixed"][i % 5];
        state.diff = ["easy", "medium", "hard"][i % 3];
        state.index = i % 10; state.total = 10;
        var q = makeQuestion();
        if (q.options.length !== 4) console.warn("selfTest: options != 4");
        var uniq = {};
        q.options.forEach(function (o) { uniq[o] = true; });
        if (Object.keys(uniq).length !== 4) console.warn("selfTest: duplicate options");
        if (q.options.indexOf(q.ans) === -1) console.warn("selfTest: answer missing");
        if (q.op === "division" && (q.a % q.b !== 0)) console.warn("selfTest: non-whole division");
        if (q.op === "division" && q.ans !== q.a / q.b) console.warn("selfTest: division answer mismatch");
        if (q.op === "addition" && q.ans !== q.a + q.b) console.warn("selfTest: addition answer mismatch");
        if (q.op === "subtraction" && (q.ans !== q.a - q.b || q.ans < 0)) console.warn("selfTest: subtraction answer mismatch");
        if (q.op === "multiplication" && q.ans !== q.a * q.b) console.warn("selfTest: multiplication answer mismatch");
        // Visual plan must reflect the REAL question
        var p = planVisual(q);
        if (p.answer !== q.ans) console.warn("selfTest: visual answer mismatch for " + q.op);
        state.op = keepOp; state.diff = keepDiff; state.index = keepIdx; state.total = keepTotal;
      }
      // Exactness: small questions must be drawn dot-for-dot (no capping surprises)
      var samples = [
        { op: "addition", a: 7, b: 5, ans: 12 },
        { op: "addition", a: 150, b: 200, ans: 350 },
        { op: "subtraction", a: 9, b: 4, ans: 5 },
        { op: "subtraction", a: 120, b: 45, ans: 75 },
        { op: "multiplication", a: 3, b: 4, ans: 12 },
        { op: "multiplication", a: 12, b: 12, ans: 144 },
        { op: "division", a: 12, b: 3, ans: 4 },
        { op: "division", a: 132, b: 12, ans: 11 }
      ];
      for (var s = 0; s < samples.length; s++) {
        var sq = samples[s], sp = planVisual(sq);
        if (sp.answer !== sq.ans) console.warn("selfTest: sample visual mismatch " + JSON.stringify(sq));
        if (sq.op === "addition" && sq.a <= 15 && sq.b <= 15 && (sp.aShow !== sq.a || sp.bShow !== sq.b || sp.capped))
          console.warn("selfTest: small addition should be exact " + JSON.stringify(sq));
        if (sq.op === "addition" && sq.a > 15 && !sp.capped)
          console.warn("selfTest: big addition should be capped " + JSON.stringify(sq));
        if (sq.op === "subtraction" && sq.a <= 30 && (sp.aShow !== sq.a || sp.takeShow !== sq.b || sp.capped))
          console.warn("selfTest: small subtraction should be exact " + JSON.stringify(sq));
        if (sq.op === "multiplication" && sq.a <= 6 && sq.b <= 6 && (sp.gShow !== sq.a || sp.perShow !== sq.b || sp.capped))
          console.warn("selfTest: small multiplication should be exact " + JSON.stringify(sq));
        if (sq.op === "division" && sq.a <= 24 && (sp.boxes !== sq.b || sp.dots !== sq.a || sp.capped))
          console.warn("selfTest: small division should be exact " + JSON.stringify(sq));
        if (sq.op === "division" && sq.a > 24 && !sp.capped)
          console.warn("selfTest: big division should be capped " + JSON.stringify(sq));
      }
    } catch (e) { console.warn("selfTest failed", e); }
  }

  updateMuteUI();
  renderHome();
  renderBadgeShelves(false);
  bindSelectors();
  bindEvents();
  selfTest();
})();
