import os
from flask import Flask, redirect
from config import Config
from database import init_db
from database.db_service import DatabaseService

# Import Blueprint Routes
from routes.home import home_bp
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.exam import exam_bp
from routes.proctoring import proctoring_bp
from routes.admin import admin_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize SQLite Database and Seed Data
    try:
        init_db()
    except Exception as e:
        print(f"Base database init warning: {e}")

    # Ensure all auto-healing tables (exam_submissions, proctoring_logs) are created
    with app.app_context():
        DatabaseService.init_db()

    # Register Blueprints
    app.register_blueprint(home_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(exam_bp)
    app.register_blueprint(proctoring_bp)
    app.register_blueprint(admin_bp)

    @app.route("/profile")
    def profile_alias():
        return redirect("/dashboard/profile")

    @app.errorhandler(404)
    def page_not_found(e):
        return "Resource requested does not exist on the ExamGuard system.", 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return "An internal server error occurred. Please contact the platform admin.", 500

    return app

app = create_app()

if __name__ == '__main__':
    print("=====================================================================")
    print(" EXAMGUARD: Smart Examination Monitoring Platform Running Locally")
    print(f" Portal Home: http://{Config.HOST}:{Config.PORT}/")
    print("=====================================================================")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)