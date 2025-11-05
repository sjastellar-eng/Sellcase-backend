import asyncio
from sqlalchemy import text
from app.db import SessionLocal
from app.services.notify import send_message

async def main():
    db = SessionLocal()
    row = db.execute(text("""
        select
          sum(case when created_at >= now()::date then 1 else 0 end) as d1,
          sum(case when created_at >= now()::date - interval '7 day' then 1 else 0 end) as d7,
          sum(case when created_at >= now()::date - interval '30 day' then 1 else 0 end) as d30
        from leads
    """)).mappings().one()

    top_src = db.execute(text("""
        select coalesce(utm_source,'-') as k, count(*) c
        from leads where created_at >= now()::date - interval '30 day'
        group by 1 order by 2 desc nulls last limit 1
    """)).mappings().first()

    top_form = db.execute(text("""
        select coalesce(form_name,'-') as k, count(*) c
        from leads where created_at >= now()::date - interval '30 day'
        group by 1 order by 2 desc nulls last limit 1
    """)).mappings().first()

    msg = "\n".join([
        "📊 <b>Sellcase Daily Digest</b>",
        "",
        f"🟢 Лиды за сегодня: <b>{row['d1'] or 0}</b>",
        f"🔵 За 7 дней: <b>{row['d7'] or 0}</b>",
        f"🔴 За 30 дней: <b>{row['d30'] or 0}</b>",
        "",
        f"🌍 Топ источник: <b>{(top_src and top_src['k']) or '-'}</b>",
        f"🗂 Топ форма: <b>{(top_form and top_form['k']) or '-'}</b>",
    ])
    await send_message(msg)

if __name__ == "__main__":
    asyncio.run(main())
