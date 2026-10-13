"""
Admin blueprint — dashboard, approvals, analytics, bulk actions, audit log,
content moderation flags.
"""

import json
from datetime import datetime, timezone, timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, extract

from app.models import User, Course, Enrollment, Review, AuditLog, ContentFlag, Coupon, Payout, Payment, db
from app.forms import CouponForm
from app.decorators import admin_required

admin_bp = Blueprint("admin", __name__)


# ── Helpers ──────────────────────────────────────────────
def _log_action(action, target_type, target_id, target_label, details=None):
    """Write an entry to the audit log."""
    entry = AuditLog(
        admin_id=current_user.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_label=target_label,
        details=details,
    )
    db.session.add(entry)


# ══════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════
@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    """Admin dashboard displaying statistics."""
    total_students = User.query.filter_by(role="student").count()
    total_tutors = User.query.filter_by(role="tutor").count()
    pending_tutors = User.query.filter_by(role="tutor", is_approved=False).filter(
        User.approval_status != 'rejected'
    ).count()
    total_courses = Course.query.count()
    pending_courses = Course.query.filter_by(is_approved=False).filter(
        Course.approval_status != 'rejected'
    ).count()
    total_enrollments = Enrollment.query.count()
    unresolved_flags = ContentFlag.query.filter_by(is_resolved=False).count()

    return render_template(
        "admin/dashboard.html",
        total_students=total_students,
        total_tutors=total_tutors,
        pending_tutors=pending_tutors,
        total_courses=total_courses,
        pending_courses=pending_courses,
        total_enrollments=total_enrollments,
        unresolved_flags=unresolved_flags,
    )


# ══════════════════════════════════════════════════════════
# TUTOR APPROVAL
# ══════════════════════════════════════════════════════════
@admin_bp.route("/tutor_approval")
@admin_required
def tutor_approval():
    """Display paginated list of tutors waiting for approval."""
    page = request.args.get('page', 1, type=int)
    tutors_pagination = (
        User.query.filter_by(role="tutor", is_approved=False)
        .filter(User.approval_status != 'rejected')
        .paginate(page=page, per_page=10, error_out=False)
    )
    return render_template("admin/tutor_approval.html", tutors_pagination=tutors_pagination)


@admin_bp.route("/approve_tutor/<int:tutor_id>", methods=["POST"])
@admin_required
def approve_tutor(tutor_id):
    """Approve a tutor."""
    tutor = User.query.get_or_404(tutor_id)
    if tutor.role == "tutor":
        tutor.is_approved = True
        tutor.approval_status = 'approved'
        _log_action("approve_tutor", "user", tutor.id, tutor.username)
        db.session.commit()
        flash(f"Tutor '{tutor.username}' has been approved!", "success")
    return redirect(url_for("admin.tutor_approval"))


@admin_bp.route("/reject_tutor/<int:tutor_id>", methods=["POST"])
@admin_required
def reject_tutor(tutor_id):
    """Reject a tutor's application."""
    tutor = User.query.get_or_404(tutor_id)
    if tutor.role == "tutor":
        tutor.is_approved = False
        tutor.approval_status = 'rejected'
        _log_action("reject_tutor", "user", tutor.id, tutor.username)
        db.session.commit()
        flash(f"Tutor application for '{tutor.username}' has been rejected.", "warning")
    return redirect(url_for("admin.tutor_approval"))


# ══════════════════════════════════════════════════════════
# COURSE APPROVAL
# ══════════════════════════════════════════════════════════
@admin_bp.route("/course_approval")
@admin_required
def course_approval():
    """Display paginated list of courses waiting for approval."""
    page = request.args.get('page', 1, type=int)
    courses_pagination = (
        Course.query.filter_by(is_approved=False)
        .filter(Course.approval_status != 'rejected')
        .paginate(page=page, per_page=10, error_out=False)
    )
    return render_template("admin/course_approval.html", courses_pagination=courses_pagination)


@admin_bp.route("/approve_course/<int:course_id>", methods=["POST"])
@admin_required
def approve_course(course_id):
    """Approve a course."""
    course = Course.query.get_or_404(course_id)
    course.is_approved = True
    course.approval_status = 'approved'
    _log_action("approve_course", "course", course.id, course.title)
    db.session.commit()
    flash(f"Course '{course.title}' has been approved!", "success")
    return redirect(url_for("admin.course_approval"))


@admin_bp.route("/reject_course/<int:course_id>", methods=["POST"])
@admin_required
def reject_course(course_id):
    """Reject a course submission."""
    course = Course.query.get_or_404(course_id)
    course.is_approved = False
    course.approval_status = 'rejected'
    _log_action("reject_course", "course", course.id, course.title)
    db.session.commit()
    flash(f"Course '{course.title}' submission has been rejected.", "warning")
    return redirect(url_for("admin.course_approval"))


# ══════════════════════════════════════════════════════════
# REGISTERED USERS
# ══════════════════════════════════════════════════════════
@admin_bp.route("/registered_users")
@admin_required
def registered_users():
    """Display paginated registered students and tutors."""
    page_students = request.args.get('page_students', 1, type=int)
    page_tutors = request.args.get('page_tutors', 1, type=int)
    students_pagination = User.query.filter_by(role="student").paginate(
        page=page_students, per_page=10, error_out=False
    )
    tutors_pagination = User.query.filter_by(role="tutor", is_approved=True).paginate(
        page=page_tutors, per_page=10, error_out=False
    )
    return render_template(
        "admin/registered_users.html",
        students_pagination=students_pagination,
        tutors_pagination=tutors_pagination,
    )


@admin_bp.route("/toggle_verify/<int:tutor_id>", methods=["POST"])
@admin_required
def toggle_verify_tutor(tutor_id):
    """Toggle verified checkmark badge status for a tutor."""
    tutor = User.query.get_or_404(tutor_id)
    if tutor.role != "tutor":
        flash("Only tutors can be verified.", "warning")
        return redirect(url_for("admin.registered_users"))

    tutor.is_verified = not tutor.is_verified
    status_str = "Verified Badge Granted" if tutor.is_verified else "Verified Badge Revoked"
    _log_action("verify_tutor", "user", tutor.id, tutor.username, details=status_str)
    db.session.commit()
    flash(f"Tutor '{tutor.username}' - {status_str}!", "success")
    return redirect(url_for("admin.registered_users"))


@admin_bp.route("/delete_user/<int:user_id>", methods=["POST"])
@admin_required
def delete_user(user_id):
    """Delete a user from the system."""
    user = User.query.get_or_404(user_id)
    if user.role == "admin":
        flash("Admins cannot be deleted!", "danger")
        return redirect(url_for("admin.registered_users"))

    username = user.username
    _log_action("delete_user", "user", user.id, username)
    db.session.delete(user)
    db.session.commit()
    flash(f"User '{username}' has been deleted!", "success")
    return redirect(url_for("admin.registered_users"))



# ══════════════════════════════════════════════════════════
# BULK ACTIONS
# ══════════════════════════════════════════════════════════
@admin_bp.route("/bulk_action", methods=["POST"])
@admin_required
def bulk_action():
    """Handle bulk approve / reject for tutors or courses."""
    ids = request.form.getlist("selected_ids", type=int)
    action = request.form.get("bulk_action", "")
    entity = request.form.get("entity_type", "")  # 'tutor' or 'course'

    if not ids or not action:
        flash("No items selected.", "warning")
        return redirect(request.referrer or url_for("admin.dashboard"))

    count = 0

    if entity == "tutor":
        for tid in ids:
            tutor = db.session.get(User, tid)
            if tutor and tutor.role == "tutor":
                if action == "approve":
                    tutor.is_approved = True
                    tutor.approval_status = "approved"
                    _log_action("bulk_approve_tutor", "user", tutor.id, tutor.username)
                elif action == "reject":
                    tutor.is_approved = False
                    tutor.approval_status = "rejected"
                    _log_action("bulk_reject_tutor", "user", tutor.id, tutor.username)
                count += 1
        db.session.commit()
        flash(f"Bulk {action}: {count} tutor(s) updated.", "success")
        return redirect(url_for("admin.tutor_approval"))

    elif entity == "course":
        for cid in ids:
            course = db.session.get(Course, cid)
            if course:
                if action == "approve":
                    course.is_approved = True
                    course.approval_status = "approved"
                    _log_action("bulk_approve_course", "course", course.id, course.title)
                elif action == "reject":
                    course.is_approved = False
                    course.approval_status = "rejected"
                    _log_action("bulk_reject_course", "course", course.id, course.title)
                count += 1
        db.session.commit()
        flash(f"Bulk {action}: {count} course(s) updated.", "success")
        return redirect(url_for("admin.course_approval"))

    flash("Invalid bulk action.", "danger")
    return redirect(url_for("admin.dashboard"))


# ══════════════════════════════════════════════════════════
# ANALYTICS DASHBOARD
# ══════════════════════════════════════════════════════════
@admin_bp.route("/analytics")
@admin_required
def analytics():
    """Rich analytics dashboard page."""
    return render_template("admin/analytics.html")


@admin_bp.route("/analytics/data")
@admin_required
def analytics_data():
    """JSON API: supply chart data to the analytics page."""
    now = datetime.now(timezone.utc)

    # ── Enrollment trends (last 12 months) ───────────────
    enrollment_trend = []
    for i in range(11, -1, -1):
        d = now - timedelta(days=30 * i)
        month_start = d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if i > 0:
            next_d = now - timedelta(days=30 * (i - 1))
            month_end = next_d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            month_end = now
        count = Enrollment.query.filter(
            Enrollment.enrolled_at >= month_start,
            Enrollment.enrolled_at < month_end,
        ).count()
        enrollment_trend.append({
            "month": month_start.strftime("%b %Y"),
            "count": count,
        })

    # ── Course category distribution ─────────────────────
    cat_counts = (
        db.session.query(Course.category, func.count(Course.id))
        .filter_by(is_approved=True)
        .group_by(Course.category)
        .all()
    )
    categories = [{"category": c, "count": n} for c, n in cat_counts]

    # ── Top 5 popular courses ────────────────────────────
    top_courses_q = (
        db.session.query(Course.title, func.count(Enrollment.id).label("cnt"))
        .join(Enrollment, Enrollment.course_id == Course.id)
        .group_by(Course.title)
        .order_by(func.count(Enrollment.id).desc())
        .limit(5)
        .all()
    )
    top_courses = [{"title": t, "enrollments": c} for t, c in top_courses_q]

    # ── Tutor performance ────────────────────────────────
    tutors = User.query.filter_by(role="tutor", is_approved=True).all()
    tutor_perf = []
    for t in tutors:
        course_count = Course.query.filter_by(tutor_id=t.id, is_approved=True).count()
        total_students = (
            db.session.query(func.count(Enrollment.id))
            .join(Course, Enrollment.course_id == Course.id)
            .filter(Course.tutor_id == t.id)
            .scalar()
        ) or 0
        avg_rating = (
            db.session.query(func.avg(Review.rating))
            .join(Course, Review.course_id == Course.id)
            .filter(Course.tutor_id == t.id)
            .scalar()
        )
        tutor_perf.append({
            "username": t.username,
            "courses": course_count,
            "students": total_students,
            "avg_rating": round(float(avg_rating), 1) if avg_rating else 0.0,
        })
    tutor_perf.sort(key=lambda x: x["students"], reverse=True)

    return jsonify({
        "enrollment_trend": enrollment_trend,
        "categories": categories,
        "top_courses": top_courses,
        "tutor_performance": tutor_perf,
    })


# ══════════════════════════════════════════════════════════
# AUDIT LOG
# ══════════════════════════════════════════════════════════
@admin_bp.route("/audit_log")
@admin_required
def audit_log():
    """Paginated audit log of admin actions."""
    page = request.args.get("page", 1, type=int)
    action_filter = request.args.get("action", "").strip()

    query = AuditLog.query.order_by(AuditLog.created_at.desc())
    if action_filter:
        query = query.filter(AuditLog.action == action_filter)

    pagination = query.paginate(page=page, per_page=20, error_out=False)

    # Available action types for filter dropdown
    action_types = [r[0] for r in db.session.query(AuditLog.action).distinct().all()]

    return render_template(
        "admin/audit_log.html",
        pagination=pagination,
        action_filter=action_filter,
        action_types=action_types,
    )


# ══════════════════════════════════════════════════════════
# CONTENT MODERATION FLAGS
# ══════════════════════════════════════════════════════════
@admin_bp.route("/content_flags")
@admin_required
def content_flags():
    """View AI-flagged content for review."""
    page = request.args.get("page", 1, type=int)
    show_resolved = request.args.get("resolved", "0") == "1"

    query = ContentFlag.query
    if not show_resolved:
        query = query.filter_by(is_resolved=False)
    query = query.order_by(ContentFlag.created_at.desc())

    pagination = query.paginate(page=page, per_page=15, error_out=False)
    return render_template("admin/content_flags.html", pagination=pagination, show_resolved=show_resolved)


@admin_bp.route("/content_flags/<int:flag_id>/resolve", methods=["POST"])
@admin_required
def resolve_flag(flag_id):
    """Mark a content flag as resolved."""
    flag = ContentFlag.query.get_or_404(flag_id)
    flag.is_resolved = True
    flag.resolved_by = current_user.id
    _log_action("resolve_content_flag", flag.flagged_type, flag.flagged_id, f"Flag #{flag.id}")
    db.session.commit()
    flash("Content flag resolved.", "success")
    return redirect(url_for("admin.content_flags"))


# ══════════════════════════════════════════════════════════
# COUPON MANAGEMENT & PAYOUTS
# ══════════════════════════════════════════════════════════

@admin_bp.route("/coupons")
@admin_required
def manage_coupons():
    """List all coupons."""
    coupons = Coupon.query.order_by(Coupon.id.desc()).all()
    return render_template("admin/coupons.html", coupons=coupons)


@admin_bp.route("/coupons/create", methods=["GET", "POST"])
@admin_required
def create_coupon():
    """Create a new coupon code."""
    form = CouponForm()
    # Populate course_id choices for specific course dropdown
    courses = Course.query.filter_by(is_approved=True).all()
    form.course_id.choices = [(0, 'All Courses')] + [(c.id, c.title) for c in courses]

    if form.validate_on_submit():
        code = form.code.data.strip().upper()
        if Coupon.query.filter_by(code=code).first():
            flash(f"Coupon code '{code}' already exists.", "danger")
            return render_template("admin/coupon_form.html", form=form, title="Create Coupon")

        course_id_val = form.course_id.data if form.course_id.data != 0 else None

        coupon = Coupon(
            code=code,
            discount_type=form.discount_type.data,
            discount_value=form.discount_value.data,
            max_uses=form.max_uses.data,
            valid_from=form.valid_from.data,
            valid_until=form.valid_until.data,
            is_active=True,
            course_id=course_id_val,
        )
        db.session.add(coupon)
        db.session.commit()
        _log_action("create_coupon", "coupon", coupon.id, coupon.code)
        flash(f"Coupon '{coupon.code}' created successfully!", "success")
        return redirect(url_for("admin.manage_coupons"))

    return render_template("admin/coupon_form.html", form=form, title="Create Coupon")


@admin_bp.route("/coupons/<int:coupon_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_coupon(coupon_id):
    """Edit an existing coupon."""
    coupon = Coupon.query.get_or_404(coupon_id)
    form = CouponForm(obj=coupon)
    courses = Course.query.filter_by(is_approved=True).all()
    form.course_id.choices = [(0, 'All Courses')] + [(c.id, c.title) for c in courses]

    if request.method == "GET":
        form.course_id.data = coupon.course_id if coupon.course_id else 0

    if form.validate_on_submit():
        coupon.code = form.code.data.strip().upper()
        coupon.discount_type = form.discount_type.data
        coupon.discount_value = form.discount_value.data
        coupon.max_uses = form.max_uses.data
        coupon.valid_from = form.valid_from.data
        coupon.valid_until = form.valid_until.data
        coupon.course_id = form.course_id.data if form.course_id.data != 0 else None

        db.session.commit()
        _log_action("edit_coupon", "coupon", coupon.id, coupon.code)
        flash(f"Coupon '{coupon.code}' updated successfully!", "success")
        return redirect(url_for("admin.manage_coupons"))

    return render_template("admin/coupon_form.html", form=form, title="Edit Coupon", coupon=coupon)


@admin_bp.route("/coupons/<int:coupon_id>/toggle", methods=["POST"])
@admin_required
def toggle_coupon(coupon_id):
    """Toggle coupon active state."""
    coupon = Coupon.query.get_or_404(coupon_id)
    coupon.is_active = not coupon.is_active
    db.session.commit()
    _log_action("toggle_coupon", "coupon", coupon.id, coupon.code)
    status_str = "activated" if coupon.is_active else "deactivated"
    flash(f"Coupon '{coupon.code}' has been {status_str}.", "info")
    return redirect(url_for("admin.manage_coupons"))


@admin_bp.route("/payouts")
@admin_required
def manage_payouts():
    """List all tutor payout requests."""
    payouts = Payout.query.order_by(Payout.requested_at.desc()).all()
    return render_template("admin/payouts.html", payouts=payouts)


@admin_bp.route("/payouts/<int:payout_id>/mark_paid", methods=["POST"])
@admin_required
def mark_payout_paid(payout_id):
    """Mark a payout request as paid."""
    payout = Payout.query.get_or_404(payout_id)
    if payout.status == "pending":
        payout.status = "paid"
        payout.paid_at = datetime.now(timezone.utc)
        _log_action("mark_payout_paid", "payout", payout.id, f"${payout.amount:.2f} for {payout.tutor.username}")
        db.session.commit()
        flash(f"Payout #{payout.id} for ${payout.amount:.2f} marked as PAID!", "success")
    return redirect(url_for("admin.manage_payouts"))
