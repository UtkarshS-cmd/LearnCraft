import sys  
sys.path.insert(0,'.')  
from app.services.curriculum_pipeline import *  
from pathlib import Path  
c10=Path('data/curriculum/class10')  
pkg=load_class_package(c10)  
print('pkg:',pkg.package_id,'subjects:',len(pkg.subjects))  
g=load_concept_graph(c10)  
print('graph nodes:',len(g['nodes']))  
rm=load_roadmap(c10)  
print('roadmap subjects:',len(rm['subjects']))  
bank=load_question_bank(c10)  
print('questions:',len(bank))  
v=validate_class_package(c10)  
print('valid:',v.get('valid'),'errors:',len(v.get('errors')))  
