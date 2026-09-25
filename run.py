# run.py
from app import create_app
from app.config import Config
from app.database import init_db

app = create_app(Config)

if __name__ == '__main__':
    with app.app_context():
        init_db()

    print("\n=== GEREGISTREERDE ROUTES ===")
    print(app.url_map)
    print("=============================\n")
    app.run(debug=True)