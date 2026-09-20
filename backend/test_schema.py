from pathlib import Path
import sys
sys.path.insert(0, '.')
from app.schemas.curriculum import Difficulty, QuestionType, CompetencyCategory, Board
print("Enums imported successfully")
print(f"Difficulty.EASY = {Difficulty.EASY}")
print(f"QuestionType.MCQ = {QuestionType.MCQ}")
print(f"CompetencyCategory.APPLY = {CompetencyCategory.APPLY}")
