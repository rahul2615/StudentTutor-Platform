"""
AI-powered routes — chatbot, recommendations, and summarisation.
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from app import db
from app.models import Course, Enrollment, CourseMaterial
from app.services import ai_service
from app import limiter

ai_bp = Blueprint("ai", __name__, url_prefix="/ai")


@ai_bp.route("/chat", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
def chat():
    """AJAX chatbot endpoint — accepts JSON { message: str }."""
    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    if not user_message:
        return jsonify({"reply": "Please type a message."}), 400

    # Build a lightweight course catalog for context
    courses = Course.query.filter_by(is_approved=True).all()
    catalog = [
        {"title": c.title, "category": c.category, "description": c.description}
        for c in courses
    ]

    reply = ai_service.chatbot_reply(user_message, course_catalog=catalog)
    return jsonify({"reply": reply})


@ai_bp.route("/recommendations")
@login_required
@limiter.limit("10 per minute")
def recommendations():
    """Return personalised course recommendations as JSON."""
    # Enrolled course titles
    enrollments = Enrollment.query.filter_by(student_id=current_user.id).all()
    enrolled_ids = {e.course_id for e in enrollments}
    enrolled_titles = [e.course.title for e in enrollments if e.course]

    # All approved courses the student isn't enrolled in
    all_approved = Course.query.filter_by(is_approved=True).all()
    candidate_courses = [
        {
            "id": c.id,
            "title": c.title,
            "category": c.category,
            "description": c.description,
            "student_count": c.student_count,
            "average_rating": c.average_rating,
            "tutor": c.tutor.username if c.tutor else "Unknown",
        }
        for c in all_approved
        if c.id not in enrolled_ids
    ]

    recommended_ids = ai_service.recommend_courses(
        enrolled_titles, candidate_courses, limit=5
    )

    # Build response with full card data
    id_map = {c["id"]: c for c in candidate_courses}
    results = [id_map[rid] for rid in recommended_ids if rid in id_map]

    return jsonify({"courses": results})


@ai_bp.route("/summarize/<int:material_id>", methods=["POST"])
@login_required
@limiter.limit("5 per minute")
def summarize(material_id):
    """Trigger AI summarisation of a course material."""
    material = CourseMaterial.query.get_or_404(material_id)
    course = material.course

    # Only the course tutor or an admin may summarise
    if current_user.id != course.tutor_id and current_user.role != "admin":
        return jsonify({"error": "Unauthorized"}), 403

    raw_text = ai_service.extract_file_text(material.file_path)
    if not raw_text:
        return jsonify({"summary": "Could not extract text from this file."}), 200

    summary = ai_service.summarize_text(raw_text)
    return jsonify({"summary": summary})
