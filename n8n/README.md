# n8n-workflow

Hier staat de export van de n8n-workflow die berichten omzet naar een reservering via
`POST /api/v1/ai-reservering` (header `X-API-Key`). Een nieuwe vestiging importeert dit bestand in n8n.

## Exporteren (alleen jij, niet Cline)

Cline stuurt alles wat het leest naar DeepSeek. Exporteer en schoon het bestand dus zelf op, en laat Cline het niet openen.

1. Download de workflow in n8n als JSON (zie de n8n-documentatie over exporteren als je de knop niet vindt).
2. Sla hem op als `n8n/reservering.json`.
3. Haal alles weg wat bij één installatie of persoon hoort:
   - de waarde van de header `X-API-Key`: vervang die door `VUL_IN` of door een n8n-expressie (begint met `={{`), of gebruik een n8n-credential;
   - het adres van de Render-service: vervang het door `https://VUL_IN/api/v1/ai-reservering`;
   - telefoonnummers, e-mailadressen of namen van echte gasten uit testdata (pinned data).
4. Draai de tests: `tests/test_n8n_export.py` weigert het bestand als er nog een sleutel, een Render- of Neon-adres
   of een connection string in staat.

## Importeren voor een vestiging

Importeer het bestand in n8n, vul bij de HTTP-stap het adres van de Render-service van die vestiging in en
gebruik een credential met de `API_KEY` van die vestiging. Zie ook `docs/NIEUW-RESTAURANT.md`, stap 7.
