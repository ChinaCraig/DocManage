"""
增强的图像识别服务
集成OCR资源管理器，提供资源控制和异常处理
"""

import logging
import os
import json
import base64
import warnings
import tempfile
from typing import Dict, List, Any, Optional, Tuple
from PIL import Image
import io
import threading

# 抑制PIL相关警告
warnings.filterwarnings('ignore', category=UserWarning, module='PIL')

# 兼容性修复：为新版本Pillow添加ANTIALIAS别名
try:
    from PIL import Image
    if not hasattr(Image, 'ANTIALIAS'):
        Image.ANTIALIAS = Image.LANCZOS
except Exception:
    pass

from .ocr_resource_manager import get_ocr_manager, OCRResourceConfig
from .image_recognition_service import ImageRecognitionService as BaseImageRecognitionService

logger = logging.getLogger(__name__)

class EnhancedImageRecognitionService(BaseImageRecognitionService):
    """增强的图像识别服务，带资源控制和异常处理"""
    
    def __init__(self, resource_config: OCRResourceConfig = None):
        """初始化增强图像识别服务"""
        super().__init__()
        self.ocr_manager = get_ocr_manager(resource_config)
        logger.info(f"✅ 增强图像识别服务初始化完成，可用引擎: {', '.join(self.available_engines) if self.available_engines else 'None'}")
    
    def recognize_image_with_control(self, 
                                   image_path: str, 
                                   engine: str = 'auto', 
                                   languages: List[str] = None,
                                   task_name: str = None) -> Dict[str, Any]:
        """
        带资源控制的图像识别
        
        Args:
            image_path: 图像文件路径
            engine: 使用的识别引擎
            languages: 识别语言列表
            task_name: 任务名称
            
        Returns:
            识别结果
        """
        if task_name is None:
            task_name = f"图像识别({os.path.basename(image_path)})"
        
        # 预检查
        if not self._pre_check_image(image_path):
            return {
                'success': False,
                'error': '图像预检查失败',
                'error_type': 'pre_check_failed'
            }
        
        # 使用OCR资源管理器执行识别
        return self.ocr_manager.execute_ocr_with_control(
            self._safe_recognize_image,
            image_path=image_path,
            engine=engine,
            languages=languages,
            task_name=task_name
        )
    
    def _pre_check_image(self, image_path: str) -> bool:
        """图像预检查"""
        try:
            # 检查文件是否存在
            if not os.path.exists(image_path):
                logger.error(f"图像文件不存在: {image_path}")
                return False
            
            # 检查文件大小
            file_size = os.path.getsize(image_path)
            max_size = 50 * 1024 * 1024  # 50MB
            if file_size > max_size:
                logger.warning(f"图像文件过大: {file_size / 1024 / 1024:.1f}MB > 50MB")
                return False
            
            # 检查文件格式
            try:
                with Image.open(image_path) as img:
                    # 检查图像尺寸
                    if img.width * img.height > 10000 * 10000:  # 1亿像素
                        logger.warning(f"图像尺寸过大: {img.width}x{img.height}")
                        return False
                    
                    logger.debug(f"✅ 图像预检查通过: {img.width}x{img.height}, {file_size / 1024:.1f}KB")
                    return True
                    
            except Exception as e:
                logger.error(f"图像格式检查失败: {e}")
                return False
                
        except Exception as e:
            logger.error(f"图像预检查失败: {e}")
            return False
    
    def _safe_recognize_image(self, 
                            image_path: str, 
                            engine: str = 'auto', 
                            languages: List[str] = None,
                            task_name: str = None) -> Dict[str, Any]:
        """安全的图像识别实现"""
        temp_image_path = None
        
        try:
            # 设置默认语言
            if languages is None:
                languages = ['zh', 'en']
            
            # 自动选择引擎
            if engine == 'auto':
                engine = self._select_best_engine()
                if engine == 'none':
                    return {
                        'success': False,
                        'error': '没有可用的OCR引擎',
                        'error_type': 'no_engine'
                    }
            
            # 检查引擎是否可用
            if engine not in self.available_engines:
                return {
                    'success': False,
                    'error': f'OCR引擎不可用: {engine}',
                    'error_type': 'engine_unavailable'
                }
            
            # 预处理图像
            temp_image_path = self._safe_preprocess_image(image_path)
            if not temp_image_path:
                temp_image_path = image_path
            
            # 获取图像信息
            image_info = self._safe_get_image_info(temp_image_path)
            
            # 执行OCR识别
            recognition_result = self._safe_recognize_with_engine(
                temp_image_path, engine, languages
            )
            
            if not recognition_result.get('success'):
                return recognition_result
            
            # 添加图像信息和增强描述
            recognition_result['image_info'] = image_info
            recognition_result['enhanced_description'] = self._generate_enhanced_description(
                recognition_result.get('text', ''), 
                image_info, 
                recognition_result.get('detected_objects', [])
            )
            recognition_result['resource_controlled'] = True
            
            # 记录成功
            text_length = len(recognition_result.get('text', ''))
            confidence = recognition_result.get('confidence', 0.0)
            logger.info(f"✅ {task_name}成功: 引擎={engine}, 文本长度={text_length}, 置信度={confidence:.2f}")
            
            return recognition_result
            
        except Exception as e:
            logger.error(f"❌ {task_name}失败: {e}")
            return {
                'success': False,
                'error': f'图像识别执行失败: {str(e)}',
                'error_type': 'execution_error'
            }
            
        finally:
            # 清理临时文件
            if temp_image_path and temp_image_path != image_path:
                self._safe_cleanup_temp_file(temp_image_path)
    
    def _safe_preprocess_image(self, image_path: str) -> Optional[str]:
        """安全的图像预处理"""
        try:
            return self._preprocess_image(image_path)
        except Exception as e:
            logger.warning(f"图像预处理失败，使用原始文件: {e}")
            return None
    
    def _safe_get_image_info(self, image_path: str) -> Dict[str, Any]:
        """安全获取图像信息"""
        try:
            return self._get_image_info(image_path)
        except Exception as e:
            logger.warning(f"获取图像信息失败: {e}")
            return {
                'file_size': os.path.getsize(image_path) if os.path.exists(image_path) else 0,
                'file_name': os.path.basename(image_path),
                'error': str(e)
            }
    
    def _safe_recognize_with_engine(self, 
                                  image_path: str, 
                                  engine: str, 
                                  languages: List[str]) -> Dict[str, Any]:
        """安全的引擎识别"""
        try:
            # 使用基类的识别方法
            return self._recognize_with_engine(image_path, engine, languages)
            
        except Exception as e:
            logger.error(f"OCR引擎{engine}识别失败: {e}")
            
            # 尝试降级到其他引擎
            fallback_engines = [eng for eng in self.available_engines if eng != engine]
            for fallback_engine in fallback_engines:
                try:
                    logger.info(f"🔄 尝试降级到引擎: {fallback_engine}")
                    result = self._recognize_with_engine(image_path, fallback_engine, languages)
                    if result.get('success'):
                        result['fallback_used'] = True
                        result['original_engine'] = engine
                        result['fallback_engine'] = fallback_engine
                        logger.info(f"✅ 降级成功，使用引擎: {fallback_engine}")
                        return result
                except Exception as fe:
                    logger.warning(f"降级引擎{fallback_engine}也失败: {fe}")
                    continue
            
            return {
                'success': False,
                'error': f'所有OCR引擎都失败，最后错误: {str(e)}',
                'error_type': 'all_engines_failed'
            }
    
    def _safe_cleanup_temp_file(self, temp_path: str):
        """安全清理临时文件"""
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                logger.debug(f"🗑️ 清理临时文件: {temp_path}")
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")
    
    def batch_recognize_images(self, 
                             image_paths: List[str],
                             engine: str = 'auto',
                             languages: List[str] = None,
                             max_images: int = None) -> List[Dict[str, Any]]:
        """
        批量图像识别，带资源控制
        
        Args:
            image_paths: 图像路径列表
            engine: OCR引擎
            languages: 识别语言
            max_images: 最大处理图片数
            
        Returns:
            识别结果列表
        """
        if not image_paths:
            return []
        
        # 构建OCR任务列表
        ocr_tasks = []
        for i, img_path in enumerate(image_paths):
            ocr_tasks.append({
                'func': self._safe_recognize_image,
                'kwargs': {
                    'image_path': img_path,
                    'engine': engine,
                    'languages': languages,
                    'task_name': f'批量图像识别{i+1}({os.path.basename(img_path)})'
                }
            })
        
        # 使用OCR资源管理器批量处理
        logger.info(f"📋 开始批量图像识别，共{len(image_paths)}张图片")
        results = self.ocr_manager.execute_batch_ocr(ocr_tasks, max_images)
        
        # 统计结果
        successful = sum(1 for r in results if r.get('success'))
        failed = len(results) - successful
        logger.info(f"📊 批量图像识别完成: 成功{successful}, 失败{failed}")
        
        return results
    
    def get_resource_stats(self) -> Dict[str, Any]:
        """获取资源使用统计"""
        stats = self.ocr_manager.get_resource_stats()
        stats['available_engines'] = self.available_engines
        stats['service_type'] = 'enhanced_image_recognition'
        return stats
    
    def optimize_resources(self):
        """优化资源使用"""
        logger.info("🧹 开始优化图像识别服务资源...")
        self.ocr_manager.optimize_memory()
        logger.info("✅ 图像识别服务资源优化完成")

# 创建全局实例
_enhanced_service_instance = None
_service_lock = threading.Lock()

def get_enhanced_image_service(resource_config: OCRResourceConfig = None) -> EnhancedImageRecognitionService:
    """获取增强图像识别服务实例"""
    global _enhanced_service_instance
    
    with _service_lock:
        if _enhanced_service_instance is None:
            _enhanced_service_instance = EnhancedImageRecognitionService(resource_config)
            logger.info("🎯 创建增强图像识别服务实例")
        return _enhanced_service_instance

def shutdown_enhanced_image_service():
    """关闭增强图像识别服务"""
    global _enhanced_service_instance
    
    with _service_lock:
        if _enhanced_service_instance:
            _enhanced_service_instance.optimize_resources()
            _enhanced_service_instance = None
            logger.info("🛑 关闭增强图像识别服务") 