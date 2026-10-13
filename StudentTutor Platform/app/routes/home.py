from flask import Blueprint, render_template, redirect, request, session

home = Blueprint("home", __name__)


@home.route("/")
def index():
    from app.models import Course, User, Certificate, db
    from sqlalchemy import func

    total_courses = Course.query.filter_by(is_approved=True).count()
    total_students = User.query.filter_by(role="student").count()
    total_tutors = User.query.filter_by(role="tutor", is_approved=True).count()
    total_certificates = Certificate.query.count()

    # Dynamic featured courses showcase
    featured_courses = (
        Course.query.filter_by(is_approved=True)
        .order_by(Course.id.desc())
        .limit(3)
        .all()
    )

    # Dynamic category breakdown
    category_counts = (
        db.session.query(Course.category, func.count(Course.id))
        .filter(Course.is_approved == True)
        .group_by(Course.category)
        .all()
    )
    categories = {cat: count for cat, count in category_counts}

    return render_template(
        "home.html",
        total_courses=total_courses,
        total_students=total_students,
        total_tutors=total_tutors,
        total_certificates=total_certificates,
        featured_courses=featured_courses,
        categories=categories
    )


@home.route("/set-language/<lang>")
def set_language(lang):
    """Switch the UI language and redirect back."""
    from flask import current_app
    supported = current_app.config.get("SUPPORTED_LANGUAGES", ["en"])
    if lang in supported:
        session["lang"] = lang
    return redirect(request.referrer or "/")


@home.route("/offline")
def offline():
    """Offline fallback page for the service worker."""
    return render_template("offline.html")