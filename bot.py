"""
Работает с этими модулями:

python-telegram-bot==11.1.0
redis==3.2.1
"""
import logging
from enum import Enum
from functools import partial

import redis
from environs import Env
from telegram.ext import Updater, Filters, CallbackContext
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from ep_api import get_products, ep_token_generator

_database = None
ep_token = ep_token_generator()


def start(update: Update, context: CallbackContext):
    main_menu_button = InlineKeyboardButton('Купить рыбу', callback_data='fish_menu')
    reply_markup = InlineKeyboardMarkup.from_button(main_menu_button)
    update.message.reply_text(text='Привет!', reply_markup=reply_markup)
    return StateFunction.MAIN_MENU.name


def main_menu(update: Update, context: CallbackContext):
    update.callback_query.answer()
    user_selection = update.callback_query.data
    if user_selection == 'fish_menu':
        return fish_menu(update, context)


def fish_menu(update: Update, context: CallbackContext):
    ep_access_token = next(ep_token)
    products = get_products(ep_access_token)
    keyboard = [
        [InlineKeyboardButton(product['attributes']['name'], callback_data=product['id'])]
        for product in products
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.effective_chat.send_message(text='Выбери рыбу:', reply_markup=reply_markup)
    return StateFunction.CHOOSING.name


def echo_choice(update: Update, context: CallbackContext):
    choice = update.callback_query.data
    update.effective_chat.send_message(choice)
    return StateFunction.CHOOSING.name


class StateFunction(Enum):
    START = partial(start)
    MAIN_MENU = partial(main_menu)
    FISH_MENU = partial(fish_menu)
    CHOOSING = partial(echo_choice)


def handle_users_reply(update: Update, context: CallbackContext):
    """Функция, которая запускается при любом сообщении от пользователя и решает как его обработать.

    Эта функция запускается в ответ на эти действия пользователя:
        * Нажатие на inline-кнопку в боте
        * Отправка сообщения боту
        * Отправка команды боту
    Она получает стейт пользователя из базы данных и запускает соответствующую функцию-обработчик (хэндлер).
    Функция-обработчик возвращает следующее состояние, которое записывается в базу данных.
    Если пользователь только начал пользоваться ботом, Telegram форсит его написать "/start",
    поэтому по этой фразе выставляется стартовое состояние.
    Если пользователь захочет начать общение с ботом заново, он также может воспользоваться этой командой.
    """
    db = get_database_connection()
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        update.callback_query.answer()
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    if user_reply == '/start':
        user_state = 'START'
    else:
        user_state = db.get(chat_id).decode("utf-8")

    state_handler = StateFunction[user_state].value
    next_state = state_handler(update, context)
    db.set(chat_id, next_state)


def get_database_connection():
    """Возвращает конекшн с базой данных Redis, либо создаёт новый, если он ещё не создан.
    """
    global _database
    if _database is None:
        env = Env()
        env.read_env()
        database_password = env.str("DATABASE_PASSWORD")
        database_host = env.str("DATABASE_HOST")
        database_port = env.int("DATABASE_PORT")
        _database = redis.Redis(host=database_host, port=database_port, password=database_password)
    return _database


def main():
    logging.basicConfig(level=logging.INFO)
    env = Env()
    env.read_env()
    token = env.str("TELEGRAM_TOKEN")
    updater = Updater(token)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
    dispatcher.add_handler(CommandHandler('start', handle_users_reply))
    updater.start_polling()


if __name__ == '__main__':
    main()
