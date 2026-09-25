# run.py
from app import create_app
from app.config import Config
from app.database import init_db

app = create_app(Config)

# Buiten de __main__-guard: gunicorn importeert deze module zonder 'm als __main__ uit te voeren.
with app.app_context():
    init_db()

if __name__ == '__main__':
    print("\n=== GEREGISTREERDE ROUTES ===")
    print(app.url_map)
    print("=============================\n")
    app.run(debug=True)