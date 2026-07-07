import os
import sys
import uuid
import platform
import requests
import time

# Укажите IP вашего сервера (хостинга)
SERVER_URL = "http://ВАШ_IP_СЕРВЕРА:8000"

def register_device():
    try:
        data = {
            "device_id": str(uuid.getnode()), # Уникальный ID материнской платы/сетевой карты
            "name": platform.node()           # Имя компьютера в сети Windows
        }
        # Отправляем запрос на сервер
        requests.post(f"{SERVER_URL}/register", params=data, timeout=5)
    except Exception:
        pass # Игнорируем ошибки, если нет интернета, чтобы программа не вылетала

if __name__ == "__main__":
    # Сразу регистрируемся при запуске
    register_device()
    
    # Бесконечный цикл для фоновой работы (опрос сервера)
    while True:
        # Здесь в будущем будет код получения команд от бота
        time.sleep(10)
