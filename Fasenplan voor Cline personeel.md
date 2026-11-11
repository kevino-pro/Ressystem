# Fasenplan voor Cline: personeelspagina's

Opgesteld 11 nov 2026 door Claude (Sonnet 5.5). Gebaseerd op `main` op commit 3375575 (PR #56). Voor Cline (uitvoerder), Sonnet (controleur) en de gebruiker (alle git-handelingen). Geen geheimen in dit bestand. HYPOTHESE = niet bewezen; BEWIJS = gezien in code of testuitslag.

Per fase staan hieronder vier blokken die je zo kunt kopiëren: (1) de git-terminal, (2) de prompt voor Cline, (3) de controle-prompt voor Sonnet, (4) commit, push, PR en merge in één keer, pas nadat Sonnet GO heeft gegeven. De bestandsinhoud staat achteraan in de bijlagen.

## Doel en besluiten

Het personeel (medewerkers) gebruikt de pagina's op een **telefoon**, de beheerder op een **tablet**. De pagina's werken en zijn consistent; versimpelen loont op vier plekken. Alles wat alleen voor telefoons is, staat in `@media (max-width: 700px)`: een tablet (breder dan 700 px) en een pc blijven zoals ze waren.

Gemeten op een testkopie met 12 reserveringen op één dag, op 390 px breed (BEWIJS):

| Wat | Voor | Na |
|---|---|---|
| Menu | 173 px hoog: 3 rijen met tot 11 items (beheerder) | 95 px: naam, knop Menu en twee hoofdpagina's |
| Eerste reservering op de pagina Reserveringen | pas op 756 px (bijna een heel scherm scrollen) | op 468 px (na fase 1 en 2) |
| Reserveringen, paginalengte | 3122 px | 2450 px |
| Plattegrond op telefoon | de **hele pagina** was 694 px breed en schoof zijwaarts; 18 tijdknoppen in 5 rijen; tafels van 33 px om op te tikken | pagina past in 390 px; tijden in één strook; tafelknoppen van 52 px in een vaste balk |
| Formulier telefonische reservering | 11 velden, 1329 px, vrij tijdveld zonder te zien of er plek is | binnenloper 560 px; telefonisch 811 px gemeten vóór personen en tijd naast elkaar kwamen te staan, dus nu korter; plus een zin met de ruimte tijdens het invullen |

| Fase | Inhoud | Tests daarna (bij main op 3375575: 614) |
|---|---|---|
| 1 | Menu: op een telefoon alleen Reserveringen en Plattegrond, de rest onder Menu | 623 (+9) |
| 2 | Reserveringsoverzicht compacter op een telefoon | 628 (+5) |
| 3 | Plattegrond op een telefoon: tijdenstrook, tafelknoppen in een vaste balk, geen zijwaarts schuivende pagina | 636 (+8) |
| 4 | Invoerformulier: minder velden vooraf en direct zien of er plek is (nieuwe hulproute `/reservering/ruimte`) | 650 (+14) |

De fases bouwen op elkaar voort (fase 3 gebruikt een klasse uit fase 2): voer ze in volgorde uit.

Wat er bewust **niet** in zit: Cijfers, Medewerkers, Mijn account en de loginpagina (rustig en helder; blijven zoals ze zijn), de tekening van de plattegrond zelf (de tafelknoppen vervangen het tikken op kleine tafels, de tekening blijft ter oriëntatie), en het ⋯-menu in het overzicht (alleen voor de beheerder).

Getest op een kopie van `main` (3375575) met SQLite, per fase met de volledige testsuite. Daarnaast heb ik de echte pagina's op een lokale testserver met een tijdelijke database in de browser bekeken: op 390 px (telefoon) en 768 px (tablet), met een echte tafeltoewijzing via de tafelknoppen en een ruimtezin in het invoerformulier. Daarbij vond ik twee layoutfouten die ik heb hersteld: de knop Menu stond ook op een tablet in beeld (de klasse pil overschreef de regel die hem verbergt) en de plattegrond rekte de hele pagina op (dat bestond al vóór deze wijzigingen). **Niet getest:** op een echte telefoon of tablet (vooral het gedrag van een vaste balk onderaan met het schermtoetsenbord in Safari op iPhone is een HYPOTHESE), en op Postgres (er is geen databasewijziging in dit plan).

Let op bij de nulmeting: als er voor deze fases andere branches in `main` zijn gemerged, wijkt het aantal tests af. Het plan rekent daarom met "nulmeting + N". Past een blok niet, dan moet Cline stoppen; stuur dan het blok naar Claude.

## Werkafspraken

- Eén fase tegelijk. Pas na merge op `main` en een groene Render-deploy begint de volgende fase.
- Repo-bestanden gebruiken CRLF. De bestandsinhoud in de bijlagen staat met gewone regeleinden (LF); Cline schrijft nieuwe bestanden met CRLF en behoudt de regeleinden van bestaande bestanden.
- Elke vertaalbare zin in een template staat in `vertalingen/en.toml` en `vertalingen/id.toml`; `tests/test_vertalingen.py` dwingt dat af. Personeel ziet de taal van het eigen account.
- Cline voert uit, Sonnet controleert (alleen lezen), jij doet alle git.

## Fase 1: Menu

### 1. Git-terminal (Git Bash)

```bash
cd /c/Codes/WPL && git checkout main && git pull && git checkout -b feat/personeel-menu && git --no-pager log --oneline -3
```

### 2. Prompt voor Cline

```text
Context
Je werkt in C:\Codes\WPL (Flask-app voor restaurantreserveringen, Nederlandse namen). Branch feat/personeel-menu is actief en komt van main.
Het fasenplan staat in "Fasenplan voor Cline personeel.md"; lees daarin alleen "Fase 1" en "Bijlage 1". Deze fase: het menu van de personeelspagina's (templates/personeel.html) inkorten voor een telefoon: alleen Reserveringen en Plattegrond staan er altijd; Medewerkers, Cijfers, het Reserveringsformulier, je eigen account, Uitloggen en de taalkeuze komen onder een knop Menu. Vanaf 700 px breed (tablet en pc) verandert er niets. Alleen templates/personeel.html, css, vertalingen en tests; geen Python in app/.

Taak
1. Draai eerst in Git Bash (vanuit de repo-root, venv actief): python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"
   Noteer het getal bij "Ran" als nulmeting. Slaagt niet alles al vóór je begint, stop dan en meld dat.
2. Maak de nieuwe bestanden en pas de bestaande bestanden aan precies zoals in Bijlage 1: nieuwe bestanden en "vervang het hele bestand" met de volledige inhoud; gewijzigde bestanden per blok (regels met - weg, regels met + erbij; de rest is omgeving). Gebruik je bewerk-tool per blok, niet git apply. Past een blok niet, stop dan en meld welk blok.
3. Repo-bestanden gebruiken CRLF: behoud de regeleinden van bestaande bestanden en schrijf nieuwe bestanden ook met CRLF.
4. Draai in Git Bash opnieuw: python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"
   Verwacht: nulmeting + 9 tests, uitslag OK (skipped mag gelijk blijven).

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
Context: Ik werk aan de Flask-app in C:\Codes\WPL. Cline heeft zojuist "Personeelspagina's, fase 1: menu" uitgevoerd
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
1. Alleen deze bestanden zijn gewijzigd of nieuw: templates/personeel.html, static/css/huisstijl.css, vertalingen/en.toml, vertalingen/id.toml en nieuw tests/test_personeelsmenu.py. Niets in app/.
2. static/css/huisstijl.css is alleen aangevuld: er verdwijnt of verandert geen enkele bestaande regel (git --no-pager diff static/css/huisstijl.css toont geen regels met - behalve de kopregel).
3. Tablet en pc blijven gelijk: buiten de media query staat `.menu-lijst { display: contents; }` (de links staan dus gewoon naast elkaar) en `nav.staf .menuknop { display: none; ... }`. De selector `nav.staf .menuknop` moet specifieker zijn dan `.pil`, want de knop heeft ook de klasse pil en die zet display anders weer aan. Binnen `@media (max-width: 700px)` staat de knop zichtbaar en is `.menu-lijst` verborgen tot hij de klasse open heeft.
4. Het script staat in het blok `pagina` van personeel.html (niet in `scripts`, dat door de kindpagina's wordt overschreven), zet `aria-expanded` op de knop, sluit met Escape en gebruikt geen innerHTML.
5. Niets is verdwenen uit het menu: Reserveringen, Plattegrond (alleen als er een plattegrond is), Medewerkers en Cijfers (alleen voor een beheerder, de rolcontrole `gebruiker.rol == 'beheerder'` is ongewijzigd), Reserveringsformulier, de naam van het account, Uitloggen (POST met csrf_token) en de taalkeuze.
6. Vertalingen: in en.toml en id.toml is precies één sleutel toegevoegd, "Menu", en niets verwijderd. tests.test_vertalingen slaagt.
7. Het aantal tests is met 9 gestegen ten opzichte van de nulmeting van Cline (bij main op 3375575: 614 naar 623), uitslag OK.
```

### 4. Commit, PR en merge (pas na GO van Sonnet)

Het blok stopt vanzelf als iets niet klopt: een andere branch dan `feat/personeel-menu`, een gewijzigd bestand dat niet bij deze fase hoort, een onbekend nieuw bestand, een mislukte push, rode CI of een PR die niet te mergen is. Alleen de bestanden van deze fase worden toegevoegd (geen `git add -A`). De merge is een gewone merge-commit. Stopt de keten ergens (bijvoorbeeld bij `no checks reported` omdat CI nog niet is gestart)? Los het op en plak hetzelfde blok opnieuw: een commit of PR die er al is wordt overgeslagen.

```bash
cd /c/Codes/WPL && [ "$(git branch --show-current)" = "feat/personeel-menu" ] && git add tests/test_personeelsmenu.py static/css/huisstijl.css templates/personeel.html vertalingen/en.toml vertalingen/id.toml && git diff --quiet && [ -z "$(git ls-files --others --exclude-standard | grep -v -E '^(ontwerp/|Fasenplan)')" ] && git --no-pager diff --cached --stat && { git diff --cached --quiet || git commit -m "Personeelsmenu: op een telefoon alleen Reserveringen en Plattegrond, de rest onder Menu" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"; } && git push -u origin feat/personeel-menu && { gh pr view >/dev/null 2>&1 || gh pr create --base main --head feat/personeel-menu --title "Personeelsmenu: op een telefoon alleen Reserveringen en Plattegrond, de rest onder Menu" --body "Fase 1 van het fasenplan personeelspagina's. Controle door Sonnet: GO. Tests groen. 🤖 Generated with [Claude Code](https://claude.com/claude-code)"; } && sleep 20 && gh pr checks --watch --fail-fast && gh pr merge --merge && git checkout main && git pull --prune && git branch -d feat/personeel-menu && git --no-pager log --oneline -3
```

### Voor en na de merge

Voor het blok hierboven: Sonnet heeft GO gegeven. Het blok maakt zelf de PR en merget pas als CI `unit-tests` groen is.

Na de merge (door de gebruiker):

1. Wacht op de groene Render-deploy.
2. Log in op je telefoon als medewerker: bovenaan staan de naam van het restaurant en een knop **Menu**, daaronder Reserveringen en Plattegrond. Tik op Menu: je ziet Reserveringsformulier, je accountnaam, Uitloggen en de taalkeuze. Nog een keer tikken (of Escape) sluit het menu.
3. Log in op je tablet als beheerder: het menu ziet er hetzelfde uit als voorheen, in een rij, zonder knop Menu. Als de knop Menu daar wel staat, meld dat dan.

## Fase 2: Overzicht op telefoon

### 1. Git-terminal (Git Bash)

```bash
cd /c/Codes/WPL && git checkout main && git pull && git checkout -b feat/personeel-overzicht && git --no-pager log --oneline -3
```

### 2. Prompt voor Cline

```text
Context
Je werkt in C:\Codes\WPL (Flask-app voor restaurantreserveringen, Nederlandse namen). Branch feat/personeel-overzicht is actief en komt van main.
Het fasenplan staat in "Fasenplan voor Cline personeel.md"; lees daarin alleen "Fase 2" en "Bijlage 2". Deze fase: de pagina Reserveringen (templates/overzicht.html) compacter maken op een telefoon: pijltjes in plaats van 'Vorige dag' en 'Volgende dag', compactere tellers (3 per rij), geen dubbel e-mailadres en geen dubbele knop Bel (het telefoonnummer zelf belt). Alleen op schermen tot 700 px; op een tablet of pc verandert niets. Alleen overzicht.html, css en tests; geen nieuwe tekst, dus geen vertalingen.

Taak
1. Draai eerst in Git Bash (vanuit de repo-root, venv actief): python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"
   Noteer het getal bij "Ran" als nulmeting. Slaagt niet alles al vóór je begint, stop dan en meld dat.
2. Maak de nieuwe bestanden en pas de bestaande bestanden aan precies zoals in Bijlage 2: nieuwe bestanden en "vervang het hele bestand" met de volledige inhoud; gewijzigde bestanden per blok (regels met - weg, regels met + erbij; de rest is omgeving). Gebruik je bewerk-tool per blok, niet git apply. Past een blok niet, stop dan en meld welk blok.
3. Repo-bestanden gebruiken CRLF: behoud de regeleinden van bestaande bestanden en schrijf nieuwe bestanden ook met CRLF.
4. Draai in Git Bash opnieuw: python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"
   Verwacht: nulmeting + 5 tests, uitslag OK (skipped mag gelijk blijven).

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
Context: Ik werk aan de Flask-app in C:\Codes\WPL. Cline heeft zojuist "Personeelspagina's, fase 2: reserveringsoverzicht op telefoon" uitgevoerd
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
1. Alleen deze bestanden zijn gewijzigd of nieuw: templates/overzicht.html, static/css/huisstijl.css en nieuw tests/test_overzicht_telefoon.py. Niets in app/ en niets in vertalingen/ (er komt geen nieuwe tekst bij).
2. In templates/overzicht.html zijn alleen klassen, een aria-label en twee span-elementen toegevoegd (alleen-breed, scheiding, tel, mailtekst, bel, mail); er is geen tekst, knop, formulier of logica verwijderd. Het formulier Is er / Niet gekomen, de knoppen Bel en Mail, het e-mailadres en het ⋯-menu (alleen voor een beheerder) staan er nog.
3. De aria-labels op de dagknoppen gebruiken de bestaande sleutels t('Vorige dag') en t('Volgende dag').
4. static/css/huisstijl.css is alleen aangevuld, en alle nieuwe regels die iets verbergen of verkleinen (`.alleen-breed`, `.mailtekst`, `.scheiding`, `.bel`, de compactere tellers en rijen) staan binnen `@media (max-width: 700px)`. Controleer dat er geen enkele nieuwe regel buiten die media query staat die bestaande elementen verbergt (tablet en pc blijven gelijk).
5. Het aantal tests is met 5 gestegen ten opzichte van de nulmeting van Cline (na fase 1: 623 naar 628), uitslag OK.
```

### 4. Commit, PR en merge (pas na GO van Sonnet)

Het blok stopt vanzelf als iets niet klopt: een andere branch dan `feat/personeel-overzicht`, een gewijzigd bestand dat niet bij deze fase hoort, een onbekend nieuw bestand, een mislukte push, rode CI of een PR die niet te mergen is. Alleen de bestanden van deze fase worden toegevoegd (geen `git add -A`). De merge is een gewone merge-commit. Stopt de keten ergens (bijvoorbeeld bij `no checks reported` omdat CI nog niet is gestart)? Los het op en plak hetzelfde blok opnieuw: een commit of PR die er al is wordt overgeslagen.

```bash
cd /c/Codes/WPL && [ "$(git branch --show-current)" = "feat/personeel-overzicht" ] && git add tests/test_overzicht_telefoon.py static/css/huisstijl.css templates/overzicht.html && git diff --quiet && [ -z "$(git ls-files --others --exclude-standard | grep -v -E '^(ontwerp/|Fasenplan)')" ] && git --no-pager diff --cached --stat && { git diff --cached --quiet || git commit -m "Reserveringsoverzicht compacter op een telefoon" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"; } && git push -u origin feat/personeel-overzicht && { gh pr view >/dev/null 2>&1 || gh pr create --base main --head feat/personeel-overzicht --title "Reserveringsoverzicht compacter op een telefoon" --body "Fase 2 van het fasenplan personeelspagina's. Controle door Sonnet: GO. Tests groen. 🤖 Generated with [Claude Code](https://claude.com/claude-code)"; } && sleep 20 && gh pr checks --watch --fail-fast && gh pr merge --merge && git checkout main && git pull --prune && git branch -d feat/personeel-overzicht && git --no-pager log --oneline -3
```

### Voor en na de merge

Voor het blok hierboven: Sonnet heeft GO gegeven. Het blok maakt zelf de PR en merget pas als CI `unit-tests` groen is. Begin pas na de merge en een groene deploy van fase 1.

Na de merge (door de gebruiker):

1. Wacht op de groene Render-deploy.
2. Open Reserveringen op je telefoon: onder de kop staan pijltjes naast Vandaag en de datum, daaronder + Reservering en + Binnenloper, de zoekbalk en de tellers in 3 kolommen. De eerste reservering staat zonder lang scrollen in beeld.
3. In een reserveringsrij staat het telefoonnummer groot genoeg om op te tikken (dat belt), met onder de naam de knoppen Is er en Mail. Het e-mailadres zelf staat er niet meer.
4. Op je tablet ziet de pagina er hetzelfde uit als voorheen, met Bel, Mail en het e-mailadres.

## Fase 3: Plattegrond op telefoon

### 1. Git-terminal (Git Bash)

```bash
cd /c/Codes/WPL && git checkout main && git pull && git checkout -b feat/personeel-plattegrond && git --no-pager log --oneline -3
```

### 2. Prompt voor Cline

```text
Context
Je werkt in C:\Codes\WPL (Flask-app voor restaurantreserveringen, Nederlandse namen). Branch feat/personeel-plattegrond is actief en komt van main.
Het fasenplan staat in "Fasenplan voor Cline personeel.md"; lees daarin alleen "Fase 3" en "Bijlage 3". Deze fase: de plattegrond (templates/plattegrond.html) bruikbaar maken op een telefoon: de tijden in een strook die je zijwaarts schuift, tafelknoppen onderaan in een vaste balk zodra je een reservering kiest (de tafels op de tekening zijn te klein om op te tikken; bezette tafels staan op grijs), en de hele pagina schuift niet meer zijwaarts. Op een tablet of pc blijft het paneel zoals het was. Geen nieuwe tekst, dus geen vertalingen.

Taak
1. Draai eerst in Git Bash (vanuit de repo-root, venv actief): python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"
   Noteer het getal bij "Ran" als nulmeting. Slaagt niet alles al vóór je begint, stop dan en meld dat.
2. Maak de nieuwe bestanden en pas de bestaande bestanden aan precies zoals in Bijlage 3: nieuwe bestanden en "vervang het hele bestand" met de volledige inhoud; gewijzigde bestanden per blok (regels met - weg, regels met + erbij; de rest is omgeving). Gebruik je bewerk-tool per blok, niet git apply. Past een blok niet, stop dan en meld welk blok.
3. Repo-bestanden gebruiken CRLF: behoud de regeleinden van bestaande bestanden en schrijf nieuwe bestanden ook met CRLF.
4. Draai in Git Bash opnieuw: python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"
   Verwacht: nulmeting + 8 tests, uitslag OK (skipped mag gelijk blijven).

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
Context: Ik werk aan de Flask-app in C:\Codes\WPL. Cline heeft zojuist "Personeelspagina's, fase 3: plattegrond op telefoon" uitgevoerd
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
1. Alleen deze bestanden zijn gewijzigd of nieuw: templates/plattegrond.html, static/css/huisstijl.css en nieuw tests/test_plattegrond_telefoon.py. Niets in app/ en niets in vertalingen/.
2. De attribuut data-bezet op een tafel bevat alleen het afgeleide kenmerk (`kenmerken[gast.id]`), nooit het reservering-id: dat is ook de annuleerlink van de gast en mag niet op de plattegrond staan (een test controleert dat).
3. Het script gebruikt geen innerHTML en bouwt de tafelknoppen met createElement en textContent. Het zoekt tafels op via een object (`tafels`) en niet met een selector op data-tafel=: de bestaande test test_toont_alle_tafels telt 22 keer `data-tafel="` in de pagina en moet ongewijzigd slagen.
4. De inline-stijlen van het paneel #toewijzen zijn vervangen door de klassen `.toewijzen`, `.toewijzen-keuze` en `.toewijzen-melding`. Op tablet en pc ziet het paneel er hetzelfde uit (`.tafelkeuze { display: none; }` staat buiten de media query, de vaste balk binnen `@media (max-width: 700px)`).
5. `.indeling > .paneel { min-width: 0; }` staat binnen de media query en lost op dat de tekening van 640 px de hele pagina zijwaarts liet schuiven.
6. Opslaan, annuleren en de serverroute /plattegrond/toewijzen zijn ongewijzigd; de tafelknoppen doen exact hetzelfde als tikken op de tekening (dezelfde functie `wissel`).
7. static/css/huisstijl.css is alleen aangevuld (geen enkele bestaande regel verdwijnt of verandert).
8. Het aantal tests is met 8 gestegen ten opzichte van de nulmeting van Cline (na fase 2: 628 naar 636), uitslag OK.
```

### 4. Commit, PR en merge (pas na GO van Sonnet)

Het blok stopt vanzelf als iets niet klopt: een andere branch dan `feat/personeel-plattegrond`, een gewijzigd bestand dat niet bij deze fase hoort, een onbekend nieuw bestand, een mislukte push, rode CI of een PR die niet te mergen is. Alleen de bestanden van deze fase worden toegevoegd (geen `git add -A`). De merge is een gewone merge-commit. Stopt de keten ergens (bijvoorbeeld bij `no checks reported` omdat CI nog niet is gestart)? Los het op en plak hetzelfde blok opnieuw: een commit of PR die er al is wordt overgeslagen.

```bash
cd /c/Codes/WPL && [ "$(git branch --show-current)" = "feat/personeel-plattegrond" ] && git add tests/test_plattegrond_telefoon.py static/css/huisstijl.css templates/plattegrond.html && git diff --quiet && [ -z "$(git ls-files --others --exclude-standard | grep -v -E '^(ontwerp/|Fasenplan)')" ] && git --no-pager diff --cached --stat && { git diff --cached --quiet || git commit -m "Plattegrond op een telefoon: tijdenstrook en tafelknoppen in een vaste balk" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"; } && git push -u origin feat/personeel-plattegrond && { gh pr view >/dev/null 2>&1 || gh pr create --base main --head feat/personeel-plattegrond --title "Plattegrond op een telefoon: tijdenstrook en tafelknoppen in een vaste balk" --body "Fase 3 van het fasenplan personeelspagina's. Controle door Sonnet: GO. Tests groen. 🤖 Generated with [Claude Code](https://claude.com/claude-code)"; } && sleep 20 && gh pr checks --watch --fail-fast && gh pr merge --merge && git checkout main && git pull --prune && git branch -d feat/personeel-plattegrond && git --no-pager log --oneline -3
```

### Voor en na de merge

Voor het blok hierboven: Sonnet heeft GO gegeven. Het blok maakt zelf de PR en merget pas als CI `unit-tests` groen is. Begin pas na de merge en een groene deploy van fase 2 (deze fase gebruikt de klasse alleen-breed uit fase 2).

Na de merge (door de gebruiker):

1. Wacht op de groene Render-deploy.
2. Open de Plattegrond op je telefoon: de tijden staan in één strook die je zijwaarts schuift, met de gekozen tijd in beeld. De pagina zelf schuift niet meer zijwaarts; alleen de tekening binnen het kader.
3. Scroll naar de lijst met reserveringen en tik er een aan: onderaan verschijnt een balk met de naam, tafelknoppen (nummer en aantal stoelen) en Tafels opslaan. Tafels die op dat moment bezet zijn staan op grijs. Kies een of twee tafels en sla op: de reservering krijgt die tafel(s).
4. Op je tablet staat het paneel naast de tekening zoals voorheen, zonder tafelknoppen.

## Fase 4: Invoerformulier

### 1. Git-terminal (Git Bash)

```bash
cd /c/Codes/WPL && git checkout main && git pull && git checkout -b feat/personeel-invoeren && git --no-pager log --oneline -3
```

### 2. Prompt voor Cline

```text
Context
Je werkt in C:\Codes\WPL (Flask-app voor restaurantreserveringen, Nederlandse namen). Branch feat/personeel-invoeren is actief en komt van main.
Het fasenplan staat in "Fasenplan voor Cline personeel.md"; lees daarin alleen "Fase 4" en "Bijlage 4". Deze fase: het formulier voor telefonische reserveringen en binnenlopers (templates/reservering_nieuw.html) korter maken: bovenaan alleen wat nodig is (naam en telefoon bij telefonisch; altijd personen, tijd en datum), de rest onder 'Meer gegevens', en tijdens het invullen een zin die zegt of er plek is. Daarvoor komt een kleine hulproute GET /reservering/ruimte in app/routes/invoeren.py, die dezelfde controle gebruikt als bij het opslaan en niets bewaart. Opslaan blijft werken zoals voorheen.

Taak
1. Draai eerst in Git Bash (vanuit de repo-root, venv actief): python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"
   Noteer het getal bij "Ran" als nulmeting. Slaagt niet alles al vóór je begint, stop dan en meld dat.
2. Maak de nieuwe bestanden en pas de bestaande bestanden aan precies zoals in Bijlage 4: nieuwe bestanden en "vervang het hele bestand" met de volledige inhoud; gewijzigde bestanden per blok (regels met - weg, regels met + erbij; de rest is omgeving). Gebruik je bewerk-tool per blok, niet git apply. Past een blok niet, stop dan en meld welk blok.
3. Repo-bestanden gebruiken CRLF: behoud de regeleinden van bestaande bestanden en schrijf nieuwe bestanden ook met CRLF.
4. Draai in Git Bash opnieuw: python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"
   Verwacht: nulmeting + 14 tests, uitslag OK (skipped mag gelijk blijven).

Rapporteer alleen
Wat er gebeurt; verzin niets, verbeter niets en voeg niets toe dat niet in het plan staat.

Beperkingen
- Alleen de bestanden uit Bijlage 4. Geen andere bestanden, geen nieuwe packages, geen refactors.
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
Context: Ik werk aan de Flask-app in C:\Codes\WPL. Cline heeft zojuist "Personeelspagina's, fase 4: invoerformulier met ruimtehint" uitgevoerd
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
1. Alleen deze bestanden zijn gewijzigd of nieuw: app/routes/invoeren.py, templates/reservering_nieuw.html, static/css/huisstijl.css, vertalingen/en.toml, vertalingen/id.toml en nieuw tests/test_invoeren_compact.py.
2. In app/routes/invoeren.py zijn alleen imports, de functie `_ruimtetekst` en de route `ruimte` toegevoegd. De route heeft `@login_vereist(json_response=True)` en `@rate_limit(..., json_response=True)`, is een GET, bewaart niets en keurt ongeldige invoer af met 400. `_ruimtetekst` hergebruikt `_waarschuwingen` (er komt geen tweede set regels). De routes `nieuw` en `opslaan` zijn ongewijzigd.
3. Alle veldnamen van het formulier bestaan nog: csrf_token, bron, naam, telefoon, aantal, tijd, datum, email, taal, kinderstoelen, allergieen, allergie_toestemming, opmerking en bevestigd. Bij een binnenloper staat het veld naam maar één keer in de HTML (onder Meer gegevens), en daar zonder `required`; bij telefonisch staan naam en telefoon bovenaan met `required`.
4. Het uitklapblok `#meer` staat open als er een melding of waarschuwing is of als er iets is ingevuld, zodat niets verborgen blijft.
5. Het script zet de zin van de server met textContent (geen innerHTML) en laat het formulier gewoon werken als de hulproute faalt.
6. Vertalingen: in en.toml en id.toml zijn precies twee sleutels toegevoegd, "Meer gegevens" en "Rond {tijd} is er plek; er blijven {vrij} van {maximum} plekken vrij.", met dezelfde plaatshouders in beide vertalingen. Niets verwijderd. tests.test_vertalingen slaagt.
7. static/css/huisstijl.css is alleen aangevuld. De tests tests/test_binnenloper.py en tests/test_personeel_reserveren.py zijn ongewijzigd en slagen.
8. Het aantal tests is met 14 gestegen ten opzichte van de nulmeting van Cline (na fase 3: 636 naar 650), uitslag OK.
```

### 4. Commit, PR en merge (pas na GO van Sonnet)

Het blok stopt vanzelf als iets niet klopt: een andere branch dan `feat/personeel-invoeren`, een gewijzigd bestand dat niet bij deze fase hoort, een onbekend nieuw bestand, een mislukte push, rode CI of een PR die niet te mergen is. Alleen de bestanden van deze fase worden toegevoegd (geen `git add -A`). De merge is een gewone merge-commit. Stopt de keten ergens (bijvoorbeeld bij `no checks reported` omdat CI nog niet is gestart)? Los het op en plak hetzelfde blok opnieuw: een commit of PR die er al is wordt overgeslagen.

```bash
cd /c/Codes/WPL && [ "$(git branch --show-current)" = "feat/personeel-invoeren" ] && git add tests/test_invoeren_compact.py app/routes/invoeren.py static/css/huisstijl.css templates/reservering_nieuw.html vertalingen/en.toml vertalingen/id.toml && git diff --quiet && [ -z "$(git ls-files --others --exclude-standard | grep -v -E '^(ontwerp/|Fasenplan)')" ] && git --no-pager diff --cached --stat && { git diff --cached --quiet || git commit -m "Telefonische reservering invoeren: minder velden en direct zien of er plek is" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"; } && git push -u origin feat/personeel-invoeren && { gh pr view >/dev/null 2>&1 || gh pr create --base main --head feat/personeel-invoeren --title "Telefonische reservering invoeren: minder velden en direct zien of er plek is" --body "Fase 4 van het fasenplan personeelspagina's. Controle door Sonnet: GO. Tests groen. 🤖 Generated with [Claude Code](https://claude.com/claude-code)"; } && sleep 20 && gh pr checks --watch --fail-fast && gh pr merge --merge && git checkout main && git pull --prune && git branch -d feat/personeel-invoeren && git --no-pager log --oneline -3
```

### Voor en na de merge

Voor het blok hierboven: Sonnet heeft GO gegeven. Het blok maakt zelf de PR en merget pas als CI `unit-tests` groen is. Begin pas na de merge en een groene deploy van fase 3.

Na de merge (door de gebruiker):

1. Wacht op de groene Render-deploy.
2. Tik in Reserveringen op + Reservering: je ziet Naam, Telefoon, Personen en Tijd naast elkaar, Datum, en een knop Meer gegevens. Vul een tijd en aantal in: onder Datum verschijnt een zin zoals "Rond 19:00 is er plek; er blijven 40 van 69 plekken vrij." Vul een groot aantal in: de zin wordt oranje en noemt het maximum.
3. Tik op + Binnenloper: alleen Personen, Tijd en Datum staan bovenaan; naam en telefoon staan onder Meer gegevens. Sla een binnenloper op: je komt op de plattegrond.
4. Maak een testreservering en verwijder die daarna weer als beheerder via ⋯ in het overzicht (dit schrijft echte gegevens naar de database).

---

# Bijlagen: bestandsinhoud per fase

## Bijlage 1: bestanden van fase 1 (Menu)

#### Nieuwe bestanden en bestanden die je helemaal vervangt

**`tests/test_personeelsmenu.py`** (nieuw)

````python
"""Het menu van de personeelspagina's (personeel, fase 1): op een telefoon alleen de hoofdpagina's, de rest onder Menu."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.security import reset_rate_limits
from tests.hulp import log_in
from tests.test_toegang import TestConfig


class PersoneelsmenuTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app = create_app(TestConfig)

    def pagina(self, rol, pad="/overzicht", taal="nl"):
        client = self.app.test_client()
        log_in(self.app, client, naam="kevin" if rol == "beheerder" else "anna", rol=rol)
        return client.get(pad, headers={"Accept-Language": taal}).get_data(as_text=True)

    def menu(self, html):
        """Alleen het stuk tussen id="menu" en het einde van het menu."""
        begin = html.index('<div class="menu-lijst" id="menu">')
        return html[begin:html.index("</nav>", html.index("Uitloggen", begin))]

    def test_menuknop_staat_dicht_en_wijst_naar_het_menu(self):
        html = self.pagina("beheerder")
        self.assertIn('id="menuknop" aria-expanded="false" aria-controls="menu"', html)
        self.assertIn(">Menu</button>", html)

    def test_hoofdpagina_s_staan_buiten_het_menu(self):
        html = self.pagina("beheerder")
        menu_begin = html.index('<div class="menu-lijst"')
        for tekst in ('href="/overzicht?', 'href="/plattegrond?'):  # met ?datum=, dus zonder sluitaanhalingsteken
            self.assertLess(html.index(tekst, html.index('class="tabs"')), menu_begin, tekst)

    def test_beheerder_heeft_beheer_formulier_account_en_uitloggen_in_het_menu(self):
        menu = self.menu(self.pagina("beheerder"))
        for tekst in ('href="/accounts"', 'href="/cijfers"', 'href="/"', 'href="/account"', 'action="/logout"'):
            self.assertIn(tekst, menu)

    def test_medewerker_ziet_geen_beheerpagina_s(self):
        menu = self.menu(self.pagina("medewerker"))
        self.assertNotIn('href="/accounts"', menu)
        self.assertNotIn('href="/cijfers"', menu)
        self.assertIn('action="/logout"', menu)
        self.assertIn('href="/account"', menu)

    def test_taalkeuze_staat_in_het_menu(self):
        html = self.pagina("medewerker")
        menu = self.menu(html)
        for code in ("en", "nl", "id"):
            self.assertIn(f'href="/taal/{code}?terug=', menu)
        self.assertEqual(html.count('class="talen"'), 1)

    def test_menu_op_elke_personeelspagina(self):
        for pad in ("/overzicht", "/plattegrond", "/cijfers", "/accounts", "/account", "/reservering/nieuw"):
            self.assertIn('id="menuknop"', self.pagina("beheerder", pad), pad)

    def test_menu_volgt_de_taal_van_het_account(self):
        # Personeel ziet de taal van het eigen account (kolom taal), niet die van de browser.
        client = self.app.test_client()
        log_in(self.app, client, naam="anna", rol="medewerker")
        html = client.get("/overzicht").get_data(as_text=True)
        self.assertIn(">Menu</button>", html)
        self.assertIn("Uitloggen", html)

    def test_menuknop_is_alleen_op_een_telefoon_zichtbaar(self):
        # De knop heeft ook de klasse pil, die display aanzet; de regel moet dus specifieker zijn (nav.staf .menuknop).
        css = (Path(__file__).resolve().parent.parent / "static" / "css" / "huisstijl.css").read_text(encoding="utf-8")
        self.assertIn("nav.staf .menuknop { display: none;", css)
        self.assertIn("nav.staf .menuknop { display: inline-flex;", css)
        self.assertLess(css.index("nav.staf .menuknop { display: none;"), css.index("max-width: 700px"))

    @unittest.skipUnless(shutil.which("node"), "node is niet geïnstalleerd")
    def test_menuscript_is_geldig_javascript(self):
        html = self.pagina("beheerder")
        script = next(s.split("</script>")[0] for s in html.split("<script>")[1:] if "menuknop" in s.split("</script>")[0])
        with tempfile.TemporaryDirectory() as map_:
            pad = Path(map_) / "menu.js"
            pad.write_text(script, encoding="utf-8")
            resultaat = subprocess.run(["node", "--check", str(pad)], capture_output=True, text=True)
        self.assertEqual(resultaat.returncode, 0, resultaat.stderr)


if __name__ == "__main__":
    unittest.main()
````

#### Gewijzigde bestanden (regels met `-` weg, regels met `+` erbij; de rest is omgeving)

**`static/css/huisstijl.css`**

````diff
@@ -53,6 +53,10 @@ nav.staf { display: flex; justify-content: space-between; align-items: center; g
 nav.staf .logo h1 { font-size: 21px; }
 .tabs { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
 .tabs form { display: inline; }
+/* Personeelsmenu: vanaf 700 px staat alles in een rij; op een telefoon alleen de twee hoofdpagina's, de rest onder Menu. */
+/* nav.staf ervoor: .pil (verderop) zet display anders weer aan */
+nav.staf .menuknop { display: none; cursor: pointer; }
+.menu-lijst { display: contents; }
 
 /* Bouwstenen */
 .kaart { background: var(--kaart); border: 1px solid var(--lijn); border-radius: 18px; padding: 28px;
@@ -302,6 +306,16 @@ fieldset.stap { min-width: 0; position: relative; }  /* min-width: anders rekt d
 @media (max-width: 480px) { .actiebalk { gap: 10px; margin-left: -18px; margin-right: -18px; padding-left: 18px; padding-right: 18px; } }
 
 @media (max-width: 700px) {
+    nav.staf { gap: 10px; padding-bottom: 14px; margin-bottom: 16px; }
+    nav.staf .logo { flex: 1; min-width: 0; }
+    nav.staf .menuknop { display: inline-flex; min-height: 38px; padding: 0 14px; }
+    nav.staf .tabs { flex-basis: 100%; }
+    .menu-lijst { display: none; flex-basis: 100%; flex-direction: column; align-items: stretch; gap: 6px;
+                  margin-top: 6px; padding-top: 10px; border-top: 1px solid var(--lijn); }
+    .menu-lijst.open { display: flex; }
+    .menu-lijst > .pil, .menu-lijst > form .pil { min-height: 44px; width: 100%; justify-content: flex-start; padding: 0 14px; font-size: 14px; }
+    .menu-lijst > form { display: block; }
+    .menu-lijst .talen { padding: 4px 0 2px; }
     .tellers { grid-template-columns: 1fr 1fr; }
     .res { grid-template-columns: 40px 1fr; row-gap: 8px; }
     .res .tafel, .res .acties { grid-column: 2; }
````

**`templates/personeel.html`**

````diff
@@ -5,11 +5,14 @@
 <div class="wrap breed">
     <nav class="staf">
         <a class="logo" href="/overzicht"><h1>{{ config.RESTAURANT_NAAM }}</h1></a>
+        <button type="button" class="pil menuknop" id="menuknop" aria-expanded="false" aria-controls="menu">{{ t("Menu") }}</button>
         <div class="tabs">
             <a class="pil {{ 'aan' if actief == 'overzicht' }}" href="/overzicht{{ '?datum=' ~ datum if datum }}">{{ t("Reserveringen") }}</a>
             {% if config.PLATTEGROND %}
             <a class="pil {{ 'aan' if actief == 'plattegrond' }}" href="/plattegrond{{ '?datum=' ~ datum if datum }}">{{ t("Plattegrond") }}</a>
             {% endif %}
+            {# Op een telefoon staat de rest onder de knop Menu; vanaf 700 px staat alles naast elkaar. #}
+            <div class="menu-lijst" id="menu">
             {% if gebruiker and gebruiker.rol == 'beheerder' %}
             <a class="pil {{ 'aan' if actief == 'accounts' }}" href="/accounts">{{ t("Medewerkers") }}</a>
             <a class="pil {{ 'aan' if actief == 'cijfers' }}" href="/cijfers">{{ t("Cijfers") }}</a>
@@ -30,8 +33,18 @@
                 {% endfor %}
             </nav>
             {% endif %}
+            </div>
         </div>
     </nav>
+    <script>
+    (function () {
+        const knop = document.getElementById('menuknop');
+        const menu = document.getElementById('menu');
+        function zet(open) { menu.classList.toggle('open', open); knop.setAttribute('aria-expanded', open ? 'true' : 'false'); }
+        knop.addEventListener('click', function () { zet(!menu.classList.contains('open')); });
+        document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { zet(false); } });
+    })();
+    </script>
     <main>
         {% block inhoud %}{% endblock %}
     </main>
````

**`vertalingen/en.toml`**

````diff
@@ -284,6 +284,7 @@
 "Plattegrond" = "Floor plan"
 "Reserveringsformulier" = "Booking form"
 "Uitloggen" = "Log out"
+"Menu" = "Menu"
 
 # plattegrond.html
 "is er" = "arrived"
````

**`vertalingen/id.toml`**

````diff
@@ -284,6 +284,7 @@
 "Plattegrond" = "Denah"
 "Reserveringsformulier" = "Formulir reservasi"
 "Uitloggen" = "Keluar"
+"Menu" = "Menu"
 
 # plattegrond.html
 "is er" = "sudah datang"
````


## Bijlage 2: bestanden van fase 2 (Overzicht op telefoon)

#### Nieuwe bestanden en bestanden die je helemaal vervangt

**`tests/test_overzicht_telefoon.py`** (nieuw)

````python
"""Het reserveringsoverzicht op een telefoon (personeel, fase 2): de opmaak hangt aan klassen, de inhoud blijft gelijk."""
import unittest

from sqlalchemy import delete, insert

from app import create_app
from app.database import get_db, metadata, reserveringen, tafeltoewijzingen
from app.security import reset_rate_limits
from tests.hulp import log_in
from tests.test_toegang import TestConfig

DAG = "2030-01-01"  # een dinsdag


class OverzichtTelefoonTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app = create_app(TestConfig)
        with self.app.app_context():
            conn = get_db()
            metadata.create_all(conn)
            conn.commit()
            with conn.begin():
                conn.execute(delete(tafeltoewijzingen))
                conn.execute(delete(reserveringen))
                conn.execute(insert(reserveringen).values(
                    id="beide", naam="Siti Rahma", email="siti@example.com", telefoon="0612345678",
                    datum=DAG, tijd="18:00", aantal=2))
                conn.execute(insert(reserveringen).values(
                    id="alleen-tel", naam="Budi Santoso", email="", telefoon="0687654321",
                    datum=DAG, tijd="19:00", aantal=4, bron="telefoon"))
        self.client = self.app.test_client()
        log_in(self.app, self.client, naam="anna", rol="medewerker")

    def pagina(self):
        return self.client.get(f"/overzicht?datum={DAG}").get_data(as_text=True)

    def test_telefoon_en_mail_hebben_klassen_voor_de_telefoonopmaak(self):
        html = self.pagina()
        for tekst in ('class="tel" href="tel:0612345678"', 'class="mailtekst" href="mailto:siti@example.com"',
                      '<span class="scheiding"> · </span>', 'class="bel" href="tel:0612345678"',
                      'class="mail" href="mailto:siti@example.com"'):
            self.assertIn(tekst, html)

    def test_de_inhoud_blijft_compleet_voor_tablet_en_pc(self):
        html = self.pagina()
        self.assertIn("siti@example.com", html)
        self.assertIn(">Bel</a>", html)
        self.assertIn(">Mail</a>", html)

    def test_zonder_mailadres_geen_mailtekst_en_geen_scheiding(self):
        rest = self.pagina().split("Budi Santoso")[1]  # Budi staat als laatste op de dag
        wie = rest.split('<div class="acties">')[0]
        self.assertNotIn("mailtekst", wie)
        self.assertNotIn("scheiding", wie)
        self.assertIn('class="tel" href="tel:0687654321"', wie)
        self.assertNotIn('class="mail"', rest)  # geen Mail-knop zonder adres

    def test_dagknoppen_hebben_een_label_en_de_tekst_verdwijnt_alleen_op_telefoon(self):
        html = self.pagina()
        self.assertIn('aria-label="Vorige dag">‹<span class="alleen-breed"> Vorige dag</span>', html)
        self.assertIn('aria-label="Volgende dag"><span class="alleen-breed">Volgende dag </span>›', html)

    def test_alle_reserveringen_en_tellers_staan_er_nog(self):
        html = self.pagina()
        self.assertIn("Siti Rahma", html)
        self.assertIn("Budi Santoso", html)
        self.assertIn("<small>Reserveringen</small><b>2</b>", html)
        self.assertIn("<small>Gasten</small><b>6</b>", html)


if __name__ == "__main__":
    unittest.main()
````

#### Gewijzigde bestanden (regels met `-` weg, regels met `+` erbij; de rest is omgeving)

**`static/css/huisstijl.css`**

````diff
@@ -324,6 +324,27 @@ fieldset.stap { min-width: 0; position: relative; }  /* min-width: anders rekt d
     .dagnav input[type=search] { flex: 1; width: auto; min-width: 0; }
     .indeling, .indeling.cijfers { grid-template-columns: 1fr; }
 }
+/* Personeel op een telefoon: de reserveringen eerst, niet de knoppen en tellers. Bellen kan met het nummer, mailen met Mail. */
+@media (max-width: 700px) {
+    .alleen-breed { display: none; }
+    .dagnav { gap: 8px; margin-bottom: 12px; }
+    .dagnav h2 { font-size: 22px; margin-right: 0; }
+    .dagnav .pil, .dagnav input[type=date] { min-height: 36px; }
+    .tellers { grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 14px; }
+    .teller { padding: 8px 10px; border-radius: 12px; }
+    .teller small { display: block; font-size: 11px; line-height: 1.25; }
+    .teller b { font-size: 19px; margin-top: 2px; }
+    .teller .balk { height: 4px; margin-top: 5px; }
+    .lijst { padding: 0 12px 4px; }
+    .tijdkop { padding: 12px 0 6px; }
+    .res { grid-template-columns: 40px 1fr auto; column-gap: 10px; row-gap: 6px; padding: 10px 0; }
+    .res .wie { grid-column: 2; grid-row: 1; }
+    .res .tafel { grid-column: 3; grid-row: 1; align-self: start; justify-self: end; }
+    .res .acties { grid-column: 2 / -1; grid-row: 2; }
+    .res .wie .mailtekst, .res .wie .scheiding, .acties .bel { display: none; }
+    .res .wie .tel { display: inline-block; padding: 4px 0; font-size: 14px; color: var(--tekst); }
+    .res .wie small { margin-top: 0; }
+}
 @media (max-width: 480px) {
     .kaart { padding: 18px; }
     .logo h1 { font-size: 24px; }
````

**`templates/overzicht.html`**

````diff
@@ -3,9 +3,9 @@
 {% block inhoud %}
 <div class="dagnav">
     <h2>{{ dag | datum_tekst(met_jaar=dag.year != vandaag.year) | hoofdletter }}</h2>
-    <a class="pil" href="/overzicht?datum={{ vorige }}">‹ {{ t("Vorige dag") }}</a>
+    <a class="pil" href="/overzicht?datum={{ vorige }}" aria-label="{{ t('Vorige dag') }}">‹<span class="alleen-breed"> {{ t("Vorige dag") }}</span></a>
     <a class="pil {{ 'aan' if dag == vandaag }}" href="/overzicht">{{ t("Vandaag") }}</a>
-    <a class="pil" href="/overzicht?datum={{ volgende }}">{{ t("Volgende dag") }} ›</a>
+    <a class="pil" href="/overzicht?datum={{ volgende }}" aria-label="{{ t('Volgende dag') }}"><span class="alleen-breed">{{ t("Volgende dag") }} </span>›</a>
     <form action="/overzicht" method="GET">
         <label for="datum" class="verborgen">{{ t("Kies datum") }}</label>
         <input type="date" id="datum" name="datum" value="{{ datum }}" onchange="this.form.submit()">
@@ -51,7 +51,7 @@
         <div class="aantal" title="{{ t('{aantal} personen', aantal=r.aantal) }}">{{ r.aantal }}</div>
         <div class="wie">
             <b>{{ r.naam }}</b>
-            <small>{% if r.telefoon %}<a href="tel:{{ r.telefoon }}">{{ r.telefoon }}</a>{% endif %}{% if r.telefoon and r.email %} · {% endif %}{% if r.email %}<a href="mailto:{{ r.email }}">{{ r.email }}</a>{% endif %}</small>
+            <small>{% if r.telefoon %}<a class="tel" href="tel:{{ r.telefoon }}">{{ r.telefoon }}</a>{% endif %}{% if r.telefoon and r.email %}<span class="scheiding"> · </span>{% endif %}{% if r.email %}<a class="mailtekst" href="mailto:{{ r.email }}">{{ r.email }}</a>{% endif %}</small>
             {% if r.kinderstoelen or r.opmerking or r.allergieen or r.bron != 'online' or r.status != 'verwacht' or r.herinnering_verstuurd or r.gewijzigd_op %}
             <div class="notities">
                 {% if r.status == 'gearriveerd' %}<span class="notitie">{{ t("Is er") }}</span>{% elif r.status == 'no_show' %}<span class="notitie allergie">{{ t("Niet gekomen") }}</span>{% endif %}
@@ -85,8 +85,8 @@
                 {% endif %}
             </form>
             {% endif %}
-            {% if r.telefoon %}<a href="tel:{{ r.telefoon }}">{{ t("Bel") }}</a>{% endif %}
-            {% if r.email %}<a href="mailto:{{ r.email }}">{{ t("Mail") }}</a>{% endif %}
+            {% if r.telefoon %}<a class="bel" href="tel:{{ r.telefoon }}">{{ t("Bel") }}</a>{% endif %}
+            {% if r.email %}<a class="mail" href="mailto:{{ r.email }}">{{ t("Mail") }}</a>{% endif %}
             {% if gebruiker and gebruiker.rol == 'beheerder' %}
             <details>
                 <summary aria-label="{{ t('Meer acties') }}">⋯</summary>
````


## Bijlage 3: bestanden van fase 3 (Plattegrond op telefoon)

#### Nieuwe bestanden en bestanden die je helemaal vervangt

**`tests/test_plattegrond_telefoon.py`** (nieuw)

````python
"""De plattegrond op een telefoon (personeel, fase 3): tafelknoppen in een vaste balk en een strook met tijden."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import insert

from app.database import get_db, init_db, reserveringen, tafeltoewijzingen, wijs_tafels_toe
from tests.test_plattegrond_pagina import TestConfig, maak_client


class PlattegrondTelefoonTests(unittest.TestCase):
    def setUp(self):
        self.app, self.client = maak_client(TestConfig)
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():  # de in-memory database wordt gedeeld tussen tests
                conn.execute(tafeltoewijzingen.delete())
                conn.execute(reserveringen.delete())

    def reservering(self, rid, tijd="19:00", aantal=2, tafels=()):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=rid, naam="Jan", email=f"{rid}@example.com", telefoon="0612345678",
                    datum="2030-01-01", tijd=tijd, aantal=aantal))
            if tafels:
                wijs_tafels_toe(conn, rid, list(tafels), self.app.config["PLATTEGROND"], 90)

    def pagina(self, query="?datum=2030-01-01&tijd=19:30"):
        antwoord = self.client.get("/plattegrond" + query)
        return antwoord.status_code, antwoord.get_data(as_text=True)

    def test_bezette_tafel_krijgt_het_kenmerk_van_haar_reservering(self):
        self.reservering("r1", tijd="19:00", aantal=2, tafels=["1a"])
        _, html = self.pagina("?datum=2030-01-01&tijd=19:30")
        kenmerk = re.search(r'data-tafel="1a" data-stoelen="\d+" data-bezet="([0-9a-f]+)"', html).group(1)
        self.assertEqual(len(kenmerk), 24)
        self.assertIn(f'data-kenmerk="{kenmerk}"', html)  # dezelfde waarde staat op de reservering in de lijst

    def test_vrije_tafel_heeft_een_leeg_kenmerk(self):
        self.reservering("r1", tijd="19:00", aantal=2, tafels=["1a"])
        _, html = self.pagina("?datum=2030-01-01&tijd=19:30")
        self.assertRegex(html, r'data-tafel="10a" data-stoelen="\d+" data-bezet=""')

    def test_het_id_van_de_reservering_staat_niet_op_de_tekening(self):
        self.reservering("geheim-id-123", tijd="19:00", aantal=2, tafels=["1a"])
        _, html = self.pagina("?datum=2030-01-01&tijd=19:30")
        self.assertNotIn("geheim-id-123", html)

    def test_toewijsbalk_heeft_een_plek_voor_tafelknoppen_en_geen_vaste_stijl_meer(self):
        _, html = self.pagina()
        self.assertIn('id="toewijzen" class="toewijzen" hidden', html)
        self.assertIn('id="tafelkeuze"', html)
        self.assertNotIn('style="margin-top: 12px; border-top', html)

    def test_dagknoppen_hebben_een_label_en_de_tekst_verdwijnt_alleen_op_telefoon(self):
        _, html = self.pagina()
        self.assertIn('aria-label="Vorige dag">‹<span class="alleen-breed"> Vorige dag</span>', html)
        self.assertIn('aria-label="Volgende dag"><span class="alleen-breed">Volgende dag </span>›', html)

    def test_tijdbalk_toont_de_gekozen_tijd(self):
        _, html = self.pagina("?datum=2030-01-01&tijd=19:30")
        self.assertIn('class="pil aan" href="/plattegrond?datum=2030-01-01&amp;tijd=19:30"', html)

    def test_meldingen_nooit_als_html(self):
        _, html = self.pagina()
        self.assertNotIn("innerHTML", html)

    @unittest.skipUnless(shutil.which("node"), "node is niet geïnstalleerd")
    def test_script_is_geldig_javascript(self):
        _, html = self.pagina()
        script = next(s.split("</script>")[0] for s in html.split("<script>")[1:] if "tafelkeuze" in s.split("</script>")[0])
        with tempfile.TemporaryDirectory() as map_:
            pad = Path(map_) / "plattegrond.js"
            pad.write_text(script, encoding="utf-8")
            resultaat = subprocess.run(["node", "--check", str(pad)], capture_output=True, text=True)
        self.assertEqual(resultaat.returncode, 0, resultaat.stderr)

if __name__ == "__main__":
    unittest.main()
````

#### Gewijzigde bestanden (regels met `-` weg, regels met `+` erbij; de rest is omgeving)

**`static/css/huisstijl.css`**

````diff
@@ -324,6 +324,19 @@ fieldset.stap { min-width: 0; position: relative; }  /* min-width: anders rekt d
     .dagnav input[type=search] { flex: 1; width: auto; min-width: 0; }
     .indeling, .indeling.cijfers { grid-template-columns: 1fr; }
 }
+/* Plattegrond: het paneel om tafels toe te wijzen. Op een telefoon is het een vaste balk met tafelknoppen. */
+.toewijzen { margin-top: 12px; border-top: 1px solid var(--lijn); padding-top: 12px; }
+.toewijzen-keuze { margin-top: 4px; font-size: 13px; }
+.toewijzen-melding { color: var(--rood); margin-top: 4px; font-size: 13px; }
+.tafelkeuze { display: none; }
+.tafelknop { flex: none; min-width: 52px; min-height: 46px; display: flex; flex-direction: column; align-items: center; justify-content: center;
+             border-radius: 10px; border: 1px solid var(--lijn); background: var(--veld); color: var(--tekst); font: inherit; cursor: pointer; }
+.tafelknop b { font-size: 15px; }
+.tafelknop small { font-size: 10.5px; color: var(--zacht); }
+.tafelknop[aria-pressed=true] { background: var(--groen); border-color: var(--groen); color: #0f1a10; }
+.tafelknop[aria-pressed=true] small { color: #0f1a10; }
+.tafelknop:disabled { opacity: .35; cursor: default; }
+
 /* Personeel op een telefoon: de reserveringen eerst, niet de knoppen en tellers. Bellen kan met het nummer, mailen met Mail. */
 @media (max-width: 700px) {
     .alleen-breed { display: none; }
@@ -344,6 +357,18 @@ fieldset.stap { min-width: 0; position: relative; }  /* min-width: anders rekt d
     .res .wie .mailtekst, .res .wie .scheiding, .acties .bel { display: none; }
     .res .wie .tel { display: inline-block; padding: 4px 0; font-size: 14px; color: var(--tekst); }
     .res .wie small { margin-top: 0; }
+
+    /* Plattegrond: tijden in een strook, tafelknoppen in een vaste balk onderaan */
+    .indeling > .paneel { min-width: 0; }  /* anders rekt de tekening (640 px) de hele pagina op in plaats van in de vloer te scrollen */
+    .tijdbalk { flex-wrap: nowrap; overflow-x: auto; scrollbar-width: none; margin: 0 -16px 14px; padding: 0 16px 6px; }
+    .tijdbalk::-webkit-scrollbar { display: none; }
+    .tijdbalk > * { flex: none; }
+    .toewijzen { position: fixed; left: 0; right: 0; bottom: 0; z-index: 20; margin: 0; padding: 10px 14px 12px; max-height: 60vh; overflow-y: auto;
+                 background: #1d1813; border-top: 1px solid var(--lijn); box-shadow: 0 -10px 30px rgba(0, 0, 0, .5); }
+    .toewijzen .klein { display: none; }
+    .tafelkeuze { display: flex; gap: 6px; overflow-x: auto; padding: 8px 0 6px; scrollbar-width: none; }
+    .tafelkeuze::-webkit-scrollbar { display: none; }
+    body.toewijzen-open { padding-bottom: 260px; }
 }
 @media (max-width: 480px) {
     .kaart { padding: 18px; }
````

**`templates/plattegrond.html`**

````diff
@@ -6,9 +6,9 @@
 {% macro kenmerken_tekst(r) %}{% if r.status == 'gearriveerd' %} · {{ t("is er") }}{% elif dag == vandaag and r.tijd <= nu_tijd %} · {{ t("nog niet binnen") }}{% endif %}{% if r.bron == 'binnenloper' %} · {{ t("binnenloper") }}{% elif r.bron == 'telefoon' %} · {{ t("telefonisch") }}{% endif %}{% if r.allergieen %} · {{ t("allergie") }}{% endif %}{% if r.kinderstoelen %} · {{ t('{aantal} kinderstoel', aantal=r.kinderstoelen) if r.kinderstoelen == 1 else t('{aantal} kinderstoelen', aantal=r.kinderstoelen) }}{% endif %}{% if r.opmerking %} · {{ t("opmerking") }}{% endif %}{% endmacro %}
 <div class="dagnav">
     <h2>{{ dag | datum_tekst(met_jaar=dag.year != vandaag.year) | hoofdletter }}</h2>
-    <a class="pil" href="/plattegrond?datum={{ vorige }}">‹ {{ t("Vorige dag") }}</a>
+    <a class="pil" href="/plattegrond?datum={{ vorige }}" aria-label="{{ t('Vorige dag') }}">‹<span class="alleen-breed"> {{ t("Vorige dag") }}</span></a>
     <a class="pil {{ 'aan' if dag == vandaag }}" href="/plattegrond">{{ t("Vandaag") }}</a>
-    <a class="pil" href="/plattegrond?datum={{ volgende }}">{{ t("Volgende dag") }} ›</a>
+    <a class="pil" href="/plattegrond?datum={{ volgende }}" aria-label="{{ t('Volgende dag') }}"><span class="alleen-breed">{{ t("Volgende dag") }} </span>›</a>
     <form action="/plattegrond" method="GET">
         <label for="datum" class="verborgen">{{ t("Kies datum") }}</label>
         <input type="date" id="datum" name="datum" value="{{ datum }}" onchange="this.form.submit()">
@@ -54,7 +54,7 @@
             {% set b = t.breedte * hokje - 8 %}{% set h = t.hoogte * hokje - 8 %}
             {% set vulling = accent ~ '38' if gast else 'rgba(255,255,255,.06)' %}
             {% set rand = accent if gast or later else 'rgba(255,255,255,.28)' %}
-            <g class="tafel" data-tafel="{{ t.nummer }}" data-stoelen="{{ t.stoelen }}">
+            <g class="tafel" data-tafel="{{ t.nummer }}" data-stoelen="{{ t.stoelen }}" data-bezet="{{ kenmerken[gast.id] if gast else '' }}">
                 <title>{{ _t('Tafel {nummer}, {stoelen} stoelen', nummer=t.nummer, stoelen=t.stoelen) }}{% if gast %}, {{ gast.naam }} ({{ gast.aantal }} p., {{ gast.tijd }}){% elif later %}, {{ _t('vanaf {tijd}', tijd=later.tijd) }} {{ later.naam }}{% endif %}</title>
                 {% if t.vorm == "rond" %}
                 <ellipse cx="{{ x + b / 2 }}" cy="{{ y + h / 2 }}" rx="{{ b / 2 }}" ry="{{ h / 2 }}"
@@ -110,11 +110,12 @@
             {% endfor %}
             {% if not reserveringen and not niet_gekomen %}<li class="leeg">{{ t("Geen reserveringen op deze dag.") }}</li>{% endif %}
         </ul>
-        <div id="toewijzen" hidden style="margin-top: 12px; border-top: 1px solid var(--lijn); padding-top: 12px">
+        <div id="toewijzen" class="toewijzen" hidden>
             <p><b id="toewijzen-titel"></b></p>
             <p class="klein">{{ t("Tik op tafels om ze aan of uit te zetten.") }}</p>
-            <p id="toewijzen-keuze" style="margin-top: 4px; font-size: 13px"></p>
-            <p id="toewijzen-melding" role="alert" style="color: var(--rood); margin-top: 4px; font-size: 13px"></p>
+            <div class="tafelkeuze" id="tafelkeuze" role="group" aria-label="{{ t('Tafel') }}"></div>
+            <p id="toewijzen-keuze" class="toewijzen-keuze"></p>
+            <p id="toewijzen-melding" class="toewijzen-melding" role="alert"></p>
             <div class="knoppen" style="margin-top: 10px">
                 <button type="button" id="toewijzen-opslaan" class="knop klein">{{ t("Tafels opslaan") }}</button>
                 <button type="button" id="toewijzen-annuleren" class="knop klein rand">{{ t("Annuleren") }}</button>
@@ -142,11 +143,34 @@
     const keuze = document.getElementById('toewijzen-keuze');
     const melding = document.getElementById('toewijzen-melding');
     const opslaan = document.getElementById('toewijzen-opslaan');
+    const tafelkeuze = document.getElementById('tafelkeuze');
+    const tafels = {};      // tafelnummer -> het element op de tekening
     let actief = null;      // het <li> van de gekozen reservering
     let gekozen = new Set();  // tafelnummers
 
     function vorm(tafel) { return tafel.querySelector('rect, ellipse'); }
 
+    // Tafelknoppen: op een telefoon zijn de tafeltjes op de tekening te klein om op te tikken.
+    // De knoppen doen hetzelfde als tikken op de tekening en laten tafels die nu bezet zijn niet toe.
+    function wissel(nummer) {
+        if (gekozen.has(nummer)) { gekozen.delete(nummer); } else { gekozen.add(nummer); }
+        teken();
+    }
+    document.querySelectorAll('#plattegrond .tafel').forEach(function (tafel) {
+        const knop = document.createElement('button');
+        knop.type = 'button';
+        knop.className = 'tafelknop';
+        knop.dataset.tafel = tafel.dataset.tafel;
+        const nummer = document.createElement('b');
+        nummer.textContent = tafel.dataset.tafel;
+        const stoelen = document.createElement('small');
+        stoelen.textContent = tafel.dataset.stoelen;
+        knop.append(nummer, stoelen);
+        knop.addEventListener('click', function () { wissel(tafel.dataset.tafel); });
+        tafelkeuze.append(knop);
+        tafels[tafel.dataset.tafel] = tafel;
+    });
+
     function teken() {
         let stoelen = 0;
         document.querySelectorAll('#plattegrond .tafel').forEach(function (tafel) {
@@ -160,6 +184,12 @@
         document.querySelectorAll('#reserveringen .reservering').forEach(function (li) {
             li.classList.toggle('actief', li === actief);
         });
+        tafelkeuze.querySelectorAll('.tafelknop').forEach(function (knop) {
+            const bezetDoor = tafels[knop.dataset.tafel].dataset.bezet;
+            knop.setAttribute('aria-pressed', gekozen.has(knop.dataset.tafel) ? 'true' : 'false');
+            knop.disabled = !actief || (bezetDoor !== '' && bezetDoor !== actief.dataset.kenmerk);  // bezet door een andere reservering
+        });
+        document.body.classList.toggle('toewijzen-open', !!actief);
         if (!actief) { paneel.hidden = true; return; }
         paneel.hidden = false;
         const lijst = Array.from(gekozen);
@@ -179,9 +209,7 @@
         tafel.style.cursor = 'pointer';
         tafel.addEventListener('click', function () {
             if (!actief) { melding.textContent = ''; return; }
-            const nummer = tafel.dataset.tafel;
-            if (gekozen.has(nummer)) { gekozen.delete(nummer); } else { gekozen.add(nummer); }
-            teken();
+            wissel(tafel.dataset.tafel);
         });
     });
 
@@ -196,6 +224,12 @@
         });
     });
 
+    // Op een telefoon is de tijdenbalk een strook: laat de gekozen tijd zien.
+    const gekozenTijd = document.querySelector('.tijdbalk .aan');
+    if (gekozenTijd) { gekozenTijd.scrollIntoView({ inline: 'center', block: 'nearest' }); }
+
+    teken();  // zet de tafelknoppen in de beginstand
+
     document.getElementById('toewijzen-annuleren').addEventListener('click', function () {
         actief = null;
         gekozen = new Set();
````


## Bijlage 4: bestanden van fase 4 (Invoerformulier)

#### Nieuwe bestanden en bestanden die je helemaal vervangt

**`tests/test_invoeren_compact.py`** (nieuw)

````python
"""Het formulier voor telefonische reserveringen en binnenlopers (personeel, fase 4): minder velden vooraf, direct zien of er plek is."""
import shutil
import subprocess
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from sqlalchemy import update

from app.database import get_db, personeel
from tests.test_personeel_reserveren import Basis


class FormulierOpbouwTests(Basis):
    def pagina(self, query=""):
        return self.client.get("/reservering/nieuw" + query).get_data(as_text=True)

    def test_telefonisch_naam_telefoon_aantal_tijd_en_datum_staan_bovenaan(self):
        html = self.pagina(f"?datum={self.dinsdag}")
        meer = html.index('<details class="meer" id="meer"')
        for veld in ("naam", "telefoon", "aantal", "tijd", "datum"):
            self.assertLess(html.index(f'id="{veld}"'), meer, veld)
        for veld in ("email", "taal", "kinderstoelen", "allergieen", "opmerking"):
            self.assertGreater(html.index(f'id="{veld}"'), meer, veld)

    def test_personen_en_tijd_staan_naast_elkaar(self):
        self.assertIn('<div class="twee naast">', self.pagina())

    def test_binnenloper_heeft_naam_en_telefoon_onder_meer_gegevens(self):
        html = self.pagina("?bron=binnenloper")
        meer = html.index('<details class="meer" id="meer"')
        for veld in ("aantal", "tijd", "datum"):
            self.assertLess(html.index(f'id="{veld}"'), meer, veld)
        for veld in ("naam", "telefoon", "email"):
            self.assertGreater(html.index(f'id="{veld}"'), meer, veld)
        self.assertEqual(html.count('id="naam"'), 1)  # nooit twee velden met dezelfde naam

    def test_uitklapblok_is_standaard_dicht(self):
        self.assertNotRegex(self.pagina(f"?datum={self.dinsdag}"), r'<details class="meer" id="meer"\s+open')

    def test_uitklapblok_gaat_open_bij_een_melding(self):
        antwoord = self.invoeren(email="geen-mail")
        self.assertEqual(antwoord.status_code, 400)
        self.assertRegex(antwoord.get_data(as_text=True), r'<details class="meer" id="meer"\s+open')

    def test_uitklapblok_gaat_open_als_er_iets_in_staat(self):
        self.bestaande("18:00", 69)  # vol: waarschuwing
        antwoord = self.invoeren(opmerking="Raamtafel")
        html = antwoord.get_data(as_text=True)
        self.assertIn("Toch opslaan", html)
        self.assertRegex(html, r'<details class="meer" id="meer"\s+open')
        self.assertIn("Raamtafel", html)

    def test_veld_voor_de_ruimtezin_en_nieuwe_tekst_in_de_taal_van_het_account(self):
        self.assertIn('id="ruimte"', self.pagina())
        self.assertIn("Meer gegevens", self.pagina())
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(update(personeel).where(personeel.c.gebruikersnaam == "anna").values(taal="id"))
        self.assertIn("Data lainnya", self.pagina())


class RuimteHulpTests(Basis):
    def ruimte(self, **query):
        vraag = {"datum": self.dinsdag.isoformat(), "tijd": "18:00", "aantal": "4", **query}
        return self.client.get("/reservering/ruimte", query_string=vraag)

    def test_alleen_voor_ingelogd_personeel(self):
        antwoord = self.app.test_client().get("/reservering/ruimte", query_string={
            "datum": self.dinsdag.isoformat(), "tijd": "18:00", "aantal": "4"})
        self.assertEqual(antwoord.status_code, 401)
        self.assertEqual(antwoord.get_json()["status"], "fout")

    def test_er_is_plek(self):
        self.bestaande("18:00", 20)
        data = self.ruimte().get_json()
        self.assertEqual(data["status"], "succes")
        self.assertFalse(data["let_op"])
        self.assertEqual(data["tekst"], "Rond 18:00 is er plek; er blijven 45 van 69 plekken vrij.")

    def test_te_vol_gebruikt_dezelfde_waarschuwing_als_bij_het_opslaan(self):
        self.bestaande("18:00", 68)
        data = self.ruimte().get_json()
        self.assertTrue(data["let_op"])
        self.assertEqual(data["tekst"], "Rond 18:00 zitten er dan 72 gasten tegelijk; het maximum is 69.")
        self.client.post("/reservering/nieuw", data={
            "bron": "telefoon", "naam": "Siti", "telefoon": "0612345678", "datum": self.dinsdag.isoformat(),
            "tijd": "18:00", "aantal": "4"})
        self.assertEqual(len(self.rijen()), 1)  # de hulproute bewaart niets

    def test_gesloten_dag_en_kinderstoelen(self):
        maandag = self.dinsdag - timedelta(days=1)
        self.assertIn("gesloten", self.ruimte(datum=maandag.isoformat()).get_json()["tekst"])
        self.bestaande("18:00", 2, kinderstoelen=2)
        tekst = self.ruimte(kinderstoelen="1").get_json()["tekst"]
        self.assertIn("kinderstoelen nodig", tekst)

    def test_ongeldige_invoer_geeft_400(self):
        for vraag in ({"datum": "morgen"}, {"tijd": "laat"}, {"aantal": "veel"}, {"aantal": "0"}, {"aantal": "201"},
                      {"kinderstoelen": "-1"}, {"datum": ""}):
            self.assertEqual(self.ruimte(**vraag).status_code, 400, vraag)

    def test_in_het_indonesisch(self):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(update(personeel).where(personeel.c.gebruikersnaam == "anna").values(taal="id"))
        self.assertIn("masih ada tempat", self.ruimte().get_json()["tekst"])


class ScriptTests(Basis):
    @unittest.skipUnless(shutil.which("node"), "node is niet geïnstalleerd")
    def test_script_is_geldig_javascript(self):
        html = self.client.get("/reservering/nieuw").get_data(as_text=True)
        script = next(s.split("</script>")[0] for s in html.split("<script>")[1:] if "ruimte" in s.split("</script>")[0])
        with tempfile.TemporaryDirectory() as map_:
            pad = Path(map_) / "invoeren.js"
            pad.write_text(script, encoding="utf-8")
            resultaat = subprocess.run(["node", "--check", str(pad)], capture_output=True, text=True)
        self.assertEqual(resultaat.returncode, 0, resultaat.stderr)
        self.assertNotIn("innerHTML", html)


# De basisklasse zelf heeft geen tests; deze regel voorkomt dat de tests van test_personeel_reserveren hier opnieuw draaien.
del Basis

if __name__ == "__main__":
    unittest.main()
````

**`templates/reservering_nieuw.html`** (vervang het hele bestand door dit)

````html
{% extends "personeel.html" %}
{% block titel %}{{ t("Nieuwe reservering") }} · {{ config.RESTAURANT_NAAM }}{% endblock %}
{% block inhoud %}
<div class="dagnav">
    <h2>{{ t('Binnenloper') if w.bron == 'binnenloper' else t('Nieuwe reservering') }}</h2>
    <a class="pil" href="/overzicht?datum={{ w.datum }}">‹ {{ t("Terug naar het overzicht") }}</a>
</div>

{% if fout %}<div class="melding fout" role="alert">{{ fout }}</div>{% endif %}

{% set is_binnenloper = w.bron == 'binnenloper' %}
{# Het uitklapblok staat open als er iets in staat of als er een melding is, zodat niets verborgen blijft. #}
{% set meer_open = fout or waarschuwingen or w.email or w.allergieen or w.opmerking or (w.kinderstoelen or '0') != '0'
                   or (is_binnenloper and (w.naam or w.telefoon)) %}
<div class="paneel paneel-smal">
    <form action="/reservering/nieuw" method="POST" id="invoeren">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <input type="hidden" name="bron" value="{{ w.bron or 'telefoon' }}">

        {% if not is_binnenloper %}
        <div class="veld">
            <label for="naam">{{ t("Naam") }}</label>
            <input type="text" id="naam" name="naam" value="{{ w.naam }}" required maxlength="100" autocomplete="off">
        </div>
        <div class="veld">
            <label for="telefoon">{{ t("Telefoon") }}</label>
            <input type="tel" id="telefoon" name="telefoon" value="{{ w.telefoon }}" required maxlength="20" autocomplete="off" inputmode="tel">
        </div>
        {% endif %}
        <div class="twee naast">
            <div class="veld">
                <label for="aantal">{{ t("Personen") }}</label>
                <input type="number" id="aantal" name="aantal" value="{{ w.aantal }}" required min="1" max="{{ max_personen }}" inputmode="numeric">
            </div>
            <div class="veld">
                <label for="tijd">{{ t("Tijd") }}</label>
                <input type="time" id="tijd" name="tijd" value="{{ w.tijd }}" required step="300">
            </div>
        </div>
        <div class="veld">
            <label for="datum">{{ t("Datum") }}</label>
            <input type="date" id="datum" name="datum" value="{{ w.datum }}" required min="{{ vandaag.isoformat() }}">
        </div>
        <p class="hint ruimte" id="ruimte" aria-live="polite" hidden></p>

        <details class="meer" id="meer" {{ 'open' if meer_open }}>
            <summary>{{ t("Meer gegevens") }} <small>({{ t("niet verplicht") }})</small></summary>
            <div class="extra">
                {% if is_binnenloper %}
                <div class="veld">
                    <label for="naam">{{ t("Naam") }} ({{ t("niet verplicht") }})</label>
                    <input type="text" id="naam" name="naam" value="{{ w.naam }}" maxlength="100" autocomplete="off"
                           placeholder="{{ t('Binnenloper') }}">
                </div>
                <div class="veld">
                    <label for="telefoon">{{ t("Telefoon") }} ({{ t("niet verplicht") }})</label>
                    <input type="tel" id="telefoon" name="telefoon" value="{{ w.telefoon }}" maxlength="20" autocomplete="off" inputmode="tel">
                </div>
                {% endif %}
                <div class="veld">
                    <label for="email">{{ t("E-mail (niet verplicht; dan krijgt de gast een bevestigingsmail)") }}</label>
                    <input type="email" id="email" name="email" value="{{ w.email }}" maxlength="254" autocomplete="off">
                </div>
                {% if talen | length > 1 %}
                <div class="veld">
                    <label for="taal">{{ t("Taal van de gast (voor de mail)") }}</label>
                    <select id="taal" name="taal">
                        {% for code in talen %}
                        <option value="{{ code }}" {{ 'selected' if w.taal == code }}>{{ taalnamen[code] }}</option>
                        {% endfor %}
                    </select>
                </div>
                {% endif %}
                <div class="veld" style="max-width: 180px">
                    <label for="kinderstoelen">{{ t("Kinderstoelen") }}</label>
                    <select id="kinderstoelen" name="kinderstoelen">
                        {% for n in range(0, 6) %}
                        <option value="{{ n }}" {{ 'selected' if (w.kinderstoelen or '0') == n | string }}>{{ n }}</option>
                        {% endfor %}
                    </select>
                </div>
                {% if regels.vraag_allergieen %}
                <div class="veld">
                    <label for="allergieen">{{ t("Allergieën") }} ({{ t("niet verplicht") }})</label>
                    <input type="text" id="allergieen" name="allergieen" value="{{ w.allergieen }}" maxlength="200" autocomplete="off">
                    <label class="klein-akkoord"><input type="checkbox" name="allergie_toestemming" value="1"
                           {{ 'checked' if w.allergie_toestemming == '1' }}>
                        {{ t("De gast geeft toestemming om de allergieën te bewaren (ze worden de nacht na het bezoek gewist).") }}</label>
                </div>
                {% endif %}
                <div class="veld">
                    <label for="opmerking">{{ t("Opmerking") }} ({{ t("niet verplicht") }})</label>
                    <textarea id="opmerking" name="opmerking" rows="2" maxlength="300">{{ w.opmerking }}</textarea>
                </div>
            </div>
        </details>

        {% if waarschuwingen %}
        <div class="melding fout" role="alert">
            <b>{{ t("Let op:") }}</b>
            <ul>{% for tekst in waarschuwingen %}<li>{{ tekst }}</li>{% endfor %}</ul>
            {{ t('Klopt het toch? Kies dan "Toch opslaan".') }}
        </div>
        <input type="hidden" name="bevestigd" value="1" id="bevestigd">
        <button type="submit" class="knop klein" id="opslaan">{{ t("Toch opslaan") }}</button>
        {% else %}
        <button type="submit" class="knop klein">{{ t("Reservering opslaan") }}</button>
        {% endif %}
    </form>
</div>
<script>
// Wie na de waarschuwing iets verandert, krijgt opnieuw de controle: "Toch opslaan" geldt alleen voor wat er stond.
(function () {
    const vlag = document.getElementById('bevestigd');
    if (!vlag) return;
    document.getElementById('invoeren').addEventListener('input', function () {
        vlag.remove();
        document.getElementById('opslaan').textContent = {{ t('Reservering opslaan') | tojson }};
    }, { once: true });
})();

// Laat bij het invullen zien of er plek is. Alleen een hulp: opslaan blijft werken zoals voorheen, ook zonder dit.
(function () {
    const form = document.getElementById('invoeren');
    const plek = document.getElementById('ruimte');
    let teller = 0;
    let timer = null;
    async function ververs() {
        const e = form.elements;
        if (!e.datum.value || !e.tijd.value || !e.aantal.value) { plek.hidden = true; return; }
        const nummer = ++teller;
        try {
            const vraag = new URLSearchParams({
                datum: e.datum.value, tijd: e.tijd.value, aantal: e.aantal.value, kinderstoelen: e.kinderstoelen.value
            });
            const antwoord = await fetch('/reservering/ruimte?' + vraag.toString());
            const data = await antwoord.json();
            if (nummer !== teller) { return; }
            if (!antwoord.ok || data.status !== 'succes') { plek.hidden = true; return; }
            plek.textContent = data.tekst;  // textContent: de tekst komt van de server en wordt nooit als HTML uitgevoerd
            plek.classList.toggle('let-op', !!data.let_op);
            plek.hidden = false;
        } catch (fout) {
            if (nummer === teller) { plek.hidden = true; }
        }
    }
    form.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(ververs, 300); });
    ververs();
})();
</script>
{% endblock %}
````

#### Gewijzigde bestanden (regels met `-` weg, regels met `+` erbij; de rest is omgeving)

**`app/routes/invoeren.py`**

````diff
@@ -8,7 +8,10 @@ restaurant die dag gesloten, dan toont de pagina eerst een waarschuwing. Pas na
 wordt de reservering bewaard. Er wordt nooit iets geblokkeerd behalve een dag in het verleden,
 een ongeldig veld of een dubbele boeking.
 """
-from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
+from datetime import date, time
+from types import SimpleNamespace
+
+from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
 from pydantic import ValidationError
 from sqlalchemy.exc import OperationalError
 
@@ -57,6 +60,38 @@ def _waarschuwingen(regels, gegevens):
     return lijst
 
 
+def _ruimtetekst(regels, dag, tijdstip, aantal, kinderstoelen):
+    """
+    De zin onder het formulier: past deze groep, of wat het personeel anders moet weten. Dezelfde controle als
+    bij het opslaan (_waarschuwingen); geeft (tekst, let_op) terug en bewaart niets.
+    """
+    waarschuwingen = _waarschuwingen(regels, SimpleNamespace(datum=dag, tijd=tijdstip, aantal=aantal, kinderstoelen=kinderstoelen))
+    if waarschuwingen:
+        return " ".join(waarschuwingen), True
+    gasten, _ = drukte_bij(get_db(), dag.isoformat(), tijdstip.strftime("%H:%M"), regels.zitduur_minuten)
+    return t("Rond {tijd} is er plek; er blijven {vrij} van {maximum} plekken vrij.", tijd=tijdstip.strftime("%H:%M"),
+             vrij=regels.max_gasten_tegelijk - gasten - aantal, maximum=regels.max_gasten_tegelijk), False
+
+
+@invoeren_bp.route('/ruimte', methods=['GET'])
+@login_vereist(json_response=True)
+@rate_limit('personeel-ruimte', 120, 600, json_response=True)
+def ruimte():
+    """Hulp voor het formulier: is er plek op deze dag en tijd? GET /reservering/ruimte?datum=...&tijd=...&aantal=..."""
+    regels = current_app.config['REGELS']
+    try:
+        dag = date.fromisoformat(request.args.get('datum', ''))
+        tijdstip = time.fromisoformat(request.args.get('tijd', ''))
+        aantal = int(request.args.get('aantal', ''))
+        kinderstoelen = int(request.args.get('kinderstoelen') or 0)
+    except ValueError:
+        return jsonify({"status": "fout"}), 400
+    if not 1 <= aantal <= MAX_PERSONEN_PERSONEEL or not 0 <= kinderstoelen <= 20:
+        return jsonify({"status": "fout"}), 400
+    tekst, let_op = _ruimtetekst(regels, dag, tijdstip, aantal, kinderstoelen)
+    return jsonify({"status": "succes", "tekst": tekst, "let_op": let_op})
+
+
 @invoeren_bp.route('/nieuw', methods=['GET'])
 @login_vereist
 def nieuw():
````

**`static/css/huisstijl.css`**

````diff
@@ -324,6 +324,12 @@ fieldset.stap { min-width: 0; position: relative; }  /* min-width: anders rekt d
     .dagnav input[type=search] { flex: 1; width: auto; min-width: 0; }
     .indeling, .indeling.cijfers { grid-template-columns: 1fr; }
 }
+/* Formulier voor telefonische reserveringen: de zin over de ruimte */
+.ruimte { margin: -4px 0 16px; font-size: 13px; }
+.ruimte.let-op { color: var(--accent); }
+.paneel details.meer { margin-bottom: 16px; }
+.paneel .twee.naast { grid-template-columns: 1fr 1fr; }  /* personen en tijd blijven ook op een telefoon naast elkaar */
+
 /* Plattegrond: het paneel om tafels toe te wijzen. Op een telefoon is het een vaste balk met tafelknoppen. */
 .toewijzen { margin-top: 12px; border-top: 1px solid var(--lijn); padding-top: 12px; }
 .toewijzen-keuze { margin-top: 4px; font-size: 13px; }
````

**`vertalingen/en.toml`**

````diff
@@ -285,6 +285,8 @@
 "Reserveringsformulier" = "Booking form"
 "Uitloggen" = "Log out"
 "Menu" = "Menu"
+"Meer gegevens" = "More details"
+"Rond {tijd} is er plek; er blijven {vrij} van {maximum} plekken vrij." = "There is room around {tijd}; {vrij} of {maximum} seats stay free."
 
 # plattegrond.html
 "is er" = "arrived"
````

**`vertalingen/id.toml`**

````diff
@@ -285,6 +285,8 @@
 "Reserveringsformulier" = "Formulir reservasi"
 "Uitloggen" = "Keluar"
 "Menu" = "Menu"
+"Meer gegevens" = "Data lainnya"
+"Rond {tijd} is er plek; er blijven {vrij} van {maximum} plekken vrij." = "Sekitar pukul {tijd} masih ada tempat; {vrij} dari {maximum} kursi tetap kosong."
 
 # plattegrond.html
 "is er" = "sudah datang"
````

