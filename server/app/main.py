from fastapi import FastAPI

app = FastAPI(title="forged-in-the-ai")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
