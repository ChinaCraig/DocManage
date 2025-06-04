"""
PDF文档向量化器
专门处理PDF文件的内容提取和向量化，支持图片内容识别
"""

import logging
import os
import re
import tempfile
import fitz  # PyMuPDF
from typing import List, Dict, Any, Optional
from .base_vectorizer import BaseVectorizer
from ..image_recognition_service import ImageRecognitionService

logger = logging.getLogger(__name__)

class PDFVectorizer(BaseVectorizer):
    """PDF文档向量化器，支持文本和图片内容提取"""
    
    def __init__(self):
        """初始化PDF向量化器"""
        super().__init__()
        self.file_type = "pdf"
        self.recognition_service = ImageRecognitionService()
    
    def get_supported_extensions(self) -> List[str]:
        """获取支持的文件扩展名"""
        return ['.pdf']
    
    def extract_text(self, file_path: str, extract_images: bool = True, recognition_options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        从PDF文件提取文本内容和图片内容
        
        Args:
            file_path: PDF文件路径
            extract_images: 是否提取和识别图片内容
            recognition_options: 图片识别选项
            
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
            
            # 设置默认识别选项
            if recognition_options is None:
                recognition_options = {
                    'engine': 'auto',
                    'languages': ['zh', 'en']
                }
            
            # 使用PyMuPDF提取内容（支持图片提取）
            try:
                result = self._extract_with_pymupdf(file_path, extract_images, recognition_options)
                if result['success']:
                    return result
            except ImportError:
                logger.warning("PyMuPDF not available, falling back to PyPDF2")
            except Exception as e:
                logger.warning(f"PyMuPDF extraction failed: {e}, falling back to PyPDF2")
            
            # 备选方案：使用PyPDF2（不支持图片）
            return self._extract_with_pypdf2(file_path)
                
        except Exception as e:
            logger.error(f"PDF text extraction failed: {e}")
            return {
                'success': False,
                'error': f'PDF文本提取失败: {str(e)}'
            }
    
    def _extract_with_pymupdf(self, file_path: str, extract_images: bool, recognition_options: Dict[str, Any]) -> Dict[str, Any]:
        """使用PyMuPDF进行内容提取（支持图片）"""
        doc = fitz.open(file_path)
        
        # 基本元数据
        metadata = {
            'total_pages': len(doc),
            'file_size': os.path.getsize(file_path),
            'file_type': 'pdf',
            'extraction_method': 'pymupdf'
        }
        
        # PDF元数据
        pdf_metadata = doc.metadata
        if pdf_metadata:
            metadata.update({
                'title': pdf_metadata.get('title', ''),
                'author': pdf_metadata.get('author', ''),
                'subject': pdf_metadata.get('subject', ''),
                'creator': pdf_metadata.get('creator', ''),
                'producer': pdf_metadata.get('producer', ''),
                'creation_date': pdf_metadata.get('creationDate', ''),
                'modification_date': pdf_metadata.get('modDate', '')
            })
        
        pages_content = []
        all_text_parts = []
        image_contents = []
        total_images = 0
        
        # 逐页处理
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_data = {
                'page': page_num + 1,
                'text': '',
                'images': [],
                'image_texts': []
            }
            
            # 提取文本
            try:
                page_text = page.get_text()
                if page_text.strip():
                    page_data['text'] = page_text.strip()
                    all_text_parts.append(f"=== 第{page_num + 1}页 ===\n{page_text.strip()}")
            except Exception as e:
                logger.warning(f"Failed to extract text from page {page_num + 1}: {e}")
            
            # 提取图片
            if extract_images:
                try:
                    image_list = page.get_images()
                    for img_index, img in enumerate(image_list):
                        try:
                            # 获取图片数据
                            xref = img[0]
                            pix = fitz.Pixmap(doc, xref)
                            
                            # 跳过CMYK图片
                            if pix.n - pix.alpha < 4:
                                # 保存图片到临时文件
                                img_data = pix.tobytes("png")
                                
                                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                                    temp_file.write(img_data)
                                    temp_img_path = temp_file.name
                                
                                try:
                                    # 识别图片内容
                                    recognition_result = self.recognition_service.recognize_image(
                                        temp_img_path,
                                        engine=recognition_options.get('engine', 'auto'),
                                        languages=recognition_options.get('languages', ['zh', 'en'])
                                    )
                                    
                                    if recognition_result.get('success'):
                                        img_text = recognition_result.get('text', '').strip()
                                        if img_text:
                                            image_text_content = f"=== 第{page_num + 1}页图片{img_index + 1} ===\n{img_text}"
                                            page_data['image_texts'].append({
                                                'index': img_index + 1,
                                                'text': img_text,
                                                'confidence': recognition_result.get('confidence', 0.0),
                                                'engine': recognition_result.get('engine_used', '未知')
                                            })
                                            image_contents.append(image_text_content)
                                            total_images += 1
                                    
                                    page_data['images'].append({
                                        'index': img_index + 1,
                                        'width': pix.width,
                                        'height': pix.height,
                                        'has_text': bool(recognition_result.get('text', '').strip()),
                                        'recognition_result': recognition_result
                                    })
                                    
                                finally:
                                    # 清理临时文件
                                    try:
                                        os.unlink(temp_img_path)
                                    except:
                                        pass
                            
                            pix = None
                        except Exception as e:
                            logger.warning(f"Failed to process image {img_index} on page {page_num + 1}: {e}")
                            
                except Exception as e:
                    logger.warning(f"Failed to extract images from page {page_num + 1}: {e}")
            
            pages_content.append(page_data)
        
        doc.close()
        
        # 构建完整文本内容
        content_parts = []
        
        # 基本信息
        filename = os.path.basename(file_path)
        content_parts.append(f"PDF文档: {filename}")
        content_parts.append(f"总页数: {metadata['total_pages']}")
        content_parts.append(f"文件大小: {self._format_file_size(metadata['file_size'])}")
        
        if metadata.get('title'):
            content_parts.append(f"标题: {metadata['title']}")
        if metadata.get('author'):
            content_parts.append(f"作者: {metadata['author']}")
        if metadata.get('subject'):
            content_parts.append(f"主题: {metadata['subject']}")
        
        # 文本内容
        if all_text_parts:
            content_parts.append(f"\n=== 文档文本内容 ===")
            content_parts.extend(all_text_parts)
        
        # 图片内容
        if image_contents:
            content_parts.append(f"\n=== 图片识别内容 ===")
            content_parts.append(f"共识别到 {total_images} 张包含文字的图片:")
            content_parts.extend(image_contents)
        
        # 关键词提取
        full_text = '\n'.join(all_text_parts + image_contents)
        keywords = self._extract_keywords(full_text, filename, metadata)
        if keywords:
            content_parts.append(f"\n=== 检索关键词 ===")
            content_parts.append(" ".join(keywords))
        
        comprehensive_text = '\n'.join(content_parts)
        
        # 更新元数据
        metadata.update({
            'total_images': len([img for page in pages_content for img in page.get('images', [])]),
            'images_with_text': total_images,
            'text_pages': len([page for page in pages_content if page.get('text')]),
            'has_images': total_images > 0,
            'content_length': len(comprehensive_text)
        })
        
        if not comprehensive_text.strip():
            return {
                'success': False,
                'error': 'PDF文件中没有可提取的文本或图片内容'
            }
        
        # 进行文本分块
        chunks = self.chunk_text(comprehensive_text)
        
        return {
            'success': True,
            'text': comprehensive_text,
            'metadata': metadata,
            'chunks': chunks,
            'pages_content': pages_content,
            'file_type': 'pdf'
        }
    
    def _extract_with_pypdf2(self, file_path: str) -> Dict[str, Any]:
        """使用PyPDF2进行基本文本提取（备选方案）"""
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
                    'file_type': 'pdf',
                    'extraction_method': 'pypdf2'
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
                        metadata['extraction_method'] = 'pdfplumber'
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
    
    def _extract_keywords(self, text: str, filename: str, metadata: Dict) -> List[str]:
        """提取关键词用于检索优化"""
        keywords = []
        
        # 文件名关键词
        base_name = os.path.splitext(filename)[0]
        filename_words = base_name.replace('_', ' ').replace('-', ' ').split()
        keywords.extend([word for word in filename_words if len(word) > 1])
        
        # 元数据关键词
        for key in ['title', 'author', 'subject']:
            value = metadata.get(key, '')
            if value and isinstance(value, str):
                words = value.replace('_', ' ').replace('-', ' ').split()
                keywords.extend([word for word in words if len(word) > 1])
        
        # 文本内容关键词
        if text:
            import re
            # 提取中文词汇（2个或以上连续汉字）
            chinese_words = re.findall(r'[\u4e00-\u9fff]{2,}', text)
            keywords.extend(chinese_words[:50])  # 限制数量
            
            # 提取英文单词（2个或以上字符）
            english_words = re.findall(r'[a-zA-Z]{2,}', text)
            keywords.extend(english_words[:50])  # 限制数量
            
            # 提取数字模式
            numbers = re.findall(r'\d{2,}', text)
            keywords.extend(numbers[:20])  # 限制数量
            
            # 提取可能的车牌号
            license_plates = re.findall(r'[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领][A-Z][A-Z0-9]{5}', text)
            keywords.extend(license_plates)
        
        # 去重并过滤
        unique_keywords = list(set(keywords))
        return [kw for kw in unique_keywords if len(kw) > 1 and not kw.isspace()][:100]  # 限制总数
    
    def _format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f}MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"
    
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
        
        # 首先按重要段落分隔符分割
        major_sections = re.split(r'\n\s*===\s*[^=]+\s*===\s*\n', text)
        
        for section in major_sections:
            section = section.strip()
            if not section:
                continue
            
            # 如果段落本身就很长，需要进一步分割
            if len(section) <= chunk_size:
                chunks.append(section)
            else:
                # 按段落分割
                paragraphs = re.split(r'\n\s*\n', section)
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
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
        
        logger.info(f"PDF text split into {len(chunks)} chunks")
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """清理PDF文本"""
        # 移除多余的空白字符
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        # 移除行末的多余空格
        text = re.sub(r' +\n', '\n', text)
        # 移除多余的空格
        text = re.sub(r' {2,}', ' ', text)
        return text.strip()
    
    def _split_long_paragraph(self, paragraph: str, chunk_size: int, overlap: int) -> List[str]:
        """分割过长的段落"""
        chunks = []
        
        # 首先尝试按句子分割
        sentences = re.split(r'[.。!！?？]+', paragraph)
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
                        current_chunk = overlap_text + sentence
                    else:
                        current_chunk = sentence
                else:
                    # 如果单个句子就超过了chunk_size，按单词分割
                    if len(sentence) > chunk_size:
                        word_chunks = self._split_by_words(sentence, chunk_size, overlap)
                        chunks.extend(word_chunks[:-1])
                        current_chunk = word_chunks[-1] if word_chunks else ""
                    else:
                        current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += sentence
                else:
                    current_chunk = sentence
        
        # 添加最后一个块
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [paragraph]
    
    def _split_by_words(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """按单词分割文本"""
        words = text.split()
        chunks = []
        current_chunk = ""
        
        for word in words:
            if len(current_chunk) + len(word) + 1 > chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    
                    # 处理重叠
                    if overlap > 0:
                        chunk_words = current_chunk.split()
                        overlap_words = chunk_words[-overlap//10:] if len(chunk_words) > overlap//10 else chunk_words
                        current_chunk = " ".join(overlap_words) + " " + word
                    else:
                        current_chunk = word
                else:
                    current_chunk = word
            else:
                if current_chunk:
                    current_chunk += " " + word
                else:
                    current_chunk = word
        
        # 添加最后一个块
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [text] 