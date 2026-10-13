import uuid
from datetime import datetime, timezone
from flask import current_app
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer as Serializer


def _utcnow():
    return datetime.now(timezone.utc)


class User(db.Model, UserMixin):
    """User model for students, tutors, and admins."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=True)
    password = db.Column(db.String(150), nullable=False)
    user_type = db.Column(db.String(50), nullable=False, default="student")  # 'student' or 'tutor'
    is_approved = db.Column(db.Boolean, default=False)  # For tutors
    approval_status = db.Column(db.String(20), nullable=False, default='approved')  # 'pending', 'approved', 'rejected'
    is_email_verified = db.Column(db.Boolean, default=True)  # Email verification status
    role = db.Column(db.String(10), nullable=False, default='student')  # student, tutor, admin
    is_verified = db.Column(db.Boolean, default=False)  # Tutor credential verification badge
    bio = db.Column(db.Text, nullable=True)
    profile_pic = db.Column(db.String(255), nullable=True)
    
    # Tutor Payout / Payment Setup
    upi_id = db.Column(db.String(100), nullable=True)           # e.g., tutor@okicici / phonepe
    qr_code_path = db.Column(db.String(255), nullable=True)      # Path to uploaded QR code image
    bank_name = db.Column(db.String(100), nullable=True)
    account_number = db.Column(db.String(50), nullable=True)
    ifsc_code = db.Column(db.String(20), nullable=True)
    account_holder_name = db.Column(db.String(150), nullable=True)
    
    # Gamification Fields
    points = db.Column(db.Integer, nullable=False, default=0)
    streak_days = db.Column(db.Integer, nullable=False, default=1)
    last_login_date = db.Column(db.DateTime, default=_utcnow)

    # Relationships
    courses = db.relationship("Course", backref="tutor", lazy=True, cascade="all, delete-orphan")
    enrollments = db.relationship("Enrollment", backref="student", lazy=True, cascade="all, delete-orphan")
    badges = db.relationship("UserBadge", backref="user", lazy=True, cascade="all, delete-orphan")
    wishlists = db.relationship("Wishlist", backref="student", lazy=True, cascade="all, delete-orphan")
    reviews = db.relationship("Review", backref="student", lazy=True, cascade="all, delete-orphan")
    student_notes = db.relationship("StudentNote", backref="student", lazy=True, cascade="all, delete-orphan")
    payments = db.relationship("Payment", backref="student", lazy=True, cascade="all, delete-orphan")
    payouts = db.relationship("Payout", backref="tutor", lazy=True, cascade="all, delete-orphan")
    subscription = db.relationship("Subscription", backref="student", uselist=False, lazy=True,
                                   cascade="all, delete-orphan")

    def set_password(self, password):
        """Hash and set the password using scrypt."""
        self.password = generate_password_hash(password, method="scrypt")

    def check_password(self, password):
        """Verify password."""
        return check_password_hash(self.password, password)

    def get_id(self):
        """Return the user ID as a string (required by Flask-Login)."""
        return str(self.id)

    def is_enrolled_in(self, course_id):
        """Check if this student is enrolled in a given course."""
        return Enrollment.query.filter_by(
            student_id=self.id, course_id=course_id
        ).first() is not None

    def is_wishlisted(self, course_id):
        """Check if a course is in user's wishlist."""
        return Wishlist.query.filter_by(
            student_id=self.id, course_id=course_id
        ).first() is not None

    def get_enrollment(self, course_id):
        """Return the Enrollment record for a given course, or None."""
        return Enrollment.query.filter_by(
            student_id=self.id, course_id=course_id
        ).first()

    def has_active_subscription(self):
        """Check if the user has an active subscription."""
        return (self.subscription is not None
                and self.subscription.status == 'active'
                and (self.subscription.current_period_end is None
                     or self.subscription.current_period_end > _utcnow()))

    def can_access_course(self, course_id):
        """Check if user can access a course: free, enrolled, or active subscription."""
        course = db.session.get(Course, course_id)
        if not course:
            return False
        if course.is_free:
            return True
        if self.is_enrolled_in(course_id):
            return True
        if self.has_active_subscription():
            return True
        return False

    def get_reset_token(self, expires_sec=1800):
        """Generate a timed password reset token."""
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id, 'purpose': 'reset_password'})

    def get_verification_token(self):
        """Generate an email verification token."""
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id, 'purpose': 'verify_email'})

    @staticmethod
    def verify_token(token, purpose='reset_password', max_age=1800):
        """Verify a timed token and return the associated user."""
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, max_age=max_age)
            if data.get('purpose') != purpose:
                return None
            user_id = data.get('user_id')
        except Exception:
            return None
        return db.session.get(User, user_id)

    def add_points(self, amount):
        """Add points and handle milestone badges."""
        self.points += amount
        db.session.commit()

    def add_badge(self, badge_name, badge_icon="fa-award"):
        """Grant a badge to the user if not already earned."""
        existing = UserBadge.query.filter_by(user_id=self.id, badge_name=badge_name).first()
        if not existing:
            badge = UserBadge(user_id=self.id, badge_name=badge_name, badge_icon=badge_icon)
            db.session.add(badge)
            db.session.commit()


class Course(db.Model):
    """Course model representing the courses tutors create."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False, default="General")
    level = db.Column(db.String(20), nullable=False, default="Beginner")  # 'Beginner', 'Intermediate', 'Advanced'
    prerequisites = db.Column(db.Text, nullable=True)
    duration = db.Column(db.String(100), nullable=True)
    tutor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    is_approved = db.Column(db.Boolean, default=False)
    approval_status = db.Column(db.String(20), nullable=False, default='pending')
    file_path = db.Column(db.String(255), nullable=True)

    # Monetization fields
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    currency = db.Column(db.String(3), nullable=False, default="usd")

    # Relationships
    modules = db.relationship("CourseModule", backref="course", lazy=True, order_by="CourseModule.order", cascade="all, delete-orphan")
    materials = db.relationship("CourseMaterial", backref="course", lazy=True, cascade="all, delete-orphan")
    enrollments = db.relationship("Enrollment", backref="course", lazy=True, cascade="all, delete-orphan")
    quizzes = db.relationship("Quiz", backref="course", lazy=True, cascade="all, delete-orphan")
    live_sessions = db.relationship("LiveSession", backref="course", lazy=True, cascade="all, delete-orphan")
    forum_posts = db.relationship("ForumPost", backref="course", lazy=True, cascade="all, delete-orphan")
    reviews = db.relationship("Review", backref="course", lazy=True, cascade="all, delete-orphan")
    notes = db.relationship("StudentNote", backref="course", lazy=True, cascade="all, delete-orphan")
    course_payments = db.relationship("Payment", backref="course", lazy=True, cascade="all, delete-orphan")

    @property
    def is_free(self):
        """Check if this course is free (price is 0 or None)."""
        return self.price is None or float(self.price) == 0

    @property
    def student_count(self):
        """Return the number of enrolled students."""
        return len(self.enrollments)

    @property
    def average_rating(self):
        """Compute average star rating from reviews."""
        if not self.reviews:
            return 0.0
        return round(sum(r.rating for r in self.reviews) / len(self.reviews), 1)


class CourseModule(db.Model):
    """Model representing an ordered module or lesson within a course."""
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    order = db.Column(db.Integer, nullable=False, default=1)
    content = db.Column(db.Text, nullable=True)


class StudentNote(db.Model):
    """Model storing a student's personal study notes for a course."""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)


class CourseMaterial(db.Model):
    """Model to store uploaded course materials."""
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)

    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)


class Enrollment(db.Model):
    """Model linking students to courses they have enrolled in."""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=_utcnow)
    status = db.Column(db.String(20), nullable=False, default='active')  # active, completed
    progress = db.Column(db.Integer, nullable=False, default=0)  # 0-100 percent
    last_accessed_at = db.Column(db.DateTime, default=_utcnow)
    last_accessed_module = db.Column(db.String(255), nullable=True, default="Course Materials")
    payment_id = db.Column(db.Integer, db.ForeignKey("payment.id"), nullable=True)  # null for free courses

    __table_args__ = (
        db.UniqueConstraint('student_id', 'course_id', name='unique_enrollment'),
    )


class Quiz(db.Model):
    """Quiz model belonging to a course."""
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    passing_score = db.Column(db.Integer, nullable=False, default=70)  # % score to pass
    created_at = db.Column(db.DateTime, default=_utcnow)

    questions = db.relationship("Question", backref="quiz", lazy=True, cascade="all, delete-orphan")
    submissions = db.relationship("QuizSubmission", backref="quiz", lazy=True, cascade="all, delete-orphan")


class Question(db.Model):
    """Multiple choice question belonging to a Quiz."""
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quiz.id"), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(255), nullable=False)
    option_b = db.Column(db.String(255), nullable=False)
    option_c = db.Column(db.String(255), nullable=False)
    option_d = db.Column(db.String(255), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)  # 'A', 'B', 'C', 'D'


class QuizSubmission(db.Model):
    """Student submission for a quiz."""
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quiz.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    score = db.Column(db.Float, nullable=False, default=0.0)
    passed = db.Column(db.Boolean, nullable=False, default=False)
    submitted_at = db.Column(db.DateTime, default=_utcnow)

    student = db.relationship("User", backref="quiz_submissions")


class Certificate(db.Model):
    """Certificate issued to students upon 100% completion."""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    certificate_code = db.Column(db.String(50), unique=True, nullable=False, default=lambda: f"CERT-{uuid.uuid4().hex[:8].upper()}")
    issued_at = db.Column(db.DateTime, default=_utcnow)

    student = db.relationship("User", backref="certificates")
    course = db.relationship("Course", backref="certificates")


class LiveSession(db.Model):
    """Scheduled live class via Jitsi/Zoom/WebRTC."""
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False, default=60)
    meeting_link = db.Column(db.String(255), nullable=False)
    recording_link = db.Column(db.String(255), nullable=True)



class ForumPost(db.Model):
    """Discussion thread post for a course."""
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)

    author = db.relationship("User", backref="forum_posts")
    comments = db.relationship("ForumComment", backref="post", lazy=True, cascade="all, delete-orphan")


class ForumComment(db.Model):
    """Reply comment on a discussion post."""
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("forum_post.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)

    author = db.relationship("User", backref="forum_comments")


class Message(db.Model):
    """Direct messaging between users (Student ↔ Tutor)."""
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=_utcnow)
    is_read = db.Column(db.Boolean, default=False)

    sender = db.relationship("User", foreign_keys=[sender_id], backref="sent_messages")
    receiver = db.relationship("User", foreign_keys=[receiver_id], backref="received_messages")


class Review(db.Model):
    """Course review and star rating."""
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1 to 5
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'course_id', name='unique_course_review'),
    )


class Wishlist(db.Model):
    """Saved/Bookmarked course for students."""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)

    course = db.relationship("Course", backref="wishlisted_by")

    __table_args__ = (
        db.UniqueConstraint('student_id', 'course_id', name='unique_wishlist_item'),
    )


class UserBadge(db.Model):
    """Badges earned by gamification actions."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    badge_name = db.Column(db.String(100), nullable=False)
    badge_icon = db.Column(db.String(50), nullable=False, default="fa-award")
    earned_at = db.Column(db.DateTime, default=_utcnow)


class AuditLog(db.Model):
    """Immutable log of every admin action for accountability."""
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action = db.Column(db.String(50), nullable=False)        # e.g. approve_tutor, reject_course, delete_user, bulk_approve
    target_type = db.Column(db.String(50), nullable=False)    # 'user' or 'course'
    target_id = db.Column(db.Integer, nullable=False)
    target_label = db.Column(db.String(200), nullable=False)  # human-readable name
    details = db.Column(db.Text, nullable=True)               # optional JSON context
    created_at = db.Column(db.DateTime, default=_utcnow)

    admin = db.relationship("User", backref="audit_actions")


class ContentFlag(db.Model):
    """AI-detected moderation flag for admin review."""
    id = db.Column(db.Integer, primary_key=True)
    flagged_type = db.Column(db.String(50), nullable=False)   # course_description, course_material, forum_post, forum_comment
    flagged_id = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text, nullable=False)               # AI explanation
    severity = db.Column(db.String(20), nullable=False, default="medium")  # low, medium, high
    is_resolved = db.Column(db.Boolean, default=False)
    resolved_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow)

    resolver = db.relationship("User", backref="resolved_flags")


# ══════════════════════════════════════════════════════════
# MONETIZATION MODELS
# ══════════════════════════════════════════════════════════

class Payment(db.Model):
    """Record of a payment for a paid course."""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="usd")
    gateway = db.Column(db.String(20), nullable=False, default="stripe")
    gateway_payment_id = db.Column(db.String(255), nullable=True)     # Stripe PaymentIntent ID
    gateway_checkout_id = db.Column(db.String(255), nullable=True)    # Stripe Checkout Session ID
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending/completed/failed/refunded
    coupon_id = db.Column(db.Integer, db.ForeignKey("coupon.id"), nullable=True)
    transaction_ref = db.Column(db.String(100), nullable=True)  # 12-digit UTR / UPI Ref No.
    payment_proof = db.Column(db.String(255), nullable=True)    # Path to uploaded payment screenshot
    created_at = db.Column(db.DateTime, default=_utcnow)

    coupon = db.relationship("Coupon", backref="payments")


class Payout(db.Model):
    """Tutor payout request."""
    id = db.Column(db.Integer, primary_key=True)
    tutor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending/paid
    requested_at = db.Column(db.DateTime, default=_utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)


class Coupon(db.Model):
    """Discount coupon for courses."""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    discount_type = db.Column(db.String(20), nullable=False)          # "percentage" or "flat"
    discount_value = db.Column(db.Numeric(10, 2), nullable=False)
    max_uses = db.Column(db.Integer, nullable=True)                   # null = unlimited
    times_used = db.Column(db.Integer, nullable=False, default=0)
    valid_from = db.Column(db.DateTime, nullable=True)
    valid_until = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=True)  # null = all courses

    course = db.relationship("Course", backref="coupons")


class Subscription(db.Model):
    """Student subscription for unlimited course access."""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    plan = db.Column(db.String(20), nullable=False)                   # "monthly" or "yearly"
    status = db.Column(db.String(20), nullable=False, default="active")  # active/cancelled/expired
    started_at = db.Column(db.DateTime, default=_utcnow)
    current_period_end = db.Column(db.DateTime, nullable=True)
    gateway_subscription_id = db.Column(db.String(255), nullable=True)
    gateway_customer_id = db.Column(db.String(255), nullable=True)
