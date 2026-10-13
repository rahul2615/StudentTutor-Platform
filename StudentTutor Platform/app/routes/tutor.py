from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import Course
from app.decorators import tutor_required

from app.controllers.course_controller import (
    create_course as create_course_func,
    edit_course as edit_course_func,
    delete_course as delete_course_func,
    view_courses,
    course_details,
    download_material,
    create_quiz as create_quiz_func,
    add_question as add_question_func,
    schedule_live_session as schedule_session_func,
    add_module as add_module_func,
)
from app.controllers.earnings_controller import (
    earnings_dashboard as earnings_dashboard_func,
    request_payout as request_payout_func,
    payment_settings as payment_settings_func,
)

tutor_bp = Blueprint("tutor", __name__)


@tutor_bp.route("/dashboard")
@tutor_required
def dashboard():
    """Tutor Dashboard Route."""
    from app.models import Enrollment
    from sqlalchemy import func

    page = request.args.get('page', 1, type=int)
    tutor_courses_pagination = Course.query.filter_by(tutor_id=current_user.id).paginate(page=page, per_page=6, error_out=False)

    # Dynamic KPI stats across ALL tutor courses (not just current page)
    total_courses = Course.query.filter_by(tutor_id=current_user.id).count()
    approved_count = Course.query.filter_by(tutor_id=current_user.id, approval_status='approved').count()
    tutor_course_ids = [c.id for c in Course.query.filter_by(tutor_id=current_user.id).with_entities(Course.id).all()]
    total_students = Enrollment.query.filter(Enrollment.course_id.in_(tutor_course_ids)).count() if tutor_course_ids else 0

    return render_template(
        'tutor/dashboard.html',
        courses_pagination=tutor_courses_pagination,
        total_courses=total_courses,
        approved_count=approved_count,
        total_students=total_students,
    )


@tutor_bp.route("/create_course", methods=["GET", "POST"])
@tutor_required
def handle_create_course():
    """Handles Course Creation for Tutors."""
    return create_course_func()


@tutor_bp.route("/edit_course/<int:course_id>", methods=["GET", "POST"])
@login_required
def handle_edit_course(course_id):
    """Handles Course Editing for Tutors."""
    return edit_course_func(course_id)


@tutor_bp.route("/delete_course/<int:course_id>", methods=["POST"])
@login_required
def handle_delete_course(course_id):
    """Handles Course Deletion for Tutors."""
    return delete_course_func(course_id)


# Course Module Addition
@tutor_bp.route("/course/<int:course_id>/add_module", methods=["POST"])
@login_required
def add_module(course_id):
    return add_module_func(course_id)


# Download/View course material
@tutor_bp.route("/materials/download/<int:material_id>")
@login_required
def handle_download_material(material_id):
    return download_material(material_id)



# Quiz creation & question addition
@tutor_bp.route("/course/<int:course_id>/quiz/create", methods=["GET", "POST"])
@login_required
def handle_create_quiz(course_id):
    return create_quiz_func(course_id)


@tutor_bp.route("/quiz/<int:quiz_id>/add_question", methods=["GET", "POST"])
@login_required
def add_question(quiz_id):
    return add_question_func(quiz_id)


# Schedule Live Session
@tutor_bp.route("/course/<int:course_id>/schedule_session", methods=["GET", "POST"])
@login_required
def schedule_session(course_id):
    return schedule_session_func(course_id)


# View all approved courses
tutor_bp.route("/courses", methods=["GET"])(view_courses)

# View course details
tutor_bp.route("/course/<int:course_id>", methods=["GET"])(course_details)


# Tutor Earnings & Payouts
@tutor_bp.route("/earnings")
@tutor_required
def earnings_dashboard():
    return earnings_dashboard_func()


@tutor_bp.route("/payout/request", methods=["POST"])
@tutor_required
def handle_request_payout():
    return request_payout_func()


@tutor_bp.route("/payment-settings", methods=["GET", "POST"])
@tutor_required
def handle_payment_settings():
    return payment_settings_func()
