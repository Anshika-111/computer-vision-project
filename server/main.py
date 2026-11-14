"""FastAPI application for ChromaFix; run with `uvicorn server.main:app`. Author: Iris."""

from fastapi import FastAPI

from server.routes import logs

app = FastAPI(title="ChromaFix API")

app.include_router(logs.router, prefix="/api")
