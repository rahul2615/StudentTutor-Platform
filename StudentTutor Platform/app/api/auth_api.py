"""Auth API — login & register endpoints that return Bearer tokens."""

from flask_restx import Namespace, Resource, fields
from werkzeug.security import generate_password_hash, check_password_hash

from app.models import User, db
from app.api.token_auth import generate_api_token
from app import limiter

ns = Namespace("auth", description="Authentication & registration")

login_model = ns.model("Login", {
    "username": fields.String(required=True),
    "password": fields.String(required=True),
})

register_model = ns.model("Register", {
    "username": fields.String(required=True),
    "email": fields.String(),
    "password": fields.String(required=True),
    "role": fields.String(required=True, enum=["student", "tutor"]),
})


@ns.route("/login")
class Login(Resource):
    decorators = [limiter.limit("10 per minute")]
    @ns.expect(login_model)
    def post(self):
        """Authenticate and receive a Bearer token."""
        data = ns.payload
        user = User.query.filter_by(username=data["username"]).first()
        if not user or not check_password_hash(user.password, data["password"]):
            return {"error": "Invalid credentials"}, 401
        if user.role == "tutor" and not user.is_approved:
            return {"error": "Tutor account not yet approved"}, 403
        return {
            "token": generate_api_token(user.id),
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.role,
            }
        }


@ns.route("/register")
class Register(Resource):
    decorators = [limiter.limit("5 per minute")]
    @ns.expect(register_model)
    def post(self):
        """Create a new user account."""
        data = ns.payload
        if User.query.filter_by(username=data["username"]).first():
            return {"error": "Username already taken"}, 409
        role = data.get("role", "student")
        user = User(
            username=data["username"],
            email=data.get("email"),
            password=generate_password_hash(data["password"], method="scrypt"),
            role=role,
            user_type=role,
            is_approved=(role == "student"),
            approval_status="approved" if role == "student" else "pending",
            is_email_verified=True,
        )
        db.session.add(user)
        db.session.commit()
        return {
            "message": "Account created",
            "token": generate_api_token(user.id),
            "user": {"id": user.id, "username": user.username, "role": user.role},
        }, 201
