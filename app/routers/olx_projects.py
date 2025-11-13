# app/routers/olx_projects.py
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import OlxProject, OlxSnapshot
from app.schemas import OlxProjectCreate, OlxProjectOut, OlxSnapshotOut

router = APIRouter(prefix="/olx/projects", tags=["OLX Projects"])


@router.post("/", response_model=OlxProjectOut)
def create_project(payload: OlxProjectCreate, db: Session = Depends(get_db)):
    project = OlxProject(
        name=payload.name,
        search_url=payload.search_url,
        notes=payload.notes,
        is_active=True,
        user_id=None,  # позже сюда подставим id юзера из токена
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/", response_model=List[OlxProjectOut])
def list_projects(db: Session = Depends(get_db)):
    projects = (
        db.query(OlxProject)
        .order_by(OlxProject.id.desc())
        .all()
    )
    return projects


@router.get("/{project_id}/snapshots", response_model=List[OlxSnapshotOut])
def list_snapshots(project_id: int, db: Session = Depends(get_db)):
    snapshots = (
        db.query(OlxSnapshot)
        .filter(OlxSnapshot.project_id == project_id)
        .order_by(OlxSnapshot.taken_at.desc())
        .limit(200)
        .all()
    )
    return snapshots
