"""FastAPI application for ChromaFix; run with `uvicorn server.main:app`. Author: Iris."""

from fastapi import FastAPI

from server.routes import games, images, logs, matrix, methods, plates, screening

app = FastAPI(title="ChromaFix API")

app.include_router(logs.router, prefix="/api")
app.include_router(matrix.router, prefix="/api")
app.include_router(methods.router, prefix="/api")
app.include_router(images.router, prefix="/api")
app.include_router(plates.router, prefix="/api")
app.include_router(screening.router, prefix="/api")
app.include_router(games.router, prefix="/api")
