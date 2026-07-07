import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session as DBSession

from app.config import MAX_QUESTIONS, ROLE_DISPLAY_NAMES, SUPPORTED_ROLES, TOP_K
from app.database import get_db
from app.models import InterviewSession, QAPair
from app.resume_parser import extract_resume_text
from app.schemas import (
    AnswerRequest,
    NextQuestionResponse,
    QAItem,
    ReportQuestion,
    StartInterviewResponse,
    SummaryResponse,
)
from app import llm, vector_store

router = APIRouter(prefix="/api", tags=["interview"])


@router.get("/roles")
def list_roles():
    """Roles the frontend can offer, with a friendly display name each."""
    return [{"id": r, "name": ROLE_DISPLAY_NAMES.get(r, r)} for r in SUPPORTED_ROLES]


def _build_question_for_session(session: InterviewSession, resume_info: dict, previous_qa: list[dict]) -> tuple[str, list[dict]]:
    """Shared logic: construct queries, retrieve chunks, generate a question."""
    role_display = ROLE_DISPLAY_NAMES.get(session.role, session.role)
    queries = llm.generate_retrieval_queries(role_display, resume_info)
    retrieved = vector_store.query_multi(session.role, queries, top_k=TOP_K)
    question = llm.generate_question(role_display, resume_info, retrieved, previous_qa)
    return question, retrieved


@router.post("/interview/start", response_model=StartInterviewResponse)
async def start_interview(
    role: str = Form(...),
    resume: UploadFile = File(...),
    db: DBSession = Depends(get_db),
):
    if role not in SUPPORTED_ROLES:
        raise HTTPException(status_code=400, detail=f"Unsupported role '{role}'. Choose one of {SUPPORTED_ROLES}")

    if vector_store.collection_is_empty(role):
        raise HTTPException(
            status_code=500,
            detail=f"No knowledge base found for role '{role}'. Run scripts/ingest_books.py first.",
        )

    file_bytes = await resume.read()
    resume_text = extract_resume_text(resume.filename, file_bytes)
    if not resume_text.strip():
        raise HTTPException(status_code=400, detail="Could not extract any text from the uploaded resume.")

    resume_info = llm.extract_resume_info(resume_text)

    session = InterviewSession(
        role=role,
        resume_text=resume_text,
        resume_skills_json=json.dumps(resume_info),
        status="in_progress",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    question, retrieved = _build_question_for_session(session, resume_info, previous_qa=[])

    qa = QAPair(
        session_id=session.id,
        order_index=1,
        question=question,
        source_chunks_json=json.dumps(retrieved),
    )
    db.add(qa)
    db.commit()

    all_skills = resume_info.get("skills", []) + resume_info.get("technologies", []) + resume_info.get("domains", [])

    return StartInterviewResponse(
        session_id=session.id,
        role=role,
        candidate_name=resume_info.get("name", ""),
        extracted_skills=all_skills,
        question_number=1,
        max_questions=MAX_QUESTIONS,
        question=question,
        source_chunks=[c["text"][:300] for c in retrieved],
    )


@router.post("/interview/{session_id}/answer", response_model=NextQuestionResponse)
def submit_answer(session_id: str, body: AnswerRequest, db: DBSession = Depends(get_db)):
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status == "completed":
        raise HTTPException(status_code=400, detail="This interview session has already ended.")

    qa_pairs = (
        db.query(QAPair)
        .filter(QAPair.session_id == session_id)
        .order_by(QAPair.order_index)
        .all()
    )
    current_qa = qa_pairs[-1]
    current_qa.answer = body.answer
    db.commit()

    if len(qa_pairs) >= MAX_QUESTIONS:
        session.status = "completed"
        db.commit()
        return NextQuestionResponse(
            session_id=session_id,
            question_number=len(qa_pairs),
            max_questions=MAX_QUESTIONS,
            question=None,
            source_chunks=[],
            done=True,
        )

    resume_info = json.loads(session.resume_skills_json or "{}")
    previous_qa = [{"question": qa.question, "answer": qa.answer} for qa in qa_pairs]

    question, retrieved = _build_question_for_session(session, resume_info, previous_qa)

    next_order = len(qa_pairs) + 1
    new_qa = QAPair(
        session_id=session_id,
        order_index=next_order,
        question=question,
        source_chunks_json=json.dumps(retrieved),
    )
    db.add(new_qa)
    db.commit()

    return NextQuestionResponse(
        session_id=session_id,
        question_number=next_order,
        max_questions=MAX_QUESTIONS,
        question=question,
        source_chunks=[c["text"][:300] for c in retrieved],
        done=False,
    )


@router.get("/interview/{session_id}/summary", response_model=SummaryResponse)
def get_summary(session_id: str, db: DBSession = Depends(get_db)):
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    qa_pairs = (
        db.query(QAPair)
        .filter(QAPair.session_id == session_id)
        .order_by(QAPair.order_index)
        .all()
    )
    qa_history = [{"question": qa.question, "answer": qa.answer} for qa in qa_pairs]
    resume_info = json.loads(session.resume_skills_json or "{}")
    role_display = ROLE_DISPLAY_NAMES.get(session.role, session.role)

    if not session.summary_text:
        report_dict = llm.generate_summary(role_display, resume_info, qa_history)
        session.summary_text = json.dumps(report_dict)
        db.commit()

    try:
        report = json.loads(session.summary_text)
    except Exception:
        report = {}

    all_skills = resume_info.get("skills", []) + resume_info.get("technologies", []) + resume_info.get("domains", [])

    report_questions = [
        ReportQuestion(
            number=q.get("number", i + 1),
            question=q.get("question", ""),
            candidate_answer=q.get("candidate_answer", ""),
            score=int(q.get("score", 0)),
            verdict=q.get("verdict", "Adequate"),
            feedback=q.get("feedback", ""),
        )
        for i, q in enumerate(report.get("questions", []))
    ]

    return SummaryResponse(
        session_id=session_id,
        role=session.role,
        candidate_name=resume_info.get("name", ""),
        extracted_skills=all_skills,
        qa_history=[
            QAItem(order_index=qa.order_index, question=qa.question, answer=qa.answer)
            for qa in qa_pairs
        ],
        summary=report.get("overall_impression", ""),
        overall_score=int(report.get("overall_score", 0)),
        overall_impression=report.get("overall_impression", ""),
        report_questions=report_questions,
        strengths=report.get("strengths", []),
        improvements=report.get("improvements", []),
        next_steps=report.get("next_steps", ""),
    )
