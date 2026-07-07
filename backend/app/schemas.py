from typing import List, Optional
from pydantic import BaseModel


class StartInterviewResponse(BaseModel):
    session_id: str
    role: str
    candidate_name: str = ""
    extracted_skills: List[str]
    question_number: int
    max_questions: int
    question: str
    source_chunks: List[str]
    done: bool = False


class AnswerRequest(BaseModel):
    answer: str


class NextQuestionResponse(BaseModel):
    session_id: str
    question_number: int
    max_questions: int
    question: Optional[str] = None
    source_chunks: List[str] = []
    done: bool = False


class QAItem(BaseModel):
    order_index: int
    question: str
    answer: Optional[str]


class ReportQuestion(BaseModel):
    number: int
    question: str
    candidate_answer: str
    score: int
    verdict: str  # Strong | Adequate | Needs Improvement
    feedback: str


class SummaryResponse(BaseModel):
    session_id: str
    role: str
    candidate_name: str = ""
    extracted_skills: List[str]
    qa_history: List[QAItem]
    summary: str  # kept for backward compat
    overall_score: int = 0
    overall_impression: str = ""
    report_questions: List[ReportQuestion] = []
    strengths: List[str] = []
    improvements: List[str] = []
    next_steps: str = ""
