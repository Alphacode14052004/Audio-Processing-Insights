# Real-Time Audio Intelligence Backend

Backend-only FastAPI service for real-time audio chunk processing over WebSocket with SQLite persistence.

## WSL + venv setup (recommended)

```bash
python3 -m venv .venv_wsl
source .venv_wsl/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

## Run the API from WSL

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- Health check: `GET http://localhost:8000/`
- Swagger docs: `http://localhost:8000/docs`

## Run pipeline test script

With server running in one terminal:

```bash
cd /mnt/c/Users/Venkataraman\ P/Documents/Code/Audio_Processing_Flow
source .venv_wsl/bin/activate
python test_pipeline.py
```

## Notes

- `backend/.env` includes defaults and placeholder keys.
- Recording WAV files are stored under `backend/recordings/`.
- STUB services are marked with `# STUB` and `# TODO` for AI integrations.
