from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, FileField, TextAreaField, SubmitField, SelectField, IntegerField, DateTimeLocalField, DecimalField, DateTimeField
from wtforms.validators import DataRequired, Length, Optional, Email, EqualTo, NumberRange
from flask_wtf.file import FileAllowed


COURSE_CATEGORIES = [
    ('General', 'General'),
    ('Computer Science', 'Computer Science'),
    ('Mathematics', 'Mathematics'),
    ('Science', 'Science & Technology'),
    ('Languages', 'Languages & Literature'),
    ('Business', 'Business & Economics'),
    ('Arts', 'Arts & Humanities'),
]


COURSE_LEVELS = [
    ('Beginner', 'Beginner'),
    ('Intermediate', 'Intermediate'),
    ('Advanced', 'Advanced'),
]


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=150)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=150)])
    email = StringField('Email Address', validators=[Optional(), Email(), Length(max=150)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=150)])
    role = SelectField('Role', choices=[('student', 'Student'), ('tutor', 'Tutor')], validators=[DataRequired()])
    submit = SubmitField('Register')


class CourseForm(FlaskForm):
    title = StringField('Course Title', validators=[DataRequired(), Length(max=255)])
    category = SelectField('Category', choices=COURSE_CATEGORIES, default='General', validators=[DataRequired()])
    level = SelectField('Difficulty Level', choices=COURSE_LEVELS, default='Beginner', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])
    prerequisites = TextAreaField('Prerequisites', validators=[Optional()])
    duration = StringField('Duration (e.g., 4 weeks)', validators=[Optional(), Length(max=100)])
    price = DecimalField('Price (0.00 for Free)', default=0.00, places=2, validators=[Optional(), NumberRange(min=0)])
    currency = SelectField('Currency', choices=[('usd', 'USD ($)'), ('eur', 'EUR (€)'), ('gbp', 'GBP (£)'), ('inr', 'INR (₹)')], default='usd', validators=[Optional()])
    file = FileField('Upload Course Material', validators=[FileAllowed(['pdf', 'docx', 'png', 'jpg'], 'Only PDF, DOCX, PNG, JPG allowed!')])
    submit = SubmitField('Save Course')


class CourseModuleForm(FlaskForm):
    title = StringField('Module / Lesson Title', validators=[DataRequired(), Length(max=150)])
    order = IntegerField('Sequence Order', default=1, validators=[DataRequired(), NumberRange(min=1, max=100)])
    content = TextAreaField('Lesson Content / Notes', validators=[Optional()])
    submit = SubmitField('Add Module')


class StudentNoteForm(FlaskForm):
    content = TextAreaField('Study Note', validators=[DataRequired(), Length(max=2000)])
    submit = SubmitField('Save Note')


class EditProfileForm(FlaskForm):
    email = StringField('Email Address', validators=[Optional(), Email(), Length(max=150)])
    bio = TextAreaField('Bio / About Me', validators=[Optional(), Length(max=1000)])
    profile_pic = FileField('Profile Picture', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'], 'Images only!')])
    current_password = PasswordField('Current Password (Required for Password Change)', validators=[Optional()])
    new_password = PasswordField('New Password', validators=[Optional(), Length(min=6, max=150)])
    confirm_password = PasswordField('Confirm New Password', validators=[EqualTo('new_password', message='Passwords must match')])
    submit = SubmitField('Update Profile')


class ForgotPasswordForm(FlaskForm):
    username_or_email = StringField('Username or Email', validators=[DataRequired()])
    submit = SubmitField('Send Reset Link')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=6, max=150)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    submit = SubmitField('Reset Password')


# Phase 3 Forms: Learning & Engagement
class QuizForm(FlaskForm):
    title = StringField('Quiz Title', validators=[DataRequired(), Length(max=150)])
    passing_score = IntegerField('Passing Score (%)', default=70, validators=[DataRequired(), NumberRange(min=1, max=100)])
    submit = SubmitField('Create Quiz')


class QuestionForm(FlaskForm):
    prompt = TextAreaField('Question Prompt', validators=[DataRequired()])
    option_a = StringField('Option A', validators=[DataRequired(), Length(max=255)])
    option_b = StringField('Option B', validators=[DataRequired(), Length(max=255)])
    option_c = StringField('Option C', validators=[DataRequired(), Length(max=255)])
    option_d = StringField('Option D', validators=[DataRequired(), Length(max=255)])
    correct_option = SelectField('Correct Option', choices=[('A', 'Option A'), ('B', 'Option B'), ('C', 'Option C'), ('D', 'Option D')], validators=[DataRequired()])
    submit = SubmitField('Save Question')


class LiveSessionForm(FlaskForm):
    title = StringField('Session Title', validators=[DataRequired(), Length(max=150)])
    description = TextAreaField('Session Description', validators=[Optional()])
    scheduled_at = DateTimeLocalField('Scheduled Time', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    duration_minutes = IntegerField('Duration (Minutes)', default=60, validators=[DataRequired(), NumberRange(min=15, max=300)])
    meeting_link = StringField('Meeting URL / Jitsi Room Name', validators=[DataRequired(), Length(max=255)])
    recording_link = StringField('Rewatch Recording URL (Optional)', validators=[Optional(), Length(max=255)])
    submit = SubmitField('Schedule Live Session')


class ForumPostForm(FlaskForm):
    title = StringField('Post Title', validators=[DataRequired(), Length(max=200)])
    content = TextAreaField('Discussion Content', validators=[DataRequired()])
    submit = SubmitField('Post Discussion')


class ForumCommentForm(FlaskForm):
    content = TextAreaField('Your Reply', validators=[DataRequired()])
    submit = SubmitField('Post Reply')


class ReviewForm(FlaskForm):
    rating = SelectField('Rating', choices=[('5', '5 Stars - Excellent'), ('4', '4 Stars - Very Good'), ('3', '3 Stars - Average'), ('2', '2 Stars - Fair'), ('1', '1 Star - Poor')], validators=[DataRequired()])
    comment = TextAreaField('Course Review', validators=[Optional(), Length(max=1000)])
    submit = SubmitField('Submit Review')


class MessageForm(FlaskForm):
    content = TextAreaField('Message', validators=[DataRequired()])
    submit = SubmitField('Send Message')


class CouponForm(FlaskForm):
    code = StringField('Coupon Code', validators=[DataRequired(), Length(max=50)])
    discount_type = SelectField('Discount Type', choices=[('percentage', 'Percentage (%)'), ('flat', 'Flat Amount')], default='percentage', validators=[DataRequired()])
    discount_value = DecimalField('Discount Value', validators=[DataRequired(), NumberRange(min=0.01)])
    max_uses = IntegerField('Max Uses (Optional, blank = unlimited)', validators=[Optional(), NumberRange(min=1)])
    valid_from = DateTimeLocalField('Valid From (Optional)', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    valid_until = DateTimeLocalField('Valid Until (Optional)', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    course_id = SelectField('Specific Course (Optional)', coerce=int, validators=[Optional()])
    submit = SubmitField('Save Coupon')


class CouponApplyForm(FlaskForm):
    code = StringField('Coupon Code', validators=[DataRequired(), Length(max=50)])
    submit = SubmitField('Apply Coupon')


class TutorPaymentSettingsForm(FlaskForm):
    upi_id = StringField('UPI ID (e.g. name@okicici, phonepe, paytm)', validators=[Optional(), Length(max=100)])
    qr_code = FileField('Upload Custom Payment QR Code Image', validators=[FileAllowed(['png', 'jpg', 'jpeg'], 'Only PNG, JPG allowed!')])
    bank_name = StringField('Bank Name', validators=[Optional(), Length(max=100)])
    account_number = StringField('Account Number', validators=[Optional(), Length(max=50)])
    ifsc_code = StringField('IFSC Code', validators=[Optional(), Length(max=20)])
    account_holder_name = StringField('Account Holder Name', validators=[Optional(), Length(max=150)])
    submit = SubmitField('Save Payment Settings')


class UpiPaymentForm(FlaskForm):
    transaction_ref = StringField('12-Digit UTR / Transaction Reference Number', validators=[DataRequired(), Length(min=6, max=50)])
    payment_proof = FileField('Upload Payment Screenshot (Optional)', validators=[FileAllowed(['png', 'jpg', 'jpeg', 'pdf'], 'Only PNG, JPG, PDF allowed!')])
    submit = SubmitField('Submit UPI Payment Verification')