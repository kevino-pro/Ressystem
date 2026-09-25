import os
import requests
from dotenv import load_dotenv

# Laad variabelen uit .env
load_dotenv()

BASE_URL = "http://127.0.0.1:5000/api/v1/ai-reservering"
VALID_API_KEY = os.getenv("WEBHOOK_API_KEY", "jouw_geheime_key_hier")

def run_tests():
    print("=== START END-TO-END WEBHOOK TESTS ===\n")

    # TEST 1: Geen API-sleutel (Verwacht 401 Unauthorized)
    print("Test 1: Request zonder X-API-Key header...")
    res = requests.post(BASE_URL, json={"naam": "Test Persoon"})
    print(f"Status: {res.status_code} | Body: {res.json()}")
    assert res.status_code == 401, "Mislukt: Moet 401 teruggeven bij ontbrekende key."
    print("✅ TEST 1 GESLAAGD\n")

    # TEST 2: Ongeldige API-sleutel (Verwacht 401 Unauthorized)
    print("Test 2: Request met foute X-API-Key header...")
    headers_fout = {"X-API-Key": "foutieve-sleutel-123"}
    res = requests.post(BASE_URL, headers=headers_fout, json={"naam": "Test Persoon"})
    print(f"Status: {res.status_code} | Body: {res.json()}")
    assert res.status_code == 401, "Mislukt: Moet 401 teruggeven bij verkeerde key."
    print("✅ TEST 2 GESLAAGD\n")

    # TEST 3: Geldige Key, maar ongeldige payload (Verwacht 400 Bad Request)
    print("Test 3: Request met geldige Key, maar incomplete JSON payload...")
    headers_goed = {"X-API-Key": VALID_API_KEY}
    res = requests.post(BASE_URL, headers=headers_goed, json={})
    print(f"Status: {res.status_code} | Body: {res.json()}")
    assert res.status_code == 400, "Mislukt: Moet 400 teruggeven bij foutieve payload."
    assert res.json().get("status") == "fout", "Mislukt: Response moet status 'fout' bevatten."
    print("✅ TEST 3 GESLAAGD\n")

    # TEST 4: Geldige Key & Geldige Payload (Verwacht 200/201 OK)
    print("Test 4: Volledig geldige webhook-aanroep...")
    geldige_payload = {
        "klant_tekst": "Hoi, ik wil graag een tafel reserveren voor 4 personen op 2026-10-15 om 19:00. Groetjes Jan de Tester, 0612345678"
    }
    res = requests.post(BASE_URL, headers=headers_goed, json=geldige_payload)
    print(f"Status: {res.status_code} | Body: {res.json()}")
    assert res.status_code in [200, 201], f"Mislukt: Verwacht 200/201, kreeg {res.status_code}"
    print("✅ TEST 4 GESLAAGD\n")

    print("🎉 ALLE END-TO-END TESTS SUCCESVOL DOORLOPEN!")

if __name__ == "__main__":
    run_tests()