"use strict";
(function () {
  var KEY = "learncraft_coding_adventure_v1";
  var missions = [
    { id: "greeting", title: "The greeting robot", skill: "Variables", prompt: "The robot needs a reusable greeting for Ada.", goal: "Create a variable named greeting with the exact value \"Hello, Ada!\".", starter: "// Create the greeting variable\nvar greeting = \"\";", hint: "Use: var greeting = \"Hello, Ada!\";", check: function (code) { return /\b(?:var|let|const)\s+greeting\s*=\s*["']Hello,\s*Ada!["']/.test(code); } },
    { id: "decision", title: "The gatekeeper", skill: "Conditions", prompt: "The gate opens only when the key is collected.", goal: "Write an if statement that checks keyFound and includes the text \"Open gate\".", starter: "var keyFound = true;\n\n// Check the key and open the gate", hint: "Start with: if (keyFound) { ... }", check: function (code) { return /\bif\s*\(\s*keyFound\s*\)/.test(code) && /open\s+gate/i.test(code); } },
    { id: "loop", title: "Count the stars", skill: "Loops", prompt: "A rocket needs three stars before launch.", goal: "Use a loop that repeats three times and includes the text \"⭐\" or star.", starter: "// Collect three stars\nfor (var i = 0; i < 3; i++) {\n  // collect a star\n}", hint: "A for loop should begin with i = 0 and continue while i < 3.", check: function (code) { return /for\s*\([^;]*i\s*=\s*0[^;]*i\s*<\s*3[^)]*\)/.test(code) && /⭐|star/i.test(code); } }
  ];
  var profile = load({ xp: 0, solved: [], current: 0 });
  var current = missions[profile.current] || missions[0];
  function $(id) { return document.getElementById(id); }
  function load(fallback) { try { var raw = localStorage.getItem(KEY); var value = raw ? JSON.parse(raw) : fallback; return value && Array.isArray(value.solved) ? value : fallback; } catch (error) { return fallback; } }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(profile)); } catch (error) {} }
  function renderProfile() { $("xp").textContent = profile.xp; $("level").textContent = Math.floor(profile.xp / 100) + 1; $("solved").textContent = profile.solved.length; }
  function renderMissions() {
    var list = $("missionList"); list.innerHTML = "";
    missions.forEach(function (mission, index) {
      var button = document.createElement("button"); button.type = "button"; button.className = "mission" + (mission.id === current.id ? " active" : "") + (profile.solved.indexOf(mission.id) !== -1 ? " done" : "");
      button.innerHTML = "<strong>" + mission.title + "</strong><small>" + mission.skill + "</small>";
      button.addEventListener("click", function () { current = mission; profile.current = index; save(); render(); });
      list.appendChild(button);
    });
  }
  function render() {
    renderProfile(); renderMissions();
    $("missionTag").textContent = "Mission " + (missions.indexOf(current) + 1) + " · " + current.skill;
    $("missionTitle").textContent = current.title; $("missionPrompt").textContent = current.prompt; $("missionGoal").textContent = current.goal;
    $("codeInput").value = current.starter; $("hint").className = "hint hidden"; $("output").className = "output neutral"; $("output").textContent = "Run your code to test the mission.";
  }
  $("runBtn").addEventListener("click", function () {
    var output = $("output");
    if (current.check($("codeInput").value)) {
      var fresh = profile.solved.indexOf(current.id) === -1;
      if (fresh) { profile.solved.push(current.id); profile.xp += 50; save(); }
      renderProfile(); renderMissions(); output.className = "output success"; output.textContent = fresh ? "✅ Mission complete! +50 XP" : "✅ Correct! You already earned XP for this mission.";
    } else { output.className = "output error"; output.textContent = "Not quite yet. Check the goal and try again."; }
  });
  $("hintBtn").addEventListener("click", function () { $("hint").textContent = current.hint; $("hint").className = "hint"; });
  $("resetCode").addEventListener("click", function () { $("codeInput").value = current.starter; });
  $("resetProgress").addEventListener("click", function () { profile = { xp: 0, solved: [], current: 0 }; current = missions[0]; save(); render(); });
  render();
})();
