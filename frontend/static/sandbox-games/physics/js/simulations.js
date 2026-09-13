/* PhysicsGame simulations — every number comes from PHYS engine (F=ma).
   Law1, Law2 (+target challenge), Law3 (carts/rocket/balloon),
   Inertia lab (rest/motion/direction), Free lab. Plain script for file://. */
"use strict";
var SIM = (function () {
  var $ = APP.$;
  var RM = APP.RM();
  var canvases = [];
  function reg(cv, fit) { canvases.push({ cv: cv, fit: fit }); }
  window.addEventListener("resize", function () {
    for (var i = 0; i < canvases.length; i++) {
      try { if (canvases[i].cv.offsetParent !== null) canvases[i].fit(); } catch (e) {}
    }
  });

  function ground(ctx, w, h, gy) {
    ctx.fillStyle = "#1e293b"; ctx.fillRect(0, gy, w, h - gy);
    ctx.fillStyle = "#334155";
    for (var x = 0; x < w; x += 14) ctx.fillRect(x, gy + 8, 4, 4);
  }
  function markers(ctx, w, gy, world, pad) {
    ctx.fillStyle = "#94a3b8"; ctx.font = "10px sans-serif"; ctx.textAlign = "center";
    for (var m = 0; m <= world; m += 2) {
      var x = pad + (m / world) * (w - 2 * pad);
      ctx.fillRect(x, gy - 6, 1, 6);
      ctx.fillText(m + "m", x, gy + 22);
    }
    ctx.textAlign = "left";
  }
  function cart(ctx, x, y, color, emoji) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.roundRect ? ctx.roundRect(x - 22, y - 26, 44, 22, 5) : ctx.rect(x - 22, y - 26, 44, 22);
    ctx.fill();
    ctx.fillStyle = "#0f172a";
    ctx.beginPath(); ctx.arc(x - 12, y, 7, 0, 7); ctx.arc(x + 12, y, 7, 0, 7); ctx.fill();
    ctx.fillStyle = "#64748b";
    ctx.beginPath(); ctx.arc(x - 12, y, 3, 0, 7); ctx.arc(x + 12, y, 3, 0, 7); ctx.fill();
    if (emoji) { ctx.font = "18px sans-serif"; ctx.fillText(emoji, x - 9, y - 8); }
  }

  // ================= NEWTON'S FIRST LAW =================
  var L1 = { on: false, running: false, b: null, F: 8, mu: 0.1, world: 16, loop: null, g: null, gi: [0, 0] };
  function l1fit() {
    var f = PHYS.fitCanvas($("c1"), 230);
    L1.ctx = f.ctx; L1.w = f.w; L1.h = f.h;
    if (!L1.g) { L1.g = new PHYS.Graph(300); L1.gi[0] = L1.g.addSeries("#38bdf8"); }
    l1draw();
  }
  function l1reset() {
    L1.b = PHYS.body1D(2, 2, 0);
    L1.g.clear();
    l1read(0, 0, 0);
    $("banner1").textContent = "Press ▶ Start, then Apply Force!";
    $("banner1").className = "banner";
    l1draw();
  }
  function l1read(a, Ff, Fnet) {
    $("r1F").textContent = (L1.on ? L1.F : 0).toFixed(1) + " N";
    $("r1Ff").textContent = Ff.toFixed(1) + " N";
    $("r1V").textContent = L1.b.v.toFixed(2) + " m/s";
    $("r1A").textContent = a.toFixed(2) + " m/s²";
    $("r1Net").textContent = Fnet.toFixed(1) + " N";
  }
  function l1step(dt) {
    if (!L1.running) return;
    var Fa = L1.on ? L1.F : 0;
    var r = PHYS.step1D(L1.b, Fa, L1.mu, dt);
    L1.g.push(L1.gi[0], L1.b.v);
    if (L1.b.x >= L1.world - 0.6) { L1.b.x = L1.world - 0.6; L1.b.v = 0; L1.running = false; $("f1Start").textContent = "▶ Start"; APP.toast("🏁 Hit the end of the track!"); }
    l1read(r.a, r.Ff, r.Fnet);
    var bn = $("banner1");
    if (Math.abs(r.Fnet) < 0.05 && Math.abs(L1.b.v) > 0.2) {
      bn.textContent = "✨ NET FORCE = 0 → constant velocity (1st Law!)";
      bn.className = "banner good";
    } else if (Math.abs(L1.b.v) < 0.02 && !L1.on) {
      bn.textContent = "🛑 At rest, stays at rest — no net force.";
      bn.className = "banner";
    } else if (Math.abs(L1.b.v) < 0.02 && L1.on && Math.abs(r.Fnet) < 0.05) {
      bn.textContent = "🧱 Static friction balances your push — still at rest!";
      bn.className = "banner warn";
    } else {
      bn.textContent = L1.on ? "🟢 Unbalanced force → accelerating!" : "🔴 Only friction acts → slowing down!";
      bn.className = "banner " + (L1.on ? "good" : "warn");
    }
  }
  function l1draw() {
    var ctx = L1.ctx; if (!ctx) return;
    var w = L1.w, h = L1.h, gy = h - 46, pad = 26;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0b1220"; ctx.fillRect(0, 0, w, h);
    markers(ctx, w, gy, L1.world, pad);
    ground(ctx, w, h, gy);
    function X(xm) { return pad + (xm / L1.world) * (w - 2 * pad); }
    var cx = X(L1.b.x);
    cart(ctx, cx, gy - 4, "#f59e0b", "📦");
    // force arrows (scale with newtons)
    if (L1.on && L1.F > 0.1) PHYS.drawArrow(ctx, cx + 26, gy - 30, cx + 26 + L1.F * 4.5, gy - 30, "#22c55e", 4, "F=" + L1.F.toFixed(0) + "N");
    var Ff = -Math.sign(L1.b.v || (L1.on ? 1 : 0)) * L1.mu * L1.b.m * PHYS.G;
    if (Math.abs(L1.b.v) > 0.05 && L1.mu > 0.005) PHYS.drawArrow(ctx, cx - 26, gy - 14, cx - 26 - Math.abs(Ff) * 4.5, gy - 14, "#ef4444", 3, "friction");
    if (Math.abs(L1.b.v) > 0.15) PHYS.drawArrow(ctx, cx, gy - 52, cx + L1.b.v * 14, gy - 52, "#38bdf8", 3, "v");
    if (L1.g) L1.g.draw(ctx, 150, 52, { label: "v–t" });
    ctx.fillStyle = "#e2e8f0"; ctx.font = "bold 12px sans-serif";
    ctx.fillText("μ=" + L1.mu.toFixed(2) + (L1.on ? "  •  PUSHING" : "  •  NO PUSH"), 8, 16);
  }

  // Law-1 real-life scenario mini-games (scripted demos of true motion + MCQ)
  var L1Q = [
    { t: "🚌 Bus brakes — why do you lurch forward?", q: "The bus stops suddenly. Why does the passenger keep moving forward?",
      opts: ["The seat pushes them forward", "Their body keeps its motion (inertia) — no force stopped it", "Gravity pulls them forward"],
      a: 1, ex: "The passenger's body tends to keep moving at the old speed. That's inertia of motion — seatbelts provide the stopping force!" },
    { t: "🧹 Beating a carpet — why does dust fly out?", q: "The carpet is beaten with a stick. Why does the dust come out?",
      opts: ["Dust is scared of sticks", "The carpet moves suddenly but dust stays at rest and gets left behind", "The stick attracts dust"],
      a: 1, ex: "Dust tends to remain at rest (inertia of rest) while the carpet jerks away — so dust separates and falls out!" },
    { t: "🔒 Why do we wear seatbelts?", q: "In a sudden stop, what does the seatbelt do?",
      opts: ["It makes the car stop faster", "It gives your body the force needed to stop with the car", "It keeps the engine running"],
      a: 1, ex: "Without it, your body would keep moving forward at full speed. The belt supplies the external stopping force. Buckle up!" }
  ];
  var l1Score = { done: [false, false, false] };
  function l1ScenarioAnim(cv, idx, t) {
    var f = PHYS.fitCanvas(cv, 150);
    var ctx = f.ctx, w = f.w, h = f.h;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0b1220"; ctx.fillRect(0, 0, w, h);
    if (idx === 0) { // bus
      var bx = t < 2 ? 20 + 60 * t : 20 + 120 - 60 * (t - 2) * (t - 2) / 2 + 60 * (t - 2);
      if (t >= 3) bx = 20 + 120 + 30;
      var px = 60 + 60 * t; // passenger keeps constant v
      var front = bx + 120;
      if (px > front - 18) px = front - 18;
      ctx.fillStyle = "#f59e0b"; ctx.fillRect(bx, h - 80, 120, 50);
      ctx.fillStyle = "#0f172a";
      ctx.beginPath(); ctx.arc(bx + 25, h - 26, 10, 0, 7); ctx.arc(bx + 95, h - 26, 10, 0, 7); ctx.fill();
      ctx.font = "24px sans-serif"; ctx.fillText("🧍", px, h - 52);
      ctx.fillStyle = "#e2e8f0"; ctx.font = "bold 12px sans-serif";
      ctx.fillText(t < 2 ? "🚌 cruising…" : t < 3 ? "🛑 BRAKES! (bus slows, you don't!)" : "💥 You lurch to the front!", 8, 16);
      PHYS.drawArrow(ctx, px + 8, h - 66, px + 8 + 40, h - 66, "#38bdf8", 3, "you");
    } else if (idx === 1) { // carpet
      ctx.strokeStyle = "#a16207"; ctx.lineWidth = 8;
      var jig = t > 0.5 && t < 1.1 ? Math.sin(t * 40) * 3 : 0;
      ctx.beginPath(); ctx.moveTo(30, 20); ctx.lineTo(30, h - 20 + jig); ctx.lineTo(150, h - 20 + jig); ctx.stroke();
      var sa = t < 0.5 ? -0.9 : t < 0.8 ? -0.9 + (t - 0.5) * 6 : 0.9 - Math.max(0, t - 1.4) * 2;
      ctx.save(); ctx.translate(150, h - 20); ctx.rotate(sa);
      ctx.strokeStyle = "#92400e"; ctx.lineWidth = 6;
      ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(70, 0); ctx.stroke(); ctx.restore();
      ctx.fillStyle = "#fde68a";
      for (var i = 0; i < 14; i++) {
        var age = t - 0.8 - (i % 5) * 0.05;
        if (age > 0) {
          var dx = 150 + (i * 13 % 40) + age * 60, dy = h - 40 + age * 90;
          if (dy < h - 4) { ctx.beginPath(); ctx.arc(dx, dy, 2.5, 0, 7); ctx.fill(); }
        }
      }
      ctx.fillStyle = "#e2e8f0"; ctx.font = "bold 12px sans-serif";
      ctx.fillText(t < 0.5 ? "🥁 Carpet hanging… WHACK incoming!" : "✨ Carpet jerks away — dust stays behind!", 8, 16);
    } else { // seatbelt
      var cxp = t < 1.5 ? 20 + 80 * t : 20 + 120 + 80 * 1.5 - 3 * (t - 1.5) * (t - 1.5) * 10;
      if (t >= 2.6) cxp = 20 + 120 + 80 * 1.5 - 3 * 1.21 * 10;
      var dp = 40 + 80 * t; // dummy keeps speed
      var dash = cxp + 110;
      if (dp > dash - 26) dp = dash - 26; // belt stops dummy
      ctx.fillStyle = "#38bdf8"; ctx.fillRect(cxp, h - 70, 110, 34);
      ctx.font = "22px sans-serif"; ctx.fillText("🧍", dp, h - 44);
      ctx.strokeStyle = "#22c55e"; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.moveTo(dp + 4, h - 60); ctx.lineTo(dp + 20, h - 40); ctx.stroke();
      ctx.fillStyle = "#e2e8f0"; ctx.font = "bold 12px sans-serif";
      ctx.fillText(t < 1.5 ? "🚗 driving…" : "🛑 CRASH STOP! Belt holds you!", 8, 16);
    }
  }
  function playScenario(cv, idx) {
    var t0 = null, DUR = 3.4;
    function fr(t) {
      if (!t0) t0 = t;
      var e = (t - t0) / 1000;
      l1ScenarioAnim(cv, idx, Math.min(e, DUR));
      if (e < DUR) requestAnimationFrame(fr);
    }
    requestAnimationFrame(fr);
  }
  function buildL1Scenarios() {
    var wrap = $("law1Scenarios");
    wrap.innerHTML = "";
    L1Q.forEach(function (s, i) {
      var card = document.createElement("div");
      card.className = "card sub";
      card.innerHTML = "<h3>" + s.t + "</h3>" +
        '<canvas class="sim" id="l1sc' + i + '"></canvas>' +
        '<div class="row"><button class="ghost-btn" id="l1play' + i + '">▶ Play scene</button></div>' +
        "<p><b>" + s.q + "</b></p><div class='opts' id='l1opts" + i + "'></div>" +
        "<p class='feedback hidden' id='l1fb" + i + "'></p>";
      wrap.appendChild(card);
      var cv = $("l1sc" + i);
      reg(cv, function () { l1ScenarioAnim(cv, i, 3.4); });
      l1ScenarioAnim(cv, i, 3.4);
      $("l1play" + i).addEventListener("click", function () { APP.SFX.click(); playScenario(cv, i); });
      var box = $("l1opts" + i);
      s.opts.forEach(function (op, oi) {
        var b = document.createElement("button");
        b.className = "answer sm";
        b.textContent = op;
        b.addEventListener("click", function () {
          if (l1Score.done[i]) return;
          var ok = oi === s.a;
          var fb = $("l1fb" + i);
          fb.classList.remove("hidden");
          fb.className = "feedback " + (ok ? "good" : "bad");
          fb.textContent = (ok ? "✅ Correct! " : "❌ Not quite. ") + s.ex;
          var btns = box.children;
          for (var k = 0; k < btns.length; k++) btns[k].disabled = true;
          btns[s.a].classList.add("correct");
          if (!ok) btns[oi].classList.add("wrong");
          var r = APP.verdict(ok, 25);
          if (ok) { l1Score.done[i] = true; APP.confetti(20); }
        });
        box.appendChild(b);
      });
    });
  }

  // ================= NEWTON'S SECOND LAW =================
  var L2 = { b: null, F: 20, m: 5, world: 12, running: false, t: 0, loop: null, gv: null, gx: null, gi: [] };
  function l2fit() {
    var f = PHYS.fitCanvas($("c2"), 230);
    L2.ctx = f.ctx; L2.w = f.w; L2.h = f.h;
    if (!L2.gv) {
      L2.gv = new PHYS.Graph(300); L2.gi[0] = L2.gv.addSeries("#38bdf8");
      L2.gx = new PHYS.Graph(300); L2.gi[1] = L2.gx.addSeries("#22c55e");
    }
    l2draw(); l2eq();
  }
  function l2reset() {
    L2.b = PHYS.body1D(L2.m, 0.5, 0);
    L2.t = 0; L2.gv.clear(); L2.gx.clear();
    $("c2Verdict").textContent = "";
    l2draw(); l2eq(); l2read();
  }
  function l2eq() {
    var a = L2.F / L2.m;
    $("f2Eq").textContent = "F = m × a  →  " + L2.F.toFixed(0) + " = " + L2.m.toFixed(0) + " × " + a.toFixed(2) +
      "      a = F/m = " + L2.F.toFixed(0) + "/" + L2.m.toFixed(0) + " = " + a.toFixed(2) + " m/s²";
  }
  function l2read() {
    $("r2F").textContent = L2.F.toFixed(0) + " N";
    $("r2M").textContent = L2.m.toFixed(0) + " kg";
    $("r2A").textContent = (L2.F / L2.m).toFixed(2) + " m/s²";
    $("r2V").textContent = L2.b.v.toFixed(2) + " m/s";
    $("r2X").textContent = L2.b.x.toFixed(2) + " m";
  }
  function l2step(dt) {
    if (!L2.running) return;
    var r = PHYS.step1D(L2.b, L2.F, 0, dt); // frictionless: pure F=ma
    L2.t += dt;
    L2.gv.push(L2.gi[0], L2.b.v);
    L2.gx.push(L2.gi[1], L2.b.x);
    l2read();
    if (L2.b.x >= L2.world - 0.5 || L2.t > 8) {
      L2.running = false; $("f2Start").textContent = "▶ Start";
      L2.measured = L2.t > 0.2 ? L2.b.v / L2.t : 0; // v=at from rest → measured a
      l2checkChallenge();
    }
  }
  function l2draw() {
    var ctx = L2.ctx; if (!ctx) return;
    var w = L2.w, h = L2.h, gy = h - 46, pad = 26;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0b1220"; ctx.fillRect(0, 0, w, h);
    markers(ctx, w, gy, L2.world, pad);
    ground(ctx, w, h, gy);
    var X = function (xm) { return pad + (xm / L2.world) * (w - 2 * pad); };
    var cx = X(Math.min(L2.b.x, L2.world - 0.5));
    var size = 30 + L2.m * 3; // heavier looks bigger
    ctx.fillStyle = "#8b5cf6";
    ctx.fillRect(cx - size / 2, gy - 8 - size * 0.6, size, size * 0.6);
    ctx.fillStyle = "#0f172a";
    ctx.beginPath(); ctx.arc(cx - size / 4, gy - 6, 7, 0, 7); ctx.arc(cx + size / 4, gy - 6, 7, 0, 7); ctx.fill();
    ctx.font = "14px sans-serif"; ctx.fillText("⚖️" + L2.m.toFixed(0) + "kg", cx - 24, gy - 14 - size * 0.6);
    PHYS.drawArrow(ctx, cx - size / 2 - 4, gy - 30, cx - size / 2 - 4 - L2.F * 2.2, gy - 30, "#22c55e", 5, L2.F.toFixed(0) + "N");
    if (L2.b.v > 0.2) PHYS.drawArrow(ctx, cx, gy - 58, cx + Math.min(90, L2.b.v * 12), gy - 58, "#38bdf8", 3, "v");
    L2.gv.draw(ctx, 150, 48, { label: "v–t (slope = a)" });
    L2.gx.draw(ctx, 150, 48, { label: "x–t" });
    // F-vs-a theory plot (bottom-right)
    var pw = 150, ph = 48, px = w - pw - 6, py = h - ph - 52;
    ctx.fillStyle = "#0f172a"; ctx.fillRect(px, py, pw, ph);
    ctx.strokeStyle = "#22c55e"; ctx.lineWidth = 2; ctx.beginPath();
    var amax = 60 / 1;
    for (var F = 0; F <= 60; F += 4) {
      var Xp = px + 4 + (F / 60) * (pw - 8);
      var Yp = py + ph - 4 - ((F / L2.m) / amax) * (ph - 8);
      if (F === 0) ctx.moveTo(Xp, Yp); else ctx.lineTo(Xp, Yp);
    }
    ctx.stroke();
    ctx.fillStyle = "#fbbf24";
    ctx.beginPath();
    ctx.arc(px + 4 + (L2.F / 60) * (pw - 8), py + ph - 4 - ((L2.F / L2.m) / amax) * (ph - 8), 4, 0, 7);
    ctx.fill();
    ctx.fillStyle = "#e2e8f0"; ctx.font = "bold 10px sans-serif";
    ctx.fillText("F–a line (m=" + L2.m.toFixed(0) + ")", px + 4, py + 11);
  }
  var L2T = { target: 3, active: false };
  function l2newTarget() {
    L2T.target = Math.round((2 + Math.random() * 4) * 100) / 100;
    L2T.active = true;
    $("c2Target").textContent = "🎯 Target acceleration: a = " + L2T.target.toFixed(2) + " m/s² — set mass & force, then Test!";
    $("c2Verdict").textContent = "";
  }
  function l2checkChallenge() {
    if (!L2T.active || L2.measured === undefined) return;
    var err = Math.abs(L2.measured - L2T.target);
    var v = $("c2Verdict");
    if (err <= 0.3) {
      v.className = "feedback good";
      v.textContent = "✅ Measured a = " + L2.measured.toFixed(2) + " m/s² — target hit! (F=ma: " + L2.F.toFixed(0) + "/" + L2.m.toFixed(0) + "=" + (L2.F / L2.m).toFixed(2) + ")";
      L2T.active = false;
      APP.reward(50, "force-master");
      APP.confetti(40);
    } else {
      v.className = "feedback bad";
      v.textContent = "❌ Measured a = " + L2.measured.toFixed(2) + " m/s², need " + L2T.target.toFixed(2) + ". Hint: a = F/m — adjust and Test again!";
      APP.verdict(false, 0);
    }
  }

  // ================= NEWTON'S THIRD LAW =================
  var L3 = { mode: "carts", mA: 2, mB: 2, A: null, B: null, phase: "idle", t: 0, thrust: 40, air: 70, r: null, bal: null, parts: [] };
  function l3fit() {
    ["c3", "c3r", "c3b"].forEach(function (id) {
      var cv = $(id);
      var f = PHYS.fitCanvas(cv, 230);
      L3[id] = { ctx: f.ctx, w: f.w, h: f.h };
    });
    l3draw();
  }
  function l3reset() {
    L3.A = PHYS.body1D(L3.mA, 7.4, 0);
    L3.B = PHYS.body1D(L3.mB, 8.6, 0);
    L3.phase = "idle"; L3.t = 0;
    L3.r = PHYS.body1D(5, 1, 0);
    L3.bal = { x: 2, y: 0, v: 0, air: 0, on: false };
    L3.parts = [];
    l3draw(); l3read();
  }
  function l3read() {
    if (L3.mode !== "carts") return;
    $("r3vA").textContent = L3.A.v.toFixed(2) + " m/s";
    $("r3vB").textContent = L3.B.v.toFixed(2) + " m/s";
    $("r3p").textContent = (L3.A.m * L3.A.v + L3.B.m * L3.B.v).toFixed(2) + " kg·m/s";
  }
  function l3push() {
    if (L3.phase !== "idle") return;
    L3.A.m = L3.mA; L3.B.m = L3.mB;
    L3.A.x = 7.4; L3.A.v = 0; L3.B.x = 8.6; L3.B.v = 0;
    L3.phase = "contact"; L3.t = 0;
    APP.SFX.pop();
  }
  function l3step(dt) {
    if (L3.mode === "carts") {
      if (L3.phase === "contact") {
        L3.t += dt;
        // equal & opposite spring-ish force while touching (F on A = -F on B)
        var F = 60;
        PHYS.step1D(L3.A, -F, 0, dt);
        PHYS.step1D(L3.B, F, 0, dt);
        L3.A.x = Math.min(L3.A.x, 7.9); L3.B.x = Math.max(L3.B.x, 8.1);
        if (L3.t >= 0.35) {
          // normalize to exact momentum-conserving impulse J for clean numbers
          var J = 12;
          L3.A.v = -J / L3.A.m; L3.B.v = J / L3.B.m;
          L3.phase = "coast";
        }
      } else if (L3.phase === "coast") {
        PHYS.step1D(L3.A, 0, 0.05, dt);
        PHYS.step1D(L3.B, 0, 0.05, dt);
        if (Math.abs(L3.A.v) < 0.03 && Math.abs(L3.B.v) < 0.03) L3.phase = "done";
      }
      // walls
      if (L3.A.x < 0.5) { L3.A.x = 0.5; L3.A.v = 0; }
      if (L3.B.x > 15.5) { L3.B.x = 15.5; L3.B.v = 0; }
      l3read();
    } else if (L3.mode === "rocket") {
      if (L3.rGo) {
        var a = L3.thrust / L3.r.m; // in space, no gravity: pure F=ma
        L3.r.v += a * dt; L3.r.x += L3.r.v * dt;
        if (!RM && Math.random() < 0.8) {
          L3.parts.push({ x: L3.r.x, y: 0.5 + Math.random(), vx: L3.r.v - 6 - Math.random() * 3, vy: (Math.random() - 0.5) * 2, life: 0.7 });
        }
        if (L3.r.x > 19) { L3.r.x = 19; L3.r.v = 0; L3.rGo = false; }
        try {
          $("r3r").textContent = "a = " + a.toFixed(2) + " m/s² • v = " + L3.r.v.toFixed(2) + " m/s • x = " + L3.r.x.toFixed(1) + " m";
        } catch (e) {}
      }
      for (var i = L3.parts.length - 1; i >= 0; i--) {
        var pt = L3.parts[i];
        pt.x += pt.vx * dt; pt.y += pt.vy * dt; pt.life -= dt;
        if (pt.life <= 0) L3.parts.splice(i, 1);
      }
    } else if (L3.mode === "balloon") {
      var b = L3.bal;
      if (b.on && b.air > 0) {
        var Fb = b.air * 0.09; // thrust ∝ remaining air
        var ab = Fb / 0.3 - 1.5 * b.v; // light balloon + drag
        b.v += ab * dt; b.x += b.v * dt; b.air -= dt * 28;
        if (!RM && Math.random() < 0.7) L3.parts.push({ x: b.x - 0.4, y: Math.random(), vx: b.v - 5, vy: (Math.random() - 0.5) * 3, life: 0.6 });
        if (b.x > 19 || b.air <= 0) { b.on = false; }
        try { $("r3b").textContent = "Air left: " + Math.max(0, b.air).toFixed(0) + "% • v = " + b.v.toFixed(2) + " m/s • x = " + b.x.toFixed(1) + " m"; } catch (e) {}
      }
      for (var j = L3.parts.length - 1; j >= 0; j--) {
        var q2 = L3.parts[j];
        q2.x += q2.vx * dt; q2.y += q2.vy * dt; q2.life -= dt;
        if (q2.life <= 0) L3.parts.splice(j, 1);
      }
    }
  }
  function l3draw() {
    var S = L3[L3.mode === "carts" ? "c3" : L3.mode === "rocket" ? "c3r" : "c3b"];
    if (!S || !S.ctx) return;
    var ctx = S.ctx, w = S.w, h = S.h, gy = h - 40, pad = 24;
    ctx.clearRect(0, 0, w, h);
    if (L3.mode === "rocket") {
      ctx.fillStyle = "#020617"; ctx.fillRect(0, 0, w, h);
      ctx.fillStyle = "#fff";
      for (var s = 0; s < 40; s++) ctx.fillRect((s * 53) % w, (s * 37) % h, 2, 2);
      var X = function (xm) { return pad + (xm / 20) * (w - 2 * pad); };
      var rx = X(L3.r.x);
      ctx.font = "34px sans-serif"; ctx.fillText("🚀", rx - 17, h / 2 + 12);
      PHYS.drawArrow(ctx, rx + 24, h / 2, rx + 24 + L3.thrust * 0.9, h / 2, "#22c55e", 4, "thrust");
      ctx.fillStyle = "#fdba74";
      for (var i = 0; i < L3.parts.length; i++) {
        var p = L3.parts[i];
        ctx.globalAlpha = Math.max(0, p.life);
        ctx.beginPath(); ctx.arc(X(p.x), h / 2 + p.y * 20, 4, 0, 7); ctx.fill();
      }
      ctx.globalAlpha = 1;
      ctx.fillStyle = "#e2e8f0"; ctx.font = "bold 12px sans-serif";
      ctx.fillText("Gas pushes DOWN-BACK ⬅ • Rocket pushes FORWARD ➡ (equal & opposite!)", 8, 16);
      return;
    }
    if (L3.mode === "balloon") {
      ctx.fillStyle = "#0b1220"; ctx.fillRect(0, 0, w, h);
      markers(ctx, w, gy, 20, pad);
      ground(ctx, w, h, gy);
      var Xb = function (xm) { return pad + (xm / 20) * (w - 2 * pad); };
      var bx = Xb(L3.bal.x), wob = L3.bal.on ? Math.sin(Date.now() / 90) * 5 : 0;
      ctx.fillStyle = "#38bdf8";
      for (var j = 0; j < L3.parts.length; j++) {
        var q3 = L3.parts[j];
        ctx.globalAlpha = Math.max(0, q3.life);
        ctx.font = "12px sans-serif"; ctx.fillText("💨", Xb(q3.x), h / 2 + q3.y * 24);
      }
      ctx.globalAlpha = 1;
      ctx.font = "34px sans-serif"; ctx.fillText("🎈", bx - 17, h / 2 + wob);
      PHYS.drawArrow(ctx, bx - 24, h / 2, bx - 60, h / 2, "#f472b6", 3, "air out");
      PHYS.drawArrow(ctx, bx + 24, h / 2, bx + 60, h / 2, "#22c55e", 3, "balloon");
      ctx.fillStyle = "#e2e8f0"; ctx.font = "bold 12px sans-serif";
      ctx.fillText("Air rushes BACK ⬅ • Balloon zooms FORWARD ➡", 8, 16);
      return;
    }
    // carts
    ctx.fillStyle = "#0b1220"; ctx.fillRect(0, 0, w, h);
    markers(ctx, w, gy, 16, pad);
    ground(ctx, w, h, gy);
    var Xc = function (xm) { return pad + (xm / 16) * (w - 2 * pad); };
    cart(ctx, Xc(L3.A.x), gy - 4, "#f472b6", "🧍");
    cart(ctx, Xc(L3.B.x), gy - 4, "#38bdf8", "🧍");
    ctx.fillStyle = "#e2e8f0"; ctx.font = "bold 12px sans-serif";
    ctx.fillText("A mass=" + L3.A.m.toFixed(0) + "kg", Xc(L3.A.x) - 34, gy - 66);
    ctx.fillText("B mass=" + L3.B.m.toFixed(0) + "kg", Xc(L3.B.x) - 34, gy - 66);
    if (L3.phase === "contact") {
      PHYS.drawArrow(ctx, Xc(8) - 6, gy - 34, Xc(8) - 60, gy - 34, "#ef4444", 5, "action");
      PHYS.drawArrow(ctx, Xc(8) + 6, gy - 34, Xc(8) + 60, gy - 34, "#22c55e", 5, "reaction");
    } else {
      if (Math.abs(L3.A.v) > 0.15) PHYS.drawArrow(ctx, Xc(L3.A.x), gy - 50, Xc(L3.A.x) + L3.A.v * 16, gy - 50, "#38bdf8", 3, "vA");
      if (Math.abs(L3.B.v) > 0.15) PHYS.drawArrow(ctx, Xc(L3.B.x), gy - 50, Xc(L3.B.x) + L3.B.v * 16, gy - 50, "#38bdf8", 3, "vB");
    }
    if (L3.phase === "done" || L3.phase === "coast") {
      ctx.fillStyle = "#bbf7d0"; ctx.font = "bold 12px sans-serif";
      ctx.fillText("Equal & opposite push! Heavy cart moves slower (a=F/m). Total momentum ≈ 0 ⚖️", 8, 16);
    } else {
      ctx.fillStyle = "#e2e8f0"; ctx.font = "bold 12px sans-serif";
      ctx.fillText("Press PUSH! — the carts shove each other apart.", 8, 16);
    }
  }
  function l3mode(m) {
    L3.mode = m;
    var btns = document.querySelectorAll("[data-l3mode]");
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle("selected", btns[i].getAttribute("data-l3mode") === m);
    $("l3pCarts").classList.toggle("hidden", m !== "carts");
    $("l3pRocket").classList.toggle("hidden", m !== "rocket");
    $("l3pBalloon").classList.toggle("hidden", m !== "balloon");
    l3draw();
  }

  // ================= INERTIA LAB =================
  var IN = { tab: "rest", runs: {} };
  function inTab(t) {
    IN.tab = t;
    var btns = document.querySelectorAll("[data-intab]");
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle("selected", btns[i].getAttribute("data-intab") === t);
    ["rest", "motion", "direction"].forEach(function (k) {
      $("intab-" + k).classList.toggle("hidden", k !== t);
    });
  }
  // --- rest: coin on card over glass. Card flicked (fast v), coin keeps vx≈0, falls with g.
  var IR = { t: 0, on: false };
  function irDraw(t) {
    var f = PHYS.fitCanvas($("ciRest"), 220);
    var ctx = f.ctx, w = f.w, h = f.h;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0b1220"; ctx.fillRect(0, 0, w, h);
    var gx = w / 2, gy = h - 40;
    ctx.strokeStyle = "#93c5fd"; ctx.lineWidth = 4;
    ctx.strokeRect(gx - 34, gy - 60, 68, 60); // glass
    ctx.fillStyle = "rgba(147,197,253,.25)"; ctx.fillRect(gx - 34, gy - 60, 68, 60);
    var cardX = t < 0.25 ? gx + t * 400 : gx + 100 + (t - 0.25) * 500;
    if (t >= 0.25) cardX = gx + 100 + 500 * 0.25 + (t - 0.25) * 500;
    ctx.fillStyle = "#f59e0b"; ctx.fillRect(cardX - 60, gy - 72, 120, 12); // card
    var coinX = gx, coinY;
    var fall = Math.max(0, t - 0.25);
    coinY = gy - 78 + 0.5 * 500 * fall * fall; // coin: no horizontal force → stays, gravity pulls down
    if (coinY > gy - 14) coinY = gy - 14;
    ctx.fillStyle = "#fde047";
    ctx.beginPath(); ctx.arc(coinX, coinY, 10, 0, 7); ctx.fill();
    ctx.fillStyle = "#e2e8f0"; ctx.font = "bold 12px sans-serif";
    ctx.fillText(t < 0.25 ? "👆 Card about to be flicked…" : "🪙 Coin stayed (at rest!) and dropped straight in!", 8, 16);
  }
  function irRun() {
    IR.t = 0; IR.on = true;
    var t0 = null;
    function fr(t) {
      if (!t0) t0 = t;
      var e = (t - t0) / 1000;
      irDraw(Math.min(e, 1.6));
      if (e < 1.6) requestAnimationFrame(fr); else IR.on = false;
    }
    requestAnimationFrame(fr);
  }
  // --- motion: bus cruises then brakes; passenger keeps v until rail.
  var IMo = { on: false };
  function imDraw(t) {
    var f = PHYS.fitCanvas($("ciMotion"), 220);
    var ctx = f.ctx, w = f.w, h = f.h, gy = h - 30;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0b1220"; ctx.fillRect(0, 0, w, h);
    ground(ctx, w, h, gy);
    var v0 = 130; // px/s cruise
    var bx = t < 1.6 ? 20 + v0 * t : 20 + v0 * 1.6 + v0 * (t - 1.6) - 0.5 * 160 * (t - 1.6) * (t - 1.6);
    var tStop = 1.6 + v0 / 160;
    if (t >= tStop) bx = 20 + v0 * 1.6 + v0 * (v0 / 160) - 0.5 * 160 * (v0 / 160) * (v0 / 160);
    var px = 70 + v0 * t;
    if (px > bx + 128) px = bx + 128; // front rail stops passenger
    ctx.fillStyle = "#f59e0b"; ctx.fillRect(bx, gy - 70, 150, 52);
    ctx.fillStyle = "#0f172a";
    ctx.beginPath(); ctx.arc(bx + 30, gy - 12, 11, 0, 7); ctx.arc(bx + 120, gy - 12, 11, 0, 7); ctx.fill();
    ctx.font = "26px sans-serif"; ctx.fillText("🧍", px, gy - 44);
    ctx.fillStyle = "#e2e8f0"; ctx.font = "bold 12px sans-serif";
    ctx.fillText(t < 1.6 ? "🚌 cruising at constant speed…" : t < tStop ? "🛑 BRAKING! Bus slows — passenger keeps speed!" : "💥 Passenger lurches to the front rail!", 8, 16);
    PHYS.drawArrow(ctx, px + 10, gy - 84, px + 10 + 44, gy - 84, "#38bdf8", 3, "you");
  }
  function imRun() {
    var t0 = null;
    function fr(t) {
      if (!t0) t0 = t;
      var e = (t - t0) / 1000;
      imDraw(Math.min(e, 3.2));
      if (e < 3.2) requestAnimationFrame(fr);
    }
    requestAnimationFrame(fr);
  }
  // --- direction: top-down car turns right; passenger goes straight until door.
  var IDr = { on: false };
  function idDraw(t) {
    var f = PHYS.fitCanvas($("ciDir"), 220);
    var ctx = f.ctx, w = f.w, h = f.h;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0b1220"; ctx.fillRect(0, 0, w, h);
    var cx = w / 2, cy0 = h - 30, v = 90;
    var turnT = 1.2, turnR = 0.9; // turn rate rad/s after turnT
    var car = { x: cx, y: cy0 - v * Math.min(t, turnT), a: 0 };
    if (t > turnT) {
      var dt2 = Math.min(t - turnT, 1.4);
      car.a = turnR * dt2;
      car.x = cx + (v / turnR) * (1 - Math.cos(car.a)) * 0 + (v * Math.sin(car.a)) * 0 + (v * dt2 * Math.sin(car.a / 2)) * 1;
      car.x = cx + v * dt2 * Math.sin(car.a) * 0.9;
      car.y = cy0 - v * turnT - v * dt2 * Math.cos(car.a) * 0.9;
    }
    // passenger: constant velocity vector (straight up) until door radius
    var px = cx, py = cy0 - 24 - v * t;
    var dx = px - car.x, dy = py - car.y;
    var dist = Math.hypot(dx, dy);
    if (dist > 16) { px = car.x + dx / dist * 16; py = car.y + dy / dist * 16; }
    ctx.strokeStyle = "#334155"; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.moveTo(cx - 40, 6); ctx.lineTo(cx - 40, h - 6); ctx.moveTo(cx + 90, 6); ctx.lineTo(cx + 90, h - 6); ctx.stroke();
    ctx.save(); ctx.translate(car.x, car.y); ctx.rotate(car.a);
    ctx.fillStyle = "#38bdf8"; ctx.fillRect(-16, -26, 32, 52);
    ctx.fillStyle = "#0f172a"; ctx.fillRect(-20, -18, 6, 10); ctx.fillRect(14, -18, 6, 10); ctx.fillRect(-20, 8, 6, 10); ctx.fillRect(14, 8, 6, 10);
    ctx.restore();
    ctx.font = "16px sans-serif"; ctx.fillText("🧍", px - 8, py + 6);
    ctx.fillStyle = "#e2e8f0"; ctx.font = "bold 12px sans-serif";
    ctx.fillText(t < turnT ? "🚗 driving straight…" : "↩️ Car turns — you keep going STRAIGHT!", 8, 16);
  }
  function idRun() {
    var t0 = null;
    function fr(t) {
      if (!t0) t0 = t;
      var e = (t - t0) / 1000;
      idDraw(Math.min(e, 3.0));
      if (e < 3.0) requestAnimationFrame(fr);
    }
    requestAnimationFrame(fr);
  }
  var INQ = {
    rest: { q: "Why did the coin drop straight into the glass?", opts: ["The card pushed it down", "The coin stayed at rest while the card shot away (inertia of rest)", "Magnets in the glass"], a: 1 },
    motion: { q: "Why did the passenger lurch forward when the bus stopped?", opts: ["The engine pushed them", "Their body kept moving (inertia of motion) — nothing stopped it", "The road tilted"], a: 1 },
    direction: { q: "Why did the passenger slide sideways when the car turned?", opts: ["A force pushed them outward", "They kept moving in the original direction (inertia of direction)", "The wheels pulled them"], a: 1 }
  };
  var inDone = {};
  function buildInertia() {
    ["rest", "motion", "direction"].forEach(function (kind) {
      var box = $("ciQuiz" + kind[0].toUpperCase() + kind.slice(1));
      var d = INQ[kind];
      var title = document.createElement("p");
      title.innerHTML = "<b>❓ " + d.q + "</b>";
      box.appendChild(title);
      var opts = document.createElement("div");
      opts.className = "opts";
      d.opts.forEach(function (op, oi) {
        var b = document.createElement("button");
        b.className = "answer sm";
        b.textContent = op;
        b.addEventListener("click", function () {
          if (inDone[kind]) return;
          var ok = oi === d.a;
          var fb = $("ciFb" + kind[0].toUpperCase() + kind.slice(1));
          fb.classList.remove("hidden");
          var names = { rest: "inertia of REST 🪙", motion: "inertia of MOTION 🚌", direction: "inertia of DIRECTION ↩️" };
          fb.className = "feedback " + (ok ? "good" : "bad");
          fb.textContent = ok ? "✅ Correct! That's " + names[kind] + " — objects resist changes to their state!" : "❌ Not quite — run the experiment again and watch carefully! 👀";
          var btns = opts.children;
          for (var k = 0; k < btns.length; k++) btns[k].disabled = true;
          btns[d.a].classList.add("correct");
          if (!ok) btns[oi].classList.add("wrong");
          APP.verdict(ok, 25);
          if (ok) {
            inDone[kind] = true;
            var n = STORE.inertiaOK(kind);
            if (n >= 3) { APP.reward(60, "inertia-explorer"); APP.toast("🧭 Inertia Explorer badge earned!", true); }
            else APP.confetti(20);
          }
        });
        opts.appendChild(b);
      });
      box.appendChild(opts);
      var fb = document.createElement("p");
      fb.className = "feedback hidden";
      fb.id = "ciFb" + kind[0].toUpperCase() + kind.slice(1);
      box.appendChild(fb);
    });
  }

  // ================= FREE LAB =================
  var LAB = { b: null, F: 10, m: 3, mu: 0.15, v0: 0, on: true, running: false, world: 20, gv: null, gx: null, gi: [] };
  function labFit() {
    var f = PHYS.fitCanvas($("labC"), 240);
    LAB.ctx = f.ctx; LAB.w = f.w; LAB.h = f.h;
    if (!LAB.gv) {
      LAB.gv = new PHYS.Graph(300); LAB.gi[0] = LAB.gv.addSeries("#38bdf8");
      LAB.gx = new PHYS.Graph(300); LAB.gi[1] = LAB.gx.addSeries("#22c55e");
    }
    labDraw();
  }
  function labReset() {
    LAB.b = PHYS.body1D(LAB.m, 1, LAB.v0);
    LAB.gv.clear(); LAB.gx.clear();
    labRead(0, 0);
    labDraw();
  }
  function labRead(a, Fnet) {
    $("labRF").textContent = (LAB.on ? LAB.F : 0).toFixed(1) + " N";
    $("labRM").textContent = LAB.m.toFixed(1) + " kg";
    $("labRA").textContent = a.toFixed(2) + " m/s²";
    $("labRV").textContent = LAB.b.v.toFixed(2) + " m/s";
    $("labRX").textContent = LAB.b.x.toFixed(2) + " m";
    $("labRNet").textContent = Fnet.toFixed(1) + " N";
  }
  function labStep(dt) {
    if (!LAB.running) return;
    LAB.b.m = LAB.m;
    var r = PHYS.step1D(LAB.b, LAB.on ? LAB.F : 0, LAB.mu, dt);
    LAB.gv.push(LAB.gi[0], LAB.b.v);
    LAB.gx.push(LAB.gi[1], LAB.b.x);
    if (LAB.b.x < 0.3) { LAB.b.x = 0.3; LAB.b.v = 0; }
    if (LAB.b.x > LAB.world - 0.4) { LAB.b.x = LAB.world - 0.4; LAB.b.v = 0; }
    labRead(r.a, r.Fnet);
  }
  function labDraw() {
    var ctx = LAB.ctx; if (!ctx) return;
    var w = LAB.w, h = LAB.h, gy = h - 46, pad = 26;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0b1220"; ctx.fillRect(0, 0, w, h);
    markers(ctx, w, gy, LAB.world, pad);
    ground(ctx, w, h, gy);
    var X = function (xm) { return pad + (xm / LAB.world) * (w - 2 * pad); };
    var cx = X(LAB.b.x);
    cart(ctx, cx, gy - 4, "#22d3ee", "🔬");
    var Fa = LAB.on ? LAB.F : 0;
    if (Math.abs(Fa) > 0.1) PHYS.drawArrow(ctx, cx, gy - 30, cx + Fa * 3.2, gy - 30, "#22c55e", 4, Fa.toFixed(0) + "N");
    if (Math.abs(LAB.b.v) > 0.15) PHYS.drawArrow(ctx, cx, gy - 54, cx + LAB.b.v * 12, gy - 54, "#38bdf8", 3, "v");
    LAB.gv.draw(ctx, 150, 48, { label: "v–t" });
    LAB.gx.draw(ctx, 150, 48, { label: "x–t" });
  }

  // ---------- wiring ----------
  function bindRange(id, fn) {
    $(id).addEventListener("input", function () { fn(parseFloat($(id).value)); });
  }
  function init() {
    // Law 1
    reg($("c1"), l1fit); l1fit(); l1reset();
    L1.loop = PHYS.makeLoop(l1step, l1draw);
    bindRange("f1Force", function (v) { L1.F = v; $("f1ForceV").textContent = v.toFixed(0) + " N"; });
    bindRange("f1Mu", function (v) { L1.mu = v; $("f1MuV").textContent = "μ = " + v.toFixed(2); });
    $("f1Apply").addEventListener("click", function () { APP.SFX.click(); L1.on = true; });
    $("f1Remove").addEventListener("click", function () { APP.SFX.click(); L1.on = false; });
    $("f1Start").addEventListener("click", function () {
      APP.SFX.click(); l1fit();
      L1.running = !L1.running;
      $("f1Start").textContent = L1.running ? "⏸ Stop" : "▶ Start";
    });
    $("f1Reset").addEventListener("click", function () { APP.SFX.click(); L1.running = false; $("f1Start").textContent = "▶ Start"; l1reset(); });
    buildL1Scenarios();
    // Law 2
    reg($("c2"), l2fit); l2fit(); l2reset();
    L2.loop = PHYS.makeLoop(l2step, l2draw);
    bindRange("f2Mass", function (v) { L2.m = v; if (!L2.running) { L2.b.m = v; } l2eq(); l2read(); l2draw(); });
    bindRange("f2Force", function (v) { L2.F = v; l2eq(); l2read(); l2draw(); });
    $("f2Start").addEventListener("click", function () {
      APP.SFX.click(); l2fit(); l2reset();
      L2.running = true; $("f2Start").textContent = "⏸ Running…";
    });
    $("f2Reset").addEventListener("click", function () { APP.SFX.click(); L2.running = false; $("f2Start").textContent = "▶ Start"; l2reset(); });
    $("c2NewTarget").addEventListener("click", function () { APP.SFX.click(); l2newTarget(); });
    $("c2Test").addEventListener("click", function () {
      APP.SFX.click(); l2fit(); l2reset();
      if (!L2T.active) l2newTarget();
      L2.running = true; $("f2Start").textContent = "⏸ Running…";
      APP.toast("🧪 Testing your F and m…");
    });
    l2newTarget();
    // Law 3
    reg($("c3"), l3fit);
    var tabs = document.querySelectorAll("[data-l3mode]");
    for (var i = 0; i < tabs.length; i++) {
      (function (b) { b.addEventListener("click", function () { APP.SFX.click(); l3mode(b.getAttribute("data-l3mode")); }); })(tabs[i]);
    }
    L3.loop = PHYS.makeLoop(l3step, l3draw);
    l3fit(); l3reset(); l3mode("carts");
    bindRange("f3mA", function (v) { L3.mA = v; $("f3mAV").textContent = v.toFixed(0) + " kg"; if (L3.phase === "idle") { L3.A.m = v; } l3draw(); });
    bindRange("f3mB", function (v) { L3.mB = v; $("f3mBV").textContent = v.toFixed(0) + " kg"; if (L3.phase === "idle") { L3.B.m = v; } l3draw(); });
    $("f3Push").addEventListener("click", function () { l3push(); });
    $("f3Reset").addEventListener("click", function () { APP.SFX.click(); l3reset(); });
    bindRange("f3Thrust", function (v) { L3.thrust = v; $("f3ThrustV").textContent = v.toFixed(0) + " N"; });
    $("f3Launch").addEventListener("click", function () { APP.SFX.click(); L3.r = PHYS.body1D(5, 1, 0); L3.parts = []; L3.rGo = true; });
    $("f3ResetR").addEventListener("click", function () { APP.SFX.click(); L3.rGo = false; L3.r = PHYS.body1D(5, 1, 0); L3.parts = []; l3draw(); });
    bindRange("f3Air", function (v) { L3.air = v; $("f3AirV").textContent = v.toFixed(0) + "%"; });
    $("f3Blow").addEventListener("click", function () { APP.SFX.click(); L3.bal = { x: 2, y: 0, v: 0, air: L3.air, on: true }; L3.parts = []; });
    // Inertia
    var itabs = document.querySelectorAll("[data-intab]");
    for (var j = 0; j < itabs.length; j++) {
      (function (b) { b.addEventListener("click", function () { APP.SFX.click(); inTab(b.getAttribute("data-intab")); }); })(itabs[j]);
    }
    irDraw(1.6); imDraw(3.2); idDraw(3.0);
    reg($("ciRest"), function () { irDraw(1.6); });
    reg($("ciMotion"), function () { imDraw(3.2); });
    reg($("ciDir"), function () { idDraw(3.0); });
    $("ciRunRest").addEventListener("click", function () { APP.SFX.click(); irRun(); });
    $("ciRunMotion").addEventListener("click", function () { APP.SFX.click(); imRun(); });
    $("ciRunDir").addEventListener("click", function () { APP.SFX.click(); idRun(); });
    buildInertia(); inTab("rest");
    // Menu card "Types of Inertia" jumps straight to that tab.
    var itabGo = document.querySelectorAll("[data-itab]");
    for (var jj = 0; jj < itabGo.length; jj++) {
      (function (b) { b.addEventListener("click", function () { setTimeout(function () { inTab(b.getAttribute("data-itab")); }, 30); }); })(itabGo[jj]);
    }
    // Lab
    reg($("labC"), labFit); labFit(); labReset();
    LAB.loop = PHYS.makeLoop(labStep, labDraw);
    bindRange("labM", function (v) { LAB.m = v; $("labMV").textContent = v.toFixed(1) + " kg"; });
    bindRange("labF", function (v) { LAB.F = v; $("labFV").textContent = v.toFixed(0) + " N"; });
    bindRange("labMu", function (v) { LAB.mu = v; $("labMuV").textContent = "μ = " + v.toFixed(2); });
    bindRange("labV0", function (v) { LAB.v0 = v; $("labV0V").textContent = v.toFixed(1) + " m/s"; });
    $("labForceOn").addEventListener("change", function () { LAB.on = $("labForceOn").checked; });
    $("labStart").addEventListener("click", function () {
      APP.SFX.click(); labFit();
      LAB.running = !LAB.running;
      $("labStart").textContent = LAB.running ? "⏸ Pause" : "▶ Start";
    });
    $("labReset").addEventListener("click", function () {
      APP.SFX.click(); LAB.running = false; $("labStart").textContent = "▶ Start";
      LAB.v0 = parseFloat($("labV0").value); labReset();
    });
  }

  return { init: init };
})();
