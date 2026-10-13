"""Courses API — browse approved courses."""

from flask_restx import Namespace, Resource, fields
from flask import request as req

from app.models import Course

ns = Namespace("courses", description="Browse and search courses")

course_model = ns.model("Course", {
    "id": fields.Integer,
    "title": fields.String,
    "description": fields.String,
    "category": fields.String,
    "prerequisites": fields.String,
    "duration": fields.String,
    "tutor": fields.String(attribute=lambda c: c.tutor.username if c.tutor else "Unknown"),
    "student_count": fields.Integer,
    "average_rating": fields.Float,
})


@ns.route("/")
class CourseList(Resource):
    @ns.marshal_list_with(course_model)
    def get(self):
        """List all approved courses. Supports ?search= and ?category= query params."""
        query = Course.query.filter_by(is_approved=True)
        search = req.args.get("search", "").strip()
        category = req.args.get("category", "").strip()
        if search:
            query = query.filter(
                (Course.title.ilike(f"%{search}%")) | (Course.description.ilike(f"%{search}%"))
            )
        if category and category != "All":
            query = query.filter_by(category=category)
        return query.all()


@ns.route("/<int:course_id>")
class CourseDetail(Resource):
    @ns.marshal_with(course_model)
    def get(self, course_id):
        """Get details of a specific course."""
        course = Course.query.get_or_404(course_id)
        if not course.is_approved:
            ns.abort(404, "Course not found or not approved")
        return course
