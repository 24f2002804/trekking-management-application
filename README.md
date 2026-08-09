# Trekking Management Application

A Flask-based web application for managing trekking activities, allowing Admin, Trek Staff, and Users (Trekkers) to interact with the system based on their roles.

## Tech Stack

- **Backend:** Flask
- **Database:** SQLite (via Flask-SQLAlchemy)
- **Authentication:** Flask-Login
- **Frontend:** Jinja2, HTML, Bootstrap 5
- **Charts:** Chart.js

## Prerequisites

- Python 3.10 or higher installed
- pip (comes with Python)

## Setup Instructions

### 1. Extract/clone the project and navigate into it

```bash
cd trekking-management-application
```

### 2. Create and activate a virtual environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Mac/Linux:**
```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create the database and seed the Admin account

Run the following script once. This programmatically creates all database tables and a pre-existing Admin account (as required — Admin cannot self-register).

```bash
python seed_admin.py
```

You should see output confirming the admin user was created:

Admin user created successfully.
Email: admin@trekking.com | Password: Admin@123


This creates a `trekking.db` file inside the `instance/` folder.

### 5. Run the application

```bash
python run.py
```

The app will start on:

http://127.0.0.1:5000/


## Default Login Credentials

**Admin**
- Email: `admin@trekking.com`
- Password: `Admin@123`

Trek Staff and Trekker accounts are created via self-registration on the app's Register page. Trek Staff accounts require Admin approval before they can log in.

## Usage Flow

1. Log in as Admin using the credentials above.
2. Create a trek (Manage Treks → Add New Trek) and approve any pending Trek Staff registrations.
3. Assign an approved staff member to a trek and set its status to **Open**.
4. Register a new account as a Trekker, log in, and book the open trek.
5. Log in as the assigned Trek Staff member to manage participants and update trek status.

## Project Structure

trekking-management-application/
├── app/
│ ├── init.py # App factory, extensions, blueprint registration
│ ├── models.py # Database models (User, StaffProfile, Trek, Booking)
│ ├── decorators.py # Role-based access control decorator
│ ├── routes/ # Flask Blueprints (auth, admin, staff, trekker)
│ └── templates/ # Jinja2 HTML templates
├── instance/ # SQLite database file (created on first run)
├── config.py # App configuration
├── seed_admin.py # Script to create tables + pre-seed Admin account
├── run.py # Application entry point
├── requirements.txt
└── .gitignore


## Notes

- The database is created entirely through code (`seed_admin.py`), not manually via any database browser tool.
- Running `python seed_admin.py` again is safe — it checks if an Admin already exists before creating one.
- If you want a completely fresh database, delete `instance/trekking.db` and re-run `python seed_admin.py`.