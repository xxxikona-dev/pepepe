import asyncio
import os
import uvicorn
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

app = FastAPI()
bot = Bot(token=TOKEN)
dp = Dispatcher()

# База данных подключенных ПК
connected_pcs = {}

# --- API ДЛЯ КЛИЕНТОВ ---
@app.post("/register")
async def register_pc(device_id: str, name: str):
    # Как только setup.exe запустит клиент, данные попадут сюда
    connected_pcs[device_id] = {"name": name, "status": "online"}
    print(f"[СЕРВЕР] Добавлено новое устройство: {name} (ID: {device_id})")
    return {"status": "success"}

# --- ТЕЛЕГРАМ БОТ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Пульт управления готов. Используйте /devices для выбора ПК.")

@dp.message(Command("devices"))
async def cmd_devices(message: types.Message):
    if not connected_pcs:
        await message.answer("Список устройств пуст. Установите программу на ПК.")
        return
    
    # Создаем клавиатуру со списком всех ПК
    keyboard = []
    for dev_id, info in connected_pcs.items():
        # В callback_data зашиваем ID устройства, чтобы бот понял, на какой ПК нажали
        button = InlineKeyboardButton(text=f"💻 {info['name']}", callback_data=f"manage_{dev_id}")
        keyboard.append([button])
        
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer("Выберите устройство для управления:", reply_markup=reply_markup)

# Обработка нажатия на конкретный ПК
@dp.callback_query(F.data.startswith("manage_"))
async def manage_device(callback: types.CallbackQuery):
    device_id = callback.data.split("_")[1]
    device_info = connected_pcs.get(device_id)
    
    if not device_info:
        await callback.answer("Устройство не найдено.", show_alert=True)
        return
        
    # Меню действий для выбранного ПК
    actions_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Сделать скриншот", callback_data=f"screen_{device_id}")],
        [InlineKeyboardButton(text="🛑 Выключить ПК", callback_data=f"shutdown_{device_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_list")]
    ])
    
    await callback.message.edit_text(
        text=f"Управление устройством: *{device_info['name']}*\nID: `{device_id}`\nСтатус: Online",
        parse_mode="Markdown",
        reply_markup=actions_keyboard
    )

@dp.callback_query(F.data == "back_to_list")
async def back_to_list(callback: types.CallbackQuery):
    # Возврат к списку устройств
    await callback.message.delete()
    await cmd_devices(callback.message)

async def run_bot():
    await dp.start_polling(bot)

async def main():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await asyncio.gather(run_bot(), server.serve())

if __name__ == "__main__":
    asyncio.run(main())
