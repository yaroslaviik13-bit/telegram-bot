from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
import time
from io import BytesIO
from PIL import Image
import pytesseract

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from groq import Groq

# ================= НАСТРОЙКИ =================
TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"
GROQ_API_KEY = "GROQ_API_KEY"

# путь к tesseract.exe (ПРОВЕРЬ!)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

FLOOD_TIMEOUT = 3  # секунд
# ============================================

client = Groq(api_key=GROQ_API_KEY)
last_message_time = {}

SYSTEM_PROMPT = (
    "Ты — ИИ помощник для задачек и справочных вопросов.\n\n"
    "ВАЖНО:\n"
    "Задают пример - без обьяснений, просто ответ.\n\n"
    "Если задачки, то необязательно математические.\n\n"
    "Сначала определи тип запроса.\n\n"

    "ТИПЫ ЗАПРОСОВ:\n\n"

    "1) Справочный вопрос\n"
    "(«что такое…», «сколько…», «каково расстояние…», «чему равно…»)\n"
    "→ НИЧЕГО НЕ СЧИТАЙ\n"
    "→ Просто дай краткий точный ответ\n"
    "→ Без слова «Решение»\n\n"

    "2) Математическая задача\n"
    "(есть условие, нужно найти, проценты, формулы)\n"
    "→ Решай по шагам\n"
    "→ Используй ТОЛЬКО данные из текста\n"
    "Если нет условия, то пиши просто ответ.\n\n"

    "СТРОГИЕ ЗАПРЕТЫ:\n"
    "❌ Не придумывай данные\n"
    "❌ Не меняй числа\n"
    "❌ Не делай предположений\n"
    "❌ Не решай другую задачу\n\n"

    "ЕСЛИ:\n"
    "– данных недостаточно → так и напиши\n"
    "– вопрос некорректен → укажи это\n\n"

    "ФОРМАТ ОТВЕТА:\n\n"

    "ЕСЛИ это задача:\n"
    "Решение:\n"
    "(коротко, по шагам)\n"
    "Ответ:\n"
    "(одна строка)\n\n"

    "ЕСЛИ это справка:\n"
    "Краткий ответ:\n"
    "(одна строка)"
)




def main_menu():
    keyboard = [
        [InlineKeyboardButton("📝 Задать вопрос", callback_data="ask")],
        [InlineKeyboardButton("📷 Решить задачу по фото", callback_data="photo")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "ask":
        await query.message.reply_text("📝 Напиши вопрос текстом")

    elif query.data == "photo":
        await query.message.reply_text("📷 Отправь фото с задачей")

    elif query.data == "help":
        await query.message.reply_text(
            "ℹ️ Я умею:\n\n"
            "• решать математические задачи\n"
            "• работать с фото (OCR)\n"
            "• отвечать строго по условиям\n\n"
            "⚠️ 1 сообщение раз в несколько секунд"
        )


# ================= /start =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет!\n\n"
        "Я решаю математические задачи и отвечаю на вопросы.\n"
        "Выбери действие:",
        reply_markup=main_menu()
    )


# ================= /help =================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Возможности бота:\n\n"
        "📝 Текст — отвечаю на вопросы\n"
        "📷 Фото — распознаю текст и решаю задачу\n"
        "🧠 Понимаю математику, шифры, условия задач\n\n"
        "⚠️ Защита от флуда: 1 сообщение раз в несколько секунд"
    )

# ================= АНТИФЛУД =================
def is_flood(user_id: int) -> bool:
    now = time.time()
    last = last_message_time.get(user_id, 0)
    if now - last < FLOOD_TIMEOUT:
        return True
    last_message_time[user_id] = now
    return False

# ================= ТЕКСТ =================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if is_flood(user_id):
        return

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": update.message.text},
            ],
            temperature=0.7,
            max_tokens=1024,
        )

        answer = completion.choices[0].message.content
        await update.message.reply_text(answer)

    except Exception as e:
        print("GROQ ERROR:", e)
        await update.message.reply_text("❌ Ошибка обработки запроса")

# ================= ФОТО =================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if is_flood(user_id):
        return

    try:
        await update.message.reply_text("📷 Распознаю текст...")

        photo = update.message.photo[-1]
        file = await photo.get_file()
        bio = BytesIO()
        await file.download_to_memory(out=bio)
        bio.seek(0)

        image = Image.open(bio)

        text = pytesseract.image_to_string(image, lang="rus+eng").strip()

        if not text:
            await update.message.reply_text("❌ Не удалось распознать текст")
            return

        prompt = (
            "Реши задачу, распознанную с фото:\n\n"
            f"{text}"
        )

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1024,
        )

        answer = completion.choices[0].message.content
        await update.message.reply_text(answer)

    except Exception as e:
        print("PHOTO ERROR:", e)
        await update.message.reply_text("❌ Ошибка обработки фото")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("🤖 Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    from telegram.ext import CallbackQueryHandler


    def main():
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))

        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

        app.add_handler(CallbackQueryHandler(menu_callback))  # ← ВАЖНО: ТУТ

        print("🤖 Бот запущен")
        app.run_polling()


    main()
