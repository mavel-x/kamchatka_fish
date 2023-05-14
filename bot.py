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
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, Dispatcher
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from ep_api import ElasticPathClient

_database = None


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
    ep_client: ElasticPathClient = context.bot_data['ep_client']
    update.callback_query.answer()
    products = ep_client.get_all_products()
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
    ep_client: ElasticPathClient = context.bot_data['ep_client']
    update.callback_query.answer()
    choice = update.callback_query.data
    product = ep_client.get_product(product_id=choice)
    image_url = ep_client.get_product_image(product)
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
    ep_client: ElasticPathClient = context.bot_data['ep_client']
    choice = update.callback_query.data
    if choice == 'fish_menu':
        return fish_menu(update, context)
    product_id, quantity = choice.split(':')
    ep_client.add_item_to_cart(
        customer_id=update.effective_user.id,
        product_id=product_id,
        quantity=quantity,
    )
    update.callback_query.answer(f'{quantity} кг добавлено в корзину.')
    return StateFunction.HANDLE_DESCRIPTION.name


def handle_cart(update: Update, context: CallbackContext):
    ep_client: ElasticPathClient = context.bot_data['ep_client']
    if update.callback_query.data == 'fish_menu':
        return fish_menu(update, context)
    elif update.callback_query.data == 'pay':
        return handle_payment(update, context)
    ep_client.delete_cart_item(
        customer_id=update.effective_user.id,
        product_id=update.callback_query.data,
    )
    update.callback_query.answer('Товар удален.')
    return show_cart(update, context)


def create_cart_message(cart_items: dict):
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
    ep_client: ElasticPathClient = context.bot_data['ep_client']
    cart_items = ep_client.get_cart_items(customer_id=update.effective_user.id)
    message_text = create_cart_message(cart_items)

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
    ep_client: ElasticPathClient = context.bot_data['ep_client']
    if update.callback_query.data == 'reenter_email':
        return handle_payment(update, context)
    ep_client.create_customer(
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
    ep_client_id = env.str('EP_CLIENT_ID')
    ep_client_secret = env.str('EP_SECRET')
    ep_client = ElasticPathClient(ep_client_id, ep_client_secret)
    
    updater = Updater(token)
    dispatcher: Dispatcher = updater.dispatcher
    dispatcher.bot_data.update({'ep_client': ep_client})
    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
    dispatcher.add_handler(CommandHandler('start', handle_users_reply))
    updater.start_polling()


if __name__ == '__main__':
    main()
