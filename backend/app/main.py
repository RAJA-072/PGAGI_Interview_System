from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app import models  # noqa: F401 - ensures models are registered before create_all
from app.routers import interview

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Candidate Screening System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # fine for local/demo use; restrict in real deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(interview.router)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "ai-candidate-screening-system"}
