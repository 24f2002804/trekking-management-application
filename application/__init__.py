from flask import Flask, redirect, url_for, render_template
from flask_login import LoginManager
from config import Config
from application.database import db

login_manager = LoginManager()


def create_app(config_class=Config):
    app = Flask(__name__, template_folder="../templates")
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    from application import models 

    @login_manager.user_loader
    def load_user(user_id):
        return models.User.query.get(int(user_id))

    from application.controllers import auth_bp, admin_bp, staff_bp, trekker_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(trekker_bp)

    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(401)
    def unauthorized(e):
        return redirect(url_for("auth.login"))

    return app