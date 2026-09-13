/* PhysicsGame core engine — 100% offline, no dependencies.
   Real equations only: F=ma (semi-implicit Euler), dry friction with
   static hold, momentum-conserving impulses. Works in browser + Node. */
"use strict";
var PHYS = (function () {
  var G = 9.8;

  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function lerp(a, b, t) { return a + (b - a) * t; }

  // 1D rigid body: { m, x, v, a }
  function body1D(m, x, v) { return { m: m, x: x, v: v || 0, a: 0 }; }

  // One physics step. Fa = applied force (N), mu = friction coefficient.
  // Returns { a, Ff (friction actually applied), Fnet }.
  function step1D(b, Fa, mu, dt) {
    var N = b.m * G, Ff = 0;
    if (Math.abs(b.v) < 0.02 && Math.abs(Fa) <= mu * N) {
      b.a = 0; Ff = -Fa; // static hold: net force = 0, stays at rest
      return { a: 0, Ff: Ff, Fnet: 0 };
    }
    if (b.v !== 0) Ff = -Math.sign(b.v) * mu * N;
    else if (Fa !== 0) Ff = -Math.sign(Fa) * mu * N;
    var Fnet = Fa + Ff;
    var a = Fnet / b.m;
    var vNew = b.v + a * dt;
    if (Fa === 0 && vNew !== 0 && Math.sign(vNew) !== Math.sign(b.v)) {
      vNew = 0; a = -b.v / dt; // friction stops it exactly, no jitter
    }
    b.v = vNew;
    b.x += b.v * dt;
    b.a = a;
    return { a: a, Ff: Ff, Fnet: Fnet };
  }

  // 2D point mass (for direction-change demos, rocket). F = {x,y}.
  function body2D(m, x, y, vx, vy) { return { m: m, x: x, y: y, vx: vx || 0, vy: vy || 0, ax: 0, ay: 0 }; }
  function step2D(p, Fx, Fy, mu, dt) {
    var N = p.m * G;
    var sp = Math.hypot(p.vx, p.vy);
    var Ffx = 0, Ffy = 0;
    if (sp > 0.02 && mu > 0) { Ffx = -p.vx / sp * mu * N; Ffy = -p.vy / sp * mu * N; }
    p.ax = (Fx + Ffx) / p.m;
    p.ay = (Fy + Ffy) / p.m;
    p.vx += p.ax * dt; p.vy += p.ay * dt;
    p.x += p.vx * dt; p.y += p.vy * dt;
    return { ax: p.ax, ay: p.ay };
  }

  // Elastic-ish impulse split for action-reaction push (momentum conserved):
  // two bodies get equal-opposite impulse J over contact time.
  function pushApart(A, B, J) {
    A.v += -J / A.m;
    B.v += J / B.m;
    return { vA: A.v, vB: B.v, pTotal: A.m * A.v + B.m * B.v };
  }

  // Analytic helpers (used by games to set targets + verify results honestly)
  function coastDistance(v0, mu) { // distance to stop under kinetic friction
    if (mu <= 0) return Infinity;
    return (v0 * v0) / (2 * mu * G);
  }
  function pushPhase(m, F, mu, T) { // v,x after pushing with F for T seconds from rest
    var r = step1D, b = body1D(m, 0, 0), dt = 1 / 240, t = 0;
    while (t < T - 1e-9) { r(b, F, mu, dt); t += dt; }
    return { v: b.v, x: b.x };
  }
  function stoppingPoint(m, F, mu, T) { // push for T then release; where does it stop?
    var ph = pushPhase(m, F, mu, T);
    return ph.x + coastDistance(Math.max(0, ph.v), mu);
  }

  // ---- Canvas helpers (browser only; guarded so Node can load this file) ----
  function fitCanvas(cv, hCss) {
    var dpr = 1;
    try { dpr = Math.min(1.5, window.devicePixelRatio || 1); } catch (e) {}
    var w = cv.clientWidth || cv.parentNode.clientWidth || 600;
    var h = hCss || 220;
    cv.width = Math.round(w * dpr);
    cv.height = Math.round(h * dpr);
    cv.style.height = h + "px";
    var ctx = cv.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx: ctx, w: w, h: h };
  }

  function drawArrow(ctx, x1, y1, x2, y2, color, width, label) {
    var dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy);
    if (len < 4) return;
    var ang = Math.atan2(dy, dx);
    ctx.save();
    ctx.strokeStyle = color; ctx.fillStyle = color;
    ctx.lineWidth = width || 3; ctx.lineCap = "round";
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    var hs = 8 + (width || 3);
    ctx.beginPath();
    ctx.moveTo(x2, y2);
    ctx.lineTo(x2 - hs * Math.cos(ang - 0.42), y2 - hs * Math.sin(ang - 0.42));
    ctx.lineTo(x2 - hs * Math.cos(ang + 0.42), y2 - hs * Math.sin(ang + 0.42));
    ctx.closePath(); ctx.fill();
    if (label) {
      ctx.font = "bold 12px sans-serif";
      ctx.fillText(label, x2 + 6, y2 - 6);
    }
    ctx.restore();
  }

  // Tiny live graph: push numbers, draws auto-scaled line chart.
  function Graph(max) {
    this.max = max || 240;
    this.series = []; // {data:[], color}
  }
  Graph.prototype.addSeries = function (color) {
    var s = { data: [], color: color };
    this.series.push(s);
    return this.series.length - 1;
  };
  Graph.prototype.push = function (idx, v) {
    var d = this.series[idx].data;
    d.push(v);
    if (d.length > this.max) d.shift();
  };
  Graph.prototype.clear = function () {
    for (var i = 0; i < this.series.length; i++) this.series[i].data = [];
  };
  Graph.prototype.draw = function (ctx, w, h, opts) {
    opts = opts || {};
    ctx.save();
    ctx.fillStyle = opts.bg || "#0f172a";
    ctx.fillRect(0, 0, w, h);
    var lo = Infinity, hi = -Infinity, i, j;
    for (i = 0; i < this.series.length; i++) {
      var d = this.series[i].data;
      for (j = 0; j < d.length; j++) { if (d[j] < lo) lo = d[j]; if (d[j] > hi) hi = d[j]; }
    }
    if (lo === Infinity) { lo = 0; hi = 1; }
    if (hi - lo < 1e-6) { hi = lo + 1; }
    var pad = (hi - lo) * 0.12; lo -= pad; hi += pad;
    function X(k, n) { return n <= 1 ? w - 2 : 4 + (k / (this.max - 1)) * (w - 8); }
    function Y(v) { return h - 4 - ((v - lo) / (hi - lo)) * (h - 8); }
    var self = this;
    ctx.strokeStyle = "rgba(255,255,255,.18)"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0, Y(0)); ctx.lineTo(w, Y(0)); ctx.stroke();
    for (i = 0; i < this.series.length; i++) {
      var dd = this.series[i].data;
      ctx.strokeStyle = this.series[i].color; ctx.lineWidth = 2;
      ctx.beginPath();
      for (j = 0; j < dd.length; j++) {
        var xx = X.call(self, j + (self.max - dd.length), dd.length), yy = Y(dd[j]);
        if (j === 0) ctx.moveTo(xx, yy); else ctx.lineTo(xx, yy);
      }
      ctx.stroke();
    }
    if (opts.label) { ctx.fillStyle = "#e2e8f0"; ctx.font = "bold 11px sans-serif"; ctx.fillText(opts.label, 6, 13); }
    ctx.restore();
  };

  // Fixed-step loop; pauses when tab hidden. Returns {stop}.
  function makeLoop(step, draw) {
    var acc = 0, last = 0, running = true, DT = 1 / 60, raf = 0;
    function frame(t) {
      if (!running) return;
      if (!last) last = t;
      var dt = Math.min(0.1, (t - last) / 1000);
      last = t;
      acc += dt;
      while (acc >= DT) { step(DT); acc -= DT; }
      draw();
      raf = requestAnimationFrame(frame);
    }
    try { raf = requestAnimationFrame(frame); } catch (e) {}
    function onVis() { try { if (document.hidden) { running = false; cancelAnimationFrame(raf); } else if (!running) { running = true; last = 0; raf = requestAnimationFrame(frame); } } catch (e) {} }
    try { document.addEventListener("visibilitychange", onVis); } catch (e) {}
    return { stop: function () { running = false; try { cancelAnimationFrame(raf); document.removeEventListener("visibilitychange", onVis); } catch (e) {} } };
  }

  var api = {
    G: G, clamp: clamp, lerp: lerp,
    body1D: body1D, step1D: step1D, body2D: body2D, step2D: step2D,
    pushApart: pushApart, coastDistance: coastDistance,
    pushPhase: pushPhase, stoppingPoint: stoppingPoint,
    fitCanvas: fitCanvas, drawArrow: drawArrow, Graph: Graph, makeLoop: makeLoop
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  return api;
})();
