import requests
import uuid
import platform
import time

SERVER_URL = "http://ВАШ_IP_СЕРВЕРА:8000"

def register():
    try:
        data = {
            "device_id": str(uuid.getnode()),
            "name": platform.node()
        }
        requests.post(f"{SERVER_URL}/register", params=data)
    except Exception as e:
        print(f"Ошибка подключения: {e}")

if __name__ == "__main__":
    register()
    # Здесь можно добавить цикл для опроса команд
    while True:
        time.sleep(60) # Стучаться на сервер раз в минуту
