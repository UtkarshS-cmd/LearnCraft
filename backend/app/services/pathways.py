"""Deterministic pathway catalog (backend data, never hardcoded in templates)."""
from __future__ import annotations

PATHWAYS = {
    "school": {"id": "school", "label": "School", "goal": "Master board syllabus",
                "prerequisites": [], "subjects": ["Science", "Mathematics"],
                "roadmap": ["Foundations", "Board chapters", "Revision", "Board practice"],
                "milestones": ["Syllabus 50%", "Syllabus 100%", "Revision complete"],
                "skills": ["Reading", "Numeracy"], "assessments": ["quiz", "mock test"],
                "projects": []},
    "college": {"id": "college", "label": "College", "goal": "Degree coursework + labs",
                "prerequisites": ["School foundations"], "subjects": ["Computer Science"],
                "roadmap": ["Core courses", "Labs", "Projects", "Internship prep"],
                "milestones": ["Core complete", "Project shipped"],
                "skills": ["Programming"], "assessments": ["quiz", "project"],
                "projects": ["Mini project"]},
    "competitive": {"id": "competitive", "label": "Competitive Exams",
                "goal": "Rank in target exam", "prerequisites": ["NCERT foundations"],
                "subjects": ["Physics", "Chemistry", "Mathematics"],
                "roadmap": ["Syllabus", "PYQ practice", "Mocks", "Revision"],
                "milestones": ["PYQ set 1", "Mock average 70%+"],
                "skills": ["Speed", "Accuracy"], "assessments": ["pyq", "mock test"],
                "projects": []},
    "gate": {"id": "gate", "label": "GATE", "goal": "GATE qualification",
             "prerequisites": ["Engineering basics"], "subjects": ["CS"],
             "roadmap": ["Core subjects", "PYQs", "Test series"],
             "milestones": ["PYQ complete", "Mock ready"],
             "skills": ["Problem solving"], "assessments": ["pyq", "mock test"],
             "projects": []},
    "industrial": {"id": "industrial", "label": "Industrial / Applied",
                "goal": "Job-ready applied skills", "prerequisites": ["Basics"],
                "subjects": ["Programming"], "roadmap": ["Tools", "Projects", "Deployment"],
                "milestones": ["Portfolio project"], "skills": ["Building"],
                "assessments": ["project"], "projects": ["Deployed app"]},
    "research": {"id": "research", "label": "Research", "goal": "Research contribution",
                 "prerequisites": ["Strong fundamentals"], "subjects": [],
                 "roadmap": ["Literature", "Experiment", "Paper"],
                 "milestones": ["Proposal", "Draft"], "skills": ["Analysis"],
                 "assessments": ["project"], "projects": ["Paper draft"]},
    "career": {"id": "career", "label": "Skill / Career",
               "goal": "Career transition",
               "prerequisites": [],
               "roadmap": ["Python", "Mathematics", "Statistics", "ML",
                           "Deep Learning", "Projects", "Deployment", "Interview"],
               "milestones": ["Python done", "ML done", "Portfolio ready"],
               "subjects": ["Python", "ML"], "skills": ["Python", "ML"],
               "assessments": ["quiz", "project", "interview"],
               "projects": ["Portfolio project"]},
    "custom": {"id": "custom", "label": "Custom Goal", "goal": "User-defined target",
               "prerequisites": [], "subjects": [], "roadmap": ["Define", "Learn", "Apply"],
               "milestones": ["Goal defined"], "skills": [],
               "assessments": ["quiz"], "projects": []},
}


def list_pathways() -> list[dict]:
    return [dict(v) for v in PATHWAYS.values()]


def get_pathway(pid: str) -> dict | None:
    return dict(PATHWAYS[pid]) if pid in PATHWAYS else None
