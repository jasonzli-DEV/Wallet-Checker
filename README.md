# Wallet-Checker

A small Flask app to derive BTC/ETH/SOL addresses from generated mnemonics, check balances (via Ankr), and persist results.

This project provides a simple web UI, background auto-generation, persistent settings, and basic stats. It's prepared to run inside a Pterodactyl Python environment (binds to `PORT` and reads `PASSWORD` from `.env`).

## Quick start

1. Create and activate a Python 3 virtualenv (optional):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` in the project root (example):

```env
PORT=6060
PASSWORD=changeme
```

4. Run:

```bash
python app.py
```

Open http://localhost:6060 and login with the `PASSWORD` value.

## Pterodactyl notes

- When deploying to Pterodactyl, use a Python 3 egg and set the startup command to:

```bash
python3 app.py
```

- Pterodactyl provides a `PORT` environment variable; `app.py` reads `PORT` from the environment so no changes are required. Make sure to set `PASSWORD` in the panel's environment variables or a `.env` file.

- Install dependencies either by building a custom Docker image that includes `pip install -r requirements.txt` or by running that command in the server's startup task.

## Security

- This is a development/demo Flask app and should not be exposed to the public without additional hardening (production WSGI, HTTPS, authentication improvements, rate limiting).

## Files of interest

- `app.py` — main Flask app and UI
- `data_store.py` — SQLite helpers (results, checks, settings)
- `requirements.txt` — Python dependencies
- `.env` — port and password (not checked into git)

If you want, I can also add a `Procfile`, a systemd unit, or a dockerfile for Pterodactyl — which would you prefer?
