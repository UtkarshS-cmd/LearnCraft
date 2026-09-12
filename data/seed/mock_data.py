"""Mock/local data for the Student App Shell. Offline-first placeholders."""

STUDENT = {
    "name": "Aarav Sharma",
    "roll_no": "LC-2026-014",
    "avatar": "AS",
    "level": 7,
    "xp": 2450,
    "xp_next": 3000,
    "streak_days": 12,
    "overall_progress": 68,
    "rank": "#3 in Lab A",
}

CONTINUE_LEARNING = {
    "subject": "Physics",
    "subject_slug": "physics",
    "subject_color": "#6366F1",
    "subject_bg": "#EEF2FF",
    "chapter": "Chapter 4 · Laws of Motion",
    "lesson": "Lesson 4.3 · Friction Simulator",
    "progress_pct": 72,
    "time_left": "12 min left",
    "last_activity": "Stopped at Step 4 of 6 · Yesterday, 4:20 PM",
    "resume_url": "/subjects/physics/lessons/friction-43",
}

TODAY_WORK = [
    {"kind": "Practical", "title": "Friction Coefficient Lab", "meta": "Physics · 4 of 6 steps done", "due": "Due tomorrow", "urgent": True, "href": "/practical", "action": "Resume lab"},
    {"kind": "Assignment", "title": "Newton's Laws — Problem Set 4", "meta": "Physics · 7 of 12 answered", "due": "Due tomorrow · 10:00 AM", "urgent": True, "href": "/assignments", "action": "Continue"},
    {"kind": "Learning", "title": "Quadratic Equations — Graphing Lab", "meta": "Mathematics · 54% · 25 min left", "due": "Incomplete", "urgent": False, "href": "/my-learning", "action": "Resume"},
    {"kind": "Deadline", "title": "Python Loops — 5 Programs", "meta": "Computer Science · Not started", "due": "Due Mon · 9:00 AM", "urgent": False, "href": "/assignments", "action": "Start"},
]

SUBJECTS = [
    {"slug": "physics", "name": "Physics", "icon": "◈", "color": "#6366F1", "bg": "#EEF2FF", "chapters": 12, "completed": 8, "progress": 67, "tag": "In progress", "current_chapter": "Ch.4 · Laws of Motion"},
    {"slug": "chemistry", "name": "Chemistry", "icon": "⬢", "color": "#0891B2", "bg": "#ECFEFF", "chapters": 10, "completed": 6, "progress": 60, "tag": "In progress", "current_chapter": "Ch.7 · Acids & Bases"},
    {"slug": "maths", "name": "Mathematics", "icon": "△", "color": "#7C3AED", "bg": "#F5F3FF", "chapters": 14, "completed": 9, "progress": 64, "tag": "In progress", "current_chapter": "Ch.5 · Quadratics"},
    {"slug": "biology", "name": "Biology", "icon": "●", "color": "#16A34A", "bg": "#F0FDF4", "chapters": 9, "completed": 7, "progress": 78, "tag": "Ahead", "current_chapter": "Ch.8 · Cell Structure"},
    {"slug": "cs", "name": "Computer Science", "icon": "▣", "color": "#EA580C", "bg": "#FFF7ED", "chapters": 11, "completed": 5, "progress": 45, "tag": "Needs focus", "current_chapter": "Ch.6 · Loops in Python"},
    {"slug": "english", "name": "English", "icon": "✎", "color": "#DB2777", "bg": "#FDF2F8", "chapters": 8, "completed": 4, "progress": 50, "tag": "In progress", "current_chapter": "Ch.5 · Writing Skills"},
]

MY_LEARNING = [
    {"subject": "Physics", "slug": "physics", "chapter": "Laws of Motion", "lesson": "Friction Simulator", "progress": 72, "status": "in_progress", "time": "12 min left", "color": "#6366F1", "bg": "#EEF2FF"},
    {"subject": "Mathematics", "slug": "maths", "chapter": "Quadratic Equations", "lesson": "Graphing Lab", "progress": 54, "status": "in_progress", "time": "25 min left", "color": "#7C3AED", "bg": "#F5F3FF"},
    {"subject": "Biology", "slug": "biology", "chapter": "Cell Structure", "lesson": "Virtual Microscope", "progress": 100, "status": "completed", "time": "Done · 2d ago", "color": "#16A34A", "bg": "#F0FDF4"},
    {"subject": "Computer Science", "slug": "cs", "chapter": "Loops in Python", "lesson": "Code Sandbox", "progress": 30, "status": "in_progress", "time": "40 min left", "color": "#EA580C", "bg": "#FFF7ED"},
    {"subject": "Chemistry", "slug": "chemistry", "chapter": "Acids & Bases", "lesson": "pH Lab", "progress": 100, "status": "completed", "time": "Done · 5d ago", "color": "#0891B2", "bg": "#ECFEFF"},
]

ASSIGNMENTS = [
    {"id": 1, "title": "Newton's Laws — Problem Set 4", "subject": "Physics", "due": "Tomorrow · 10:00 AM", "due_tone": "warn", "status": "Pending", "progress": 60, "questions": 12, "done": 7},
    {"id": 2, "title": "Quadratic Graphs Worksheet", "subject": "Mathematics", "due": "Fri · 2:00 PM", "due_tone": "info", "status": "Pending", "progress": 20, "questions": 10, "done": 2},
    {"id": 3, "title": "Cell Diagram Labelling", "subject": "Biology", "due": "Submitted · On time", "due_tone": "ok", "status": "Submitted", "progress": 100, "questions": 8, "done": 8},
    {"id": 4, "title": "Python Loops — 5 Programs", "subject": "Computer Science", "due": "Mon · 9:00 AM", "due_tone": "info", "status": "Not started", "progress": 0, "questions": 5, "done": 0},
]

# Assignment types are registry entries so new task renderers can be added without
# changing the assignment shell or submission lifecycle.
ASSIGNMENT_TYPES = ["mcq", "short_answer", "numerical", "coding", "file_submission", "practical_task"]
ASSIGNMENT_WORKSPACE = {
    "id": "newtons-laws-4", "subject": "Physics", "subject_color": "#6366F1", "subject_bg": "#EEF2FF",
    "title": "Newton's Laws — Problem Set 4", "instructions": "Show how forces change motion. Answer each task, then review your work before submitting.",
    "estimated_time": "25 min", "marks": 20, "deadline": "Tomorrow · 10:00 AM", "progress": 0,
    "tasks": [
        {"id": "q1", "type": "mcq", "label": "Question 1 · Concept check", "prompt": "Which statement best describes Newton's First Law?", "options": ["Objects need a force to keep moving.", "An object keeps its motion unless an unbalanced force acts.", "Every force creates acceleration of the same size."]},
        {"id": "q2", "type": "short_answer", "label": "Question 2 · Explain", "prompt": "In one or two sentences, explain why a passenger moves forward when a bus stops suddenly.", "placeholder": "Write your explanation..."},
        {"id": "q3", "type": "numerical", "label": "Question 3 · Calculate", "prompt": "A 4 kg cart accelerates at 3 m/s². What net force acts on it?", "unit": "N", "answer": "12"},
        {"id": "q4", "type": "coding", "label": "Question 4 · Code it", "prompt": "Write a function that returns force using F = m × a. Run the tests before reviewing.", "starter": "def force(mass, acceleration):\n    # Return the net force\n    pass", "tests": ["Returns 12 for force(4, 3)", "Returns 0 for force(0, 8)"]},
        {"id": "q5", "type": "file_submission", "label": "Question 5 · Show your work", "prompt": "Optionally attach a photo or PDF of your force diagram.", "accept": ".png,.jpg,.jpeg,.pdf"},
        {"id": "q6", "type": "practical_task", "label": "Question 6 · Practical task", "prompt": "Describe one experiment you could perform to measure the acceleration of a toy car.", "placeholder": "List the setup, measurement, and calculation..."},
    ],
}

PRACTICALS = [
    {"id": 1, "title": "Friction Coefficient Lab", "subject": "Physics", "env": "Physics Sim · v2.1", "status": "Pending", "tone": "warn", "steps": 6, "done": 4},
    {"id": 2, "title": "Titration — Acid vs Base", "subject": "Chemistry", "env": "Chem Lab · v1.4", "status": "Ready", "tone": "info", "steps": 8, "done": 0},
    {"id": 3, "title": "Onion Peel Microscopy", "subject": "Biology", "env": "Bio Scope · v3.0", "status": "Completed", "tone": "ok", "steps": 5, "done": 5},
    {"id": 4, "title": "Loops Lab — 5 Programs", "subject": "Computer Science", "env": "Code Lab · v2.0", "status": "In Progress", "tone": "info", "steps": 5, "done": 2},
]

# Common practical workspace schema for future code, calculation, diagram, and simulation modes.
PRACTICAL_WORKSPACE = {
    "subject": "Computer Science", "subject_color": "#EA580C", "subject_bg": "#FFF7ED",
    "title": "Loops Lab — 5 Programs", "environment": "Code Lab · Python", "progress": 40,
    "step": "2 of 5 programs", "time": "35 min suggested", "mode": "code",
    "instructions": "Write a program that prints the squares of the numbers 1 through 5, one per line. Use a loop so the pattern can scale to any ending number.",
    "requirements": ["Use a for loop", "Start at 1 and end at 5", "Print one square per line"],
    "starter_code": "# Print the squares from 1 through 5\nfor number in range(1, 6):\n    # Your code here\n    pass",
    "tests": [
        {"name": "Uses a loop", "detail": "A for loop iterates over the numbers", "id": "loop"},
        {"name": "Prints five squares", "detail": "The output is 1, 4, 9, 16, 25", "id": "squares"},
        {"name": "Scales cleanly", "detail": "The range ends at 6 (exclusive)", "id": "range"},
    ],
}

SANDBOX_CARDS = [
    {"slug": "python", "name": "Python Playground", "desc": "Write & run Python offline. 5 starter templates.", "meta": "Offline · Auto-save", "icon": "▣", "color": "#EA580C", "bg": "#FFF7ED"},
    {"slug": "physics-sim", "name": "Physics Simulator", "desc": "Friction, projectile & pendulum sandboxes.", "meta": "3 sims · No setup", "icon": "◈", "color": "#6366F1", "bg": "#EEF2FF"},
    {"slug": "chem-lab", "name": "Chemistry Lab", "desc": "Mix acids, bases & salts safely — virtual.", "meta": "12 reagents", "icon": "⬢", "color": "#0891B2", "bg": "#ECFEFF"},
    {"slug": "web-lab", "name": "Web Lab (HTML/CSS)", "desc": "Build mini pages with live preview.", "meta": "Live preview", "icon": "✎", "color": "#DB2777", "bg": "#FDF2F8"},
]

ACTIVITY = [
    {"text": "Friction Simulator · Step 4 of 6", "time": "Yesterday · 4:20 PM", "dot": "#6366F1"},
    {"text": "Cell Diagram Labelling submitted", "time": "Yesterday · 11:05 AM", "dot": "#16A34A"},
    {"text": "Quadratic Graphs · 2 of 10 solved", "time": "Mon · 3:40 PM", "dot": "#7C3AED"},
    {"text": "Titration guide opened", "time": "Mon · 10:15 AM", "dot": "#0891B2"},
]

WEEKLY = [
    {"d": "M", "v": 40}, {"d": "T", "v": 65}, {"d": "W", "v": 30},
    {"d": "T", "v": 80}, {"d": "F", "v": 55}, {"d": "S", "v": 90}, {"d": "S", "v": 70},
]

ACHIEVEMENTS = [
    {"name": "7-Day Streak", "desc": "Learned 7 days in a row", "earned": True, "icon": "▲"},
    {"name": "Lab Explorer", "desc": "Tried 3 simulations", "earned": True, "icon": "◈"},
    {"name": "Perfect Score", "desc": "Score 10/10 in any quiz", "earned": False, "icon": "★"},
    {"name": "Early Bird", "desc": "Submit 3 assignments early", "earned": False, "icon": "●"},
]

NOTES_SEED = [
    {"subject": "Physics", "title": "Friction — key formulas", "body": "Static fs ≤ μs·N · Kinetic fk = μk·N · Angle of repose tan θ = μs", "updated": "2h ago"},
    {"subject": "Maths", "title": "Quadratic discriminant", "body": "D > 0 two roots · D = 0 one root · D < 0 no real roots", "updated": "Yesterday"},
]

SUBJECT_DETAIL = None  # legacy: replaced by SUBJECT_PAGES (universal config)

# ---- Universal Subject Page config ----
# Every subject shares ONE schema; only content values change.
# Chapter states: Locked | Available | In Progress | Completed
# Activity states add: Submitted | Needs Review
def _ch(n, title, est, lessons_count, status, progress, prereq, sim, practical, quiz, is_current=False, is_next=False):
    return {"n": n, "title": title, "est": est, "lessons_count": lessons_count,
            "status": status, "progress": progress, "prereq": prereq,
            "sim": sim, "practical": practical, "quiz": quiz,
            "is_current": is_current, "is_next": is_next}


def _make_subject(slug, name, icon, color, bg, description, progress, tags,
                  unit_titles, chapter_titles, sims, practicals, assignments, notes, practice):
    # chapter_titles: 8 titles -> U1: 1-3 Completed, U2: 4 In Progress(current), 5-6 Available(next on 5), U3: 7-8 Locked
    ests = ["40 min", "45 min", "50 min", "55 min", "45 min", "50 min", "60 min", "60 min"]
    statuses = ["Completed", "Completed", "Completed", "In Progress", "Available", "Available", "Locked", "Locked"]
    progs = [100, 100, 100, 68, 0, 0, 0, 0]
    chs = []
    for i, t in enumerate(chapter_titles):
        n = i + 1
        prereq = None if n <= 4 else f"Complete Ch.{n - 1}"
        chs.append(_ch(n, t, ests[i], 6 if n != 4 else 5, statuses[i], progs[i], prereq,
                        sims[(i % len(sims))], practicals[i % len(practicals)]["title"], f"Quiz {n} · 10 Qs",
                        is_current=(n == 4), is_next=(n == 5)))
    units = [
        {"id": "u1", "title": unit_titles[0], "desc": "Foundations — complete to unlock core labs.", "chapters": chs[0:3]},
        {"id": "u2", "title": unit_titles[1], "desc": "Core applications — where you are now.", "chapters": chs[3:6]},
        {"id": "u3", "title": unit_titles[2], "desc": "Advanced — unlocks after Unit 2.", "chapters": chs[6:8]},
    ]
    cur = chs[3]
    return {"slug": slug, "name": name, "icon": icon, "color": color, "bg": bg,
            "description": description, "progress": progress, "tags": tags,
            "continue": {"chapter_label": f"Chapter {cur['n']} · {cur['title']}",
                         "lesson": f"Lesson {cur['n']}.3 · {cur['sim']}",
                         "progress": cur["progress"], "time_left": "12 min left",
                         "href": "/sandbox", "cta": f"Continue {cur['sim']}"},
            "units": units, "practice": practice, "sims": sims,
            "practicals": practicals, "assignments": assignments, "notes": notes}


SUBJECT_PAGES = {}
for _cfg in [
    dict(slug="physics", name="Physics", icon="◈", color="#6366F1", bg="#EEF2FF", progress=67,
         description="Forces, motion and energy — learn by running simulations, not just reading.",
         tags=["12 chapters", "5 labs", "Lab A syllabus"],
         unit_titles=["Unit 1 · Motion Basics", "Unit 2 · Forces in Action", "Unit 3 · Energy & Beyond"],
         chapter_titles=["Motion in a Straight Line", "Vectors & Projectiles", "Newton's Laws — Basics", "Friction & Applications", "Work, Energy & Power", "Circular Motion", "Gravitation", "Oscillations"],
         sims=["Friction Simulator", "Projectile Sim"],
         practicals=[{"title": "Friction Coefficient Lab", "env": "Physics Sim · v2.1", "status": "In Progress", "steps": "4/6 steps", "due": "Due tomorrow"}, {"title": "Projectile Range Lab", "env": "Physics Sim · v2.1", "status": "Available", "steps": "0/5 steps", "due": "Opens after Ch.4"}],
         assignments=[{"title": "Newton's Laws — Problem Set 4", "meta": "7/12 answered", "due": "Due tomorrow · 10:00 AM", "status": "In Progress"}, {"title": "Vectors Worksheet", "meta": "Submitted · auto-graded", "due": "Submitted", "status": "Submitted"}],
         notes=[{"title": "Friction — key formulas", "body": "fs ≤ μs·N · fk = μk·N · tan θ = μs", "updated": "2h ago"}],
         practice=[{"title": "Friction Mastery Quiz", "meta": "10 Qs · 15 min · Ch.4", "status": "In Progress"}, {"title": "Vectors Check", "meta": "8 Qs · submitted, awaiting review", "status": "Needs Review"}, {"title": "Motion Basics Final", "meta": "12 Qs · scored 11/12", "status": "Completed"}]),
    dict(slug="chemistry", name="Chemistry", icon="⬢", color="#0891B2", bg="#ECFEFF", progress=60,
         description="Atoms, reactions and labs — mix chemicals safely in the virtual lab.",
         tags=["10 chapters", "4 labs", "Lab A syllabus"],
         unit_titles=["Unit 1 · Matter Basics", "Unit 2 · Reactions", "Unit 3 · Organic Start"],
         chapter_titles=["Atomic Structure", "Periodic Table", "Chemical Bonding", "Acids, Bases & Salts", "Mole Concept", "Titration & Indicators", "Organic Basics", "Hydrocarbons"],
         sims=["pH Lab", "Titration Sim"],
         practicals=[{"title": "Titration — Acid vs Base", "env": "Chem Lab · v1.4", "status": "Available", "steps": "0/8 steps", "due": "Opens after Ch.4"}, {"title": "Salt Analysis", "env": "Chem Lab · v1.4", "status": "Locked", "steps": "Locked", "due": "Complete Ch.5"}],
         assignments=[{"title": "Acids & Bases Worksheet", "meta": "3/10 answered", "due": "Due Fri", "status": "In Progress"}, {"title": "Bonding Quiz", "meta": "Submitted", "due": "Submitted", "status": "Submitted"}],
         notes=[{"title": "pH scale", "body": "pH < 7 acid · = 7 neutral · > 7 base", "updated": "Yesterday"}],
         practice=[{"title": "Acids Mastery Quiz", "meta": "10 Qs · 15 min · Ch.4", "status": "In Progress"}, {"title": "Bonding Check", "meta": "Submitted, awaiting review", "status": "Needs Review"}, {"title": "Atoms Final", "meta": "Scored 9/10", "status": "Completed"}]),
    dict(slug="maths", name="Mathematics", icon="△", color="#7C3AED", bg="#F5F3FF", progress=64,
         description="Patterns and problem-solving — graph it, don't just memorize it.",
         tags=["14 chapters", "3 labs", "Lab A syllabus"],
         unit_titles=["Unit 1 · Numbers", "Unit 2 · Algebra Core", "Unit 3 · Geometry & Data"],
         chapter_titles=["Number Systems", "Linear Equations", "Polynomials", "Quadratic Equations", "Triangles", "Trigonometry", "Statistics", "Probability"],
         sims=["Graphing Lab", "Geometry Board"],
         practicals=[{"title": "Graphing Quadratics Lab", "env": "Maths Lab · v1.0", "status": "In Progress", "steps": "2/5 steps", "due": "Due Fri"}, {"title": "Trig Table Lab", "env": "Maths Lab · v1.0", "status": "Locked", "steps": "Locked", "due": "Complete Ch.5"}],
         assignments=[{"title": "Quadratic Graphs Worksheet", "meta": "2/10 answered", "due": "Due Fri · 2:00 PM", "status": "In Progress"}, {"title": "Linear Equations Set", "meta": "Submitted", "due": "Submitted", "status": "Submitted"}],
         notes=[{"title": "Discriminant", "body": "D > 0 two roots · = 0 one · < 0 none", "updated": "Yesterday"}],
         practice=[{"title": "Quadratics Quiz", "meta": "10 Qs · Ch.4", "status": "In Progress"}, {"title": "Polynomials Check", "meta": "Awaiting review", "status": "Needs Review"}, {"title": "Numbers Final", "meta": "Scored 10/10", "status": "Completed"}]),
    dict(slug="biology", name="Biology", icon="●", color="#16A34A", bg="#F0FDF4", progress=78,
         description="Life up close — explore cells and systems with the virtual microscope.",
         tags=["9 chapters", "4 labs", "Lab A syllabus"],
         unit_titles=["Unit 1 · Cell Basics", "Unit 2 · Body Systems", "Unit 3 · Life & Environment"],
         chapter_titles=["Cell Structure", "Tissues", "Life Processes", "Control & Coordination", "Reproduction", "Heredity & Evolution", "Ecosystems", "Health & Disease"],
         sims=["Virtual Microscope", "Dissection Lab"],
         practicals=[{"title": "Onion Peel Microscopy", "env": "Bio Scope · v3.0", "status": "Completed", "steps": "5/5 steps", "due": "Done"}, {"title": "Pulse & Response Lab", "env": "Bio Scope · v3.0", "status": "In Progress", "steps": "2/5 steps", "due": "Due Mon"}],
         assignments=[{"title": "Cell Diagram Labelling", "meta": "Submitted · on time", "due": "Submitted", "status": "Submitted"}, {"title": "Coordination Worksheet", "meta": "4/8 answered", "due": "Due Mon", "status": "In Progress"}],
         notes=[{"title": "Neuron parts", "body": "Dendrite → axon → synapse", "updated": "2d ago"}],
         practice=[{"title": "Coordination Quiz", "meta": "10 Qs · Ch.4", "status": "In Progress"}, {"title": "Tissues Check", "meta": "Awaiting review", "status": "Needs Review"}, {"title": "Cell Final", "meta": "Scored 9/10", "status": "Completed"}]),
    dict(slug="cs", name="Computer Science", icon="▣", color="#EA580C", bg="#FFF7ED", progress=45,
         description="Think like a programmer — write and run real code, offline.",
         tags=["11 chapters", "6 labs", "Lab A syllabus"],
         unit_titles=["Unit 1 · Python Start", "Unit 2 · Logic Building", "Unit 3 · Projects"],
         chapter_titles=["Python Basics", "Conditionals", "Loops — Part 1", "Loops & Patterns", "Functions", "Lists & Dicts", "Files & Data", "Mini Project"],
         sims=["Code Sandbox", "Logic Visualizer"],
         practicals=[{"title": "Loops Lab — 5 Programs", "env": "Code Lab · v2.0", "status": "In Progress", "steps": "2/5 programs", "due": "Due Mon"}, {"title": "Functions Lab", "env": "Code Lab · v2.0", "status": "Locked", "steps": "Locked", "due": "Complete Ch.5"}],
         assignments=[{"title": "Python Loops — 5 Programs", "meta": "0/5 submitted", "due": "Due Mon · 9:00 AM", "status": "Available"}, {"title": "Conditionals Set", "meta": "Submitted", "due": "Submitted", "status": "Submitted"}],
         notes=[{"title": "Loop recipe", "body": "for i in range(n): … · while cond: …", "updated": "3d ago"}],
         practice=[{"title": "Loops Quiz", "meta": "10 Qs · Ch.4", "status": "Available"}, {"title": "Conditionals Check", "meta": "Awaiting review", "status": "Needs Review"}, {"title": "Basics Final", "meta": "Scored 8/10", "status": "Completed"}]),
]:
    SUBJECT_PAGES[_cfg["slug"]] = _make_subject(**_cfg)


def get_subject_page(slug):
    return SUBJECT_PAGES.get(slug)


def _build_progress_subjects():
    progress_subjects = []
    for subject in SUBJECTS:
        page = SUBJECT_PAGES.get(subject["slug"])
        if page is None:
            progress_subjects.append({**subject, "modules": [{
                "title": "Current learning", "progress": subject["progress"], "chapters": [{
                    "title": subject["current_chapter"], "progress": subject["progress"],
                    "status": "In Progress", "activity": [{"name": "Lesson", "status": "In progress"}]
                }]
            }]})
            continue
        modules = []
        for unit in page["units"]:
            chapters = []
            for chapter in unit["chapters"]:
                if chapter["status"] == "Completed":
                    activity_status = "Completed"
                elif chapter["status"] == "In Progress":
                    activity_status = "In progress"
                else:
                    activity_status = "Not started"
                chapters.append({
                    "title": chapter["title"], "progress": chapter["progress"],
                    "status": chapter["status"], "activity": [
                        {"name": "Lesson", "status": activity_status},
                        {"name": chapter["sim"], "status": activity_status},
                        {"name": chapter["practical"], "status": activity_status},
                        {"name": chapter["quiz"], "status": "Completed" if chapter["status"] == "Completed" else "Not started"},
                    ]
                })
            module_progress = round(sum(chapter["progress"] for chapter in chapters) / len(chapters))
            modules.append({"title": unit["title"], "progress": module_progress, "chapters": chapters})
        progress_subjects.append({**subject, "modules": modules})
    return progress_subjects


PROGRESS_SUBJECTS = _build_progress_subjects()
PROGRESS_NEXT = {
    "kind": "Practical", "title": "Resume Friction Coefficient Lab",
    "detail": "Physics · Step 4 of 6 · your next unfinished activity",
    "reason": "You are already 72% through this lab.", "href": "/practical", "action": "Resume lab"
}
PROGRESS_PENDING = [
    {"kind": "Assignment", "title": "Newton's Laws — Problem Set 4", "detail": "7 of 12 answered · due tomorrow", "href": "/assignments", "action": "Continue"},
    {"kind": "Learning", "title": "Quadratic Equations — Graphing Lab", "detail": "54% complete · 25 min left", "href": "/my-learning", "action": "Resume"},
    {"kind": "Practical", "title": "Loops Lab — 5 Programs", "detail": "2 of 5 programs · due Monday", "href": "/practical", "action": "Open workspace"},
]
PROGRESS_ACTIVITY = [
    {"title": "Friction Simulator", "detail": "Physics · Step 4 of 6", "time": "Yesterday · 4:20 PM", "tone": "info"},
    {"title": "Cell Diagram Labelling", "detail": "Biology · submitted", "time": "Yesterday · 11:05 AM", "tone": "ok"},
    {"title": "Quadratic Graphs", "detail": "Mathematics · 2 of 10 solved", "time": "Mon · 3:40 PM", "tone": "info"},
    {"title": "Titration guide", "detail": "Chemistry · opened", "time": "Mon · 10:15 AM", "tone": "muted"},
]

NAV = [
    {"slug": "home", "label": "Home", "href": "/home", "icon": "home"},
    {"slug": "my-learning", "label": "My Learning", "href": "/my-learning", "icon": "play"},
    {"slug": "subjects", "label": "Subjects", "href": "/subjects", "icon": "grid"},
    {"slug": "tests", "label": "Tests", "href": "/tests", "icon": "clip"},
    {"slug": "practical", "label": "Practical", "href": "/practical", "icon": "flask"},
    {"slug": "assignments", "label": "Assignments", "href": "/assignments", "icon": "clip"},
    {"slug": "sandbox", "label": "Sandbox", "href": "/sandbox", "icon": "code"},
    {"slug": "progress", "label": "Progress", "href": "/progress", "icon": "chart"},
    {"slug": "notes", "label": "Notes", "href": "/notes", "icon": "note"},
    {"slug": "ask-ai", "label": "Ask AI", "href": "/ask-ai", "icon": "user"},
    {"slug": "profile", "label": "Profile", "href": "/profile", "icon": "user"},
    {"slug": "settings", "label": "Settings", "href": "/settings", "icon": "user"},
    {"slug": "help", "label": "Help", "href": "/help", "icon": "user"},
    {"slug": "logout", "label": "Sign out", "href": "/logout", "icon": "user"},
]
