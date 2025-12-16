# app/routers/analytics.py

from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models import SearchQuery

router = APIRouter(prefix="/analytics", tags=["Analytics"])
