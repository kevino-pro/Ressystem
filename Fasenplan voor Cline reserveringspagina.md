# Fasenplan voor Cline: reserveringspagina versimpelen

Opgesteld 11 nov 2026 door Claude (Sonnet 5.5). Gebaseerd op `main` op commit 43321aa (PR #51). Voor Cline (uitvoerder), Sonnet (controleur) en de gebruiker (alle git-handelingen). Geen geheimen in dit bestand. HYPOTHESE = niet bewezen; BEWIJS = gezien in code of testuitslag.

Per fase staan hieronder drie blokken die je zo kunt kopiëren: (1) de git-terminal, (2) de prompt voor Cline, (3) de controle-prompt voor Sonnet. De bestandsinhoud staat achteraan in de bijlagen. Het ontwerpvoorbeeld waar dit op gebaseerd is staat in `ontwerp/reserveren-voorbeeld.html` (losstaand, nepdata, niet bedoeld om te committen).

## Doel en besluiten

De reserveringspagina voor gasten wordt rustiger en korter, zonder iets te schrappen dat nodig is:

- Aantal personen: een keuzelijst in plaats van 15 knoppen.
- Geen nummerbadges bij de kopjes; geen dubbele uitleg (info-regel boven het formulier weg, geen placeholders bij naam en e-mail).
- Kinderstoel, allergie en opmerking in een uitklapblok.
- Vaste balk onderaan met je keuze ("wo 11 nov · 17:00, 2 personen · tot 18:00") en de knop; de knop is uit tot er een tijd is gekozen.
- Meldingen per veld, direct onder het veld.
- Dagstrook die je kunt schuiven (Vandaag, Morgen, "Andere dag" met kalender); een dag zonder boekbare tijd staat dicht, zodat het formulier op de eerstvolgende dag met plek begint (was bug B4 uit de review van 8 nov).
- Link Personeel van de kop naar de voet.
- Privacyvinkje wordt een zin met link (alleen na jouw bevestiging, fase 3). Het vinkje voor de allergie-toestemming blijft.

Bewust anders dan Gemini's advies: de 17 tijdknoppen blijven (8 tijden zou de helft van je boekbare momenten schrappen); de kopjes Lunch en Diner blijven.

| Fase | Inhoud | Tests na de fase (bij main op 43321aa) |
|---|---|---|
| 1 | Compact formulier: keuzelijst, uitklapblok, vaste balk, meldingen per veld, Personeel naar de voet | 575 (+11) |
| 2 | Dagstrook met Vandaag/Morgen en Andere dag; dag dicht als er niets meer kan | 582 (+7) |
| 3 | Privacyzin in plaats van vinkje | 588 (+6) |

Wat hierna kan (niet in dit plan): de wijzigpagina (`templates/annuleren_bevestigen.html`, de link in de bevestigingsmail) heeft zijn eigen kopie van de kiezer en houdt de oude opmaak; die in dezelfde stijl zetten is een aparte fase 4. Ook niet erin: de grondslag in de privacyverklaring noemen, een bericht "dag vol, eerstvolgende plek: ..." en een Engelse tekstcontrole door een moedertaalspreker.

Getest op een kopie van `main` (43321aa) met SQLite, in drie stappen, met 564 tests als nulmeting. Daarnaast heb ik de echte pagina (de app op een lokale testserver met een tijdelijke database) in de browser op telefoonbreedte doorlopen: in fase 1 met een fout e-mailadres en een echte testreservering, in fase 2 de dagstrook met "Andere dag" (ook op een breed scherm) en in fase 3 de zin onder de knop. Tijdens dat bekijken zijn twee layoutfouten gevonden en hersteld (de dagstrook rekte de pagina op, en de knop in de vaste balk was te breed); de oplossingen zitten in het plan. **Niet getest op Postgres** (er is geen databasewijziging in dit plan) en niet op een echte telefoon.

Let op bij de nulmeting: als er voor deze fases andere branches (bijvoorbeeld `feat/cijfers`) in `main` zijn gemerged, wijkt het aantal tests af. Het plan rekent daarom met "nulmeting + N". Past een blok niet doordat dezelfde regels in de tussentijd zijn veranderd, dan moet Cline stoppen; stuur dan het blok naar Claude.

## Werkafspraken

- Eén fase tegelijk. Pas na merge op `main` en een groene Render-deploy begint de volgende fase.
- Repo-bestanden gebruiken CRLF. De bestandsinhoud in de bijlagen staat met gewone regeleinden (LF); Cline schrijft nieuwe bestanden met CRLF en behoudt de regeleinden van bestaande bestanden.
- Elke vertaalbare zin in een template staat in `vertalingen/en.toml` en `vertalingen/id.toml`; `tests/test_vertalingen.py` dwingt dat af, ook dat er geen ongebruikte vertalingen blijven staan. Daarom verwijderen de fases ook sleutels.
- Cline voert uit, Sonnet controleert (alleen lezen), jij doet alle git.

## Fase 1: Compact formulier

### 1. Git-terminal (Git Bash)

```bash
cd /c/Codes/WPL && git checkout main && git pull && git checkout -b feat/reserveren-compact && git --no-pager log --oneline -3
```

### 2. Prompt voor Cline

```text
Context
Je werkt in C:\Codes\WPL (Flask-app voor restaurantreserveringen, Nederlandse namen). Branch feat/reserveren-compact is actief en komt van main.
Het fasenplan staat in "Fasenplan voor Cline reserveringspagina.md"; lees daarin alleen "Fase 1" en "Bijlage 1". Deze fase: het reserveerformulier compacter maken: aantal personen als keuzelijst, geen nummerbadges, extra velden in een uitklapblok, een vaste balk onderaan met je keuze en de knop, meldingen per veld, en de link Personeel van de kop naar de voet. Alleen templates, css, vertalingen en tests; geen Python in app/.

Taak
1. Draai eerst in Git Bash (vanuit de repo-root, venv actief): python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"
   Noteer het getal bij "Ran" als nulmeting. Slaagt niet alles al vóór je begint, stop dan en meld dat.
2. Maak de nieuwe bestanden en pas de bestaande bestanden aan precies zoals in Bijlage 1: nieuwe bestanden en "vervang het hele bestand" met de volledige inhoud; gewijzigde bestanden per blok (regels met - weg, regels met + erbij; de rest is omgeving). Gebruik je bewerk-tool per blok, niet git apply. Past een blok niet, stop dan en meld welk blok.
3. Repo-bestanden gebruiken CRLF: behoud de regeleinden van bestaande bestanden en schrijf nieuwe bestanden ook met CRLF.
4. Draai in Git Bash opnieuw: python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"
   Verwacht: nulmeting + 11 tests, uitslag OK (skipped mag gelijk blijven).

Rapporteer alleen
Wat er gebeurt; verzin niets, verbeter niets en voeg niets toe dat niet in het plan staat.

Beperkingen
- Alleen de bestanden uit Bijlage 1. Geen andere bestanden, geen nieuwe packages, geen refactors.
- Geen git-commando's (geen add, commit, push, branch, merge): de gebruiker doet alle git zelf.
- Geen echte databaseverbinding: gebruik geen DATABASE_URL, geen Neon, geen .env en geen *.db-bestanden; start de app niet tegen een echte database.
- Lees of toon geen .env, .flaskenv, mcp.json of .neon.
- Bij twijfel stop je en vraagt het mij.

Wat je mij meldt
- Lijst van nieuwe en gewijzigde bestanden.
- Nulmeting en eindresultaat van de tests (de regels Ran, OK of FAILED).
- Elke afwijking van het plan, met reden.
```

### 3. Controle-prompt voor Sonnet

```text
Context: Ik werk aan de Flask-app in C:\Codes\WPL. Cline heeft zojuist "Reserveringspagina, fase 1: compact formulier" uitgevoerd
volgens een vast plan. Jij bent de controleur; je wijzigt zelf niets.
Taak (alleen lezen):

1. Draai in Git Bash: git --no-pager status -sb en git --no-pager diff --stat
en git --no-pager diff
2. Lees de gewijzigde en nieuwe bestanden volledig.
3. Draai in Git Bash: python -m unittest discover -s tests -v
4. Controleer de algemene punten hieronder en de extra punten van deze fase.

Algemene punten:

* Alleen de bestanden uit de fase zijn gewijzigd of nieuw; geen andere.
* Geen hele-bestand-diffs door regeleinden (CRLF moet CRLF blijven).
* Geen geheimen, echte URL's, wachtwoorden of klantgegevens in de diff.
* Alle tests slagen; het aantal tests is gestegen met het verwachte aantal.
* Code past bij de stijl van het project (Nederlandse namen, bestaande patronen
zoals _guard en de TestConfig-klassen).
* Niets aan wat de fase niet vraagt (geen extra refactors, geen nieuwe packages).

Rapporteer alleen: GO of NO-GO, dan per punt OK of een concrete bevinding met
bestand:regel. Geen codevoorstellen tenzij bij NO-GO, en dan de kleinste fix.
Beperkingen: niets wijzigen, niets committen, .env/.neon/*.db niet openen,
geen databaseverbinding buiten de tests.
Extra punten voor deze fase:
1. Alleen deze bestanden zijn gewijzigd of nieuw: templates/index.html, templates/basis.html, static/css/huisstijl.css, vertalingen/en.toml, vertalingen/id.toml, tests/test_formulier.py, tests/test_extra_wensen.py, tests/test_regels_in_routes.py, tests/test_wpl_regels.py en nieuw tests/test_formulier_compact.py. Niets in app/ en niets in templates/annuleren_bevestigen.html (de wijzigpagina houdt bewust de oude opmaak).
2. static/css/huisstijl.css is alleen aangevuld: er verdwijnt geen enkele bestaande regel (git --no-pager diff static/css/huisstijl.css toont geen regels die met - beginnen, behalve de kopregel).
3. Vertalingen: in zowel en.toml als id.toml zijn precies deze sleutels verwijderd: "Online tot", "Jan Jansen", "naam@voorbeeld.nl", en precies deze vier toegevoegd: "Kies een tijd", "Vul een geldig e-mailadres in.", "Alleen voor als we je moeten bereiken over je reservering.", "Bevestiging direct per e-mail". Verder niets veranderd. tests.test_vertalingen slaagt.
4. Het script in templates/index.html gebruikt geen innerHTML (alleen textContent en createElement), en de sleutels kies_tijd, naam_fout, email_fout, telefoon_fout en allergie_fout staan in het T-object.
5. Het formulier stuurt nog dezelfde velden als voorheen naar /reservering: naam, email, telefoon, datum, tijd, aantal, website, privacy_akkoord, opmerking, kinderstoelen, allergieen, allergie_toestemming. Het privacyvinkje (id privacy_akkoord) bestaat in deze fase nog.
6. De link naar /login staat nog maar één keer op de gastpagina en alleen in de voet (templates/basis.html), niet meer in de kop van templates/index.html.
7. Het aantal tests is met 11 gestegen ten opzichte van de nulmeting van Cline (bij main op 43321aa: 564 naar 575), uitslag OK.
```

### Voor en na de merge

Voor de merge: PR maken; CI `unit-tests` moet groen zijn.

Na de merge (door de gebruiker):

1. Wacht op de groene Render-deploy.
2. Open de site op je telefoon, in het Nederlands, Engels en Indonesisch (taalkiezer rechtsboven): je ziet een keuzelijst voor het aantal personen, geen nummertjes bij de kopjes, onderaan een vaste balk. Kies een tijd: de balk toont je keuze en de knop gaat aan.
3. Vul een fout e-mailadres in: de melding verschijnt onder het veld. Klap "Nog iets dat we moeten weten?" open en dicht.
4. Doe een echte testreservering met je eigen e-mailadres en annuleer die daarna via de link in de mail (dit schrijft echte gegevens naar de database en verstuurt echt een mail).
5. Link Personeel staat onderaan de pagina. De wijzigpagina (link in de bevestigingsmail) heeft nog de oude opmaak; dat is bewust, zie "Wat hierna kan".

## Fase 2: Dagstrook

### 1. Git-terminal (Git Bash)

```bash
cd /c/Codes/WPL && git checkout main && git pull && git checkout -b feat/reserveren-dagstrook && git --no-pager log --oneline -3
```

### 2. Prompt voor Cline

```text
Context
Je werkt in C:\Codes\WPL (Flask-app voor restaurantreserveringen, Nederlandse namen). Branch feat/reserveren-dagstrook is actief en komt van main.
Het fasenplan staat in "Fasenplan voor Cline reserveringspagina.md"; lees daarin alleen "Fase 2" en "Bijlage 2". Deze fase: de dagen boven de tijden: een strook die je kunt schuiven met Vandaag en Morgen, een knop Andere dag die de kalender opent, en een dag die dicht staat als er niets meer te boeken valt (zodat het formulier op de eerstvolgende dag met plek begint).

Taak
1. Draai eerst in Git Bash (vanuit de repo-root, venv actief): python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"
   Noteer het getal bij "Ran" als nulmeting. Slaagt niet alles al vóór je begint, stop dan en meld dat.
2. Maak de nieuwe bestanden en pas de bestaande bestanden aan precies zoals in Bijlage 2: nieuwe bestanden en "vervang het hele bestand" met de volledige inhoud; gewijzigde bestanden per blok (regels met - weg, regels met + erbij; de rest is omgeving). Gebruik je bewerk-tool per blok, niet git apply. Past een blok niet, stop dan en meld welk blok.
3. Repo-bestanden gebruiken CRLF: behoud de regeleinden van bestaande bestanden en schrijf nieuwe bestanden ook met CRLF.
4. Draai in Git Bash opnieuw: python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"
   Verwacht: nulmeting + 7 tests, uitslag OK (skipped mag gelijk blijven).

Rapporteer alleen
Wat er gebeurt; verzin niets, verbeter niets en voeg niets toe dat niet in het plan staat.

Beperkingen
- Alleen de bestanden uit Bijlage 2. Geen andere bestanden, geen nieuwe packages, geen refactors.
- Geen git-commando's (geen add, commit, push, branch, merge): de gebruiker doet alle git zelf.
- Geen echte databaseverbinding: gebruik geen DATABASE_URL, geen Neon, geen .env en geen *.db-bestanden; start de app niet tegen een echte database.
- Lees of toon geen .env, .flaskenv, mcp.json of .neon.
- Bij twijfel stop je en vraagt het mij.

Wat je mij meldt
- Lijst van nieuwe en gewijzigde bestanden.
- Nulmeting en eindresultaat van de tests (de regels Ran, OK of FAILED).
- Elke afwijking van het plan, met reden.
```

### 3. Controle-prompt voor Sonnet

```text
Context: Ik werk aan de Flask-app in C:\Codes\WPL. Cline heeft zojuist "Reserveringspagina, fase 2: dagstrook" uitgevoerd
volgens een vast plan. Jij bent de controleur; je wijzigt zelf niets.
Taak (alleen lezen):

1. Draai in Git Bash: git --no-pager status -sb en git --no-pager diff --stat
en git --no-pager diff
2. Lees de gewijzigde en nieuwe bestanden volledig.
3. Draai in Git Bash: python -m unittest discover -s tests -v
4. Controleer de algemene punten hieronder en de extra punten van deze fase.

Algemene punten:

* Alleen de bestanden uit de fase zijn gewijzigd of nieuw; geen andere.
* Geen hele-bestand-diffs door regeleinden (CRLF moet CRLF blijven).
* Geen geheimen, echte URL's, wachtwoorden of klantgegevens in de diff.
* Alle tests slagen; het aantal tests is gestegen met het verwachte aantal.
* Code past bij de stijl van het project (Nederlandse namen, bestaande patronen
zoals _guard en de TestConfig-klassen).
* Niets aan wat de fase niet vraagt (geen extra refactors, geen nieuwe packages).

Rapporteer alleen: GO of NO-GO, dan per punt OK of een concrete bevinding met
bestand:regel. Geen codevoorstellen tenzij bij NO-GO, en dan de kleinste fix.
Beperkingen: niets wijzigen, niets committen, .env/.neon/*.db niet openen,
geen databaseverbinding buiten de tests.
Extra punten voor deze fase:
1. Alleen deze bestanden zijn gewijzigd of nieuw: app/routes/web.py, templates/index.html, static/css/huisstijl.css, vertalingen/en.toml, vertalingen/id.toml en nieuw tests/test_dagstrook.py.
2. In app/routes/web.py is alleen functie _heeft_plek_op toegevoegd en _kiezer aangepast (de dag is open als er nog een tijd te boeken is). Geen route gewijzigd, geen nieuwe import (RegelFout was al geïmporteerd). _kiezer wordt ook door de wijzigpagina gebruikt: tests.test_gast_wijzigen moet slagen.
3. Vertalingen: in en.toml en id.toml zijn precies twee sleutels toegevoegd, "Morgen" en "Andere dag" (de sleutel "Vandaag" bestond al); er is niets verwijderd. "Andere datum?" blijft bestaan (staat als aria-label op het datumveld en wordt ook door de wijzigpagina gebruikt).
4. Het script gebruikt geen innerHTML. De knop "Andere dag" opent de kalender met showPicker(), en valt terug op het zichtbaar maken van het datumveld (klasse zichtbaar) als dat niet kan.
5. De dagknoppen houden hun opmaak class="keuze" data-datum=... aria-pressed="false" (de bestaande tests in tests/test_formulier.py blijven ongewijzigd slagen).
6. static/css/huisstijl.css is alleen aangevuld. De regel fieldset.stap { min-width: 0; position: relative; } geldt voor alle fieldsets met klasse stap (ook op de wijzigpagina): beoordeel of dat daar geen kwaad kan.
7. De grenstests staan er: om 18:59 is vandaag nog open en om 19:01 dicht (laatste tijd 20:00, 60 minuten vooraf); maandag blijft dicht.
8. Het aantal tests is met 7 gestegen ten opzichte van de nulmeting van Cline (na fase 1: 575 naar 582), uitslag OK.
```

### Voor en na de merge

Voor de merge: PR maken; CI `unit-tests` moet groen zijn. Begin pas na de merge en een groene deploy van fase 1.

Na de merge (door de gebruiker):

1. Wacht op de groene Render-deploy.
2. Op je telefoon: de dagen vormen een strook die je met je vinger schuift. De eerste twee heten Vandaag en Morgen; maandag staat grijs met "dicht".
3. Tik op "Andere dag": de kalender opent; kies een datum ver vooruit: de knop toont die datum en de tijden worden geladen.
4. Kijk na 19:00 (laatste boektijd 20:00 min 1 uur vooraf): Vandaag staat grijs en het formulier begint op morgen. (Zie je dit pas morgen, dan is dat ook goed.)
5. De wijzigpagina (link in de bevestigingsmail) moet nog gewoon werken.

## Fase 3: Privacyzin

### 1. Git-terminal (Git Bash)

```bash
cd /c/Codes/WPL && git checkout main && git pull && git checkout -b feat/reserveren-privacyzin && git --no-pager log --oneline -3
```

### 2. Prompt voor Cline

```text
Context
Je werkt in C:\Codes\WPL (Flask-app voor restaurantreserveringen, Nederlandse namen). Branch feat/reserveren-privacyzin is actief en komt van main.
Het fasenplan staat in "Fasenplan voor Cline reserveringspagina.md"; lees daarin alleen "Fase 3" en "Bijlage 3". Deze fase: het vinkje voor de privacyverklaring vervangen door een zin met een link onder de knop. De server eist het veld privacy_akkoord niet meer, maar accepteert het nog wel (een pagina uit de cache stuurt het nog mee). Het vinkje voor de allergie-toestemming blijft zoals het is.

Taak
1. Draai eerst in Git Bash (vanuit de repo-root, venv actief): python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"
   Noteer het getal bij "Ran" als nulmeting. Slaagt niet alles al vóór je begint, stop dan en meld dat.
2. Maak de nieuwe bestanden en pas de bestaande bestanden aan precies zoals in Bijlage 3: nieuwe bestanden en "vervang het hele bestand" met de volledige inhoud; gewijzigde bestanden per blok (regels met - weg, regels met + erbij; de rest is omgeving). Gebruik je bewerk-tool per blok, niet git apply. Past een blok niet, stop dan en meld welk blok.
3. Repo-bestanden gebruiken CRLF: behoud de regeleinden van bestaande bestanden en schrijf nieuwe bestanden ook met CRLF.
4. Draai in Git Bash opnieuw: python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"
   Verwacht: nulmeting + 6 tests, uitslag OK (skipped mag gelijk blijven).

Rapporteer alleen
Wat er gebeurt; verzin niets, verbeter niets en voeg niets toe dat niet in het plan staat.

Beperkingen
- Alleen de bestanden uit Bijlage 3. Geen andere bestanden, geen nieuwe packages, geen refactors.
- Geen git-commando's (geen add, commit, push, branch, merge): de gebruiker doet alle git zelf.
- Geen echte databaseverbinding: gebruik geen DATABASE_URL, geen Neon, geen .env en geen *.db-bestanden; start de app niet tegen een echte database.
- Lees of toon geen .env, .flaskenv, mcp.json of .neon.
- Bij twijfel stop je en vraagt het mij.

Wat je mij meldt
- Lijst van nieuwe en gewijzigde bestanden.
- Nulmeting en eindresultaat van de tests (de regels Ran, OK of FAILED).
- Elke afwijking van het plan, met reden.
```

### 3. Controle-prompt voor Sonnet

```text
Context: Ik werk aan de Flask-app in C:\Codes\WPL. Cline heeft zojuist "Reserveringspagina, fase 3: privacyzin in plaats van vinkje" uitgevoerd
volgens een vast plan. Jij bent de controleur; je wijzigt zelf niets.
Taak (alleen lezen):

1. Draai in Git Bash: git --no-pager status -sb en git --no-pager diff --stat
en git --no-pager diff
2. Lees de gewijzigde en nieuwe bestanden volledig.
3. Draai in Git Bash: python -m unittest discover -s tests -v
4. Controleer de algemene punten hieronder en de extra punten van deze fase.

Algemene punten:

* Alleen de bestanden uit de fase zijn gewijzigd of nieuw; geen andere.
* Geen hele-bestand-diffs door regeleinden (CRLF moet CRLF blijven).
* Geen geheimen, echte URL's, wachtwoorden of klantgegevens in de diff.
* Alle tests slagen; het aantal tests is gestegen met het verwachte aantal.
* Code past bij de stijl van het project (Nederlandse namen, bestaande patronen
zoals _guard en de TestConfig-klassen).
* Niets aan wat de fase niet vraagt (geen extra refactors, geen nieuwe packages).

Rapporteer alleen: GO of NO-GO, dan per punt OK of een concrete bevinding met
bestand:regel. Geen codevoorstellen tenzij bij NO-GO, en dan de kleinste fix.
Beperkingen: niets wijzigen, niets committen, .env/.neon/*.db niet openen,
geen databaseverbinding buiten de tests.
Extra punten voor deze fase:
1. Alleen deze bestanden zijn gewijzigd of nieuw: app/schemas.py, templates/index.html, static/css/huisstijl.css, vertalingen/en.toml, vertalingen/id.toml, tests/test_formulier_compact.py en nieuw tests/test_privacy_zin.py.
2. In app/schemas.py is het veld privacy_akkoord niet verwijderd maar Optional[bool] = None geworden. (Verwijderen zou oudere pagina's laten falen, omdat DTO extra="forbid" heeft.) Verder niets in dat bestand gewijzigd.
3. grep -c "privacy_akkoord" templates/index.html geeft 0, en grep -c "privacyverklaring" templates/index.html geeft minstens 1 (controleer het zoeken zelf met dat tweede patroon, want een 0 kan ook een kapotte pipe zijn).
4. De zin gebruikt th() met de link via een {% set privacylink %}-blok, zodat alleen de link als HTML wordt getoond en de rest wordt ge-escaped, en de zin staat onder de vaste balk, niet erin.
5. Vertalingen: in en.toml en id.toml zijn precies twee sleutels verwijderd ("Ik ga akkoord met het opslaan van mijn gegevens voor deze reservering." en "Lees de") en precies één toegevoegd, "Door te reserveren ga je akkoord met onze {privacy}. Wijzigen of annuleren kan altijd via de link in je mail.", met {privacy} in beide vertalingen. "privacyverklaring" blijft bestaan. tests.test_vertalingen slaagt.
6. Het vinkje voor de allergie-toestemming (id allergie_toestemming) en de bijbehorende tests (tests/test_allergieen.py) zijn ongewijzigd en slagen.
7. Het script stuurt privacy_akkoord niet meer mee; de andere payloadvelden zijn gelijk gebleven.
8. Het aantal tests is met 6 gestegen ten opzichte van de nulmeting van Cline (na fase 2: 582 naar 588), uitslag OK.
```

### Voor en na de merge

Voor de merge: Begin pas als jij (en liefst iemand die verstand heeft van de AVG) hebt bevestigd dat een zin met een link volstaat. HYPOTHESE van Claude: de grondslag is de uitvoering van de reservering, waarvoor geen toestemmingsvinkje nodig is; dat is geen juridisch advies. Je privacyverklaring noemt toestemming nu alleen bij allergieën. Overweeg een aparte kleine wijziging die in de privacyverklaring de grondslag noemt; die zit niet in dit plan.
PR maken; CI `unit-tests` moet groen zijn.

Na de merge (door de gebruiker):

1. Wacht op de groene Render-deploy.
2. Op je telefoon: geen vinkje meer boven de knop; onder de knop staat de zin met een link naar de privacyverklaring (NL, EN, ID).
3. Een reservering zonder vinkje lukt. Vul bij allergieën iets in: het aparte toestemmingsvinkje verschijnt nog en is verplicht.
4. De AI-route (n8n) is niet gewijzigd en werkt zoals voorheen; controleer dat een test via n8n nog slaagt als je dat wilt.

---

# Bijlagen: bestandsinhoud per fase

## Bijlage 1: bestanden van fase 1 (Compact formulier)

#### Nieuwe bestanden en bestanden die je helemaal vervangt

**`tests/test_formulier_compact.py`** (nieuw)

````python
"""Reserveerformulier, compacte opzet (reserveringspagina, fase 1)."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app import create_app
from tests.test_formulier import TestConfig
from tests.test_toegang import TestConfig as TalenConfig


class CompactFormulierTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.html = self.pagina()

    def pagina(self, taal="nl"):
        return self.client.get("/", headers={"Accept-Language": taal}).get_data(as_text=True)

    def test_aantal_is_een_keuzelijst_met_twee_als_start(self):
        keuzelijst = self.html.split('<select id="aantal">')[1].split("</select>")[0]
        opties = re.findall(r'<option value="(\d+)"( selected)?>([^<]+)</option>', keuzelijst)
        self.assertEqual([o[0] for o in opties], [str(n) for n in range(1, 9)])
        self.assertEqual([o[0] for o in opties if o[1]], ["2"])
        self.assertEqual(opties[0][2], "1 persoon")
        self.assertEqual(opties[1][2], "2 personen")
        self.assertNotIn("data-aantal", self.html)

    def test_geen_nummerbadges(self):
        self.assertNotIn('class="nr"', self.html)

    def test_extras_staan_in_een_uitklapblok(self):
        begin = self.html.index('<details class="meer" id="meer">')
        einde = self.html.index("</details>", begin)
        self.assertIn("Nog iets dat we moeten weten?", self.html[begin:einde])
        self.assertIn('id="opmerking"', self.html[begin:einde])
        self.assertNotIn(" open", self.html[begin:begin + 40])  # standaard dicht

    def test_knop_staat_uit_tot_er_een_tijd_is(self):
        self.assertIn('id="submitBtn" class="knop" disabled', self.html)
        self.assertIn('id="samen"', self.html)
        self.assertIn("Kies een tijd", self.html)

    def test_personeel_alleen_in_de_voet(self):
        self.assertEqual(self.html.count('href="/login"'), 1)
        self.assertGreater(self.html.index('href="/login"'), self.html.index("<footer"))

    def test_naam_en_email_zonder_placeholder(self):
        for veld in ("naam", "email"):
            tag = re.search(rf'<input[^>]*id="{veld}"[^>]*>', self.html).group(0)
            self.assertNotIn("placeholder", tag, veld)

    def test_meldingen_per_veld_en_uitleg_bij_telefoon(self):
        for veld in ("naam", "email", "telefoon"):
            self.assertIn(f'id="fout-{veld}" role="alert" hidden', self.html)
        self.assertIn("Alleen voor als we je moeten bereiken", self.html)

    def test_bel_ons_staat_bij_het_aantal(self):
        self.assertIn("Met meer dan 8 personen? Bel", self.html)
        self.assertNotIn("Online tot", self.html)

    def test_privacyvinkje_blijft_in_deze_fase(self):
        self.assertIn('id="privacy_akkoord"', self.html)


class MeertaligFormulierTests(unittest.TestCase):
    """Met [talen] in het restaurantbestand (restaurants/wpl.toml) kiest de gast Nederlands, Engels of Indonesisch."""

    def setUp(self):
        self.client = create_app(TalenConfig).test_client()

    def pagina(self, taal):
        return self.client.get("/", headers={"Accept-Language": taal}).get_data(as_text=True)

    def test_nieuwe_teksten_in_alle_talen(self):
        verwacht = {
            "nl": ("Kies een tijd", "Vul een geldig e-mailadres in."),
            "en": ("Choose a time", "Please enter a valid email address."),
            "id": ("Pilih waktu", "Masukkan alamat email yang valid."),
        }
        for taal, teksten in verwacht.items():
            html = self.pagina(taal)
            for tekst in teksten:
                self.assertTrue(tekst in html, f"{taal}: {tekst}")

    @unittest.skipUnless(shutil.which("node"), "node is niet geïnstalleerd")
    def test_script_is_geldig_javascript(self):
        for taal in ("nl", "en", "id"):
            script = self.pagina(taal).split("<script>")[-1].split("</script>")[0]
            with tempfile.TemporaryDirectory() as map_:
                pad = Path(map_) / "formulier.js"
                pad.write_text(script, encoding="utf-8")
                resultaat = subprocess.run(["node", "--check", str(pad)], capture_output=True, text=True)
            self.assertEqual(resultaat.returncode, 0, f"{taal}: {resultaat.stderr}")


if __name__ == "__main__":
    unittest.main()
````

**`templates/index.html`** (vervang het hele bestand door dit)

````html
{% extends "basis.html" %}
{% block inhoud %}
<div class="kaart">
    <h2>{{ t("Reserveer een tafel") }}</h2>
    <p class="intro">{{ t("Tafel voor") }} {{ zitduur_tekst }} &middot; {{ t("Bevestiging direct per e-mail") }}</p>

    <form id="reserveringsForm" novalidate>
        <!-- HONEYPOT (anti-spam, onzichtbaar voor mensen) -->
        <div hidden aria-hidden="true">
            <label for="website">{{ t("Laat dit veld leeg:") }}</label>
            <input type="text" id="website" name="website" tabindex="-1" autocomplete="off">
        </div>

        <div class="stap">
            <label class="kop-label" for="aantal">{{ t("Met hoeveel personen?") }}</label>
            <div class="kiezer-select">
                <select id="aantal">
                    {% for n in range(1, regels.max_personen_per_boeking + 1) %}
                    <option value="{{ n }}"{{ ' selected' if n == 2 }}>{{ n }} {{ t('persoon') if n == 1 else t('personen') }}</option>
                    {% endfor %}
                </select>
            </div>
            <p class="hint">
                {{ t("Met meer dan {aantal} personen? Bel", aantal=regels.max_personen_per_boeking) }}
                <a href="tel:{{ config.RESTAURANT_TELEFOON }}">{{ config.RESTAURANT_TELEFOON }}</a>.
                {{ t("Dan kun je ook meteen vooraf bestellen.") }}
            </p>
        </div>

        <fieldset class="stap">
            <legend>{{ t("Welke dag?") }}</legend>
            <div class="keuzes dagen" id="dagen">
                {% for d in dagen %}
                <button type="button" class="keuze" data-datum="{{ d.datum }}" aria-pressed="false" {{ 'disabled' if not d.open }}>
                    <small>{{ d.dag | dag_kort }}</small><b>{{ d.dag.day }}</b><small>{{ t('dicht') if not d.open else d.dag | maand_kort }}</small>
                </button>
                {% endfor %}
            </div>
            <p class="klein" style="margin-top: 8px">
                <label for="datum" style="display: inline">{{ t("Andere datum?") }}</label>
                <input type="date" id="datum" min="{{ vandaag }}" max="{{ laatste }}" style="width: auto; height: 34px; margin-left: 6px">
            </p>
        </fieldset>

        <fieldset class="stap">
            <legend>{{ t("Hoe laat?") }}</legend>
            <div id="tijden" aria-live="polite"><p class="leeg">{{ t("Kies eerst een dag.") }}</p></div>
        </fieldset>

        <fieldset class="stap">
            <legend>{{ t("Je gegevens") }}</legend>
            <div class="veld">
                <label for="naam">{{ t("Naam") }}</label>
                <input type="text" id="naam" required minlength="2" maxlength="100" autocomplete="name">
                <p class="fout-tekst" id="fout-naam" role="alert" hidden></p>
            </div>
            <div class="twee">
                <div class="veld">
                    <label for="email">{{ t("E-mailadres") }}</label>
                    <input type="email" id="email" required autocomplete="email" inputmode="email">
                    <p class="fout-tekst" id="fout-email" role="alert" hidden></p>
                </div>
                <div class="veld">
                    <label for="telefoon">{{ t("Telefoonnummer") }}</label>
                    <input type="tel" id="telefoon" required minlength="9" maxlength="20"
                           inputmode="tel" autocomplete="tel" pattern="\+?[0-9][0-9 \-]*"
                           title="{{ t('Vul een geldig telefoonnummer in, bijvoorbeeld 0612345678 of +31 6 12345678.') }}">
                    <p class="fout-tekst" id="fout-telefoon" role="alert" hidden></p>
                    <p class="hint">{{ t("Alleen voor als we je moeten bereiken over je reservering.") }}</p>
                </div>
            </div>
            <details class="meer" id="meer">
                <summary>{{ t("Nog iets dat we moeten weten?") }} <small>({{ t("niet verplicht") }})</small></summary>
                <div class="extra">
                    {% if regels.kinderstoelen %}
                    <div class="veld">
                        <label for="kinderstoelen">{{ t("Kinderstoelen") }}</label>
                        <select id="kinderstoelen">
                            {% for n in range(0, regels.kinderstoelen + 1) %}
                            <option value="{{ n }}">{{ t('Geen') if n == 0 else n }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    {% endif %}
                    {% if regels.vraag_allergieen %}
                    <div class="veld">
                        <label for="allergieen">{{ t("Allergieën") }}</label>
                        <input type="text" id="allergieen" maxlength="200" autocomplete="off"
                               placeholder="{{ t('Bijvoorbeeld: pinda, gluten') }}">
                        <label class="akkoord klein-akkoord" id="allergie_akkoord" hidden>
                            <input type="checkbox" id="allergie_toestemming">
                            <span>{{ t("Ik geef toestemming om deze allergie-informatie te bewaren. Alleen ons personeel ziet het, en we wissen het de dag na mijn bezoek.") }}</span>
                        </label>
                        <p class="fout-tekst" id="fout-allergie" role="alert" hidden></p>
                    </div>
                    {% endif %}
                    <div class="veld">
                        <label for="opmerking">{{ t("Opmerking") }}</label>
                        <textarea id="opmerking" rows="2" maxlength="300"
                                  placeholder="{{ t('Bijvoorbeeld: we vieren een verjaardag, of we bestellen graag vooraf') }}"></textarea>
                    </div>
                </div>
            </details>
        </fieldset>

        <label class="akkoord">
            <input type="checkbox" id="privacy_akkoord" required>
            <span>{{ t("Ik ga akkoord met het opslaan van mijn gegevens voor deze reservering.") }}
                {{ t("Lees de") }} <a href="/privacy" target="_blank">{{ t("privacyverklaring") }}</a>.</span>
        </label>

        <div id="alertBox" class="melding fout" role="alert" hidden></div>
        <div class="actiebalk">
            <div class="samen" id="samen" aria-live="polite"><b>{{ t("Kies een tijd") }}</b></div>
            <button type="submit" id="submitBtn" class="knop" disabled>{{ t("Reservering bevestigen") }}</button>
        </div>
    </form>
</div>
{% endblock %}

{% block scripts %}
<script>
(function () {
    const ZITDUUR = {{ regels.zitduur_minuten | int }};
    const T = {{ {
        'persoon': t('persoon'), 'personen': t('personen'), 'tot': t('tot'), 'lunch': t('Lunch'),
        'diner': t('Diner'), 'vol': t('Vol'), 'nog_plekken': t('Nog {vrij} plekken'),
        'dag_vol': t('Deze dag is vol voor {aantal} personen. Kies een andere dag of bel ons.'),
        'laden': t('Tijden laden…'), 'laden_mislukt': t('Tijden laden lukte niet.'),
        'geen_verbinding': t('Geen verbinding. Probeer het opnieuw.'), 'kalender': t('Kies een datum in de kalender.'),
        'kies_dag_tijd': t('Kies een dag en een tijd.'), 'kies_tijd': t('Kies een tijd'), 'verwerken': t('Verwerken…'),
        'fout': t('Er is een fout opgetreden bij het verzenden.'),
        'netwerk': t('Netwerkfout: kan geen verbinding maken met de server.'),
        'bevestigen': t('Reservering bevestigen'),
        'naam_fout': t('Vul je naam in.'), 'email_fout': t('Vul een geldig e-mailadres in.'),
        'telefoon_fout': t('Vul een geldig telefoonnummer in, bijvoorbeeld 0612345678 of +31 6 12345678.'),
        'allergie_fout': t('Vink aan dat we je allergie-informatie mogen bewaren, of laat het veld leeg. Je kunt het ook bij aankomst aan ons doorgeven.'),
    } | tojson }};
    const keuze = { aantal: 2, datum: null, tijd: null };

    const form = document.getElementById('reserveringsForm');
    const tijdenVak = document.getElementById('tijden');
    const alertBox = document.getElementById('alertBox');
    const samen = document.getElementById('samen');
    const submitBtn = document.getElementById('submitBtn');
    const datumVeld = document.getElementById('datum');
    const aantalVeld = document.getElementById('aantal');
    let verzoek = 0;  // alleen het laatste antwoord van /beschikbaarheid telt
    let bezig = false;

    function druk(groep, knop) {
        document.querySelectorAll('#' + groep + ' .keuze').forEach(function (k) {
            k.setAttribute('aria-pressed', k === knop ? 'true' : 'false');
        });
    }

    // Kort, in de taal van de pagina: "wo 11 nov" / "Wed, 11 Nov" / "Rab, 11 Nov".
    function korteDatum(iso) {
        return new Date(iso + 'T12:00:00').toLocaleDateString(document.documentElement.lang, { weekday: 'short', day: 'numeric', month: 'short' });
    }

    function plus(tijd, minuten) {
        const [u, m] = tijd.split(':').map(Number);
        const totaal = (u * 60 + m + minuten) % (24 * 60);
        return String(Math.floor(totaal / 60)).padStart(2, '0') + ':' + String(totaal % 60).padStart(2, '0');
    }

    // De vaste balk onderaan: wat je gekozen hebt, en de knop die pas aan gaat als er een tijd is.
    function updateBalk() {
        samen.replaceChildren();
        const regel = document.createElement('b');
        if (!keuze.datum || !keuze.tijd) {
            regel.textContent = T.kies_tijd;
            samen.append(regel);
        } else {
            regel.textContent = korteDatum(keuze.datum) + ' · ' + keuze.tijd;
            const onder = document.createElement('small');
            onder.textContent = keuze.aantal + ' ' + (keuze.aantal === 1 ? T.persoon : T.personen) + ' · ' + T.tot + ' ' + plus(keuze.tijd, ZITDUUR);
            samen.append(regel, onder);
        }
        submitBtn.disabled = bezig || !keuze.datum || !keuze.tijd;
    }

    function melding(tekst) {
        keuze.tijd = null;  // zonder tijden is er ook niets gekozen
        tijdenVak.replaceChildren();
        const p = document.createElement('p');
        p.className = 'leeg';
        p.textContent = tekst;
        tijdenVak.append(p);
        updateBalk();
    }

    function tekenTijden(data) {
        tijdenVak.replaceChildren();
        if (!data.open) { melding(data.bericht); return; }
        let groep = null;
        let raster = null;
        if (!data.tijden.some(function (t) { return t.tijd === keuze.tijd && t.beschikbaar; })) { keuze.tijd = null; }
        data.tijden.forEach(function (t) {
            const naam = data.diner_vanaf ? (t.tijd < data.diner_vanaf ? T.lunch : T.diner) : '';
            if (!raster || naam !== groep) {
                groep = naam;
                if (naam) {
                    const kop = document.createElement('div');
                    kop.className = 'groep';
                    kop.textContent = naam;
                    tijdenVak.append(kop);
                }
                raster = document.createElement('div');
                raster.className = 'keuzes tijden';
                tijdenVak.append(raster);
            }
            const knop = document.createElement('button');
            knop.type = 'button';
            knop.className = 'keuze';
            knop.dataset.tijd = t.tijd;
            knop.textContent = t.tijd;
            knop.setAttribute('aria-pressed', t.tijd === keuze.tijd ? 'true' : 'false');
            if (!t.beschikbaar) {
                knop.disabled = true;
                const klein = document.createElement('small');
                klein.textContent = T.vol;
                knop.append(klein);
            } else if (t.vrij <= 10) {
                knop.classList.add('bijna');
                const klein = document.createElement('small');
                klein.textContent = T.nog_plekken.replace('{vrij}', t.vrij);
                knop.append(klein);
            }
            raster.append(knop);
        });
        if (!data.tijden.some(function (t) { return t.beschikbaar; })) {
            const p = document.createElement('p');
            p.className = 'leeg';
            p.textContent = T.dag_vol.replace('{aantal}', keuze.aantal);
            tijdenVak.append(p);
        }
        updateBalk();
    }

    async function laadTijden() {
        if (!keuze.datum) { return; }
        const nummer = ++verzoek;
        melding(T.laden);
        try {
            const antwoord = await fetch('/beschikbaarheid?datum=' + encodeURIComponent(keuze.datum) + '&aantal=' + keuze.aantal);
            const data = await antwoord.json();
            if (nummer !== verzoek) { return; }
            if (!antwoord.ok) { melding(data.bericht || T.laden_mislukt); return; }
            tekenTijden(data);
        } catch (fout) {
            if (nummer === verzoek) { melding(T.geen_verbinding); }
        }
    }

    function kiesDatum(iso, knop) {
        keuze.datum = iso;
        druk('dagen', knop);
        if (knop) { datumVeld.value = ''; }
        updateBalk();
        laadTijden();
    }

    aantalVeld.addEventListener('change', function () {
        keuze.aantal = Number(aantalVeld.value);
        laadTijden();
    });
    document.getElementById('dagen').addEventListener('click', function (e) {
        const knop = e.target.closest('.keuze');
        if (knop && !knop.disabled) { kiesDatum(knop.dataset.datum, knop); }
    });
    datumVeld.addEventListener('change', function () {
        if (!datumVeld.value) { return; }
        const knop = document.querySelector('#dagen .keuze[data-datum="' + datumVeld.value + '"]');
        kiesDatum(datumVeld.value, knop && !knop.disabled ? knop : null);
    });
    tijdenVak.addEventListener('click', function (e) {
        const knop = e.target.closest('.keuze');
        if (!knop || knop.disabled) { return; }
        keuze.tijd = knop.dataset.tijd;
        tijdenVak.querySelectorAll('.keuze').forEach(function (k) {
            k.setAttribute('aria-pressed', k === knop ? 'true' : 'false');
        });
        updateBalk();
    });

    // Begin met de eerste open dag.
    const eerste = document.querySelector('#dagen .keuze:not(:disabled)');
    if (eerste) { kiesDatum(eerste.dataset.datum, eerste); } else { melding(T.kalender); }

    function fout(tekst) {
        alertBox.textContent = tekst;  // textContent: meldingen van de server worden nooit als HTML uitgevoerd
        alertBox.hidden = false;
    }

    // Een melding onder één veld; een lege tekst haalt de melding weg. Geeft true als het veld goed is.
    function veldMelding(id, tekst) {
        const veld = document.getElementById(id);
        const plek = document.getElementById('fout-' + id);
        if (!veld || !plek) { return !tekst; }
        plek.textContent = tekst;  // textContent, zoals bij alle meldingen
        plek.hidden = !tekst;
        veld.classList.toggle('ongeldig', !!tekst);
        veld.setAttribute('aria-invalid', tekst ? 'true' : 'false');
        return !tekst;
    }

    // Dezelfde eisen als de server (app/schemas.py); de server blijft de baas.
    const CONTROLES = {
        naam: function (w) { return w.trim().length >= 2 && /\p{L}/u.test(w) ? '' : T.naam_fout; },
        email: function (w) { return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(w.trim()) ? '' : T.email_fout; },
        telefoon: function (w) {
            const cijfers = w.replace(/\D/g, '').length;
            return /^\+?[0-9][0-9 \-]*$/.test(w.trim()) && cijfers >= 9 && cijfers <= 15 ? '' : T.telefoon_fout;
        }
    };
    Object.keys(CONTROLES).forEach(function (id) {
        const veld = document.getElementById(id);
        veld.addEventListener('blur', function () { if (veld.value !== '') { veldMelding(id, CONTROLES[id](veld.value)); } });
        veld.addEventListener('input', function () { if (veld.classList.contains('ongeldig')) { veldMelding(id, CONTROLES[id](veld.value)); } });
    });

    const kinderstoelVeld = document.getElementById('kinderstoelen');  // ontbreekt als het restaurant er geen heeft
    const allergieVeld = document.getElementById('allergieen');        // ontbreekt als het restaurant er niet naar vraagt
    if (allergieVeld) {
        // De toestemming verschijnt pas als er iets is ingevuld, en is dan verplicht.
        const akkoord = document.getElementById('allergie_akkoord');
        const vinkje = document.getElementById('allergie_toestemming');
        allergieVeld.addEventListener('input', function () {
            const ingevuld = allergieVeld.value.trim() !== '';
            akkoord.hidden = !ingevuld;
            vinkje.required = ingevuld;
            if (!ingevuld) { vinkje.checked = false; veldMelding('allergie', ''); }
        });
    }

    form.addEventListener('submit', async function (e) {
        e.preventDefault();
        alertBox.hidden = true;
        if (!keuze.datum || !keuze.tijd) { fout(T.kies_dag_tijd); return; }

        let eersteFout = null;
        Object.keys(CONTROLES).forEach(function (id) {
            const veld = document.getElementById(id);
            if (!veldMelding(id, CONTROLES[id](veld.value)) && !eersteFout) { eersteFout = veld; }
        });
        if (allergieVeld && allergieVeld.value.trim() !== '' && !document.getElementById('allergie_toestemming').checked) {
            veldMelding('allergie', T.allergie_fout);
            document.getElementById('meer').open = true;
            if (!eersteFout) { eersteFout = allergieVeld; }
        }
        if (eersteFout) { eersteFout.focus(); return; }
        if (!form.reportValidity()) { return; }  // o.a. het vinkje voor de privacyverklaring

        bezig = true;
        updateBalk();
        submitBtn.textContent = T.verwerken;
        const payload = {
            naam: document.getElementById('naam').value.trim(),
            email: document.getElementById('email').value.trim(),
            telefoon: document.getElementById('telefoon').value.trim(),
            datum: keuze.datum,
            tijd: keuze.tijd,
            aantal: keuze.aantal,  // Integer voor Pydantic
            website: document.getElementById('website').value,  // honeypot
            privacy_akkoord: document.getElementById('privacy_akkoord').checked,  // Boolean
            opmerking: document.getElementById('opmerking').value.trim(),
            kinderstoelen: kinderstoelVeld ? parseInt(kinderstoelVeld.value, 10) : 0,
            allergieen: allergieVeld ? allergieVeld.value.trim() : '',
            allergie_toestemming: allergieVeld ? document.getElementById('allergie_toestemming').checked : false
        };
        try {
            const antwoord = await fetch('/reservering', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content
                },
                body: JSON.stringify(payload)
            });
            const result = await antwoord.json();
            if (antwoord.ok && result.status === 'succes') {
                window.location.href = '/bevestiging';
                return;
            }
            fout(result.bericht || T.fout);
            (result.velden || []).forEach(function (id) {
                const veld = document.getElementById(id);
                if (veld && CONTROLES[id]) { veld.classList.add('ongeldig'); veld.setAttribute('aria-invalid', 'true'); }
            });
            laadTijden();  // misschien is de tijd net vol geraakt
        } catch (err) {
            fout(T.netwerk);
        } finally {
            bezig = false;
            submitBtn.textContent = T.bevestigen;
            updateBalk();
        }
    });
})();
</script>
{% endblock %}
````

#### Gewijzigde bestanden (regels met `-` weg, regels met `+` erbij; de rest is omgeving)

**`static/css/huisstijl.css`**

````diff
@@ -243,6 +243,35 @@ textarea { height: auto; min-height: 64px; padding: 10px 12px; resize: vertical;
 .account details form { display: flex; gap: 8px; margin-top: 8px; }
 .account details input { flex: 1; min-width: 0; }
 
+/* Reserveerformulier: compact, met een vaste balk onderaan */
+.intro { color: var(--zacht); font-size: 13px; margin: 6px 0 22px; }
+.kop-label { display: block; font-size: 13px; font-weight: 600; color: var(--tekst); margin-bottom: 8px; }
+.kiezer-select { position: relative; }
+.kiezer-select select { appearance: none; -webkit-appearance: none; padding-right: 38px; font-size: 15px; font-weight: 500; }
+.kiezer-select::after { content: ""; position: absolute; right: 15px; top: 50%; width: 7px; height: 7px; margin-top: -6px;
+                        border-right: 2px solid var(--zacht); border-bottom: 2px solid var(--zacht); transform: rotate(45deg);
+                        pointer-events: none; }
+.hint { color: var(--zacht); font-size: 12px; margin-top: 6px; line-height: 1.5; }
+.hint a { color: var(--zacht); }
+.fout-tekst { color: #f2b8b8; font-size: 12px; margin-top: 5px; }
+input.ongeldig, textarea.ongeldig { border-color: var(--rood); }
+details.meer { border-top: 1px solid var(--lijn); padding-top: 14px; }
+details.meer > summary { cursor: pointer; list-style: none; color: var(--accent); font-size: 13.5px; font-weight: 500; }
+details.meer > summary::-webkit-details-marker { display: none; }
+details.meer > summary::before { content: "+ "; }
+details.meer[open] > summary::before { content: "\2212  "; }
+details.meer > summary small { color: var(--zacht); font-weight: 400; }
+details.meer .extra { margin-top: 14px; }
+.actiebalk { position: sticky; bottom: 0; display: flex; align-items: center; gap: 14px; margin: 22px -28px 0; padding: 14px 28px;
+             background: linear-gradient(to top, rgba(20, 16, 12, .98) 70%, rgba(20, 16, 12, 0)); }
+.actiebalk .samen { flex: 1; min-width: 0; line-height: 1.3; }
+.actiebalk .samen b { display: block; font-size: 14.5px; }
+.actiebalk .samen small { color: var(--zacht); font-size: 12px; }
+.actiebalk .knop { width: auto; flex: none; min-width: 130px; max-width: 46%; min-height: 52px; padding: 0 12px; font-size: 14.5px;
+                   line-height: 1.2; text-align: center; }
+footer.voet .personeel { opacity: .7; }
+@media (max-width: 480px) { .actiebalk { gap: 10px; margin-left: -18px; margin-right: -18px; padding-left: 18px; padding-right: 18px; } }
+
 @media (max-width: 700px) {
     .tellers { grid-template-columns: 1fr 1fr; }
     .res { grid-template-columns: 40px 1fr; row-gap: 8px; }
````

**`templates/basis.html`**

````diff
@@ -42,6 +42,7 @@
     · <a href="mailto:{{ config.RESTAURANT_EMAIL }}">{{ config.RESTAURANT_EMAIL }}</a>
     · <a href="tel:{{ config.RESTAURANT_TELEFOON }}">{{ config.RESTAURANT_TELEFOON }}</a>
     · <a href="/privacy">{{ t('Privacy') }}</a>
+    · <a href="/login" class="personeel">{{ t('Personeel') }}</a>
 </footer>
 {% endblock %}
 {% block scripts %}{% endblock %}
````

**`tests/test_extra_wensen.py`**

````diff
@@ -73,7 +73,8 @@ class FormulierTests(Basis):
     def test_velden_op_het_formulier(self):
         html = self.client.get("/").get_data(as_text=True)
         self.assertIn('<select id="kinderstoelen">', html)
-        self.assertEqual(html.count("<option value="), 3)  # Geen, 1, 2
+        kinderstoelen = html.split('<select id="kinderstoelen">')[1].split("</select>")[0]
+        self.assertEqual(kinderstoelen.count("<option value="), 3)  # Geen, 1, 2
         self.assertIn('<textarea id="opmerking"', html)
         self.assertIn('maxlength="300"', html)
 
````

**`tests/test_formulier.py`**

````diff
@@ -1,3 +1,4 @@
+import re
 import unittest
 from datetime import timedelta
 
@@ -27,7 +28,7 @@ class FormulierTests(unittest.TestCase):
                       'id="tijden"', "/beschikbaarheid?datum=", "Reservering bevestigen"):
             with self.subTest(tekst=tekst):
                 self.assertIn(tekst, self.html)
-        self.assertEqual(self.html.count('class="keuze" data-aantal='), 8)
+        self.assertEqual(len(re.findall(r'<option value="\d+"', self.html.split('id="aantal"')[1].split("</select>")[0])), 8)
 
     def test_zeven_dagen_met_gesloten_maandag(self):
         self.assertEqual(self.html.count('class="keuze" data-datum='), 7)
````

**`tests/test_regels_in_routes.py`**

````diff
@@ -102,8 +102,8 @@ class RegelsInRoutesTests(unittest.TestCase):
 
     def test_formulier_toont_slot_en_maximum(self):
         html = self.client.get("/").get_data(as_text=True)
-        self.assertIn('data-aantal="6"', html)  # personen-knoppen 1 t/m max_personen_per_boeking
-        self.assertNotIn('data-aantal="7"', html)
+        self.assertIn('<option value="6"', html)  # keuzelijst 1 t/m max_personen_per_boeking
+        self.assertNotIn('<option value="7"', html)
 
 
 if __name__ == "__main__":
````

**`tests/test_wpl_regels.py`**

````diff
@@ -64,7 +64,8 @@ class WplRegelsTests(unittest.TestCase):
 
     def test_formulier(self):
         html = self.client.get("/").get_data(as_text=True)
-        self.assertEqual(html.count('class="keuze" data-aantal='), 15)
+        aantal = html.split('<select id="aantal">')[1].split("</select>")[0]
+        self.assertEqual(aantal.count("<option value="), 15)
         self.assertIn("1 uur", html)
         self.assertNotIn("1,5 uur", html)
         self.assertIn("const ZITDUUR = 60;", html)
````

**`vertalingen/en.toml`**

````diff
@@ -170,13 +170,14 @@
 "Personeel" = "Staff"
 "Reserveer een tafel" = "Book a table"
 "Tafel voor" = "Table for"
-"Online tot" = "Online up to"
+"Kies een tijd" = "Choose a time"
+"Vul een geldig e-mailadres in." = "Please enter a valid email address."
+"Alleen voor als we je moeten bereiken over je reservering." = "Only in case we need to reach you about your booking."
+"Bevestiging direct per e-mail" = "Confirmation by email right away"
 "{aantal} personen" = "{aantal} people"
 "Laat dit veld leeg:" = "Leave this field empty:"
 "Je gegevens" = "Your details"
-"Jan Jansen" = "Jane Smith"
 "E-mailadres" = "Email address"
-"naam@voorbeeld.nl" = "name@example.com"
 "Telefoonnummer" = "Phone number"
 "Nog iets dat we moeten weten?" = "Anything else we should know?"
 "niet verplicht" = "optional"
````

**`vertalingen/id.toml`**

````diff
@@ -170,13 +170,14 @@
 "Personeel" = "Staf"
 "Reserveer een tafel" = "Pesan meja"
 "Tafel voor" = "Meja selama"
-"Online tot" = "Online hingga"
+"Kies een tijd" = "Pilih waktu"
+"Vul een geldig e-mailadres in." = "Masukkan alamat email yang valid."
+"Alleen voor als we je moeten bereiken over je reservering." = "Hanya jika kami perlu menghubungi Anda tentang reservasi Anda."
+"Bevestiging direct per e-mail" = "Konfirmasi langsung lewat email"
 "{aantal} personen" = "{aantal} orang"
 "Laat dit veld leeg:" = "Biarkan kolom ini kosong:"
 "Je gegevens" = "Data Anda"
-"Jan Jansen" = "Budi Santoso"
 "E-mailadres" = "Alamat email"
-"naam@voorbeeld.nl" = "nama@contoh.com"
 "Telefoonnummer" = "Nomor telepon"
 "Nog iets dat we moeten weten?" = "Ada hal lain yang perlu kami ketahui?"
 "niet verplicht" = "tidak wajib"
````


## Bijlage 2: bestanden van fase 2 (Dagstrook)

#### Nieuwe bestanden en bestanden die je helemaal vervangt

**`tests/test_dagstrook.py`** (nieuw)

````python
"""Reserveerformulier: de dagen boven de tijden (reserveringspagina, fase 2)."""
import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from app import create_app
from app.reserveringsregels import ReserveringsRegels
from tests.test_toegang import TestConfig  # restaurants/wpl.toml: di t/m zo 12:00 tot 20:00, maandag dicht, 60 min vooruit

AMS = ZoneInfo("Europe/Amsterdam")
DINSDAG = "2030-01-01"
WOENSDAG = "2030-01-02"


class DagstrookTests(unittest.TestCase):
    def pagina(self, nu, taal="nl"):
        patcher = mock.patch.object(ReserveringsRegels, "nu", lambda self: nu)
        patcher.start()
        self.addCleanup(patcher.stop)
        client = create_app(TestConfig).test_client()
        return client.get("/", headers={"Accept-Language": taal}).get_data(as_text=True)

    def knop(self, datum, html):
        """De openingstag van de dagknop met deze datum, bijvoorbeeld 'aria-pressed="false" disabled'."""
        begin = html.index(f'data-datum="{datum}"')
        return html[begin:html.index(">", begin)]

    def test_vandaag_en_morgen_als_label(self):
        html = self.pagina(datetime(2030, 1, 1, 10, 0, tzinfo=AMS))
        self.assertIn("<small>Vandaag</small><b>1</b>", html)
        self.assertIn("<small>Morgen</small><b>2</b>", html)
        self.assertIn("<small>vr</small><b>4</b>", html)  # daarna de weekdag

    def test_labels_in_alle_talen(self):
        nu = datetime(2030, 1, 1, 10, 0, tzinfo=AMS)
        for taal, (vandaag, morgen) in {"en": ("Today", "Tomorrow"), "id": ("Hari ini", "Besok")}.items():
            html = self.pagina(nu, taal)
            self.assertTrue(f"<small>{vandaag}</small><b>1</b>" in html, taal)
            self.assertTrue(f"<small>{morgen}</small><b>2</b>" in html, taal)

    def test_vandaag_is_open_overdag(self):
        html = self.pagina(datetime(2030, 1, 1, 10, 0, tzinfo=AMS))
        self.assertNotIn("disabled", self.knop(DINSDAG, html))

    def test_vandaag_dicht_als_er_niets_meer_kan(self):
        html = self.pagina(datetime(2030, 1, 1, 21, 0, tzinfo=AMS))
        self.assertIn("disabled", self.knop(DINSDAG, html))
        self.assertNotIn("disabled", self.knop(WOENSDAG, html))

    def test_grens_een_uur_voor_de_laatste_tijd(self):
        # De laatste tijd is 20:00 en je moet 60 minuten van tevoren boeken.
        open_ = self.pagina(datetime(2030, 1, 1, 18, 59, tzinfo=AMS))
        dicht = self.pagina(datetime(2030, 1, 1, 19, 1, tzinfo=AMS))
        self.assertNotIn("disabled", self.knop(DINSDAG, open_))
        self.assertIn("disabled", self.knop(DINSDAG, dicht))

    def test_maandag_blijft_dicht(self):
        html = self.pagina(datetime(2030, 1, 5, 10, 0, tzinfo=AMS))  # zaterdag; maandag 7 januari valt in de strook
        self.assertIn("disabled", self.knop("2030-01-07", html))

    def test_andere_dag_met_verborgen_datumveld(self):
        html = self.pagina(datetime(2030, 1, 1, 10, 0, tzinfo=AMS))
        self.assertIn('id="andere"', html)
        self.assertIn('id="datum" class="datumveld"', html)
        self.assertIn('min="2030-01-01"', html)
        self.assertNotIn("innerHTML", html)
        self.assertNotIn('class="keuzes dagen"', html)


if __name__ == "__main__":
    unittest.main()
````

#### Gewijzigde bestanden (regels met `-` weg, regels met `+` erbij; de rest is omgeving)

**`app/routes/web.py`**

````diff
@@ -76,14 +76,24 @@ def kies_taal(code):
         )
     return antwoord
 
+def _heeft_plek_op(regels, dag, nu):
+    """True als er op deze dag nog een tijd is die online geboekt mag worden (open, niet te laat, niet te ver vooruit)."""
+    for tijdstip in regels.knoptijden_op(dag):
+        try:
+            regels.controleer(dag, tijdstip, 1, nu=nu)
+        except RegelFout:
+            continue
+        return True
+    return False
+
 def _kiezer(regels):
     """Wat de knoppen voor personen, dag en tijd nodig hebben (reserveren en wijzigen)."""
-    vandaag = regels.nu().date()
+    nu = regels.nu()
+    vandaag = nu.date()
     dagen = []
     for i in range(DAGEN_IN_STRIP):
         dag = vandaag + timedelta(days=i)
-        dagen.append({'datum': dag.isoformat(), 'dag': dag,
-                      'open': bool(regels.blokken_op(dag)) and dag not in regels.sluitingsdagen})
+        dagen.append({'datum': dag.isoformat(), 'dag': dag, 'open': _heeft_plek_op(regels, dag, nu)})
     laatste = vandaag + timedelta(days=regels.max_dagen_vooruit)
     taal = huidige_taal()
     return {'regels': regels, 'dagen': dagen, 'vandaag': vandaag.isoformat(), 'laatste': laatste.isoformat(),
````

**`static/css/huisstijl.css`**

````diff
@@ -270,6 +270,15 @@ details.meer .extra { margin-top: 14px; }
 .actiebalk .knop { width: auto; flex: none; min-width: 130px; max-width: 46%; min-height: 52px; padding: 0 12px; font-size: 14.5px;
                    line-height: 1.2; text-align: center; }
 footer.voet .personeel { opacity: .7; }
+fieldset.stap { min-width: 0; position: relative; }  /* min-width: anders rekt de fieldset mee met de dagstrook i.p.v. die te laten scrollen */
+.dagrij { display: flex; gap: 8px; overflow-x: auto; padding: 2px 2px 8px; margin: 0 -2px; scroll-snap-type: x proximity; scrollbar-width: none; }
+.dagrij::-webkit-scrollbar { display: none; }
+.dagrij .keuze { flex: 1 0 56px; min-height: 66px; scroll-snap-align: start; }
+.dagrij .keuze span { display: flex; flex-direction: column; align-items: center; line-height: 1.25; }
+.dagrij #andere svg { width: 20px; height: 20px; margin-bottom: 2px; }
+.datumveld { position: absolute; left: 0; top: 0; opacity: 0; pointer-events: none; width: 1px; height: 1px; }
+.datumveld.zichtbaar { position: static; opacity: 1; pointer-events: auto; width: auto; height: 40px; margin-top: 8px; }
+@media (max-width: 480px) { .dagrij { margin: 0 -18px; padding: 2px 18px 8px; } .dagrij .keuze { flex: none; width: 66px; } }
 @media (max-width: 480px) { .actiebalk { gap: 10px; margin-left: -18px; margin-right: -18px; padding-left: 18px; padding-right: 18px; } }
 
 @media (max-width: 700px) {
````

**`templates/index.html`**

````diff
@@ -29,17 +29,21 @@
 
         <fieldset class="stap">
             <legend>{{ t("Welke dag?") }}</legend>
-            <div class="keuzes dagen" id="dagen">
+            <div class="dagrij" id="dagen">
                 {% for d in dagen %}
                 <button type="button" class="keuze" data-datum="{{ d.datum }}" aria-pressed="false" {{ 'disabled' if not d.open }}>
-                    <small>{{ d.dag | dag_kort }}</small><b>{{ d.dag.day }}</b><small>{{ t('dicht') if not d.open else d.dag | maand_kort }}</small>
+                    <small>{{ t('Vandaag') if loop.first else (t('Morgen') if loop.index == 2 else d.dag | dag_kort) }}</small><b>{{ d.dag.day }}</b><small>{{ t('dicht') if not d.open else d.dag | maand_kort }}</small>
                 </button>
                 {% endfor %}
+                <button type="button" class="keuze" id="andere" aria-pressed="false">
+                    <span id="andere-leeg">
+                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3.5" y="5" width="17" height="15" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/></svg>
+                        <small>{{ t("Andere dag") }}</small>
+                    </span>
+                    <span id="andere-gekozen" hidden><small id="andere-dag"></small><b id="andere-nr"></b><small id="andere-maand"></small></span>
+                </button>
             </div>
-            <p class="klein" style="margin-top: 8px">
-                <label for="datum" style="display: inline">{{ t("Andere datum?") }}</label>
-                <input type="date" id="datum" min="{{ vandaag }}" max="{{ laatste }}" style="width: auto; height: 34px; margin-left: 6px">
-            </p>
+            <input type="date" id="datum" class="datumveld" min="{{ vandaag }}" max="{{ laatste }}" aria-label="{{ t('Andere datum?') }}">
         </fieldset>
 
         <fieldset class="stap">
@@ -145,6 +149,7 @@
     const submitBtn = document.getElementById('submitBtn');
     const datumVeld = document.getElementById('datum');
     const aantalVeld = document.getElementById('aantal');
+    const andere = document.getElementById('andere');
     let verzoek = 0;  // alleen het laatste antwoord van /beschikbaarheid telt
     let bezig = false;
 
@@ -254,10 +259,23 @@
         }
     }
 
+    // De knop "Andere dag" toont de gekozen datum als die niet bij de dagen ernaast hoort.
+    function toonAndere(iso) {
+        document.getElementById('andere-leeg').hidden = !!iso;
+        document.getElementById('andere-gekozen').hidden = !iso;
+        if (!iso) { return; }
+        const d = new Date(iso + 'T12:00:00');
+        const taal = document.documentElement.lang;
+        document.getElementById('andere-dag').textContent = d.toLocaleDateString(taal, { weekday: 'short' });
+        document.getElementById('andere-nr').textContent = d.getDate();
+        document.getElementById('andere-maand').textContent = d.toLocaleDateString(taal, { month: 'short' });
+    }
+
     function kiesDatum(iso, knop) {
         keuze.datum = iso;
-        druk('dagen', knop);
-        if (knop) { datumVeld.value = ''; }
+        druk('dagen', knop || andere);
+        toonAndere(knop ? null : iso);
+        if (knop) { datumVeld.value = ''; } else { andere.scrollIntoView({ inline: 'nearest', block: 'nearest' }); }
         updateBalk();
         laadTijden();
     }
@@ -268,7 +286,16 @@
     });
     document.getElementById('dagen').addEventListener('click', function (e) {
         const knop = e.target.closest('.keuze');
-        if (knop && !knop.disabled) { kiesDatum(knop.dataset.datum, knop); }
+        if (!knop || knop.disabled) { return; }
+        if (knop === andere) {
+            if (typeof datumVeld.showPicker === 'function') {
+                try { datumVeld.showPicker(); return; } catch (fout) { /* dan het gewone veld hieronder */ }
+            }
+            datumVeld.classList.add('zichtbaar');  // oudere browsers: toon het datumveld zelf
+            datumVeld.focus();
+            return;
+        }
+        kiesDatum(knop.dataset.datum, knop);
     });
     datumVeld.addEventListener('change', function () {
         if (!datumVeld.value) { return; }
@@ -286,7 +313,7 @@
     });
 
     // Begin met de eerste open dag.
-    const eerste = document.querySelector('#dagen .keuze:not(:disabled)');
+    const eerste = document.querySelector('#dagen .keuze[data-datum]:not(:disabled)');
     if (eerste) { kiesDatum(eerste.dataset.datum, eerste); } else { melding(T.kalender); }
 
     function fout(tekst) {
````

**`vertalingen/en.toml`**

````diff
@@ -217,6 +217,8 @@
 "Reserveringen" = "Bookings"
 "Vorige dag" = "Previous day"
 "Vandaag" = "Today"
+"Morgen" = "Tomorrow"
+"Andere dag" = "Other day"
 "Volgende dag" = "Next day"
 "Kies datum" = "Choose date"
 "Tonen" = "Show"
````

**`vertalingen/id.toml`**

````diff
@@ -217,6 +217,8 @@
 "Reserveringen" = "Reservasi"
 "Vorige dag" = "Hari sebelumnya"
 "Vandaag" = "Hari ini"
+"Morgen" = "Besok"
+"Andere dag" = "Hari lain"
 "Volgende dag" = "Hari berikutnya"
 "Kies datum" = "Pilih tanggal"
 "Tonen" = "Tampilkan"
````


## Bijlage 3: bestanden van fase 3 (Privacyzin)

#### Nieuwe bestanden en bestanden die je helemaal vervangt

**`tests/test_privacy_zin.py`** (nieuw)

````python
"""Reserveerformulier: een zin over de privacyverklaring in plaats van een vinkje (reserveringspagina, fase 3)."""
import unittest

from tests.test_talen import ZATERDAG, Basis


class PrivacyZinTests(Basis):
    def boek(self, **velden):
        data = {"naam": "Siti Rahma", "email": "siti@example.com", "telefoon": "0612345678", "datum": ZATERDAG,
                "tijd": "19:00", "aantal": 2, **velden}
        return self.client.post("/reservering", json=data)

    def test_zin_met_link_in_alle_talen(self):
        verwacht = {
            "nl": "Door te reserveren ga je akkoord met onze",
            "en": "By booking you agree to our",
            "id": "Dengan memesan, Anda menyetujui",
        }
        for taal, begin in verwacht.items():
            html = self.pagina(**{"Accept-Language": taal})
            self.assertTrue(begin in html, taal)
            self.assertTrue('<a href="/privacy" target="_blank">' in html, taal)
            self.assertFalse('id="privacy_akkoord"' in html, taal)

    def test_zin_staat_onder_de_knop_en_niet_in_de_vaste_balk(self):
        html = self.pagina(**{"Accept-Language": "nl"})
        balk_einde = html.index("</div>", html.index('id="submitBtn"'))
        self.assertGreater(html.index('class="juridisch"'), balk_einde)

    def test_reserveren_zonder_privacy_akkoord(self):
        antwoord = self.boek()
        self.assertEqual(antwoord.status_code, 200, antwoord.get_json())
        self.assertEqual(antwoord.get_json()["status"], "succes")

    def test_oudere_pagina_met_privacy_akkoord_blijft_werken(self):
        for waarde, email in ((True, "a@example.com"), (False, "b@example.com")):
            antwoord = self.boek(privacy_akkoord=waarde, email=email, telefoon=f"06{abs(hash(email)) % 10**8:08d}")
            self.assertEqual(antwoord.status_code, 200, antwoord.get_json())

    def test_onzin_in_privacy_akkoord_wordt_geweigerd(self):
        antwoord = self.boek(privacy_akkoord="misschien")
        self.assertEqual(antwoord.status_code, 422)

    def test_onbekend_veld_blijft_geweigerd(self):
        self.assertEqual(self.boek(iets_anders=1).status_code, 422)


if __name__ == "__main__":
    unittest.main()
````

#### Gewijzigde bestanden (regels met `-` weg, regels met `+` erbij; de rest is omgeving)

**`app/schemas.py`**

````diff
@@ -95,7 +95,7 @@ class ReserveringSchema(DTO):
     tijd: ISOTime
     aantal: int = Field(..., ge=1, le=20, validation_alias=AliasChoices("aantal", "aantal_personen"))
     website: Optional[str] = None
-    privacy_akkoord: Literal[True]
+    privacy_akkoord: Optional[bool] = None  # niet meer nodig; oudere pagina's sturen het nog mee
     opmerking: Opmerking = None
     kinderstoelen: int = Field(default=0, ge=0, le=20)
     allergieen: Allergieen = None
````

**`static/css/huisstijl.css`**

````diff
@@ -270,6 +270,7 @@ details.meer .extra { margin-top: 14px; }
 .actiebalk .knop { width: auto; flex: none; min-width: 130px; max-width: 46%; min-height: 52px; padding: 0 12px; font-size: 14.5px;
                    line-height: 1.2; text-align: center; }
 footer.voet .personeel { opacity: .7; }
+.juridisch { text-align: center; font-size: 12px; color: var(--zacht); line-height: 1.55; margin-top: 10px; }
 fieldset.stap { min-width: 0; position: relative; }  /* min-width: anders rekt de fieldset mee met de dagstrook i.p.v. die te laten scrollen */
 .dagrij { display: flex; gap: 8px; overflow-x: auto; padding: 2px 2px 8px; margin: 0 -2px; scroll-snap-type: x proximity; scrollbar-width: none; }
 .dagrij::-webkit-scrollbar { display: none; }
````

**`templates/index.html`**

````diff
@@ -107,17 +107,13 @@
             </details>
         </fieldset>
 
-        <label class="akkoord">
-            <input type="checkbox" id="privacy_akkoord" required>
-            <span>{{ t("Ik ga akkoord met het opslaan van mijn gegevens voor deze reservering.") }}
-                {{ t("Lees de") }} <a href="/privacy" target="_blank">{{ t("privacyverklaring") }}</a>.</span>
-        </label>
-
         <div id="alertBox" class="melding fout" role="alert" hidden></div>
         <div class="actiebalk">
             <div class="samen" id="samen" aria-live="polite"><b>{{ t("Kies een tijd") }}</b></div>
             <button type="submit" id="submitBtn" class="knop" disabled>{{ t("Reservering bevestigen") }}</button>
         </div>
+        {% set privacylink %}<a href="/privacy" target="_blank">{{ t("privacyverklaring") }}</a>{% endset %}
+        <p class="juridisch">{{ th("Door te reserveren ga je akkoord met onze {privacy}. Wijzigen of annuleren kan altijd via de link in je mail.", privacy=privacylink) }}</p>
     </form>
 </div>
 {% endblock %}
@@ -378,7 +374,7 @@
             if (!eersteFout) { eersteFout = allergieVeld; }
         }
         if (eersteFout) { eersteFout.focus(); return; }
-        if (!form.reportValidity()) { return; }  // o.a. het vinkje voor de privacyverklaring
+        if (!form.reportValidity()) { return; }
 
         bezig = true;
         updateBalk();
@@ -391,7 +387,6 @@
             tijd: keuze.tijd,
             aantal: keuze.aantal,  // Integer voor Pydantic
             website: document.getElementById('website').value,  // honeypot
-            privacy_akkoord: document.getElementById('privacy_akkoord').checked,  // Boolean
             opmerking: document.getElementById('opmerking').value.trim(),
             kinderstoelen: kinderstoelVeld ? parseInt(kinderstoelVeld.value, 10) : 0,
             allergieen: allergieVeld ? allergieVeld.value.trim() : '',
````

**`tests/test_formulier_compact.py`**

````diff
@@ -62,8 +62,8 @@ class CompactFormulierTests(unittest.TestCase):
         self.assertIn("Met meer dan 8 personen? Bel", self.html)
         self.assertNotIn("Online tot", self.html)
 
-    def test_privacyvinkje_blijft_in_deze_fase(self):
-        self.assertIn('id="privacy_akkoord"', self.html)
+    def test_geen_privacyvinkje_meer(self):
+        self.assertNotIn('id="privacy_akkoord"', self.html)
 
 
 class MeertaligFormulierTests(unittest.TestCase):
````

**`vertalingen/en.toml`**

````diff
@@ -185,9 +185,8 @@
 "Bijvoorbeeld: pinda, gluten" = "For example: peanuts, gluten"
 "Ik geef toestemming om deze allergie-informatie te bewaren. Alleen ons personeel ziet het, en we wissen het de dag na mijn bezoek." = "I agree that this allergy information may be stored. Only our staff can see it, and it is deleted the day after my visit."
 "Bijvoorbeeld: we vieren een verjaardag, of we bestellen graag vooraf" = "For example: we're celebrating a birthday, or we'd like to order in advance"
-"Ik ga akkoord met het opslaan van mijn gegevens voor deze reservering." = "I agree that my details are stored for this booking."
-"Lees de" = "Read the"
 "privacyverklaring" = "privacy statement"
+"Door te reserveren ga je akkoord met onze {privacy}. Wijzigen of annuleren kan altijd via de link in je mail." = "By booking you agree to our {privacy}. You can always change or cancel via the link in your email."
 "Reservering bevestigen" = "Confirm booking"
 "Met meer dan {aantal} personen? Bel" = "More than {aantal} people? Call"
 "Dan kun je ook meteen vooraf bestellen." = "You can also order your food in advance."
````

**`vertalingen/id.toml`**

````diff
@@ -185,9 +185,8 @@
 "Bijvoorbeeld: pinda, gluten" = "Misalnya: kacang, gluten"
 "Ik geef toestemming om deze allergie-informatie te bewaren. Alleen ons personeel ziet het, en we wissen het de dag na mijn bezoek." = "Saya setuju informasi alergi ini disimpan. Hanya staf kami yang dapat melihatnya, dan informasi ini dihapus sehari setelah kunjungan saya."
 "Bijvoorbeeld: we vieren een verjaardag, of we bestellen graag vooraf" = "Misalnya: kami merayakan ulang tahun, atau kami ingin memesan makanan terlebih dahulu"
-"Ik ga akkoord met het opslaan van mijn gegevens voor deze reservering." = "Saya setuju data saya disimpan untuk reservasi ini."
-"Lees de" = "Baca"
 "privacyverklaring" = "pernyataan privasi"
+"Door te reserveren ga je akkoord met onze {privacy}. Wijzigen of annuleren kan altijd via de link in je mail." = "Dengan memesan, Anda menyetujui {privacy} kami. Anda selalu dapat mengubah atau membatalkan melalui tautan di email Anda."
 "Reservering bevestigen" = "Konfirmasi reservasi"
 "Met meer dan {aantal} personen? Bel" = "Lebih dari {aantal} orang? Telepon"
 "Dan kun je ook meteen vooraf bestellen." = "Anda juga bisa langsung memesan makanan terlebih dahulu."
````

