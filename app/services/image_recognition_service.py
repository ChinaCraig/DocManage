"""
图像识别服务
支持多种OCR引擎和图像内容分析
"""

import logging
import os
import json
import base64
from typing import Dict, List, Any, Optional, Tuple
from PIL import Image
import io

# 兼容性修复：为新版本Pillow添加ANTIALIAS别名
try:
    from PIL import Image
    if not hasattr(Image, 'ANTIALIAS'):
        Image.ANTIALIAS = Image.LANCZOS
except Exception:
    pass

logger = logging.getLogger(__name__)

class ImageRecognitionService:
    """图像识别服务，支持多种识别引擎"""
    
    def __init__(self):
        """初始化图像识别服务"""
        self.available_engines = self._check_available_engines()
        logger.info(f"Available OCR engines: {', '.join(self.available_engines) if self.available_engines else 'None'}")
    
    def _check_available_engines(self) -> List[str]:
        """检查可用的识别引擎"""
        engines = []
        
        # 检查Tesseract
        try:
            import pytesseract
            engines.append('tesseract')
        except ImportError:
            pass
        
        # 检查EasyOCR
        try:
            import easyocr
            engines.append('easyocr')
        except ImportError:
            pass
        
        # 检查PaddleOCR
        try:
            import paddleocr
            engines.append('paddleocr')
        except ImportError:
            pass
        
        return engines
    
    def recognize_image(self, image_path: str, engine: str = 'auto', languages: List[str] = None) -> Dict[str, Any]:
        """
        识别图像中的文本和内容
        
        Args:
            image_path: 图像文件路径
            engine: 使用的识别引擎 ('auto', 'tesseract', 'easyocr', 'paddleocr')
            languages: 识别语言列表，默认为中英文
            
        Returns:
            识别结果字典
        """
        try:
            if not os.path.exists(image_path):
                return {
                    'success': False,
                    'error': f'图像文件不存在: {image_path}'
                }
            
            # 获取图像基本信息
            image_info = self._get_image_info(image_path)
            
            # 如果没有可用的OCR引擎，返回基本描述
            if not self.available_engines:
                return {
                    'success': True,
                    'text': f"图像文件: {os.path.basename(image_path)}",
                    'description': f"这是一个{image_info.get('format', '未知格式')}格式的图像文件，尺寸为{image_info.get('width', 0)}x{image_info.get('height', 0)}像素。",
                    'image_info': image_info,
                    'confidence': 0.0,
                    'engine_used': 'none',
                    'detected_objects': [],
                    'text_regions': []
                }
            
            # 选择识别引擎
            if engine == 'auto':
                engine = self._select_best_engine()
            
            if engine not in self.available_engines:
                engine = self.available_engines[0]
            
            # 设置默认语言
            if languages is None:
                languages = ['zh', 'en']  # 中英文
            
            # 执行图像识别
            result = self._recognize_with_engine(image_path, engine, languages)
            
            # 添加图像信息和增强描述
            if result.get('success'):
                result['image_info'] = image_info
                result['enhanced_description'] = self._generate_enhanced_description(
                    result.get('text', ''), image_info, result.get('detected_objects', [])
                )
            
            return result
            
        except Exception as e:
            logger.error(f"图像识别失败: {e}")
            return {
                'success': False,
                'error': f'图像识别失败: {str(e)}'
            }
    
    def _get_image_info(self, image_path: str) -> Dict[str, Any]:
        """获取图像基本信息"""
        try:
            with Image.open(image_path) as img:
                return {
                    'width': img.width,
                    'height': img.height,
                    'mode': img.mode,
                    'format': img.format,
                    'file_size': os.path.getsize(image_path),
                    'file_name': os.path.basename(image_path)
                }
        except Exception as e:
            logger.warning(f"获取图像信息失败: {e}")
            return {
                'file_size': os.path.getsize(image_path),
                'file_name': os.path.basename(image_path)
            }
    
    def _select_best_engine(self) -> str:
        """选择最佳的识别引擎"""
        # 优先级: PaddleOCR > EasyOCR > Tesseract
        if 'paddleocr' in self.available_engines:
            return 'paddleocr'
        elif 'easyocr' in self.available_engines:
            return 'easyocr'
        elif 'tesseract' in self.available_engines:
            return 'tesseract'
        else:
            return self.available_engines[0] if self.available_engines else 'none'
    
    def _recognize_with_engine(self, image_path: str, engine: str, languages: List[str]) -> Dict[str, Any]:
        """使用指定引擎进行识别"""
        if engine == 'tesseract':
            return self._recognize_with_tesseract(image_path, languages)
        elif engine == 'easyocr':
            return self._recognize_with_easyocr(image_path, languages)
        elif engine == 'paddleocr':
            return self._recognize_with_paddleocr(image_path, languages)
        else:
            return {
                'success': False,
                'error': f'不支持的识别引擎: {engine}'
            }
    
    def _recognize_with_tesseract(self, image_path: str, languages: List[str]) -> Dict[str, Any]:
        """使用Tesseract进行OCR识别"""
        try:
            import pytesseract
            from PIL import Image
            
            # 语言映射
            lang_map = {
                'zh': 'chi_sim',
                'en': 'eng',
                'ja': 'jpn',
                'ko': 'kor'
            }
            
            # 构建语言参数
            lang_codes = [lang_map.get(lang, lang) for lang in languages]
            lang_param = '+'.join(lang_codes)
            
            # 打开图像
            image = Image.open(image_path)
            
            # 执行OCR
            text = pytesseract.image_to_string(image, lang=lang_param)
            
            # 获取详细信息（包含置信度和位置）
            data = pytesseract.image_to_data(image, lang=lang_param, output_type=pytesseract.Output.DICT)
            
            # 提取文本区域信息
            text_regions = []
            for i in range(len(data['text'])):
                if int(data['conf'][i]) > 0:  # 过滤低置信度文本
                    text_regions.append({
                        'text': data['text'][i],
                        'confidence': float(data['conf'][i]) / 100.0,
                        'bbox': {
                            'x': int(data['left'][i]),
                            'y': int(data['top'][i]),
                            'width': int(data['width'][i]),
                            'height': int(data['height'][i])
                        }
                    })
            
            # 计算平均置信度
            confidences = [region['confidence'] for region in text_regions if region['confidence'] > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return {
                'success': True,
                'text': text.strip(),
                'confidence': avg_confidence,
                'engine_used': 'tesseract',
                'text_regions': text_regions,
                'detected_objects': []  # Tesseract不支持对象检测
            }
            
        except Exception as e:
            logger.error(f"Tesseract OCR失败: {e}")
            return {
                'success': False,
                'error': f'Tesseract OCR失败: {str(e)}'
            }
    
    def _recognize_with_easyocr(self, image_path: str, languages: List[str]) -> Dict[str, Any]:
        """使用EasyOCR进行识别"""
        try:
            import easyocr
            
            # 语言映射
            lang_map = {
                'zh': 'ch_sim',
                'en': 'en',
                'ja': 'ja',
                'ko': 'ko'
            }
            
            # 构建语言列表
            lang_codes = [lang_map.get(lang, lang) for lang in languages]
            
            # 初始化读取器
            reader = easyocr.Reader(lang_codes)
            
            # 执行识别
            results = reader.readtext(image_path)
            
            # 提取文本和区域信息
            text_parts = []
            text_regions = []
            confidences = []
            
            for bbox, text, confidence in results:
                if confidence > 0.1:  # 过滤低置信度文本
                    text_parts.append(text)
                    confidences.append(confidence)
                    
                    # 计算边界框
                    x_coords = [point[0] for point in bbox]
                    y_coords = [point[1] for point in bbox]
                    
                    text_regions.append({
                        'text': text,
                        'confidence': float(confidence),
                        'bbox': {
                            'x': int(min(x_coords)),
                            'y': int(min(y_coords)),
                            'width': int(max(x_coords) - min(x_coords)),
                            'height': int(max(y_coords) - min(y_coords))
                        }
                    })
            
            # 合并文本
            full_text = '\n'.join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return {
                'success': True,
                'text': full_text,
                'confidence': avg_confidence,
                'engine_used': 'easyocr',
                'text_regions': text_regions,
                'detected_objects': []  # EasyOCR主要专注于文本识别
            }
            
        except Exception as e:
            logger.error(f"EasyOCR识别失败: {e}")
            return {
                'success': False,
                'error': f'EasyOCR识别失败: {str(e)}'
            }
    
    def _recognize_with_paddleocr(self, image_path: str, languages: List[str]) -> Dict[str, Any]:
        """使用PaddleOCR进行识别"""
        try:
            from paddleocr import PaddleOCR
            
            # 判断是否包含中文
            use_chinese = 'zh' in languages
            
            # 初始化PaddleOCR
            ocr = PaddleOCR(use_angle_cls=True, lang='ch' if use_chinese else 'en')
            
            # 执行识别
            results = ocr.ocr(image_path, cls=True)
            
            # 提取文本和区域信息
            text_parts = []
            text_regions = []
            confidences = []
            
            if results and results[0]:
                for line in results[0]:
                    bbox, (text, confidence) = line
                    
                    if confidence > 0.1:  # 过滤低置信度文本
                        text_parts.append(text)
                        confidences.append(confidence)
                        
                        # 计算边界框
                        x_coords = [point[0] for point in bbox]
                        y_coords = [point[1] for point in bbox]
                        
                        text_regions.append({
                            'text': text,
                            'confidence': float(confidence),
                            'bbox': {
                                'x': int(min(x_coords)),
                                'y': int(min(y_coords)),
                                'width': int(max(x_coords) - min(x_coords)),
                                'height': int(max(y_coords) - min(y_coords))
                            }
                        })
            
            # 合并文本
            full_text = '\n'.join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return {
                'success': True,
                'text': full_text,
                'confidence': avg_confidence,
                'engine_used': 'paddleocr',
                'text_regions': text_regions,
                'detected_objects': []  # PaddleOCR主要专注于文本识别
            }
            
        except Exception as e:
            logger.error(f"PaddleOCR识别失败: {e}")
            return {
                'success': False,
                'error': f'PaddleOCR识别失败: {str(e)}'
            }
    
    def _generate_enhanced_description(self, text: str, image_info: Dict, detected_objects: List) -> str:
        """生成增强的图像描述"""
        description_parts = []
        
        # 基本信息
        file_name = image_info.get('file_name', '未知文件')
        format_info = image_info.get('format', '未知格式')
        size_info = f"{image_info.get('width', 0)}x{image_info.get('height', 0)}"
        
        description_parts.append(f"图像文件: {file_name}")
        description_parts.append(f"格式: {format_info}, 尺寸: {size_info}像素")
        
        # 文本内容
        if text and text.strip():
            text_length = len(text.strip())
            description_parts.append(f"检测到文本内容({text_length}个字符):")
            description_parts.append(text.strip())
        else:
            description_parts.append("未检测到文本内容")
        
        # 检测到的对象
        if detected_objects:
            obj_names = [obj.get('name', '未知对象') for obj in detected_objects]
            description_parts.append(f"检测到的对象: {', '.join(obj_names)}")
        
        return '\n'.join(description_parts)
    
    def get_available_engines(self) -> List[str]:
        """获取可用的识别引擎列表"""
        return self.available_engines.copy()
    
    def get_supported_languages(self, engine: str = None) -> List[Dict[str, str]]:
        """获取支持的语言列表"""
        languages = [
            {'code': 'zh', 'name': '中文简体'},
            {'code': 'en', 'name': '英语'},
            {'code': 'ja', 'name': '日语'},
            {'code': 'ko', 'name': '韩语'}
        ]
        
        if engine == 'tesseract':
            # Tesseract支持更多语言，可以扩展
            pass
        elif engine == 'paddleocr':
            # PaddleOCR支持的语言
            pass
        
        return languages 