"""
视频向量化器
专门处理视频文件的内容提取和向量化
"""

import logging
import os
from typing import List, Dict, Any
from .base_vectorizer import BaseVectorizer

logger = logging.getLogger(__name__)

class VideoVectorizer(BaseVectorizer):
    """视频向量化器"""
    
    def __init__(self):
        """初始化视频向量化器"""
        super().__init__()
        self.file_type = "video"
    
    def get_supported_extensions(self) -> List[str]:
        """获取支持的文件扩展名"""
        return ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv', '.m4v']
    
    def extract_text(self, file_path: str) -> Dict[str, Any]:
        """
        从视频文件提取文本内容（字幕、音频转文字等）
        
        Args:
            file_path: 视频文件路径
            
        Returns:
            包含提取结果的字典
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return {
                    'success': False,
                    'error': f'视频文件不存在: {file_path}'
                }
            
            # 检查文件扩展名
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext not in self.get_supported_extensions():
                return {
                    'success': False,
                    'error': f'不支持的视频格式: {file_ext}'
                }
            
            # 获取基本元数据
            metadata = {
                'file_size': os.path.getsize(file_path),
                'file_type': file_ext.replace('.', ''),
                'file_path': file_path
            }
            
            # 尝试提取视频元数据
            self._extract_video_metadata(file_path, metadata)
            
            # 尝试提取字幕
            subtitle_text = self._extract_subtitles(file_path)
            
            # 构建文本内容
            text_content = self._build_text_content(file_path, metadata, subtitle_text)
            
            # 进行文本分块
            chunks = self.chunk_text(text_content)
            
            return {
                'success': True,
                'text': text_content,
                'metadata': metadata,
                'chunks': chunks
            }
            
        except Exception as e:
            logger.error(f"Video text extraction failed: {e}")
            return {
                'success': False,
                'error': f'视频文本提取失败: {str(e)}'
            }
    
    def _extract_video_metadata(self, file_path: str, metadata: Dict) -> None:
        """提取视频元数据"""
        try:
            # 尝试使用opencv-python
            try:
                import cv2
                
                cap = cv2.VideoCapture(file_path)
                
                if cap.isOpened():
                    # 获取视频属性
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    duration = frame_count / fps if fps > 0 else 0
                    
                    metadata.update({
                        'duration_seconds': duration,
                        'fps': fps,
                        'frame_count': frame_count,
                        'width': width,
                        'height': height,
                        'resolution': f"{width}x{height}"
                    })
                    
                cap.release()
                logger.info("Video metadata extracted with OpenCV")
                
            except ImportError:
                logger.warning("OpenCV not available for video metadata extraction")
                # 可以尝试其他库如ffmpeg-python
                pass
                
        except Exception as e:
            logger.warning(f"Video metadata extraction failed: {e}")
    
    def _extract_subtitles(self, file_path: str) -> str:
        """提取视频字幕"""
        try:
            # 首先查找同名字幕文件
            subtitle_text = self._find_subtitle_files(file_path)
            
            if subtitle_text:
                return subtitle_text
            
            # TODO: 实现从视频内嵌字幕的提取
            # 这需要ffmpeg或类似工具
            
            # TODO: 实现音频转文字功能
            # 这需要语音识别库如speech_recognition, whisper等
            
            return ""
            
        except Exception as e:
            logger.warning(f"Subtitle extraction failed: {e}")
            return ""
    
    def _find_subtitle_files(self, video_path: str) -> str:
        """查找同名字幕文件"""
        try:
            video_dir = os.path.dirname(video_path)
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            
            # 常见字幕文件扩展名
            subtitle_extensions = ['.srt', '.ass', '.ssa', '.vtt', '.sub']
            
            for ext in subtitle_extensions:
                subtitle_path = os.path.join(video_dir, video_name + ext)
                if os.path.exists(subtitle_path):
                    try:
                        with open(subtitle_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # 简单解析SRT格式
                        if ext == '.srt':
                            content = self._parse_srt(content)
                        
                        if content.strip():
                            logger.info(f"Found subtitle file: {subtitle_path}")
                            return content
                            
                    except Exception as e:
                        logger.warning(f"Failed to read subtitle file {subtitle_path}: {e}")
                        continue
            
            return ""
            
        except Exception as e:
            logger.warning(f"Subtitle file search failed: {e}")
            return ""
    
    def _parse_srt(self, srt_content: str) -> str:
        """解析SRT字幕格式"""
        try:
            import re
            
            # 移除时间戳，只保留文本
            lines = srt_content.split('\n')
            text_lines = []
            
            for line in lines:
                line = line.strip()
                # 跳过序号行和时间戳行
                if not line or line.isdigit() or '-->' in line:
                    continue
                # 移除HTML标签
                line = re.sub(r'<[^>]+>', '', line)
                if line:
                    text_lines.append(line)
            
            return '\n'.join(text_lines)
            
        except Exception as e:
            logger.warning(f"SRT parsing failed: {e}")
            return srt_content
    
    def _build_text_content(self, file_path: str, metadata: Dict, subtitle_text: str) -> str:
        """构建文本内容"""
        filename = os.path.basename(file_path)
        file_ext = os.path.splitext(file_path)[1]
        
        text_parts = [
            f"视频文件: {filename}",
            f"文件类型: {file_ext}",
            f"文件大小: {metadata.get('file_size', 0)} 字节"
        ]
        
        # 添加视频属性信息
        if 'duration_seconds' in metadata:
            duration = metadata['duration_seconds']
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            text_parts.append(f"视频时长: {minutes}分{seconds}秒")
        
        if 'resolution' in metadata:
            text_parts.append(f"视频分辨率: {metadata['resolution']}")
        
        if 'fps' in metadata:
            text_parts.append(f"帧率: {metadata['fps']:.2f} FPS")
        
        # 添加字幕内容
        if subtitle_text:
            text_parts.append("字幕内容:")
            text_parts.append(subtitle_text)
        else:
            text_parts.append("未找到字幕内容")
        
        return '\n\n'.join(text_parts)
    
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        将视频相关文本进行分块
        
        Args:
            text: 原始文本
            chunk_size: 块大小
            overlap: 重叠大小
            
        Returns:
            文本块列表
        """
        if not text or not text.strip():
            return []
        
        # 清理文本
        text = text.strip()
        
        # 如果文本长度小于chunk_size，直接返回
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        
        # 按段落分割
        paragraphs = text.split('\n\n')
        current_chunk = ""
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # 如果当前段落加上当前块的长度超过chunk_size
            if len(current_chunk) + len(paragraph) > chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    
                    # 处理重叠
                    if overlap > 0 and len(current_chunk) > overlap:
                        overlap_text = current_chunk[-overlap:]
                        current_chunk = overlap_text + "\n\n" + paragraph
                    else:
                        current_chunk = paragraph
                else:
                    # 如果单个段落就超过了chunk_size，需要强制分割
                    if len(paragraph) > chunk_size:
                        sub_chunks = self._split_long_text(paragraph, chunk_size, overlap)
                        chunks.extend(sub_chunks[:-1])
                        current_chunk = sub_chunks[-1] if sub_chunks else ""
                    else:
                        current_chunk = paragraph
            else:
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
        
        # 添加最后一个块
        if current_chunk and current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        # 过滤掉太短的块
        chunks = [chunk for chunk in chunks if len(chunk.strip()) > 20]
        
        logger.info(f"Video text split into {len(chunks)} chunks")
        return chunks
    
    def _split_long_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """分割过长的文本"""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # 如果不是最后一块，尝试在句号或换行符处断开
            if end < len(text):
                for i in range(end, max(start + chunk_size // 2, start + 1), -1):
                    if text[i-1] in '.。\n':
                        end = i
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # 计算下一个开始位置（考虑重叠）
            start = max(start + 1, end - overlap)
        
        return chunks 