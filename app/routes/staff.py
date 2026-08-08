from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app import db
from app.decorators import role_required
from app.models import Trek, Booking

staff_bp = Blueprint("staff", __name__, url_prefix="/staff")


def _get_staff_profile_or_404():
    """Helper: get the logged-in staff member's profile, or block access."""
    if not current_user.staff_profile:
        abort(403)
    return current_user.staff_profile


def _get_owned_trek_or_403(trek_id):
    """Helper: fetch a trek only if it's assigned to the logged-in staff member."""
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

    return render_template(
        "staff/dashboard.html",
        assigned_treks=assigned_treks,
        total_participants=total_participants,
        open_treks_count=open_treks_count,
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

        if not full_name:
            flash("Name cannot be empty.", "danger")
            return redirect(url_for("staff.profile"))

        current_user.full_name = full_name
        staff_profile.contact_number = contact_number
        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("staff.profile"))

    return render_template("staff/profile.html", staff_profile=staff_profile)