from fastapi import FastAPI

app = FastAPI(title="TraceX API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
