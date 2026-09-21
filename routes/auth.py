import os
import re
import uuid
import base64
import traceback

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    current_app
)

from werkzeug.security import check_password_hash

from database.db_service import DatabaseService

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        print(f"\n--- [LOGIN ATTEMPT] Email: '{email}' ---")

        if not email or not password:
            flash("Please provide both email and password.", "danger")
            return render_template('login.html')

        user = DatabaseService.get_user_by_email(email)

        if not user:
            print(f"--> User NOT found for email: '{email}'")
        else:
            stored_password = user.get('password_hash')
            if stored_password:
                try:
                    is_valid = check_password_hash(stored_password, password)
                except Exception as e:
                    print(f"--> Password check error: {e}")
                    is_valid = False

                if is_valid:
                    session['user_id'] = user['id']
                    session['user_name'] = user.get('full_name') or user.get('username') or email
                    session['email'] = user.get('email', email)
                    session['candidate_email'] = user.get('email', email)

                    flash("Login successful!", "success")
                    return redirect(url_for('dashboard.dashboard'))

        flash("Invalid email or password. Please try again.", "danger")

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        college = request.form.get('college', '').strip()
        branch = request.form.get('course', '').strip() or request.form.get('branch',
                                                                             '').strip()
        year = request.form.get('year_of_study', '').strip() or request.form.get('year', '').strip()
        roll_number = request.form.get('roll_number', '').strip()
        photo_data = request.form.get('photo_data', '').strip()

        if not full_name or not email or not password:
            flash("Please fill in all required fields.", "danger")
            return render_template('Register.html')

        if password != confirm_password:
            flash("Password and confirm password do not match.", "danger")
            return render_template('Register.html')

        if not photo_data:
            flash("Please start the camera and capture your identity photograph.", "danger")
            return render_template('Register.html')

        if DatabaseService.get_user_by_email(email):
            flash("This email is already registered. Please log in instead.", "warning")
            return redirect(url_for('auth.login'))

        try:
            encoded = photo_data.split(",", 1)[1] if "," in photo_data else photo_data
            image_bytes = base64.b64decode(encoded, validate=True)

            upload_dir = current_app.config.get("REGISTRATION_PHOTOS_FOLDER") or os.path.join(current_app.root_path, "uploads", "registration_photos")
            os.makedirs(upload_dir, exist_ok=True)

            safe_email = re.sub(r'[^A-Za-z0-9_.-]+', '_', email)
            filename = f"user_{safe_email}_{uuid.uuid4().hex[:8]}.jpg"
            absolute_photo_path = os.path.join(upload_dir, filename)
            stored_photo_path = os.path.relpath(
                absolute_photo_path,
                current_app.root_path
            ).replace(os.sep, "/")

            with open(absolute_photo_path, "wb") as f:
                f.write(image_bytes)

            if not os.path.isfile(absolute_photo_path) or os.path.getsize(absolute_photo_path) == 0:
                raise ValueError("Captured photo file is empty or was not created.")

        except Exception as e:
            traceback.print_exc()
            flash("Failed to save captured photo. Please capture it again.", "danger")
            return render_template('Register.html')

        try:
            username = email.split('@')[0]

            user_id = DatabaseService.create_candidate_with_profile(
                username=username,
                email=email,
                password=password,
                full_name=full_name,
                college=college,
                branch=branch,
                year=year,
                roll_number=roll_number,
                photo_path=stored_photo_path
            )

            if user_id:
                flash("Registration successful with identity photograph. Please log in.", "success")
                return redirect(url_for('auth.login'))

            flash("Registration failed while writing to the database.", "danger")

        except Exception as e:
            traceback.print_exc()
            if absolute_photo_path and os.path.exists(absolute_photo_path):
                os.remove(absolute_photo_path)
            flash(f"Registration error: {str(e)}", "danger")

    return render_template('Register.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('auth.login'))