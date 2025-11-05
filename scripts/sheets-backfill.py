import csv
from app.db import SessionLocal
from app.models import Lead

CSV_PATH = "data/leads.csv"   # положи сюда экспорт листа Leads (UTF-8, с заголовками)

def run():
    db = SessionLocal()
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            lead = Lead(
                form_name=row.get("FormName") or row.get("form_name"),
                name=row.get("Name") or row.get("name"),
                phone=row.get("Phone") or row.get("phone"),
                email=row.get("Email") or row.get("email"),
                page=row.get("Page") or row.get("page"),
                utm_source=row.get("UTM Source") or row.get("utm_source"),
                utm_medium=row.get("UTM Medium") or row.get("utm_medium"),
                utm_campaign=row.get("UTM Campaign") or row.get("utm_campaign"),
                utm_content=row.get("UTM Content") or row.get("utm_content"),
                utm_term=row.get("UTM Term") or row.get("utm_term"),
            )
            db.add(lead)
        db.commit()
    print("Backfill done.")

if __name__ == "__main__":
    run()
