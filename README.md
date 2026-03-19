# Telegram Avito Notifier с базой данных

Простой, но демонстрационный Telegram-бот на Python, который:
- Сохраняет вставленную ссылку в базу данных
- Проверяет наличие новых объявлений
- Уведомляет о новых объявлениях

## Возможности
- Команды: /start, /set_url, /hcheck, /status
- Сохранение URL

## Стек
- pyTelegramBotAPI
- SQLite3
- python-dotenv

## Запуск

```bash
pip install -r requirements.txt
# создай .env с BOT_TOKEN=... и ADMIN_ID=...
python bot.py
