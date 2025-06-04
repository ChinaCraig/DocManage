from .base_preview import BasePreviewService
import os
import logging
from datetime import datetime
from PIL import Image, ExifTags
import json

logger = logging.getLogger(__name__)

class ImagePreviewService(BasePreviewService):
    """图片预览服务"""
    
    def __init__(self):
        super().__init__()
        self.supported_formats = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp']
    
    def extract_content(self, file_path):
        """提取图片文件信息"""
        if not self.validate_file(file_path):
            raise FileNotFoundError(f"文件不存在或无法读取: {file_path}")
        
        try:
            content_data = {
                'type': 'image',
                'metadata': {}
            }
            
            # 使用PIL获取图片信息
            with Image.open(file_path) as img:
                content_data['metadata'] = {
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode,
                    'has_transparency': img.mode in ('RGBA', 'LA') or 'transparency' in img.info
                }
                
                # 获取EXIF数据（如果是JPEG）
                if hasattr(img, '_getexif') and img._getexif() is not None:
                    exif_data = self._extract_exif_data(img)
                    if exif_data:
                        content_data['metadata']['exif'] = exif_data
            
            logger.info(f"✅ 图片信息提取成功: {file_path}")
            return content_data
            
        except Exception as e:
            logger.error(f"❌ 图片信息提取失败: {file_path}, 错误: {str(e)}")
            raise
    
    def _extract_exif_data(self, img):
        """提取EXIF数据"""
        try:
            exif_dict = {}
            if hasattr(img, '_getexif'):
                exif = img._getexif()
                if exif is not None:
                    for tag_id, value in exif.items():
                        tag_name = ExifTags.TAGS.get(tag_id, tag_id)
                        try:
                            # 确保值可以序列化为JSON
                            if isinstance(value, (int, float, str, bool)):
                                exif_dict[tag_name] = value
                            else:
                                exif_dict[tag_name] = str(value)
                        except:
                            # 跳过无法处理的值
                            continue
            
            return exif_dict
            
        except Exception as e:
            logger.warning(f"EXIF数据提取失败: {str(e)}")
            return {}
    
    def get_metadata(self, file_path):
        """获取图片元数据"""
        if not self.validate_file(file_path):
            raise FileNotFoundError(f"文件不存在或无法读取: {file_path}")
        
        try:
            metadata = {
                'file_size': self.get_file_size(file_path),
                'file_size_formatted': self.format_file_size(self.get_file_size(file_path)),
                'file_type': 'Image',
                'last_modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
            }
            
            # 获取图片详细信息
            try:
                with Image.open(file_path) as img:
                    metadata.update({
                        'width': img.width,
                        'height': img.height,
                        'resolution': f"{img.width} x {img.height}",
                        'format': img.format,
                        'mode': img.mode,
                        'color_mode': self._get_color_mode_description(img.mode),
                        'has_transparency': img.mode in ('RGBA', 'LA') or 'transparency' in img.info
                    })
                    
                    # 计算图片比例
                    if img.height > 0:
                        metadata['aspect_ratio'] = round(img.width / img.height, 2)
                    
                    # 获取DPI信息
                    if hasattr(img, 'info') and 'dpi' in img.info:
                        metadata['dpi'] = img.info['dpi']
                    
                    # 获取EXIF数据
                    if hasattr(img, '_getexif') and img._getexif() is not None:
                        exif_data = self._extract_exif_data(img)
                        if exif_data:
                            metadata['exif'] = exif_data
                            
                            # 提取常用EXIF信息到顶层
                            if 'DateTime' in exif_data:
                                metadata['photo_date'] = exif_data['DateTime']
                            if 'Make' in exif_data:
                                metadata['camera_make'] = exif_data['Make']
                            if 'Model' in exif_data:
                                metadata['camera_model'] = exif_data['Model']
                
            except Exception as e:
                logger.warning(f"无法获取图片详细信息: {file_path}, 错误: {str(e)}")
                metadata['error'] = str(e)
            
            return metadata
            
        except Exception as e:
            logger.error(f"获取图片元数据失败: {file_path}, 错误: {str(e)}")
            return {
                'file_size': self.get_file_size(file_path),
                'file_size_formatted': self.format_file_size(self.get_file_size(file_path)),
                'file_type': 'Image',
                'last_modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
                'error': str(e)
            }
    
    def _get_color_mode_description(self, mode):
        """获取颜色模式描述"""
        mode_descriptions = {
            '1': '1位黑白',
            'L': '8位灰度',
            'P': '8位调色板',
            'RGB': '24位真彩色',
            'RGBA': '32位真彩色（含透明度）',
            'CMYK': 'CMYK颜色模式',
            'YCbCr': 'YCbCr颜色模式',
            'LAB': 'LAB颜色模式',
            'HSV': 'HSV颜色模式'
        }
        return mode_descriptions.get(mode, mode)
    
    def generate_thumbnail(self, file_path, output_path=None, size=(200, 200)):
        """生成图片缩略图"""
        if not self.validate_file(file_path):
            return None
        
        try:
            # 生成输出路径
            if output_path is None:
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                output_dir = os.path.join(os.path.dirname(file_path), 'thumbnails')
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, f"{base_name}_thumb.jpg")
            
            # 生成缩略图
            with Image.open(file_path) as img:
                # 转换为RGB模式（如果需要）
                if img.mode in ('RGBA', 'LA'):
                    # 创建白色背景
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'RGBA':
                        background.paste(img, mask=img.split()[-1])  # 使用alpha通道作为mask
                    else:
                        background.paste(img)
                    img = background
                elif img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                
                # 创建缩略图
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                # 保存缩略图
                img.save(output_path, "JPEG", quality=85, optimize=True)
                
                logger.info(f"✅ 图片缩略图生成成功: {output_path}")
                return output_path
            
        except Exception as e:
            logger.error(f"❌ 图片缩略图生成失败: {file_path}, 错误: {str(e)}")
            return None 