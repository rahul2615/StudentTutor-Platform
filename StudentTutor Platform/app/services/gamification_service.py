"""
Centralized Gamification Service
---------------------------------
All point awards, streak tracking, and badge grants flow through here
so the logic is consistent and easy to maintain.
"""

from datetime import datetime, timezone, timedelta
from app import db


def update_login_streak(user):
    """Update the user's login streak based on last_login_date.

    - Same day login: no change
    - Consecutive day: streak_days += 1
    - Gap > 1 day: reset streak to 1
    Always updates last_login_date to now.
    """
    now = datetime.now(timezone.utc)
    today = now.date()

    if user.last_login_date:
        last_date = user.last_login_date.date()
        delta = (today - last_date).days

        if delta == 0:
            # Already logged in today — no streak change
            return user.streak_days
        elif delta == 1:
            # Consecutive day login
            user.streak_days += 1
        else:
            # Streak broken — reset
            user.streak_days = 1
    else:
        # First ever login
        user.streak_days = 1

    user.last_login_date = now
    db.session.commit()

    # Check streak milestone badges
    _check_streak_badges(user)

    return user.streak_days


def award_enrollment_points(user):
    """Award points when a student enrolls in a course. +5 points."""
    user.add_points(5)

    # First enrollment badge
    from app.models import Enrollment
    enrollment_count = Enrollment.query.filter_by(student_id=user.id).count()
    if enrollment_count == 1:
        user.add_badge("First Step", "fa-shoe-prints")


def award_quiz_points(user, score_pct, passed):
    """Award points for quiz completion.

    - Passed: +25 points
    - Perfect score: "Quiz Master" badge
    """
    if passed:
        user.add_points(25)
        if score_pct == 100:
            user.add_badge("Quiz Master", "fa-brain")


def award_forum_points(user, action="post"):
    """Award points for forum activity.

    - New post: +10 points
    - Reply/comment: +5 points
    """
    if action == "post":
        user.add_points(10)
    elif action == "comment":
        user.add_points(5)


def award_review_points(user):
    """Award points for submitting a new course review. +15 points."""
    user.add_points(15)


def award_completion(user, course):
    """Award points and badges when a student completes a course (100% progress).

    - +50 bonus points
    - "Graduate" badge
    - Certificate is issued (if not already)
    """
    from app.models import Certificate

    user.add_points(50)
    user.add_badge("Graduate", "fa-graduation-cap")

    # Issue certificate if not already issued
    cert = Certificate.query.filter_by(student_id=user.id, course_id=course.id).first()
    if not cert:
        cert = Certificate(student_id=user.id, course_id=course.id)
        db.session.add(cert)
        db.session.commit()

    _check_milestone_badges(user)
    return cert


def _check_streak_badges(user):
    """Award badges for streak milestones."""
    if user.streak_days >= 7:
        user.add_badge("Week Warrior", "fa-fire")
    if user.streak_days >= 30:
        user.add_badge("Monthly Master", "fa-fire-alt")
    if user.streak_days >= 100:
        user.add_badge("Century Streak", "fa-meteor")


def _check_milestone_badges(user):
    """Award badges based on total point thresholds."""
    if user.points >= 100:
        user.add_badge("Rising Star", "fa-star")
    if user.points >= 500:
        user.add_badge("Knowledge Seeker", "fa-book-reader")
    if user.points >= 1000:
        user.add_badge("Grand Scholar", "fa-crown")
