from .base_preview import BasePreviewService
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class VideoPreviewService(BasePreviewService):
    """视频预览服务"""
    
    def __init__(self):
        super().__init__()
        self.supported_formats = ['mp4', 'avi', 'mov', 'wmv', 'mkv', 'flv', 'webm']
    
    def extract_content(self, file_path):
        """提取视频文件信息"""
        if not self.validate_file(file_path):
            raise FileNotFoundError(f"文件不存在或无法读取: {file_path}")
        
        try:
            content_data = {
                'type': 'video',
                'metadata': {}
            }
            
            # 尝试使用cv2获取视频信息
            try:
                import cv2
                video_info = self._extract_video_info_cv2(file_path)
                content_data['metadata'].update(video_info)
            except ImportError:
                logger.warning("OpenCV未安装，无法提取详细视频信息")
                content_data['metadata']['note'] = '需要安装OpenCV以获取详细视频信息'
            except Exception as e:
                logger.warning(f"使用OpenCV提取视频信息失败: {str(e)}")
                # 尝试使用其他方法
                try:
                    video_info = self._extract_video_info_basic(file_path)
                    content_data['metadata'].update(video_info)
                except Exception as e2:
                    logger.error(f"视频信息提取失败: {str(e2)}")
                    content_data['metadata']['error'] = str(e2)
            
            logger.info(f"✅ 视频信息提取成功: {file_path}")
            return content_data
            
        except Exception as e:
            logger.error(f"❌ 视频信息提取失败: {file_path}, 错误: {str(e)}")
            raise
    
    def _extract_video_info_cv2(self, file_path):
        """使用OpenCV提取视频信息"""
        import cv2
        
        video_info = {}
        cap = cv2.VideoCapture(file_path)
        
        if cap.isOpened():
            # 基本信息
            video_info.update({
                'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                'fps': cap.get(cv2.CAP_PROP_FPS),
                'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                'fourcc': int(cap.get(cv2.CAP_PROP_FOURCC))
            })
            
            # 计算时长
            if video_info['fps'] > 0:
                duration_seconds = video_info['frame_count'] / video_info['fps']
                video_info['duration_seconds'] = duration_seconds
                video_info['duration_formatted'] = self._format_duration(duration_seconds)
            
            # 分辨率信息
            video_info['resolution'] = f"{video_info['width']} x {video_info['height']}"
            
            # 计算比特率（近似）
            file_size = self.get_file_size(file_path)
            if video_info.get('duration_seconds', 0) > 0:
                bitrate_bps = (file_size * 8) / video_info['duration_seconds']
                video_info['bitrate_kbps'] = round(bitrate_bps / 1000, 2)
        
        cap.release()
        return video_info
    
    def _extract_video_info_basic(self, file_path):
        """基础视频信息提取"""
        # 这里可以使用其他库如ffmpeg-python等
        # 当前只返回基本文件信息
        return {
            'note': '仅提供基本文件信息，安装OpenCV可获取更多视频详情'
        }
    
    def _format_duration(self, seconds):
        """格式化时长"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
    
    def get_metadata(self, file_path):
        """获取视频元数据"""
        if not self.validate_file(file_path):
            raise FileNotFoundError(f"文件不存在或无法读取: {file_path}")
        
        try:
            metadata = {
                'file_size': self.get_file_size(file_path),
                'file_size_formatted': self.format_file_size(self.get_file_size(file_path)),
                'file_type': 'Video',
                'last_modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
            }
            
            # 获取视频详细信息
            try:
                content_data = self.extract_content(file_path)
                if 'metadata' in content_data:
                    metadata.update(content_data['metadata'])
                    
            except Exception as e:
                logger.warning(f"无法获取视频详细信息: {file_path}, 错误: {str(e)}")
                metadata['error'] = str(e)
            
            return metadata
            
        except Exception as e:
            logger.error(f"获取视频元数据失败: {file_path}, 错误: {str(e)}")
            return {
                'file_size': self.get_file_size(file_path),
                'file_size_formatted': self.format_file_size(self.get_file_size(file_path)),
                'file_type': 'Video',
                'last_modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
                'error': str(e)
            }
    
    def generate_thumbnail(self, file_path, output_path=None, size=(200, 200)):
        """生成视频缩略图"""
        if not self.validate_file(file_path):
            return None
        
        try:
            import cv2
            from PIL import Image
            
            # 生成输出路径
            if output_path is None:
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                output_dir = os.path.join(os.path.dirname(file_path), 'thumbnails')
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, f"{base_name}_thumb.jpg")
            
            # 打开视频文件
            cap = cv2.VideoCapture(file_path)
            
            if cap.isOpened():
                # 获取视频总帧数
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                
                # 跳到视频中间位置
                middle_frame = total_frames // 2
                cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame)
                
                # 读取帧
                ret, frame = cap.read()
                
                if ret:
                    # 转换颜色空间（BGR到RGB）
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # 转换为PIL图像
                    img = Image.fromarray(frame_rgb)
                    
                    # 调整尺寸
                    img.thumbnail(size, Image.Resampling.LANCZOS)
                    
                    # 保存缩略图
                    img.save(output_path, "JPEG", quality=85, optimize=True)
                    
                    cap.release()
                    logger.info(f"✅ 视频缩略图生成成功: {output_path}")
                    return output_path
            
            cap.release()
            
        except ImportError:
            logger.warning(f"OpenCV未安装，无法生成视频缩略图: {file_path}")
        except Exception as e:
            logger.error(f"❌ 视频缩略图生成失败: {file_path}, 错误: {str(e)}")
        
        return None 