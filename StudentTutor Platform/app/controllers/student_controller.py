from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import Course, Enrollment, User, db
from app.decorators import student_required
from app.services.gamification_service import award_enrollment_points


@student_required
def dashboard():
    """Student dashboard — show enrolled courses with enrollment metadata and pagination."""
    page = request.args.get('page', 1, type=int)
    enrollments_pagination = (
        Enrollment.query
        .filter_by(student_id=current_user.id)
        .paginate(page=page, per_page=6, error_out=False)
    )

    total_enrolled = Enrollment.query.filter_by(student_id=current_user.id).count()
    completed_count = Enrollment.query.filter_by(student_id=current_user.id).filter(Enrollment.progress >= 100).count()

    return render_template(
        'student/dashboard.html',
        enrollments_pagination=enrollments_pagination,
        total_enrolled=total_enrolled,
        completed_count=completed_count
    )


@student_required
def courses():
    """Browse approved courses with backend search, category filter, level filter, tutor filter, and pagination."""
    if request.method == 'POST':
        course_id = request.form.get('course_id', type=int)
        if course_id:
            return enroll(course_id)

    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    selected_category = request.args.get('category', '').strip()
    selected_level = request.args.get('level', '').strip()
    selected_tutor_id = request.args.get('tutor_id', type=int)

    query = Course.query.filter_by(is_approved=True)

    if search_query:
        query = query.filter((Course.title.ilike(f"%{search_query}%")) | (Course.description.ilike(f"%{search_query}%")))

    if selected_category and selected_category != 'All':
        query = query.filter_by(category=selected_category)

    if selected_level and selected_level != 'All':
        query = query.filter_by(level=selected_level)

    if selected_tutor_id:
        query = query.filter_by(tutor_id=selected_tutor_id)

    courses_pagination = query.paginate(page=page, per_page=6, error_out=False)

    # Fetch tutors who have approved courses for filter dropdown
    tutors = User.query.filter_by(role='tutor', is_approved=True).all()

    return render_template(
        'student/courses.html',
        courses_pagination=courses_pagination,
        search_query=search_query,
        selected_category=selected_category,
        selected_level=selected_level,
        selected_tutor_id=selected_tutor_id,
        tutors=tutors
    )



@student_required
def enroll(course_id):
    """POST: Enroll the current student in a course."""
    course = db.session.get(Course, course_id)
    if not course or not course.is_approved:
        flash("Course not found or not yet approved.", "danger")
        return redirect(url_for("student.courses"))

    # Paid course check: if paid and student has no subscription, redirect to checkout
    if not course.is_free and not current_user.has_active_subscription():
        return redirect(url_for("payment.checkout", course_id=course.id))

    # Check if already enrolled
    existing = Enrollment.query.filter_by(
        student_id=current_user.id,
        course_id=course.id
    ).first()
    if existing:
        flash(f"You are already enrolled in '{course.title}'.", "info")
    else:
        enrollment = Enrollment(
            student_id=current_user.id,
            course_id=course.id,
            status='active',
            progress=0
        )
        db.session.add(enrollment)
        db.session.commit()

        # Gamification: award enrollment points
        award_enrollment_points(current_user)
        flash(f"Successfully enrolled in '{course.title}'! +5 Points earned.", "success")

    return redirect(url_for("student.courses"))


@student_required
def unenroll(course_id):
    """POST: Remove student's enrollment from a course."""
    enrollment = Enrollment.query.filter_by(
        student_id=current_user.id,
        course_id=course_id
    ).first()

    if enrollment:
        course_title = enrollment.course.title
        db.session.delete(enrollment)
        db.session.commit()
        flash(f"You have been unenrolled from '{course_title}'.", "success")
    else:
        flash("You are not enrolled in this course.", "warning")

    return redirect(url_for("student.dashboard"))