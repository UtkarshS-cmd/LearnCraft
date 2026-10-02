// Concept Mastery Map.
// Renders the concept graph entirely from backend data (/api/v1/mastery/map).
// No curriculum, mastery or concept data is hard-coded in this file.
(function () {
  'use strict';

  var STATE_COLORS = {
    NOT_STARTED: '#94a3b8',
    LEARNING: '#f59e0b',
    DEVELOPING: '#3b82f6',
    MASTERED: '#16a34a'
  };

  var nodes = [];
  var edges = [];

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/[&<>"]/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
      });
  }

  function nodeById(id) {
    for (var i = 0; i < nodes.length; i += 1) {
      if (nodes[i].concept_id === id) return nodes[i];
    }
    return null;
  }

  // ---- data -----------------------------------------------------------
  function loadMap() {
    var params = new URLSearchParams();
    var classSelect = document.getElementById('classFilter');
    var subjectSelect = document.getElementById('subjectFilter');
    if (classSelect && classSelect.value) params.set('class', classSelect.value);
    if (subjectSelect && subjectSelect.value) params.set('subject', subjectSelect.value);
    document.getElementById('mapLoading').hidden = false;

    fetch('/api/v1/mastery/map?' + params.toString())
      .then(function (response) {
        return response.json().then(function (data) {
          return { ok: response.ok, data: data };
        });
      })
      .then(function (result) {
        if (!result.ok) throw new Error(result.data.message || 'Could not load the map');
        nodes = result.data.nodes || [];
        edges = result.data.edges || [];
        renderLegend(result.data.summary, result.data.legend);
        renderFilters(result.data);
        document.getElementById('mapEmpty').hidden = nodes.length > 0;
        draw();
        document.getElementById('mapIntro').textContent =
          nodes.length + ' concepts. States come from your recorded mastery scores.';
      })
      .catch(function (error) {
        document.getElementById('mapIntro').textContent = 'Could not load the mastery map.';
        var empty = document.getElementById('mapEmpty');
        empty.hidden = false;
        var body = empty.querySelector('.body-sm');
        if (body) body.textContent = error.message;
      })
      .finally(function () {
        document.getElementById('mapLoading').hidden = true;
      });
  }

  function renderLegend(summary, legend) {
    var states = (legend && legend.states) || Object.keys(STATE_COLORS);
    var masteredAt = (legend && legend.mastered_at != null) ? legend.mastered_at : 75;
    var developingAt = (legend && legend.developing_at != null) ? legend.developing_at : 45;
    document.getElementById('legend').innerHTML = states.map(function (state) {
      var count = (summary && summary[state] != null) ? summary[state] : 0;
      return '<span><i style="background:' + STATE_COLORS[state] + '"></i>' +
        esc(state.replace('_', ' ')) + ' (' + count + ')</span>';
    }).join('') +
      '<span class="caption">Mastered from ' + masteredAt + '% - developing from ' +
      developingAt + '%</span>';
  }

  function renderFilters(data) {
    var classSelect = document.getElementById('classFilter');
    if (classSelect && data.classes && data.classes.length &&
        classSelect.options.length !== data.classes.length + 1) {
      classSelect.innerHTML = '<option value="">All classes</option>' +
        data.classes.map(function (item) {
          return '<option value="' + esc(item.class_name) + '">' +
            esc(item.class_level || item.class_name) + '</option>';
        }).join('');
    }
    var subjectSelect = document.getElementById('subjectFilter');
    if (subjectSelect && data.subjects && data.subjects.length &&
        subjectSelect.options.length !== data.subjects.length + 1) {
      subjectSelect.innerHTML = '<option value="">All subjects</option>' +
        data.subjects.map(function (item) {
          return '<option value="' + esc(item.slug) + '">' + esc(item.name) + '</option>';
        }).join('');
    }
  }

  // ---- layout ---------------------------------------------------------
  // Deterministic layered layout: prerequisites sit left of their dependents.
  function layout() {
    var depth = {};

    function resolve(id, seen) {
      if (depth[id] !== undefined) return depth[id];
      if (seen[id]) return 0;
      seen[id] = true;
      var node = nodeById(id);
      var parents = ((node && node.prerequisites) || []).filter(nodeById);
      depth[id] = parents.length
        ? Math.max.apply(null, parents.map(function (p) {
            return resolve(p.concept_id, seen);
          })) + 1
        : 0;
      return depth[id];
    }

    nodes.forEach(function (node) {
      resolve(node.concept_id, {});
    });

    var columns = {};
    nodes.forEach(function (node) {
      var level = depth[node.concept_id];
      (columns[level] = columns[level] || []).push(node);
    });

    var positions = {};
    Object.keys(columns).forEach(function (key) {
      var column = columns[key];
      column.forEach(function (node, index) {
        positions[node.concept_id] = {
          x: 90 + Number(key) * 150,
          y: 60 + index * (460 / Math.max(1, column.length))
        };
      });
    });
    return positions;
  }

  // ---- rendering ------------------------------------------------------
  function draw() {
    var svg = document.getElementById('mapSvg');
    if (!svg) return;
    if (!nodes.length) {
      svg.innerHTML = '';
      return;
    }
    var positions = layout();
    var maxX = 560;
    Object.keys(positions).forEach(function (key) {
      if (positions[key].x + 150 > maxX) maxX = positions[key].x + 150;
    });
    svg.setAttribute('viewBox', '0 0 ' + maxX + ' 520');

    var edgeMarkup = edges.map(function (edge) {
      var from = positions[edge.from];
      var to = positions[edge.to];
      if (!from || !to) return '';
      var mid = (from.x + to.x) / 2;
      return '<path class="map-edge" d="M ' + from.x + ' ' + from.y +
        ' C ' + mid + ' ' + from.y + ', ' + mid + ' ' + to.y + ', ' + to.x + ' ' + to.y + '"/>';
    }).join('');

    var nodeMarkup = nodes.map(function (node) {
      var pos = positions[node.concept_id];
      if (!pos) return '';
      var color = STATE_COLORS[node.state] || '#94a3b8';
      var radius = 12 + Math.round(((node.mastery || 0) / 100) * 8);
      var title = node.title || node.concept_id;
      var label = title.length > 16 ? title.slice(0, 15) + '...' : title;
      return '<g class="map-node state-' + esc(node.state) + '" tabindex="0" role="button" ' +
        'aria-label="' + esc(title) + ': ' + esc(node.state) + ', ' +
        Math.round(node.mastery || 0) + ' percent mastery" data-concept="' +
        esc(node.concept_id) + '" transform="translate(' + pos.x + ',' + pos.y + ')">' +
        '<circle r="' + radius + '" fill="' + color + '"></circle>' +
        '<text y="' + (radius + 14) + '">' + esc(label) + '</text></g>';
    }).join('');

    svg.innerHTML = edgeMarkup + nodeMarkup;
    svg.querySelectorAll('.map-node').forEach(function (group) {
      var open = function () {
        showConcept(group.getAttribute('data-concept'));
      };
      group.addEventListener('click', open);
      group.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          open();
        }
      });
    });

    var requested = new URLSearchParams(window.location.search).get('concept');
    if (requested && nodeById(requested)) showConcept(requested);

  // ---- drill-down -----------------------------------------------------
  function chips(list) {
    if (!list || !list.length) return '';
    return '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:4px">' +
      list.map(function (p) {
        return '<button class="btn btn-ghost btn-sm" data-concept="' +
          esc(p.concept_id) + '">' + esc(p.title) + '</button>';
      }).join('') + '</div>';
  }

  function detailMarkup(c) {
    var recommended = c.recommended || {};
    var actions = (recommended.actions || []).map(function (a) {
      return '<a class="btn btn-primary btn-sm" href="' + esc(a.href) + '">' +
        esc(a.label) + '</a>';
    }).join('');

    var extras = '';
    if (c.lesson && c.lesson.href) {
      extras += '<a class="btn btn-secondary btn-sm" style="margin-top:8px" href="' +
        esc(c.lesson.href) + '">' + esc(c.lesson.title || 'Open lesson') + '</a>';
    }
    if (c.simulation && c.simulation.href) {
      extras += ' <a class="btn btn-secondary btn-sm" style="margin-top:8px" href="' +
        esc(c.simulation.href) + '">' +
        esc(c.simulation.title || 'Run simulation') + '</a>';
    }

    var attempts = '';
    if (c.recent_attempts && c.recent_attempts.length) {
      attempts = '<div class="caption" style="margin-top:12px">Recent attempts</div>' +
        '<div style="margin-top:4px">' +
        c.recent_attempts.slice(0, 5).map(function (a) {
          return '<div class="caption">' + (a.correct ? 'correct' : 'incorrect') +
            ' - ' + esc(a.question_id) + ' (' + esc(a.created_at || '') + ')</div>';
        }).join('') + '</div>';
    }

    return '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">' +
        '<div><div class="eyebrow">Concept</div>' +
        '<div class="h3" style="margin-top:4px">' + esc(c.title) + '</div></div>' +
        '<span class="state-pill state-' + esc(c.state) + '">' +
        esc(String(c.state || '').replace('_', ' ')) + '</span></div>' +
      '<div class="mini-stats">' +
        '<div><b>' + Math.round(c.mastery || 0) + '%</b>' +
        '<span class="caption">Mastery</span></div>' +
        '<div><b>' + (c.attempts || 0) + '</b>' +
        '<span class="caption">Attempts</span></div>' +
        '<div><b>' + Math.round(c.accuracy || 0) + '%</b>' +
        '<span class="caption">Accuracy</span></div>' +
      '</div>' +
      (c.prerequisites && c.prerequisites.length
        ? '<div class="caption" style="margin-top:12px">Prerequisites</div>' +
          chips(c.prerequisites)
        : '') +
      (c.next_concepts && c.next_concepts.length
        ? '<div class="caption" style="margin-top:12px">Next concepts</div>' +
          chips(c.next_concepts)
        : '') +
      '<div class="caption" style="margin-top:12px">Recommended because</div>' +
      '<ul class="why-list">' +
      (recommended.why || []).map(function (w) {
        return '<li>' + esc(w) + '</li>';
      }).join('') + '</ul>' +
      '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px">' +
        actions + '</div>' + extras + attempts;
  }

  function showConcept(conceptId) {
    var panel = document.getElementById('detailPanel');
    if (!panel || !conceptId) return;
    panel.innerHTML = '<div class="caption">Loading concept...</div>';
    fetch('/api/v1/mastery/concepts/' + encodeURIComponent(conceptId))
      .then(function (response) {
        return response.json().then(function (data) {
          return { ok: response.ok, data: data };
        });
      })
      .then(function (result) {
        if (!result.ok) throw new Error(result.data.message || 'Concept not found');
        panel.innerHTML = detailMarkup(result.data.concept);
        panel.querySelectorAll('[data-concept]').forEach(function (button) {
          button.addEventListener('click', function () {
            showConcept(button.getAttribute('data-concept'));
          });
        });
      })
      .catch(function (error) {
        panel.innerHTML = '<div class="h3">Unavailable</div><p class="caption">' +
          esc(error.message) + '</p>';
      });
  }

  // ---- init -----------------------------------------------------------
  document.addEventListener('DOMContentLoaded', function () {
    if (!document.getElementById('mapSvg')) return;
    var classSelect = document.getElementById('classFilter');
    var subjectSelect = document.getElementById('subjectFilter');
    if (classSelect) classSelect.addEventListener('change', loadMap);
    if (subjectSelect) subjectSelect.addEventListener('change', loadMap);
    loadMap();
  });
})();

  }

