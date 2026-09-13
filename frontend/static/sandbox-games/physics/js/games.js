/* PhysicsGame mini-games G1–G4. All outcomes computed live with PHYS engine.
   Plain script for file://. Depends on: PHYS, STORE, APP. */
"use strict";
var GAMES = (function () {
  var $ = APP.$;
  var RM = APP.RM();

  function optsBox(el, labels, cb) {
    el.innerHTML = "";
    var btns = [];
    labels.forEach(function (txt, i) {
      var b = document.createElement("button");
      b.className = "answer sm gopt";
      b.innerHTML = "<b>" + (i + 1) + ".</b> " + txt;
      b.addEventListener("click", function () { cb(i, btns); });
      el.appendChild(b);
      btns.push(b);
    });
    return btns;
  }
  function lockBtns(btns, goodIdx, picked) {
    for (var i = 0; i < btns.length; i++) btns[i].disabled = true;
    if (goodIdx !== null && goodIdx !== undefined) btns[goodIdx].classList.add("correct");
    if (picked !== null && picked !== undefined && picked !== goodIdx) btns[picked].classList.add("wrong");
  }

  // ================= GAME 1 — FORCE CHALLENGE =================
  var G1 = { round: 0, tries: 0, D: 8, m: 2, mu: 0.2, T: 1.5, F: 18, b: null, phase: "aim", t: 0, total: 0, scores: [] };
  function g1fit() {
    var f = PHYS.fitCanvas($("g1c"), 230);
    G1.ctx = f.ctx; G1.w = f.w; G1.h = f.h;
    g1draw();
  }
  function g1newRound() {
    G1.round++;
    G1.tries = 0;
    G1.D = Math.round((6 + Math.random() * 6) * 10) / 10;
    G1.b = PHYS.body1D(G1.m, 0.5, 0);
    G1.phase = "aim"; G1.t = 0;
    $("g1Target").textContent = "Round " + G1.round + "/3 — land the cart at the 🚩 " + G1.D.toFixed(1) + " m flag! (push lasts " + G1.T + " s, then friction stops it)";
    $("g1Info").textContent = "Pick a force and press LAUNCH. Green zone = ±0.5 m.";
    $("g1Launch").disabled = false;
    g1draw();
  }
  function g1launch() {
    if (G1.phase !== "aim") return;
    G1.b = PHYS.body1D(G1.m, 0.5, 0);
    G1.F = parseFloat($("g1Force").value);
    G1.phase = "push"; G1.t = 0; G1.tries++;
    $("g1Launch").disabled = true;
    APP.SFX.pop();
  }
  function g1step(dt) {
    if (G1.phase === "push" || G1.phase === "coast") {
      var Fa = G1.phase === "push" ? G1.F : 0;
      PHYS.step1D(G1.b, Fa, G1.mu, dt);
      G1.t += dt;
      if (G1.phase === "push" && G1.t >= G1.T) { G1.phase = "coast"; }
      if (G1.phase === "coast" && Math.abs(G1.b.v) < 0.02) {
        G1.phase = "done";
        var err = Math.abs(G1.b.x - G1.D);
        var sc = Math.max(0, Math.round(100 - 30 * err - 10 * (G1.tries - 1)));
        if (err <= 0.5) {
          G1.scores.push(sc); G1.total += sc;
          $("g1Info").className = "feedback good";
          $("g1Info").textContent = "🎯 Bullseye! Stopped at " + G1.b.x.toFixed(2) + " m (target " + G1.D.toFixed(1) + ") +" + sc + " pts";
          APP.verdict(true, 30);
          APP.confetti(40);
          STORE.award("sharp");
          setTimeout(g1after, 1800);
        } else {
          $("g1Info").className = "feedback bad";
          $("g1Info").textContent = "Stopped at " + G1.b.x.toFixed(2) + " m — off by " + err.toFixed(2) + " m. " +
            (G1.b.x < G1.D ? "Too SHORT → push harder! 💪" : "Too FAR → ease off! 🪶") + " Try again!";
          APP.verdict(false, 0);
          G1.phase = "aim";
          $("g1Launch").disabled = false;
        }
        g1score();
      }
    }
  }
  function g1after() {
    if (G1.round >= 3) {
      var xp = Math.min(75, Math.round(G1.total / 4));
      STORE.best("g1", G1.total);
      APP.reward(xp, null);
      $("g1Info").className = "feedback good";
      $("g1Info").textContent = "🏁 Tournament over! Total: " + G1.total + "/300 (best saved!). Play again to beat it!";
      $("g1Launch").disabled = true;
      var b = document.createElement("button");
      b.className = "big-btn";
      b.textContent = "🔁 Play Again";
      b.addEventListener("click", function () { APP.SFX.click(); b.remove(); g1start(); });
      $("screen-g1").querySelector(".card").appendChild(b);
      G1.phase = "over";
    } else g1newRound();
  }
  function g1score() { $("g1Score").textContent = "Score: " + G1.total + " pts • Round " + G1.round + "/3 • Try #" + (G1.tries + (G1.phase === "aim" ? 1 : 0)); }
  function g1draw() {
    var ctx = G1.ctx; if (!ctx) return;
    var w = G1.w, h = G1.h, gy = h - 46, pad = 26, world = 14;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0b1220"; ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = "#1e293b"; ctx.fillRect(0, gy, w, h - gy);
    ctx.fillStyle = "#334155";
    for (var x = 0; x < w; x += 14) ctx.fillRect(x, gy + 8, 4, 4);
    var X = function (xm) { return pad + (xm / world) * (w - 2 * pad); };
    // target zone
    ctx.fillStyle = "rgba(34,197,94,.3)";
    ctx.fillRect(X(G1.D - 0.5), gy - 60, X(G1.D + 0.5) - X(G1.D - 0.5), 60);
    ctx.font = "26px sans-serif"; ctx.fillText("🚩", X(G1.D) - 13, gy - 34);
    ctx.fillStyle = "#e2e8f0"; ctx.font = "bold 11px sans-serif";
    ctx.fillText(G1.D.toFixed(1) + "m", X(G1.D) - 16, gy + 22);
    // cart
    var cx = X(Math.max(0.3, Math.min(G1.b.x, world - 0.3)));
    ctx.fillStyle = "#f59e0b";
    ctx.fillRect(cx - 20, gy - 30, 40, 22);
    ctx.fillStyle = "#0f172a";
    ctx.beginPath(); ctx.arc(cx - 11, gy - 5, 6, 0, 7); ctx.arc(cx + 11, gy - 5, 6, 0, 7); ctx.fill();
    if (G1.phase === "push") PHYS.drawArrow(ctx, cx + 24, gy - 26, cx + 24 + G1.F * 2.4, gy - 26, "#22c55e", 4, G1.F.toFixed(0) + "N");
    if (Math.abs(G1.b.v) > 0.2) PHYS.drawArrow(ctx, cx, gy - 48, cx + G1.b.v * 10, gy - 48, "#38bdf8", 3, "v");
    ctx.fillStyle = "#e2e8f0"; ctx.font = "bold 12px sans-serif";
    ctx.fillText("m=2kg  μ=0.2  push=" + G1.T + "s", 8, 16);
  }
  function g1start() {
    G1.round = 0; G1.total = 0; G1.scores = [];
    g1newRound(); g1score();
  }

  // ================= GAME 2 — INERTIA DETECTIVE =================
  var CASES = [
    { kind: "rest", name: "🪙 The coin & card", hint: "Card flicked away, coin drops in the glass." },
    { kind: "motion", name: "🚌 The sudden bus stop", hint: "Bus brakes hard, standing passengers lurch." },
    { kind: "direction", name: "↩️ The sharp turn", hint: "Car turns left, passenger slides right." },
    { kind: "rest", name: "🍽️ The tablecloth trick", hint: "Cloth yanked fast, dishes stay on the table." },
    { kind: "motion", name: "📦 The braking truck", hint: "Truck brakes, loose crate slides forward." },
    { kind: "direction", name: "🚴 The turning cyclist", hint: "Bike turns, loose bag keeps going straight." }
  ];
  var G2 = { round: 0, score: 0, order: [], cur: null, lock: true };
  function g2fit() {
    var f = PHYS.fitCanvas($("g2c"), 200);
    G2.ctx = f.ctx; G2.w = f.w; G2.h = f.h;
    if (G2.cur) g2draw(3.9);
  }
  function g2draw(t) {
    var ctx = G2.ctx; if (!ctx || !G2.cur) return;
    var w = G2.w, h = G2.h, gy = h - 24;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0b1220"; ctx.fillRect(0, 0, w, h);
    var k = G2.cur.kind, i = G2.cur.idx;
    ctx.fillStyle = "#e2e8f0"; ctx.font = "bold 13px sans-serif";
    ctx.fillText("CASE " + G2.round + "/5: " + G2.cur.name, 8, 16);
    ctx.font = "12px sans-serif"; ctx.fillStyle = "#94a3b8";
    ctx.fillText("Watch, then answer: rest / motion / direction?", 8, 32);
    if (k === "rest" && i === 0) {
      var gx = w / 2;
      ctx.strokeStyle = "#93c5fd"; ctx.lineWidth = 3; ctx.strokeRect(gx - 26, gy - 70, 52, 46);
      var cx = t < 0.3 ? gx + t * 500 : gx + 150 + (t - 0.3) * 500;
      ctx.fillStyle = "#f59e0b"; ctx.fillRect(cx - 50, gy - 80, 100, 10);
      var fall = Math.max(0, t - 0.3), cy = gy - 86 + 0.5 * 500 * fall * fall;
      if (cy > gy - 30) cy = gy - 30;
      ctx.fillStyle = "#fde047"; ctx.beginPath(); ctx.arc(gx, cy, 8, 0, 7); ctx.fill();
    } else if (k === "rest") {
      var off = t < 0.4 ? t * 500 : 200 + (t - 0.4) * 60;
      ctx.fillStyle = "#a16207"; ctx.fillRect(30 + Math.min(off, 220), gy - 60, 160, 12);
      ctx.fillStyle = "#e2e8f0";
      ctx.fillRect(w / 2 - 40, gy - 78, 26, 18); ctx.fillRect(w / 2 + 14, gy - 78, 26, 18);
      ctx.fillText("🍽️ dishes never moved!", w / 2 - 60, gy - 86);
    } else if (k === "motion" && i === 1) {
      ctx.fillStyle = "#1e293b"; ctx.fillRect(0, gy, w, h - gy);
      var v = 110, bx = t < 1.5 ? 20 + v * t : 20 + v * 1.5 + v * (t - 1.5) - 80 * (t - 1.5) * (t - 1.5);
      var ts = 1.5 + v / 160;
      if (t >= ts) bx = 20 + v * 1.5 + v * (v / 160) - 80 * (v / 160) * (v / 160);
      var px = 60 + v * t;
      if (px > bx + 118) px = bx + 118;
      ctx.fillStyle = "#f59e0b"; ctx.fillRect(bx, gy - 62, 140, 44);
      ctx.font = "24px sans-serif"; ctx.fillText("🧍", px, gy - 40);
    } else if (k === "motion") {
      ctx.fillStyle = "#1e293b"; ctx.fillRect(0, gy, w, h - gy);
      var v2 = 120, tx = t < 1.4 ? 20 + v2 * t : 20 + v2 * 1.4 + v2 * (t - 1.4) - 90 * (t - 1.4) * (t - 1.4);
      var ts2 = 1.4 + v2 / 180;
      if (t >= ts2) tx = 20 + v2 * 1.4 + v2 * (v2 / 180) - 90 * (v2 / 180) * (v2 / 180);
      var crate = 50 + v2 * t;
      if (crate > tx + 96) crate = tx + 96;
      ctx.fillStyle = "#64748b"; ctx.fillRect(tx, gy - 56, 120, 40);
      ctx.fillStyle = "#f59e0b"; ctx.fillRect(crate, gy - 78, 26, 22);
      ctx.fillStyle = "#e2e8f0"; ctx.font = "12px sans-serif";
      ctx.fillText("📦 crate slides forward as truck brakes!", 8, 48);
    } else {
      var ccx = w / 2, up = 80 * t, turn = Math.max(0, t - 1.2);
      var carx = ccx + turn * 70, cary = h - 30 - up + turn * 30;
      ctx.strokeStyle = "#334155"; ctx.beginPath(); ctx.moveTo(ccx - 30, 0); ctx.lineTo(ccx - 30, h); ctx.stroke();
      ctx.fillStyle = "#38bdf8"; ctx.fillRect(carx - 14, cary - 22, 28, 44);
      var perx = ccx, pery = h - 54 - 80 * t;
      var ddx = perx - carx, ddy = pery - cary, dd = Math.hypot(ddx, ddy);
      if (dd > 13) { perx = carx + ddx / dd * 13; pery = cary + ddy / dd * 13; }
      ctx.font = "15px sans-serif"; ctx.fillText("🧍", perx - 8, pery + 5);
      ctx.fillStyle = "#e2e8f0"; ctx.font = "12px sans-serif";
      ctx.fillText("↩️ vehicle turns — rider keeps straight!", 8, 48);
    }
  }
  function g2play() {
    var t0 = null;
    function fr(t) {
      if (!t0) t0 = t;
      var e = (t - t0) / 1000;
      g2draw(Math.min(e, 3.9));
      if (e < 3.9) requestAnimationFrame(fr);
    }
    requestAnimationFrame(fr);
  }
  function g2next() {
    if (G2.order.length === 0) return g2end();
    G2.round++;
    G2.cur = G2.order.pop();
    G2.lock = false;
    $("g2Fb").className = "feedback hidden";
    $("g2Fb").textContent = "";
    g2play();
    optsBox($("g2Opts"), ["🪙 Inertia of REST (stays still)", "🚌 Inertia of MOTION (keeps moving)", "↩️ Inertia of DIRECTION (keeps direction)"], function (i, btns) {
      if (G2.lock) return;
      G2.lock = true;
      var good = { rest: 0, motion: 1, direction: 2 }[G2.cur.kind];
      var ok = i === good;
      lockBtns(btns, good, i);
      var fb = $("g2Fb");
      fb.className = "feedback " + (ok ? "good" : "bad");
      fb.textContent = ok ? "✅ Correct detective work! +" : "❌ It was " + ["REST", "MOTION", "DIRECTION"][good] + ". ";
      if (ok) { G2.score++; APP.verdict(true, 25); APP.confetti(20); }
      else APP.verdict(false, 0);
      $("g2Score").textContent = "Solved: " + G2.score + "/" + (G2.round) + " • Case " + G2.round + "/5";
      setTimeout(g2next, 1900);
    });
  }
  function g2end() {
    STORE.best("g2", G2.score * 20);
    var xp = 15 + G2.score * 10;
    APP.reward(xp, G2.score >= 4 ? "detective" : null);
    $("g2Fb").className = "feedback good";
    $("g2Fb").textContent = "🏁 Casebook closed! You solved " + G2.score + "/5. " + (G2.score >= 4 ? "🔍 Inertia Detective badge earned!" : "Play again to earn the Detective badge (4+)!");
    var b = document.createElement("button");
    b.className = "big-btn"; b.textContent = "🔁 New Cases";
    b.addEventListener("click", function () { APP.SFX.click(); b.remove(); g2start(); });
    $("screen-g2").querySelector(".card").appendChild(b);
  }
  function g2start() {
    G2.order = CASES.map(function (c, i) { return { kind: c.kind, name: c.name, idx: i }; })
      .sort(function () { return Math.random() - 0.5; }).slice(0, 5);
    G2.round = 0; G2.score = 0;
    $("g2Score").textContent = "Solved: 0/0 • Case 0/5";
    g2next();
  }

  // ================= GAME 3 — LAW MATCH =================
  var SIT = [
    { s: "🧍 Bus stops, passengers lurch forward", law: 1 },
    { s: "🧹 Dust flies out when carpet is beaten", law: 1 },
    { s: "🪙 Coin drops in glass when card is flicked", law: 1 },
    { s: "📦 A loaded truck needs a bigger push than an empty one", law: 2 },
    { s: "⚽ Kicking a ball harder makes it accelerate more", law: 2 },
    { s: "🏎️ Same engine, lighter car speeds up faster", law: 2 },
    { s: "🚀 Rocket throws gas down, rocket goes up", law: 3 },
    { s: "🏊 Swimmer pushes the wall, glides forward", law: 3 },
    { s: "🎈 Air rushes out back, balloon zooms forward", law: 3 }
  ];
  var G3 = { round: 0, score: 0, order: [], lock: true };
  function g3next() {
    if (G3.order.length === 0) return g3end();
    G3.round++;
    var cur = G3.order.pop();
    G3.lock = false;
    $("g3Sit").textContent = "Situation " + G3.round + "/6: " + cur.s;
    $("g3Fb").className = "feedback hidden";
    optsBox($("g3Opts"), ["🥌 Newton's 1st Law (inertia)", "🚀 Newton's 2nd Law (F = ma)", "🎈 Newton's 3rd Law (action–reaction)"], function (i, btns) {
      if (G3.lock) return;
      G3.lock = true;
      var good = cur.law - 1, ok = i === good;
      lockBtns(btns, good, i);
      var fb = $("g3Fb");
      var why = ["1st: objects resist changes (inertia).", "2nd: force & mass decide acceleration (F=ma).", "3rd: equal & opposite reaction."];
      fb.className = "feedback " + (ok ? "good" : "bad");
      fb.textContent = (ok ? "✅ Correct! " : "❌ It was Law " + cur.law + ". ") + why[cur.law - 1];
      if (ok) { G3.score++; APP.verdict(true, 20); APP.confetti(15); }
      else APP.verdict(false, 0);
      $("g3Score").textContent = "Matched: " + G3.score + "/" + G3.round + " • Q " + G3.round + "/6";
      setTimeout(g3next, 2000);
    });
  }
  function g3end() {
    STORE.best("g3", G3.score * 20);
    APP.reward(10 + G3.score * 10, G3.score >= 5 ? "apprentice" : null);
    $("g3Fb").className = "feedback good";
    $("g3Fb").textContent = "🏁 You matched " + G3.score + "/6! " + (G3.score >= 5 ? "🍎 Newton's Apprentice badge earned!" : "Score 5+ to earn the Apprentice badge!");
    var b = document.createElement("button");
    b.className = "big-btn"; b.textContent = "🔁 Play Again";
    b.addEventListener("click", function () { APP.SFX.click(); b.remove(); g3start(); });
    $("screen-g3").querySelector(".card").appendChild(b);
  }
  function g3start() {
    G3.order = SIT.slice().sort(function () { return Math.random() - 0.5; }).slice(0, 6);
    G3.round = 0; G3.score = 0;
    $("g3Score").textContent = "Matched: 0/0 • Q 0/6";
    g3next();
  }

  // ================= GAME 4 — PREDICT THE MOTION =================
  // Scenario kinds generated from real params; outcome simulated live.
  var G4 = { round: 0, score: 0, cur: null, lock: true, anim: null };
  function g4make() {
    var kinds = ["accel", "const", "stop", "turn"];
    var kind = kinds[Math.floor(Math.random() * kinds.length)];
    var c;
    if (kind === "accel") c = { kind: kind, v0: 2, F: { x: 12, y: 0 }, mu: 0, ans: 0, why: "Unbalanced forward force → it ACCELERATES (F=ma)!" };
    else if (kind === "const") c = { kind: kind, v0: 4, F: { x: 0, y: 0 }, mu: 0, ans: 2, why: "No net force in space → CONSTANT velocity (1st Law)!" };
    else if (kind === "stop") c = { kind: kind, v0: 5, F: { x: 0, y: 0 }, mu: 0.4, ans: 1, why: "Friction opposes motion → it slows and STOPS!" };
    else c = { kind: kind, v0: 4, F: { x: 0, y: 10 }, mu: 0, ans: 3, why: "A sideways force bends the path → it CHANGES DIRECTION!" };
    return c;
  }
  function g4fit() {
    var f = PHYS.fitCanvas($("g4c"), 220);
    G4.ctx = f.ctx; G4.w = f.w; G4.h = f.h;
    if (G4.cur) g4frame(0, false);
  }
  function g4frame(t, live) {
    var ctx = G4.ctx; if (!ctx || !G4.cur) return;
    var w = G4.w, h = G4.h, c = G4.cur;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0b1220"; ctx.fillRect(0, 0, w, h);
    // integrate from t=0 to t for honest positions
    var p = PHYS.body2D(2, w / 2 - 120, h / 2, c.v0 * 22, 0);
    var dt = 1 / 60, tt = 0;
    var trail = [];
    while (tt < t) {
      PHYS.step2D(p, c.F.x, -c.F.y, c.mu, dt); // -y: screen up
      tt += dt;
      if (trail.length === 0 || tt % 0.08 < dt) trail.push([p.x, p.y]);
    }
    ctx.strokeStyle = "rgba(56,189,248,.5)"; ctx.lineWidth = 2;
    ctx.beginPath();
    for (var i = 0; i < trail.length; i++) { if (i === 0) ctx.moveTo(trail[i][0], trail[i][1]); else ctx.lineTo(trail[i][0], trail[i][1]); }
    ctx.stroke();
    var bx = Math.max(16, Math.min(w - 16, p.x)), by = Math.max(30, Math.min(h - 16, p.y));
    ctx.font = "26px sans-serif"; ctx.fillText("⚽", bx - 13, by + 9);
    if (c.F.x || c.F.y) PHYS.drawArrow(ctx, bx, by, bx + c.F.x * 4, by - c.F.y * 4, "#22c55e", 4, "F");
    var sp = Math.hypot(p.vx, p.vy);
    if (sp > 8) PHYS.drawArrow(ctx, bx, by - 22, bx + p.vx * 1.1, by - 22 - p.vy * 1.1, "#38bdf8", 3, "v");
    if (c.mu > 0) { ctx.fillStyle = "#f87171"; ctx.font = "bold 11px sans-serif"; ctx.fillText("rough ground μ=" + c.mu, 8, h - 8); }
    else { ctx.fillStyle = "#67e8f9"; ctx.font = "bold 11px sans-serif"; ctx.fillText("frictionless ice / space ✨", 8, h - 8); }
    if (!live) {
      ctx.fillStyle = "rgba(2,6,23,.55)"; ctx.fillRect(0, 0, w, h);
      ctx.fillStyle = "#fbbf24"; ctx.font = "bold 22px sans-serif"; ctx.textAlign = "center";
      ctx.fillText("⏸ PAUSED — what happens next?", w / 2, 34);
      ctx.textAlign = "left";
    }
  }
  function g4ask() {
    G4.cur = g4make();
    G4.lock = false;
    g4frame(0, false);
    $("g4Fb").className = "feedback hidden";
    optsBox($("g4Opts"), ["🚀 Accelerate", "🛑 Stop", "➡️ Continue at constant velocity", "↩️ Change direction"], function (i, btns) {
      if (G4.lock) return;
      G4.lock = true;
      var ok = i === G4.cur.ans;
      lockBtns(btns, null, null);
      for (var k = 0; k < btns.length; k++) btns[k].disabled = true;
      $("g4Fb").className = "feedback";
      $("g4Fb").textContent = "🎬 Running the real physics… watch!";
      // animate the true outcome
      var t0 = null;
      function fr(t) {
        if (!t0) t0 = t;
        var e = (t - t0) / 1000;
        g4frame(Math.min(e, 2.6), true);
        if (e < 2.6) requestAnimationFrame(fr);
        else {
          var fb = $("g4Fb");
          fb.className = "feedback " + (ok ? "good" : "bad");
          fb.textContent = (ok ? "✅ You predicted it! " : "❌ The answer was: " + ["Accelerate", "Stop", "Constant velocity", "Change direction"][G4.cur.ans] + ". ") + G4.cur.why;
          lockBtns(btns, G4.cur.ans, i);
          if (ok) { G4.score++; APP.verdict(true, 25); APP.confetti(20); }
          else APP.verdict(false, 0);
          $("g4Score").textContent = "Predicted: " + G4.score + "/" + G4.round + " • Q " + G4.round + "/5";
          setTimeout(function () {
            if (G4.round >= 5) g4end();
            else { G4.round++; g4ask(); $("g4Score").textContent = "Predicted: " + G4.score + "/" + (G4.round - 1) + " • Q " + G4.round + "/5"; }
          }, 2400);
        }
      }
      requestAnimationFrame(fr);
    });
  }
  function g4end() {
    STORE.best("g4", G4.score * 20);
    APP.reward(10 + G4.score * 10, null);
    $("g4Fb").className = "feedback good";
    $("g4Fb").textContent = "🏁 You predicted " + G4.score + "/5 correctly! The physics never lies. ⚛️";
    var b = document.createElement("button");
    b.className = "big-btn"; b.textContent = "🔁 Play Again";
    b.addEventListener("click", function () { APP.SFX.click(); b.remove(); g4start(); });
    $("screen-g4").querySelector(".card").appendChild(b);
  }
  function g4start() {
    G4.round = 1; G4.score = 0;
    $("g4Score").textContent = "Predicted: 0/0 • Q 1/5";
    g4ask();
  }

  function init() {
    // G1
    g1fit(); window.addEventListener("resize", function () { try { if ($("g1c").offsetParent !== null) g1fit(); } catch (e) {} });
    G1.b = PHYS.body1D(G1.m, 0.5, 0);
    G1.loop = PHYS.makeLoop(g1step, g1draw);
    $("g1Force").addEventListener("input", function () { $("g1ForceV").textContent = parseFloat($("g1Force").value).toFixed(0) + " N"; });
    $("g1Launch").addEventListener("click", function () { g1launch(); });
    $("g1Start").addEventListener("click", function () {
      APP.SFX.click(); g1fit();
      var old = $("screen-g1").querySelectorAll(".big-btn");
      for (var i = 0; i < old.length; i++) if (old[i].id !== "g1Start" && old[i].id !== "g1Launch") old[i].remove();
      g1start();
    });
    // G2
    g2fit(); window.addEventListener("resize", function () { try { if ($("g2c").offsetParent !== null) g2fit(); } catch (e) {} });
    $("g2Start").addEventListener("click", function () {
      APP.SFX.click(); g2fit();
      var old = $("screen-g2").querySelectorAll(".big-btn");
      for (var i = 0; i < old.length; i++) if (old[i].id !== "g2Start") old[i].remove();
      g2start();
    });
    // G3
    $("g3Start").addEventListener("click", function () {
      APP.SFX.click();
      var old = $("screen-g3").querySelectorAll(".big-btn");
      for (var i = 0; i < old.length; i++) if (old[i].id !== "g3Start") old[i].remove();
      g3start();
    });
    // G4
    g4fit(); window.addEventListener("resize", function () { try { if ($("g4c").offsetParent !== null) g4fit(); } catch (e) {} });
    $("g4Start").addEventListener("click", function () {
      APP.SFX.click(); g4fit();
      var old = $("screen-g4").querySelectorAll(".big-btn");
      for (var i = 0; i < old.length; i++) if (old[i].id !== "g4Start") old[i].remove();
      g4start();
    });
    // keyboard 1-4 for options on game screens
    document.addEventListener("keydown", function (e) {
      var n = parseInt(e.key, 10);
      if (!(n >= 1 && n <= 4)) return;
      var active = document.querySelector(".screen.active");
      if (!active) return;
      if (["screen-g2", "screen-g3", "screen-g4"].indexOf(active.id) === -1) return;
      var btns = active.querySelectorAll(".gopt");
      if (btns[n - 1] && !btns[n - 1].disabled) btns[n - 1].click();
    });
  }

  return { init: init };
})();
