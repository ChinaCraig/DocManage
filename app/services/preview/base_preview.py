from abc import ABC, abstractmethod
import os
import logging

logger = logging.getLogger(__name__)

class BasePreviewService(ABC):
    """文档预览服务基类"""
    
    def __init__(self):
        self.supported_formats = []
    
    @abstractmethod
    def extract_content(self, file_path):
        """提取文档内容
        
        Args:
            file_path (str): 文件路径
            
        Returns:
            dict: 包含文档内容和元数据的字典
        """
        pass
    
    @abstractmethod
    def get_metadata(self, file_path):
        """获取文档元数据
        
        Args:
            file_path (str): 文件路径
            
        Returns:
            dict: 文档元数据
        """
        pass
    
    def generate_thumbnail(self, file_path, output_path=None, size=(200, 200)):
        """生成缩略图
        
        Args:
            file_path (str): 原文件路径
            output_path (str): 输出路径，如果为None则自动生成
            size (tuple): 缩略图尺寸
            
        Returns:
            str: 缩略图文件路径，失败返回None
        """
        # 默认实现，子类可以重写
        return None
    
    def validate_file(self, file_path):
        """验证文件是否存在且可读
        
        Args:
            file_path (str): 文件路径
            
        Returns:
            bool: 验证结果
        """
        try:
            return os.path.exists(file_path) and os.path.isfile(file_path) and os.access(file_path, os.R_OK)
        except Exception as e:
            logger.error(f"文件验证失败: {file_path}, 错误: {str(e)}")
            return False
    
    def get_file_size(self, file_path):
        """获取文件大小
        
        Args:
            file_path (str): 文件路径
            
        Returns:
            int: 文件大小（字节），失败返回0
        """
        try:
            return os.path.getsize(file_path)
        except Exception as e:
            logger.error(f"获取文件大小失败: {file_path}, 错误: {str(e)}")
            return 0
    
    def format_file_size(self, size_bytes):
        """格式化文件大小
        
        Args:
            size_bytes (int): 文件大小（字节）
            
        Returns:
            str: 格式化后的文件大小
        """
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    def is_supported_format(self, file_extension):
        """检查是否支持的文件格式
        
        Args:
            file_extension (str): 文件扩展名
            
        Returns:
            bool: 是否支持
        """
        return file_extension.lower() in self.supported_formats 