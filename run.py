# run.py
import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.logger.info("Geregistreerde routes:\n%s", app.url_map)

    db_url = app.config['DATABASE_URL']
    if 'neon.tech' in db_url and os.getenv('ALLOW_PROD_DB_LOCAL') != '1':
        app.logger.error(
            "GEBLOKKEERD: run.py (lokale dev-server) wijst naar de Neon-productiedatabase. "
            "Zet DATABASE_URL in .env terug naar sqlite:///reserveringen.db, of zet "
            "ALLOW_PROD_DB_LOCAL=1 als dit echt bewust is."
        )
        raise SystemExit(1)

    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1')
    app.run(debug=debug_mode)
