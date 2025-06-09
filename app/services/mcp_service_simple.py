import asyncio
import logging
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import os

logger = logging.getLogger(__name__)

@dataclass
class MCPToolCall:
    """MCP工具调用结果"""
    tool_name: str
    arguments: Dict[str, Any]
    result: Optional[str] = None
    error: Optional[str] = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

class SimpleMCPService:
    """简化的MCP服务，支持文件和文件夹创建"""
    
    def __init__(self):
        self.tool_history = []
    
    def analyze_query(self, query: str) -> Dict[str, Any]:
        """分析查询意图"""
        analysis = {
            'intent': 'unknown',
            'confidence': 0.0,
            'suggested_tools': []
        }
        
        query_lower = query.lower()
        
        # 检测文件创建意图 - 优先级更高，因为文件创建更具体
        file_extensions = ['.txt', '.doc', '.docx', '.pdf', '.xls', '.xlsx', '.jpg', '.png', '.mp4', '.md']
        has_extension = any(ext in query_lower for ext in file_extensions)
        has_file_keyword = any(keyword in query_lower for keyword in ['文件', '.'])
        
        logger.info(f"分析查询意图: '{query}'")
        
        # 如果有文件扩展名或明确说是文件，则识别为创建文件
        if has_extension or (has_file_keyword and '文件夹' not in query_lower and '目录' not in query_lower):
            analysis['intent'] = 'create_file'
            analysis['confidence'] = 0.95
            analysis['suggested_tools'] = ['create_file_api']
            logger.info(f"识别为创建文件 - has_extension: {has_extension}, has_file_keyword: {has_file_keyword}")
        # 检测文件夹创建意图
        elif any(keyword in query_lower for keyword in ['文件夹', '目录']):
            analysis['intent'] = 'create_folder'
            analysis['confidence'] = 0.9
            analysis['suggested_tools'] = ['create_folder_api']
        # 如果只有创建/新建关键词，默认为文件夹
        elif any(keyword in query_lower for keyword in ['创建', '新建']):
            analysis['intent'] = 'create_folder'
            analysis['confidence'] = 0.7
            analysis['suggested_tools'] = ['create_folder_api']
        
        return analysis
    
    async def execute_tool_sequence(self, query: str) -> List[MCPToolCall]:
        """执行工具序列"""
        analysis = self.analyze_query(query)
        
        if analysis['intent'] == 'create_folder':
            return await self._handle_create_folder_request(query)
        elif analysis['intent'] == 'create_file':
            return await self._handle_create_file_request(query)
        
        return [MCPToolCall('unknown', {}, error="未识别的操作类型")]
    
    async def _handle_create_folder_request(self, query: str) -> List[MCPToolCall]:
        """处理创建文件夹请求"""
        try:
            # 解析文件夹名称
            import re
            
            # 改进的正则表达式模式，支持更多种表达方式
            parent_folder_patterns = [
                # 匹配"在XXX目录下创建YYY目录"
                r'在\s*([a-zA-Z0-9\u4e00-\u9fff\s]+?)\s*(?:目录|文件夹)\s*(?:下|中|里)\s*(?:创建|新建).*?(?:一个)?\s*([a-zA-Z0-9\u4e00-\u9fff]+)\s*(?:文件夹|目录)',
                # 匹配"在XXX下创建YYY目录"
                r'在\s*([a-zA-Z0-9\u4e00-\u9fff\s]+?)\s*(?:下|中|里)\s*(?:创建|新建).*?(?:一个)?\s*([a-zA-Z0-9\u4e00-\u9fff]+)\s*(?:文件夹|目录)',
                # 匹配"在XXX文件夹创建YYY"  
                r'在\s*([a-zA-Z0-9\u4e00-\u9fff\s]+?)\s*(?:文件夹|目录)\s*(?:创建|新建).*?(?:一个)?\s*([a-zA-Z0-9\u4e00-\u9fff]+)',
                # 匹配"XXX目录下创建YYY"
                r'([a-zA-Z0-9\u4e00-\u9fff\s]+?)\s*(?:目录|文件夹)\s*下\s*(?:创建|新建).*?(?:一个)?\s*([a-zA-Z0-9\u4e00-\u9fff]+)\s*(?:文件夹|目录)',
            ]
            
            parent_folder_name = None
            folder_name = None
            
            # 尝试匹配父目录模式
            for pattern in parent_folder_patterns:
                parent_match = re.search(pattern, query)
                if parent_match:
                    parent_folder_name = parent_match.group(1).strip()
                    folder_name = parent_match.group(2).strip()
                    logger.info(f"解析到父目录模式 - 父目录: '{parent_folder_name}', 新文件夹名: '{folder_name}' (模式: {pattern})")
                    break
            
            # 如果没有找到父目录模式，尝试简单模式
            if not folder_name:
                # 改进的简单模式匹配
                simple_patterns = [
                    r'(?:创建|新建)(?:新的|新|一个|个)?\s*([a-zA-Z0-9\u4e00-\u9fff]+)\s*(?:文件夹|目录)',  # 创建xxx文件夹
                    r'(?:创建|新建)(?:新的|新|一个|个)?\s*(?:文件夹|目录)\s*([a-zA-Z0-9\u4e00-\u9fff]+)',  # 创建文件夹xxx
                    r'(?:创建|新建).*?([a-zA-Z0-9\u4e00-\u9fff]+?)(?:\s*文件夹|\s*目录|\s*$)',  # 通用模式
                    r'([a-zA-Z0-9\u4e00-\u9fff]+)\s*(?:文件夹|目录)',  # 最简单的匹配
                ]
                
                for pattern in simple_patterns:
                    simple_match = re.search(pattern, query)
                    if simple_match:
                        folder_name = simple_match.group(1).strip()
                        if folder_name and len(folder_name) > 0 and folder_name not in ['创建', '新建', '一个', '新的', '新']:
                            logger.info(f"解析到简单模式 - 文件夹名: '{folder_name}' (使用模式: {pattern})")
                            break
                
                if not folder_name:
                    folder_name = "新文件夹"
                    logger.warning(f"无法解析文件夹名称，使用默认名称: {folder_name}")
            
            # 直接使用API创建文件夹
            return await self._create_folder_via_api(folder_name, parent_folder_name)
            
        except Exception as e:
            logger.error(f"处理创建文件夹请求失败: {e}")
            return [MCPToolCall('error', {}, error=str(e))]
    
    async def _create_folder_via_api(self, folder_name: str, parent_folder_name: str = None) -> List[MCPToolCall]:
        """通过后端API创建文件夹"""
        results = []
        try:
            logger.info(f"🚀 使用后端API创建文件夹: {folder_name}, 父目录: {parent_folder_name}")
            
            # 导入必要的模块
            from app.models import DocumentNode
            from app import db
            import uuid
            from datetime import datetime
            
            parent_id = None
            parent_info_msg = " (在根目录下)"
            
            # 如果指定了父目录，先查找父目录
            if parent_folder_name:
                logger.info(f"🔍 查找父目录: {parent_folder_name}")
                
                # 查找父目录（支持模糊匹配）
                parent_folder = db.session.query(DocumentNode).filter(
                    DocumentNode.type == 'folder',
                    DocumentNode.is_deleted == False,
                    DocumentNode.name.like(f'%{parent_folder_name}%')
                ).first()
                
                if parent_folder:
                    parent_id = parent_folder.id
                    parent_info_msg = f" (在 {parent_folder.name} 目录下)"
                    logger.info(f"✅ 找到父目录: {parent_folder.name} (ID: {parent_id})")
                else:
                    # 尝试精确匹配
                    parent_folder = db.session.query(DocumentNode).filter(
                        DocumentNode.type == 'folder',
                        DocumentNode.is_deleted == False,
                        DocumentNode.name == parent_folder_name
                    ).first()
                    
                    if parent_folder:
                        parent_id = parent_folder.id
                        parent_info_msg = f" (在 {parent_folder.name} 目录下)"
                        logger.info(f"✅ 精确匹配找到父目录: {parent_folder.name} (ID: {parent_id})")
                    else:
                        # 父目录不存在时，先在根目录创建父目录，再创建子目录
                        logger.warning(f"⚠️ 未找到父目录 '{parent_folder_name}'，将在根目录下创建 '{folder_name}' 文件夹")
                        
                        # 重置父目录信息，改为在根目录下创建
                        parent_folder_name = None
                        parent_id = None
                        parent_info_msg = f" (原计划在 {parent_folder_name} 目录下，但该目录不存在，已改为在根目录下创建)"
            
            # 检查是否已存在同名文件夹
            existing_folder = db.session.query(DocumentNode).filter(
                DocumentNode.name == folder_name,
                DocumentNode.type == 'folder',
                DocumentNode.parent_id == parent_id,
                DocumentNode.is_deleted == False
            ).first()
            
            if existing_folder:
                error_message = f"文件夹 '{folder_name}' 已存在于{('根目录' if parent_id is None else f'目录 {parent_folder_name}') }中"
                logger.warning(error_message)
                results.append(MCPToolCall(
                    'create_folder_api', 
                    {
                        'name': folder_name, 
                        'parent': parent_folder_name,
                        'action': 'refresh_tree'  # 即使有错误也尝试刷新
                    }, 
                    error=error_message
                ))
                return results
            
            # 创建新文件夹
            new_folder = DocumentNode(
                name=folder_name,
                file_path=f"virtual_folder_{folder_name}_{int(datetime.now().timestamp())}",
                file_type='folder',
                type='folder',
                file_size=0,
                parent_id=parent_id,  # 使用找到的父目录ID
                description=f"通过MCP API创建的文件夹",
                is_deleted=False,
                created_by='mcp_service'
            )
            
            # 保存到数据库
            db.session.add(new_folder)
            db.session.commit()
            
            result_message = f"✅ 成功创建文件夹 '{folder_name}'{parent_info_msg}"
            logger.info(result_message)
            
            results.append(MCPToolCall(
                'create_folder_api', 
                {
                    'name': folder_name, 
                    'parent': parent_folder_name, 
                    'parent_id': parent_id,
                    'folder_id': new_folder.id,
                    'action': 'refresh_tree'  # 通知前端刷新文档树
                }, 
                result=result_message
            ))
            
        except Exception as e:
            error_message = f"API创建文件夹失败: {str(e)}"
            logger.error(error_message)
            results.append(MCPToolCall(
                'create_folder_api', 
                {
                    'name': folder_name, 
                    'parent': parent_folder_name,
                    'action': 'refresh_tree'  # 即使失败也尝试刷新
                }, 
                error=error_message
            ))
        
        return results

    async def _handle_create_file_request(self, query: str) -> List[MCPToolCall]:
        """处理创建文件请求"""
        try:
            import re
            
            # 尝试匹配"在...下创建...文件"的模式
            parent_folder_pattern = r'在\s*([a-zA-Z0-9\u4e00-\u9fff\s]+?)(?:文件夹|目录|下|中|里)\s*(?:下|中|里)?\s*(?:创建|新建).*?(?:一个)?\s*([a-zA-Z0-9\u4e00-\u9fff._-]+\.[a-zA-Z0-9]+)\s*(?:文件)?'
            parent_match = re.search(parent_folder_pattern, query)
            
            if parent_match:
                parent_folder_name = parent_match.group(1).strip()
                file_name = parent_match.group(2).strip()
                logger.info(f"解析到父目录模式 - 父目录: '{parent_folder_name}', 新文件名: '{file_name}'")
            else:
                # 尝试匹配简单的"创建...文件"模式
                simple_patterns = [
                    r'(?:创建|新建)(?:新|一个|个)?\s*([a-zA-Z0-9\u4e00-\u9fff._-]+\.[a-zA-Z0-9]+)',  # 创建file.txt
                    r'(?:创建|新建).*?([a-zA-Z0-9\u4e00-\u9fff._-]+)\s*文件',  # 创建xxx文件
                    r'(?:创建|新建).*?文件.*?([a-zA-Z0-9\u4e00-\u9fff._-]+)',  # 创建文件xxx
                    r'创建\s*(?:一个)?\s*([a-zA-Z0-9\u4e00-\u9fff._-]+\.[a-zA-Z0-9]+)',  # 创建 readme.md
                ]
                
                file_name = None
                parent_folder_name = None
                
                for pattern in simple_patterns:
                    simple_match = re.search(pattern, query)
                    if simple_match:
                        file_name = simple_match.group(1).strip()
                        if file_name and len(file_name) > 0:
                            logger.info(f"解析到简单模式 - 文件名: '{file_name}' (使用模式: {pattern})")
                            break
                
                if not file_name:
                    file_name = "新文件.txt"
                    logger.warning(f"无法解析文件名称，使用默认名称: {file_name}")
                
                # 确保文件有扩展名
                if '.' not in file_name:
                    file_name = file_name + '.txt'
            
            # 解析文件内容
            file_content = self._extract_file_content(query, file_name)
            
            # 使用API创建文件
            return await self._create_file_via_api(file_name, parent_folder_name, file_content)
            
        except Exception as e:
            logger.error(f"处理创建文件请求失败: {e}")
            return [MCPToolCall('error', {}, error=str(e))]
    
    def _extract_file_content(self, query: str, file_name: str) -> str:
        """从查询中提取文件内容"""
        try:
            import re
            import os
            
            # 特殊处理静夜思
            if '静夜思' in file_name or '静夜思' in query:
                return """静夜思
李白

床前明月光，疑是地上霜。
举头望明月，低头思故乡。"""
            
            # 检查是否包含具体内容要求
            content_patterns = [
                r'(?:写上|写入|内容是|内容为|包含)[:：]?\s*["\'](.*?)["\']',  # 引号内容
                r'(?:写上|写入|内容是|内容为|包含)[:：]?\s*(.+?)(?:\s*(?:，|。|$))',  # 一般内容
                r'在文件中写上(.+?)(?:\s*(?:，|。|$))',  # 在文件中写上...
                r'文件内容[:：]?\s*(.+?)(?:\s*(?:，|。|$))',  # 文件内容：...
            ]
            
            for pattern in content_patterns:
                match = re.search(pattern, query)
                if match:
                    content = match.group(1).strip()
                    if content and len(content) > 0:
                        logger.info(f"提取到文件内容: '{content}'")
                        return content
            
            # 检查是否是代码文件，提供模板
            file_ext = os.path.splitext(file_name)[1].lower()
            if file_ext == '.py':
                return f'# {file_name}\n# 通过MCP创建的Python文件\n\nprint("Hello, World!")\n'
            elif file_ext == '.js':
                return f'// {file_name}\n// 通过MCP创建的JavaScript文件\n\nconsole.log("Hello, World!");\n'
            elif file_ext in ['.md', '.markdown']:
                return f'# {file_name}\n\n这是通过MCP创建的Markdown文件。\n\n## 说明\n\n您可以在此编辑内容。\n'
            elif file_ext == '.json':
                return '{\n  "name": "通过MCP创建的JSON文件",\n  "editable": true\n}'
            elif file_ext == '.html':
                return f'''<!DOCTYPE html>
<html>
<head>
    <title>{file_name}</title>
</head>
<body>
    <h1>通过MCP创建的HTML文件</h1>
    <p>您可以编辑此文件内容。</p>
</body>
</html>'''
            
            # 默认返回基本内容
            return f'这是通过MCP创建的 {file_name} 文件。\n\n您可以编辑此文件内容。\n'
            
        except Exception as e:
            logger.error(f"提取文件内容失败: {e}")
            return f'这是通过MCP创建的 {file_name} 文件。\n'
    
    async def _create_file_via_api(self, file_name: str, parent_folder_name: str = None, file_content: str = '') -> List[MCPToolCall]:
        """通过后端API创建文件"""
        results = []
        try:
            logger.info(f"🚀 使用后端API创建文件: {file_name}, 父目录: {parent_folder_name}")
            
            # 导入必要的模块
            from app.models import DocumentNode
            from app import db
            from datetime import datetime
            from config import Config
            import os
            import uuid
            
            parent_id = None
            
            # 如果指定了父目录，先查找父目录
            if parent_folder_name:
                logger.info(f"🔍 查找父目录: {parent_folder_name}")
                
                # 查找父目录（支持模糊匹配）
                parent_folder = db.session.query(DocumentNode).filter(
                    DocumentNode.type == 'folder',
                    DocumentNode.is_deleted == False,
                    DocumentNode.name.like(f'%{parent_folder_name}%')
                ).first()
                
                if parent_folder:
                    parent_id = parent_folder.id
                    logger.info(f"✅ 找到父目录: {parent_folder.name} (ID: {parent_id})")
                else:
                    # 尝试精确匹配
                    parent_folder = db.session.query(DocumentNode).filter(
                        DocumentNode.type == 'folder',
                        DocumentNode.is_deleted == False,
                        DocumentNode.name == parent_folder_name
                    ).first()
                    
                    if parent_folder:
                        parent_id = parent_folder.id
                        logger.info(f"✅ 精确匹配找到父目录: {parent_folder.name} (ID: {parent_id})")
                    else:
                        # 显示所有可用的文件夹供参考
                        available_folders = db.session.query(DocumentNode).filter(
                            DocumentNode.type == 'folder',
                            DocumentNode.is_deleted == False
                        ).all()
                        folder_names = [f.name for f in available_folders]
                        logger.error(f"❌ 未找到父目录 '{parent_folder_name}'")
                        
                        error_message = f"未找到指定的父目录 '{parent_folder_name}'。可用的文件夹: {', '.join(folder_names[:10])}{'...' if len(folder_names) > 10 else ''}"
                        results.append(MCPToolCall(
                            'create_file_api', 
                            {'name': file_name, 'parent': parent_folder_name}, 
                            error=error_message
                        ))
                        return results
            
            # 检查是否已存在同名文件
            existing_file = db.session.query(DocumentNode).filter(
                DocumentNode.name == file_name,
                DocumentNode.type == 'file',
                DocumentNode.parent_id == parent_id,
                DocumentNode.is_deleted == False
            ).first()
            
            if existing_file:
                error_message = f"文件 '{file_name}' 已存在于{('根目录' if parent_id is None else f'目录 {parent_folder_name}') }中"
                logger.warning(error_message)
                results.append(MCPToolCall(
                    'create_file_api', 
                    {'name': file_name, 'parent': parent_folder_name}, 
                    error=error_message
                ))
                return results
            
            # 获取文件扩展名
            file_ext = os.path.splitext(file_name)[1].lower()
            file_type = file_ext[1:] if file_ext else 'txt'  # 去掉点号
            
            # 创建真实的物理文件
            # 生成唯一文件名
            unique_filename = str(uuid.uuid4()) + (file_ext if file_ext else '.txt')
            
            # 确保uploads目录存在
            uploads_dir = Config.UPLOAD_FOLDER
            if not os.path.exists(uploads_dir):
                os.makedirs(uploads_dir)
            
            # 创建物理文件路径
            physical_path = os.path.join(uploads_dir, unique_filename)
            
            # 创建文件并写入内容
            with open(physical_path, 'w', encoding='utf-8') as f:
                f.write(file_content if file_content else '')  # 写入指定内容或空文件
            
            # 获取文件大小
            file_size = os.path.getsize(physical_path)
            
            # 创建新文件记录
            new_file = DocumentNode(
                name=file_name,
                file_path=physical_path,
                file_type=file_type,
                type='file',
                file_size=file_size,
                parent_id=parent_id,
                description=f"通过MCP API创建的{file_type.upper()}文件",
                is_deleted=False,
                created_by='mcp_service'
            )
            
            # 保存到数据库
            db.session.add(new_file)
            db.session.commit()
            
            parent_info = f" (在 {parent_folder_name} 目录下)" if parent_folder_name else " (在根目录下)"
            result_message = f"✅ 成功创建文件 '{file_name}'{parent_info}"
            logger.info(result_message)
            
            results.append(MCPToolCall(
                'create_file_api', 
                {
                    'name': file_name, 
                    'parent': parent_folder_name, 
                    'parent_id': parent_id,
                    'file_id': new_file.id,
                    'action': 'refresh_tree'  # 通知前端刷新文档树
                }, 
                result=result_message
            ))
            
        except Exception as e:
            error_message = f"API创建文件失败: {str(e)}"
            logger.error(error_message)
            results.append(MCPToolCall(
                'create_file_api', 
                {'name': file_name, 'parent': parent_folder_name}, 
                error=error_message
            ))
        
        return results

# 全局简化MCP服务实例
simple_mcp_service = SimpleMCPService() 