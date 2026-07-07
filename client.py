import requests
import uuid

# Отправляем данные на ваш сервер
requests.post("http://ВАШ_IP_СЕРВЕРА:8000/register", params={
    "device_id": str(uuid.getnode()), # Уникальный ID железа
    "name": "PC"
})
