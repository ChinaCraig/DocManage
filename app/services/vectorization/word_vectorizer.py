"""
Word文档向量化器
专门处理Word文档(.doc, .docx)的内容提取和向量化
"""

import logging
import os
import re
from typing import List, Dict, Any
from .base_vectorizer import BaseVectorizer

logger = logging.getLogger(__name__)

class WordVectorizer(BaseVectorizer):
    """Word文档向量化器"""
    
    def __init__(self):
        """初始化Word向量化器"""
        super().__init__()
        self.file_type = "word"
    
    def get_supported_extensions(self) -> List[str]:
        """获取支持的文件扩展名"""
        return ['.doc', '.docx']
    
    def extract_text(self, file_path: str) -> Dict[str, Any]:
        """
        从Word文档提取文本内容
        
        Args:
            file_path: Word文档路径
            
        Returns:
            包含提取结果的字典
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return {
                    'success': False,
                    'error': f'Word文档不存在: {file_path}'
                }
            
            # 检查文件扩展名
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext not in self.get_supported_extensions():
                return {
                    'success': False,
                    'error': f'不支持的文件格式: {file_ext}'
                }
            
            # 根据文件类型选择提取方法
            if file_ext == '.docx':
                return self._extract_docx(file_path)
            elif file_ext == '.doc':
                return self._extract_doc(file_path)
            else:
                return {
                    'success': False,
                    'error': f'不支持的Word文档格式: {file_ext}'
                }
                
        except Exception as e:
            logger.error(f"Word document text extraction failed: {e}")
            return {
                'success': False,
                'error': f'Word文档文本提取失败: {str(e)}'
            }
    
    def _extract_docx(self, file_path: str) -> Dict[str, Any]:
        """提取.docx文档内容"""
        try:
            import docx
            
            doc = docx.Document(file_path)
            
            # 获取基本元数据
            metadata = {
                'file_size': os.path.getsize(file_path),
                'file_type': 'docx',
                'total_paragraphs': len(doc.paragraphs),
                'total_tables': len(doc.tables)
            }
            
            # 提取文档属性
            core_properties = doc.core_properties
            if core_properties:
                metadata.update({
                    'title': core_properties.title or '',
                    'author': core_properties.author or '',
                    'subject': core_properties.subject or '',
                    'keywords': core_properties.keywords or '',
                    'comments': core_properties.comments or '',
                    'created': str(core_properties.created) if core_properties.created else '',
                    'modified': str(core_properties.modified) if core_properties.modified else '',
                    'last_modified_by': core_properties.last_modified_by or '',
                    'category': core_properties.category or ''
                })
            
            # 提取文本内容
            text_parts = []
            
            # 提取段落文本
            for paragraph in doc.paragraphs:
                text = paragraph.text.strip()
                if text:
                    text_parts.append(text)
            
            # 提取表格内容
            for table in doc.tables:
                table_text = self._extract_table_text(table)
                if table_text:
                    text_parts.append(f"[表格内容]\n{table_text}")
            
            # 合并所有文本
            full_text = '\n\n'.join(text_parts)
            
            if not full_text.strip():
                return {
                    'success': False,
                    'error': 'Word文档中没有可提取的文本内容'
                }
            
            # 进行文本分块
            chunks = self.chunk_text(full_text)
            
            return {
                'success': True,
                'text': full_text,
                'metadata': metadata,
                'chunks': chunks
            }
            
        except ImportError:
            return {
                'success': False,
                'error': 'python-docx库未安装，请运行: pip install python-docx'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'DOCX文档处理失败: {str(e)}'
            }
    
    def _extract_doc(self, file_path: str) -> Dict[str, Any]:
        """提取.doc文档内容（旧版本Word）"""
        try:
            # 尝试使用python-docx2txt
            try:
                import docx2txt
                
                text = docx2txt.process(file_path)
                
                if not text or not text.strip():
                    return {
                        'success': False,
                        'error': 'DOC文档中没有可提取的文本内容'
                    }
                
                metadata = {
                    'file_size': os.path.getsize(file_path),
                    'file_type': 'doc'
                }
                
                # 进行文本分块
                chunks = self.chunk_text(text)
                
                return {
                    'success': True,
                    'text': text,
                    'metadata': metadata,
                    'chunks': chunks
                }
                
            except ImportError:
                # 尝试使用antiword（需要系统安装）
                try:
                    import subprocess
                    result = subprocess.run(['antiword', file_path], 
                                          capture_output=True, text=True, encoding='utf-8')
                    
                    if result.returncode == 0 and result.stdout.strip():
                        text = result.stdout
                        
                        metadata = {
                            'file_size': os.path.getsize(file_path),
                            'file_type': 'doc'
                        }
                        
                        chunks = self.chunk_text(text)
                        
                        return {
                            'success': True,
                            'text': text,
                            'metadata': metadata,
                            'chunks': chunks
                        }
                    else:
                        return {
                            'success': False,
                            'error': 'antiword处理DOC文档失败'
                        }
                        
                except FileNotFoundError:
                    return {
                        'success': False,
                        'error': 'DOC文档处理需要安装 docx2txt 或 antiword。\n建议: pip install docx2txt'
                    }
                except Exception as e:
                    return {
                        'success': False,
                        'error': f'DOC文档处理失败: {str(e)}'
                    }
                    
        except Exception as e:
            return {
                'success': False,
                'error': f'DOC文档处理失败: {str(e)}'
            }
    
    def _extract_table_text(self, table) -> str:
        """提取表格中的文本"""
        table_text = []
        
        for row in table.rows:
            row_text = []
            for cell in row.cells:
                cell_text = cell.text.strip()
                if cell_text:
                    row_text.append(cell_text)
            
            if row_text:
                table_text.append(' | '.join(row_text))
        
        return '\n'.join(table_text)
    
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        将Word文档文本进行智能分块
        
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
                        current_chunk = overlap_text + "\n\n" + paragraph
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
        chunks = [chunk for chunk in chunks if len(chunk.strip()) > 30]
        
        logger.info(f"Word document text split into {len(chunks)} chunks")
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """清理Word文档提取的文本"""
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        
        # 移除常见的Word文档格式字符
        text = re.sub(r'\x0c', '', text)  # 移除换页符
        text = re.sub(r'\x07', '', text)  # 移除响铃符
        
        # 恢复段落结构
        text = re.sub(r'\n+', '\n\n', text)
        
        return text.strip()
    
    def _split_long_paragraph(self, paragraph: str, chunk_size: int, overlap: int) -> List[str]:
        """分割过长的段落"""
        chunks = []
        
        # 首先尝试按句子分割
        sentences = re.split(r'[.!?。！？]+', paragraph)
        
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
                    # 如果单个句子还是太长，按单词分割
                    if len(sentence) > chunk_size:
                        word_chunks = self._split_by_words(sentence, chunk_size, overlap)
                        chunks.extend(word_chunks[:-1])
                        current_chunk = word_chunks[-1] if word_chunks else ""
                    else:
                        current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += "。 " + sentence
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