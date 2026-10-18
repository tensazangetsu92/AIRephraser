# app/routers/pages.py
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jinja2 import select_autoescape
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.database import UserHistory, get_db
from auth import REFRESH_COOKIE_NAME, get_user_from_refresh_session

router = APIRouter(tags=["pages"])

templates_dir = Path(__file__).parent.parent.parent.parent / "frontend" / "html"
templates = Jinja2Templates(directory=str(templates_dir))
templates.env.autoescape = select_autoescape(
    enabled_extensions=("html", "xml"),
    default_for_string=True,
)


def _css_bundle_url() -> str:
    """Return the immutable, content-versioned CSS bundle URL for templates."""
    bundle_path = templates_dir.parent / "css" / "app.css"
    digest = sha256(bundle_path.read_bytes()).hexdigest()[:16]
    return f"/css/app.css?v={digest}"


templates.env.globals["css_bundle_url"] = _css_bundle_url

AVAILABLE_HISTORY_TOOL_TYPES = ("study_work", "humanizer", "detector", "paraphraser")
PUBLIC_PAGE_CACHE_CONTROL = "public, max-age=300, must-revalidate"
PRIVATE_PAGE_CACHE_CONTROL = "private, no-store"


def _public_template(request: Request, name: str):
    """Render a page that contains no server-side user data."""
    response = templates.TemplateResponse(request=request, name=name)
    response.headers["Cache-Control"] = PUBLIC_PAGE_CACHE_CONTROL
    return response


def _private_template(request: Request, name: str, context: dict | None = None):
    """Prevent browser or intermediary caching of an authenticated page."""
    response = templates.TemplateResponse(request=request, name=name, context=context or {})
    response.headers["Cache-Control"] = PRIVATE_PAGE_CACHE_CONTROL
    return response


def _private_page_redirect(
        request: Request,
        refresh_token: str | None,
        db: Session,
) -> RedirectResponse | None:
    """Redirect unauthenticated browser navigation before private HTML is rendered."""
    if get_user_from_refresh_session(db, refresh_token):
        return None

    requested_path = request.url.path
    if request.url.query:
        requested_path = f"{requested_path}?{request.url.query}"
    response = RedirectResponse(url=f"/auth?next={quote(requested_path, safe='/?=&')}", status_code=303)
    response.headers["Cache-Control"] = PRIVATE_PAGE_CACHE_CONTROL
    return response


def _require_owned_history(
        db: Session,
        history_id: int,
        user_id: int,
        tool_type: str | None = None,
) -> None:
    """Allow rendering a history page only for its owner and matching tool."""
    query = db.query(UserHistory.id).filter(
        UserHistory.id == history_id,
        UserHistory.user_id == user_id,
    )
    if tool_type:
        query = query.filter(UserHistory.tool_type == tool_type)
    else:
        query = query.filter(UserHistory.tool_type.in_(AVAILABLE_HISTORY_TOOL_TYPES))

    if query.first() is None:
        # A 404 deliberately does not disclose whether this ID exists for another user.
        raise HTTPException(status_code=404, detail="Текст не найден")


@router.get("/")
async def root(request: Request):
    return _public_template(request, "home.html")


@router.get("/humanize", response_class=HTMLResponse)
async def humanize_page(request: Request):
    return _public_template(request, "humanizer.html")


@router.get("/humanize/{history_id}", response_class=HTMLResponse)
async def humanize_history_page(
        request: Request,
        history_id: int,
        refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
        db: Session = Depends(get_db),
):
    redirect = _private_page_redirect(request, refresh_token, db)
    if redirect:
        return redirect
    current_user = get_user_from_refresh_session(db, refresh_token)
    _require_owned_history(db, history_id, current_user.id, "humanizer")
    return _private_template(request, "humanizer.html")


@router.get("/humanizer", include_in_schema=False)
async def legacy_humanizer_route():
    return RedirectResponse(url="/humanize", status_code=307)


@router.get("/auth", response_class=HTMLResponse)
async def auth_page(request: Request):
    return _public_template(request, "auth.html")


@router.get("/cookies", response_class=HTMLResponse)
async def cookies_page(request: Request):
    return _public_template(request, "cookies.html")


@router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    return _public_template(request, "terms.html")


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return _public_template(request, "privacy.html")


@router.get("/contacts", response_class=HTMLResponse)
async def contacts_page(request: Request):
    return _public_template(request, "contacts.html")


@router.get("/support", response_class=HTMLResponse)
async def support_page(request: Request):
    return _public_template(request, "support.html")


@router.get("/how-it-works", response_class=HTMLResponse)
async def how_it_works_page(request: Request):
    return _public_template(request, "how-it-works.html")


@router.get("/study-work", response_class=HTMLResponse)
async def study_work_page(request: Request):
    return _public_template(request, "study-work.html")


@router.get("/study-work/{history_id}", response_class=HTMLResponse)
async def study_work_history_page(
        request: Request,
        history_id: int,
        refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
        db: Session = Depends(get_db),
):
    redirect = _private_page_redirect(request, refresh_token, db)
    if redirect:
        return redirect
    current_user = get_user_from_refresh_session(db, refresh_token)
    _require_owned_history(db, history_id, current_user.id, "study_work")
    return _private_template(request, "study-work.html")

@router.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    return _public_template(request, "pricing.html")


@router.get("/detector", response_class=HTMLResponse)
async def detector(request: Request):
    return _public_template(request, "detector.html")


@router.get("/detector/{history_id}", response_class=HTMLResponse)
async def detector_history_page(
        request: Request,
        history_id: int,
        refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
        db: Session = Depends(get_db),
):
    redirect = _private_page_redirect(request, refresh_token, db)
    if redirect:
        return redirect
    current_user = get_user_from_refresh_session(db, refresh_token)
    _require_owned_history(db, history_id, current_user.id, "detector")
    return _private_template(request, "detector.html")


@router.get("/paraphraser", response_class=HTMLResponse)
async def paraphraser(request: Request):
    return _public_template(request, "paraphraser.html")


@router.get("/paraphraser/{history_id}", response_class=HTMLResponse)
async def paraphraser_history_page(
        request: Request,
        history_id: int,
        refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
        db: Session = Depends(get_db),
):
    redirect = _private_page_redirect(request, refresh_token, db)
    if redirect:
        return redirect
    current_user = get_user_from_refresh_session(db, refresh_token)
    _require_owned_history(db, history_id, current_user.id, "paraphraser")
    return _private_template(request, "paraphraser.html")


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(
        request: Request,
        refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
        db: Session = Depends(get_db),
):
    redirect = _private_page_redirect(request, refresh_token, db)
    if redirect:
        return redirect
    return _private_template(request, "profile.html")


@router.get("/history", response_class=HTMLResponse)
async def history_page(
        request: Request,
        refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
        db: Session = Depends(get_db),
):
    redirect = _private_page_redirect(request, refresh_token, db)
    if redirect:
        return redirect
    return _private_template(request, "history.html")


@router.get("/history/{history_id}", response_class=HTMLResponse)
async def history_detail_page(
        request: Request,
        history_id: int,
        refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
        db: Session = Depends(get_db),
):
    redirect = _private_page_redirect(request, refresh_token, db)
    if redirect:
        return redirect
    current_user = get_user_from_refresh_session(db, refresh_token)
    _require_owned_history(db, history_id, current_user.id)
    return _private_template(request, "history-detail.html", {"history_id": history_id})
