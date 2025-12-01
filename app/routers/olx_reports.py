from fastapi import APIRouter, Depends, HTTPException, Response, Query
from sqlalchemy.orm import Session
from typing import List
from app.db import get_db
from app import models
from app.schemas import (
    OlxReportCreate, OlxReportOut, OlxReportWithItemsOut, OlxReportListOut
)
from app.services.olx_parser import fetch_olx_ads
from app.services.csv_utils import rows_to_csv

router = APIRouter(prefix="/olx/reports", tags=["OLX reports"])

@router.post("", response_model=OlxReportOut)
async def create_report(payload: OlxReportCreate, db: Session = Depends(get_db)):
    # создаём запись-черновик (можно сразу planned/running, но делаем просто)
    rpt = models.OlxReport(
        source="olx",
        query_url=str(payload.url),
        status="running",
        note=payload.note or None,
    )
    db.add(rpt)
    db.commit()
    db.refresh(rpt)

    try:
        # парсим
        ads = await fetch_olx_ads(str(payload.url), max_pages=payload.max_pages)

        # агрегаты
        prices = [a.get("price") for a in ads if a.get("price") is not None]
        items_count = len(ads)
        avg_price = round(sum(prices) / len(prices), 2) if prices else None
        min_price = min(prices) if prices else None
        max_price = max(prices) if prices else None

        # сохраняем строки
        for a in ads:
            db.add(models.OlxReportItem(
                report_id=rpt.id,
                external_id=a.get("external_id"),
                title=a.get("title"),
                url=a.get("url"),
                price=a.get("price"),
                currency=a.get("currency") or "UAH",
                seller_id=a.get("seller_id"),
                seller_name=a.get("seller_name"),
                location=a.get("location"),
                position=a.get("position"),
                page=a.get("page"),
            ))

        # финализируем отчёт
        rpt.status = "done"
        rpt.items_count = items_count
        rpt.avg_price = avg_price
        rpt.min_price = min_price
        rpt.max_price = max_price

        db.commit()
        db.refresh(rpt)

    except Exception as e:
        db.rollback()
        rpt.status = "error"
        rpt.error = str(e)
        db.add(rpt)
        db.commit()
        db.refresh(rpt)
        raise HTTPException(status_code=500, detail=f"Report failed: {e}")

    return rpt


@router.get("", response_model=OlxReportListOut)
def list_reports(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    q: str | None = Query(None),
):
    qset = db.query(models.OlxReport).order_by(models.OlxReport.id.desc())
    if status:
        qset = qset.filter(models.OlxReport.status == status)
    if q:
        like = f"%{q}%"
        qset = qset.filter(models.OlxReport.query_url.ilike(like))
    total = qset.count()
    rows = qset.limit(limit).offset(offset).all()
    return OlxReportListOut(total=total, items=rows)


@router.get("/{report_id}", response_model=OlxReportWithItemsOut)
def get_report(report_id: int, db: Session = Depends(get_db)):
    rpt = db.query(models.OlxReport).filter(models.OlxReport.id == report_id).first()
    if not rpt:
        raise HTTPException(status_code=404, detail="Report not found")
    # при необходимости можно добавить пагинацию по items
    return rpt


@router.get("/{report_id}/download")
def download_report_csv(report_id: int, db: Session = Depends(get_db)):
    rpt = db.query(models.OlxReport).filter(models.OlxReport.id == report_id).first()
    if not rpt:
        raise HTTPException(status_code=404, detail="Report not found")

    items = db.query(models.OlxReportItem).filter(models.OlxReportItem.report_id == report_id).all()

    rows = []
    for it in items:
        rows.append({
            "external_id": it.external_id,
            "title": it.title,
            "url": it.url,
            "price": it.price,
            "currency": it.currency,
            "seller_id": it.seller_id,
            "seller_name": it.seller_name,
            "location": it.location,
            "position": it.position,
            "page": it.page,
        })

    csv_bytes = rows_to_csv(rows)
    filename = f"sellcase_report_{report_id}.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
