from .pdf_preview import PdfPreviewService
from .word_preview import WordPreviewService
from .excel_preview import ExcelPreviewService
from .image_preview import ImagePreviewService
from .video_preview import VideoPreviewService
import logging

logger = logging.getLogger(__name__)

class PreviewServiceFactory:
    """预览服务工厂"""
    
    _services = {}
    
    @classmethod
    def get_service(cls, file_type):
        """根据文件类型获取预览服务
        
        Args:
            file_type (str): 文件类型 (pdf, word, excel, image, video)
            
        Returns:
            BasePreviewService: 预览服务实例
        """
        file_type = file_type.lower()
        
        if file_type not in cls._services:
            try:
                if file_type == 'pdf':
                    cls._services[file_type] = PdfPreviewService()
                elif file_type == 'word':
                    cls._services[file_type] = WordPreviewService()
                elif file_type == 'excel':
                    cls._services[file_type] = ExcelPreviewService()
                elif file_type == 'image':
                    cls._services[file_type] = ImagePreviewService()
                elif file_type == 'video':
                    cls._services[file_type] = VideoPreviewService()
                else:
                    raise ValueError(f"不支持的文件类型: {file_type}")
                    
                logger.info(f"✅ 创建预览服务成功: {file_type}")
                
            except Exception as e:
                logger.error(f"❌ 创建预览服务失败: {file_type}, 错误: {str(e)}")
                raise
        
        return cls._services[file_type]
    
    @classmethod
    def get_supported_types(cls):
        """获取支持的文件类型列表
        
        Returns:
            list: 支持的文件类型列表
        """
        return ['pdf', 'word', 'excel', 'image', 'video']
    
    @classmethod
    def clear_cache(cls):
        """清空服务缓存"""
        cls._services.clear()
        logger.info("🧹 预览服务缓存已清空")
    
    @classmethod
    def get_service_by_extension(cls, file_extension):
        """根据文件扩展名获取预览服务
        
        Args:
            file_extension (str): 文件扩展名（包含或不包含点）
            
        Returns:
            BasePreviewService: 预览服务实例
        """
        # 移除扩展名前的点
        ext = file_extension.lstrip('.').lower()
        
        # 映射扩展名到服务类型
        extension_mapping = {
            'pdf': 'pdf',
            'doc': 'word',
            'docx': 'word',
            'xls': 'excel',
            'xlsx': 'excel',
            'jpg': 'image',
            'jpeg': 'image',
            'png': 'image',
            'gif': 'image',
            'bmp': 'image',
            'mp4': 'video',
            'avi': 'video',
            'mov': 'video',
            'wmv': 'video'
        }
        
        service_type = extension_mapping.get(ext)
        if service_type:
            return cls.get_service(service_type)
        else:
            raise ValueError(f"不支持的文件扩展名: {file_extension}") 