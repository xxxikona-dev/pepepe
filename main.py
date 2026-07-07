import asyncio
import os
import uvicorn
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

# Загрузка настроек
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Инициализация
app = FastAPI()
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Временная база данных (в реальном проекте используйте SQL)
connected_pcs = {}

# --- API Эндпоинт для клиентов ---
@app.post("/register")
async def register_pc(device_id: str, name: str):
    connected_pcs[device_id] = {"name": name, "status": "online"}
    print(f"Зарегистрирован ПК: {name} ({device_id})")
    return {"status": "success"}

# --- Telegram Бот ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Система управления ПК активна.\n/list — список устройств")

@dp.message(Command("list"))
async def cmd_list(message: types.Message):
    if not connected_pcs:
        await message.answer("Нет подключенных устройств.")
        return
    text = "Подключенные устройства:\n"
    for dev_id, info in connected_pcs.items():
        text += f"• {info['name']}\n"
    await message.answer(text)

async def run_bot():
    await dp.start_polling(bot)

async def main():
    # Запуск бота и сервера в одном цикле
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await asyncio.gather(run_bot(), server.serve())

if __name__ == "__main__":
    asyncio.run(main())
