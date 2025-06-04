"""
图片向量化器
专门处理图片文件的内容提取和向量化
"""

import logging
import os
from typing import List, Dict, Any
from .base_vectorizer import BaseVectorizer

logger = logging.getLogger(__name__)

class ImageVectorizer(BaseVectorizer):
    """图片向量化器"""
    
    def __init__(self):
        """初始化图片向量化器"""
        super().__init__()
        self.file_type = "image"
    
    def get_supported_extensions(self) -> List[str]:
        """获取支持的文件扩展名"""
        return ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']
    
    def extract_text(self, file_path: str) -> Dict[str, Any]:
        """
        从图片文件提取文本内容（OCR）
        
        Args:
            file_path: 图片文件路径
            
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
            
            # 获取基本元数据
            metadata = {
                'file_size': os.path.getsize(file_path),
                'file_type': file_ext.replace('.', ''),
                'file_path': file_path
            }
            
            # 尝试使用OCR提取文本
            text_content = self._extract_text_with_ocr(file_path, metadata)
            
            if not text_content.strip():
                # 如果没有提取到文本，生成基于文件名的描述
                filename = os.path.basename(file_path)
                text_content = f"图片文件: {filename}\n文件类型: {file_ext}\n这是一个{file_ext}格式的图片文件。"
            
            # 进行文本分块
            chunks = self.chunk_text(text_content)
            
            return {
                'success': True,
                'text': text_content,
                'metadata': metadata,
                'chunks': chunks
            }
            
        except Exception as e:
            logger.error(f"Image text extraction failed: {e}")
            return {
                'success': False,
                'error': f'图片文本提取失败: {str(e)}'
            }
    
    def _extract_text_with_ocr(self, file_path: str, metadata: Dict) -> str:
        """使用OCR从图片中提取文本"""
        try:
            # 尝试使用pytesseract进行OCR
            try:
                import pytesseract
                from PIL import Image
                
                # 打开图片
                image = Image.open(file_path)
                
                # 更新元数据
                metadata.update({
                    'width': image.width,
                    'height': image.height,
                    'mode': image.mode,
                    'format': image.format
                })
                
                # 执行OCR
                text = pytesseract.image_to_string(image, lang='chi_sim+eng')
                
                if text and text.strip():
                    logger.info(f"OCR extracted {len(text)} characters from image")
                    return text.strip()
                else:
                    logger.info("No text found in image via OCR")
                    return ""
                    
            except ImportError:
                logger.warning("pytesseract not available for OCR")
                # 尝试使用easyocr作为备选
                try:
                    import easyocr
                    
                    reader = easyocr.Reader(['ch_sim', 'en'])
                    result = reader.readtext(file_path)
                    
                    if result:
                        text_parts = [item[1] for item in result if item[1].strip()]
                        text = '\n'.join(text_parts)
                        
                        if text.strip():
                            logger.info(f"EasyOCR extracted {len(text)} characters from image")
                            return text.strip()
                    
                    logger.info("No text found in image via EasyOCR")
                    return ""
                    
                except ImportError:
                    logger.warning("EasyOCR not available either")
                    return ""
                    
        except Exception as e:
            logger.warning(f"OCR processing failed: {e}")
            return ""
    
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
        
        # 对于图片OCR文本，通常较短，可以使用简单的分块策略
        text = text.strip()
        
        # 如果文本长度小于chunk_size，直接返回
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # 如果不是最后一块，尝试在句号或换行符处断开
            if end < len(text):
                # 寻找最近的句号或换行符
                for i in range(end, max(start + chunk_size // 2, start + 1), -1):
                    if text[i-1] in '.。\n':
                        end = i
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # 计算下一个开始位置（考虑重叠）
            start = max(start + 1, end - overlap)
        
        logger.info(f"Image text split into {len(chunks)} chunks")
        return chunks 