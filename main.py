import os
import json
import io
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters
)
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from google.apps import forms_v1
from googleapiclient.discovery import build
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

QUEST_NAME, PARTICIPANTS_COUNT, EMAIL = range(3)

# Координаты элементов (в пикселях для размера 8400x2100)
BACKGROUND_COLOR = (31, 79, 109)  # Темный сине-зеленый цвет
TEXT_COLOR = (255, 223, 87)  # Золотистый цвет

# Размеры в исходных единицах фигмы (8400x2100)
FIGMA_WIDTH = 8400
FIGMA_HEIGHT = 2100


def generate_quest_image(quest_name: str) -> bytes:
    """Генерирует картинку для квеста с заданным названием"""

    img = Image.new('RGB', (FIGMA_WIDTH, FIGMA_HEIGHT), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(img)

    try:
        # Загружаем шрифты (если нет, используем стандартный)
        try:
            font_small = ImageFont.truetype("montserrat-bold.ttf", 223)
            font_middle = ImageFont.truetype("montserrat-black.ttf", 350)
            font_large = ImageFont.truetype("montserrat-black.ttf", 600)
        except:
            # Fallback на стандартный шрифт
            font_small = ImageFont.load_default()
            font_middle = ImageFont.load_default()
            font_large = ImageFont.load_default()

        # Текст "РЕГИСТРАЦИЯ НА"
        text_registration = "РЕГИСТРАЦИЯ НА"
        bbox = draw.textbbox((0, 0), text_registration, font=font_middle)
        text_width = bbox[2] - bbox[0]
        x_reg = (FIGMA_WIDTH - text_width) // 2
        y_reg = 550
        draw.text((x_reg, y_reg), text_registration, font=font_middle, fill=TEXT_COLOR)

        # Название квеста (адаптивный размер)
        quest_upper = quest_name.upper()

        # Подбираем размер шрифта чтобы текст поместился
        font_size = 500
        while font_size > 100:
            try:
                font_quest = ImageFont.truetype("montserrat-black.ttf", font_size)
            except:
                font_quest = font_large

            bbox = draw.textbbox((0, 0), quest_upper, font=font_quest)
            text_width = bbox[2] - bbox[0]

            if text_width < FIGMA_WIDTH - 200:
                break
            font_size -= 50

        bbox = draw.textbbox((0, 0), quest_upper, font=font_quest)
        text_width = bbox[2] - bbox[0]
        x_quest = (FIGMA_WIDTH - text_width) // 2
        y_quest = 900
        draw.text((x_quest, y_quest), quest_upper, font=font_quest, fill=TEXT_COLOR)

        # Текст "bsuirhostel.5"
        text_brand = "bsuirhostel.5"
        try:
            font_brand = ImageFont.truetype("montserrat-bold.ttf", 223)
        except:
            font_brand = font_small

        bbox = draw.textbbox((0, 0), text_brand, font=font_brand)
        text_width = bbox[2] - bbox[0]
        x_brand = (FIGMA_WIDTH - text_width) // 2
        y_brand = 1550
        draw.text((x_brand, y_brand), text_brand, font=font_brand, fill=(100, 150, 180))

    except Exception as e:
        logger.error(f"Ошибка при генерации изображения: {e}")

    # Сохраняем в буфер
    img_io = io.BytesIO()
    img.save(img_io, format='PNG')
    img_io.seek(0)
    return img_io.getvalue()


def get_google_credentials():
    """Получает credentials для Google API"""
    creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS_JSON не установлена")

    creds_dict = json.loads(creds_json)
    credentials = Credentials.from_service_account_info(
        creds_dict,
        scopes=[
            'https://www.googleapis.com/auth/forms',
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
    )
    return credentials


def create_google_form_and_sheet(quest_name: str, participants_count: int, user_email: str = None):
    """Создает Google Form и Google Sheet с подключением"""
    try:
        credentials = get_google_credentials()

        # Создаем Google Sheet
        sheets_service = build('sheets', 'v4', credentials=credentials)
        spreadsheet = sheets_service.spreadsheets().create(
            body={'properties': {'title': f'{quest_name} - Ответы'}}
        ).execute()
        sheet_id = spreadsheet['spreadsheetId']
        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"

        # Создаем заголовки для ответов
        headers = ['Временная метка', 'Email', 'Имя']
        for i in range(1, participants_count + 1):
            headers.append(f'Участник {i}')

        sheets_service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range='Sheet1!A1',
            valueInputOption='RAW',
            body={'values': [headers]}
        ).execute()

        # Создаем Google Form
        forms_service = build('forms', 'v1', credentials=credentials)
        form_body = {
            'info': {
                'title': quest_name,
                'description': f'Регистрация на {quest_name}'
            }
        }
        form = forms_service.forms().create(body=form_body).execute()
        form_id = form['formId']
        form_url = f"https://docs.google.com/forms/d/{form_id}/viewform"

        # Добавляем поля в форму
        update_request = {
            'requests': [
                {
                    'addItem': {
                        'item': {
                            'title': 'Email',
                            'questionItem': {
                                'question': {
                                    'required': True,
                                    'textQuestion': {'paragraph': False}
                                }
                            }
                        },
                        'location': {'index': 0}
                    }
                },
                {
                    'addItem': {
                        'item': {
                            'title': 'Имя',
                            'questionItem': {
                                'question': {
                                    'required': True,
                                    'textQuestion': {'paragraph': False}
                                }
                            }
                        },
                        'location': {'index': 1}
                    }
                }
            ]
        }

        # Добавляем поля для участников
        for i in range(participants_count):
            update_request['requests'].append({
                'addItem': {
                    'item': {
                        'title': f'Участник {i + 1}',
                        'questionItem': {
                            'question': {
                                'required': False,
                                'textQuestion': {'paragraph': False}
                            }
                        }
                    },
                    'location': {'index': i + 2}
                }
            })

        forms_service.forms().batchUpdate(
            formId=form_id,
            body=update_request
        ).execute()

        # Подключаем форму к таблице
        forms_service.forms().batchUpdate(
            formId=form_id,
            body={
                'requests': [{
                    'updateFormInfo': {
                        'info': {'linkedSheetId': sheet_id},
                        'updateMask': 'linkedSheetId'
                    }
                }]
            }
        ).execute()

        return form_url, sheet_url

    except Exception as e:
        logger.error(f"Ошибка при создании формы: {e}")
        raise


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Стартовая команда"""
    await update.message.reply_text(
        'Привет! Я помогу создать форму для регистрации на квест.\n\n'
        'Напиши название мероприятия:'
    )
    return QUEST_NAME


async def quest_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает название квеста"""
    context.user_data['quest_name'] = update.message.text
    await update.message.reply_text(
        'Отлично! Теперь укажи количество участников:'
    )
    return PARTICIPANTS_COUNT


async def participants_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает количество участников"""
    try:
        count = int(update.message.text)
        if count <= 0:
            await update.message.reply_text('Количество должно быть больше 0. Попробуй ещё раз:')
            return PARTICIPANTS_COUNT

        context.user_data['participants_count'] = count
        await update.message.reply_text(
            '✨ Создаю твой квест...',
            reply_markup=ReplyKeyboardRemove()
        )

        quest_name = context.user_data['quest_name']

        # Генерируем картинку
        img_data = generate_quest_image(quest_name)
        await update.message.reply_photo(photo=img_data)

        # Создаем форму и таблицу
        form_url, sheet_url = create_google_form_and_sheet(
            quest_name,
            count,
            update.effective_user.id
        )

        # Отправляем ссылки
        response = (
            f'🎉 Готово!\n\n'
            f'📋 Форма для регистрации:\n{form_url}\n\n'
            f'📊 Таблица с ответами:\n{sheet_url}\n\n'
            f'Для создания нового квеста напиши /start'
        )
        await update.message.reply_text(response)

        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text('Это не число! Попробуй ещё раз:')
        return PARTICIPANTS_COUNT


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена"""
    await update.message.reply_text(
        'Отменено. Напиши /start когда будешь готов.',
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


def main():
    """Запускает бота"""
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не установлена")

    application = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            QUEST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, quest_name)],
            PARTICIPANTS_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, participants_count)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)

    application.run_polling()


if __name__ == '__main__':
    main()