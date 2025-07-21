#!/usr/bin/env python3
import subprocess
import sys
import os

def install_requirements():
    """Установка зависимостей из requirements.txt"""
    try:
        print("📦 Установка зависимостей...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Зависимости установлены успешно!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при установке зависимостей: {e}")
        return False
    return True

def check_ffmpeg():
    """Проверка наличия FFmpeg в системе"""
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✅ FFmpeg найден в системе")
        return True
    except FileNotFoundError:
        print("❌ FFmpeg не найден в системе")
        print("Установите FFmpeg:")
        print("  macOS: brew install ffmpeg")
        print("  Ubuntu/Debian: sudo apt install ffmpeg")
        print("  Windows: https://ffmpeg.org/download.html")
        return False

def create_env_example():
    """Создание примера файла с переменными окружения"""
    env_content = """# Скопируйте этот файл в .env и заполните своими данными

# Токен Telegram бота (получить у @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Папка для временных файлов (необязательно)
DOWNLOAD_DIR=./downloads
"""
    
    if not os.path.exists(".env.example"):
        with open(".env.example", "w", encoding="utf-8") as f:
            f.write(env_content)
        print("✅ Создан файл .env.example")

def main():
    print("🚀 Настройка YouTube Downloader Bot")
    print("=" * 40)
    
    # Проверка Python версии
    if sys.version_info < (3, 8):
        print("❌ Требуется Python 3.8 или выше")
        sys.exit(1)
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Установка зависимостей
    if not install_requirements():
        sys.exit(1)
    
    # Проверка FFmpeg
    if not check_ffmpeg():
        print("\n⚠️  Бот может работать без FFmpeg, но конвертация в MP3 будет недоступна")
    
    # Создание примера .env
    create_env_example()
    
    print("\n" + "=" * 40)
    print("✅ Установка завершена!")
    print("\nСледующие шаги:")
    print("1. Создайте бота у @BotFather в Telegram")
    print("2. Скопируйте .env.example в .env")
    print("3. Добавьте токен бота в .env файл")
    print("4. Запустите: python telegram_bot.py")
    print("\nДля тестирования локального скрипта:")
    print("python downloader.py")

if __name__ == "__main__":
    main()