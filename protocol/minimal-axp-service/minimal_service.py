from fastapi import FastAPI

app = FastAPI()
_store: dict[str, dict] = {}


@app.post("/v1/intents")
def create_intent(payload: dict) -> dict:
    intent_id = payload.get("correlation_id", "intent-demo")
    _store[intent_id] = {
        "intent_id": intent_id,
        "status": "COMPLETED",
        "result": {"accepted": True},
    }
    return {"intent_id": intent_id, "status": "CREATED"}


@app.get("/v1/intents/{intent_id}")
def get_intent(intent_id: str) -> dict:
    return _store.get(intent_id, {"intent_id": intent_id, "status": "NOT_FOUND"})
