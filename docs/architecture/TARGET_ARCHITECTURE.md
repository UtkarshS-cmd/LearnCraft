# LearnCraft — Target Architecture

Companion to ARCHITECTURE_AUDIT.md. Offline-first is non-negotiable.

## Vision

LearnCraft stays the intelligence layer (curriculum, concept graph, mastery, roadmap, AI tutoring, assessment, progress, teacher analytics, resource orchestration). External platforms provide specialized function via links/adapters, never as iframe wrappers.

## Layers (target)

Frontend: keep Jinja shell now; add /resources hub in same design-system. Later: templates/static -> app/components/features/hooks/stores/lib/public (React/Next only after backend contracts freeze). Never one giant migration.
Backend: thin main.py -> routes/* blueprints + api/v1/* versioned JSON. Repository (SQL) / Service (rules) / API (HTTP) separation. SQLite stays; Postgres only when required (no SQLite SQL in services).
AI: keep ai_tutor.py facade; grow app/ai/{orchestrator,tutor,mentor,memory,rag,assessment,providers/ollama,openai,gemini,groq,openrouter}. Orchestrator routes Tutor/Mentor/Notes/Assessment/RAG/Curriculum. RAG retrieves Subject/Chapter/Topic/Lesson/Concept/Question/Simulation/Notes (+ registry resources) with provenance; never invent URLs. Memory stores weak/strong concepts, goals, difficulty, mistakes, completions, revisions only.
Learning: Board->Class->Subject->Chapter->Topic->Lesson->Concept->Question (board-agnostic core; CBSE IX/X first dataset). Concept graph acyclic + validated. Mastery = accuracy + consistency + difficulty + recency + completion (rule-based, configurable). Roadmap = Curriculum + Graph + Mastery + Goals + Performance with WHY reasons.
Assessment: Practice/Quiz/Mock/Adaptive/Revision/AI-test/PYQ; keep difficulty/type/competency/concept/chapter/source/verification; AI questions marked generated.
Notes: workspace (CRUD/pin/search/tag + concept/lesson links + AI summarize/flashcards/quiz) behind clean abstractions.
Teacher: students/classes/assignments/progress/weak concepts/quiz/activity/announcements/interventions; strict roles; resource verify/disable.
Offline: OFFLINE/ONLINE/AUTO modes + sync queue preserved. External launches show Requires Internet offline; metadata/bookmarks stay visible.
Sims: common interface {simulation_id,subject,chapter,concepts,difficulty,launch_url,offline_supported,metadata}; link every sim to concepts.
Gamification (services/gamification): XP/levels/streaks/badges; never affects correctness. Profile: identity/education/goals/subjects/skills/mastery/activity/preferences/achievements (minimal PII).

## API compatibility

Never break /auth/*, /api/v1/*, /notes, /api/content/*, /api/sync/* without: find consumers, check templates+tests, version compatibly, update callers, add regression tests.

## Order

P0 stabilize (bug fixes, no features) -> P1 learning core (profile/mastery/roadmap) -> P2 AI (orchestrator/RAG/memory) -> P3 notes+assessment/recall -> P4 teacher analytics -> P5 sims -> P6 gamification -> P7 frontend. Small groups, runnable after every phase, pytest + validate + smoke + route + functional + live + assets each time.

