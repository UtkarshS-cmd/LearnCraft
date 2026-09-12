import sys
sys.path.insert(0, '.')
from server import app

c = app.test_client()
r = c.get('/subjects/physics/lessons/friction-43')
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