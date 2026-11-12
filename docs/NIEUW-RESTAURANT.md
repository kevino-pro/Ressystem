# Checklist: een nieuw restaurant of een nieuwe vestiging

Elke vestiging is een eigen installatie: een eigen Render-service, een eigen Neon-database en een eigen
restaurantbestand, allemaal uit deze ene repo. Werk de stappen van boven naar beneden af en vink ze af.
In dit bestand staan alleen **namen** van instellingen, nooit waarden. Een geheim maak je zelf in je eigen
terminal en plak je alleen in het dashboard waar het hoort, nooit in een chat of in een bestand in de repo.

Voorbeeld hieronder: de vestiging Amsterdam met het korte achtervoegsel `AMSTERDAM`.

## 1. Restaurantbestand (in de repo)

- [ ] Kopieer `restaurants/voorbeeld.toml` naar `restaurants/<naam>.toml` (bijvoorbeeld `restaurants/wpl-amsterdam.toml`).
- [ ] Vul in: `[restaurant]` (naam, e-mail, telefoon), `[reserveringen]` en `[reserveringen.openingstijden]`,
      `[privacy]` (verantwoordelijke, adres, verwerkers), `[huisstijl]`, `[talen]`, `[herinnering]` en, als het
      personeel tafels wil toewijzen, `[plattegrond]`. Zie de README voor wat elk veld betekent.
- [ ] Controleer het bestand:

      python -m app.controle restaurants/<naam>.toml

      Elke regel moet `OK` zijn; `LET OP` mag als het zo bedoeld is. Bij `FOUT` start de app niet in productie.
- [ ] Noemt `[privacy]` een verwerker met een doel of locatie die nog nergens staat, dan meldt de controle
      "niet vertaald". Zet die zin dan in `vertalingen/en.toml` en `vertalingen/id.toml`.
- [ ] Commit, PR en merge alleen het restaurantbestand (en eventuele vertalingen) vóór stap 4: Render deployt vanaf main en de app start niet zonder dit bestand. installaties.json volgt pas in stap 2/6.

## 2. Installatie in `installaties.json` (in de repo)

- [ ] Voeg een blok toe met de namen die je in stap 6 in GitHub aanmaakt:

      {
        "naam": "wpl-amsterdam",
        "restaurantbestand": "restaurants/wpl-amsterdam.toml",
        "app_url": "RENDER_APP_URL_AMSTERDAM",
        "health_url": "RENDER_HEALTH_URL_AMSTERDAM",
        "service_id": "RENDER_SERVICE_ID_AMSTERDAM",
        "beheer_sleutel": "BEHEER_API_KEY_AMSTERDAM"
      }

- [ ] Draai de tests: `python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"`.
      `tests/test_installaties.py` controleert dat elke installatie eigen namen heeft en dat het restaurantbestand klopt.
- [ ] Commit, PR en merge pas **na** stap 6: zodra dit in main staat, draaien de geplande taken ook voor de nieuwe installatie.

## 3. Neon (database)

- [ ] Maak een nieuw project aan voor deze vestiging, in een regio in de Europese Unie (de privacyverklaring belooft dat).
- [ ] Noteer voor jezelf welke connection string de pooled is (host met `-pooler`) en welke de directe. Niet in de repo zetten.

## 4. Render (website)

- [ ] Nieuwe Web Service uit dezelfde GitHub-repo, branch `main`, regio in de Europese Unie.
- [ ] Build Command en Start Command precies zoals in de README onder "Render deployment"; Health Check Path `/health`.
- [ ] Environment, alleen namen (de waarden zet je zelf):
  - `APP_ENV` = `production`, `RESTAURANT_CONFIG` = `restaurants/<naam>.toml`, `APP_BASE_URL` (https-adres van deze service)
  - `DATABASE_URL` (pooled), `MIGRATION_DATABASE_URL` (direct, zonder `-pooler`)
  - `SECRET_KEY`, `API_KEY`, `BEHEER_API_KEY` (minstens 32 tekens): elk een nieuwe, eigen waarde, gemaakt in je eigen terminal, bijvoorbeeld
    `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Gebruik nooit de waarden van een andere vestiging.
  - `RESEND_API_KEY`, `VERZENDER_EMAIL` (een adres op een domein dat bij Resend geverifieerd is)
  - `ANTHROPIC_API_KEY` (alleen als deze vestiging reserveren via een bericht gebruikt)
- [ ] Wacht op de eerste groene deploy en open `<adres>/health`: die moet 200 geven.

## 5. Eerste beheerder

- [ ] Maak het eerste beheerdersaccount met `flask create-admin --productie` zoals bij Den Haag, met de pooled URL van
      **deze** Neon-database. Controleer vóór het commando welke database-host is ingesteld (les uit OVERDRACHT §7:
      een account in de verkeerde database lijkt te werken maar is onvindbaar).
- [ ] Log in en maak de andere accounts via `/accounts`.

## 6. GitHub (geplande taken)

Settings → Secrets and variables → Actions, op het tabblad **Variables** en **Secrets** van de repository
(niet bij Codespaces, Dependabot of een environment):

- [ ] Variables: `RENDER_APP_URL_AMSTERDAM` (adres zonder `/health`), `RENDER_HEALTH_URL_AMSTERDAM` (met `/health`), `RENDER_SERVICE_ID_AMSTERDAM`.
- [ ] Secret: `BEHEER_API_KEY_AMSTERDAM` met dezelfde waarde als `BEHEER_API_KEY` in Render van deze vestiging.
- [ ] `RENDER_API_KEY` is er al en geldt voor het hele Render-account.
- [ ] Merge nu de PR van stap 2.

## 7. n8n (reserveren via een bericht)

- [ ] Alleen als deze vestiging dat gebruikt: importeer de workflow uit `n8n/` (zie `n8n/README.md`), vul het adres van deze
      service en een eigen credential met de `API_KEY` van deze vestiging in.

## 8. Controleren

- [ ] Open de site op je telefoon: naam, adres, openingstijden, taalkiezer en privacyverklaring kloppen.
- [ ] Maak een testreservering met je eigen e-mailadres: de mail komt aan met de naam van het restaurant als afzender.
      Verwijder de testreservering daarna als beheerder.
- [ ] Start in GitHub Actions met de hand "Dagelijks opschonen (AVG)", "Herinneringsmails" en "Keep Neon Alive"
      (Run workflow). Elke taak heeft nu een regel voor elke installatie, en ze zijn allemaal groen.
- [ ] Werk OVERDRACHT.md bij: vestiging, restaurantbestand, de namen in GitHub en de datum van livegang.
