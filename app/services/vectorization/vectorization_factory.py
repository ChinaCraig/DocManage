"""
向量化工厂
根据文件类型自动选择合适的向量化器
"""

import logging
import os
from typing import Optional, Dict, Any, List
from .base_vectorizer import BaseVectorizer
from .pdf_vectorizer import PDFVectorizer
from .word_vectorizer import WordVectorizer
from .excel_vectorizer import ExcelVectorizer
from .image_vectorizer import ImageVectorizer
from .video_vectorizer import VideoVectorizer

logger = logging.getLogger(__name__)

class VectorizationFactory:
    """向量化工厂类"""
    
    def __init__(self):
        """初始化向量化工厂"""
        self._vectorizers = {
            'pdf': PDFVectorizer,
            'word': WordVectorizer,
            'excel': ExcelVectorizer,
            'image': ImageVectorizer,
            'video': VideoVectorizer
        }
        
        # 文件扩展名到向量化器的映射
        self._extension_mapping = {}
        self._build_extension_mapping()
    
    def _build_extension_mapping(self):
        """构建文件扩展名到向量化器的映射"""
        for vectorizer_type, vectorizer_class in self._vectorizers.items():
            try:
                # 临时实例化以获取支持的扩展名
                temp_instance = vectorizer_class()
                extensions = temp_instance.get_supported_extensions()
                
                for ext in extensions:
                    self._extension_mapping[ext.lower()] = vectorizer_type
                    
            except Exception as e:
                logger.warning(f"Failed to get extensions for {vectorizer_type}: {e}")
    
    def get_vectorizer(self, file_path: str) -> Optional[BaseVectorizer]:
        """
        根据文件路径获取合适的向量化器
        
        Args:
            file_path: 文件路径
            
        Returns:
            向量化器实例，如果不支持则返回None
        """
        try:
            # 获取文件扩展名
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if not file_ext:
                logger.warning(f"No file extension found: {file_path}")
                return None
            
            # 查找对应的向量化器类型
            vectorizer_type = self._extension_mapping.get(file_ext)
            
            if not vectorizer_type:
                logger.warning(f"Unsupported file extension: {file_ext}")
                return None
            
            # 创建向量化器实例
            vectorizer_class = self._vectorizers[vectorizer_type]
            vectorizer = vectorizer_class()
            
            logger.info(f"Selected {vectorizer_type} vectorizer for file: {file_path}")
            return vectorizer
            
        except Exception as e:
            logger.error(f"Failed to get vectorizer for {file_path}: {e}")
            return None
    
    def get_vectorizer_by_type(self, vectorizer_type: str) -> Optional[BaseVectorizer]:
        """
        根据类型获取向量化器
        
        Args:
            vectorizer_type: 向量化器类型（pdf, word, excel, image, video）
            
        Returns:
            向量化器实例，如果类型不存在则返回None
        """
        try:
            vectorizer_class = self._vectorizers.get(vectorizer_type.lower())
            
            if not vectorizer_class:
                logger.warning(f"Unknown vectorizer type: {vectorizer_type}")
                return None
            
            return vectorizer_class()
            
        except Exception as e:
            logger.error(f"Failed to create vectorizer of type {vectorizer_type}: {e}")
            return None
    
    def get_supported_extensions(self) -> Dict[str, List[str]]:
        """
        获取所有支持的文件扩展名
        
        Returns:
            按类型分组的扩展名字典
        """
        extensions_by_type = {}
        
        for vectorizer_type, vectorizer_class in self._vectorizers.items():
            try:
                temp_instance = vectorizer_class()
                extensions = temp_instance.get_supported_extensions()
                extensions_by_type[vectorizer_type] = extensions
                
            except Exception as e:
                logger.warning(f"Failed to get extensions for {vectorizer_type}: {e}")
                extensions_by_type[vectorizer_type] = []
        
        return extensions_by_type
    
    def get_all_supported_extensions(self) -> List[str]:
        """
        获取所有支持的文件扩展名列表
        
        Returns:
            所有支持的扩展名列表
        """
        all_extensions = []
        extensions_by_type = self.get_supported_extensions()
        
        for extensions in extensions_by_type.values():
            all_extensions.extend(extensions)
        
        return sorted(list(set(all_extensions)))
    
    def is_supported_file(self, file_path: str) -> bool:
        """
        检查文件是否支持向量化
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否支持
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        return file_ext in self._extension_mapping
    
    def get_file_type(self, file_path: str) -> Optional[str]:
        """
        获取文件的向量化类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件类型（pdf, word, excel, image, video），如果不支持则返回None
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        return self._extension_mapping.get(file_ext)
    
    def vectorize_document(self, file_path: str, document_id: str, 
                          chunk_size: int = 1000, overlap: int = 200) -> Dict[str, Any]:
        """
        向量化文档的便捷方法
        
        Args:
            file_path: 文件路径
            document_id: 文档ID
            chunk_size: 分块大小
            overlap: 重叠大小
            
        Returns:
            向量化结果
        """
        try:
            # 获取向量化器
            vectorizer = self.get_vectorizer(file_path)
            
            if not vectorizer:
                return {
                    'success': False,
                    'error': f'不支持的文件类型: {os.path.splitext(file_path)[1]}'
                }
            
            # 初始化向量服务
            vectorizer.initialize_vector_service()
            
            # 执行向量化
            result = vectorizer.vectorize_document(file_path, document_id, chunk_size, overlap)
            
            # 添加文件类型信息
            if result.get('success'):
                result['file_type'] = vectorizer.file_type
                result['vectorizer_used'] = vectorizer.__class__.__name__
            
            return result
            
        except Exception as e:
            logger.error(f"Document vectorization failed: {e}")
            return {
                'success': False,
                'error': f'文档向量化失败: {str(e)}'
            }
    
    def get_vectorizer_info(self) -> Dict[str, Any]:
        """
        获取向量化器信息
        
        Returns:
            向量化器信息字典
        """
        info = {
            'available_vectorizers': list(self._vectorizers.keys()),
            'total_vectorizers': len(self._vectorizers),
            'supported_extensions': self.get_supported_extensions(),
            'total_supported_extensions': len(self.get_all_supported_extensions())
        }
        
        return info
    
    def register_vectorizer(self, vectorizer_type: str, vectorizer_class: type):
        """
        注册新的向量化器
        
        Args:
            vectorizer_type: 向量化器类型名称
            vectorizer_class: 向量化器类
        """
        try:
            if not issubclass(vectorizer_class, BaseVectorizer):
                raise ValueError("Vectorizer class must inherit from BaseVectorizer")
            
            self._vectorizers[vectorizer_type] = vectorizer_class
            
            # 重新构建扩展名映射
            temp_instance = vectorizer_class()
            extensions = temp_instance.get_supported_extensions()
            
            for ext in extensions:
                self._extension_mapping[ext.lower()] = vectorizer_type
            
            logger.info(f"Registered new vectorizer: {vectorizer_type}")
            
        except Exception as e:
            logger.error(f"Failed to register vectorizer {vectorizer_type}: {e}")
            raise 