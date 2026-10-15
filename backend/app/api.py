# app/api.py
from fastapi import APIRouter
from app.routers import router as routers_combined

router = APIRouter()
router.include_router(routers_combined)
