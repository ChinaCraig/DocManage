"""
PDF文档处理服务
处理PDF文档的文本提取、OCR识别等功能
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
import os

logger = logging.getLogger(__name__)

class PDFService:
    """PDF处理服务类"""
    
    def __init__(self):
        """初始化PDF服务"""
        self.is_available = True
        try:
            import PyPDF2
            self.PyPDF2 = PyPDF2
            logger.info("PDF service initialized with PyPDF2")
        except ImportError:
            self.is_available = False
            logger.warning("PDF service is disabled - PyPDF2 not available")
    
    def extract_text(self, file_path: str) -> str:
        """
        从PDF文件提取文本
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            提取的文本内容
        """
        if not self.is_available:
            logger.info(f"PDF text extraction skipped for {file_path}")
            return f"Mock PDF content for file: {os.path.basename(file_path)}"
        
        try:
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = self.PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            
            logger.info(f"Successfully extracted text from PDF: {file_path}")
            return text.strip()
            
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            return f"Error extracting content from: {os.path.basename(file_path)}"
    
    def extract_text_with_ocr(self, file_path: str) -> str:
        """
        使用OCR从PDF文件提取文本（用于扫描版PDF）
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            OCR识别的文本内容
        """
        # 暂时返回普通文本提取结果
        logger.info(f"OCR extraction not implemented, falling back to text extraction for {file_path}")
        return self.extract_text(file_path)
    
    def get_page_count(self, file_path: str) -> int:
        """
        获取PDF页数
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            页数
        """
        if not self.is_available:
            logger.info(f"PDF page count check skipped for {file_path}")
            return 1
        
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = self.PyPDF2.PdfReader(file)
                page_count = len(pdf_reader.pages)
                logger.info(f"PDF {file_path} has {page_count} pages")
                return page_count
                
        except Exception as e:
            logger.error(f"Failed to get page count: {e}")
            return 0
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        提取PDF元数据
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            元数据字典
        """
        if not self.is_available:
            logger.info(f"PDF metadata extraction skipped for {file_path}")
            return {
                "title": f"Mock Title for {os.path.basename(file_path)}",
                "author": "Unknown",
                "subject": "",
                "creator": "",
                "producer": "",
                "creation_date": None,
                "modification_date": None,
                "page_count": 1
            }
        
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = self.PyPDF2.PdfReader(file)
                metadata = pdf_reader.metadata or {}
                
                return {
                    "title": str(metadata.get('/Title', os.path.basename(file_path))),
                    "author": str(metadata.get('/Author', 'Unknown')),
                    "subject": str(metadata.get('/Subject', '')),
                    "creator": str(metadata.get('/Creator', '')),
                    "producer": str(metadata.get('/Producer', '')),
                    "creation_date": metadata.get('/CreationDate'),
                    "modification_date": metadata.get('/ModDate'),
                    "page_count": len(pdf_reader.pages)
                }
                
        except Exception as e:
            logger.error(f"Failed to extract metadata: {e}")
            return {
                "title": os.path.basename(file_path),
                "author": "Unknown",
                "subject": "",
                "creator": "",
                "producer": "",
                "creation_date": None,
                "modification_date": None,
                "page_count": 0
            }
    
    def split_into_chunks(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        将文本分割成块
        
        Args:
            text: 输入文本
            chunk_size: 块大小
            overlap: 重叠大小
            
        Returns:
            文本块列表
        """
        try:
            if not text:
                return []
            
            chunks = []
            start = 0
            
            while start < len(text):
                end = start + chunk_size
                chunk = text[start:end]
                
                # 如果不是最后一块，尝试在句号或换行符处分割
                if end < len(text):
                    last_break = max(
                        chunk.rfind('。'),
                        chunk.rfind('\n'),
                        chunk.rfind('.')
                    )
                    if last_break > chunk_size * 0.7:  # 如果断点位置合理
                        chunk = chunk[:last_break + 1]
                        end = start + last_break + 1
                
                chunks.append(chunk.strip())
                start = end - overlap
                
                if start >= len(text):
                    break
            
            return chunks
        except Exception as e:
            logger.error(f"Failed to split text into chunks: {e}")
            return [text] if text else []
    
    def process_pdf(self, file_path: str) -> Dict[str, Any]:
        """
        完整处理PDF文件
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            处理结果字典
        """
        try:
            # 提取基本信息
            metadata = self.extract_metadata(file_path)
            page_count = self.get_page_count(file_path)
            
            # 提取文本
            text = self.extract_text(file_path)
            
            # 如果文本提取失败或内容很少，尝试OCR
            if not text or len(text.strip()) < 100:
                logger.info("Text extraction yielded little content, trying OCR...")
                ocr_text = self.extract_text_with_ocr(file_path)
                if ocr_text and len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text
            
            # 分割文本
            chunks = self.split_into_chunks(text)
            
            return {
                "success": True,
                "text": text,
                "chunks": chunks,
                "metadata": metadata,
                "page_count": page_count,
                "chunk_count": len(chunks),
                "text_length": len(text)
            }
        except Exception as e:
            logger.error(f"Failed to process PDF: {e}")
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "chunks": [],
                "metadata": {},
                "page_count": 0,
                "chunk_count": 0,
                "text_length": 0
            }
    
    def extract_text_content(self, file_path: str) -> Dict[str, Any]:
        """
        提取文件文本内容（为upload_routes.py兼容）
        
        Args:
            file_path: 文件路径
            
        Returns:
            提取结果字典
        """
        try:
            text = self.extract_text(file_path)
            page_count = self.get_page_count(file_path)
            
            # 按页面组织结果
            pages = []
            if text:
                # 简单按页数分割文本
                lines = text.split('\n')
                lines_per_page = max(1, len(lines) // max(1, page_count))
                
                for i in range(page_count):
                    start_line = i * lines_per_page
                    end_line = start_line + lines_per_page
                    page_text = '\n'.join(lines[start_line:end_line])
                    
                    pages.append({
                        'page_number': i + 1,
                        'content': page_text
                    })
            
            return {
                'success': True,
                'content': text,
                'pages': pages,
                'page_count': page_count
            }
            
        except Exception as e:
            logger.error(f"Failed to extract text content: {e}")
            return {
                'success': False,
                'error': str(e),
                'content': '',
                'pages': [],
                'page_count': 0
            } 