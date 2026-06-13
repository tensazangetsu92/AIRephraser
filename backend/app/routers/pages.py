# app/routers/pages.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter(tags=["pages"])

templates_dir = Path(__file__).parent.parent.parent.parent / "frontend" / "html"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/")
async def root(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="humanizer.html"
    )


@router.get("/humanizer")
async def humanizer_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="humanizer.html"
    )


@router.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="pricing.html"
    )


@router.get("/detector", response_class=HTMLResponse)
async def detector(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="detector.html"
    )


@router.get("/paraphraser", response_class=HTMLResponse)
async def paraphraser(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="paraphraser.html"
    )


@router.get("/grammar", response_class=HTMLResponse)
async def grammar(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="grammar.html"
    )


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="profile.html"
    )


@router.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="history.html"
    )