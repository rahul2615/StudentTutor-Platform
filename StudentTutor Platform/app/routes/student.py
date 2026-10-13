from flask import Blueprint
from app.controllers.student_controller import dashboard, courses, enroll, unenroll
from app.controllers.course_controller import take_quiz, view_certificate, add_student_note, delete_student_note
from app import limiter

student = Blueprint("student", __name__)

# Routes for Student Dashboard and Courses Page
student.route("/dashboard")(dashboard)
student.route("/courses", methods=["GET", "POST"])(courses)
student.route("/enroll/<int:course_id>", methods=["POST"])(limiter.limit("20 per minute")(enroll))
student.route("/unenroll/<int:course_id>", methods=["POST"])(unenroll)

# Quizzes & Certificates
student.route("/quiz/<int:quiz_id>", methods=["GET", "POST"])(limiter.limit("15 per minute")(take_quiz))
student.route("/certificate/<int:course_id>", methods=["GET"])(view_certificate)

# Student Notes
student.route("/course/<int:course_id>/add_note", methods=["POST"])(add_student_note)
student.route("/note/<int:note_id>/delete", methods=["POST"])(delete_student_note)

