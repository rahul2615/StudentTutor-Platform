"""
Centralised AI service powered by Google Gemini.

Every public function gracefully degrades when GEMINI_API_KEY is absent.
"""

import json
import os
import logging

from flask import current_app

logger = logging.getLogger(__name__)

# ── Lazy Gemini client ───────────────────────────────────
_model = None


def _get_model():
    """Return a cached GenerativeModel, or None if the key is missing."""
    global _model
    if _model is not None:
        return _model

    api_key = current_app.config.get("GEMINI_API_KEY", "")
    if not api_key:
        logger.warning("GEMINI_API_KEY not configured — AI features disabled.")
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        _model = genai.GenerativeModel("gemini-2.5-flash")
        return _model
    except Exception as exc:
        logger.error("Failed to initialise Gemini model: %s", exc)
        return None


# ── 1. Chatbot ───────────────────────────────────────────
def chatbot_reply(user_message: str, course_catalog: list[dict] | None = None) -> str:
    """Return a helpful chatbot response for a student query.

    Parameters
    ----------
    user_message : str
        The student's free-text question.
    course_catalog : list[dict] | None
        Summarised list of available courses (title, category, description snippet).
    """
    model = _get_model()
    if model is None:
        return ("I'm currently offline.  Please check back later or contact "
                "support through the Messages page.")

    catalog_block = ""
    if course_catalog:
        catalog_block = "\n\nAvailable courses on the platform:\n"
        for c in course_catalog[:30]:  # cap to keep prompt small
            catalog_block += f"- {c['title']} (Category: {c['category']}): {c['description'][:120]}\n"

    system_prompt = (
        "You are EduConnect AI Assistant — a friendly, concise student-support "
        "chatbot for an online tutoring platform.  Your job is to:\n"
        "• Answer FAQs about how the platform works (enrollment, quizzes, "
        "certificates, live sessions, messaging).\n"
        "• Recommend courses that match the student's goals.\n"
        "• Be encouraging and professional.  Keep answers under 150 words.\n"
        f"{catalog_block}"
    )

    try:
        response = model.generate_content(
            [{"role": "user", "parts": [system_prompt + "\n\nStudent asks: " + user_message]}],
        )
        return response.text.strip()
    except Exception as exc:
        logger.error("Chatbot generation error: %s", exc)
        return "Sorry, I ran into a problem processing your request.  Please try again."


# ── 2. Personalised Recommendations ─────────────────────
def recommend_courses(enrolled_titles: list[str],
                      all_courses: list[dict],
                      limit: int = 5) -> list[int]:
    """Return IDs of recommended courses based on enrollment history.

    Falls back to popularity-based sorting when AI is unavailable.
    """
    model = _get_model()

    # Fallback: return most-enrolled courses the student hasn't taken
    if model is None or not enrolled_titles:
        return [c["id"] for c in all_courses[:limit]]

    enrolled_str = ", ".join(enrolled_titles)
    catalog_str = "\n".join(
        f'ID:{c["id"]} | {c["title"]} | {c["category"]} | {c["description"][:100]}'
        for c in all_courses[:40]
    )

    prompt = (
        "You are a course recommendation engine.  A student is currently enrolled in: "
        f"{enrolled_str}.\n\n"
        f"Available courses they have NOT enrolled in:\n{catalog_str}\n\n"
        f"Return ONLY a JSON array of the top {limit} course IDs that best complement "
        "their learning path.  Example: [3, 7, 12].  No explanation."
    )

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        # Extract JSON array from response
        start = text.index("[")
        end = text.index("]") + 1
        ids = json.loads(text[start:end])
        return [int(i) for i in ids][:limit]
    except Exception as exc:
        logger.error("Recommendation error: %s", exc)
        return [c["id"] for c in all_courses[:limit]]


# ── 3. Material Summarisation ────────────────────────────
def summarize_text(text: str) -> str:
    """Summarise a block of extracted text (from PDF / DOCX)."""
    model = _get_model()
    if model is None:
        return "AI summarisation is currently unavailable."

    if len(text) > 15000:
        text = text[:15000] + "\n[... truncated for length ...]"

    prompt = (
        "Summarise the following course material in clear, student-friendly "
        "bullet points (max 8 bullets).  Keep each bullet under 30 words.\n\n"
        f"{text}"
    )
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as exc:
        logger.error("Summarisation error: %s", exc)
        return "Unable to generate summary at this time."


def extract_file_text(file_path: str) -> str:
    """Extract raw text from a PDF or DOCX file for summarisation."""
    ext = os.path.splitext(file_path)[1].lower()
    abs_path = os.path.abspath(file_path)

    if not os.path.exists(abs_path):
        return ""

    try:
        if ext == ".pdf":
            from PyPDF2 import PdfReader
            reader = PdfReader(abs_path)
            return "\n".join(page.extract_text() or "" for page in reader.pages)

        elif ext in (".docx",):
            from docx import Document
            doc = Document(abs_path)
            return "\n".join(p.text for p in doc.paragraphs)

        elif ext in (".txt", ".md"):
            with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    except Exception as exc:
        logger.error("Text extraction error for %s: %s", file_path, exc)

    return ""


# ── 4. Content Moderation ────────────────────────────────
def moderate_content(text: str, content_type: str = "general") -> dict:
    """Check text for inappropriate or spam content.

    Returns
    -------
    dict  {"flagged": bool, "reason": str, "severity": "low"|"medium"|"high"}
    """
    safe_result = {"flagged": False, "reason": "", "severity": "low"}
    model = _get_model()
    if model is None:
        return safe_result

    prompt = (
        "You are an automated content moderator for an educational platform.  "
        f"Analyse the following {content_type} and decide if it contains "
        "inappropriate, offensive, hateful, violent, sexually explicit, or "
        "spam content.\n\n"
        "Respond in STRICT JSON format ONLY:\n"
        '{"flagged": true/false, "reason": "brief reason", "severity": "low|medium|high"}\n\n'
        f"Content to review:\n{text[:3000]}"
    )

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()
        start = raw.index("{")
        end = raw.rindex("}") + 1
        result = json.loads(raw[start:end])
        return {
            "flagged": bool(result.get("flagged", False)),
            "reason": str(result.get("reason", "")),
            "severity": result.get("severity", "low"),
        }
    except Exception as exc:
        logger.error("Moderation error: %s", exc)
        return safe_result
