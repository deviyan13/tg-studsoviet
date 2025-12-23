import os
import io
import logging
import asyncio
import requests

from PIL import Image, ImageDraw, ImageFont
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters
)
from dotenv import load_dotenv

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

# Добавлен новый этап REQUIRED_COUNT
QUEST_NAME, PARTICIPANTS_COUNT, REQUIRED_COUNT = range(3)
# Параметры изображения
IMAGE_WIDTH = 1400
IMAGE_HEIGHT = 350
BACKGROUND_COLOR = (16, 53, 71)  # Темный синий цвет
TEXT_COLOR = (248, 241, 222)  # Белый текст
ACCENT_COLOR = (253, 188, 58)  # Золотой/желтый цвет

# 🔐 СИСТЕМА ДОСТУПА
# Получаем список разрешенных пользователей из переменной окружения
ALLOWED_USERS = os.environ.get('ALLOWED_USERS', '').split(',')
ALLOWED_USERS = [int(user_id.strip()) for user_id in ALLOWED_USERS if user_id.strip()]
ADMIN_USER_ID = int(os.environ.get('ADMIN_USER_ID', 0))  # Твой ID для административных функций

MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [["📝 Создать форму"]],
    resize_keyboard=True,
    is_persistent=True # Делаем клавиатуру постоянной
)


def check_access(user_id: int) -> bool:
    """Проверяет доступ пользователя к боту"""
    print("user is admin")
    return user_id in ALLOWED_USERS


async def access_denied(update: Update) -> None:
    """Сообщение об отказе в доступе"""
    await update.message.reply_text(
        "❌ Доступ запрещен.\n\n"
        "Этот бот доступен только для авторизованных пользователей. "
        "Обратитесь к @deviyann для получения доступа."
    )


def split_text_to_lines(text: str) -> tuple:
    """Разбивает текст по кавычкам: первая строка - до кавычек, вторая - в кавычках"""

    text = text.replace('"', '«', 1)
    text = text.replace('"', '»', 1)

    # Ищем кавычки
    if '«' in text and '»' in text:
        # Разбиваем по кавычкам
        before_quotes = text[:text.index('«')].strip().upper()
        quoted_part = text[text.index('«'):text.index('»') + 1].upper()

        return before_quotes, quoted_part
    else:
        # Если кавычек нет, просто разбиваем на две части
        words = text.split()
        if len(words) <= 1:
            return "КВЕСТ", text.upper()

        mid = len(words) // 2
        line1 = " ".join(words[:mid]).upper()
        line2 = " ".join(words[mid:]).upper()

        return line1, line2


import re


async def send_image_as_both_photo_and_file(update: Update, image_buffer: io.BytesIO, quest_name: str,
                                            caption: str = ""):
    """Отправляет картинку как фото и как файл (документ)"""

    # Очищаем название для имени файла
    safe_name = re.sub(r'[^\w\s-]', '', quest_name)
    safe_name = re.sub(r'[-\s]+', '_', safe_name)
    safe_name = safe_name.strip('-_')

    # Если имя слишком длинное, обрезаем
    if len(safe_name) > 50:
        safe_name = safe_name[:50]

    filename = f"{safe_name}.png"

    # Сбрасываем буфер для повторного использования
    image_buffer.seek(0)

    # Отправляем как фото
    await update.message.reply_photo(
        photo=image_buffer,
        caption=caption
    )

    # Снова сбрасываем буфер для отправки как файл
    image_buffer.seek(0)

    # Отправляем как документ (файл)
    await update.message.reply_document(
        document=image_buffer,
        filename=filename,
        caption="📎 А это тот же файл в формате PNG для скачивания"
    )

def generate_quest_image(quest_name: str) -> io.BytesIO:
    """Генерирует картинку и возвращает буфер для Telegram"""

    img = Image.new('RGB', (IMAGE_WIDTH, IMAGE_HEIGHT), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(img)

    # Загружаем шрифты Montserrat
    try:
        font_subtitle = ImageFont.truetype("Montserrat-Black.ttf", 58.3)
        font_main = ImageFont.truetype("Montserrat-Black.ttf", 95)
        font_footer = ImageFont.truetype("Montserrat-Bold.ttf", 37.23)
    except:
        # Если Montserrat не найден, используем Arial
        print("ahhh")
        font_subtitle = ImageFont.truetype("arialbd.ttf", 50)
        font_main = ImageFont.truetype("arialbd.ttf", 95)
        font_footer = ImageFont.truetype("arial.ttf", 28)

    # Подзаголовок "РЕГИСТРАЦИЯ НА"
    draw.text(
        (IMAGE_WIDTH / 2, 25),
        "РЕГИСТРАЦИЯ",
        font=font_subtitle,
        fill=TEXT_COLOR,
        anchor="mt"
    )

    line1, line2 = split_text_to_lines(quest_name)
    draw.text(
        (IMAGE_WIDTH / 2, 120),
        f'НА {line1.upper()}',
        font=font_main,
        fill=TEXT_COLOR,
        anchor="mt"
    )

    # Основное название - с адаптивным размером шрифта
    curr_size = 95
    q_font = ImageFont.truetype("Montserrat-Black.ttf", 95)

    while True:
        q_font = ImageFont.truetype("Montserrat-Black.ttf", curr_size)

        bbox = draw.textbbox((0, 0), line2.upper(), font=q_font)
        text_width = bbox[2] - bbox[0]

        if text_width < IMAGE_WIDTH - 100 or curr_size <= 30:
            break
        curr_size -= 2.5

    draw.text(
        (IMAGE_WIDTH / 2, 225),
        line2.upper(),
        font=q_font,
        fill=ACCENT_COLOR,
        anchor="mt"
    )

    # Подпись внизу
    draw.text(
        (30.5, 30),
        "bsuirhostel.5",
        font=font_footer,
        fill=(76, 107, 125, 80),
        anchor="lt"
    )

    draw.text(
        (1118.33, 30),
        "bsuirhostel.5",
        font=font_footer,
        fill=(76, 107, 125, 80),
        anchor="lt"
    )

    # Сохраняем в буфер
    img_io = io.BytesIO()
    img.save(img_io, format='PNG')
    img_io.seek(0)
    return img_io


# --- ЗАПРОС К СКРИПТУ ---
def call_google_script(quest_name, count, req_count):  # Передача req_count
    """Отправляем данные формы и req_count"""
    script_url = os.environ.get('GOOGLE_SCRIPT_URL')
    folder_id = os.environ.get('GOOGLE_DRIVE_FOLDER_ID')

    if not script_url: raise ValueError("Нет URL скрипта")

    payload = {
        "questName": quest_name,
        "count": count,
        "required_count": req_count,  # Отправляем минимальное количество
        "folderId": folder_id
    }

    response = requests.post(script_url, json=payload)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"HTTP {response.status_code}: {response.text}")


# --- АДМИНИСТРАТИВНЫЕ КОМАНДЫ ---
async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список административных команд"""
    if not check_access(update.effective_user.id):
        await access_denied(update)
        return

    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Эта команда только для администратора.")
        return

    user_list = "\n".join([f"• {user_id}" for user_id in ALLOWED_USERS])

    await update.message.reply_text(
        f"🛠️ <b>Административные команды:</b>\n\n"
        f"<b>Текущие пользователи:</b>\n{user_list}\n\n"
        f"<b>Команды:</b>\n"
        f"/users - Показать список пользователей\n"
        f"/stats - Статистика использования",
        parse_mode='HTML',
        reply_markup=MAIN_MENU_KEYBOARD
    )


async def show_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список разрешенных пользователей"""
    if not check_access(update.effective_user.id):
        await access_denied(update)
        return

    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Эта команда только для администратора.")
        return

    if not ALLOWED_USERS:
        await update.message.reply_text("📝 Список пользователей пуст.", reply_markup=MAIN_MENU_KEYBOARD)
        return

    user_list = "\n".join([f"• {user_id}" for user_id in ALLOWED_USERS])
    await update.message.reply_text(
        f"📋 <b>Разрешенные пользователи:</b>\n\n{user_list}",
        parse_mode='HTML',
        reply_markup=MAIN_MENU_KEYBOARD
    )


# --- ОБНОВЛЕННЫЕ HANDLERS С ПРОВЕРКОЙ ДОСТУПА И МЕНЮ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start с кнопкой"""
    if not check_access(update.effective_user.id):
        await access_denied(update)
        return ConversationHandler.END

    await update.message.reply_text(
        "🤖 Привет! Я бот для создания форм регистрации на мероприятия.\n\n"
        "Используй кнопку ниже чтобы начать создание формы:",
        reply_markup=MAIN_MENU_KEYBOARD
    )
    return ConversationHandler.END


async def create_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /createForm"""
    if not check_access(update.effective_user.id):
        await access_denied(update)
        return ConversationHandler.END

    await update.message.reply_text(
        "🤖 Привет! Введи название мероприятия:",
        reply_markup=ReplyKeyboardRemove()  # Убираем меню на время диалога
    )
    return QUEST_NAME


async def create_form_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия на кнопку 'Создать форму'"""
    if not check_access(update.effective_user.id):
        await access_denied(update)
        return ConversationHandler.END

    await update.message.reply_text(
        "🤖 Отлично! Введи название мероприятия:",
        reply_markup=ReplyKeyboardRemove()  # Убираем меню на время диалога
    )
    return QUEST_NAME


async def get_quest_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает название квеста"""
    if not check_access(update.effective_user.id):
        await access_denied(update)
        return ConversationHandler.END

    context.user_data['quest_name'] = update.message.text.upper()
    await update.message.reply_text("🔢 Введи МАКСИМАЛЬНОЕ количество участников в команде:")
    return PARTICIPANTS_COUNT


async def get_participants_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает количество участников"""
    if not check_access(update.effective_user.id):
        await access_denied(update)
        return ConversationHandler.END

    try:
        count = int(update.message.text)
        if count <= 0:
            await update.message.reply_text("Количество должно быть положительным числом.")
            return PARTICIPANTS_COUNT

        context.user_data['count'] = count
        await update.message.reply_text(
            f"📝 Теперь введи МИНИМАЛЬНОЕ количество участников в команде (должно быть не больше {count}):")
        return REQUIRED_COUNT

    except ValueError:
        await update.message.reply_text("Нужно ввести число.")
        return PARTICIPANTS_COUNT


async def get_required_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершает создание формы"""
    if not check_access(update.effective_user.id):
        await access_denied(update)
        return ConversationHandler.END

    try:
        req_count = int(update.message.text)
        max_count = context.user_data['count']

        if req_count <= 0 or req_count > max_count:
            await update.message.reply_text(f"Минимальное количество должно быть числом от 1 до {max_count}.")
            return REQUIRED_COUNT

        # Собираем все данные
        quest_name = context.user_data['quest_name']

        # 1. Генерируем картинку и отправляем в чат
        status_msg = await update.message.reply_text("🎨 Генерирую картинку...")
        img_io = generate_quest_image(quest_name)

        # await update.message.reply_photo(
        #     photo=img_io,
        #     caption="✅ Картинка готова! Сохрани ее и загрузи в форму вручную в Шапку."
        # )
        await send_image_as_both_photo_and_file(
            update=update,
            image_buffer=img_io,
            quest_name=quest_name,
            caption="✅ Картинка готова! Сохрани ее и загрузи в форму вручную в Шапку."
        )

        await status_msg.edit_text("🚀 Отправляю задачу в Google (создание + связка)...")

        # 2. Запускаем скрипт
        loop = asyncio.get_running_loop()
        try:
            # Передаем обе переменные с количеством
            result = await loop.run_in_executor(None, call_google_script, quest_name, max_count, req_count)

            if result.get('status') == 'success':
                text = (
                    f"✅ Автоматизация завершена!\n\n"
                    f"📝 Форма (для заполнения): {result['formUrl']}\n"
                    f"📝 Форма (редактирование): {result['editFormUrl']}\n"
                    f"📊 Таблица: {result['sheetUrl']}\n\n"
                    f"ℹ️ Важно! Форма настроена так, что {req_count} первых участника ОБЯЗАТЕЛЬНЫ.\n"
                    f"Следующие шаги:\n"
                    f"1. Открой форму и установи шрифт Montserrat.\n"
                    f"2. Загрузи картинку, которую я прислал, в Шапку темы."
                )
                await status_msg.edit_text(text, disable_web_page_preview=True)

                # Возвращаем меню после успешного создания
                await update.message.reply_text(
                    "🎉 Форма готова! Хочешь создать еще одну?",
                    reply_markup=MAIN_MENU_KEYBOARD
                )
            else:
                await status_msg.edit_text(f"⚠️ Ошибка скрипта: {result.get('message')}")
                # Возвращаем меню даже при ошибке
                await update.message.reply_text(
                    "Попробуй еще раз:",
                    reply_markup=MAIN_MENU_KEYBOARD
                )

        except Exception as e:
            logger.error(f"Error: {e}")
            await status_msg.edit_text(f"❌ Ошибка соединения.")
            # Возвращаем меню при ошибке соединения
            await update.message.reply_text(
                "Произошла ошибка. Попробуй еще раз:",
                reply_markup=MAIN_MENU_KEYBOARD
            )

        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text("Нужно число.")
        return REQUIRED_COUNT


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена с возвратом в главное меню"""
    if not check_access(update.effective_user.id):
        await access_denied(update)
        return ConversationHandler.END

    await update.message.reply_text(
        "Отмена. Возвращаю в главное меню.",
        reply_markup=MAIN_MENU_KEYBOARD
    )
    return ConversationHandler.END


async def handle_unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик неизвестных сообщений"""
    if not check_access(update.effective_user.id):
        await access_denied(update)
        return

    await update.message.reply_text(
        "🤔 Не понял твоего сообщения. Используй кнопку 'Создать форму' для начала работы.",
        reply_markup=MAIN_MENU_KEYBOARD
    )


import os


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    # URL вашего приложения на Render (вы получите его после создания сервиса)
    # Например: https://my-cool-bot.onrender.com
    webhook_url = os.environ.get("WEBHOOK_URL")

    # Порт, который Render выдает автоматически.
    # Если локально — используем 8000
    port = int(os.environ.get("PORT", 8000))

    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не установлен")

    app = Application.builder().token(token).build()

    # --- РЕГИСТРАЦИЯ ВАШИХ HANDLERS (ОСТАЕТСЯ КАК БЫЛО) ---
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('createForm', create_form),
            MessageHandler(filters.Regex('^📝 Создать форму$'), create_form_button)
        ],
        states={
            QUEST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_quest_name)],
            PARTICIPANTS_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_participants_count)],
            REQUIRED_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_required_count)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("admin", admin_help))
    app.add_handler(CommandHandler("users", show_users))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message))

    # --- ЛОГИКА ЗАПУСКА ---
    if webhook_url:
        # Запуск на Render (Webhooks)
        logger.info(f"Запуск Webhook: {webhook_url} на порту {port}")
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=token,
            webhook_url=f"{webhook_url}/{token}"
        )
    else:
        # Запуск локально (Polling)
        logger.info("Запуск Polling (локально)...")
        app.run_polling()


if __name__ == '__main__':
    main()