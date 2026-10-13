import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from app.models import User, db
from app.forms import LoginForm, RegisterForm, EditProfileForm, ForgotPasswordForm, ResetPasswordForm
from app.services.gamification_service import update_login_streak
from app import limiter

auth_bp = Blueprint("auth", __name__)
AVATAR_UPLOAD_FOLDER = 'app/static/uploads/avatars/'
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    """Handles user login for students, tutors, and admins."""
    if current_user.is_authenticated:
        flash("You are already logged in!", "info")
        return redirect(url_for(f"{current_user.role}.dashboard"))

    form = LoginForm()

    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            if user.role == "tutor" and not user.is_approved:
                if user.approval_status == 'rejected':
                    flash("Your tutor account application was rejected by administration.", "danger")
                else:
                    flash("Your tutor account is pending approval by administration.", "warning")
                return redirect(url_for("auth.login"))

            if not user.is_email_verified and user.role != 'admin':
                token = user.get_verification_token()
                verify_url = url_for('auth.verify_email', token=token, _external=True)
                flash(f"Please verify your email to log in. Dev Link: <a href='{verify_url}' class='alert-link'>Verify Email Here</a>", "warning")
                return redirect(url_for("auth.login"))

            login_user(user)
            session["user_id"] = user.id
            session["role"] = user.role.lower()
            session.permanent = True

            # Track login streak via gamification service
            streak = update_login_streak(user)
            flash("Login successful!", "success")
            if streak > 1:
                flash(f"🔥 Login streak: {streak} days!", "info")

            return redirect(url_for(f"{user.role}.dashboard"))

        flash("Invalid credentials. Try again.", "danger")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    """Handles user logout and clears session."""
    logout_user()
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def register():
    """Handles user registration with optional email & verification link."""
    form = RegisterForm()

    if form.validate_on_submit():
        username = form.username.data.strip()
        email = form.email.data.strip() if form.email.data else None
        password = form.password.data
        role = form.role.data.lower()

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Username already taken. Please choose another.", "danger")
            return redirect(url_for("auth.register"))

        if email:
            existing_email = User.query.filter_by(email=email).first()
            if existing_email:
                flash("Email already registered. Please login or reset password.", "danger")
                return redirect(url_for("auth.register"))

        hashed_password = generate_password_hash(password, method="scrypt")

        # Students auto-verify if no email entered, or require email verification if provided
        is_verified = False if (email and role == 'student') else True

        new_user = User(
            username=username,
            email=email,
            password=hashed_password,
            role=role,
            user_type=role,
            is_approved=True if role == "student" else False,
            approval_status='approved' if role == "student" else 'pending',
            is_email_verified=is_verified
        )

        db.session.add(new_user)
        db.session.commit()

        if not is_verified:
            token = new_user.get_verification_token()
            verify_url = url_for('auth.verify_email', token=token, _external=True)
            flash(f"Registration successful! Please verify your email. Dev link: <a href='{verify_url}' class='alert-link'>Click here to verify</a>", "info")
        else:
            if role == "tutor":
                flash("Registration successful! Your tutor account is pending admin approval.", "info")
            else:
                flash("Registration successful! You can now log in.", "success")

        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/verify_email/<token>")
def verify_email(token):
    """Verify email via token."""
    user = User.verify_token(token, purpose='verify_email', max_age=86400)
    if not user:
        flash("The email verification link is invalid or has expired.", "danger")
        return redirect(url_for("auth.login"))

    user.is_email_verified = True
    db.session.commit()
    flash("Your email has been verified! You can now log in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot_password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def forgot_password():
    """Request password reset link."""
    if current_user.is_authenticated:
        return redirect(url_for(f"{current_user.role}.dashboard"))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        identifier = form.username_or_email.data.strip()
        user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()

        if user:
            token = user.get_reset_token()
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            flash(f"Password reset link generated! Dev Link: <a href='{reset_url}' class='alert-link'>Reset Password Here</a>", "success")
        else:
            flash("If an account exists with that username or email, a reset link was generated.", "info")

        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset_password/<token>", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def reset_password(token):
    """Reset password using verified token."""
    if current_user.is_authenticated:
        return redirect(url_for(f"{current_user.role}.dashboard"))

    user = User.verify_token(token, purpose='reset_password', max_age=1800)
    if not user:
        flash("The password reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Your password has been updated! You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form)


@auth_bp.route("/profile")
@login_required
def profile():
    """View user profile."""
    return render_template("auth/profile.html", user=current_user)


@auth_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    """Edit profile bio, email, profile picture, and password."""
    form = EditProfileForm(obj=current_user)

    if form.validate_on_submit():
        # Check email uniqueness if modified
        new_email = form.email.data.strip() if form.email.data else None
        if new_email and new_email != current_user.email:
            existing = User.query.filter_by(email=new_email).first()
            if existing:
                flash("That email address is already in use by another account.", "danger")
                return render_template("auth/edit_profile.html", form=form)
            current_user.email = new_email

        current_user.bio = form.bio.data

        # Profile Picture Upload
        if form.profile_pic.data and allowed_image(form.profile_pic.data.filename):
            filename = secure_filename(form.profile_pic.data.filename)
            file_ext = filename.rsplit('.', 1)[1].lower()
            new_filename = f"user_{current_user.id}_avatar.{file_ext}"
            os.makedirs(AVATAR_UPLOAD_FOLDER, exist_ok=True)
            save_path = os.path.join(AVATAR_UPLOAD_FOLDER, new_filename)
            form.profile_pic.data.save(save_path)
            current_user.profile_pic = f"uploads/avatars/{new_filename}"

        # Password Update
        if form.new_password.data:
            if not form.current_password.data or not current_user.check_password(form.current_password.data):
                flash("Current password is incorrect. Could not update password.", "danger")
                return render_template("auth/edit_profile.html", form=form)
            current_user.set_password(form.new_password.data)
            flash("Password updated successfully!", "info")

        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for("auth.profile"))

    return render_template("auth/edit_profile.html", form=form)


@auth_bp.route("/admin/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def admin_login():
    """Handles admin login separately."""
    if current_user.is_authenticated and current_user.role == "admin":
        return redirect(url_for("admin.dashboard"))

    form = LoginForm()

    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data

        admin_user = User.query.filter_by(username=username, role="admin").first()

        if admin_user and check_password_hash(admin_user.password, password):
            login_user(admin_user)
            session["user_id"] = admin_user.id
            session["role"] = "admin"
            session.permanent = True

            # Track login streak
            update_login_streak(admin_user)
            flash("Admin login successful!", "success")
            return redirect(url_for("admin.dashboard"))

        flash("Invalid admin credentials. Try again.", "danger")

    return render_template("auth/admin_login.html", form=form)
