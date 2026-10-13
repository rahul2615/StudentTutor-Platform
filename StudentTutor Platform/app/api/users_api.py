"""Users API — current user profile."""

from flask_restx import Namespace, Resource, fields

from app.models import db
from app.api.token_auth import token_required

ns = Namespace("users", description="User profile management")

user_model = ns.model("User", {
    "id": fields.Integer,
    "username": fields.String,
    "email": fields.String,
    "role": fields.String,
    "bio": fields.String,
    "points": fields.Integer,
    "streak_days": fields.Integer,
})

update_model = ns.model("UpdateProfile", {
    "bio": fields.String,
    "email": fields.String,
})


@ns.route("/me")
class Me(Resource):
    @ns.marshal_with(user_model)
    @token_required
    def get(self, user):
        """Get current authenticated user's profile."""
        return user

    @ns.expect(update_model)
    @token_required
    def put(self, user):
        """Update current user's profile."""
        data = ns.payload
        if "bio" in data:
            user.bio = data["bio"]
        if "email" in data:
            user.email = data["email"]
        db.session.commit()
        return {"message": "Profile updated"}
