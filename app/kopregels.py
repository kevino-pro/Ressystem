"""Vaste beveiligingskopregels op elk antwoord van de app (pagina's, API, static en foutpagina's)."""
import secrets

from flask import g

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

# Content-Security-Policy: alles komt van de eigen site. Scripts draaien alleen uit een eigen bestand of met de
# nonce van dit verzoek; een <script> dat via een naam of opmerking in de pagina zou komen, draait dus niet.
# Stijlen mogen inline: de templates gebruiken style="..." en basis.html zet de accentkleur in een <style>.
CSP_VAST = (
    "default-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
)


def csp_nonce():
    """Eén willekeurige waarde per verzoek, voor <script nonce="{{ csp_nonce() }}"> in de templates."""
    if "csp_nonce" not in g:
        g.csp_nonce = secrets.token_urlsafe(16)
    return g.csp_nonce


def _csp():
    nonce = g.get("csp_nonce")  # alleen gezet als een template erom vroeg
    script = "script-src 'self'" + (f" 'nonce-{nonce}'" if nonce else "")
    return "; ".join((*CSP_VAST, script))


def registreer(app):
    app.jinja_env.globals["csp_nonce"] = csp_nonce

    @app.after_request
    def zet_kopregels(antwoord):
        for naam, waarde in KOPREGELS.items():
            antwoord.headers.setdefault(naam, waarde)
        antwoord.headers.setdefault("Content-Security-Policy", _csp())
        return antwoord
