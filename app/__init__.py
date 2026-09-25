# app/__init__.py
from flask import Flask
from app.config import Config
from app.database import init_db_pool, close_db

def create_app(config_class=Config):
    app = Flask(__name__, template_folder='../templates')
    app.config.from_object(config_class)

    init_db_pool(app)
    app.teardown_appcontext(close_db)

    from app.routes.web import web_bp
    from app.routes.api import api_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)

    return app