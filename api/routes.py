from flask import request, jsonify, current_app as app
from extensions import db
from models import User, Target
from tasks import ping_target
from . import bp

@bp.post("/targets")
def add_target():
    data = request.get_json(force=True)
    user_email = data["email"].lower()
    host       = data["host"]
    user = User.query.filter_by(email=user_email).first() or User(email=user_email)
    db.session.add(user)
    tgt = Target(host=host, owner=user)
    db.session.add(tgt)
    db.session.commit()

    # start immediate ping plus schedule periodic (every 60 s via Celery beat or cron)
    ping_target.delay(tgt.id)
    return jsonify({"target_id": tgt.id}), 201

@bp.get("/ping/<host>")
def single_ping(host):
    from ping_utils import do_ping
    latency = do_ping(host)
    return jsonify({"host": host, "latency_ms": latency})
