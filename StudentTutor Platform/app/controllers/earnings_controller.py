"""
Tutor Earnings Controller — handles earnings calculation, sales history, and payout requests.
"""

from decimal import Decimal
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app import db
from app.models import Course, Payment, Payout
from app.decorators import tutor_required
from app.services.payment_service import get_tutor_balance


@tutor_required
def earnings_dashboard():
    """Tutor Earnings & Payouts Dashboard."""
    balance_info = get_tutor_balance(current_user.id)

    # Detailed sales table: completed payments for tutor's courses
    sales = (
        db.session.query(Payment)
        .join(Course, Payment.course_id == Course.id)
        .filter(Course.tutor_id == current_user.id)
        .order_by(Payment.created_at.desc())
        .all()
    )

    # Payout history table
    payout_history = (
        Payout.query
        .filter_by(tutor_id=current_user.id)
        .order_by(Payout.requested_at.desc())
        .all()
    )

    return render_template(
        "tutor/earnings.html",
        balance_info=balance_info,
        sales=sales,
        payout_history=payout_history,
    )


@tutor_required
def request_payout():
    """POST: Request a payout for the available balance."""
    balance_info = get_tutor_balance(current_user.id)
    available = balance_info["available_balance"]

    if available <= 0:
        flash("You have no available balance to request a payout.", "warning")
        return redirect(url_for("tutor.earnings_dashboard"))

    payout = Payout(
        tutor_id=current_user.id,
        amount=available,
        status="pending"
    )
    db.session.add(payout)
    db.session.commit()

    flash(f"Payout request for ${available:.2f} submitted successfully! Administration will process your request.", "success")
    return redirect(url_for("tutor.earnings_dashboard"))


@tutor_required
def payment_settings():
    """Manage Tutor Payout & Payment Settings (UPI ID, QR Code, Bank Account)."""
    from app.forms import TutorPaymentSettingsForm
    from werkzeug.utils import secure_filename
    import os

    form = TutorPaymentSettingsForm(obj=current_user)

    if form.validate_on_submit():
        current_user.upi_id = form.upi_id.data.strip() if form.upi_id.data else None
        current_user.bank_name = form.bank_name.data.strip() if form.bank_name.data else None
        current_user.account_number = form.account_number.data.strip() if form.account_number.data else None
        current_user.ifsc_code = form.ifsc_code.data.strip().upper() if form.ifsc_code.data else None
        current_user.account_holder_name = form.account_holder_name.data.strip() if form.account_holder_name.data else None

        if form.qr_code.data:
            folder = os.path.join("app", "static", "uploads", "qr_codes")
            os.makedirs(folder, exist_ok=True)
            filename = f"qr_tutor_{current_user.id}_" + secure_filename(form.qr_code.data.filename)
            filepath = os.path.join(folder, filename)
            form.qr_code.data.save(filepath)
            current_user.qr_code_path = f"uploads/qr_codes/{filename}"

        db.session.commit()
        flash("Your payment and payout settings have been updated successfully!", "success")
        return redirect(url_for("tutor.earnings_dashboard"))

    return render_template("tutor/payment_settings.html", form=form)
