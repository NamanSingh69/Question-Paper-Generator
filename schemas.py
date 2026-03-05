from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Union

class GenerateQuestionsRequest(BaseModel):
    filename: str
    subject: str = "General"
    topics: List[str] = []
    difficulty: str = "Medium"
    question_types: List[str] = ["MCQ", "Short Answer"]
    num_questions: int = Field(default=10, ge=1, le=100)
    question_bank: List[Dict[str, Any]] = []

class ExportPaperRequest(BaseModel):
    questions: Union[List[Dict[str, Any]], str]
    format: str = "pdf"
    title: str = "Exam Paper"
    include_answers: Union[bool, str] = False

class ConvertHtmlRequest(BaseModel):
    html: str
