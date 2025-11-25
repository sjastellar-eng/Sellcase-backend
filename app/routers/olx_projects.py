# app/routers/olx_projects.py

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.services.auth import get_current_user
from app import models
from app.db import get_db
from app.models import OlxProject, OlxSnapshot
from app.schemas import OlxProjectCreate, OlxProjectOut, OlxSnapshotOut

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

@router.get("/{project_id}/snapshots", response_model=List[OlxSnapshotOut])
def list_snapshots(
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
        # либо проект чужой, либо его нет
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # 2) Отдаём снапшоты только этого проекта
    snapshots = (
        db.query(OlxSnapshot)
        .filter(OlxSnapshot.project_id == project_id)
        .order_by(OlxSnapshot.taken_at.desc())
        .limit(200)
        .all()
    )
    return snapshots
