from .base_preview import BasePreviewService
import os
import logging
from datetime import datetime
import chardet
import mimetypes
import re

logger = logging.getLogger(__name__)

class TextPreviewService(BasePreviewService):
    """文本文件预览服务"""
    
    def __init__(self):
        super().__init__()
        self.supported_formats = ['txt', 'text', 'log', 'md', 'markdown', 'csv', 'json', 'xml', 'py', 'js', 'html', 'css', 'sql']
        self.max_content_length = 50000  # 最大内容长度，避免内存问题
    
    def extract_content(self, file_path, document_id=None):
        """提取文本文件内容"""
        # 检查是否是MCP创建的虚拟文件
        if file_path.startswith('mcp_created/'):
            return self._extract_mcp_content(file_path, document_id)
        
        if not self.validate_file(file_path):
            raise FileNotFoundError(f"文件不存在或无法读取: {file_path}")
        
        try:
            # 检测文件编码
            encoding = self._detect_encoding(file_path)
            
            # 读取文件内容
            with open(file_path, 'r', encoding=encoding, errors='ignore') as file:
                content = file.read()
            
            # 如果内容太长，截断并添加提示
            if len(content) > self.max_content_length:
                content = content[:self.max_content_length] + "\n\n... (内容已截断，完整内容请下载文件查看) ..."
                is_truncated = True
            else:
                is_truncated = False
            
            # 统计基本信息
            lines = content.count('\n') + 1 if content else 0
            words = len(content.split()) if content else 0
            chars = len(content)
            
            content_data = {
                'type': 'text',
                'content': content,
                'encoding': encoding,
                'is_truncated': is_truncated,
                'metadata': {
                    'lines': lines,
                    'words': words,
                    'characters': chars,
                    'file_type': self._get_file_type_description(file_path)
                }
            }
            
            logger.info(f"✅ 文本文件内容提取成功: {file_path}, 编码: {encoding}")
            return content_data
            
        except Exception as e:
            logger.error(f"❌ 文本文件内容提取失败: {file_path}, 错误: {str(e)}")
            raise
    
    def _extract_mcp_content(self, file_path, document_id):
        """提取MCP创建的文件内容"""
        try:
            logger.info(f"🔍 处理MCP文件: {file_path}")
            
            # 导入模型
            from app.models.document_models import DocumentNode, DocumentContent
            from app import db
            
            if document_id:
                # 使用document_id查找
                document = db.session.query(DocumentNode).filter_by(
                    id=document_id,
                    is_deleted=False
                ).first()
            else:
                # 使用file_path查找
                document = db.session.query(DocumentNode).filter_by(
                    file_path=file_path,
                    is_deleted=False
                ).first()
                
            if not document:
                raise FileNotFoundError(f"MCP文件不存在: {file_path}")
            
            # 检查虚拟文件是否存在于文件系统中
            import os
            full_virtual_path = os.path.join('uploads', file_path)
            content = ""
            
            if os.path.exists(full_virtual_path):
                # 文件存在于文件系统中，尝试读取
                logger.info(f"📁 虚拟文件存在于文件系统: {full_virtual_path}")
                
                file_ext = document.file_type.lower()
                if file_ext in ['pdf', 'xlsx', 'docx']:
                    # 对于二进制格式，从数据库获取文本内容
                    content_record = db.session.query(DocumentContent).filter_by(
                        document_id=document.id
                    ).first()
                    
                    if content_record and content_record.content_text:
                        content = content_record.content_text
                    else:
                        content = f"[{file_ext.upper()}文档] 原始内容请下载文件查看"
                        
                    # 添加下载链接信息
                    content += f"\n\n💾 文件已生成为 {file_ext.upper()} 格式，可通过下载功能获取完整文档。"
                    
                else:
                    # 文本格式，直接读取文件
                    try:
                        with open(full_virtual_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                    except UnicodeDecodeError:
                        # 尝试其他编码
                        for encoding in ['gbk', 'gb2312', 'latin1']:
                            try:
                                with open(full_virtual_path, 'r', encoding=encoding) as f:
                                    content = f.read()
                                break
                            except:
                                continue
            else:
                # 文件不存在于文件系统中，从数据库读取
                logger.info(f"💾 从数据库读取MCP文件内容: {file_path}")
                
                content_record = db.session.query(DocumentContent).filter_by(
                    document_id=document.id
                ).first()
                
                if content_record and content_record.content_text:
                    content = content_record.content_text
                else:
                    content = ""
            
            # 如果内容太长，截断并添加提示
            if len(content) > self.max_content_length:
                content = content[:self.max_content_length] + "\n\n... (内容已截断，完整内容请下载文件查看) ..."
                is_truncated = True
            else:
                is_truncated = False
            
            # 统计基本信息
            lines = content.count('\n') + 1 if content else 0
            words = len(content.split()) if content else 0
            chars = len(content)
            
            # 根据文件类型设置描述
            file_type_desc = {
                'txt': '文本文档',
                'pdf': 'PDF文档',
                'xlsx': 'Excel工作簿',
                'docx': 'Word文档'
            }.get(document.file_type, '生成文档')
            
            content_data = {
                'type': 'text',
                'content': content,
                'encoding': 'utf-8',
                'is_truncated': is_truncated,
                'metadata': {
                    'lines': lines,
                    'words': words,
                    'characters': chars,
                    'file_type': file_type_desc,
                    'source': 'mcp_created',
                    'format': document.file_type,
                    'has_binary_file': os.path.exists(full_virtual_path),
                    'mime_type': document.mime_type
                }
            }
            
            logger.info(f"✅ MCP文件内容提取成功: {file_path}, 格式: {document.file_type}, 字符数: {chars}")
            return content_data
            
        except Exception as e:
            logger.error(f"❌ MCP文件内容提取失败: {file_path}, 错误: {str(e)}")
            raise
    
    def _detect_encoding(self, file_path):
        """检测文件编码"""
        try:
            # 读取文件的前几个字节来检测编码
            with open(file_path, 'rb') as file:
                raw_data = file.read(10000)  # 读取前10KB
            
            # 使用chardet检测编码
            detected = chardet.detect(raw_data)
            encoding = detected.get('encoding', 'utf-8')
            confidence = detected.get('confidence', 0)
            
            # 如果置信度太低，使用常见编码
            if confidence < 0.7:
                # 尝试常见的中文编码
                for enc in ['utf-8', 'gbk', 'gb2312', 'big5', 'utf-16']:
                    try:
                        with open(file_path, 'r', encoding=enc) as f:
                            f.read(1000)  # 尝试读取一小部分
                        encoding = enc
                        break
                    except (UnicodeDecodeError, UnicodeError):
                        continue
            
            # 确保使用安全的编码
            if encoding is None or encoding.lower() in ['ascii']:
                encoding = 'utf-8'
            
            return encoding
            
        except Exception as e:
            logger.warning(f"编码检测失败，使用默认编码UTF-8: {file_path}, 错误: {str(e)}")
            return 'utf-8'
    
    def _get_file_type_description(self, file_path):
        """获取文件类型描述"""
        ext = os.path.splitext(file_path)[1].lower()
        
        type_descriptions = {
            '.txt': '纯文本文件',
            '.log': '日志文件',
            '.md': 'Markdown文档',
            '.markdown': 'Markdown文档',
            '.csv': 'CSV数据文件',
            '.json': 'JSON数据文件',
            '.xml': 'XML文档',
            '.py': 'Python源代码',
            '.js': 'JavaScript源代码',
            '.html': 'HTML网页文件',
            '.htm': 'HTML网页文件',
            '.css': 'CSS样式表',
            '.sql': 'SQL脚本文件'
        }
        
        return type_descriptions.get(ext, '文本文件')
    
    def get_metadata(self, file_path):
        """获取文本文件元数据"""
        if not self.validate_file(file_path):
            raise FileNotFoundError(f"文件不存在或无法读取: {file_path}")
        
        try:
            # 基本文件信息
            file_stats = os.stat(file_path)
            metadata = {
                'file_size': file_stats.st_size,
                'file_size_formatted': self.format_file_size(file_stats.st_size),
                'file_type': self._get_file_type_description(file_path),
                'last_modified': datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                'created': datetime.fromtimestamp(file_stats.st_ctime).isoformat()
            }
            
            # 检测编码
            encoding = self._detect_encoding(file_path)
            metadata['encoding'] = encoding
            
            # 获取MIME类型
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type:
                metadata['mime_type'] = mime_type
            
            # 分析文件内容
            try:
                with open(file_path, 'r', encoding=encoding, errors='ignore') as file:
                    content = file.read()
                
                # 统计信息
                lines = content.count('\n') + 1 if content else 0
                words = len(content.split()) if content else 0
                chars = len(content)
                chars_no_spaces = len(content.replace(' ', '').replace('\n', '').replace('\t', ''))
                
                metadata.update({
                    'lines': lines,
                    'words': words,
                    'characters': chars,
                    'characters_no_spaces': chars_no_spaces,
                    'is_empty': chars == 0,
                    'estimated_read_time': self._estimate_read_time(words)
                })
                
                # 检查是否为空行较多
                if lines > 1:
                    empty_lines = content.count('\n\n') + content.count('\n \n')
                    metadata['empty_lines'] = empty_lines
                    metadata['content_density'] = round((lines - empty_lines) / lines * 100, 2)
                
                # 文件格式特定分析
                ext = os.path.splitext(file_path)[1].lower()
                if ext == '.csv':
                    metadata.update(self._analyze_csv_content(content))
                elif ext == '.json':
                    metadata.update(self._analyze_json_content(content))
                elif ext in ['.py', '.js', '.html', '.css', '.sql']:
                    metadata.update(self._analyze_code_content(content, ext))
                
            except Exception as e:
                logger.warning(f"无法分析文件内容: {file_path}, 错误: {str(e)}")
                metadata['content_analysis_error'] = str(e)
            
            return metadata
            
        except Exception as e:
            logger.error(f"获取文本文件元数据失败: {file_path}, 错误: {str(e)}")
            return {
                'file_size': self.get_file_size(file_path),
                'file_size_formatted': self.format_file_size(self.get_file_size(file_path)),
                'file_type': self._get_file_type_description(file_path),
                'last_modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
                'error': str(e)
            }
    
    def _estimate_read_time(self, word_count):
        """估算阅读时间（按每分钟250词计算）"""
        if word_count == 0:
            return "0分钟"
        
        minutes = max(1, round(word_count / 250))
        if minutes < 60:
            return f"{minutes}分钟"
        else:
            hours = minutes // 60
            remaining_minutes = minutes % 60
            if remaining_minutes == 0:
                return f"{hours}小时"
            else:
                return f"{hours}小时{remaining_minutes}分钟"
    
    def _analyze_csv_content(self, content):
        """分析CSV文件内容"""
        try:
            lines = content.strip().split('\n')
            if not lines:
                return {}
            
            # 估算列数（基于第一行）
            first_line = lines[0]
            comma_count = first_line.count(',')
            semicolon_count = first_line.count(';')
            tab_count = first_line.count('\t')
            
            # 判断分隔符
            if comma_count > semicolon_count and comma_count > tab_count:
                separator = ','
                columns = comma_count + 1
            elif semicolon_count > tab_count:
                separator = ';'
                columns = semicolon_count + 1
            elif tab_count > 0:
                separator = '\t'
                columns = tab_count + 1
            else:
                separator = ','
                columns = 1
            
            return {
                'csv_rows': len(lines),
                'csv_columns': columns,
                'csv_separator': separator,
                'has_header': True  # 假设有标题行
            }
        except:
            return {}
    
    def _analyze_json_content(self, content):
        """分析JSON文件内容"""
        try:
            import json
            data = json.loads(content)
            
            analysis = {'json_valid': True}
            
            if isinstance(data, dict):
                analysis['json_type'] = '对象'
                analysis['json_keys'] = len(data.keys())
            elif isinstance(data, list):
                analysis['json_type'] = '数组'
                analysis['json_items'] = len(data)
            else:
                analysis['json_type'] = '简单值'
            
            return analysis
        except:
            return {'json_valid': False}
    
    def _analyze_code_content(self, content, extension):
        """分析代码文件内容"""
        try:
            lines = content.split('\n')
            code_lines = 0
            comment_lines = 0
            blank_lines = 0
            
            # 简单的代码分析
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    blank_lines += 1
                elif self._is_comment_line(stripped, extension):
                    comment_lines += 1
                else:
                    code_lines += 1
            
            total_lines = len(lines)
            return {
                'code_lines': code_lines,
                'comment_lines': comment_lines,
                'blank_lines': blank_lines,
                'code_ratio': round(code_lines / total_lines * 100, 2) if total_lines > 0 else 0
            }
        except:
            return {}
    
    def _is_comment_line(self, line, extension):
        """判断是否为注释行"""
        if extension == '.py':
            return line.startswith('#')
        elif extension == '.js':
            return line.startswith('//') or line.startswith('/*') or line.startswith('*')
        elif extension in ['.html', '.htm']:
            return '<!--' in line
        elif extension == '.css':
            return line.startswith('/*') or line.startswith('*')
        elif extension == '.sql':
            return line.startswith('--') or line.startswith('/*')
        return False
    
    def generate_thumbnail(self, file_path, output_path=None, size=(200, 200)):
        """文本文件不支持缩略图生成"""
        return None
    
    def _process_hyperlinks(self, content):
        """处理文档内容中的超链接标记"""
        try:
            # 导入所需模块
            from app.models.document_models import DocumentNode
            from app import db
            
            # 处理[LINK:文件名:document_id]格式的超链接
            def replace_link(match):
                file_name = match.group(1)
                doc_id = match.group(2)
                
                try:
                    # 验证文档是否存在
                    doc = db.session.query(DocumentNode).filter_by(
                        id=int(doc_id),
                        is_deleted=False
                    ).first()
                    
                    if doc:
                        # 创建可点击的HTML链接
                        return f'<a href="#" class="file-name-link" onclick="selectFileFromChat({doc_id}); return false;" title="点击定位并预览文件">{file_name}</a>'
                    else:
                        # 如果文档不存在，返回普通文本
                        return file_name
                except (ValueError, TypeError):
                    # 如果document_id无效，返回普通文本
                    return file_name
            
            # 匹配[LINK:文件名:document_id]格式
            link_pattern = r'\[LINK:([^:]+):(\d+)\]'
            processed_content = re.sub(link_pattern, replace_link, content)
            
            # 处理[FILE:文件名:document_id]格式（作为备用格式）
            file_pattern = r'\[FILE:([^:]+):(\d+)\]'
            processed_content = re.sub(file_pattern, replace_link, processed_content)
            
            return processed_content
            
        except Exception as e:
            logger.error(f"处理超链接失败: {e}")
            return content 