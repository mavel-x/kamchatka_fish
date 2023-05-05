"""
Работает с этими модулями:

python-telegram-bot==11.1.0
redis==3.2.1
"""
import logging
from enum import Enum
from functools import partial

import redis
import telegram.error
from environs import Env
from telegram.ext import Updater, Filters, CallbackContext
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from ep_api import (get_all_products, get_product, get_image_url, ep_token_generator,
                    add_item_to_cart, get_cart_items, delete_cart_item,
                    create_customer)

_database = None
ep_token = ep_token_generator()


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


def start(update: Update, context: CallbackContext):
    main_menu_button = InlineKeyboardButton('Купить рыбу', callback_data='fish_menu')
    reply_markup = InlineKeyboardMarkup.from_button(main_menu_button)
    update.message.reply_text(text='Kamchatka Fish:\nГлавное меню', reply_markup=reply_markup)
    return StateFunction.MAIN_MENU.name


def main_menu(update: Update, context: CallbackContext):
    update.callback_query.answer()
    choice = update.callback_query.data
    if choice == 'fish_menu':
        return fish_menu(update, context)


def fish_menu(update: Update, context: CallbackContext):
    update.callback_query.answer()
    access_token = next(ep_token)
    products = get_all_products(access_token)
    keyboard = [
        [InlineKeyboardButton(product['attributes']['name'], callback_data=product['id'])]
        for product in products
    ]
    keyboard.append([InlineKeyboardButton('Корзина', callback_data='cart')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = 'Выберите рыбу:'
    try:
        update.effective_message.edit_text(message_text, reply_markup=reply_markup)
    except telegram.error.BadRequest:
        update.effective_chat.send_message(message_text, reply_markup=reply_markup)
        update.effective_message.delete()
    return StateFunction.HANDLE_MENU.name


def handle_menu(update: Update, context: CallbackContext):
    update.callback_query.answer()
    if update.callback_query.data == 'cart':
        return show_cart(update, context)
    else:
        return fish_description(update, context)


def fish_description(update: Update, context: CallbackContext):
    update.callback_query.answer()
    choice = update.callback_query.data
    access_token = next(ep_token)
    product = get_product(access_token, product_id=choice)
    image_id = product['relationships']['main_image']['data']['id']
    image_url = get_image_url(access_token, image_id=image_id)
    description = (f'{product["attributes"]["name"]}\n\n'
                   f'{product["attributes"]["description"]}')
    keyboard = [
        [
            InlineKeyboardButton(f'{num_kg} кг', callback_data=f'{choice}:{num_kg}')
            for num_kg in [1, 5, 10]
        ],
        [InlineKeyboardButton('Назад', callback_data='fish_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.effective_chat.send_photo(image_url, caption=description, reply_markup=reply_markup)
    update.effective_message.delete()
    return StateFunction.HANDLE_DESCRIPTION.name


def handle_description(update: Update, context: CallbackContext):
    choice = update.callback_query.data
    if choice == 'fish_menu':
        return fish_menu(update, context)
    product_id, quantity = choice.split(':')
    access_token = next(ep_token)
    add_item_to_cart(
        access_token=access_token,
        customer_id=update.effective_user.id,
        product_id=product_id,
        quantity=quantity,
    )
    update.callback_query.answer(f'{quantity} кг добавлено в корзину.')
    return StateFunction.HANDLE_DESCRIPTION.name


def handle_cart(update: Update, context: CallbackContext):
    if update.callback_query.data == 'fish_menu':
        return fish_menu(update, context)
    elif update.callback_query.data == 'pay':
        return handle_payment(update, context)
    access_token = next(ep_token)
    delete_cart_item(
        access_token,
        customer_id=update.effective_user.id,
        product_id=update.callback_query.data,
    )
    update.callback_query.answer('Товар удален.')
    return show_cart(update, context)


def format_cart_message(cart_items: dict):
    if not cart_items['data']:
        return 'Ваша корзина пока пуста.'
    cart_total = cart_items["meta"]["display_price"]["with_tax"]["formatted"]
    message_text = '\n'.join(
        [f'{product["name"]}\n'
         f'{product["quantity"]} кг в корзине '
         f'на сумму {product["meta"]["display_price"]["with_tax"]["value"]["formatted"]}\n'
         for product in cart_items['data']]
    )
    message_text += f'\nВсего товаров на сумму {cart_total}'
    return message_text


def show_cart(update: Update, context: CallbackContext):
    access_token = next(ep_token)
    cart_items = get_cart_items(access_token, customer_id=update.effective_user.id)
    message_text = format_cart_message(cart_items)
    keyboard = [
        [InlineKeyboardButton(f'Убрать {product["name"]}', callback_data=product['id'])]
        for product in cart_items['data']
    ]
    if cart_items['data']:
        keyboard.append([InlineKeyboardButton('Оплатить заказ', callback_data='pay')])
    keyboard.append([InlineKeyboardButton('Обратно в меню', callback_data='fish_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.effective_message.edit_text(message_text, reply_markup=reply_markup)
    return StateFunction.HANDLE_CART.name


def handle_payment(update: Update, context: CallbackContext):
    update.callback_query.answer()
    message_text = 'Пожалуйста, пришлите мне ваш контактный имейл.'
    update.effective_message.edit_text(message_text, reply_markup=None)
    return StateFunction.WAIT_EMAIL.name


def handle_email(update: Update, context: CallbackContext):
    email = update.message.text
    # TODO validate email
    message_text = f'Ваш имейл: {email}. Всё верно?'
    keyboard = [
        [InlineKeyboardButton('Да', callback_data=email)],
        [InlineKeyboardButton('Нет', callback_data='reenter_email')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.effective_chat.send_message(message_text, reply_markup=reply_markup)
    return StateFunction.CONFIRM_EMAIL.name


def confirm_email(update: Update, context: CallbackContext):
    if update.callback_query.data == 'reenter_email':
        return handle_payment(update, context)
    access_token = next(ep_token)
    create_customer(
        access_token,
        full_name=update.effective_user.full_name,
        email=update.callback_query.data
    )
    return confirm_payment(update, context)


def confirm_payment(update: Update, context: CallbackContext):
    update.callback_query.answer()
    message_text = 'Спасибо! С вами свяжутся для завершения оплаты.'
    reply_markup = InlineKeyboardMarkup.from_button(
        InlineKeyboardButton('Обратно в меню', callback_data='fish_menu')
    )
    update.effective_message.edit_text(message_text, reply_markup=reply_markup)
    return StateFunction.MAIN_MENU.name


class StateFunction(Enum):
    START = partial(start)
    MAIN_MENU = partial(main_menu)
    HANDLE_MENU = partial(handle_menu)
    HANDLE_DESCRIPTION = partial(handle_description)
    HANDLE_CART = partial(handle_cart)
    WAIT_EMAIL = partial(handle_email)
    CONFIRM_EMAIL = partial(confirm_email)


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
