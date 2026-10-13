import secrets
from app import create_app, db
from app.models import User

# Create Flask app instance
app = create_app()

# Run inside the application context
with app.app_context():
    username = "admin"

    # Check if admin user already exists
    existing_admin = User.query.filter_by(username=username, role="admin").first()

    if not existing_admin:
        random_password = secrets.token_urlsafe(16)
        admin = User(
            username=username,
            user_type="admin",
            is_approved=True,
            role="admin"
        )
        admin.set_password(random_password)
        db.session.add(admin)
        db.session.commit()
        print(f"Admin user created successfully!")
        print(f"Username: {username}")
        print(f"Password: {random_password}")
        print("Please save this password securely. Change it upon first login.")
    else:
        print("Admin user already exists!")
