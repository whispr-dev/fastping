import os
from celery import Celery
from flask import Flask
from config import Config
from extensions import db
from models import Target, PingResult
from ping_utils import do_ping

celery = Celery(__name__, broker=Config.REDIS_URL)

def make_celery_app():
    app = Flask("fastping")
    app.config.from_object(Config)
    db.init_app(app)
    return app

app = make_celery_app()

@celery.task
def ping_target(target_id: str):
    with app.app_context():
        tgt = Target.query.get_or_404(target_id)
        latency = do_ping(tgt.host)
        r = PingResult(ms=latency, target=tgt)
        db.session.add(r)
        db.session.commit()
        from extensions import sse
        sse.publish({"host": tgt.host, "ms": latency}, type="ping", channel=tgt.user_id)
