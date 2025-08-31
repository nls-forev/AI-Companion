# Runbook — RTX 4050 (Local Dev)

## Prereqs
- Nvidia drivers + CUDA/CUDNN (for GPU acceleration)
- Docker + Docker Compose
- Python 3.10+

## Start Datastores (Redis, Qdrant)
```bash
cd /media/klasta/New\ Volume1/Apps/projects/Companion
docker compose up -d
```

## Python venv + install deps
```bash
cd /media/klasta/New\ Volume1/Apps/projects/Companion/backend
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

## Run FastAPI backend (WS on :8000)
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Open Web client
- Use a simple static server or VSCode Live Server to serve `web/`.
- Example with `python -m http.server`:
```bash
cd /media/klasta/New\ Volume1/Apps/projects/Companion/web
python -m http.server 5500
```
- Open http://localhost:5500
- Click "Connect" then "Send Test Utterance" to see stub messages and simple avatar reaction.

## Next Steps
- Wire microphone capture in web client and stream to backend
- Add faster-whisper streaming in backend; echo partials to client
- Implement emotion engine and persist mood in Redis
- Add Qdrant collection for episodic memory and simple write policy
- Integrate TTS endpoint (RTX 4060 laptop) and stream audio + visemes back to client 