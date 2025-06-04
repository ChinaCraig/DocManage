"""
PDF文档向量化器
专门处理PDF文件的内容提取和向量化
"""

import logging
import os
import re
from typing import List, Dict, Any
from .base_vectorizer import BaseVectorizer

logger = logging.getLogger(__name__)

class PDFVectorizer(BaseVectorizer):
    """PDF文档向量化器"""
    
    def __init__(self):
        """初始化PDF向量化器"""
        super().__init__()
        self.file_type = "pdf"
    
    def get_supported_extensions(self) -> List[str]:
        """获取支持的文件扩展名"""
        return ['.pdf']
    
    def extract_text(self, file_path: str) -> Dict[str, Any]:
        """
        从PDF文件提取文本内容
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            包含提取结果的字典
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return {
                    'success': False,
                    'error': f'PDF文件不存在: {file_path}'
                }
            
            # 检查文件扩展名
            if not file_path.lower().endswith('.pdf'):
                return {
                    'success': False,
                    'error': '文件不是PDF格式'
                }
            
            try:
                import PyPDF2
                
                text_content = []
                metadata = {}
                
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    
                    # 获取元数据
                    metadata = {
                        'total_pages': len(pdf_reader.pages),
                        'file_size': os.path.getsize(file_path),
                        'file_type': 'pdf'
                    }
                    
                    # 如果PDF有元数据
                    if pdf_reader.metadata:
                        metadata.update({
                            'title': pdf_reader.metadata.get('/Title', ''),
                            'author': pdf_reader.metadata.get('/Author', ''),
                            'subject': pdf_reader.metadata.get('/Subject', ''),
                            'creator': pdf_reader.metadata.get('/Creator', ''),
                            'producer': pdf_reader.metadata.get('/Producer', ''),
                            'creation_date': str(pdf_reader.metadata.get('/CreationDate', '')),
                            'modification_date': str(pdf_reader.metadata.get('/ModDate', ''))
                        })
                    
                    # 提取每页文本
                    for page_num, page in enumerate(pdf_reader.pages):
                        try:
                            page_text = page.extract_text()
                            if page_text.strip():
                                text_content.append({
                                    'page': page_num + 1,
                                    'text': page_text.strip()
                                })
                        except Exception as e:
                            logger.warning(f"Failed to extract text from page {page_num + 1}: {e}")
                            continue
                
                # 合并所有页面的文本
                full_text = '\n\n'.join([page['text'] for page in text_content])
                
                if not full_text.strip():
                    # 尝试使用pdfplumber作为备选方案
                    try:
                        import pdfplumber
                        with pdfplumber.open(file_path) as pdf:
                            text_pages = []
                            for page in pdf.pages:
                                page_text = page.extract_text()
                                if page_text:
                                    text_pages.append(page_text)
                            full_text = '\n\n'.join(text_pages)
                            logger.info("Used pdfplumber as fallback for text extraction")
                    except ImportError:
                        logger.warning("pdfplumber not available, cannot use as fallback")
                    except Exception as e:
                        logger.warning(f"pdfplumber extraction failed: {e}")
                
                if not full_text.strip():
                    return {
                        'success': False,
                        'error': 'PDF文件中没有可提取的文本内容'
                    }
                
                # 进行文本分块
                chunks = self.chunk_text(full_text)
                
                return {
                    'success': True,
                    'text': full_text,
                    'metadata': metadata,
                    'chunks': chunks,
                    'pages_content': text_content
                }
                
            except ImportError:
                return {
                    'success': False,
                    'error': 'PyPDF2库未安装，请运行: pip install PyPDF2'
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': f'PDF文件处理失败: {str(e)}'
                }
                
        except Exception as e:
            logger.error(f"PDF text extraction failed: {e}")
            return {
                'success': False,
                'error': f'PDF文本提取失败: {str(e)}'
            }
    
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        将PDF文本进行智能分块
        
        Args:
            text: 原始文本
            chunk_size: 块大小
            overlap: 重叠大小
            
        Returns:
            文本块列表
        """
        if not text or not text.strip():
            return []
        
        # 清理文本
        text = self._clean_text(text)
        
        chunks = []
        
        # 首先按段落分割
        paragraphs = re.split(r'\n\s*\n', text)
        
        current_chunk = ""
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # 如果当前段落加上当前块的长度超过chunk_size
            if len(current_chunk) + len(paragraph) > chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    
                    # 处理重叠
                    if overlap > 0 and len(current_chunk) > overlap:
                        overlap_text = current_chunk[-overlap:]
                        current_chunk = overlap_text + "\n" + paragraph
                    else:
                        current_chunk = paragraph
                else:
                    # 如果单个段落就超过了chunk_size，需要强制分割
                    if len(paragraph) > chunk_size:
                        sub_chunks = self._split_long_paragraph(paragraph, chunk_size, overlap)
                        chunks.extend(sub_chunks[:-1])
                        current_chunk = sub_chunks[-1] if sub_chunks else ""
                    else:
                        current_chunk = paragraph
            else:
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
        
        # 添加最后一个块
        if current_chunk and current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        # 过滤掉太短的块
        chunks = [chunk for chunk in chunks if len(chunk.strip()) > 50]
        
        logger.info(f"PDF text split into {len(chunks)} chunks")
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """清理PDF提取的文本"""
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        
        # 移除页眉页脚常见模式
        text = re.sub(r'Page \d+.*?\n', '', text)
        text = re.sub(r'\d+\s*\n', '', text)
        
        # 修复被分割的单词
        text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
        
        # 恢复段落结构
        text = re.sub(r'\n+', '\n\n', text)
        
        return text.strip()
    
    def _split_long_paragraph(self, paragraph: str, chunk_size: int, overlap: int) -> List[str]:
        """分割过长的段落"""
        chunks = []
        sentences = re.split(r'[.!?]+', paragraph)
        
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            if len(current_chunk) + len(sentence) > chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    
                    # 处理重叠
                    if overlap > 0 and len(current_chunk) > overlap:
                        overlap_text = current_chunk[-overlap:]
                        current_chunk = overlap_text + " " + sentence
                    else:
                        current_chunk = sentence
                else:
                    # 如果单个句子还是太长，按字符强制分割
                    if len(sentence) > chunk_size:
                        word_chunks = self._split_by_words(sentence, chunk_size, overlap)
                        chunks.extend(word_chunks[:-1])
                        current_chunk = word_chunks[-1] if word_chunks else ""
                    else:
                        current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += ". " + sentence
                else:
                    current_chunk = sentence
        
        if current_chunk and current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _split_by_words(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """按单词分割文本"""
        words = text.split()
        chunks = []
        current_chunk = []
        current_length = 0
        
        for word in words:
            word_length = len(word) + 1  # +1 for space
            
            if current_length + word_length > chunk_size and current_chunk:
                chunk_text = ' '.join(current_chunk)
                chunks.append(chunk_text)
                
                # 处理重叠
                if overlap > 0:
                    overlap_words = []
                    overlap_length = 0
                    for w in reversed(current_chunk):
                        if overlap_length + len(w) + 1 <= overlap:
                            overlap_words.insert(0, w)
                            overlap_length += len(w) + 1
                        else:
                            break
                    current_chunk = overlap_words + [word]
                    current_length = sum(len(w) + 1 for w in current_chunk) - 1
                else:
                    current_chunk = [word]
                    current_length = word_length - 1
            else:
                current_chunk.append(word)
                current_length += word_length
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks 