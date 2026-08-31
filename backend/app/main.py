from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def read_root():
    return {"status": "OK", "service": "Problem Finder", "version": "1.0.0"}