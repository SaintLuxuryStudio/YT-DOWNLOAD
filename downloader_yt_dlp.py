import os
import logging
import yt_dlp
import ffmpeg
from typing import Optional, Tuple, List

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('downloader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class YouTubeDownloader:
    def __init__(self, download_dir: str = "./downloads"):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
        
        self.ydl_opts = {
            'outtmpl': f'{download_dir}/%(title)s.%(ext)s',
            'format': 'best',  # Будем задавать конкретный формат в download_video
            'noplaylist': True,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'merge_output_format': 'mp4',  # Объединяем в mp4
        }
    
    def get_video_info(self, url: str) -> Optional[dict]:
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                logger.info(f"Video found: {info.get('title', 'Unknown')}")
                return info
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None
    
    def get_available_resolutions(self, info: dict) -> List[str]:
        try:
            formats = info.get('formats', [])
            resolutions = set()
            
            # Логируем все форматы для отладки
            logger.info("Available formats:")
            for f in formats:
                logger.info(f"Format ID: {f.get('format_id')}, Height: {f.get('height')}, "
                           f"VCodec: {f.get('vcodec')}, Extension: {f.get('ext')}")
                
                if f.get('height') and f.get('vcodec') != 'none' and f.get('ext') in ['mp4', 'webm']:
                    resolutions.add(f"{f['height']}p")
            
            # Если нет видео форматов, добавляем стандартные опции
            if not resolutions:
                logger.warning("No video formats found, using fallback")
                return ['audio']  # Только аудио
            
            # Сортируем по качеству
            sorted_resolutions = sorted(resolutions, 
                                      key=lambda x: int(x.replace('p', '')), 
                                      reverse=True)
            
            # Добавляем опцию "audio"
            result = sorted_resolutions[:5] + ['audio']
            logger.info(f"Available resolutions: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting resolutions: {e}")
            return ['audio']  # Fallback только к аудио
    
    def check_file_size(self, info: dict, format_id: str = None) -> bool:
        try:
            max_size = 1.9 * 1024 * 1024 * 1024  # 1.9 GB in bytes
            
            if format_id:
                for f in info.get('formats', []):
                    if f.get('format_id') == format_id:
                        filesize = f.get('filesize') or f.get('filesize_approx', 0)
                        if filesize > max_size:
                            logger.warning(f"File size {filesize / (1024**3):.2f}GB exceeds 1.9GB limit")
                            return False
                        return True
            
            # Проверяем общий размер
            filesize = info.get('filesize') or info.get('filesize_approx', 0)
            if filesize and filesize > max_size:
                logger.warning(f"File size {filesize / (1024**3):.2f}GB exceeds 1.9GB limit")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Error checking file size: {e}")
            return True  # Разрешаем загрузку если не можем проверить
    
    def download_video(self, url: str, resolution: str = None, 
                      progress_callback=None) -> Optional[Tuple[str, str]]:
        try:
            info = self.get_video_info(url)
            if not info:
                return None
            
            title = info.get('title', 'video')
            
            # Полностью переработанная логика выбора формата
            opts = self.ydl_opts.copy()
            
            if resolution == 'audio':
                # Для аудио - просто скачиваем аудио и конвертируем отдельно
                opts['format'] = 'bestaudio[ext=m4a]/bestaudio/best'
                # Убираем автоматическую конвертацию, сделаем это вручную
                logger.info("Using audio format: bestaudio")
                
            elif resolution and resolution != 'audio':
                # Для видео - простая логика выбора качества
                height = resolution.replace("p", "")
                
                # Сначала получаем все доступные форматы
                with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                    try:
                        formats_info = ydl.extract_info(url, download=False)
                        available_formats = formats_info.get('formats', [])
                        
                        # Ищем подходящий формат
                        best_format = None
                        target_height = int(height)
                        
                        # Ищем комбинированные форматы (с видео и аудио)
                        combined_formats = [f for f in available_formats 
                                          if f.get('vcodec') != 'none' and f.get('acodec') != 'none' 
                                          and f.get('height')]
                        
                        # Ищем отдельные видео форматы
                        video_only_formats = [f for f in available_formats 
                                            if f.get('vcodec') != 'none' and f.get('acodec') == 'none' 
                                            and f.get('height')]
                        
                        # Ищем аудио форматы
                        audio_formats = [f for f in available_formats 
                                       if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
                        
                        # Сначала пробуем найти комбинированный формат
                        if combined_formats:
                            suitable_formats = [f for f in combined_formats 
                                              if f.get('height', 0) <= target_height]
                            
                            if suitable_formats:
                                best_format = max(suitable_formats, 
                                                key=lambda x: x.get('height', 0))
                                opts['format'] = best_format['format_id']
                                logger.info(f"Selected combined format: {best_format['format_id']} "
                                          f"({best_format.get('height')}p)")
                            else:
                                # Берем самый низкий комбинированный
                                best_format = min(combined_formats, 
                                                key=lambda x: x.get('height', 999999))
                                opts['format'] = best_format['format_id']
                                logger.info(f"Fallback to lowest combined format: {best_format['format_id']} "
                                          f"({best_format.get('height')}p)")
                        
                        # Если нет комбинированных, объединяем видео + аудио
                        elif video_only_formats and audio_formats:
                            suitable_video = [f for f in video_only_formats 
                                            if f.get('height', 0) <= target_height]
                            
                            if suitable_video:
                                best_video = max(suitable_video, 
                                               key=lambda x: x.get('height', 0))
                            else:
                                best_video = min(video_only_formats, 
                                               key=lambda x: x.get('height', 999999))
                            
                            # Берем лучший аудио формат
                            best_audio = max(audio_formats, 
                                           key=lambda x: x.get('abr', 0) or 0)
                            
                            opts['format'] = f"{best_video['format_id']}+{best_audio['format_id']}"
                            logger.info(f"Selected video+audio: {best_video['format_id']} "
                                      f"({best_video.get('height')}p) + {best_audio['format_id']}")
                        
                        else:
                            opts['format'] = 'best'
                            logger.info("No suitable formats found, using 'best'")
                            
                    except Exception as e:
                        logger.error(f"Error selecting format: {e}")
                        opts['format'] = 'best'
                        logger.info("Using fallback format: best")
            else:
                # Просто лучшее качество
                opts['format'] = 'best'
                logger.info("Using format: best")
            
            if progress_callback:
                opts['progress_hooks'] = [self._wrap_progress_callback(progress_callback)]
            
            # Проверяем размер файла
            if not self.check_file_size(info):
                logger.error("File too large")
                return None
            
            logger.info(f"Starting download: {title}")
            
            # Убираем simulate для реального скачивания
            opts.pop('simulate', None)
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            
            # Находим скачанный файл
            video_path = self._find_downloaded_file(title)
            if video_path:
                logger.info(f"Download completed: {video_path}")
                return video_path, title
            else:
                logger.error("Downloaded file not found")
                return None
            
        except Exception as e:
            logger.error(f"Error downloading video: {e}")
            return None
    
    def _wrap_progress_callback(self, callback):
        def progress_hook(d):
            try:
                if d['status'] == 'downloading':
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    
                    if total > 0:
                        # Создаем фейковый stream объект
                        class FakeStream:
                            def __init__(self, filesize):
                                self.filesize = filesize
                        
                        fake_stream = FakeStream(total)
                        bytes_remaining = total - downloaded
                        
                        # Вызываем оригинальный callback
                        callback(fake_stream, None, bytes_remaining)
                        
                elif d['status'] == 'finished':
                    # 100% когда закончили
                    class FakeStream:
                        def __init__(self, filesize):
                            self.filesize = filesize
                    
                    total = d.get('total_bytes', 0) or 1000000  # fallback
                    fake_stream = FakeStream(total)
                    callback(fake_stream, None, 0)  # 0 bytes remaining = 100%
                    
            except Exception as e:
                logger.error(f"Progress callback error: {e}")
        
        return progress_hook
    
    def _find_downloaded_file(self, title: str) -> Optional[str]:
        try:
            # Ищем файлы с медиа расширениями
            media_extensions = ['.mp4', '.mkv', '.webm', '.avi', '.mp3', '.m4a', '.opus', '.aac']
            
            # Сначала ищем по имени
            clean_title = title.replace('/', '_').replace('"', '').replace("'", '')[:50]
            
            for file in os.listdir(self.download_dir):
                file_path = os.path.join(self.download_dir, file)
                
                # Проверяем по имени файла и расширению
                if any(file.endswith(ext) for ext in media_extensions):
                    if clean_title[:20] in file:
                        logger.info(f"Found file by name: {file_path}")
                        return file_path
            
            # Если не нашли по имени, ищем последний созданный медиа файл
            media_files = []
            for file in os.listdir(self.download_dir):
                if any(file.endswith(ext) for ext in media_extensions):
                    media_files.append(os.path.join(self.download_dir, file))
            
            if media_files:
                latest_file = max(media_files, key=os.path.getctime)
                logger.info(f"Found latest file: {latest_file}")
                return latest_file
                
        except Exception as e:
            logger.error(f"Error finding downloaded file: {e}")
        
        return None
    
    def convert_to_mp3(self, video_path: str) -> Optional[str]:
        try:
            audio_path = video_path.rsplit('.', 1)[0] + '.mp3'
            
            logger.info(f"Converting to MP3: {video_path}")
            (
                ffmpeg
                .input(video_path)
                .output(audio_path, acodec='mp3', audio_bitrate='192k')
                .overwrite_output()
                .run(quiet=True)
            )
            
            logger.info(f"Conversion completed: {audio_path}")
            return audio_path
            
        except Exception as e:
            logger.error(f"Error converting to MP3: {e}")
            return None
    
    def cleanup_file(self, file_path: str):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"File deleted: {file_path}")
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")

if __name__ == "__main__":
    downloader = YouTubeDownloader()
    
    url = input("Enter YouTube URL: ")
    info = downloader.get_video_info(url)
    
    if info:
        resolutions = downloader.get_available_resolutions(info)
        print(f"\nAvailable resolutions: {resolutions}")
        
        choice = input("Enter desired resolution (or press Enter for best): ").strip()
        resolution = choice if choice in resolutions else None
        
        result = downloader.download_video(url, resolution)
        
        if result:
            video_path, title = result
            print(f"\nDownloaded: {title}")
            
            convert = input("Convert to MP3? (y/n): ").lower().strip() == 'y'
            if convert:
                audio_path = downloader.convert_to_mp3(video_path)
                if audio_path:
                    print(f"Audio saved: {audio_path}")