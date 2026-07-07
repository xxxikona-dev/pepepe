import os
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import asyncio
from dotenv import load_dotenv

# Загрузка переменных из .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Инициализация
app = FastAPI()
bot = Bot(token=TOKEN)
dp = Dispatcher()

# База данных в памяти (для примера)
connected_pcs = {}

# --- API ДЛЯ КЛИЕНТОВ (ПК) ---
@app.post("/register")
async def register_pc(device_id: str, name: str):
    connected_pcs[device_id] = {"name": name, "status": "online"}
    return {"status": "registered"}

# --- TELEGRAM БОТ ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Бот запущен. Используйте /list для просмотра ПК.")

@dp.message(Command("list"))
async def list_pcs(message: types.Message):
    if not connected_pcs:
        await message.answer("Нет активных компьютеров.")
        return
    
    text = "Список устройств:\n"
    for dev_id, info in connected_pcs.items():
        text += f"- {info['name']} (ID: {dev_id})\n"
    await message.answer(text)

# --- ЗАПУСК ---
async def run_bot():
    await dp.start_polling(bot)

# Команда для запуска сервера (через uvicorn main:app)
if __name__ == "__main__":
    # Запуск бота и сервера в одном процессе
    loop = asyncio.get_event_loop()
    loop.create_task(run_bot())
