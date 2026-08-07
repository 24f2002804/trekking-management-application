from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, StaffProfile

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role = request.form.get("role", "")  # 'staff' or 'trekker' only

        if role not in ("staff", "trekker"):
            flash("Please select a valid role.", "danger")
            return redirect(url_for("auth.register"))

        if not full_name or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("auth.register"))

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists.", "danger")
            return redirect(url_for("auth.register"))

        new_user = User(full_name=full_name, email=email, role=role)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.flush()  # assigns new_user.id before commit

        if role == "staff":
            staff_profile = StaffProfile(user_id=new_user.id, status="pending")
            db.session.add(staff_profile)

        db.session.commit()

        if role == "staff":
            flash("Registration successful. Your account needs Admin approval before you can log in.", "info")
        else:
            flash("Registration successful. You can now log in.", "success")

        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_dashboard_url_for(current_user))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("auth.login"))

        if user.is_blacklisted:
            flash("Your account has been blacklisted. Contact the Admin.", "danger")
            return redirect(url_for("auth.login"))

        if user.role == "staff":
            if not user.staff_profile or user.staff_profile.status == "pending":
                flash("Your account is awaiting Admin approval.", "warning")
                return redirect(url_for("auth.login"))
            if user.staff_profile.status == "blacklisted":
                flash("Your staff account has been blacklisted. Contact the Admin.", "danger")
                return redirect(url_for("auth.login"))

        login_user(user)
        flash(f"Welcome back, {user.full_name}!", "success")
        return redirect(_dashboard_url_for(user))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


def _dashboard_url_for(user):
    if user.role == "admin":
        return url_for("admin.dashboard")
    if user.role == "staff":
        return url_for("staff.dashboard")
    return url_for("trekker.dashboard")