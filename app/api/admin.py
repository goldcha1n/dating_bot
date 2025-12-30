from __future__ import annotations

from datetime import datetime
from typing import AsyncIterator, Optional
import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth import create_session_token, read_session_token, verify_credentials
from app.config import Settings, TEMPLATES_DIR
from app.db import session_scope
from app.models import AdminAction, Message, User, Complaint

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
logger = logging.getLogger(__name__)


async def notify_user(bot_token: str, tg_id: int, text: str) -> None:
    bot = Bot(token=bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        await bot.send_message(tg_id, text)
    except Exception:
        logger.exception("Failed to notify user tg_id=%s", tg_id)
    finally:
        await bot.session.close()


def get_sessionmaker(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.sessionmaker


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with session_scope(sessionmaker) as session:
        yield session


async def require_admin(
    request: Request, settings: Settings = Depends(get_settings_dep)
) -> str:
    token = request.cookies.get("admin_session")
    if not token:
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})
    session = read_session_token(token, settings)
    if not session:
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})
    return session.username


@router.get("/admin/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/admin/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    settings: Settings = Depends(get_settings_dep),
):
    if not verify_credentials(username, password, settings):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Невірний логін або пароль"},
            status_code=401,
        )
    token = create_session_token(username, settings)
    response = RedirectResponse(url="/admin", status_code=303)
    response.set_cookie(
        "admin_session",
        token,
        httponly=True,
        samesite="lax",
        max_age=settings.session_ttl_seconds,
    )
    return response


@router.get("/admin/logout")
async def logout() -> RedirectResponse:
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie("admin_session")
    return response


@router.get("/admin", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    admin_username: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    counts = {"users": 0, "messages": 0, "actions": 0, "complaints": 0}
    try:
        counts["users"] = (await session.execute(select(func.count(User.id)))).scalar_one()
        counts["messages"] = (await session.execute(select(func.count(Message.id)))).scalar_one()
        counts["actions"] = (await session.execute(select(func.count(AdminAction.id)))).scalar_one()
        counts["complaints"] = (await session.execute(select(func.count(Complaint.id)))).scalar_one()
    except OperationalError:
        pass
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "counts": counts, "admin_username": admin_username},
    )


@router.get("/admin/users", response_class=HTMLResponse)
async def users_list(
    request: Request,
    admin_username: str = Depends(require_admin),
    q: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default=None),
    order: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    session: AsyncSession = Depends(get_session),
):
    per_page = 20
    sort_field = (sort or "created_at").lower()
    sort_order = (order or "desc").lower()

    complaints_subq = (
        select(Complaint.target_user_id.label("target_id"), func.count(Complaint.id).label("complaints"))
        .group_by(Complaint.target_user_id)
        .subquery()
    )

    sort_map = {
        "id": (User.id,),
        "tg_id": (User.tg_id,),
        "username": (User.username,),
        "name": (User.first_name, User.last_name, User.name),
        "is_banned": (User.is_banned,),
        "created_at": (User.created_at,),
        "complaints": (func.coalesce(complaints_subq.c.complaints, 0), User.id),
    }
    if sort_field not in sort_map:
        sort_field = "created_at"
    if sort_order not in {"asc", "desc"}:
        sort_order = "desc"

    stmt = select(User, func.coalesce(complaints_subq.c.complaints, 0).label("complaints")).outerjoin(
        complaints_subq, complaints_subq.c.target_id == User.id
    )
    if q:
        if q.isdigit():
            stmt = stmt.where(User.tg_id == int(q))
        else:
            stmt = stmt.where(User.username.ilike(f"%{q}%"))
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    order_by_columns = [
        col.asc() if sort_order == "asc" else col.desc() for col in sort_map[sort_field]
    ]
    stmt = stmt.order_by(*order_by_columns).offset((page - 1) * per_page).limit(per_page)
    result = await session.execute(stmt)
    users = [{"user": row[0], "complaints": row[1]} for row in result.all()]
    total_pages = max(1, (total + per_page - 1) // per_page)
    return templates.TemplateResponse(
        "users.html",
        {
            "request": request,
            "users": users,
            "q": q or "",
            "sort": sort_field,
            "order": sort_order,
            "complaints_sort_value": "complaints",
            "page": page,
            "total_pages": total_pages,
            "admin_username": admin_username,
        },
    )


@router.get("/admin/profiles", response_class=HTMLResponse)
async def profiles_list(
    request: Request,
    admin_username: str = Depends(require_admin),
    q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    session: AsyncSession = Depends(get_session),
):
    per_page = 20
    stmt = select(User)
    search_terms = [term.lower() for term in (q or "").split() if term.strip()]
    if search_terms:
        about_field = func.lower(func.coalesce(User.about, ""))
        for term in search_terms:
            stmt = stmt.where(about_field.like(f"%{term}%"))
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(User.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    profiles = (await session.execute(stmt)).scalars().all()
    total_pages = max(1, (total + per_page - 1) // per_page)
    return templates.TemplateResponse(
        "profiles.html",
        {
            "request": request,
            "profiles": profiles,
            "q": q or "",
            "page": page,
            "total_pages": total_pages,
            "admin_username": admin_username,
        },
    )


@router.post("/admin/users/{user_id}/ban")
async def ban_user(
    user_id: int,
    admin_username: str = Depends(require_admin),
    settings: Settings = Depends(get_settings_dep),
    page: int = Query(default=1, ge=1),
    q: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default=None),
    order: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    tg_id = (await session.execute(select(User.tg_id).where(User.id == user_id))).scalar_one_or_none()
    await session.execute(update(User).where(User.id == user_id).values(is_banned=True))
    session.add(
        AdminAction(
            admin_username=admin_username,
            action="ban",
            target_type="user",
            target_id=user_id,
            payload_json=None,
        )
    )
    await session.commit()
    redirect_url = (
        f"/admin/users?page={page}&q={q or ''}&sort={sort or ''}&order={order or ''}"
    )
    if tg_id:
        asyncio.create_task(
            notify_user(
                settings.bot_token,
                tg_id,
                "Ваш акаунт заблоковано адміністратором. Доступ до бота закрито.",
            )
        )
    return RedirectResponse(url=redirect_url, status_code=303)


@router.post("/admin/users/{user_id}/unban")
async def unban_user(
    user_id: int,
    admin_username: str = Depends(require_admin),
    settings: Settings = Depends(get_settings_dep),
    page: int = Query(default=1, ge=1),
    q: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default=None),
    order: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    tg_id = (await session.execute(select(User.tg_id).where(User.id == user_id))).scalar_one_or_none()
    await session.execute(update(User).where(User.id == user_id).values(is_banned=False))
    session.add(
        AdminAction(
            admin_username=admin_username,
            action="unban",
            target_type="user",
            target_id=user_id,
            payload_json=None,
        )
    )
    await session.commit()
    redirect_url = (
        f"/admin/users?page={page}&q={q or ''}&sort={sort or ''}&order={order or ''}"
    )
    if tg_id:
        asyncio.create_task(
            notify_user(
                settings.bot_token,
                tg_id,
                "Ваш акаунт розблоковано. Доступ до бота відновлено.",
            )
        )
    return RedirectResponse(url=redirect_url, status_code=303)


@router.get("/admin/actions", response_class=HTMLResponse)
async def actions_log(
    request: Request,
    admin_username: str = Depends(require_admin),
    action: Optional[str] = Query(default=None),
    from_date: Optional[str] = Query(default=None),
    to_date: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    session: AsyncSession = Depends(get_session),
):
    per_page = 20
    stmt = select(AdminAction)
    if action:
        stmt = stmt.where(AdminAction.action == action)
    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date)
            stmt = stmt.where(AdminAction.created_at >= from_dt)
        except ValueError:
            pass
    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date)
            stmt = stmt.where(AdminAction.created_at <= to_dt)
        except ValueError:
            pass
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(AdminAction.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    actions = (await session.execute(stmt)).scalars().all()
    total_pages = max(1, (total + per_page - 1) // per_page)
    return templates.TemplateResponse(
        "actions.html",
        {
            "request": request,
            "actions": actions,
            "action": action or "",
            "from_date": from_date or "",
            "to_date": to_date or "",
            "page": page,
        "total_pages": total_pages,
        "admin_username": admin_username,
    },
)


@router.get("/admin/complaints", response_class=HTMLResponse)
async def complaints_list(
    request: Request,
    admin_username: str = Depends(require_admin),
    target_user_id: Optional[int] = Query(default=None),
    reporter_user_id: Optional[int] = Query(default=None),
    from_date: Optional[str] = Query(default=None),
    to_date: Optional[str] = Query(default=None),
    reason: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    session: AsyncSession = Depends(get_session),
):
    per_page = 20
    stmt = select(Complaint)
    if target_user_id:
        stmt = stmt.where(Complaint.target_user_id == target_user_id)
    if reporter_user_id:
        stmt = stmt.where(Complaint.reporter_user_id == reporter_user_id)
    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date)
            stmt = stmt.where(Complaint.created_at >= from_dt)
        except ValueError:
            pass
    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date)
            stmt = stmt.where(Complaint.created_at <= to_dt)
        except ValueError:
            pass
    if reason:
        stmt = stmt.where(Complaint.reason.ilike(f"%{reason}%"))

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Complaint.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    complaints = (await session.execute(stmt)).scalars().all()
    total_pages = max(1, (total + per_page - 1) // per_page)
    return templates.TemplateResponse(
        "complaints.html",
        {
            "request": request,
            "complaints": complaints,
            "target_user_id": target_user_id or "",
            "reporter_user_id": reporter_user_id or "",
            "from_date": from_date or "",
            "to_date": to_date or "",
            "reason": reason or "",
            "page": page,
            "total_pages": total_pages,
            "admin_username": admin_username,
        },
    )
