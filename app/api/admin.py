from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Optional

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth import create_session_token, read_session_token, verify_credentials
from app.config import Settings, TEMPLATES_DIR
from app.db import session_scope
from app.models import AdminAction, Complaint, Feedback, Message, Photo, UaLocation, User
from services.location_repo import DISTRICT_CATEGORIES, HROMADA_CATEGORIES, SETTLEMENT_CATEGORIES

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
logger = logging.getLogger(__name__)

FEEDBACK_STATUSES = ("new", "in_progress", "done")
FEEDBACK_CATEGORIES = ("general", "issue", "idea", "other")


async def _get_region_code(session: AsyncSession, name: str | None) -> str | None:
    if not name:
        return None
    region_name = name.strip().lower()
    res = await session.execute(
        select(UaLocation.level1)
        .where(UaLocation.category == "O", func.lower(func.trim(UaLocation.name)) == region_name)
        .limit(1)
    )
    return res.scalar_one_or_none()


async def _get_district_code(session: AsyncSession, region_code: str | None, name: str | None) -> str | None:
    if not region_code or not name:
        return None
    district_name = name.strip().lower()
    res = await session.execute(
        select(UaLocation.level2)
        .where(
            UaLocation.level1 == region_code,
            UaLocation.category.in_(DISTRICT_CATEGORIES),
            func.lower(func.trim(UaLocation.name)) == district_name,
        )
        .limit(1)
    )
    return res.scalar_one_or_none()


async def _get_hromada_code(
    session: AsyncSession, region_code: str | None, district_code: str | None, name: str | None
) -> str | None:
    if not region_code or not district_code or not name:
        return None
    hromada_name = name.strip().lower()
    res = await session.execute(
        select(UaLocation.level3)
        .where(
            UaLocation.level1 == region_code,
            UaLocation.level2 == district_code,
            UaLocation.category.in_(HROMADA_CATEGORIES),
            func.lower(func.trim(UaLocation.name)) == hromada_name,
        )
        .limit(1)
    )
    return res.scalar_one_or_none()


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


def _guess_media_type(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext in {".png"}:
        return "image/png"
    if ext in {".webp"}:
        return "image/webp"
    if ext in {".gif"}:
        return "image/gif"
    return "image/jpeg"


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
    counts = {"users": 0, "messages": 0, "actions": 0, "complaints": 0, "feedback": 0}
    try:
        counts["users"] = (await session.execute(select(func.count(User.id)))).scalar_one()
        counts["messages"] = (await session.execute(select(func.count(Message.id)))).scalar_one()
        counts["actions"] = (await session.execute(select(func.count(AdminAction.id)))).scalar_one()
        counts["complaints"] = (await session.execute(select(func.count(Complaint.id)))).scalar_one()
        counts["feedback"] = (await session.execute(select(func.count(Feedback.id)))).scalar_one()
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
    region: Optional[str] = Query(default=None),
    district: Optional[str] = Query(default=None),
    settlement: Optional[str] = Query(default=None),
    hromada: Optional[str] = Query(default=None),
    search_scope: Optional[str] = Query(default=None),
    active_hours: Optional[str] = Query(default=None),
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
        "last_activity_at": (User.last_activity_at,),
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
    if region:
        stmt = stmt.where(func.lower(User.region) == region.strip().lower())
    if district:
        stmt = stmt.where(func.lower(User.district) == district.strip().lower())
    if hromada:
        stmt = stmt.where(func.lower(User.hromada) == hromada.strip().lower())
    if settlement:
        stmt = stmt.where(func.lower(User.settlement) == settlement.strip().lower())
    if search_scope in {"settlement", "hromada", "district", "region", "country"}:
        stmt = stmt.where(User.search_scope == search_scope)
    if active_hours:
        try:
            hours = max(1, int(active_hours))
            stmt = stmt.where(User.last_activity_at >= func.now() - func.make_interval(hours=hours))
        except Exception:
            pass
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
        "region": region or "",
        "district": district or "",
        "settlement": settlement or "",
        "hromada": hromada or "",
        "search_scope": search_scope or "",
        "active_hours": active_hours or "",
    },
)


@router.get("/admin/filters/regions")
async def filter_regions(
    admin_username: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    region_expr = func.trim(UaLocation.name)
    rows = (
        await session.execute(
            select(region_expr)
            .where(UaLocation.category == "O")
            .distinct()
            .order_by(region_expr)
        )
    ).scalars()
    return JSONResponse({"items": [r for r in rows if r]})


@router.get("/admin/filters/districts")
async def filter_districts(
    admin_username: str = Depends(require_admin),
    region: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    if not region:
        return JSONResponse({"items": []})
    region_code = await _get_region_code(session, region)
    if not region_code:
        return JSONResponse({"items": []})
    district_expr = func.trim(UaLocation.name)
    rows = (
        await session.execute(
            select(district_expr)
            .where(
                UaLocation.level1 == region_code,
                UaLocation.category.in_(DISTRICT_CATEGORIES),
            )
            .distinct()
            .order_by(district_expr)
        )
    ).scalars()
    return JSONResponse({"items": [r for r in rows if r]})


@router.get("/admin/filters/settlements")
async def filter_settlements(
    admin_username: str = Depends(require_admin),
    region: Optional[str] = Query(default=None),
    district: Optional[str] = Query(default=None),
    hromada: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    if not region or not district:
        return JSONResponse({"items": []})
    region_code = await _get_region_code(session, region)
    district_code = await _get_district_code(session, region_code, district)
    hromada_code = await _get_hromada_code(session, region_code, district_code, hromada) if hromada else None
    if not region_code or not district_code:
        return JSONResponse({"items": []})
    settlement_expr = func.trim(UaLocation.name)
    rows = (
        await session.execute(
            select(settlement_expr)
            .where(
                UaLocation.level1 == region_code,
                UaLocation.level2 == district_code,
                (UaLocation.level3 == hromada_code if hromada_code else True),
                UaLocation.category.in_(SETTLEMENT_CATEGORIES),
            )
            .distinct()
            .order_by(settlement_expr)
        )
    ).scalars()
    return JSONResponse({"items": [r for r in rows if r]})


@router.get("/admin/filters/hromadas")
async def filter_hromadas(
    admin_username: str = Depends(require_admin),
    region: Optional[str] = Query(default=None),
    district: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    if not region or not district:
        return JSONResponse({"items": []})
    region_code = await _get_region_code(session, region)
    district_code = await _get_district_code(session, region_code, district)
    if not region_code or not district_code:
        return JSONResponse({"items": []})
    hromada_expr = func.trim(UaLocation.name)
    rows = (
        await session.execute(
            select(hromada_expr)
            .where(
                UaLocation.level1 == region_code,
                UaLocation.level2 == district_code,
                UaLocation.category.in_(HROMADA_CATEGORIES),
                UaLocation.name.isnot(None),
                UaLocation.name != "",
            )
            .distinct()
            .order_by(hromada_expr)
        )
    ).scalars()
    return JSONResponse({"items": [r for r in rows if r]})


@router.get("/admin/profiles", response_class=HTMLResponse)
async def profiles_list(
    request: Request,
    admin_username: str = Depends(require_admin),
    q: Optional[str] = Query(default=None),
    region: Optional[str] = Query(default=None),
    district: Optional[str] = Query(default=None),
    settlement: Optional[str] = Query(default=None),
    search_scope: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    session: AsyncSession = Depends(get_session),
):
    per_page = 20
    base_stmt = select(User)
    search_terms = [term.lower() for term in (q or "").split() if term.strip()]
    if search_terms:
        about_field = func.lower(func.coalesce(User.about, ""))
        for term in search_terms:
            base_stmt = base_stmt.where(about_field.like(f"%{term}%"))
    if region:
        base_stmt = base_stmt.where(func.lower(User.region) == region.strip().lower())
    if district:
        base_stmt = base_stmt.where(func.lower(User.district) == district.strip().lower())
    if settlement:
        base_stmt = base_stmt.where(func.lower(User.settlement) == settlement.strip().lower())
    if search_scope in {"settlement", "hromada", "district", "region", "country"}:
        base_stmt = base_stmt.where(User.search_scope == search_scope)

    total = (await session.execute(select(func.count()).select_from(base_stmt.subquery()))).scalar_one()

    ranked_photos = (
        select(
            Photo.user_id.label("user_id"),
            Photo.id.label("photo_id"),
            Photo.file_id.label("file_id"),
            func.row_number()
            .over(partition_by=Photo.user_id, order_by=(Photo.is_main.desc(), Photo.id.asc()))
            .label("rn"),
        ).subquery()
    )

    stmt = (
        base_stmt.outerjoin(
            ranked_photos,
            and_(ranked_photos.c.user_id == User.id, ranked_photos.c.rn == 1),
        )
        .add_columns(ranked_photos.c.photo_id, ranked_photos.c.file_id)
        .order_by(User.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await session.execute(stmt)
    profiles = [
        {"user": row[0], "photo_id": row[1], "photo_file_id": row[2]}
        for row in result.all()
    ]
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
            "region": region or "",
            "district": district or "",
            "settlement": settlement or "",
            "search_scope": search_scope or "",
        },
    )


@router.get("/admin/photos/{photo_id}")
async def profile_photo(
    photo_id: int,
    admin_username: str = Depends(require_admin),
    settings: Settings = Depends(get_settings_dep),
    session: AsyncSession = Depends(get_session),
):
    photo = await session.get(Photo, photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Фото не знайдено")

    file_id = photo.file_id
    if file_id.startswith(("http://", "https://")):
        return RedirectResponse(url=file_id)

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        telegram_file = await bot.get_file(file_id)
        buffer = await bot.download_file(telegram_file.file_path)
        if buffer is None:
            raise HTTPException(status_code=500, detail="Не вдалося завантажити фото")
        buffer.seek(0)
        media_type = _guess_media_type(telegram_file.file_path)
        return StreamingResponse(buffer, media_type=media_type)
    except Exception:
        logger.exception("Failed to fetch photo id=%s", photo_id)
        raise HTTPException(status_code=500, detail="Не вдалося завантажити фото")
    finally:
        await bot.session.close()


@router.post("/admin/users/{user_id}/ban")
async def ban_user(
    user_id: int,
    admin_username: str = Depends(require_admin),
    settings: Settings = Depends(get_settings_dep),
    page: int = Query(default=1, ge=1),
    q: Optional[str] = Query(default=None),
    sort: Optional[str] = Query(default=None),
    order: Optional[str] = Query(default=None),
    region: Optional[str] = Query(default=None),
    district: Optional[str] = Query(default=None),
    settlement: Optional[str] = Query(default=None),
    search_scope: Optional[str] = Query(default=None),
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
        f"&region={region or ''}&district={district or ''}&settlement={settlement or ''}"
        f"&search_scope={search_scope or ''}"
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
    region: Optional[str] = Query(default=None),
    district: Optional[str] = Query(default=None),
    settlement: Optional[str] = Query(default=None),
    search_scope: Optional[str] = Query(default=None),
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
        f"&region={region or ''}&district={district or ''}&settlement={settlement or ''}"
        f"&search_scope={search_scope or ''}"
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


@router.get("/admin/feedback", response_class=HTMLResponse)
async def feedback_list(
    request: Request,
    admin_username: str = Depends(require_admin),
    user_id: Optional[int] = Query(default=None),
    tg_id: Optional[int] = Query(default=None),
    status: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    from_date: Optional[str] = Query(default=None),
    to_date: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    session: AsyncSession = Depends(get_session),
):
    per_page = 20
    stmt = select(Feedback)
    if user_id:
        stmt = stmt.where(Feedback.user_id == user_id)
    if tg_id:
        stmt = stmt.where(Feedback.tg_id == tg_id)
    if status and status in FEEDBACK_STATUSES:
        stmt = stmt.where(Feedback.status == status)
    if category and category in FEEDBACK_CATEGORIES:
        stmt = stmt.where(Feedback.category == category)
    if q:
        stmt = stmt.where(or_(Feedback.description.ilike(f"%{q}%"), Feedback.username.ilike(f"%{q}%")))
    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date)
            stmt = stmt.where(Feedback.created_at >= from_dt)
        except ValueError:
            pass
    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date)
            stmt = stmt.where(Feedback.created_at <= to_dt)
        except ValueError:
            pass

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Feedback.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    feedback_items = (await session.execute(stmt)).scalars().all()
    total_pages = max(1, (total + per_page - 1) // per_page)
    return templates.TemplateResponse(
        "feedback.html",
        {
            "request": request,
            "feedback_items": feedback_items,
            "user_id": user_id or "",
            "tg_id": tg_id or "",
            "status": status or "",
            "category": category or "",
            "q": q or "",
            "from_date": from_date or "",
            "to_date": to_date or "",
            "page": page,
            "total_pages": total_pages,
            "status_options": FEEDBACK_STATUSES,
            "category_options": FEEDBACK_CATEGORIES,
            "admin_username": admin_username,
        },
    )


@router.post("/admin/feedback/{feedback_id}/status")
async def feedback_update_status(
    feedback_id: int,
    status: str = Form(...),
    admin_username: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    if status not in FEEDBACK_STATUSES:
        raise HTTPException(status_code=400, detail="Unknown status")

    exists_stmt = select(func.count()).select_from(Feedback).where(Feedback.id == feedback_id)
    if (await session.execute(exists_stmt)).scalar_one() == 0:
        raise HTTPException(status_code=404, detail="Feedback not found")

    await session.execute(update(Feedback).where(Feedback.id == feedback_id).values(status=status))
    session.add(
        AdminAction(
            admin_username=admin_username,
            action="feedback_status",
            target_type="feedback",
            target_id=feedback_id,
            payload_json=status,
        )
    )
    await session.commit()
    return RedirectResponse(url="/admin/feedback", status_code=303)


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
