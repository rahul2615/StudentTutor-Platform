from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import (
    Course, Enrollment, ForumPost, ForumComment, Message, Review,
    Wishlist, User, LiveSession, Quiz, QuizSubmission, Certificate, UserBadge
)
from app.forms import ForumPostForm, ForumCommentForm, ReviewForm, MessageForm, LiveSessionForm
from app.services.gamification_service import award_forum_points, award_review_points
from app import limiter

engagement_bp = Blueprint("engagement", __name__)


# ── FORUM / Q&A ──────────────────────────────────────────
@engagement_bp.route("/course/<int:course_id>/forum")
@login_required
def course_forum(course_id):
    """View discussion posts for a course."""
    course = Course.query.get_or_404(course_id)
    page = request.args.get('page', 1, type=int)
    posts_pagination = ForumPost.query.filter_by(course_id=course_id).order_by(ForumPost.created_at.desc()).paginate(page=page, per_page=10, error_out=False)
    form = ForumPostForm()
    return render_template("engagement/forum.html", course=course, posts_pagination=posts_pagination, form=form)


@engagement_bp.route("/course/<int:course_id>/forum/new", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def new_forum_post(course_id):
    """Create a new discussion post."""
    course = Course.query.get_or_404(course_id)
    form = ForumPostForm()
    if form.validate_on_submit():
        post = ForumPost(
            course_id=course.id,
            user_id=current_user.id,
            title=form.title.data,
            content=form.content.data
        )
        db.session.add(post)
        db.session.commit()
        award_forum_points(current_user, action="post")
        flash("Discussion post published! +10 Points earned.", "success")
    return redirect(url_for("engagement.course_forum", course_id=course.id))


@engagement_bp.route("/forum/post/<int:post_id>", methods=["GET", "POST"])
@login_required
@limiter.limit("20 per minute")
def view_forum_post(post_id):
    """View post details and reply comments."""
    post = ForumPost.query.get_or_404(post_id)
    comment_form = ForumCommentForm()

    if comment_form.validate_on_submit():
        comment = ForumComment(
            post_id=post.id,
            user_id=current_user.id,
            content=comment_form.content.data
        )
        db.session.add(comment)
        db.session.commit()
        award_forum_points(current_user, action="comment")
        flash("Reply posted! +5 Points earned.", "success")
        return redirect(url_for("engagement.view_forum_post", post_id=post.id))

    return render_template("engagement/forum_post.html", post=post, comment_form=comment_form)


# ── DIRECT MESSAGING ─────────────────────────────────────
@engagement_bp.route("/messages")
@login_required
def inbox():
    """View inbox of conversations."""
    # Find all users with whom current_user has exchanged messages
    sent_receivers = [m.receiver_id for m in Message.query.filter_by(sender_id=current_user.id).all()]
    rec_senders = [m.sender_id for m in Message.query.filter_by(receiver_id=current_user.id).all()]
    user_ids = list(set(sent_receivers + rec_senders))
    chat_users = User.query.filter(User.id.in_(user_ids)).all() if user_ids else []

    return render_template("engagement/inbox.html", chat_users=chat_users)


@engagement_bp.route("/messages/<int:user_id>", methods=["GET", "POST"])
@login_required
@limiter.limit("30 per minute")
def chat_thread(user_id):
    """Chat thread with a specific user."""
    other_user = User.query.get_or_404(user_id)
    form = MessageForm()

    if form.validate_on_submit():
        msg = Message(
            sender_id=current_user.id,
            receiver_id=other_user.id,
            content=form.content.data
        )
        db.session.add(msg)
        db.session.commit()
        return redirect(url_for("engagement.chat_thread", user_id=other_user.id))

    # Mark received messages from this user as read
    Message.query.filter_by(sender_id=other_user.id, receiver_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()

    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == other_user.id)) |
        ((Message.sender_id == other_user.id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()

    return render_template("engagement/chat.html", other_user=other_user, messages=messages, form=form)


# ── CALENDAR VIEW & LIVE SESSIONS ────────────────────────
@engagement_bp.route("/calendar")
@login_required
def calendar_view():
    """Interactive calendar of scheduled live classes."""
    if current_user.role == 'student':
        enrolled_course_ids = [e.course_id for e in current_user.enrollments]
        sessions = LiveSession.query.filter(LiveSession.course_id.in_(enrolled_course_ids)).order_by(LiveSession.scheduled_at.asc()).all() if enrolled_course_ids else []
    elif current_user.role == 'tutor':
        authored_course_ids = [c.id for c in current_user.courses]
        sessions = LiveSession.query.filter(LiveSession.course_id.in_(authored_course_ids)).order_by(LiveSession.scheduled_at.asc()).all() if authored_course_ids else []
    else:
        sessions = LiveSession.query.order_by(LiveSession.scheduled_at.asc()).all()

    return render_template("engagement/calendar.html", sessions=sessions)


@engagement_bp.route("/session/<int:session_id>/edit", methods=["GET", "POST"])
@login_required
def edit_live_session(session_id):
    """Edit a scheduled live session (tutor/admin only)."""
    session_obj = LiveSession.query.get_or_404(session_id)
    course = session_obj.course

    if current_user.id != course.tutor_id and current_user.role != 'admin':
        flash("Unauthorized.", "danger")
        return redirect(url_for("engagement.calendar_view"))

    form = LiveSessionForm(obj=session_obj)

    if form.validate_on_submit():
        session_obj.title = form.title.data
        session_obj.description = form.description.data
        session_obj.scheduled_at = form.scheduled_at.data
        session_obj.duration_minutes = form.duration_minutes.data

        meeting_link = form.meeting_link.data.strip()
        if not meeting_link.startswith('http'):
            meeting_link = f"https://meet.jit.si/EduConnect-{meeting_link.replace(' ', '-')}"
        session_obj.meeting_link = meeting_link

        session_obj.recording_link = form.recording_link.data.strip() if form.recording_link.data else None

        db.session.commit()
        flash(f"Live Session '{session_obj.title}' updated successfully!", "success")
        return redirect(url_for("tutor.course_details", course_id=course.id))

    return render_template("engagement/edit_session.html", form=form, session_obj=session_obj, course=course)


@engagement_bp.route("/session/<int:session_id>/delete", methods=["POST"])
@login_required
def delete_live_session(session_id):
    """Delete a scheduled live session (tutor/admin only)."""
    session_obj = LiveSession.query.get_or_404(session_id)
    course = session_obj.course

    if current_user.id != course.tutor_id and current_user.role != 'admin':
        flash("Unauthorized.", "danger")
        return redirect(url_for("engagement.calendar_view"))

    session_title = session_obj.title
    db.session.delete(session_obj)
    db.session.commit()
    flash(f"Live Session '{session_title}' has been deleted.", "info")

    referrer = request.referrer
    if referrer:
        return redirect(referrer)
    return redirect(url_for("tutor.course_details", course_id=course.id))


# ── REVIEWS & STAR RATINGS ──────────────────────────────
@engagement_bp.route("/course/<int:course_id>/review", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def submit_review(course_id):
    """Submit a course rating and review."""
    course = Course.query.get_or_404(course_id)
    if not current_user.is_enrolled_in(course.id) and current_user.role != 'admin':
        flash("You must be enrolled in this course to leave a review.", "danger")
        return redirect(url_for("tutor.course_details", course_id=course.id))

    form = ReviewForm()
    if form.validate_on_submit():
        existing = Review.query.filter_by(student_id=current_user.id, course_id=course.id).first()
        if existing:
            existing.rating = int(form.rating.data)
            existing.comment = form.comment.data
            flash("Your review has been updated!", "success")
        else:
            review = Review(
                course_id=course.id,
                student_id=current_user.id,
                rating=int(form.rating.data),
                comment=form.comment.data
            )
            db.session.add(review)
            db.session.commit()
            award_review_points(current_user)
            flash("Thank you for your review! +15 Points earned.", "success")
        db.session.commit()

    return redirect(url_for("tutor.course_details", course_id=course.id))


# ── WISHLIST / SAVE-FOR-LATER ────────────────────────────
@engagement_bp.route("/course/<int:course_id>/wishlist", methods=["POST"])
@login_required
def toggle_wishlist(course_id):
    """Toggle course in student wishlist."""
    course = Course.query.get_or_404(course_id)
    existing = Wishlist.query.filter_by(student_id=current_user.id, course_id=course.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash(f"Removed '{course.title}' from your wishlist.", "info")
    else:
        wishlist_item = Wishlist(student_id=current_user.id, course_id=course.id)
        db.session.add(wishlist_item)
        db.session.commit()
        flash(f"Added '{course.title}' to your wishlist!", "success")
    return redirect(request.referrer or url_for("student.courses"))


@engagement_bp.route("/student/wishlist")
@login_required
def view_wishlist():
    """View saved/bookmarked courses."""
    items = Wishlist.query.filter_by(student_id=current_user.id).order_by(Wishlist.created_at.desc()).all()
    return render_template("engagement/wishlist.html", wishlist_items=items)


# ── LEADERBOARD & GAMIFICATION ───────────────────────────
@engagement_bp.route("/leaderboard")
@login_required
def leaderboard():
    """Gamification leaderboard showing top learners by points and badges."""
    top_students = User.query.filter_by(role='student').order_by(User.points.desc()).limit(20).all()
    user_badges = current_user.badges
    return render_template("engagement/leaderboard.html", top_students=top_students, user_badges=user_badges)
