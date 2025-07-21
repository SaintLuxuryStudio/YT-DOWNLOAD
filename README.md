# YouTube Downloader Telegram Bot

Telegram бот для скачивания видео и аудио с YouTube с поддержкой разных качеств и автоматической конвертацией в MP3.

## Возможности

- 📹 Скачивание видео в формате MP4
- 🎵 Конвертация и скачивание аудио в формате MP3
- 📊 Прогресс-бар загрузки в реальном времени
- 🔍 Выбор качества видео
- 🧹 Автоматическое удаление файлов после отправки
- 📝 Подробное логирование
- ⚖️ Проверка размера файла (лимит 1.9GB для Telegram)

## Установка

### 1. Клонирование и установка зависимостей

```bash
# Перейдите в папку проекта
cd "YT DOWNLOAD"

# Запустите установку
python setup.py
```

### 2. Настройка бота

1. Создайте бота у [@BotFather](https://t.me/BotFather) в Telegram
2. Получите токен бота
3. Скопируйте `.env.example` в `.env`:
   ```bash
   cp .env.example .env
   ```
4. Отредактируйте `.env` файл и добавьте ваш токен:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   ```

### 3. Установка FFmpeg (для конвертации в MP3)

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt install ffmpeg
```

**Windows:**
Скачайте с [ffmpeg.org](https://ffmpeg.org/download.html)

## Запуск

### Telegram бот
```bash
python telegram_bot.py
```

### Локальный скрипт (для тестирования)
```bash
python downloader.py
```

## Использование

1. Отправьте боту ссылку на YouTube видео
2. Выберите качество из предложенных вариантов
3. Выберите формат:
   - Отправьте желаемое разрешение (например, "720p") для видео
   - Отправьте "audio" для получения MP3

## Структура проекта

```
YT DOWNLOAD/
├── requirements.txt          # Зависимости Python
├── setup.py                 # Скрипт установки
├── downloader.py            # Основной модуль скачивания
├── telegram_bot.py          # Telegram бот
├── .env.example             # Пример файла окружения
├── README.md               # Документация
└── downloads/              # Папка для временных файлов (создается автоматически)
```

## Ограничения

- Максимальный размер файла: 1.9GB (ограничение Telegram)
- Поддерживаются только отдельные видео (не плейлисты)
- Файлы автоматически удаляются после отправки

## Логи

Логи сохраняются в файлы:
- `downloader.log` - логи модуля скачивания
- `bot.log` - логи Telegram бота

## Команды бота

- `/start` - Приветствие и инструкции
- `/help` - Справка по использованию

## Развертывание на сервере

Для развертывания на VPS используйте systemd service или Docker. Пример systemd service:

```ini
[Unit]
Description=YouTube Downloader Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/project
ExecStart=/usr/bin/python3 telegram_bot.py
Restart=always
Environment=TELEGRAM_BOT_TOKEN=your_token

[Install]
WantedBy=multi-user.target
```

## Безопасность

- Никогда не коммитьте `.env` файл с токенами
- Регулярно обновляйте зависимости
- Мониторьте логи на предмет ошибок