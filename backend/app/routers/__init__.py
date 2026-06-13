# app/routers/__init__.py
from fastapi import APIRouter

from . import pages
from . import auth_routes
from . import user_routes
from . import subscription_routes
from . import humanize_routes

router = APIRouter()

router.include_router(pages.router)
router.include_router(auth_routes.router)
router.include_router(user_routes.router)
router.include_router(subscription_routes.router)
router.include_router(humanize_routes.router)