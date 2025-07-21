import os
import logging
import ffmpeg
from pytubefix import YouTube
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
    
    def get_video_info(self, url: str) -> Optional[dict]:
        try:
            yt = YouTube(url)
            info = {
                'title': yt.title,
                'duration': yt.length,
                'view_count': yt.views,
                'streams': yt.streams
            }
            logger.info(f"Video found: {info.get('title', 'Unknown')}")
            return info
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return None
    
    def get_available_resolutions(self, info: dict) -> List[str]:
        try:
            streams = info.get('streams')
            if not streams:
                return ['audio']
            
            # Получаем видео разрешения
            video_streams = streams.filter(progressive=True).order_by('resolution')
            resolutions = set()
            
            for stream in video_streams:
                if stream.resolution:
                    resolutions.add(stream.resolution)
            
            # Также проверяем адаптивные потоки
            adaptive_video = streams.filter(adaptive=True, only_video=True).order_by('resolution')
            for stream in adaptive_video:
                if stream.resolution:
                    resolutions.add(stream.resolution)
            
            # Сортируем по качеству
            resolution_order = ['144p', '240p', '360p', '480p', '720p', '1080p', '1440p', '2160p']
            sorted_resolutions = [res for res in resolution_order if res in resolutions]
            
            # Добавляем аудио опцию
            result = sorted_resolutions + ['audio']
            logger.info(f"Available resolutions: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting resolutions: {e}")
            return ['audio']
    
    def check_file_size(self, stream, max_size_gb: float = 1.9) -> bool:
        try:
            if hasattr(stream, 'filesize') and stream.filesize:
                max_size = max_size_gb * 1024 * 1024 * 1024  # Convert to bytes
                if stream.filesize > max_size:
                    logger.warning(f"File size {stream.filesize / (1024**3):.2f}GB exceeds {max_size_gb}GB limit")
                    return False
            return True
        except Exception as e:
            logger.error(f"Error checking file size: {e}")
            return True
    
    def download_video(self, url: str, resolution: str = None, 
                      progress_callback=None) -> Optional[Tuple[str, str]]:
        try:
            yt = YouTube(url, on_progress_callback=progress_callback)
            title = yt.title
            
            logger.info(f"Starting download: {title}")
            
            if resolution == 'audio':
                # Скачиваем аудио
                stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
                if not stream:
                    logger.error("No audio stream found")
                    return None
                    
                if not self.check_file_size(stream):
                    return None
                    
                file_path = stream.download(output_path=self.download_dir)
                logger.info(f"Audio download completed: {file_path}")
                return file_path, title
                
            elif resolution:
                # Скачиваем видео определенного качества
                # Сначала пробуем прогрессивный поток (видео+аудио)
                progressive_stream = yt.streams.filter(progressive=True, res=resolution).first()
                
                if progressive_stream:
                    if not self.check_file_size(progressive_stream):
                        return None
                        
                    file_path = progressive_stream.download(output_path=self.download_dir)
                    logger.info(f"Progressive video download completed: {file_path}")
                    return file_path, title
                
                # Если нет прогрессивного, пробуем ближайшее качество
                all_progressive = yt.streams.filter(progressive=True).order_by('resolution').desc()
                target_height = int(resolution.replace('p', ''))
                
                for stream in all_progressive:
                    if stream.resolution:
                        stream_height = int(stream.resolution.replace('p', ''))
                        if stream_height <= target_height:
                            if self.check_file_size(stream):
                                file_path = stream.download(output_path=self.download_dir)
                                logger.info(f"Best available progressive video ({stream.resolution}) download completed: {file_path}")
                                return file_path, title
                
                # В крайнем случае пробуем адаптивные потоки
                video_stream = yt.streams.filter(adaptive=True, res=resolution, only_video=True).first()
                audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
                
                if video_stream and audio_stream:
                    if not self.check_file_size(video_stream) or not self.check_file_size(audio_stream):
                        return None
                        
                    try:
                        # Скачиваем видео и аудио отдельно
                        video_path = video_stream.download(output_path=self.download_dir, filename_prefix='video_')
                        audio_path = audio_stream.download(output_path=self.download_dir, filename_prefix='audio_')
                        
                        # Объединяем с помощью ffmpeg
                        output_path = os.path.join(self.download_dir, f"{self._clean_filename(title)}.mp4")
                        self._merge_video_audio(video_path, audio_path, output_path)
                        
                        # Удаляем временные файлы
                        self.cleanup_file(video_path)
                        self.cleanup_file(audio_path)
                        
                        logger.info(f"Merged video download completed: {output_path}")
                        return output_path, title
                    except Exception as merge_error:
                        logger.error(f"Merge failed: {merge_error}")
                        # Возвращаем только видео если merge не удался
                        logger.info(f"Returning video-only file: {video_path}")
                        return video_path, title
                else:
                    logger.error(f"No streams found for resolution {resolution}")
                    return None
            else:
                # Скачиваем лучшее качество
                stream = yt.streams.get_highest_resolution()
                if not stream:
                    logger.error("No streams found")
                    return None
                    
                if not self.check_file_size(stream):
                    return None
                    
                file_path = stream.download(output_path=self.download_dir)
                logger.info(f"Best quality download completed: {file_path}")
                return file_path, title
                
        except Exception as e:
            logger.error(f"Error downloading video: {e}")
            return None
    
    def _clean_filename(self, filename: str) -> str:
        """Очищает имя файла от недопустимых символов"""
        import re
        return re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    def _merge_video_audio(self, video_path: str, audio_path: str, output_path: str):
        """Объединяет видео и аудио файлы"""
        try:
            # Проверяем что исходные файлы существуют и не пустые
            if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
                raise Exception(f"Video file is missing or empty: {video_path}")
            if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
                raise Exception(f"Audio file is missing or empty: {audio_path}")
            
            logger.info(f"Merging video ({os.path.getsize(video_path)} bytes) with audio ({os.path.getsize(audio_path)} bytes)")
            
            # Используем более безопасные параметры ffmpeg
            (
                ffmpeg
                .input(video_path)
                .input(audio_path)
                .output(
                    output_path,
                    vcodec='copy',
                    acodec='aac',  # Конвертируем аудио в AAC для совместимости
                    strict='experimental'
                )
                .overwrite_output()
                .run(quiet=False, capture_stdout=True, capture_stderr=True)
            )
            
            # Проверяем что результат не пустой
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                raise Exception(f"Merged file is empty or wasn't created: {output_path}")
                
            logger.info(f"Successfully merged to {output_path} ({os.path.getsize(output_path)} bytes)")
            
        except ffmpeg.Error as e:
            logger.error(f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error merging video and audio: {e}")
            raise
    
    def convert_to_mp3(self, video_path: str) -> Optional[str]:
        try:
            audio_path = video_path.rsplit('.', 1)[0] + '.mp3'
            
            logger.info(f"Converting to MP3: {video_path}")
            (
                ffmpeg
                .input(video_path)
                .output(audio_path, acodec='mp3', audio_bitrate='64k')
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