import requests
import time

BASE_URL = "http://127.0.0.1:8000"  # сервер должен быть запущен

def wait_for_server():
    for i in range(20):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=1)
            if r.status_code == 200:
                print("✅ Сервер отвечает:", r.json())
                return True
        except Exception:
            pass
        time.sleep(0.5)
    print("❌ Сервер не отвечает, возможно не запущен.")
    return False


def test_watchlist():
    print("\n📦 Добавляем товар в watchlist:")
    data = {"url": "https://example.com/product/123", "note": "Хочу отследить цену"}
    r = requests.post(f"{BASE_URL}/watchlist/", json=data)
    print("→", r.status_code, r.text)

    print("\n📋 Получаем список watchlist:")
    r = requests.get(f"{BASE_URL}/watchlist/")
    print("→", r.status_code, r.text)


def test_leads():
    print("\n👤 Отправляем lead-заявку:")
    data = {
        "name": "Тестовый пользователь",
        "email": "test@example.com",
        "source": "Telegram",
        "message": "Хочу попробовать сервис!"
    }
    r = requests.post(f"{BASE_URL}/leads/", json=data)
    print("→", r.status_code, r.text)


if __name__ == "__main__":
    if wait_for_server():
        test_watchlist()
        test_leads()