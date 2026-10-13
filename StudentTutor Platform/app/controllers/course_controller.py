import os
import uuid
from flask import request, redirect, url_for, render_template, flash, send_from_directory, abort
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from app import db
from app.models import Course, CourseMaterial, Enrollment, Quiz, Question, QuizSubmission, LiveSession, Certificate, User
from app.forms import CourseForm, QuizForm, QuestionForm, LiveSessionForm, ReviewForm
from app.services.gamification_service import award_quiz_points, award_completion

UPLOAD_FOLDER = 'app/static/uploads/'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'png', 'jpg', 'jpeg'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@login_required
def create_course():
    """Handle course creation for tutors."""
    if current_user.role != "tutor":
        flash("Only tutors can create courses!", "danger")
        return redirect(url_for("tutor.dashboard"))

    form = CourseForm()

    if form.validate_on_submit():
        new_course = Course(
            title=form.title.data,
            category=form.category.data,
            level=form.level.data if hasattr(form, 'level') else 'Beginner',
            description=form.description.data,
            prerequisites=form.prerequisites.data,
            duration=form.duration.data,
            price=form.price.data if form.price.data is not None else 0.00,
            currency=form.currency.data if form.currency.data else 'usd',
            tutor_id=current_user.id,
            is_approved=False,
            approval_status='pending'
        )
        db.session.add(new_course)
        db.session.commit()

        if form.file.data and allowed_file(form.file.data.filename):
            filename = secure_filename(form.file.data.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            form.file.data.save(file_path)

            new_material = CourseMaterial(course_id=new_course.id, file_name=filename, file_path=file_path)
            db.session.add(new_material)
            db.session.commit()

        flash("Course created successfully! Sent to admin for approval.", "success")
        return redirect(url_for("tutor.dashboard"))

    return render_template("tutor/create_course.html", form=form)


@login_required
def edit_course(course_id):
    """Handle course editing for authoring tutor or admin."""
    course = Course.query.get_or_404(course_id)

    if current_user.id != course.tutor_id and current_user.role != "admin":
        flash("You are not authorized to edit this course.", "danger")
        return redirect(url_for("tutor.dashboard"))

    form = CourseForm(obj=course)

    if form.validate_on_submit():
        course.title = form.title.data
        course.category = form.category.data
        if hasattr(form, 'level'):
            course.level = form.level.data
        course.description = form.description.data
        course.prerequisites = form.prerequisites.data
        course.duration = form.duration.data
        if hasattr(form, 'price') and form.price.data is not None:
            course.price = form.price.data
        if hasattr(form, 'currency') and form.currency.data:
            course.currency = form.currency.data

        if form.file.data and allowed_file(form.file.data.filename):
            filename = secure_filename(form.file.data.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            form.file.data.save(file_path)

            new_material = CourseMaterial(course_id=course.id, file_name=filename, file_path=file_path)
            db.session.add(new_material)

        db.session.commit()
        flash(f"Course '{course.title}' updated successfully!", "success")
        return redirect(url_for("tutor.course_details", course_id=course.id))

    return render_template("tutor/edit_course.html", form=form, course=course)


@login_required
def delete_course(course_id):
    """Handle course deletion for authoring tutor or admin."""
    course = Course.query.get_or_404(course_id)

    if current_user.id != course.tutor_id and current_user.role != "admin":
        flash("You are not authorized to delete this course.", "danger")
        return redirect(url_for("tutor.dashboard"))

    course_title = course.title
    for material in course.materials:
        if os.path.exists(material.file_path):
            try:
                os.remove(material.file_path)
            except Exception:
                pass

    db.session.delete(course)
    db.session.commit()
    flash(f"Course '{course_title}' has been permanently deleted.", "success")
    return redirect(url_for("tutor.dashboard"))


@login_required
def view_courses():
    """View all approved courses with category, level & search filtering."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    level = request.args.get('level', '').strip()

    query = Course.query.filter_by(is_approved=True)

    if search:
        query = query.filter((Course.title.ilike(f"%{search}%")) | (Course.description.ilike(f"%{search}%")))
    if category and category != 'All':
        query = query.filter_by(category=category)
    if level and level != 'All':
        query = query.filter_by(level=level)

    courses_pagination = query.paginate(page=page, per_page=6, error_out=False)
    return render_template("courses/view_courses.html", courses_pagination=courses_pagination, selected_category=category, selected_level=level, search_query=search)


@login_required
def course_details(course_id):
    """View details for a specific course — with modules, notes, reviews, quizzes, and live sessions."""
    from app.models import StudentNote
    from app.forms import CourseModuleForm, StudentNoteForm

    course = Course.query.get_or_404(course_id)
    enrollment = None
    if current_user.is_authenticated and current_user.role == 'student':
        enrollment = current_user.get_enrollment(course_id)
        if enrollment:
            enrollment.last_accessed_module = "Course Overview"
            db.session.commit()

    user_notes = []
    if current_user.is_authenticated:
        user_notes = StudentNote.query.filter_by(student_id=current_user.id, course_id=course.id).order_by(StudentNote.created_at.desc()).all()

    review_form = ReviewForm()
    module_form = CourseModuleForm()
    note_form = StudentNoteForm()

    return render_template(
        "tutor/course_details.html",
        course=course,
        enrollment=enrollment,
        review_form=review_form,
        module_form=module_form,
        note_form=note_form,
        user_notes=user_notes
    )



@login_required
def download_material(material_id):
    """Secure file download/preview route for course materials."""
    material = CourseMaterial.query.get_or_404(material_id)
    course = material.course

    is_author = (current_user.id == course.tutor_id)
    is_admin = (current_user.role == 'admin')
    is_enrolled = (current_user.role == 'student' and current_user.is_enrolled_in(course.id))

    if not (is_author or is_admin or is_enrolled):
        flash("You must be enrolled in this course to download or view materials.", "danger")
        return redirect(url_for("tutor.course_details", course_id=course.id))

    abs_path = os.path.abspath(material.file_path)
    directory = os.path.dirname(abs_path)
    filename = os.path.basename(abs_path)

    if not os.path.exists(abs_path):
        flash("File not found on server.", "danger")
        return redirect(url_for("tutor.course_details", course_id=course.id))

    return send_from_directory(directory, filename, as_attachment=request.args.get('as_attachment', type=bool, default=False))


# ── QUIZ CONTROLLERS ─────────────────────────────────────
@login_required
def create_quiz(course_id):
    """Create a new quiz for a course."""
    course = Course.query.get_or_404(course_id)
    if current_user.id != course.tutor_id and current_user.role != 'admin':
        flash("Unauthorized.", "danger")
        return redirect(url_for("tutor.course_details", course_id=course.id))

    form = QuizForm()
    if form.validate_on_submit():
        quiz = Quiz(
            course_id=course.id,
            title=form.title.data,
            passing_score=form.passing_score.data
        )
        db.session.add(quiz)
        db.session.commit()
        flash(f"Quiz '{quiz.title}' created! Add questions now.", "success")
        return redirect(url_for("tutor.add_question", quiz_id=quiz.id))

    return render_template("engagement/create_quiz.html", form=form, course=course)


@login_required
def add_question(quiz_id):
    """Add a question to a quiz."""
    quiz = Quiz.query.get_or_404(quiz_id)
    if current_user.id != quiz.course.tutor_id and current_user.role != 'admin':
        flash("Unauthorized.", "danger")
        return redirect(url_for("tutor.dashboard"))

    form = QuestionForm()
    if form.validate_on_submit():
        question = Question(
            quiz_id=quiz.id,
            prompt=form.prompt.data,
            option_a=form.option_a.data,
            option_b=form.option_b.data,
            option_c=form.option_c.data,
            option_d=form.option_d.data,
            correct_option=form.correct_option.data
        )
        db.session.add(question)
        db.session.commit()
        flash("Question added to quiz!", "success")

    return render_template("engagement/add_question.html", form=form, quiz=quiz)


@login_required
def take_quiz(quiz_id):
    """Student takes a quiz and gets auto-graded."""
    quiz = Quiz.query.get_or_404(quiz_id)
    course = quiz.course

    if current_user.role == 'student' and not current_user.is_enrolled_in(course.id):
        flash("You must be enrolled in the course to take quizzes.", "danger")
        return redirect(url_for("tutor.course_details", course_id=course.id))

    if request.method == 'POST':
        questions = quiz.questions
        if not questions:
            flash("This quiz has no questions yet.", "warning")
            return redirect(url_for("tutor.course_details", course_id=course.id))

        correct_count = 0
        for q in questions:
            selected = request.form.get(f"question_{q.id}")
            if selected and selected == q.correct_option:
                correct_count += 1

        score_pct = round((correct_count / len(questions)) * 100, 1)
        passed = score_pct >= quiz.passing_score

        submission = QuizSubmission(
            quiz_id=quiz.id,
            student_id=current_user.id,
            score=score_pct,
            passed=passed
        )
        db.session.add(submission)

        # Gamification via centralized service
        award_quiz_points(current_user, score_pct, passed)

        # Update enrollment progress
        enrollment = current_user.get_enrollment(course.id)
        if enrollment:
            enrollment.progress = min(100, enrollment.progress + 25)
            if enrollment.progress >= 100:
                enrollment.status = 'completed'
                cert = award_completion(current_user, course)
                if cert:
                    flash("Congratulations! You have completed 100% of this course and earned your Certificate of Completion! 🎓", "success")

        db.session.commit()

        if passed:
            flash(f"Quiz Passed! Score: {score_pct}%. +25 Points earned!", "success")
        else:
            flash(f"Quiz Failed. Score: {score_pct}%. Passing score is {quiz.passing_score}%. Try again!", "danger")

        return redirect(url_for("tutor.course_details", course_id=course.id))

    return render_template("engagement/quiz_view.html", quiz=quiz)


# ── LIVE SESSION CONTROLLER ──────────────────────────────
@login_required
def schedule_live_session(course_id):
    """Schedule a new live class session."""
    course = Course.query.get_or_404(course_id)
    if current_user.id != course.tutor_id and current_user.role != 'admin':
        flash("Unauthorized.", "danger")
        return redirect(url_for("tutor.course_details", course_id=course.id))

    form = LiveSessionForm()
    if form.validate_on_submit():
        meeting_link = form.meeting_link.data.strip()
        if not meeting_link.startswith('http'):
            meeting_link = f"https://meet.jit.si/EduConnect-{meeting_link.replace(' ', '-')}"

        recording_link = form.recording_link.data.strip() if hasattr(form, 'recording_link') and form.recording_link.data else None

        session_obj = LiveSession(
            course_id=course.id,
            title=form.title.data,
            description=form.description.data,
            scheduled_at=form.scheduled_at.data,
            duration_minutes=form.duration_minutes.data,
            meeting_link=meeting_link,
            recording_link=recording_link
        )
        db.session.add(session_obj)
        db.session.commit()
        flash(f"Live Session '{session_obj.title}' scheduled successfully!", "success")
        return redirect(url_for("tutor.course_details", course_id=course.id))

    return render_template("engagement/schedule_session.html", form=form, course=course)


# ── MODULE & NOTE CONTROLLERS ──────────────────────────────
@login_required
def add_module(course_id):
    """Add a new module/lesson to a course."""
    from app.models import CourseModule
    from app.forms import CourseModuleForm

    course = Course.query.get_or_404(course_id)
    if current_user.id != course.tutor_id and current_user.role != 'admin':
        flash("Unauthorized.", "danger")
        return redirect(url_for("tutor.course_details", course_id=course.id))

    form = CourseModuleForm()
    if form.validate_on_submit():
        module = CourseModule(
            course_id=course.id,
            title=form.title.data,
            order=form.order.data,
            content=form.content.data
        )
        db.session.add(module)
        db.session.commit()
        flash(f"Module '{module.title}' added to course!", "success")
    return redirect(url_for("tutor.course_details", course_id=course.id))


@login_required
def add_student_note(course_id):
    """Add a study note for a student."""
    from app.models import StudentNote
    from app.forms import StudentNoteForm

    course = Course.query.get_or_404(course_id)
    form = StudentNoteForm()
    if form.validate_on_submit():
        note = StudentNote(
            student_id=current_user.id,
            course_id=course.id,
            content=form.content.data
        )
        db.session.add(note)
        db.session.commit()
        flash("Study note saved!", "success")
    return redirect(url_for("tutor.course_details", course_id=course.id))


@login_required
def delete_student_note(note_id):
    """Delete a student note."""
    from app.models import StudentNote
    note = StudentNote.query.get_or_404(note_id)
    if note.student_id != current_user.id and current_user.role != 'admin':
        flash("Unauthorized.", "danger")
        return redirect(url_for("tutor.dashboard"))
    course_id = note.course_id
    db.session.delete(note)
    db.session.commit()
    flash("Study note deleted.", "info")
    return redirect(url_for("tutor.course_details", course_id=course_id))


# ── CERTIFICATE CONTROLLER ───────────────────────────────
@login_required
def view_certificate(course_id):
    """View / Print Certificate of Completion."""
    course = Course.query.get_or_404(course_id)
    cert = Certificate.query.filter_by(student_id=current_user.id, course_id=course.id).first()

    if not cert:
        enrollment = current_user.get_enrollment(course.id)
        if enrollment and enrollment.progress >= 100:
            cert = Certificate(student_id=current_user.id, course_id=course.id)
            db.session.add(cert)
            db.session.commit()
        else:
            flash("Certificate available only after reaching 100% course progress.", "warning")
            return redirect(url_for("tutor.course_details", course_id=course.id))

    return render_template("student/certificate.html", cert=cert, student=current_user, course=course)

