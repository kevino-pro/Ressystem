"""
Normalisatie van gastgegevens om reserveringen te vergelijken (dubbele boekingen).
De database bewaart wat de gast heeft ingevuld; deze vormen worden alleen gebruikt om te vergelijken.
"""
import re


def normaliseer_email(email):
    return str(email).strip().lower()


def normaliseer_naam(naam):
    """Kleine letters, en spaties aan de randen en dubbele spaties weg."""
    return " ".join(str(naam).split()).casefold()


def telefoon_cijfers(telefoon):
    """Alleen de cijfers van een telefoonnummer, zonder +, spaties of koppeltekens."""
    return re.sub(r"\D", "", str(telefoon))


def normaliseer_telefoon(telefoon):
    """+31 6 1234 5678, 0031612345678 en 06-12345678 worden allemaal 0612345678."""
    cijfers = telefoon_cijfers(telefoon)
    if str(telefoon).strip().startswith("+"):
        cijfers = "00" + cijfers
    if cijfers.startswith("0031"):
        cijfers = "0" + cijfers[4:]
    return cijfers
