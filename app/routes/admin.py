from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.decorators import role_required
from app.models import User, Trek, Booking, StaffProfile

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/dashboard")
@login_required
@role_required("admin")
def dashboard():
    total_treks = Trek.query.count()
    total_users = User.query.filter_by(role="trekker").count()
    total_staff = User.query.filter_by(role="staff").count()
    total_bookings = Booking.query.count()

    recent_bookings = (
        Booking.query.order_by(Booking.booking_date.desc()).limit(5).all()
    )

    return render_template(
        "admin/dashboard.html",
        total_treks=total_treks,
        total_users=total_users,
        total_staff=total_staff,
        total_bookings=total_bookings,
        recent_bookings=recent_bookings,
    )


# ---------------- TREK MANAGEMENT ----------------

@admin_bp.route("/treks")
@login_required
@role_required("admin")
def treks():
    search = request.args.get("q", "").strip()
    query = Trek.query
    if search:
        query = query.filter(
            (Trek.name.ilike(f"%{search}%")) | (Trek.location.ilike(f"%{search}%"))
        )
    all_treks = query.order_by(Trek.created_at.desc()).all()
    return render_template("admin/treks.html", treks=all_treks, search=search)



@admin_bp.route("/treks/approve/<int:trek_id>", methods=["POST"])
@login_required
@role_required("admin")
def approve_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    if trek.status == "Pending":
        trek.status = "Approved"
        db.session.commit()
        flash(f"Trek '{trek.name}' approved.", "success")
    return redirect(url_for("admin.treks"))


@admin_bp.route("/treks/add", methods=["GET", "POST"])
@login_required
@role_required("admin")
def add_trek():
    approved_staff = StaffProfile.query.filter_by(status="approved").all()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        location = request.form.get("location", "").strip()
        difficulty = request.form.get("difficulty", "")
        duration_days = request.form.get("duration_days", type=int)
        total_slots = request.form.get("total_slots", type=int)
        assigned_staff_id = request.form.get("assigned_staff_id") or None
        status = request.form.get("status", "Pending")
        start_date = request.form.get("start_date") or None
        end_date = request.form.get("end_date") or None
        description = request.form.get("description", "")

        if not name or not location or not difficulty or not duration_days or not total_slots:
            flash("Please fill all required fields.", "danger")
            return redirect(url_for("admin.add_trek"))

        new_trek = Trek(
            name=name,
            location=location,
            difficulty=difficulty,
            duration_days=duration_days,
            total_slots=total_slots,
            available_slots=total_slots,
            assigned_staff_id=assigned_staff_id,
            status=status,
            start_date=datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None,
            end_date=datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
            description=description,
        )
        db.session.add(new_trek)
        db.session.commit()
        flash("Trek created successfully.", "success")
        return redirect(url_for("admin.treks"))

    return render_template("admin/trek_form.html", trek=None, staff_list=approved_staff)


@admin_bp.route("/treks/edit/<int:trek_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    approved_staff = StaffProfile.query.filter_by(status="approved").all()

    if request.method == "POST":
        trek.name = request.form.get("name", "").strip()
        trek.location = request.form.get("location", "").strip()
        trek.difficulty = request.form.get("difficulty", "")
        trek.duration_days = request.form.get("duration_days", type=int)
        trek.total_slots = request.form.get("total_slots", type=int)
        trek.available_slots = request.form.get("available_slots", type=int)
        trek.assigned_staff_id = request.form.get("assigned_staff_id") or None
        trek.status = request.form.get("status", trek.status)
        start_date = request.form.get("start_date") or None
        end_date = request.form.get("end_date") or None
        trek.start_date = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
        trek.end_date = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None
        trek.description = request.form.get("description", "")

        db.session.commit()
        flash("Trek updated successfully.", "success")
        return redirect(url_for("admin.treks"))

    return render_template("admin/trek_form.html", trek=trek, staff_list=approved_staff)


@admin_bp.route("/treks/delete/<int:trek_id>", methods=["POST"])
@login_required
@role_required("admin")
def delete_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    db.session.delete(trek)
    db.session.commit()
    flash("Trek removed successfully.", "info")
    return redirect(url_for("admin.treks"))


# ---------------- STAFF MANAGEMENT ----------------

@admin_bp.route("/staff")
@login_required
@role_required("admin")
def staff():
    search = request.args.get("q", "").strip()
    query = User.query.filter_by(role="staff")
    if search:
        query = query.filter(
            (User.full_name.ilike(f"%{search}%")) | (User.email.ilike(f"%{search}%"))
        )
    all_staff = query.order_by(User.created_at.desc()).all()
    return render_template("admin/staff.html", staff_members=all_staff, search=search)


@admin_bp.route("/staff/approve/<int:user_id>", methods=["POST"])
@login_required
@role_required("admin")
def approve_staff(user_id):
    user = User.query.get_or_404(user_id)
    if user.staff_profile:
        user.staff_profile.status = "approved"
        user.staff_profile.approved_at = datetime.utcnow()
        db.session.commit()
        flash(f"{user.full_name} approved as Trek Staff.", "success")
    return redirect(url_for("admin.staff"))


@admin_bp.route("/staff/blacklist/<int:user_id>", methods=["POST"])
@login_required
@role_required("admin")
def blacklist_staff(user_id):
    user = User.query.get_or_404(user_id)
    if user.staff_profile:
        user.staff_profile.status = "blacklisted"
        db.session.commit()
        flash(f"{user.full_name} has been blacklisted.", "warning")
    return redirect(url_for("admin.staff"))


@admin_bp.route("/staff/remove/<int:user_id>", methods=["POST"])
@login_required
@role_required("admin")
def remove_staff(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("Staff account removed.", "info")
    return redirect(url_for("admin.staff"))


# ---------------- USER (TREKKER) MANAGEMENT ----------------

@admin_bp.route("/users")
@login_required
@role_required("admin")
def users():
    search = request.args.get("q", "").strip()
    query = User.query.filter_by(role="trekker")
    if search:
        query = query.filter(
            (User.full_name.ilike(f"%{search}%")) | (User.email.ilike(f"%{search}%"))
        )
    all_users = query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=all_users, search=search)


@admin_bp.route("/users/blacklist/<int:user_id>", methods=["POST"])
@login_required
@role_required("admin")
def blacklist_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_blacklisted = not user.is_blacklisted
    db.session.commit()
    status = "blacklisted" if user.is_blacklisted else "reactivated"
    flash(f"{user.full_name} has been {status}.", "warning")
    return redirect(url_for("admin.users"))


# ---------------- BOOKINGS / HISTORY ----------------

@admin_bp.route("/bookings")
@login_required
@role_required("admin")
def bookings():
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "")

    query = Booking.query.join(Trek).join(User)

    if search:
        query = query.filter(
            (Trek.name.ilike(f"%{search}%")) | (User.full_name.ilike(f"%{search}%"))
        )
    if status_filter:
        query = query.filter(Booking.status == status_filter)

    all_bookings = query.order_by(Booking.booking_date.desc()).all()
    return render_template(
        "admin/bookings.html", bookings=all_bookings, search=search, status_filter=status_filter
    )