from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    db.create_all()

    existing_admin = User.query.filter_by(role="admin").first()
    if existing_admin:
        print(f"Admin already exists: {existing_admin.email}")
    else:
        admin = User(
            full_name="System Admin",
            email="admin@trekking.com",
            role="admin",
        )
        admin.set_password("Admin@123") 
        db.session.add(admin)   
        db.session.commit()
        print("Admin user created successfully.")
        print("Email: admin@trekking.com | Password: Admin@123")
