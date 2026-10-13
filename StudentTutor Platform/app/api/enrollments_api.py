"""Enrollments API — enroll / list student enrollments."""

from flask_restx import Namespace, Resource, fields

from app.models import Course, Enrollment, db
from app.api.token_auth import token_required
from app import limiter

ns = Namespace("enrollments", description="Student enrollments")

enrollment_model = ns.model("Enrollment", {
    "id": fields.Integer,
    "course_id": fields.Integer,
    "course_title": fields.String(attribute=lambda e: e.course.title if e.course else ""),
    "status": fields.String,
    "progress": fields.Integer,
    "enrolled_at": fields.DateTime(dt_format="iso8601"),
})

enroll_input = ns.model("EnrollInput", {
    "course_id": fields.Integer(required=True),
})


@ns.route("/")
class EnrollmentList(Resource):
    decorators = [limiter.limit("30 per minute")]
    @ns.marshal_list_with(enrollment_model)
    @token_required
    def get(self, user):
        """List current user's enrollments."""
        return Enrollment.query.filter_by(student_id=user.id).all()

    @ns.expect(enroll_input)
    @token_required
    def post(self, user):
        """Enroll in a course."""
        if user.role != "student":
            return {"error": "Only students can enroll"}, 403
        course_id = ns.payload["course_id"]
        course = Course.query.get(course_id)
        if not course or not course.is_approved:
            return {"error": "Course not found or not approved"}, 404
        existing = Enrollment.query.filter_by(student_id=user.id, course_id=course_id).first()
        if existing:
            return {"error": "Already enrolled"}, 409
        enrollment = Enrollment(student_id=user.id, course_id=course_id, status="active", progress=0)
        db.session.add(enrollment)
        db.session.commit()
        return {"message": "Enrolled successfully", "enrollment_id": enrollment.id}, 201
