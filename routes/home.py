from flask import Blueprint, render_template

home_bp = Blueprint('home', __name__)

@home_bp.route('/')
def home():
    """Renders the official portal homepage directly upon root navigation."""
    return render_template('home.html')