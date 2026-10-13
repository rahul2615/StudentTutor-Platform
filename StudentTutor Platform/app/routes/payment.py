"""
Payment Blueprint — handles checkout, webhooks, coupons, and subscription routes.
"""

import logging
from decimal import Decimal
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user

from app import db
from app.models import Course, Payment, Coupon, Subscription, Enrollment
from app.forms import CouponApplyForm, UpiPaymentForm
from app.services import payment_service
from app.decorators import student_required

logger = logging.getLogger(__name__)

payment_bp = Blueprint("payment", __name__, url_prefix="/payment")


@payment_bp.route("/checkout/<int:course_id>", methods=["GET", "POST"])
@student_required
def checkout(course_id):
    """Checkout page for purchasing a paid course."""
    course = Course.query.get_or_404(course_id)

    if not course.is_approved:
        flash("Course is not available for purchase.", "danger")
        return redirect(url_for("student.courses"))

    # Free course fallback — direct enrollment
    if course.is_free:
        return redirect(url_for("student.enroll", course_id=course.id))

    # Check if student already enrolled or has subscription access
    if current_user.can_access_course(course.id):
        flash("You already have full access to this course!", "info")
        return redirect(url_for("tutor.course_details", course_id=course.id))

    form = CouponApplyForm()
    applied_coupon = None
    discount_msg = None
    original_price = Decimal(str(course.price))
    final_price = original_price

    code = request.args.get("coupon_code", "").strip() or (form.code.data.strip() if form.validate_on_submit() else "")
    if code:
        is_valid, msg, coupon_obj = payment_service.validate_coupon(code, course.id)
        if is_valid:
            applied_coupon = coupon_obj
            final_price = payment_service.calculate_discounted_price(original_price, applied_coupon)
            discount_msg = f"Coupon '{applied_coupon.code}' applied! Saved {original_price - final_price:.2f} {course.currency.upper()}."
        else:
            flash(msg, "warning")

    if request.method == "POST" and "confirm_payment" in request.form:
        try:
            checkout_url, payment = payment_service.create_checkout_session(
                course, current_user, coupon=applied_coupon
            )
            return redirect(checkout_url)
        except Exception as e:
            logger.error(f"Error creating checkout session: {e}")
            flash("Could not initialize payment gateway. Please try again later.", "danger")

    # Generate dynamic UPI QR Code if tutor has upi_id configured
    tutor_upi = course.tutor.upi_id if course.tutor else None
    upi_qr_data_uri = payment_service.generate_upi_qr_code(
        upi_id=tutor_upi or "edusupport@upi",
        payee_name=course.tutor.username if course.tutor else "EduConnect",
        amount=final_price,
        currency=(course.currency or "INR").upper(),
        note=f"Course_{course.id}"
    )

    upi_form = UpiPaymentForm()

    return render_template(
        "payment/checkout.html",
        course=course,
        form=form,
        upi_form=upi_form,
        applied_coupon=applied_coupon,
        discount_msg=discount_msg,
        original_price=original_price,
        final_price=final_price,
        tutor_upi=tutor_upi,
        upi_qr_data_uri=upi_qr_data_uri,
        stripe_pub_key=current_app.config.get("STRIPE_PUBLISHABLE_KEY", ""),
    )


@payment_bp.route("/success")
@login_required
def payment_success():
    """Payment success landing page."""
    payment_id = request.args.get("payment_id", type=int)
    session_id = request.args.get("session_id", "").strip()

    payment = None
    if payment_id:
        payment = db.session.get(Payment, payment_id)
    elif session_id:
        payment = Payment.query.filter_by(gateway_checkout_id=session_id).first()

    return render_template("payment/success.html", payment=payment)


@payment_bp.route("/subscription_success")
@login_required
def subscription_success():
    """Subscription success landing page."""
    flash("Your subscription has been activated successfully! You now have pass access to all courses.", "success")
    return redirect(url_for("student.courses"))


@payment_bp.route("/cancel/<int:course_id>")
@login_required
def payment_cancel(course_id):
    """Payment cancellation page."""
    course = Course.query.get_or_404(course_id)
    flash("Payment process was cancelled.", "info")
    return render_template("payment/cancel.html", course=course)


@payment_bp.route("/dev_simulate/<int:payment_id>", methods=["GET", "POST"])
@login_required
def dev_simulate_payment(payment_id):
    """Sandbox simulation page for testing payments when no real Stripe API keys are configured."""
    payment = Payment.query.get_or_404(payment_id)
    if payment.student_id != current_user.id and current_user.role != "admin":
        flash("Unauthorized", "danger")
        return redirect(url_for("student.dashboard"))

    if request.method == "POST":
        action = request.form.get("action", "success")
        if action == "success":
            payment_service.process_successful_payment(payment.id, gateway_payment_id=f"sim_pay_{payment.id}")
            flash("Sandbox Payment Successful! Course enrollment granted.", "success")
            return redirect(url_for("payment.payment_success", payment_id=payment.id))
        else:
            payment.status = "failed"
            db.session.commit()
            flash("Sandbox Payment Simulated Failure.", "danger")
            return redirect(url_for("payment.payment_cancel", course_id=payment.course_id))

    return render_template("payment/dev_simulate.html", payment=payment)


@payment_bp.route("/webhook", methods=["POST"])
def webhook():
    """Stripe Webhook Listener (CSRF Exempt)."""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature", None)

    try:
        event = payment_service.verify_stripe_webhook(payload, sig_header)
        payment_service.handle_webhook_event(event)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 400


@payment_bp.route("/pricing")
def pricing():
    """Subscription & Pricing comparison page."""
    return render_template("payment/pricing.html")


@payment_bp.route("/subscribe/<plan>", methods=["POST"])
@student_required
def subscribe(plan):
    """Initiate a subscription checkout session (monthly or yearly)."""
    if plan not in ["monthly", "yearly"]:
        flash("Invalid subscription plan.", "danger")
        return redirect(url_for("payment.pricing"))

    try:
        checkout_url = payment_service.create_subscription_session(current_user, plan)
        return redirect(checkout_url)
    except Exception as e:
        logger.error(f"Subscription creation error: {e}")
        flash("Could not initiate subscription checkout.", "danger")
        return redirect(url_for("payment.pricing"))


@payment_bp.route("/pay-upi/<int:course_id>", methods=["POST"])
@student_required
def pay_upi(course_id):
    """Process UPI UTR submission for a course purchase."""
    course = Course.query.get_or_404(course_id)
    upi_form = UpiPaymentForm()

    code = request.form.get("coupon_code", "").strip()
    applied_coupon = None
    original_price = Decimal(str(course.price))
    final_price = original_price

    if code:
        is_valid, msg, coupon_obj = payment_service.validate_coupon(code, course.id)
        if is_valid:
            applied_coupon = coupon_obj
            final_price = payment_service.calculate_discounted_price(original_price, applied_coupon)

    if upi_form.validate_on_submit():
        utr_number = upi_form.transaction_ref.data.strip()
        proof_path = None

        if upi_form.payment_proof.data:
            from werkzeug.utils import secure_filename
            import os
            folder = os.path.join("app", "static", "uploads", "payment_proofs")
            os.makedirs(folder, exist_ok=True)
            filename = f"proof_{current_user.id}_{course_id}_" + secure_filename(upi_form.payment_proof.data.filename)
            filepath = os.path.join(folder, filename)
            upi_form.payment_proof.data.save(filepath)
            proof_path = f"uploads/payment_proofs/{filename}"

        payment = payment_service.submit_upi_payment(
            course=course,
            student=current_user,
            amount=final_price,
            transaction_ref=utr_number,
            payment_proof=proof_path,
            coupon=applied_coupon,
        )

        flash(f"UPI Payment submitted (UTR: {utr_number})! Pending tutor/admin verification.", "info")
        return redirect(url_for("payment.payment_success", payment_id=payment.id))

    flash("Invalid UTR number provided. Please enter a valid 12-digit UTR.", "danger")
    return redirect(url_for("payment.checkout", course_id=course.id))


@payment_bp.route("/verify-upi/<int:payment_id>", methods=["POST"])
@login_required
def verify_upi(payment_id):
    """Approve or reject a pending UPI payment submission."""
    payment = Payment.query.get_or_404(payment_id)

    # Only course tutor or admin can verify payments
    if current_user.id != payment.course.tutor_id and current_user.role != "admin":
        flash("Unauthorized to verify this payment.", "danger")
        return redirect(url_for("student.dashboard"))

    action = request.form.get("action", "approve")
    if action == "approve":
        payment_service.verify_upi_payment(payment.id, approved=True)
        flash(f"UPI Payment #{payment.id} APPROVED! Course enrollment activated for {payment.student.username}.", "success")
    else:
        payment_service.verify_upi_payment(payment.id, approved=False)
        flash(f"UPI Payment #{payment.id} rejected.", "warning")

    if current_user.role == "admin":
        return redirect(url_for("admin.manage_payouts"))
    return redirect(url_for("tutor.earnings_dashboard"))
