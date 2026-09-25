# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A Flask-based restaurant reservation system, built as a **whitelabel template** ("Whitelabel Agency Templates" per `app/config.py`) — the intent is that a new restaurant client is onboarded by only changing values in `.env`, not code. The UI text, code comments, and validation messages are in Dutch (`naam`, `reservering`, `personeel`, etc.).

Core flow: a public booking form (`/`) POSTs to `/reservering`, which validates input, checks slot capacity, writes to SQLite, and fires an async confirmation email. A second entry point, `/api/v1/ai-reservering`, accepts free-text (e.g. from a WhatsApp bot) and uses Anthropic's Claude with forced tool-use to extract structured reservation data before running the same capacity-check/insert flow. Staff log in at `/login` to view/manage bookings at `/overzicht`.

## Commands

There is no `requirements.txt` — dependencies are only reflected in the existing `venv`. When adding dependencies, install into `venv` and consider generating a requirements file.

```powershell
# Activate the virtualenv (PowerShell)
venv\Scripts\Activate.ps1

# Run the app (dev server, debug=True, on http://127.0.0.1:5000)
python run.py
```

There are no test files, lint configs, or build steps in this repo currently.

`run.py` calls `init_db()` on every startup, which creates tables if missing, seeds an `admin` user (password from `ADMIN_INITIAL_PASSWORD` env var) if `personeel` is empty, and prunes reservations older than `RETENTIE_DAGEN_AVG` days.

## Architecture

**App factory** (`app/__init__.py`): `create_app()` builds the Flask app from `Config` and registers two blueprints — `web_bp` (HTML pages + form POSTs, no prefix) and `api_bp` (JSON webhook, `/api/v1` prefix).

**Configuration** (`app/config.py`): all environment/branding/business config lives in one `Config` class, read via `os.getenv` with defaults, loaded from `.env` through `python-dotenv` if available. This is the single place whitelabel customization happens (restaurant name, capacity limits, SMTP creds, secret key, webhook key, Anthropic model name).

**Database** (`app/database.py`): raw `sqlite3` (no ORM), with `Row` factory for dict-like access. WAL mode + 5s busy timeout are set on every connection for concurrency. Connections are opened and closed per-request manually (`get_db_connection()` / `conn.close()`) — there's no connection pooling or teardown hook. Booking creation uses `BEGIN EXCLUSIVE` transactions to serialize the capacity check + insert against race conditions on the same date/time slot.

**Validation** (`app/schemas.py`): Pydantic models define the two external contracts:
- `ReserveringSchema` — the public booking form payload, including a honeypot `website` field (must be empty) and a `privacy_akkoord: Literal[True]` consent gate.
- `AIWebhookSchema` / `AIReserveringExtractieSchema` — the webhook input (`klant_tekst`) and the structure Claude must extract from it.

**Routes**:
- `app/routes/web.py` — public pages (`/`, `/privacy`, `/bevestiging`), staff auth (`/login`, `/logout`, session-based via Flask `session['ingelogd']`), the booking overview (`/overzicht`, optionally filtered by `?datum=`), booking deletion (`/verwijder/<id>`, staff-only), and customer self-service cancellation (`/annuleren/<id>`, no auth — reachable via the emailed cancellation link).
- `app/routes/api.py` — `/api/v1/ai-reservering`, gated by a static `X-API-Key` header checked against `WEBHOOK_API_KEY` (`require_api_key` decorator). Sanitizes free-text input, calls Claude for extraction, then re-runs the same capacity-check/insert transaction pattern as the web route.

**Services**:
- `app/services/ai_service.py` — wraps the Anthropic client. `sanitize_user_input` strips newlines/tabs and prompt-injection markers (```` ``` ````, `[system]`, `<system>`) before the text reaches the model. `verwerk_tekst_met_anthropic` forces tool use (`tool_choice={"type": "tool", ...}`) against a tool schema generated directly from `AIReserveringExtractieSchema.model_json_schema()`, and injects today's/tomorrow's date into the system prompt so the model can resolve relative dates ("morgen", "vrijdag") into absolute `YYYY-MM-DD`.
- `app/services/email_service.py` — sends confirmation emails on a daemon thread (`stuur_bevestigingsmail_async`) so SMTP latency doesn't block the request. Falls back to a console "simulation" log instead of actually sending if `VERZENDER_WACHTWOORD` is unset or `VERZENDER_EMAIL` is still the placeholder — this is the expected local-dev behavior, not a bug.

**Capacity logic**: both booking paths (web form and AI webhook) independently implement the identical pattern — `BEGIN EXCLUSIVE`, sum existing `aantal` for the `(datum, tijd)` slot, compare against `MAX_CAPACITEIT_PER_SLOT`, insert if there's room. Keep these two implementations in sync if the capacity rule changes.

**Templates** (`templates/`): server-rendered Jinja2, styled with Tailwind utility classes (via CDN, no build step), reading branding values straight from `config.*` (e.g. `config.RESTAURANT_NAAM`). The booking form on `index.html` is submitted via `fetch()` as JSON rather than a normal form POST, so client-side validation/type-coercion must match the Pydantic schema exactly (e.g. `aantal` is parsed to an int, `privacy_akkoord` to a bool).
