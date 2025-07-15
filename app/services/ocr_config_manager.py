"""
OCR配置管理器
统一管理OCR资源配置和监控设置
"""

import logging
import os
import yaml
from typing import Dict, Any
from .ocr_resource_manager import OCRResourceConfig

logger = logging.getLogger(__name__)

class OCRConfigManager:
    """OCR配置管理器"""
    
    def __init__(self):
        """初始化OCR配置管理器"""
        self._config = self._load_default_config()
        self._load_config_from_env()
        self._load_config_from_file()
        logger.info(f"✅ OCR配置管理器初始化完成")
    
    def _load_default_config(self) -> Dict[str, Any]:
        """加载默认配置"""
        return {
            'resource_control': {
                'max_concurrent_tasks': 2,
                'single_task_timeout': 30,
                'max_memory_usage_mb': 2048,
                'memory_check_interval': 5,
                'enable_resource_monitoring': True
            },
            'document_limits': {
                'pdf_max_images': 30,
                'word_max_images': 20,
                'excel_max_images': 15,
                'max_image_size_mb': 50,
                'max_image_pixels': 100000000  # 1亿像素
            },
            'ocr_engines': {
                'preferred_order': ['paddleocr', 'easyocr', 'tesseract'],
                'fallback_enabled': True,
                'engine_timeout': 25
            },
            'performance': {
                'enable_batch_processing': True,
                'batch_size': 5,
                'enable_image_preprocessing': True,
                'enable_memory_optimization': True
            },
            'logging': {
                'log_level': 'INFO',
                'log_ocr_stats': True,
                'log_resource_usage': True
            }
        }
    
    def _load_config_from_env(self):
        """从环境变量加载配置"""
        # 资源控制
        if os.getenv('OCR_MAX_CONCURRENT_TASKS'):
            self._config['resource_control']['max_concurrent_tasks'] = int(os.getenv('OCR_MAX_CONCURRENT_TASKS'))
        
        if os.getenv('OCR_TASK_TIMEOUT'):
            self._config['resource_control']['single_task_timeout'] = int(os.getenv('OCR_TASK_TIMEOUT'))
        
        if os.getenv('OCR_MAX_MEMORY_MB'):
            self._config['resource_control']['max_memory_usage_mb'] = int(os.getenv('OCR_MAX_MEMORY_MB'))
        
        # 文档限制
        if os.getenv('OCR_PDF_MAX_IMAGES'):
            self._config['document_limits']['pdf_max_images'] = int(os.getenv('OCR_PDF_MAX_IMAGES'))
        
        if os.getenv('OCR_WORD_MAX_IMAGES'):
            self._config['document_limits']['word_max_images'] = int(os.getenv('OCR_WORD_MAX_IMAGES'))
        
        # 引擎设置
        if os.getenv('OCR_PREFERRED_ENGINE'):
            preferred = os.getenv('OCR_PREFERRED_ENGINE').split(',')
            self._config['ocr_engines']['preferred_order'] = [e.strip() for e in preferred]
        
        if os.getenv('OCR_FALLBACK_ENABLED'):
            self._config['ocr_engines']['fallback_enabled'] = os.getenv('OCR_FALLBACK_ENABLED').lower() == 'true'
        
        logger.info("📋 已从环境变量加载OCR配置")
    
    def _load_config_from_file(self):
        """从配置文件加载配置"""
        config_path = os.path.join('config', 'ocr_config.yaml')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        self._merge_config(self._config, file_config)
                        logger.info(f"📄 已从配置文件加载OCR配置: {config_path}")
            except Exception as e:
                logger.warning(f"加载OCR配置文件失败: {e}")
    
    def _merge_config(self, base_config: Dict, new_config: Dict):
        """合并配置"""
        for key, value in new_config.items():
            if key in base_config and isinstance(base_config[key], dict) and isinstance(value, dict):
                self._merge_config(base_config[key], value)
            else:
                base_config[key] = value
    
    def get_resource_config_for_document_type(self, doc_type: str) -> OCRResourceConfig:
        """
        获取特定文档类型的资源配置
        
        Args:
            doc_type: 文档类型 (pdf, word, image, excel)
            
        Returns:
            OCR资源配置
        """
        base_config = self._config['resource_control']
        doc_limits = self._config['document_limits']
        
        # 根据文档类型调整配置
        if doc_type == 'pdf':
            max_images = doc_limits['pdf_max_images']
            timeout = base_config['single_task_timeout']
            memory_mb = base_config['max_memory_usage_mb']
        elif doc_type == 'word':
            max_images = doc_limits['word_max_images']
            timeout = base_config['single_task_timeout'] - 5
            memory_mb = int(base_config['max_memory_usage_mb'] * 0.7)
        elif doc_type == 'image':
            max_images = 1
            timeout = base_config['single_task_timeout'] + 10
            memory_mb = int(base_config['max_memory_usage_mb'] * 0.5)
        elif doc_type == 'excel':
            max_images = doc_limits['excel_max_images']
            timeout = base_config['single_task_timeout'] - 10
            memory_mb = int(base_config['max_memory_usage_mb'] * 0.5)
        else:
            max_images = doc_limits['pdf_max_images']
            timeout = base_config['single_task_timeout']
            memory_mb = base_config['max_memory_usage_mb']
        
        return OCRResourceConfig(
            max_concurrent_tasks=base_config['max_concurrent_tasks'],
            single_task_timeout=timeout,
            max_memory_usage_mb=memory_mb,
            max_images_per_document=max_images,
            memory_check_interval=base_config['memory_check_interval'],
            enable_resource_monitoring=base_config['enable_resource_monitoring']
        )
    
    def get_engine_config(self) -> Dict[str, Any]:
        """获取引擎配置"""
        return self._config['ocr_engines'].copy()
    
    def get_performance_config(self) -> Dict[str, Any]:
        """获取性能配置"""
        return self._config['performance'].copy()
    
    def get_document_limits(self) -> Dict[str, Any]:
        """获取文档限制配置"""
        return self._config['document_limits'].copy()
    
    def is_image_size_allowed(self, file_path: str) -> bool:
        """检查图像尺寸是否允许"""
        try:
            file_size = os.path.getsize(file_path)
            max_size = self._config['document_limits']['max_image_size_mb'] * 1024 * 1024
            
            if file_size > max_size:
                logger.warning(f"图像文件过大: {file_size / 1024 / 1024:.1f}MB > {max_size / 1024 / 1024}MB")
                return False
            
            # 检查像素数（如果是图像文件）
            try:
                from PIL import Image
                with Image.open(file_path) as img:
                    pixels = img.width * img.height
                    max_pixels = self._config['document_limits']['max_image_pixels']
                    
                    if pixels > max_pixels:
                        logger.warning(f"图像像素过多: {pixels} > {max_pixels}")
                        return False
            except Exception:
                pass  # 非图像文件或无法读取，跳过像素检查
            
            return True
            
        except Exception as e:
            logger.error(f"检查图像尺寸失败: {e}")
            return True  # 检查失败时允许处理
    
    def get_full_config(self) -> Dict[str, Any]:
        """获取完整配置"""
        return self._config.copy()
    
    def update_config(self, new_config: Dict[str, Any]):
        """更新配置"""
        self._merge_config(self._config, new_config)
        logger.info("🔄 OCR配置已更新")
    
    def save_config_to_file(self, file_path: str = None):
        """保存配置到文件"""
        if file_path is None:
            file_path = os.path.join('config', 'ocr_config.yaml')
        
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, default_flow_style=False, allow_unicode=True)
            logger.info(f"💾 OCR配置已保存到: {file_path}")
        except Exception as e:
            logger.error(f"保存OCR配置失败: {e}")

# 全局配置管理器实例
_config_manager = None

def get_ocr_config_manager() -> OCRConfigManager:
    """获取全局OCR配置管理器"""
    global _config_manager
    if _config_manager is None:
        _config_manager = OCRConfigManager()
    return _config_manager 