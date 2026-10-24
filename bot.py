import os
import sqlite3
from aiogram import Bot, Dispatcher, executor, types
from cryptography.fernet import Fernet

# --- НАСТРОЙКИ ---
# Получите токен у @BotFather в Telegram
TOKEN = "8900278508:AAGNu2mkUGLahK4v4mk1Jc7ws_nGUEH_zKg"

# Укажите ваш Telegram ID (узнать можно у @userinfobot), чтобы доступ был только у вас
MY_TELEGRAM_ID = 8640253231

# Ключ шифрования (генерируется один раз и сохраняется в файл secret.key)
KEY_FILE = "secret.key"

def load_or_create_key():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
        return key

ENCRYPT_KEY = load_or_create_key()
cipher = Fernet(ENCRYPT_KEY)

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("passwords.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS passwords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service TEXT,
            login TEXT,
            password TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- ПРОВЕРКА ДОСТУПА ---
def check_access(user_id):
    return user_id == MY_TELEGRAM_ID

# --- КОМАНДЫ БОТА ---

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    if not check_access(message.from_user.id):
        await message.reply("У вас нет доступа к этому боту.")
        return
    
    help_text = (
        "🔐 **Менеджер паролей**\n\n"
        "Доступные команды:\n"
        "• Сохранить: `/add Сервис Логин Пароль`\n"
        "• Найти: `/get Сервис`\n"
        "• Список: `/list`\n"
        "• Удалить: `/del ID`"
    )
    await message.reply(help_text, parse_mode="Markdown")

@dp.message_handler(commands=['add'])
async def cmd_add(message: types.Message):
    if not check_access(message.from_user.id):
        return

    args = message.get_args().split(maxsplit=2)
    if len(args) < 3:
        await message.reply("❌ Неверный формат.\nИспользуйте: `/add Сервис Логин Пароль`", parse_mode="Markdown")
        return

    service, login, raw_password = args
    
    # Шифруем пароль перед сохранением в БД
    encrypted_password = cipher.encrypt(raw_password.encode()).decode()

    conn = sqlite3.connect("passwords.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO passwords (service, login, password) VALUES (?, ?, ?)",
                   (service, login, encrypted_password))
    conn.commit()
    conn.close()

    await message.reply(f"✅ Пароль для **{service}** успешно сохранен!", parse_mode="Markdown")

@dp.message_handler(commands=['get'])
async def cmd_get(message: types.Message):
    if not check_access(message.from_user.id):
        return

    service_query = message.get_args().strip()
    if not service_query:
        await message.reply("❌ Укажите сервис для поиска.\nИспользуйте: `/get Сервис`", parse_mode="Markdown")
        return

    conn = sqlite3.connect("passwords.db")
    cursor = conn.cursor()
    cursor.execute("SELECT login, password FROM passwords WHERE service LIKE ?", (f"%{service_query}%",))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await message.reply("🔍 Ничего не найдено.")
        return

    response = "🔑 **Найденные записи:**\n\n"
    for login, encrypted_password in rows:
        # Расшифровываем пароль
        decrypted_password = cipher.decrypt(encrypted_password.encode()).decode()
        response += f"👤 Логин: `{login}`\n🔑 Пароль: `{decrypted_password}`\n\n"

    await message.reply(response, parse_mode="Markdown")

@dp.message_handler(commands=['list'])
async def cmd_list(message: types.Message):
    if not check_access(message.from_user.id):
        return

    conn = sqlite3.connect("passwords.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, service, login FROM passwords")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        dispatch_text = "📭 База данных пуста."
    else:
        dispatch_text = "📋 **Все сохраненные сервисы:**\n\n"
        for row_id, service, login in rows:
            dispatch_text += f"ID: `{row_id}` | Сервис: **{service}** | Логин: `{login}`\n"

    await message.reply(dispatch_text, parse_mode="Markdown")

@dp.message_handler(commands=['del'])
async def cmd_del(message: types.Message):
    if not check_access(message.from_user.id):
        return

    record_id = message.get_args().strip()
    if not record_id.isdigit():
        await message.reply("❌ Укажите корректный ID записи.\nИспользуйте: `/del ID` (посмотреть ID можно через `/list`)", parse_mode="Markdown")
        return

    conn = sqlite3.connect("passwords.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM passwords WHERE id = ?", (record_id,))
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()

    if rows_affected > 0:
        await message.reply(f"🗑 Запись с ID `{record_id}` удалена.", parse_mode="Markdown")
    else:
        await message.reply("❌ Запись с таким ID не найдена.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
