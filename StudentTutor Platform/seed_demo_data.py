from datetime import datetime, timedelta, timezone
from app import create_app, db
from app.models import (
    User, Course, Enrollment, CourseMaterial, Quiz, Question,
    LiveSession, ForumPost, ForumComment, Message, Review, Wishlist, UserBadge
)

app = create_app()

def seed_data():
    with app.app_context():
        db.create_all()
        print("Seeding demo accounts, courses, quizzes, forums, and live sessions...")

        # 1. Create Tutors
        tutors_data = [
            {
                "username": "alex_tutor",
                "email": "alex.tutor@example.com",
                "password": "password123",
                "role": "tutor",
                "user_type": "tutor",
                "is_approved": True,
                "approval_status": "approved",
                "is_email_verified": True,
                "bio": "Senior Software Engineer & Educator with 8+ years teaching Python, Web Dev, and System Design.",
                "points": 120,
                "streak_days": 5
            },
            {
                "username": "sarah_tutor",
                "email": "sarah.tutor@example.com",
                "password": "password123",
                "role": "tutor",
                "user_type": "tutor",
                "is_approved": True,
                "approval_status": "approved",
                "is_email_verified": True,
                "bio": "PhD candidate in Applied Mathematics. Passionate about calculus, linear algebra, and data science.",
                "points": 95,
                "streak_days": 3
            },
            {
                "username": "david_tutor",
                "email": "david.tutor@example.com",
                "password": "password123",
                "role": "tutor",
                "user_type": "tutor",
                "is_approved": False,
                "approval_status": "pending",
                "is_email_verified": True,
                "bio": "Physics & Astronomy enthusiast looking to teach introductory quantum mechanics.",
                "points": 10,
                "streak_days": 1
            }
        ]

        tutor_objs = {}
        for td in tutors_data:
            existing = User.query.filter_by(username=td["username"]).first()
            if not existing:
                tutor = User(
                    username=td["username"],
                    email=td["email"],
                    role=td["role"],
                    user_type=td["user_type"],
                    is_approved=td["is_approved"],
                    approval_status=td["approval_status"],
                    is_email_verified=td["is_email_verified"],
                    bio=td["bio"],
                    points=td["points"],
                    streak_days=td["streak_days"]
                )
                tutor.set_password(td["password"])
                db.session.add(tutor)
                db.session.commit()
                tutor_objs[td["username"]] = tutor
                print(f"Created tutor: {td['username']}")
            else:
                tutor_objs[td["username"]] = existing

        # 2. Create Students
        students_data = [
            {
                "username": "john_student",
                "email": "john.student@example.com",
                "password": "password123",
                "role": "student",
                "user_type": "student",
                "is_approved": True,
                "approval_status": "approved",
                "is_email_verified": True,
                "bio": "Computer Science sophomore interested in web platforms and AI.",
                "points": 150,
                "streak_days": 7
            },
            {
                "username": "emma_student",
                "email": "emma.student@example.com",
                "password": "password123",
                "role": "student",
                "user_type": "student",
                "is_approved": True,
                "approval_status": "approved",
                "is_email_verified": True,
                "bio": "Mathematics major eager to learn data analysis and programming.",
                "points": 210,
                "streak_days": 12
            },
            {
                "username": "lucas_student",
                "email": "lucas.student@example.com",
                "password": "password123",
                "role": "student",
                "user_type": "student",
                "is_approved": True,
                "approval_status": "approved",
                "is_email_verified": True,
                "bio": "Self-taught developer building personal projects.",
                "points": 35,
                "streak_days": 2
            }
        ]

        student_objs = {}
        for sd in students_data:
            existing = User.query.filter_by(username=sd["username"]).first()
            if not existing:
                student = User(
                    username=sd["username"],
                    email=sd["email"],
                    role=sd["role"],
                    user_type=sd["user_type"],
                    is_approved=sd["is_approved"],
                    approval_status=sd["approval_status"],
                    is_email_verified=sd["is_email_verified"],
                    bio=sd["bio"],
                    points=sd["points"],
                    streak_days=sd["streak_days"]
                )
                student.set_password(sd["password"])
                db.session.add(student)
                db.session.commit()
                student_objs[sd["username"]] = student

                # Grant starting badges
                student.add_badge("First Step", "fa-graduation-cap")
                if sd["points"] > 100:
                    student.add_badge("Streak Master", "fa-fire")
                print(f"Created student: {sd['username']}")
            else:
                student_objs[sd["username"]] = existing

        # 3. Create Sample Courses
        courses_data = [
            {
                "title": "Mastering Python & Flask Web Development",
                "category": "Computer Science",
                "description": "Learn to build modern, responsive web applications using Flask, Jinja2, SQL-Alchemy, and RESTful principles from scratch.",
                "prerequisites": "Basic programming concepts in any language.",
                "duration": "6 weeks (4 hrs/week)",
                "tutor": tutor_objs["alex_tutor"],
                "is_approved": True,
                "approval_status": "approved"
            },
            {
                "title": "Data Structures & Algorithms in Java",
                "category": "Computer Science",
                "description": "Master essential data structures (Arrays, Trees, Graphs, HashTables) and algorithmic techniques for technical interviews.",
                "prerequisites": "Introductory Java knowledge.",
                "duration": "8 weeks (5 hrs/week)",
                "tutor": tutor_objs["alex_tutor"],
                "is_approved": True,
                "approval_status": "approved"
            },
            {
                "title": "Linear Algebra & Vector Calculus",
                "category": "Mathematics",
                "description": "A comprehensive deep-dive into matrices, vector spaces, eigenvalues, multi-variable derivatives, and gradient fields.",
                "prerequisites": "High school calculus and basic geometry.",
                "duration": "10 weeks (3 hrs/week)",
                "tutor": tutor_objs["sarah_tutor"],
                "is_approved": True,
                "approval_status": "approved"
            },
            {
                "title": "Quantum Physics & Relativity 101",
                "category": "Science",
                "description": "Explore wave-particle duality, Schrödinger equations, spacetime distortion, and the foundations of modern physics.",
                "prerequisites": "Physics 1 and basic calculus.",
                "duration": "5 weeks (2 hrs/week)",
                "tutor": tutor_objs["david_tutor"],
                "is_approved": False,
                "approval_status": "pending"
            }
        ]

        course_objs = {}
        for cd in courses_data:
            existing = Course.query.filter_by(title=cd["title"]).first()
            if not existing:
                course = Course(
                    title=cd["title"],
                    category=cd["category"],
                    description=cd["description"],
                    prerequisites=cd["prerequisites"],
                    duration=cd["duration"],
                    tutor_id=cd["tutor"].id,
                    is_approved=cd["is_approved"],
                    approval_status=cd["approval_status"]
                )
                db.session.add(course)
                db.session.commit()
                course_objs[cd["title"]] = course
                print(f"Created course: {cd['title']}")
            else:
                course_objs[cd["title"]] = existing

        # 4. Enrollments
        enrollments_data = [
            {
                "student": student_objs["john_student"],
                "course": course_objs["Mastering Python & Flask Web Development"],
                "progress": 45,
                "status": "active"
            },
            {
                "student": student_objs["emma_student"],
                "course": course_objs["Linear Algebra & Vector Calculus"],
                "progress": 80,
                "status": "active"
            }
        ]

        for ed in enrollments_data:
            existing = Enrollment.query.filter_by(
                student_id=ed["student"].id,
                course_id=ed["course"].id
            ).first()
            if not existing:
                enrollment = Enrollment(
                    student_id=ed["student"].id,
                    course_id=ed["course"].id,
                    progress=ed["progress"],
                    status=ed["status"]
                )
                db.session.add(enrollment)
                db.session.commit()

        # 5. Quizzes & Questions
        python_course = course_objs["Mastering Python & Flask Web Development"]
        quiz_existing = Quiz.query.filter_by(course_id=python_course.id, title="Flask Fundamentals Quiz").first()
        if not quiz_existing:
            quiz = Quiz(course_id=python_course.id, title="Flask Fundamentals Quiz", passing_score=70)
            db.session.add(quiz)
            db.session.commit()

            questions_data = [
                {
                    "prompt": "What is the primary function of Flask's render_template() helper?",
                    "a": "Compiles Python code into machine instructions",
                    "b": "Renders Jinja2 HTML template files with provided context",
                    "c": "Establishes a direct connection to PostgreSQL",
                    "d": "Deletes obsolete database tables",
                    "correct": "B"
                },
                {
                    "prompt": "Which decorator registers a URL route handler in Flask?",
                    "a": "@app.route('/path')",
                    "b": "@app.get_url('/path')",
                    "c": "@flask.path('/path')",
                    "d": "@url.register('/path')",
                    "correct": "A"
                }
            ]

            for qd in questions_data:
                q = Question(
                    quiz_id=quiz.id,
                    prompt=qd["prompt"],
                    option_a=qd["a"],
                    option_b=qd["b"],
                    option_c=qd["c"],
                    option_d=qd["d"],
                    correct_option=qd["correct"]
                )
                db.session.add(q)
            db.session.commit()
            print("Created quiz and questions for Python course.")

        # 6. Live Session
        session_existing = LiveSession.query.filter_by(course_id=python_course.id).first()
        if not session_existing:
            live = LiveSession(
                course_id=python_course.id,
                title="Flask Architecture & Live Q&A Workshop",
                description="Join instructor Alex for a live code review of Flask blueprints, session management, and database migrations.",
                scheduled_at=datetime.now(timezone.utc) + timedelta(days=2),
                duration_minutes=60,
                meeting_link="https://meet.jit.si/EduConnect-Flask-Workshop"
            )
            db.session.add(live)
            db.session.commit()
            print("Created sample Live Session.")

        # 7. Forum Discussion
        forum_existing = ForumPost.query.filter_by(course_id=python_course.id).first()
        if not forum_existing:
            post = ForumPost(
                course_id=python_course.id,
                user_id=student_objs["john_student"].id,
                title="How to manage circular imports between models and route blueprints?",
                content="Hi everyone! When defining Flask-SQLAlchemy models in models.py and registering blueprints in routes, what is the cleanest pattern to prevent circular imports?"
            )
            db.session.add(post)
            db.session.commit()

            reply = ForumComment(
                post_id=post.id,
                user_id=tutor_objs["alex_tutor"].id,
                content="Great question, John! The standard pattern is to instantiate `db = SQLAlchemy()` in app/__init__.py and import models inside `create_app()` after app context initialization."
            )
            db.session.add(reply)
            db.session.commit()
            print("Created sample Forum post and reply.")

        # 8. Direct Message
        msg_existing = Message.query.filter_by(sender_id=student_objs["john_student"].id, receiver_id=tutor_objs["alex_tutor"].id).first()
        if not msg_existing:
            msg1 = Message(
                sender_id=student_objs["john_student"].id,
                receiver_id=tutor_objs["alex_tutor"].id,
                content="Hello Alex! I really enjoyed the Flask tutorial. Do you have any recommendations for database deployment?"
            )
            msg2 = Message(
                sender_id=tutor_objs["alex_tutor"].id,
                receiver_id=student_objs["john_student"].id,
                content="Hi John! Thanks for asking. For production, PostgreSQL with Gunicorn and Flask-Migrate is highly recommended."
            )
            db.session.add_all([msg1, msg2])
            db.session.commit()
            print("Created sample direct messages.")

        # 9. Review
        rev_existing = Review.query.filter_by(course_id=python_course.id, student_id=student_objs["john_student"].id).first()
        if not rev_existing:
            rev = Review(
                course_id=python_course.id,
                student_id=student_objs["john_student"].id,
                rating=5,
                comment="Outstanding course! Clear explanations and great hands-on examples."
            )
            db.session.add(rev)
            db.session.commit()
            print("Created sample course review.")

        # 10. Wishlist
        algo_course = course_objs["Data Structures & Algorithms in Java"]
        wish_existing = Wishlist.query.filter_by(student_id=student_objs["john_student"].id, course_id=algo_course.id).first()
        if not wish_existing:
            wish = Wishlist(student_id=student_objs["john_student"].id, course_id=algo_course.id)
            db.session.add(wish)
            db.session.commit()
            print("Created sample wishlist entry.")

        # 11. Spread enrollment dates for analytics chart data
        enrollments = Enrollment.query.all()
        now = datetime.now(timezone.utc)
        for i, enr in enumerate(enrollments):
            # Spread across last 12 months
            days_back = (i * 35) % 365
            enr.enrolled_at = now - timedelta(days=days_back)
        db.session.commit()
        print("Spread enrollment dates across 12 months for analytics.")

        # 12. Audit Log demo entries
        from app.models import AuditLog, ContentFlag
        admin_user = User.query.filter_by(role="admin").first()
        if admin_user and AuditLog.query.count() == 0:
            demo_logs = [
                AuditLog(admin_id=admin_user.id, action="approve_tutor", target_type="user",
                         target_id=tutor_objs["alex_tutor"].id, target_label="alex_tutor",
                         created_at=now - timedelta(days=30)),
                AuditLog(admin_id=admin_user.id, action="approve_tutor", target_type="user",
                         target_id=tutor_objs["sarah_tutor"].id, target_label="sarah_tutor",
                         created_at=now - timedelta(days=28)),
                AuditLog(admin_id=admin_user.id, action="approve_course", target_type="course",
                         target_id=python_course.id, target_label=python_course.title,
                         created_at=now - timedelta(days=25)),
                AuditLog(admin_id=admin_user.id, action="approve_course", target_type="course",
                         target_id=algo_course.id, target_label=algo_course.title,
                         created_at=now - timedelta(days=20)),
                AuditLog(admin_id=admin_user.id, action="reject_tutor", target_type="user",
                         target_id=tutor_objs.get("david_tutor", tutor_objs["alex_tutor"]).id,
                         target_label="david_tutor",
                         created_at=now - timedelta(days=15)),
            ]
            db.session.add_all(demo_logs)
            db.session.commit()
            print("Created sample audit log entries.")

        # 13. Content Flag demo entries
        if ContentFlag.query.count() == 0:
            demo_flags = [
                ContentFlag(
                    flagged_type="forum_post", flagged_id=1,
                    reason="Contains promotional links to external commercial services",
                    severity="medium",
                    created_at=now - timedelta(days=5)
                ),
                ContentFlag(
                    flagged_type="course_description", flagged_id=2,
                    reason="Description contains potentially misleading claims about certification",
                    severity="low",
                    created_at=now - timedelta(days=3)
                ),
            ]
            db.session.add_all(demo_flags)
            db.session.commit()
            print("Created sample content flags.")

        print("\nAll demo data seeded successfully!")

if __name__ == "__main__":
    seed_data()

