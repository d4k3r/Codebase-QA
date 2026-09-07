"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.routes import router
from app.config import get_settings


app = FastAPI(title=get_settings().app_name)
app.include_router(router)
