# kamchatka_fish
Selling seafood on Telegram.

Демо-бот (MVP): https://t.me/kamchatka_fish_bot.

## Установка и настройка

### Установка зависимостей
1. Создайте виртуальное окружение и установите в него необходимые библиотеки:
   ```commandline
   python3 -m venv venv
   venv/bin/pip install -U -r requirements.txt 
   ```
1. Создайте файл `.env` в корневой директории проекта. Далее в него предстоит добавить
переменные окружения для Redis, ElasticPath (Moltin) и Telegram.

### Бот для Телеграма
1. Создать бота через BotFather
2. Добавить его токен в файл `.env`:
    ```
    TELEGRAM_TOKEN=...
    ```

### Интернет-магазин на базе Elastic Path
1. Зарегистрируйтесь и добавьте товары в магазин через админку [Elastic Path](https://elasticpath.dev/docs/getting-started/overview).
2. Для использования [API Elastic Path](https://elasticpath.dev/docs/getting-started/overview) вам потребуется ключ клиента и секретный ключ.
Сохраните их в `.env`:
   ```
    EP_SECRET=...
    EP_CLIENT_ID=...
    ```

### База данных Redis
Часть функционала бота зависит от соединения с Redis [(гайд)](https://developer.redis.com/howtos/quick-start/). 
Сохраните в `.env` следующие переменные:
```
DATABASE_PASSWORD=...
DATABASE_HOST=...
DATABASE_PORT=...
```

## Использование
Запустите бота из скрипта bot.py.
Для запуска на сервере вам поможет, например, утилита 
[screens](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Hosting-your-bot#start-your-bot).

## О проекте
Это учебный проект для школы Python-разработчиков [dvmn.org](https://dvmn.org).