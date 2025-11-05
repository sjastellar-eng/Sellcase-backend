from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db import get_db

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    q = text("""
        select
          sum(case when created_at >= now()::date then 1 else 0 end) as d1,
          sum(case when created_at >= now()::date - interval '7 day' then 1 else 0 end) as d7,
          sum(case when created_at >= now()::date - interval '30 day' then 1 else 0 end) as d30
        from leads
    """)
    row = db.execute(q).mappings().one()
    return {"today": int(row["d1"]), "d7": int(row["d7"]), "d30": int(row["d30"])}

@router.get("/daily")
def daily(db: Session = Depends(get_db), days: int = 30):
    q = text(f"""
        select to_char(date_trunc('day', created_at), 'YYYY-MM-DD') as d, count(*) as c
        from leads
        where created_at >= now()::date - interval '{days} day'
        group by 1 order by 1
    """)
    return list(db.execute(q).mappings().all())
