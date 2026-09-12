import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app

client = app.test_client()
credentials = {
    "name": "Lesson Verification",
    "email": "lesson-verification@learncraft.local",
    "password": "VerifyLesson123!",
}
registration = client.post("/auth/register", json=credentials)
if registration.status_code == 409:
    client.post("/auth/login", json={
        "email": credentials["email"],
        "password": credentials["password"],
    })

r = client.get('/subjects/physics/lessons/friction-43')
html = r.data.decode()

checks = {
    'blocks': html.count('data-type=') >= 6,
    'stages': all(s in html for s in ['CONCEPT','EXPLAIN','INTERACT','EXPERIMENT','PRACTICE','REFLECT','APPLY']),
    'widgets': 'id="muSlider"' in html,
    'progress': 'lprog' in html,
    'nav': 'prevBtn' in html and 'nextBtn' in html,
    'check': 'check-opt' in html,
    'code': 'runLessonCode' in html,
    'reflect': 'data-reflect' in html,
    'apply': 'Apply it' in html,
}
print(checks)
raise SystemExit(0 if all(checks.values()) else 1)