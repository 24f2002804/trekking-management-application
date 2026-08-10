from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.decorators import role_required, is_valid_password
from app.models import Trek, Booking

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

    # For filter dropdowns: distinct locations currently open
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