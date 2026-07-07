import datetime
import uuid

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class InterviewSession(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=gen_uuid)
    role = Column(String, nullable=False)
    resume_text = Column(Text, nullable=True)
    resume_skills_json = Column(Text, nullable=True)  # JSON string: {skills, technologies, domains}
    status = Column(String, default="in_progress")  # in_progress | completed
    summary_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    qa_pairs = relationship(
        "QAPair", back_populates="session", cascade="all, delete-orphan"
    )


class QAPair(Base):
    __tablename__ = "qa_pairs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    order_index = Column(Integer, nullable=False)
    question = Column(Text, nullable=False)
    source_chunks_json = Column(Text, nullable=True)  # JSON list of retrieved chunk texts/metadata
    answer = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("InterviewSession", back_populates="qa_pairs")
