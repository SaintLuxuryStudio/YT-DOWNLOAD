import os
import re
import logging
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from downloader_pytubefix import YouTubeDownloader

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TelegramYTBot:
    def __init__(self, token: str):
        self.token = token
        self.downloader = YouTubeDownloader()
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await update.message.reply_html(
            f"Привет, {user.mention_html()}!\n"
            f"Отправь мне ссылку на YouTube видео, и я скачаю его для тебя.\n"
            f"Можешь выбрать формат: видео (MP4) или аудио (MP3)."
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
Как пользоваться ботом:

1. Отправь ссылку на YouTube видео
2. Выбери качество из предложенных вариантов
3. Выбери формат: видео или аудио
4. Дождись загрузки и получи файл

Поддерживаемые форматы:
• MP4 для видео
• MP3 для аудио

Ограничения:
• Максимальный размер файла: 1.9 ГБ
        """
        await update.message.reply_text(help_text)
    
    def is_youtube_url(self, text: str) -> bool:
        youtube_regex = re.compile(
            r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
            r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
        )
        return bool(youtube_regex.match(text))
    
    def create_progress_callback(self, query, context):
        progress_data = {'query': query, 'context': context, 'current_progress': 0}
        last_pct = [0]
        
        def progress_callback(stream, chunk, bytes_remaining):
            try:
                total = stream.filesize
                done = total - bytes_remaining
                pct = int(done / total * 100)
                
                # Обновляем каждые 5%
                if pct >= last_pct[0] + 5:
                    progress_data['current_progress'] = pct
                    last_pct[0] = pct
                    logger.info(f"Progress: {pct}%")
            except Exception as e:
                logger.error(f"Progress callback error: {e}")
        
        progress_callback.progress_data = progress_data
        return progress_callback
    
    def split_large_file(self, file_path: str, max_size: int = 50 * 1024 * 1024) -> list:
        """Разбивает большой файл на части"""
        try:
            file_size = os.path.getsize(file_path)
            if file_size <= max_size:
                return [file_path]
            
            part_files = []
            with open(file_path, 'rb') as f:
                part_num = 1
                while True:
                    chunk = f.read(max_size)
                    if not chunk:
                        break
                    
                    part_path = f"{file_path}.part{part_num:03d}"
                    with open(part_path, 'wb') as part_file:
                        part_file.write(chunk)
                    
                    part_files.append(part_path)
                    part_num += 1
            
            return part_files
        except Exception as e:
            logger.error(f"Error splitting file: {e}")
            return [file_path]
    
    async def update_progress_periodically(self, progress_callback, query):
        """Периодически обновляет прогресс в сообщении"""
        last_shown_progress = 0
        
        while True:
            try:
                await asyncio.sleep(1)  # Проверяем каждую секунду
                
                current_progress = progress_callback.progress_data.get('current_progress', 0)
                
                # Показываем изменения прогресса каждые 5%
                if current_progress >= last_shown_progress + 5:
                    await query.edit_message_text(f"⏬ Скачивание: {current_progress}%")
                    last_shown_progress = current_progress
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in progress update: {e}")
                break
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message_text = update.message.text
        
        if not self.is_youtube_url(message_text):
            await update.message.reply_text(
                "❌ Пожалуйста, отправь корректную ссылку на YouTube видео."
            )
            return
        
        await self.process_youtube_url(update, context, message_text)
    
    async def process_youtube_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
        try:
            status_message = await update.message.reply_text("🔍 Получаю информацию о видео...")
            
            # Запускаем в отдельном потоке, так как yt-dlp синхронный
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, self.downloader.get_video_info, url)
            
            if not info:
                await status_message.edit_text("❌ Не удалось получить информацию о видео.")
                return
            
            resolutions = await loop.run_in_executor(None, self.downloader.get_available_resolutions, info)
            if not resolutions:
                await status_message.edit_text("❌ Не найдено доступных форматов для скачивания.")
                return
            
            title = info.get('title', 'Unknown')
            duration = info.get('duration', 0)
            view_count = info.get('view_count', 0)
            
            # Создаем клавиатуру с кнопками
            keyboard = []
            
            # Добавляем кнопки для видео качества
            video_resolutions = [res for res in resolutions if res != 'audio']
            for i in range(0, len(video_resolutions), 2):
                row = []
                for j in range(2):
                    if i + j < len(video_resolutions):
                        res = video_resolutions[i + j]
                        row.append(InlineKeyboardButton(f"📹 {res}", callback_data=f"video_{res}"))
                keyboard.append(row)
            
            # Добавляем кнопку для аудио
            keyboard.append([InlineKeyboardButton("🎵 MP3 Audio", callback_data="audio")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await status_message.edit_text(
                f"📹 Видео: {title}\n"
                f"⏱️ Длительность: {duration // 60}:{duration % 60:02d}\n"
                f"👁️ Просмотры: {view_count:,}\n\n"
                f"Выберите формат для скачивания:",
                reply_markup=reply_markup
            )
            
            context.user_data['video_info'] = {
                'url': url,
                'info': info,
                'resolutions': resolutions,
                'status_message': status_message
            }
            
        except Exception as e:
            logger.error(f"Error processing URL: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке ссылки.")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        video_info = context.user_data.get('video_info')
        if not video_info:
            await query.edit_message_text("❌ Сессия истекла. Отправьте ссылку заново.")
            return
        
        callback_data = query.data
        
        if callback_data == "audio":
            await self.download_and_send_callback(query, context, resolution="audio", audio_only=True)
        elif callback_data.startswith("video_"):
            resolution = callback_data.replace("video_", "")
            await self.download_and_send_callback(query, context, resolution=resolution)
    
    async def download_and_send_callback(self, query, context: ContextTypes.DEFAULT_TYPE, 
                                        resolution: str = None, audio_only: bool = False):
        try:
            video_info = context.user_data.get('video_info')
            if not video_info:
                await query.edit_message_text("❌ Сначала отправь ссылку на видео.")
                return
            
            await query.edit_message_text("⏬ Начинаю скачивание...")
            
            progress_callback = self.create_progress_callback(query, context)
            
            # Запускаем периодическое обновление прогресса
            progress_task = asyncio.create_task(self.update_progress_periodically(progress_callback, query))
            
            # Запускаем скачивание в отдельном потоке
            loop = asyncio.get_event_loop()
            try:
                result = await loop.run_in_executor(
                    None, 
                    self.downloader.download_video,
                    video_info['url'], 
                    resolution,
                    progress_callback
                )
            finally:
                # Останавливаем задачу обновления прогресса
                progress_task.cancel()
                try:
                    await progress_task
                except asyncio.CancelledError:
                    pass
            
            if not result:
                await query.edit_message_text("❌ Ошибка при скачивании видео.")
                return
            
            video_path, title = result
            
            if audio_only:
                # Проверяем, уже ли это MP3 файл
                if video_path.endswith('.mp3'):
                    audio_path = video_path
                    await query.edit_message_text("📤 Отправляю аудио...")
                else:
                    await query.edit_message_text("🎵 Конвертирую в MP3...")
                    audio_path = await loop.run_in_executor(None, self.downloader.convert_to_mp3, video_path)
                
                if audio_path:
                    # Проверяем размер файла
                    file_size = os.path.getsize(audio_path)
                    max_size = 50 * 1024 * 1024  # 50 MB лимит для аудио в Telegram
                    
                    if file_size > max_size:
                        size_mb = file_size / (1024 * 1024)
                        await query.edit_message_text(
                            f"❌ Аудио файл слишком большой ({size_mb:.1f} MB).\n"
                            f"Максимальный размер для аудио: 50 MB.\n"
                            f"Попробуйте выбрать видео вместо аудио."
                        )
                        self.downloader.cleanup_file(video_path)
                        if audio_path != video_path:
                            self.downloader.cleanup_file(audio_path)
                        return
                    
                    if not video_path.endswith('.mp3'):
                        await query.edit_message_text("📤 Отправляю аудио...")
                    
                    with open(audio_path, 'rb') as audio_file:
                        await context.bot.send_audio(
                            chat_id=query.message.chat_id,
                            audio=audio_file,
                            title=title[:50],
                            caption=f"🎵 {title}",
                            read_timeout=300,
                            write_timeout=300,
                            connect_timeout=60,
                            pool_timeout=60
                        )
                    
                    self.downloader.cleanup_file(video_path)
                    if audio_path != video_path:
                        self.downloader.cleanup_file(audio_path)
                    await query.edit_message_text("✅ Аудио отправлено!")
                else:
                    await query.edit_message_text("❌ Ошибка при конвертации в MP3.")
            else:
                # Проверяем размер видео файла
                file_size = os.path.getsize(video_path)
                size_mb = file_size / (1024 * 1024)
                
                # Более строгий лимит для надежной отправки
                max_size = 50 * 1024 * 1024  # 50 MB лимит для надежной отправки
                
                if file_size > max_size:
                    # Предлагаем разбить файл на части
                    await query.edit_message_text(
                        f"📁 Видео файл большой ({size_mb:.1f} MB).\n"
                        f"Разбиваю на части для отправки..."
                    )
                    
                    part_files = self.split_large_file(video_path)
                    
                    if len(part_files) > 1:
                        await query.edit_message_text(f"📤 Отправляю видео ({len(part_files)} частей)...")
                        
                        for i, part_path in enumerate(part_files, 1):
                            try:
                                with open(part_path, 'rb') as part_file:
                                    await context.bot.send_document(
                                        chat_id=query.message.chat_id,
                                        document=part_file,
                                        caption=f"📹 {title} (часть {i}/{len(part_files)})",
                                        read_timeout=600,
                                        write_timeout=600,
                                        connect_timeout=120,
                                        pool_timeout=120
                                    )
                                # Удаляем часть после отправки
                                os.remove(part_path)
                            except Exception as e:
                                logger.error(f"Error sending part {i}: {e}")
                                await query.edit_message_text(f"❌ Ошибка при отправке части {i}")
                                return
                        
                        await query.edit_message_text(f"✅ Видео отправлено ({len(part_files)} частей)!")
                    else:
                        # Если не удалось разбить, отправляем как обычно
                        await query.edit_message_text("📤 Отправляю видео...")
                        try:
                            with open(video_path, 'rb') as video_file:
                                await context.bot.send_video(
                                    chat_id=query.message.chat_id,
                                    video=video_file,
                                    caption=f"📹 {title}",
                                    supports_streaming=True,
                                    read_timeout=600,
                                    write_timeout=600,
                                    connect_timeout=120,
                                    pool_timeout=120
                                )
                        except Exception as e:
                            logger.error(f"Error sending video: {e}")
                            await query.edit_message_text("❌ Ошибка при отправке видео")
                            return
                    
                    self.downloader.cleanup_file(video_path)
                    return
                
                # Если файл не большой, отправляем как обычно
                await query.edit_message_text("📤 Отправляю видео...")
                
                # Retry логика для отправки видео
                for attempt in range(3):  # 3 попытки
                    try:
                        with open(video_path, 'rb') as video_file:
                            await context.bot.send_video(
                                chat_id=query.message.chat_id,
                                video=video_file,
                                caption=f"📹 {title}",
                                supports_streaming=True,
                                read_timeout=600,  # Увеличиваем таймауты
                                write_timeout=600,
                                connect_timeout=120,
                                pool_timeout=120
                            )
                        break  # Успешно отправили, выходим из цикла
                    except Exception as send_error:
                        logger.error(f"Video send attempt {attempt + 1} failed: {send_error}")
                        if attempt == 2:  # Последняя попытка
                            raise  # Перебрасываем исключение
                        await asyncio.sleep(5)  # Пауза перед повторной попыткой
                
                self.downloader.cleanup_file(video_path)
                await query.edit_message_text("✅ Видео отправлено!")
            
            context.user_data.pop('video_info', None)
            
        except Exception as e:
            logger.error(f"Error in download_and_send_callback: {e}")
            await query.edit_message_text("❌ Произошла ошибка при скачивании.")
    
    async def download_and_send(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                               resolution: str = None, audio_only: bool = False):
        try:
            video_info = context.user_data.get('video_info')
            if not video_info:
                await update.message.reply_text("❌ Сначала отправь ссылку на видео.")
                return
            
            status_message = video_info['status_message']
            await status_message.edit_text("⏬ Начинаю скачивание...")
            
            progress_callback = self.create_progress_callback(status_message)
            
            # Запускаем скачивание в отдельном потоке
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                self.downloader.download_video,
                video_info['url'], 
                resolution,
                progress_callback
            )
            
            if not result:
                await status_message.edit_text("❌ Ошибка при скачивании видео.")
                return
            
            video_path, title = result
            
            if audio_only:
                await status_message.edit_text("🎵 Конвертирую в MP3...")
                audio_path = await loop.run_in_executor(None, self.downloader.convert_to_mp3, video_path)
                
                if audio_path:
                    await status_message.edit_text("📤 Отправляю аудио...")
                    
                    with open(audio_path, 'rb') as audio_file:
                        await context.bot.send_audio(
                            chat_id=update.effective_chat.id,
                            audio=audio_file,
                            title=title[:50],  # Ограничиваем длину названия
                            caption=f"🎵 {title}"
                        )
                    
                    self.downloader.cleanup_file(video_path)
                    self.downloader.cleanup_file(audio_path)
                    await status_message.edit_text("✅ Аудио отправлено!")
                else:
                    await status_message.edit_text("❌ Ошибка при конвертации в MP3.")
            else:
                # Проверяем размер видео файла
                file_size = os.path.getsize(video_path)
                size_mb = file_size / (1024 * 1024)
                
                # Более строгий лимит для надежной отправки
                max_size = 50 * 1024 * 1024  # 50 MB лимит для надежной отправки
                
                if file_size > max_size:
                    # Предлагаем разбить файл на части
                    await status_message.edit_text(
                        f"📁 Видео файл большой ({size_mb:.1f} MB).\n"
                        f"Разбиваю на части для отправки..."
                    )
                    
                    part_files = self.split_large_file(video_path)
                    
                    if len(part_files) > 1:
                        await status_message.edit_text(f"📤 Отправляю видео ({len(part_files)} частей)...")
                        
                        for i, part_path in enumerate(part_files, 1):
                            try:
                                with open(part_path, 'rb') as part_file:
                                    await context.bot.send_document(
                                        chat_id=update.effective_chat.id,
                                        document=part_file,
                                        caption=f"📹 {title} (часть {i}/{len(part_files)})",
                                        read_timeout=600,
                                        write_timeout=600,
                                        connect_timeout=120,
                                        pool_timeout=120
                                    )
                                # Удаляем часть после отправки
                                os.remove(part_path)
                            except Exception as e:
                                logger.error(f"Error sending part {i}: {e}")
                                await status_message.edit_text(f"❌ Ошибка при отправке части {i}")
                                return
                        
                        await status_message.edit_text(f"✅ Видео отправлено ({len(part_files)} частей)!")
                    else:
                        # Если не удалось разбить, отправляем как обычно
                        await status_message.edit_text("📤 Отправляю видео...")
                        try:
                            with open(video_path, 'rb') as video_file:
                                await context.bot.send_video(
                                    chat_id=update.effective_chat.id,
                                    video=video_file,
                                    caption=f"📹 {title}",
                                    supports_streaming=True,
                                    read_timeout=600,
                                    write_timeout=600,
                                    connect_timeout=120,
                                    pool_timeout=120
                                )
                        except Exception as e:
                            logger.error(f"Error sending video: {e}")
                            await status_message.edit_text("❌ Ошибка при отправке видео")
                            return
                    
                    self.downloader.cleanup_file(video_path)
                    return
                
                await status_message.edit_text("📤 Отправляю видео...")
                
                # Retry логика для отправки видео
                for attempt in range(3):  # 3 попытки
                    try:
                        with open(video_path, 'rb') as video_file:
                            await context.bot.send_video(
                                chat_id=update.effective_chat.id,
                                video=video_file,
                                caption=f"📹 {title}",
                                supports_streaming=True,
                                read_timeout=600,  # Увеличиваем таймауты
                                write_timeout=600,
                                connect_timeout=120,
                                pool_timeout=120
                            )
                        break  # Успешно отправили, выходим из цикла
                    except Exception as send_error:
                        logger.error(f"Video send attempt {attempt + 1} failed: {send_error}")
                        if attempt == 2:  # Последняя попытка
                            raise  # Перебрасываем исключение
                        await asyncio.sleep(5)  # Пауза перед повторной попыткой
                
                self.downloader.cleanup_file(video_path)
                await status_message.edit_text("✅ Видео отправлено!")
            
            context.user_data.pop('video_info', None)
            
        except Exception as e:
            logger.error(f"Error in download_and_send: {e}")
            await update.message.reply_text("❌ Произошла ошибка при скачивании.")
    
    def run(self):
        self.application.run_polling()

def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        print("❌ Установите переменную окружения TELEGRAM_BOT_TOKEN")
        print("Создайте бота через @BotFather и получите токен")
        return
    
    bot = TelegramYTBot(token)
    print("🤖 Бот запущен! Нажмите Ctrl+C для остановки.")
    bot.run()

if __name__ == '__main__':
    main()