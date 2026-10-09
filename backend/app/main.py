from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="PriorityGrid API",
    description="Backend API for the PriorityGrid decision-and-control application.",
    version="1.0.0"
)

class StatusResponse(BaseModel):
    status: str
    message: str

@app.get("/", response_model=StatusResponse)
async def root():
    return {"status": "ok", "message": "PriorityGrid Backend API is running."}

@app.get("/health", response_model=StatusResponse)
async def health_check():
    return {"status": "ok", "message": "Healthy"}
