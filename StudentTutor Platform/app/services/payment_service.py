"""
Centralized Payment Service
---------------------------
Handles Stripe checkout sessions, webhooks, subscription billing,
coupon validation, and tutor earnings balance calculations.
"""

import logging
import io
import base64
import qrcode
from datetime import datetime, timezone
from decimal import Decimal
from flask import current_app, url_for
import stripe
from app import db
from app.models import Course, Enrollment, Payment, Payout, Coupon, Subscription, User

logger = logging.getLogger(__name__)


def generate_upi_qr_code(upi_id, payee_name, amount, currency="INR", note="Course Payment"):
    """Generate a base64 Data URI SVG/PNG QR Code for UPI payments.

    Format: upi://pay?pa={upi_id}&pn={payee_name}&am={amount}&cu={currency}&tn={note}
    """
    if not upi_id:
        return None

    # Format UPI String
    upi_url = f"upi://pay?pa={upi_id.strip()}&pn={payee_name.strip()}&am={amount}&cu={currency}&tn={note}"

    # Generate QR Code image
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(upi_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{img_str}"


def submit_upi_payment(course, student, amount, transaction_ref, payment_proof=None, coupon=None):
    """Submit a UPI payment with UTR reference number for verification."""
    payment = Payment(
        student_id=student.id,
        course_id=course.id,
        amount=Decimal(str(amount)),
        currency=course.currency or "inr",
        gateway="upi_qr",
        status="pending",
        transaction_ref=transaction_ref.strip() if transaction_ref else None,
        payment_proof=payment_proof,
        coupon_id=coupon.id if coupon else None,
    )
    db.session.add(payment)
    db.session.commit()
    logger.info(f"UPI Payment #{payment.id} submitted with UTR '{transaction_ref}' for course #{course.id}")
    return payment


def verify_upi_payment(payment_id, approved=True):
    """Approve or reject a pending UPI payment (by Tutor or Admin)."""
    payment = db.session.get(Payment, payment_id)
    if not payment:
        return None

    if approved:
        payment.status = "completed"
        if payment.coupon_id:
            coupon = db.session.get(Coupon, payment.coupon_id)
            if coupon:
                coupon.times_used += 1
        db.session.commit()
        enrollment = _grant_enrollment(payment)
        logger.info(f"UPI Payment #{payment.id} approved! Enrollment #{enrollment.id if enrollment else 'N/A'} granted.")
        return payment
    else:
        payment.status = "failed"
        db.session.commit()
        logger.warning(f"UPI Payment #{payment.id} rejected by verifier.")
        return payment


def _init_stripe():
    """Configure Stripe API key from Flask config."""
    secret_key = current_app.config.get("STRIPE_SECRET_KEY", "")
    if secret_key:
        stripe.api_key = secret_key
    return bool(secret_key)


def validate_coupon(code, course_id):
    """Validate a coupon code for a given course.

    Returns (is_valid, coupon_or_error_msg, coupon_obj)
    """
    if not code:
        return False, "No coupon code provided.", None

    code_clean = code.strip().upper()
    coupon = Coupon.query.filter_by(code=code_clean).first()

    if not coupon:
        return False, "Invalid coupon code.", None

    if not coupon.is_active:
        return False, "This coupon is no longer active.", None

    now = datetime.now(timezone.utc)
    if coupon.valid_from and coupon.valid_from > now:
        return False, "This coupon is not yet active.", None

    if coupon.valid_until and coupon.valid_until < now:
        return False, "This coupon has expired.", None

    if coupon.max_uses is not None and coupon.times_used >= coupon.max_uses:
        return False, "This coupon has reached its maximum usage limit.", None

    if coupon.course_id is not None and coupon.course_id != course_id:
        return False, "This coupon is not applicable to this course.", None

    return True, "Coupon applied successfully!", coupon


def calculate_discounted_price(original_price, coupon):
    """Compute final price after applying a valid coupon."""
    if not coupon:
        return Decimal(str(original_price))

    price = Decimal(str(original_price))
    val = Decimal(str(coupon.discount_value))

    if coupon.discount_type == "percentage":
        discount = (price * val) / Decimal("100")
        final_price = price - discount
    elif coupon.discount_type == "flat":
        final_price = price - val
    else:
        final_price = price

    return max(Decimal("0.00"), final_price.quantize(Decimal("0.01")))


def create_checkout_session(course, student, coupon=None):
    """Create a Stripe Checkout Session or local test link for course purchase.

    Returns (checkout_url, payment_record)
    """
    original_price = Decimal(str(course.price))
    final_price = calculate_discounted_price(original_price, coupon)

    payment = Payment(
        student_id=student.id,
        course_id=course.id,
        amount=final_price,
        currency=course.currency or "usd",
        gateway="stripe",
        status="pending",
        coupon_id=coupon.id if coupon else None,
    )
    db.session.add(payment)
    db.session.commit()

    has_stripe = _init_stripe()

    if has_stripe:
        try:
            # Convert price to cents for Stripe
            unit_amount = int(final_price * 100)

            # 0 price edge case
            if unit_amount == 0:
                # 100% discount via coupon — complete immediately
                payment.status = "completed"
                if coupon:
                    coupon.times_used += 1
                db.session.commit()
                _grant_enrollment(payment)
                success_url = url_for("payment.payment_success", payment_id=payment.id, _external=True)
                return success_url, payment

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": (course.currency or "usd").lower(),
                        "product_data": {
                            "name": course.title,
                            "description": course.description[:200] if course.description else "",
                        },
                        "unit_amount": unit_amount,
                    },
                    "quantity": 1,
                }],
                mode="payment",
                client_reference_id=str(payment.id),
                customer_email=student.email if student.email else None,
                success_url=url_for("payment.payment_success", _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=url_for("payment.payment_cancel", course_id=course.id, _external=True),
                metadata={
                    "payment_id": str(payment.id),
                    "course_id": str(course.id),
                    "student_id": str(student.id),
                    "coupon_id": str(coupon.id) if coupon else "",
                }
            )

            payment.gateway_checkout_id = session.id
            db.session.commit()
            logger.info(f"Stripe Checkout Session created: {session.id} for Payment #{payment.id}")
            return session.url, payment

        except Exception as e:
            logger.error(f"Stripe Checkout creation failed: {e}")
            db.session.rollback()
            raise e
    else:
        # Development / Sandbox Fallback mode when STRIPE_SECRET_KEY is not configured
        logger.warning("STRIPE_SECRET_KEY not set. Using dev test mode payment URL.")
        test_url = url_for("payment.dev_simulate_payment", payment_id=payment.id, _external=True)
        return test_url, payment


def process_successful_payment(payment_id, gateway_payment_id=None):
    """Mark Payment as completed and grant course enrollment.

    Invoked by webhook or dev simulator.
    """
    payment = db.session.get(Payment, payment_id)
    if not payment:
        logger.error(f"Payment #{payment_id} not found for completion.")
        return None

    if payment.status == "completed":
        logger.info(f"Payment #{payment_id} already completed.")
        return payment

    payment.status = "completed"
    if gateway_payment_id:
        payment.gateway_payment_id = gateway_payment_id

    # Increment coupon usage if used
    if payment.coupon_id:
        coupon = db.session.get(Coupon, payment.coupon_id)
        if coupon:
            coupon.times_used += 1

    db.session.commit()

    # Grant enrollment
    enrollment = _grant_enrollment(payment)
    logger.info(f"Payment #{payment.id} completed. Enrollment #{enrollment.id if enrollment else 'N/A'} granted to student #{payment.student_id}.")
    return payment


def _grant_enrollment(payment):
    """Helper to create an Enrollment for a completed payment."""
    existing = Enrollment.query.filter_by(
        student_id=payment.student_id, course_id=payment.course_id
    ).first()

    if existing:
        if not existing.payment_id:
            existing.payment_id = payment.id
            db.session.commit()
        return existing

    enrollment = Enrollment(
        student_id=payment.student_id,
        course_id=payment.course_id,
        status="active",
        progress=0,
        payment_id=payment.id,
    )
    db.session.add(enrollment)

    # Award enrollment gamification points
    from app.services.gamification_service import award_enrollment_points
    student = db.session.get(User, payment.student_id)
    if student:
        award_enrollment_points(student)

    db.session.commit()
    return enrollment


def verify_stripe_webhook(payload, sig_header):
    """Verify Stripe webhook signature and return the parsed event."""
    webhook_secret = current_app.config.get("STRIPE_WEBHOOK_SECRET", "")
    if not webhook_secret:
        # Dev mode without secret: parse unverified json
        logger.warning("STRIPE_WEBHOOK_SECRET not set. Processing event unverified.")
        return stripe.Event.construct_from(payload, stripe.api_key)

    return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)


def handle_webhook_event(event):
    """Handle dispatched Stripe webhook events."""
    event_type = event.type
    logger.info(f"Received Stripe webhook event: {event_type}")

    if event_type == "checkout.session.completed":
        session = event.data.object
        payment_id_str = session.metadata.get("payment_id") if session.metadata else None

        if payment_id_str:
            payment_id = int(payment_id_str)
            payment_intent = session.get("payment_intent")
            process_successful_payment(payment_id, gateway_payment_id=payment_intent)
        elif session.mode == "subscription":
            # Handle subscription checkout completed
            student_id_str = session.metadata.get("student_id") if session.metadata else None
            plan = session.metadata.get("plan", "monthly")
            if student_id_str:
                student_id = int(student_id_str)
                _activate_subscription(student_id, plan, session.subscription, session.customer)

    elif event_type == "invoice.payment_failed":
        session = event.data.object
        payment_id_str = session.metadata.get("payment_id") if session.metadata else None
        if payment_id_str:
            payment = db.session.get(Payment, int(payment_id_str))
            if payment:
                payment.status = "failed"
                db.session.commit()
                logger.warning(f"Payment #{payment.id} marked as failed.")

    elif event_type == "customer.subscription.deleted":
        sub_obj = event.data.object
        sub_id = sub_obj.id
        sub = Subscription.query.filter_by(gateway_subscription_id=sub_id).first()
        if sub:
            sub.status = "cancelled"
            db.session.commit()
            logger.info(f"Subscription #{sub.id} cancelled via webhook.")


def create_subscription_session(student, plan="monthly"):
    """Create a Stripe subscription checkout session."""
    has_stripe = _init_stripe()
    price_id = (current_app.config.get("STRIPE_MONTHLY_PRICE_ID") if plan == "monthly"
                else current_app.config.get("STRIPE_YEARLY_PRICE_ID"))

    if has_stripe and price_id:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            customer_email=student.email if student.email else None,
            success_url=url_for("payment.subscription_success", _external=True),
            cancel_url=url_for("payment.pricing", _external=True),
            metadata={
                "student_id": str(student.id),
                "plan": plan,
            }
        )
        return session.url
    else:
        # Dev fallback simulation
        _activate_subscription(student.id, plan, f"sub_dev_{student.id}", f"cus_dev_{student.id}")
        return url_for("payment.subscription_success", _external=True)


def _activate_subscription(student_id, plan, sub_id, customer_id):
    """Activate or update a student's subscription."""
    sub = Subscription.query.filter_by(student_id=student_id).first()
    if not sub:
        sub = Subscription(student_id=student_id, plan=plan)
        db.session.add(sub)

    sub.plan = plan
    sub.status = "active"
    sub.started_at = datetime.now(timezone.utc)
    sub.gateway_subscription_id = sub_id
    sub.gateway_customer_id = customer_id
    db.session.commit()
    return sub


def get_tutor_balance(tutor_id):
    """Compute available earnings balance for a tutor.

    Available = Sum(completed payments for tutor's courses) * (1 - platform_fee%) - Sum(paid & pending payouts)
    """
    fee_pct = Decimal(str(current_app.config.get("PLATFORM_FEE_PERCENT", 15)))
    keep_ratio = (Decimal("100") - fee_pct) / Decimal("100")

    # Fetch all completed payments for courses authored by this tutor
    completed_payments = (
        db.session.query(Payment)
        .join(Course, Payment.course_id == Course.id)
        .filter(Course.tutor_id == tutor_id, Payment.status == "completed")
        .all()
    )

    gross_earnings = sum(Decimal(str(p.amount)) for p in completed_payments)
    net_earnings = (gross_earnings * keep_ratio).quantize(Decimal("0.01"))

    # Fetch all payouts (both pending and paid)
    payouts = Payout.query.filter_by(tutor_id=tutor_id).all()
    total_payouts = sum(Decimal(str(p.amount)) for p in payouts)

    available_balance = max(Decimal("0.00"), net_earnings - total_payouts)

    return {
        "gross_earnings": gross_earnings,
        "net_earnings": net_earnings,
        "total_payouts": total_payouts,
        "available_balance": available_balance,
        "platform_fee_percent": fee_pct,
        "completed_sales_count": len(completed_payments),
    }
