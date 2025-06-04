from .base_preview import BasePreviewService
import PyPDF2
import fitz  # PyMuPDF
import os
import logging
from datetime import datetime
from PIL import Image
import io

logger = logging.getLogger(__name__)

class PdfPreviewService(BasePreviewService):
    """PDF文档预览服务"""
    
    def __init__(self):
        super().__init__()
        self.supported_formats = ['pdf']
    
    def extract_content(self, file_path):
        """提取PDF文档内容"""
        if not self.validate_file(file_path):
            raise FileNotFoundError(f"文件不存在或无法读取: {file_path}")
        
        try:
            content_data = {
                'text': '',
                'pages': 0,
                'metadata': {}
            }
            
            # 使用 PyMuPDF 提取文本内容
            doc = fitz.open(file_path)
            content_data['pages'] = len(doc)
            
            # 提取所有页面的文本
            full_text = []
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()
                if text.strip():
                    full_text.append(f"--- 第 {page_num + 1} 页 ---\n{text}")
            
            content_data['text'] = '\n\n'.join(full_text)
            
            # 获取文档元数据
            metadata = doc.metadata
            content_data['metadata'] = {
                'title': metadata.get('title', ''),
                'author': metadata.get('author', ''),
                'subject': metadata.get('subject', ''),
                'keywords': metadata.get('keywords', ''),
                'creator': metadata.get('creator', ''),
                'producer': metadata.get('producer', ''),
                'creationDate': metadata.get('creationDate', ''),
                'modDate': metadata.get('modDate', '')
            }
            
            doc.close()
            
            logger.info(f"✅ PDF内容提取成功: {file_path}, 页数: {content_data['pages']}")
            return content_data
            
        except Exception as e:
            logger.error(f"❌ PDF内容提取失败: {file_path}, 错误: {str(e)}")
            # 尝试使用 PyPDF2 作为备选方案
            return self._extract_with_pypdf2(file_path)
    
    def _extract_with_pypdf2(self, file_path):
        """使用PyPDF2提取内容（备选方案）"""
        try:
            content_data = {
                'text': '',
                'pages': 0,
                'metadata': {}
            }
            
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                content_data['pages'] = len(reader.pages)
                
                # 提取文本
                full_text = []
                for page_num, page in enumerate(reader.pages):
                    text = page.extract_text()
                    if text.strip():
                        full_text.append(f"--- 第 {page_num + 1} 页 ---\n{text}")
                
                content_data['text'] = '\n\n'.join(full_text)
                
                # 获取元数据
                if reader.metadata:
                    content_data['metadata'] = {
                        'title': reader.metadata.get('/Title', ''),
                        'author': reader.metadata.get('/Author', ''),
                        'subject': reader.metadata.get('/Subject', ''),
                        'creator': reader.metadata.get('/Creator', ''),
                        'producer': reader.metadata.get('/Producer', ''),
                        'creationDate': str(reader.metadata.get('/CreationDate', '')),
                        'modDate': str(reader.metadata.get('/ModDate', ''))
                    }
            
            logger.info(f"✅ PDF内容提取成功（PyPDF2）: {file_path}")
            return content_data
            
        except Exception as e:
            logger.error(f"❌ PDF内容提取失败（PyPDF2）: {file_path}, 错误: {str(e)}")
            raise
    
    def get_metadata(self, file_path):
        """获取PDF元数据"""
        if not self.validate_file(file_path):
            raise FileNotFoundError(f"文件不存在或无法读取: {file_path}")
        
        try:
            metadata = {
                'file_size': self.get_file_size(file_path),
                'file_size_formatted': self.format_file_size(self.get_file_size(file_path)),
                'file_type': 'PDF',
                'last_modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
            }
            
            # 使用 PyMuPDF 获取详细元数据
            doc = fitz.open(file_path)
            
            metadata.update({
                'pages': len(doc),
                'title': doc.metadata.get('title', ''),
                'author': doc.metadata.get('author', ''),
                'subject': doc.metadata.get('subject', ''),
                'keywords': doc.metadata.get('keywords', ''),
                'creator': doc.metadata.get('creator', ''),
                'producer': doc.metadata.get('producer', ''),
                'creation_date': doc.metadata.get('creationDate', ''),
                'modification_date': doc.metadata.get('modDate', '')
            })
            
            doc.close()
            
            return metadata
            
        except Exception as e:
            logger.error(f"获取PDF元数据失败: {file_path}, 错误: {str(e)}")
            # 返回基本信息
            return {
                'file_size': self.get_file_size(file_path),
                'file_size_formatted': self.format_file_size(self.get_file_size(file_path)),
                'file_type': 'PDF',
                'last_modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
                'pages': 0,
                'error': str(e)
            }
    
    def generate_thumbnail(self, file_path, output_path=None, size=(200, 200)):
        """生成PDF缩略图"""
        if not self.validate_file(file_path):
            return None
        
        try:
            # 生成输出路径
            if output_path is None:
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                output_dir = os.path.join(os.path.dirname(file_path), 'thumbnails')
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, f"{base_name}_thumb.png")
            
            # 使用 PyMuPDF 生成缩略图
            doc = fitz.open(file_path)
            
            if len(doc) > 0:
                # 获取第一页
                page = doc.load_page(0)
                
                # 计算缩放比例
                mat = fitz.Matrix(2, 2)  # 2x放大，提高质量
                pix = page.get_pixmap(matrix=mat)
                
                # 转换为PIL图像
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                
                # 调整尺寸
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                # 保存缩略图
                img.save(output_path, "PNG", quality=95)
                
                doc.close()
                logger.info(f"✅ PDF缩略图生成成功: {output_path}")
                return output_path
            
        except Exception as e:
            logger.error(f"❌ PDF缩略图生成失败: {file_path}, 错误: {str(e)}")
        
        return None 