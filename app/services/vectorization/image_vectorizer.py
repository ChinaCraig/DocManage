"""
图片向量化器
专门处理图片文件的内容提取和向量化
"""

import logging
import os
from typing import List, Dict, Any
from .base_vectorizer import BaseVectorizer
from ..image_recognition_service import ImageRecognitionService

logger = logging.getLogger(__name__)

class ImageVectorizer(BaseVectorizer):
    """图片向量化器"""
    
    def __init__(self):
        """初始化图片向量化器"""
        super().__init__()
        self.file_type = "image"
        self.recognition_service = ImageRecognitionService()
    
    def get_supported_extensions(self) -> List[str]:
        """获取支持的文件扩展名"""
        return ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.svg']
    
    def extract_text(self, file_path: str, recognition_options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        从图片文件提取文本内容和图像信息
        
        Args:
            file_path: 图片文件路径
            recognition_options: 识别选项，包括引擎和语言设置
            
        Returns:
            包含提取结果的字典
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return {
                    'success': False,
                    'error': f'图片文件不存在: {file_path}'
                }
            
            # 检查文件扩展名
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext not in self.get_supported_extensions():
                return {
                    'success': False,
                    'error': f'不支持的图片格式: {file_ext}'
                }
            
            # 设置默认识别选项
            if recognition_options is None:
                recognition_options = {
                    'engine': 'auto',
                    'languages': ['zh', 'en']
                }
            
            # 使用图像识别服务进行内容识别
            recognition_result = self.recognition_service.recognize_image(
                file_path,
                engine=recognition_options.get('engine', 'auto'),
                languages=recognition_options.get('languages', ['zh', 'en'])
            )
            
            if not recognition_result.get('success'):
                return {
                    'success': False,
                    'error': f'图像识别失败: {recognition_result.get("error", "未知错误")}'
                }
            
            # 构建完整的文本内容
            text_content = self._build_comprehensive_content(recognition_result, file_path)
            
            # 获取元数据
            metadata = self._build_metadata(recognition_result, file_path)
            
            # 进行文本分块
            chunks = self.chunk_text(text_content)
            
            return {
                'success': True,
                'text': text_content,
                'metadata': metadata,
                'chunks': chunks,
                'recognition_result': recognition_result,
                'file_type': 'image'
            }
            
        except Exception as e:
            logger.error(f"Image text extraction failed: {e}")
            return {
                'success': False,
                'error': f'图片文本提取失败: {str(e)}'
            }
    
    def _build_comprehensive_content(self, recognition_result: Dict[str, Any], file_path: str) -> str:
        """构建综合的图像内容描述"""
        content_parts = []
        
        # 基本信息
        filename = os.path.basename(file_path)
        image_info = recognition_result.get('image_info', {})
        
        content_parts.append(f"图像文件: {filename}")
        
        # 图像属性
        if image_info:
            format_info = image_info.get('format', '未知')
            size_info = f"{image_info.get('width', 0)}x{image_info.get('height', 0)}"
            file_size = image_info.get('file_size', 0)
            
            content_parts.append(f"图像格式: {format_info}")
            content_parts.append(f"图像尺寸: {size_info}像素")
            content_parts.append(f"文件大小: {self._format_file_size(file_size)}")
        
        # 识别引擎信息
        engine_used = recognition_result.get('engine_used', '未知')
        confidence = recognition_result.get('confidence', 0.0)
        content_parts.append(f"识别引擎: {engine_used}, 置信度: {confidence:.2%}")
        
        # OCR识别的文本内容
        ocr_text = recognition_result.get('text', '').strip()
        if ocr_text:
            content_parts.append("\n=== 识别的文字内容 ===")
            content_parts.append(ocr_text)
        else:
            content_parts.append("\n=== 图像分析 ===")
            content_parts.append("未检测到文字内容，这可能是一个纯图像文件。")
        
        # 文本区域信息
        text_regions = recognition_result.get('text_regions', [])
        if text_regions:
            content_parts.append(f"\n=== 文本区域分析 ===")
            content_parts.append(f"检测到 {len(text_regions)} 个文本区域:")
            
            for i, region in enumerate(text_regions[:10]):  # 最多显示10个区域
                region_text = region.get('text', '').strip()
                confidence = region.get('confidence', 0.0)
                bbox = region.get('bbox', {})
                
                if region_text:
                    content_parts.append(
                        f"区域{i+1}: \"{region_text}\" "
                        f"(置信度: {confidence:.2%}, "
                        f"位置: {bbox.get('x', 0)},{bbox.get('y', 0)})"
                    )
        
        # 增强描述
        enhanced_desc = recognition_result.get('enhanced_description', '')
        if enhanced_desc and enhanced_desc not in '\n'.join(content_parts):
            content_parts.append(f"\n=== 综合描述 ===")
            content_parts.append(enhanced_desc)
        
        # 为检索优化的关键词
        content_parts.append(f"\n=== 检索关键词 ===")
        keywords = self._extract_keywords(filename, ocr_text, image_info)
        content_parts.append(" ".join(keywords))
        
        return '\n'.join(content_parts)
    
    def _build_metadata(self, recognition_result: Dict[str, Any], file_path: str) -> Dict[str, Any]:
        """构建元数据"""
        image_info = recognition_result.get('image_info', {})
        
        metadata = {
            'file_path': file_path,
            'file_size': image_info.get('file_size', os.path.getsize(file_path)),
            'file_type': 'image',
            'format': image_info.get('format', '未知'),
            'width': image_info.get('width', 0),
            'height': image_info.get('height', 0),
            'mode': image_info.get('mode', '未知'),
            'recognition_engine': recognition_result.get('engine_used', '未知'),
            'recognition_confidence': recognition_result.get('confidence', 0.0),
            'text_regions_count': len(recognition_result.get('text_regions', [])),
            'has_text': bool(recognition_result.get('text', '').strip()),
            'ocr_text_length': len(recognition_result.get('text', '')),
        }
        
        # 添加文本区域统计
        text_regions = recognition_result.get('text_regions', [])
        if text_regions:
            confidences = [r.get('confidence', 0.0) for r in text_regions]
            metadata.update({
                'avg_text_confidence': sum(confidences) / len(confidences),
                'max_text_confidence': max(confidences),
                'min_text_confidence': min(confidences)
            })
        
        return metadata
    
    def _extract_keywords(self, filename: str, ocr_text: str, image_info: Dict) -> List[str]:
        """提取用于检索的关键词"""
        keywords = []
        
        # 文件名关键词（去除扩展名和特殊字符）
        base_name = os.path.splitext(filename)[0]
        filename_words = base_name.replace('_', ' ').replace('-', ' ').split()
        keywords.extend([word for word in filename_words if len(word) > 1])
        
        # 图像格式和属性
        if image_info:
            format_name = image_info.get('format', '').lower()
            if format_name:
                keywords.append(format_name)
        
        # OCR文本中的关键词
        if ocr_text:
            # 简单的中英文分词
            import re
            # 提取中文词汇（2个或以上连续汉字）
            chinese_words = re.findall(r'[\u4e00-\u9fff]{2,}', ocr_text)
            keywords.extend(chinese_words)
            
            # 提取英文单词（2个或以上字符）
            english_words = re.findall(r'[a-zA-Z]{2,}', ocr_text)
            keywords.extend(english_words)
            
            # 提取数字和特殊模式（如车牌号、身份证号等）
            numbers = re.findall(r'\d{2,}', ocr_text)
            keywords.extend(numbers)
            
            # 提取可能的车牌号
            license_plates = re.findall(r'[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领][A-Z][A-Z0-9]{5}', ocr_text)
            keywords.extend(license_plates)
        
        # 去重并过滤
        unique_keywords = list(set(keywords))
        return [kw for kw in unique_keywords if len(kw) > 1 and not kw.isspace()]
    
    def _format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f}MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"
    
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        将图片提取的文本进行分块
        
        Args:
            text: 原始文本
            chunk_size: 块大小
            overlap: 重叠大小
            
        Returns:
            文本块列表
        """
        if not text or not text.strip():
            return []
        
        text = text.strip()
        
        # 如果文本长度小于chunk_size，直接返回
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # 如果不是最后一块，尝试在合适的位置断开
            if end < len(text):
                # 优先在段落分隔符处断开
                for delimiter in ['\n\n=== ', '\n=== ', '\n\n', '\n', '。', '. ', '，', ', ']:
                    break_pos = text.rfind(delimiter, start + chunk_size // 2, end)
                    if break_pos > start:
                        end = break_pos + len(delimiter)
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # 计算下一个开始位置（考虑重叠）
            start = max(start + 1, end - overlap)
        
        logger.info(f"Image text split into {len(chunks)} chunks")
        return chunks
    
    def get_recognition_options(self) -> Dict[str, Any]:
        """获取可用的识别选项"""
        return {
            'engines': self.recognition_service.get_available_engines(),
            'languages': self.recognition_service.get_supported_languages(),
            'default_engine': 'auto',
            'default_languages': ['zh', 'en']
        } 