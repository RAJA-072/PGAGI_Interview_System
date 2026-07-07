"""
All LLM calls go through this module so prompts are easy to find/tune in one place.
Uses Groq for every generation step: skill extraction, query construction,
question generation, and final summary.
"""
import json
import re

from groq import Groq

from app.config import GROQ_API_KEY, GROQ_MODEL

_client = Groq(api_key=GROQ_API_KEY)


def _chat(system_prompt: str, user_prompt: str, temperature: float = 0.4) -> str:
    resp = _client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return resp.choices[0].message.content.strip()


def _extract_json(text: str) -> dict:
    """LLMs sometimes wrap JSON in prose or code fences -- pull the JSON object out."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def extract_resume_info(resume_text: str) -> dict:
    """Return {name, skills, technologies, domains, projects} from raw resume text."""
    system = (
        "You extract structured information from resumes. "
        "Respond with ONLY a raw JSON object, no markdown, no explanation."
    )
    user = f"""Resume text:
---
{resume_text[:6000]}
---

Extract the candidate's:
- "name": candidate's full name (string, empty string if not found)
- "skills": general skills (e.g. "data structures", "model evaluation")
- "technologies": specific tools/frameworks/languages (e.g. "Python", "PyTorch")
- "domains": application domains or exposure areas (e.g. "NLP", "computer vision")
- "projects": list of project titles or 1-line descriptions from the resume (e.g. "Sentiment analysis on Twitter data using BERT")

Return ONLY this JSON shape:
{{"name": "...", "skills": ["..."], "technologies": ["..."], "domains": ["..."], "projects": ["..."]}}
If a category is unclear from the resume, return an empty list for it."""
    try:
        raw = _chat(system, user, temperature=0.2)
        data = _extract_json(raw)
        return {
            "name": data.get("name", "") or "",
            "skills": data.get("skills", []) or [],
            "technologies": data.get("technologies", []) or [],
            "domains": data.get("domains", []) or [],
            "projects": data.get("projects", []) or [],
        }
    except Exception:
        # Fail safe: interview can still proceed with generic queries
        return {"name": "", "skills": [], "technologies": [], "domains": [], "projects": []}


def generate_retrieval_queries(role_display: str, resume_info: dict, num_queries: int = 3) -> list[str]:
    """Turn resume signal + role into concrete search queries against the book corpus."""
    system = (
        "You generate short search queries to retrieve relevant textbook passages. "
        "Respond with ONLY a raw JSON array of strings, no markdown, no explanation."
    )
    user = f"""Target role: {role_display}
Candidate skills: {resume_info.get('skills')}
Candidate technologies: {resume_info.get('technologies')}
Candidate domains: {resume_info.get('domains')}

Generate {num_queries} short, specific search queries (3-8 words each) to retrieve
textbook passages that would help construct interview questions well-matched to
this candidate's background and the target role. Favor topics adjacent to or
slightly beyond what the candidate already knows, to probe depth.

Return ONLY a JSON array like: ["query one", "query two", "query three"]"""
    try:
        raw = _chat(system, user, temperature=0.5)
        text = raw.strip()
        text = re.sub(r"^```(json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            text = match.group(0)
        queries = json.loads(text)
        queries = [q for q in queries if isinstance(q, str) and q.strip()]
        return queries[:num_queries] if queries else [role_display]
    except Exception:
        return [role_display]


def generate_question(
    role_display: str,
    resume_info: dict,
    retrieved_chunks: list[dict],
    previous_qa: list[dict],
) -> str:
    """Generate one interview question grounded in retrieved textbook chunks."""
    context_block = "\n\n".join(
        f"[Source: {c['source']}]\n{c['text'][:800]}" for c in retrieved_chunks
    ) or "No specific passage retrieved; ask a foundational question for this role."

    history_block = "\n".join(
        f"Q{i+1}: {qa['question']}\nA{i+1}: {qa.get('answer') or '(not yet answered)'}"
        for i, qa in enumerate(previous_qa)
    ) or "(This is the first question.)"

    projects_block = ", ".join(resume_info.get("projects", [])[:5]) or "(none listed)"

    system = (
        "You are an experienced technical interviewer. "
        "You write ONE short, direct question grounded in the candidate's actual resume and the retrieved context. "
        "Respond with ONLY the question text — no numbering, no preamble, no explanation."
    )
    user = f"""Role: {role_display}
Candidate name: {resume_info.get('name') or 'the candidate'}
Candidate skills: {resume_info.get('skills')}
Candidate technologies: {resume_info.get('technologies')}
Candidate domains: {resume_info.get('domains')}
Candidate projects: {projects_block}

Retrieved textbook context (use as grounding, not as the question itself):
{context_block}

Interview so far:
{history_block}

Write ONE new interview question that:
- Is SHORT and DIRECT (max 15 words) — absolutely no compound or multi-part questions
- References a specific project, skill, or technology from the candidate's resume when possible
- Is grounded in the retrieved context (ask about something the context covers)
- Does not repeat a previous question
- If previous answers were weak, ask a more foundational question; if strong, go one level deeper

Return ONLY the question text. No numbering. No preamble. No bullet points."""
    question = _chat(system, user, temperature=0.6)
    # Strip accidental quotes/numbering the model sometimes adds
    return question.strip().strip('"').lstrip("0123456789. ")


def generate_summary(role_display: str, resume_info: dict, qa_history: list[dict]) -> dict:
    """Produce a structured interview report as a parsed dict with per-question scores."""
    transcript = "\n\n".join(
        f"Q{i+1}: {qa['question']}\nCandidate answer: {qa.get('answer') or '(no answer given)'}"
        for i, qa in enumerate(qa_history)
    )
    system = (
        "You are a strict technical interview evaluator. "
        "Respond with ONLY a raw JSON object, no markdown, no explanation."
    )
    user = f"""Role: {role_display}
Candidate: {resume_info.get('name') or 'the candidate'}
Skills: {resume_info.get('skills')}
Technologies: {resume_info.get('technologies')}
Projects: {resume_info.get('projects')}

Full interview transcript:
{transcript}

Evaluate the interview and return ONLY this JSON (no markdown, no extra text):
{{
  "overall_score": <integer 0-10>,
  "overall_impression": "<2-3 sentence summary of the candidate's overall performance>",
  "questions": [
    {{
      "number": 1,
      "question": "<exact question text>",
      "candidate_answer": "<exact candidate answer, verbatim>",
      "score": <integer 0-10>,
      "verdict": "Strong" | "Adequate" | "Needs Improvement",
      "feedback": "<1-2 sentence specific feedback on this answer>"
    }}
  ],
  "strengths": ["<bullet>", "..."],
  "improvements": ["<bullet>", "..."],
  "next_steps": "<1-2 sentence recommendation for the candidate>"
}}

Score each answer honestly: 8-10 = strong, 5-7 = adequate, 0-4 = needs improvement."""
    try:
        raw = _chat(system, user, temperature=0.3)
        return _extract_json(raw)
    except Exception:
        # Fallback: return minimal structured dict so the API never breaks
        return {
            "overall_score": 0,
            "overall_impression": "Could not generate structured report.",
            "questions": [
                {
                    "number": i + 1,
                    "question": qa["question"],
                    "candidate_answer": qa.get("answer") or "",
                    "score": 0,
                    "verdict": "Adequate",
                    "feedback": "",
                }
                for i, qa in enumerate(qa_history)
            ],
            "strengths": [],
            "improvements": [],
            "next_steps": "",
        }
