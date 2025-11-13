import os
import json
from urllib import request

from app.models import Lead

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_lead_to_telegram(lead: Lead) -> None:
    """
    Отправляет информацию о лиде в Telegram.
    Не бросает исключения наружу, только пишет в логи.
    """
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram env vars are not set, skipping notification")
        return

    text_lines = [
        "🆕 Новый лид SellCase",
        "",
        f"👤 Имя: {lead.name or '-'}",
        f"📱 Телефон: {lead.phone or '-'}",
        f"✉️ Email: {lead.email or '-'}",
        "",
        f"📄 Страница: {lead.page or '-'}",
        f"🧾 Форма: {lead.form_name or '-'}",
        "",
        f"UTM source: {lead.utm_source or '-'}",
        f"UTM medium: {lead.utm_medium or '-'}",
        f"UTM campaign: {lead.utm_campaign or '-'}",
        f"UTM content: {lead.utm_content or '-'}",
        f"UTM term: {lead.utm_term or '-'}",
    ]

    text = "\n".join(text_lines)

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}

    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            print("Telegram response:", resp.status, body)
    except Exception as e:
        # Тут ошибка не ломает API, только пишем в логи
        print("Error sending Telegram notification:", repr(e))
