"""FastAPI application for ChromaFix; run with `uvicorn server.main:app`. Author: Iris."""

from fastapi import FastAPI

from server.routes import logs, matrix, methods

app = FastAPI(title="ChromaFix API")

app.include_router(logs.router, prefix="/api")
app.include_router(matrix.router, prefix="/api")
app.include_router(methods.router, prefix="/api")
