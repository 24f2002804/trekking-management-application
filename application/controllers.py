import re
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_user, logout_user, login_required, current_user
from application.database import db
from application.models import User, StaffProfile, Trek, Booking
from application.decorators import role_required, is_valid_password


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role = request.form.get("role", "")

        if role not in ("staff", "trekker"):
            flash("Please select a valid role.", "danger")
            return redirect(url_for("auth.register"))

        if not full_name or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("auth.register"))

        if not is_valid_password(password):
            flash("Password must be at least 8 characters long and contain at least one digit.", "danger")
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
        db.session.flush()

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




admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/dashboard")
@login_required
@role_required("admin")
def dashboard():
    total_treks = Trek.query.count()
    total_users = User.query.filter_by(role="trekker").count()
    total_staff = User.query.filter_by(role="staff").count()
    total_bookings = Booking.query.count()

    all_treks = Trek.query.order_by(Trek.name).all()
    participants_chart_labels = [t.name for t in all_treks]
    participants_chart_values = [
        Booking.query.filter_by(trek_id=t.id).filter(Booking.status != "Cancelled").count()
        for t in all_treks
    ]

    return render_template(
        "admin/dashboard.html",
        total_treks=total_treks,
        total_users=total_users,
        total_staff=total_staff,
        total_bookings=total_bookings,
        chart_labels=["Treks", "Bookings", "Active Users", "Staff"],
        chart_values=[total_treks, total_bookings, total_users, total_staff],
        all_treks=all_treks,
        participants_chart_labels=participants_chart_labels,
        participants_chart_values=participants_chart_values,
    )


@admin_bp.route("/treks")
@login_required
@role_required("admin")
def treks():
    search = request.args.get("q", "").strip()
    query = Trek.query
    if search:
        filters = [Trek.name.ilike(f"%{search}%"), Trek.location.ilike(f"%{search}%")]
        if search.isdigit():
            filters.append(Trek.id == int(search))
        query = query.filter(db.or_(*filters))
    all_treks = query.order_by(Trek.created_at.desc()).all()
    return render_template("admin/treks.html", treks=all_treks, search=search)


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


@admin_bp.route("/staff")
@login_required
@role_required("admin")
def staff():
    search = request.args.get("q", "").strip()
    query = User.query.filter_by(role="staff")
    if search:
        filters = [User.full_name.ilike(f"%{search}%"), User.email.ilike(f"%{search}%")]
        if search.isdigit():
            filters.append(User.id == int(search))
        query = query.filter(db.or_(*filters))
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


@admin_bp.route("/users")
@login_required
@role_required("admin")
def users():
    search = request.args.get("q", "").strip()
    query = User.query.filter_by(role="trekker")
    if search:
        filters = [User.full_name.ilike(f"%{search}%"), User.email.ilike(f"%{search}%")]
        if search.isdigit():
            filters.append(User.id == int(search))
        query = query.filter(db.or_(*filters))
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

    unique_participants = (
        db.session.query(Booking.user_id)
        .filter(Booking.status != "Cancelled")
        .distinct()
        .count()
    )

    return render_template(
        "admin/bookings.html",
        bookings=all_bookings,
        search=search,
        status_filter=status_filter,
        total_participants=unique_participants,
    )

@admin_bp.route("/profile", methods=["GET", "POST"])
@login_required
@role_required("admin")
def profile():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not full_name:
            flash("Name cannot be empty.", "danger")
            return redirect(url_for("admin.profile"))

        current_user.full_name = full_name

        if current_password or new_password or confirm_password:
            if not current_user.check_password(current_password):
                flash("Current password is incorrect.", "danger")
                return redirect(url_for("admin.profile"))

            if not new_password:
                flash("New password cannot be empty.", "danger")
                return redirect(url_for("admin.profile"))

            if not is_valid_password(new_password):
                flash("New password must be at least 8 characters long and contain at least one digit.", "danger")
                return redirect(url_for("admin.profile"))

            if new_password != confirm_password:
                flash("New password and confirm password do not match.", "danger")
                return redirect(url_for("admin.profile"))

            current_user.set_password(new_password)
            flash("Profile and password updated successfully.", "success")
        else:
            flash("Profile updated successfully.", "success")

        db.session.commit()
        return redirect(url_for("admin.profile"))

    return render_template("admin/profile.html")




staff_bp = Blueprint("staff", __name__, url_prefix="/staff")


def _get_staff_profile_or_404():
    if not current_user.staff_profile:
        abort(403)
    return current_user.staff_profile


def _get_owned_trek_or_403(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    staff_profile = _get_staff_profile_or_404()
    if trek.assigned_staff_id != staff_profile.id:
        abort(403)
    return trek


@staff_bp.route("/dashboard")
@login_required
@role_required("staff")
def dashboard():
    staff_profile = _get_staff_profile_or_404()

    assigned_treks = Trek.query.filter_by(assigned_staff_id=staff_profile.id).all()
    total_participants = sum(
        Booking.query.filter_by(trek_id=t.id, status="Booked").count() for t in assigned_treks
    )
    open_treks_count = sum(1 for t in assigned_treks if t.status == "Open")

    chart_labels = [t.name for t in assigned_treks]
    chart_values = [
        Booking.query.filter_by(trek_id=t.id).filter(Booking.status != "Cancelled").count()
        for t in assigned_treks
    ]

    return render_template(
        "staff/dashboard.html",
        assigned_treks=assigned_treks,
        total_participants=total_participants,
        open_treks_count=open_treks_count,
        chart_labels=chart_labels,
        chart_values=chart_values,
    )


@staff_bp.route("/treks")
@login_required
@role_required("staff")
def my_treks():
    staff_profile = _get_staff_profile_or_404()
    assigned_treks = Trek.query.filter_by(assigned_staff_id=staff_profile.id).all()
    return render_template("staff/my_treks.html", treks=assigned_treks)


@staff_bp.route("/treks/<int:trek_id>", methods=["GET", "POST"])
@login_required
@role_required("staff")
def manage_trek(trek_id):
    trek = _get_owned_trek_or_403(trek_id)

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_slots_status":
            available_slots = request.form.get("available_slots", type=int)
            status = request.form.get("status")

            if available_slots is not None:
                if available_slots > trek.total_slots or available_slots < 0:
                    flash("Available slots must be between 0 and total slots.", "danger")
                    return redirect(url_for("staff.manage_trek", trek_id=trek.id))
                trek.available_slots = available_slots

            if status in ("Open", "Closed"):
                trek.status = status

            db.session.commit()
            flash("Trek details updated.", "success")

        elif action == "mark_status":
            new_status = request.form.get("new_status")
            if new_status in ("Ongoing", "Completed"):
                trek.status = new_status

                if new_status == "Completed":
                    active_bookings = Booking.query.filter_by(
                        trek_id=trek.id, status="Booked"
                    ).all()
                    for booking in active_bookings:
                        booking.status = "Completed"

                db.session.commit()
                flash(f"Trek marked as {new_status}.", "success")

        return redirect(url_for("staff.manage_trek", trek_id=trek.id))

    participants = (
        Booking.query.filter_by(trek_id=trek.id)
        .filter(Booking.status != "Cancelled")
        .all()
    )
    return render_template("staff/trek_manage.html", trek=trek, participants=participants)


@staff_bp.route("/profile", methods=["GET", "POST"])
@login_required
@role_required("staff")
def profile():
    staff_profile = _get_staff_profile_or_404()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        contact_number = request.form.get("contact_number", "").strip()
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not full_name:
            flash("Name cannot be empty.", "danger")
            return redirect(url_for("staff.profile"))

        current_user.full_name = full_name
        staff_profile.contact_number = contact_number

        if current_password or new_password or confirm_password:
            if not current_user.check_password(current_password):
                flash("Current password is incorrect.", "danger")
                return redirect(url_for("staff.profile"))

            if not new_password:
                flash("New password cannot be empty.", "danger")
                return redirect(url_for("staff.profile"))

            if not is_valid_password(new_password):
                flash("New password must be at least 8 characters long and contain at least one digit.", "danger")
                return redirect(url_for("staff.profile"))

            if new_password != confirm_password:
                flash("New password and confirm password do not match.", "danger")
                return redirect(url_for("staff.profile"))

            current_user.set_password(new_password)
            flash("Profile and password updated successfully.", "success")
        else:
            flash("Profile updated successfully.", "success")

        db.session.commit()
        return redirect(url_for("staff.profile"))

    return render_template("staff/profile.html", staff_profile=staff_profile)




trekker_bp = Blueprint("trekker", __name__, url_prefix="/trekker")


@trekker_bp.route("/dashboard")
@login_required
@role_required("trekker")
def dashboard():
    available_treks = Trek.query.filter_by(status="Open").order_by(Trek.start_date).limit(5).all()
    my_bookings = (
        Booking.query.filter_by(user_id=current_user.id)
        .order_by(Booking.booking_date.desc())
        .limit(5)
        .all()
    )
    return render_template(
        "trekker/dashboard.html",
        available_treks=available_treks,
        my_bookings=my_bookings,
    )


@trekker_bp.route("/treks")
@login_required
@role_required("trekker")
def browse_treks():
    difficulty = request.args.get("difficulty", "")
    location = request.args.get("location", "")
    search = request.args.get("q", "").strip()

    query = Trek.query.filter_by(status="Open")

    if difficulty:
        query = query.filter(Trek.difficulty == difficulty)
    if location:
        query = query.filter(Trek.location == location)
    if search:
        query = query.filter(Trek.name.ilike(f"%{search}%"))

    treks = query.order_by(Trek.start_date).all()

    all_locations = [
        row[0] for row in db.session.query(Trek.location).filter_by(status="Open").distinct()
    ]

    already_booked_trek_ids = {
        b.trek_id
        for b in Booking.query.filter_by(user_id=current_user.id)
        .filter(Booking.status != "Cancelled")
        .all()
    }

    return render_template(
        "trekker/browse_treks.html",
        treks=treks,
        difficulty=difficulty,
        location=location,
        search=search,
        all_locations=all_locations,
        already_booked_trek_ids=already_booked_trek_ids,
    )


@trekker_bp.route("/treks/<int:trek_id>")
@login_required
@role_required("trekker")
def trek_details(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    already_booked = (
        Booking.query.filter_by(user_id=current_user.id, trek_id=trek.id)
        .filter(Booking.status != "Cancelled")
        .first()
        is not None
    )
    return render_template("trekker/trek_details.html", trek=trek, already_booked=already_booked)


@trekker_bp.route("/treks/<int:trek_id>/book", methods=["POST"])
@login_required
@role_required("trekker")
def book_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)

    if trek.status != "Open":
        flash("This trek is not currently open for booking.", "danger")
        return redirect(url_for("trekker.trek_details", trek_id=trek.id))

    if trek.available_slots <= 0:
        flash("Sorry, this trek is fully booked.", "danger")
        return redirect(url_for("trekker.trek_details", trek_id=trek.id))

    existing = (
        Booking.query.filter_by(user_id=current_user.id, trek_id=trek.id)
        .filter(Booking.status != "Cancelled")
        .first()
    )
    if existing:
        flash("You have already booked this trek.", "warning")
        return redirect(url_for("trekker.trek_details", trek_id=trek.id))

    new_booking = Booking(
        user_id=current_user.id,
        trek_id=trek.id,
        status="Booked",
        payment_status="Pending",
    )
    trek.available_slots -= 1

    db.session.add(new_booking)
    db.session.commit()

    flash(f"Trek '{trek.name}' booked successfully!", "success")
    return redirect(url_for("trekker.my_bookings"))


@trekker_bp.route("/bookings")
@login_required
@role_required("trekker")
def my_bookings():
    bookings = (
        Booking.query.filter_by(user_id=current_user.id)
        .filter(Booking.status.in_(["Booked"]))
        .order_by(Booking.booking_date.desc())
        .all()
    )
    return render_template("trekker/my_bookings.html", bookings=bookings)


@trekker_bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@login_required
@role_required("trekker")
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)

    if booking.user_id != current_user.id:
        flash("You cannot cancel this booking.", "danger")
        return redirect(url_for("trekker.my_bookings"))

    if booking.status == "Booked":
        booking.status = "Cancelled"
        booking.trek.available_slots += 1
        db.session.commit()
        flash("Booking cancelled.", "info")

    return redirect(url_for("trekker.my_bookings"))


@trekker_bp.route("/history")
@login_required
@role_required("trekker")
def history():
    past_bookings = (
        Booking.query.filter_by(user_id=current_user.id)
        .filter(Booking.status.in_(["Completed", "Cancelled"]))
        .order_by(Booking.booking_date.desc())
        .all()
    )

    chart_labels = ["Booked", "Completed", "Cancelled"]
    chart_values = [
        Booking.query.filter_by(user_id=current_user.id, status=s).count() for s in chart_labels
    ]

    return render_template(
        "trekker/history.html",
        bookings=past_bookings,
        chart_labels=chart_labels,
        chart_values=chart_values,
    )


@trekker_bp.route("/profile", methods=["GET", "POST"])
@login_required
@role_required("trekker")
def profile():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not full_name:
            flash("Name cannot be empty.", "danger")
            return redirect(url_for("trekker.profile"))

        current_user.full_name = full_name

        if current_password or new_password or confirm_password:
            if not current_user.check_password(current_password):
                flash("Current password is incorrect.", "danger")
                return redirect(url_for("trekker.profile"))

            if not new_password:
                flash("New password cannot be empty.", "danger")
                return redirect(url_for("trekker.profile"))

            if not is_valid_password(new_password):
                flash("New password must be at least 8 characters long and contain at least one digit.", "danger")
                return redirect(url_for("trekker.profile"))

            if new_password != confirm_password:
                flash("New password and confirm password do not match.", "danger")
                return redirect(url_for("trekker.profile"))

            current_user.set_password(new_password)
            flash("Profile and password updated successfully.", "success")
        else:
            flash("Profile updated successfully.", "success")

        db.session.commit()
        return redirect(url_for("trekker.profile"))

    return render_template("trekker/profile.html")