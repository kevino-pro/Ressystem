"""Vaste beveiligingskopregels op elk antwoord van de app (pagina's, API, static en foutpagina's)."""

KOPREGELS = {
    # Een jaar lang alleen via https. Browsers negeren deze kopregel op http, dus lokaal doet hij niets.
    "Strict-Transport-Security": "max-age=31536000",
    # De browser raadt het bestandstype niet zelf.
    "X-Content-Type-Options": "nosniff",
    # Geen enkele pagina mag in een frame van een andere site (clickjacking op de personeelspagina's).
    "X-Frame-Options": "DENY",
    # Het reserverings-id in /annuleren/<id> is ook de annuleerlink: stuur het adres nooit mee naar een andere site.
    "Referrer-Policy": "same-origin",
}


def registreer(app):
    @app.after_request
    def zet_kopregels(antwoord):
        for naam, waarde in KOPREGELS.items():
            antwoord.headers.setdefault(naam, waarde)
        return antwoord
