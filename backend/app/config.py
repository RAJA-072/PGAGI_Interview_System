import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
CHROMA_DB_DIR = os.getenv("CHROMA_DB_DIR", "./chroma_db")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./interview_system.db")
BOOKS_DIR = os.getenv("BOOKS_DIR", "./data/books")
MAX_QUESTIONS = int(os.getenv("MAX_QUESTIONS", "5"))
TOP_K = int(os.getenv("TOP_K", "3"))

# Roles supported out of the box. Each must have a matching folder under BOOKS_DIR.
SUPPORTED_ROLES = ["ai_ml", "data_science"]

ROLE_DISPLAY_NAMES = {
    "ai_ml": "AI/ML Engineer",
    "data_science": "Data Science / Applied ML Engineer",
}
