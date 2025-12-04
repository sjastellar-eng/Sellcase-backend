# app/routers/olx_projects.py

from typing import List

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.routers.auth import get_current_user
from app import models
from app.db import get_db
from app.models import OlxProject, OlxSnapshot
from app.schemas import (
    OlxProjectCreate,
    OlxProjectOut,
    OlxSnapshotOut,
    OlxProjectUpdate,
    OlxProjectOverview,
    OlxAdOut,           # ← добавляем эту строку
)
from app.services.olx_parser import fetch_olx_data, fetch_olx_ads

router = APIRouter(prefix="/olx/projects", tags=["OLX Projects"])


@router.post("/", response_model=OlxProjectOut)
def create_project(
    payload: OlxProjectCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = OlxProject(
        name=payload.name,
        search_url=payload.search_url,
        notes=payload.notes,
        is_active=True,
        user_id=current_user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

@router.put("/{project_id}", response_model=OlxProjectOut)
def update_project(
    project_id: int,
    payload: OlxProjectUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # 1. Ищем проект текущего пользователя
    project = (
        db.query(OlxProject)
        .filter(
            OlxProject.id == project_id,
            OlxProject.user_id == current_user.id,
        )
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # 2. Обновляем только те поля, которые пришли в запросе
    if payload.name is not None:
        project.name = payload.name
    if payload.search_url is not None:
        project.search_url = payload.search_url
    if payload.notes is not None:
        project.notes = payload.notes
    if payload.is_active is not None:  # важно проверять именно 'is not None'
        project.is_active = payload.is_active

    # 3. Сохраняем изменения
    db.add(project)
    db.commit()
    db.refresh(project)

    return project

@router.get("/", response_model=List[OlxProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    projects = (
        db.query(OlxProject)
        .filter(OlxProject.user_id == current_user.id)
        .order_by(OlxProject.id.desc())
        .all()
    )
    return projects

@router.get("/overview", response_model=List[OlxProjectOverview])
def list_projects_overview(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # 1) Берём все проекты текущего пользователя
    projects = (
        db.query(OlxProject)
        .filter(OlxProject.user_id == current_user.id)
        .order_by(OlxProject.id.desc())
        .all()
    )

    results = []

    for project in projects:
        # 2) Ищем последний снапшот по дате
        last_snapshot = (
            db.query(OlxSnapshot)
            .filter(OlxSnapshot.project_id == project.id)
            .order_by(OlxSnapshot.taken_at.desc())
            .first()
        )

        # 3) Собираем словарь под нашу схему OlxProjectOverview
        last_snapshot_data = None
        if last_snapshot:
            last_snapshot_data = {
                "id": last_snapshot.id,
                "project_id": last_snapshot.project_id,
                "items_count": last_snapshot.items_count,
                "min_price": last_snapshot.min_price,
                "max_price": last_snapshot.max_price,
                "avg_price": last_snapshot.avg_price,
                "taken_at": last_snapshot.taken_at,
            }

        results.append(
            {
                "id": project.id,
                "name": project.name,
                "search_url": project.search_url,
                "notes": project.notes,
                "is_active": project.is_active,
                "last_snapshot": last_snapshot_data,
            }
        )

    return results

@router.post("/{project_id}/refresh")
async def refresh_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # 1) Проверяем, что проект принадлежит текущему пользователю
    project = (
        db.query(OlxProject)
        .filter(
            OlxProject.id == project_id,
            OlxProject.user_id == current_user.id,
        )
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # 2) Запрашиваем данные OLX
    stats = await fetch_olx_data(project.search_url)
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to parse OLX page",
        )

    # 3) Сохраняем снапшот в БД
    snapshot = OlxSnapshot(
        project_id=project.id,
        items_count=stats["items_count"],
        min_price=stats["min_price"],
        max_price=stats["max_price"],
        avg_price=stats["avg_price"],
    )

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    # 4) Возвращаем статус и id созданного снапшота
    return {"status": "ok", "snapshot_id": snapshot.id}

@router.post("/refresh_all")
async def refresh_all_projects(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Обновляет ВСЕ активные проекты текущего пользователя.
    Для каждого проекта создаётся новый снапшот.
    """

    # 1) Берём все активные проекты пользователя
    projects = (
        db.query(OlxProject)
        .filter(
            OlxProject.user_id == current_user.id,
            OlxProject.is_active == True,  # только активные
        )
        .all()
    )

    if not projects:
        return {
            "status": "ok",
            "updated": 0,
            "snapshots": [],
        }

    snapshots_info = []

    # 2) Для каждого проекта тянем данные OLX и создаём снапшот
    for project in projects:
        stats = await fetch_olx_data(project.search_url)
        if not stats:
            # если OLX вернул ошибку / редирект / капчу — пропускаем
            continue

        snapshot = OlxSnapshot(
            project_id=project.id,
            items_count=stats["items_count"],
            min_price=stats["min_price"],
            max_price=stats["max_price"],
            avg_price=stats["avg_price"],
        )
        db.add(snapshot)
        db.flush()  # чтобы получить snapshot.id без отдельного commit

        snapshots_info.append(
            {
                "project_id": project.id,
                "snapshot_id": snapshot.id,
            }
        )

    # 3) Один общий commit для всех снапшотов
    db.commit()

    return {
        "status": "ok",
        "updated": len(snapshots_info),
        "snapshots": snapshots_info,
    }

from sqlalchemy import inspect
from app.db import SessionLocal
from app.services.olx_parser import fetch_olx_ads
from pydantic import BaseModel


@router.get("/debug/tables")
def list_tables():
    inspector = inspect(SessionLocal().bind)
    return inspector.get_table_names()

class DebugParseRequest(BaseModel):
    url: str
    max_pages: int = 3

@router.post("/debug/parse")
async def debug_parse(body: DebugParseRequest):
    ads = await fetch_olx_ads(body.url, max_pages=body.max_pages)
    return ads

@router.get(
    "/{project_id}/snapshots",
    response_model=List[OlxSnapshotOut],
)
def list_project_snapshots(
    project_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Проверяем, что проект принадлежит текущему пользователю
    project = (
        db.query(models.OlxProject)
        .filter(
            models.OlxProject.id == project_id,
            models.OlxProject.user_id == current_user.id,  # если у тебя поле owner_id — поменяй здесь
        )
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    snapshots = (
        db.query(models.OlxSnapshot)
        .filter(models.OlxSnapshot.project_id == project_id)
        .order_by(models.OlxSnapshot.taken_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return snapshots

@router.get(
    "/{project_id}/ads",
    response_model=List[OlxAdOut],
)
async def list_project_ads(
    project_id: int,
    max_pages: int = 3,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # 1) Проверяем, что проект принадлежит текущему пользователю
    project = (
        db.query(OlxProject)
        .filter(
            OlxProject.id == project_id,
            OlxProject.user_id == current_user.id,
        )
        .first()
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # 2) Парсим объявления по ссылке проекта
    ads = await fetch_olx_ads(project.search_url, max_pages=max_pages)

    # 3) Просто отдаём список объявлений
    return ads

@router.get(
    "/{project_id}/ads.csv",
    response_class=StreamingResponse,
    summary="Download project ads as CSV",
)
async def download_project_ads_csv(
    project_id: int,
    max_pages: int = 3,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Глубоко парсит объявления OLX по проекту и отдаёт CSV-файл.
    """

    # 1) Проверяем, что проект принадлежит текущему пользователю
    project = (
        db.query(OlxProject)
        .filter(
            OlxProject.id == project_id,
            OlxProject.user_id == current_user.id,
        )
        .first()
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # 2) Грузим объявления через deep-парсер
    ads = await fetch_olx_ads(project.search_url, max_pages=max_pages)

    # 3) Формируем CSV в памяти
    fieldnames = [
        "external_id",
        "title",
        "url",
        "price",
        "currency",
        "seller_id",
        "seller_name",
        "location",
        "position",
        "page",
    ]

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()

    for ad in ads:
        row = {name: ad.get(name, "") for name in fieldnames}
        writer.writerow(row)

    buffer.seek(0)
    csv_bytes = buffer.getvalue().encode("utf-8-sig")  # для Excel и кириллицы

    # 4) Отдаём как файл
    filename = f"project_{project_id}_ads.csv"
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
