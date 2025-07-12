from flask import Flask
from config import Config
from extensions import db, migrate, sse
from api import bp as api_bp
from dashboard import bp as dash_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(dash_bp)
    app.register_blueprint(sse, url_prefix="/stream")

    return app

if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8000)
