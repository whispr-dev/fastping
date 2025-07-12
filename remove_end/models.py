import uuid, datetime as dt
from extensions import db

class User(db.Model):
    id    = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(120), unique=True, nullable=False)
    targets = db.relationship("Target", backref="owner", lazy=True)

class Target(db.Model):
    id      = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    host    = db.Column(db.String(255), nullable=False)
    created = db.Column(db.DateTime, default=dt.datetime.utcnow)
    user_id = db.Column(db.String(36), db.ForeignKey("user.id"), nullable=False)
    results = db.relationship("PingResult", backref="target", lazy=True, cascade="all,delete")

class PingResult(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    sent_at   = db.Column(db.DateTime, default=dt.datetime.utcnow, index=True)
    ms        = db.Column(db.Float, nullable=False)   # latency in ms (-1 = timeout)
    target_id = db.Column(db.String(36), db.ForeignKey("target.id"), nullable=False)
