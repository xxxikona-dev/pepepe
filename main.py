# main.py - Серверная часть (Linux/Windows)
import paho.mqtt.client as mqtt
import json
import sqlite3
import time
import os
from datetime import datetime
import base64
import threading
import logging
import sys
from typing import Dict, List, Optional, Any

# ============ НАСТРОЙКА ЛОГИРОВАНИЯ ============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============ КОНФИГУРАЦИЯ HIVEMQ ============
# ЗАМЕНИТЕ НА ВАШИ ДАННЫЕ!
MQTT_CONFIG = {
    "host": "04f19c56c4b441a68aa08dafd39d7713.s1.eu.hivemq.cloud",
    "port": 8883,  # TLS порт
    "username": "admin",  # ЗАМЕНИТЕ на ваш логин
    "password": "your_password_here"  # ЗАМЕНИТЕ на ваш пароль
}

# ============ БАЗА ДАННЫХ ============
DB_PATH = os.path.join(os.path.dirname(__file__), "devices.db")

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Таблица устройств
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
    
    # Таблица команд
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
    
    # Таблица скриншотов
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

def update_device(device_id: str, name: str, os_info: str = None, ip: str = None):
    """Обновление информации об устройстве"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    current_time = int(time.time())
    
    cursor.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,))
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute("""
            UPDATE devices 
            SET name = ?, last_seen = ?, os_info = ?, ip_address = ?, is_online = 1
            WHERE device_id = ?
        """, (name, current_time, os_info, ip, device_id))
    else:
        cursor.execute("""
            INSERT INTO devices (device_id, name, last_seen, first_seen, os_info, ip_address, is_online)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (device_id, name, current_time, current_time, os_info, ip))
    
    conn.commit()
    conn.close()
    logger.info(f"✅ Device updated: {name}")

def set_device_offline(device_id: str):
    """Отметить устройство как оффлайн"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE devices SET is_online = 0 WHERE device_id = ?", (device_id,))
    conn.commit()
    conn.close()

def get_all_devices() -> List[tuple]:
    """Получить все устройства"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT device_id, name, last_seen, is_online, os_info 
        FROM devices 
        ORDER BY last_seen DESC
    """)
    devices = cursor.fetchall()
    conn.close()
    return devices

def get_device(device_id: str) -> Optional[tuple]:
    """Получить информацию об устройстве"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT device_id, name, last_seen, is_online, os_info 
        FROM devices 
        WHERE device_id = ?
    """, (device_id,))
    device = cursor.fetchone()
    conn.close()
    return device

def delete_device(device_id: str):
    """Удалить устройство"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM devices WHERE device_id = ?", (device_id,))
    cursor.execute("DELETE FROM command_history WHERE device_id = ?", (device_id,))
    cursor.execute("DELETE FROM screenshots WHERE device_id = ?", (device_id,))
    conn.commit()
    conn.close()
    logger.info(f"🗑 Device deleted: {device_id}")

def save_command_history(device_id: str, command: str, result: str = None, status: str = "pending"):
    """Сохранить историю команд"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO command_history (device_id, command, result, timestamp, status)
        VALUES (?, ?, ?, ?, ?)
    """, (device_id, command, result, int(time.time()), status))
    conn.commit()
    conn.close()

def save_screenshot(device_id: str, image_data: str) -> str:
    """Сохранить скриншот в файл и БД"""
    try:
        # Декодируем base64
        image_bytes = base64.b64decode(image_data)
        
        # Создаем папку если нет
        os.makedirs("screenshots", exist_ok=True)
        
        # Создаем имя файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshots/screenshot_{device_id[:8]}_{timestamp}.jpg"
        
        # Сохраняем файл
        with open(filename, 'wb') as f:
            f.write(image_bytes)
        
        # Сохраняем в БД
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO screenshots (device_id, image_data, timestamp, filename)
            VALUES (?, ?, ?, ?)
        """, (device_id, image_data, int(time.time()), filename))
        conn.commit()
        conn.close()
        
        logger.info(f"📸 Screenshot saved: {filename}")
        return filename
        
    except Exception as e:
        logger.error(f"Error saving screenshot: {e}")
        return None

# ============ MQTT СЕРВЕР ============
class MQTTDeviceServer:
    def __init__(self):
        self.client = mqtt.Client(
            client_id="server_admin",
            protocol=mqtt.MQTTv311
        )
        
        # Настройка SSL
        self.client.tls_set()
        
        # Аутентификация
        self.client.username_pw_set(
            MQTT_CONFIG["username"], 
            MQTT_CONFIG["password"]
        )
        
        # Callbacks
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        
        # Состояние
        self.online_devices = set()
        self.pending_commands = {}
        self.running = True
        
        # Топики
        self.base_topic = "devices"
        
        logger.info("🚀 MQTT Server initialized")
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("✅ Connected to HiveMQ Cloud!")
            
            # Подписываемся на все топики
            topics = [
                f"{self.base_topic}/+/status",
                f"{self.base_topic}/+/response",
                f"{self.base_topic}/+/screenshot",
                f"{self.base_topic}/+/ping",
                f"{self.base_topic}/+/info"
            ]
            
            for topic in topics:
                self.client.subscribe(topic, qos=1)
                logger.info(f"📡 Subscribed to: {topic}")
            
            # Запускаем проверку оффлайн устройств
            threading.Thread(target=self.check_offline_devices, daemon=True).start()
            
        else:
            logger.error(f"❌ Connection failed with code: {rc}")
            logger.info("Проверьте логин и пароль в MQTT_CONFIG")
    
    def on_disconnect(self, client, userdata, rc):
        logger.warning("⚠️ Disconnected from HiveMQ Cloud")
        if self.running:
            logger.info("🔄 Reconnecting in 5 seconds...")
            time.sleep(5)
            self.connect()
    
    def on_message(self, client, userdata, msg):
        """Обработка входящих сообщений"""
        try:
            topic = msg.topic
            parts = topic.split('/')
            
            if len(parts) < 3:
                return
            
            device_id = parts[1]
            msg_type = parts[2]
            payload = msg.payload.decode('utf-8')
            
            # Обработка по типу сообщения
            handlers = {
                'status': self.handle_status,
                'ping': self.handle_ping,
                'response': self.handle_response,
                'screenshot': self.handle_screenshot,
                'info': self.handle_info
            }
            
            if msg_type in handlers:
                handlers[msg_type](device_id, payload)
            else:
                logger.debug(f"Unknown message type: {msg_type}")
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def handle_status(self, device_id: str, payload: str):
        """Обработка статуса"""
        try:
            data = json.loads(payload)
            name = data.get('name', 'Unknown')
            os_info = data.get('os', 'Unknown')
            
            update_device(device_id, name, os_info)
            self.online_devices.add(device_id)
            
            logger.info(f"🟢 {name} ({device_id[:8]}) подключен")
            
            # Отправляем ожидающие команды
            if device_id in self.pending_commands:
                for cmd in self.pending_commands[device_id]:
                    self.send_command(device_id, cmd)
                self.pending_commands[device_id] = []
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in status from {device_id}")
    
    def handle_ping(self, device_id: str, payload: str):
        """Обработка пинга"""
        try:
            data = json.loads(payload)
            name = data.get('name', 'Unknown')
            
            update_device(device_id, name)
            self.online_devices.add(device_id)
            
            logger.debug(f"📡 Ping from {device_id[:8]}")
            
        except Exception as e:
            logger.error(f"Ping error: {e}")
    
    def handle_response(self, device_id: str, payload: str):
        """Обработка ответа на команду"""
        try:
            data = json.loads(payload)
            command = data.get('command', '')
            result = data.get('result', '')
            
            # Форматируем результат для отображения
            result_str = json.dumps(result, indent=2, ensure_ascii=False)
            
            # Сохраняем в историю
            save_command_history(device_id, command, result_str, "completed")
            
            # Отображаем результат
            self.display_result(device_id, command, result)
            
        except Exception as e:
            logger.error(f"Response error: {e}")
    
    def handle_screenshot(self, device_id: str, payload: str):
        """Обработка скриншота"""
        try:
            # Сохраняем скриншот
            filename = save_screenshot(device_id, payload)
            
            if filename:
                # Получаем имя устройства
                device = get_device(device_id)
                name = device[1] if device else device_id[:8]
                
                print("\n" + "="*60)
                print(f"📸 СКРИНШОТ ПОЛУЧЕН")
                print(f"🖥 Устройство: {name}")
                print(f"📁 Файл: {filename}")
                print("="*60 + "\n")
            
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
    
    def handle_info(self, device_id: str, payload: str):
        """Обработка системной информации"""
        try:
            data = json.loads(payload)
            name = data.get('name', 'Unknown')
            os_info = data.get('os', 'Unknown')
            
            update_device(device_id, name, os_info)
            
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
        """Отправка команды устройству"""
        try:
            topic = f"{self.base_topic}/{device_id}/command"
            
            # Если устройство оффлайн - сохраняем команду
            if device_id not in self.online_devices:
                if device_id not in self.pending_commands:
                    self.pending_commands[device_id] = []
                self.pending_commands[device_id].append(command)
                logger.info(f"💾 Command '{command}' saved for offline device {device_id[:8]}")
                save_command_history(device_id, command, None, "queued")
                return True
            
            payload = json.dumps({
                'command': command,
                'timestamp': int(time.time())
            })
            
            result = self.client.publish(topic, payload, qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                save_command_history(device_id, command, None, "sent")
                logger.info(f"🚀 Command '{command}' sent to {device_id[:8]}")
                return True
            else:
                logger.error(f"❌ Failed to send command to {device_id[:8]}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return False
    
    def display_result(self, device_id: str, command: str, result: Any):
        """Отображение результата"""
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
        """Проверка оффлайн устройств"""
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
                        
            except Exception as e:
                logger.error(f"Check offline error: {e}")
    
    def connect(self) -> bool:
        """Подключение к брокеру"""
        try:
            self.client.connect(
                MQTT_CONFIG["host"],
                MQTT_CONFIG["port"],
                60
            )
            self.client.loop_start()
            return True
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            return False
    
    def disconnect(self):
        """Отключение от брокера"""
        self.running = False
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("👋 Disconnected")
    
    def list_devices(self):
        """Список устройств"""
        devices = get_all_devices()
        
        if not devices:
            print("\n❌ Нет подключенных устройств")
            return
        
        print("\n" + "="*70)
        print(f"📋 СПИСОК УСТРОЙСТВ (Всего: {len(devices)})")
        print("="*70)
        
        for device_id, name, last_seen, is_online, os_info in devices:
            status = "🟢 Онлайн" if is_online else "🔴 Оффлайн"
            last = datetime.fromtimestamp(last_seen).strftime("%H:%M:%S %d.%m.%Y")
            os_short = os_info[:30] if os_info else "Неизвестно"
            print(f"{status} | {name:15} | ID: {device_id[:8]}... | {last} | {os_short}")
        
        print("="*70)
    
    def show_device_info(self, device_id: str):
        """Информация об устройстве"""
        device = get_device(device_id)
        if not device:
            print(f"❌ Устройство {device_id[:8]}... не найдено")
            return
        
        print("\n" + "="*60)
        print(f"💻 ИНФОРМАЦИЯ О УСТРОЙСТВЕ")
        print("="*60)
        print(f"ID: {device[0]}")
        print(f"Имя: {device[1]}")
        print(f"ОС: {device[4] if device[4] else 'Неизвестно'}")
        print(f"Статус: {'🟢 Онлайн' if device[3] else '🔴 Оффлайн'}")
        print(f"Последнее: {datetime.fromtimestamp(device[2]).strftime('%H:%M:%S %d.%m.%Y')}")
        print("="*60)
    
    def show_history(self, device_id: str, limit: int = 10):
        """Показать историю команд устройства"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT command, result, timestamp, status 
            FROM command_history 
            WHERE device_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (device_id, limit))
        history = cursor.fetchall()
        conn.close()
        
        if not history:
            print(f"❌ Нет истории для устройства {device_id[:8]}...")
            return
        
        print("\n" + "="*60)
        print(f"📜 ИСТОРИЯ КОМАНД")
        print("="*60)
        
        for command, result, timestamp, status in history:
            dt = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
            status_emoji = "✅" if status == "completed" else "⏳" if status == "sent" else "💾"
            print(f"{dt} {status_emoji} {command}")
            if result and len(result) < 200:
                print(f"   Результат: {result[:100]}")
        print("="*60)

# ============ КОНСОЛЬНЫЙ ИНТЕРФЕЙС ============
class ConsoleUI:
    def __init__(self, server: MQTTDeviceServer):
        self.server = server
        self.commands = {
            'list': self.cmd_list,
            'info': self.cmd_info,
            'cmd': self.cmd_send,
            'screenshot': self.cmd_screenshot,
            'sysinfo': self.cmd_sysinfo,
            'history': self.cmd_history,
            'delete': self.cmd_delete,
            'clean': self.cmd_clean,
            'help': self.cmd_help,
            'exit': self.cmd_exit
        }
    
    def show_help(self):
        """Показать помощь"""
        print("\n" + "="*60)
        print("🤖 MQTT DEVICE SERVER v2.0")
        print("="*60)
        print("Доступные команды:")
        print("  list                 - показать все устройства")
        print("  info <device_id>     - информация об устройстве")
        print("  history <device_id>  - история команд")
        print("  cmd <id> <command>   - отправить команду")
        print("  screenshot <id>      - сделать скриншот")
        print("  sysinfo <id>         - получить системную инфо")
        print("  delete <id>          - удалить устройство")
        print("  clean                - удалить все оффлайн устройства")
        print("  help                 - показать это сообщение")
        print("  exit                 - выйти")
        print("="*60 + "\n")
    
    def cmd_list(self, args):
        self.server.list_devices()
    
    def cmd_info(self, args):
        if not args:
            print("❌ Использование: info <device_id>")
            return
        self.server.show_device_info(args[0])
    
    def cmd_history(self, args):
        if not args:
            print("❌ Использование: history <device_id>")
            return
        limit = int(args[1]) if len(args) > 1 else 10
        self.server.show_history(args[0], limit)
    
    def cmd_send(self, args):
        if len(args) < 2:
            print("❌ Использование: cmd <device_id> <command>")
            return
        device_id = args[0]
        command = ' '.join(args[1:])
        self.server.send_command(device_id, command)
    
    def cmd_screenshot(self, args):
        if not args:
            print("❌ Использование: screenshot <device_id>")
            return
        self.server.send_command(args[0], "screenshot")
        print(f"📸 Команда screenshot отправлена {args[0][:8]}...")
    
    def cmd_sysinfo(self, args):
        if not args:
            print("❌ Использование: sysinfo <device_id>")
            return
        self.server.send_command(args[0], "sysinfo")
        print(f"💻 Команда sysinfo отправлена {args[0][:8]}...")
    
    def cmd_delete(self, args):
        if not args:
            print("❌ Использование: delete <device_id>")
            return
        delete_device(args[0])
        self.server.online_devices.discard(args[0])
        print(f"✅ Устройство {args[0][:8]}... удалено")
    
    def cmd_clean(self, args):
        devices = get_all_devices()
        deleted = 0
        for device_id, _, _, is_online, _ in devices:
            if not is_online:
                delete_device(device_id)
                self.server.online_devices.discard(device_id)
                deleted += 1
        print(f"✅ Удалено {deleted} оффлайн устройств")
    
    def cmd_help(self, args):
        self.show_help()
    
    def cmd_exit(self, args):
        print("👋 Выход...")
        return False
    
    def run(self):
        """Запуск интерфейса"""
        self.show_help()
        
        while True:
            try:
                cmd_input = input("> ").strip()
                
                if not cmd_input:
                    continue
                
                parts = cmd_input.split()
                cmd_name = parts[0].lower()
                args = parts[1:] if len(parts) > 1 else []
                
                if cmd_name in self.commands:
                    result = self.commands[cmd_name](args)
                    if result is False:
                        break
                else:
                    print(f"❌ Неизвестная команда: {cmd_name}. Введите 'help'")
                    
            except KeyboardInterrupt:
                print("\n👋 Выход...")
                break
            except Exception as e:
                print(f"❌ Ошибка: {e}")

# ============ ЗАПУСК ============
def main():
    print("="*60)
    print("🤖 MQTT DEVICE SERVER v2.0")
    print("📡 Подключение к HiveMQ Cloud...")
    print("="*60)
    
    # Инициализация БД
    init_db()
    
    # Создаем сервер
    server = MQTTDeviceServer()
    
    # Подключаемся
    if not server.connect():
        print("\n❌ Не удалось подключиться к HiveMQ Cloud")
        print("Проверьте настройки в MQTT_CONFIG:")
        print(f"  Host: {MQTT_CONFIG['host']}")
        print(f"  Port: {MQTT_CONFIG['port']}")
        print(f"  Username: {MQTT_CONFIG['username']}")
        print("  Password: ********")
        return
    
    # Запускаем интерфейс
    ui = ConsoleUI(server)
    ui.run()
    
    # Отключаемся
    server.disconnect()
    print("👋 Сервер остановлен")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Программа остановлена")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
