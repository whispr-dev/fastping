from flask import render_template
from . import bp

@bp.route("/dashboard")
def index():
    return render_template("index.html")
