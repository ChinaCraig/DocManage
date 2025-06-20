"""
MCP工具执行器
基于LLM分析结果执行具体的MCP工具
"""

import asyncio
import logging
import time
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from .mcp.servers.mcp_installer import MCPInstaller

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

class MCPToolExecutor:
    """基于LLM分析结果的MCP工具执行器"""
    
    def __init__(self, mcp_manager=None):
        self.tool_history = []
        self.installer = MCPInstaller()
        self.mcp_manager = mcp_manager
    
    async def execute_tools_from_analysis(self, query: str, tool_analysis: Dict[str, Any]) -> List[MCPToolCall]:
        """根据LLM分析结果执行工具"""
        try:
            tools_needed = tool_analysis.get('tools_needed', [])
            execution_sequence = tool_analysis.get('execution_sequence', [])
            
            logger.info(f"开始执行MCP工具: {tools_needed}")
            
            # 步骤1: 检查并安装所需的MCP服务
            logger.info("步骤1: 检查并安装所需的MCP服务")
            install_result = await self.installer.check_and_install_required_services(tools_needed)
            
            if not install_result["success"]:
                logger.error(f"MCP服务安装失败: {install_result}")
                return [MCPToolCall(
                    'service_installation_error', 
                    install_result,
                    error=f"无法安装所需的MCP服务: {install_result.get('failed_services', [])}"
                )]
            
            if install_result["installed_services"]:
                logger.info(f"成功安装MCP服务: {install_result['installed_services']}")
            
            if install_result["skipped_services"]:
                logger.info(f"跳过的MCP服务: {install_result['skipped_services']}")
            
            # 步骤2: 执行工具
            logger.info("步骤2: 执行MCP工具")
            results = []
            
            # 如果有执行序列，按序列执行
            if execution_sequence:
                for tool_step in execution_sequence:
                    tool_name = tool_step.get('tool_name')
                    if tool_name in tools_needed:
                        result = await self._execute_single_tool(tool_name, query, tool_step)
                        results.append(result)
            else:
                # 否则按工具列表执行
                for tool_name in tools_needed:
                    if tool_name != 'unknown':
                        result = await self._execute_single_tool(tool_name, query)
                        results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"工具执行失败: {e}")
            return [MCPToolCall('error', {}, error=str(e))]
    
    async def _execute_single_tool(self, tool_name: str, query: str, tool_step: Dict = None) -> MCPToolCall:
        """执行单个工具"""
        try:
            if tool_name == 'create_file':
                return await self._execute_create_file(query, tool_step)
            elif tool_name == 'create_folder':
                return await self._execute_create_folder(query, tool_step)
            else:
                return MCPToolCall(
                    tool_name=tool_name,
                    arguments={},
                    error=f"工具 {tool_name} 暂未实现"
                )
                
        except Exception as e:
            logger.error(f"执行工具 {tool_name} 失败: {e}")
            return MCPToolCall(
                tool_name=tool_name,
                arguments={},
                error=str(e)
            )
    
    async def _execute_create_file(self, query: str, tool_step: Dict = None) -> MCPToolCall:
        """执行创建文件工具"""
        try:
            # 优先使用LLM分析的参数
            if tool_step and 'parameters' in tool_step:
                llm_params = tool_step['parameters']
                logger.info(f"使用LLM分析的参数: {llm_params}")
                
                file_name = llm_params.get('file_name')
                parent_folder = llm_params.get('parent_folder')
                content = llm_params.get('content', '')
                
                # 验证参数有效性 - 检查是否是描述性文字
                if file_name and not any(desc in file_name.lower() for desc in ['从查询中提取', '提取的', '描述', '参数值描述']):
                    logger.info(f"🚀 使用LLM分析结果创建文件: {file_name}, 父目录: {parent_folder}")
                    return await self._create_file_via_api(file_name, parent_folder, content)
            
            # 降级到正则表达式分析
            logger.info("LLM参数无效，降级到正则表达式分析")
            file_info = self._extract_file_info(query)
            
            return await self._create_file_via_api(
                file_info['file_name'],
                file_info.get('parent_folder'),
                file_info.get('content', '')
            )
            
        except Exception as e:
            logger.error(f"创建文件失败: {e}")
            return MCPToolCall('create_file', {}, error=str(e))
    
    async def _execute_create_folder(self, query: str, tool_step: Dict = None) -> MCPToolCall:
        """执行创建文件夹工具"""
        try:
            # 优先使用LLM分析的参数
            if tool_step and 'parameters' in tool_step:
                llm_params = tool_step['parameters']
                logger.info(f"使用LLM分析的参数: {llm_params}")
                
                folder_name = llm_params.get('folder_name')
                parent_folder = llm_params.get('parent_folder')
                
                # 验证参数有效性 - 检查是否是描述性文字
                if folder_name and not any(desc in folder_name.lower() for desc in ['从查询中提取', '提取的', '描述', '参数值描述']):
                    logger.info(f"🚀 使用LLM分析结果创建文件夹: {folder_name}, 父目录: {parent_folder}")
                    return await self._create_folder_via_api(folder_name, parent_folder)
            
            # 降级到正则表达式分析
            logger.info("LLM参数无效，降级到正则表达式分析")
            folder_info = self._extract_folder_info(query)
            
            return await self._create_folder_via_api(
                folder_info['folder_name'],
                folder_info.get('parent_folder')
            )
            
        except Exception as e:
            logger.error(f"创建文件夹失败: {e}")
            return MCPToolCall('create_folder', {}, error=str(e))
    
    def _extract_file_info(self, query: str) -> Dict[str, str]:
        """从查询中提取文件信息"""
        file_info = {
            'file_name': '新文件.txt',
            'content': '',
            'parent_folder': None
        }
        
        # 提取文件名
        file_patterns = [
            r'(?:创建|生成|新建).*?([a-zA-Z0-9\u4e00-\u9fff]+\.[a-zA-Z0-9]+)',  # 文件名.扩展名
            r'([a-zA-Z0-9\u4e00-\u9fff]+\.[a-zA-Z0-9]+)',  # 直接匹配文件名
        ]
        
        for pattern in file_patterns:
            match = re.search(pattern, query)
            if match:
                file_info['file_name'] = match.group(1)
                break
        
        # 提取父目录
        parent_patterns = [
            r'在\s*([a-zA-Z0-9\u4e00-\u9fff]+)\s*(?:文件夹|目录|下)',
            r'([a-zA-Z0-9\u4e00-\u9fff]+)\s*(?:文件夹|目录)\s*下',
        ]
        
        for pattern in parent_patterns:
            match = re.search(pattern, query)
            if match:
                file_info['parent_folder'] = match.group(1)
                break
        
        # 提取内容描述
        content_patterns = [
            r'内容(?:是|为)([^，。]+)',
            r'写(?:入|上)([^，。]+)',
        ]
        
        for pattern in content_patterns:
            match = re.search(pattern, query)
            if match:
                file_info['content'] = match.group(1).strip()
                break
        
        logger.info(f"提取文件信息: {file_info}")
        return file_info
    
    def _extract_folder_info(self, query: str) -> Dict[str, str]:
        """从查询中提取文件夹信息"""
        folder_info = {
            'folder_name': '新文件夹',
            'parent_folder': None
        }
        
        # 改进的文件夹名称提取
        folder_patterns = [
            # 匹配"在XXX目录下创建YYY目录"
            r'在\s*([a-zA-Z0-9\u4e00-\u9fff\s]+?)\s*(?:目录|文件夹)\s*(?:下|中|里)\s*(?:创建|新建|添加).*?(?:一个)?\s*([a-zA-Z0-9\u4e00-\u9fff]+)\s*(?:文件夹|目录)',
            # 匹配"在XXX下创建YYY目录"  
            r'在\s*([a-zA-Z0-9\u4e00-\u9fff\s]+?)\s*(?:下|中|里)\s*(?:创建|新建|添加).*?(?:一个)?\s*([a-zA-Z0-9\u4e00-\u9fff]+)\s*(?:文件夹|目录)',
            # 匹配"XXX目录下创建YYY"
            r'([a-zA-Z0-9\u4e00-\u9fff\s]+?)\s*(?:目录|文件夹)\s*下\s*(?:创建|新建|添加).*?(?:一个)?\s*([a-zA-Z0-9\u4e00-\u9fff]+)\s*(?:文件夹|目录)',
        ]
        
        # 尝试匹配父目录模式
        for pattern in folder_patterns:
            match = re.search(pattern, query)
            if match:
                folder_info['parent_folder'] = match.group(1).strip()
                folder_info['folder_name'] = match.group(2).strip()
                logger.info(f"解析到父目录模式 - 父目录: '{folder_info['parent_folder']}', 新文件夹名: '{folder_info['folder_name']}' (模式: {pattern})")
                return folder_info
        
        # 如果没有找到父目录模式，尝试简单模式
        simple_patterns = [
            r'(?:创建|新建|添加)(?:新的|新|一个|个)?\s*([a-zA-Z0-9\u4e00-\u9fff]+)\s*(?:文件夹|目录)',  # 创建xxx文件夹
            r'(?:创建|新建|添加)(?:新的|新|一个|个)?\s*(?:文件夹|目录)\s*([a-zA-Z0-9\u4e00-\u9fff]+)',  # 创建文件夹xxx
            r'([a-zA-Z0-9\u4e00-\u9fff]+)\s*(?:文件夹|目录)',  # 最简单的匹配
        ]
        
        for pattern in simple_patterns:
            match = re.search(pattern, query)
            if match:
                folder_name = match.group(1).strip()
                if folder_name and len(folder_name) > 0 and folder_name not in ['创建', '新建', '添加', '一个', '新的', '新', '帮我', '在', '下']:
                    folder_info['folder_name'] = folder_name
                    logger.info(f"解析到简单模式 - 文件夹名: '{folder_name}' (使用模式: {pattern})")
                    break
        
        logger.info(f"提取文件夹信息: {folder_info}")
        return folder_info
    
    async def _create_file_via_api(self, file_name: str, parent_folder_name: str = None, file_content: str = '') -> MCPToolCall:
        """通过后端API创建文件"""
        try:
            logger.info(f"🚀 使用后端API创建文件: {file_name}, 父目录: {parent_folder_name}")
            
            # 导入必要的模块
            from app.models import DocumentNode
            from app import db
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
                    logger.warning(f"⚠️ 未找到父目录 '{parent_folder_name}'，将在根目录下创建文件")
            
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
                return MCPToolCall(
                    'create_file',
                    {'name': file_name, 'parent_folder': parent_folder_name},
                    error=error_message
                )
            
            # 创建新文件节点 - 不设置id，让数据库自动生成
            new_file = DocumentNode(
                name=file_name,
                type='file',
                parent_id=parent_id,
                file_type=self._get_file_type(file_name),
                file_size=len(file_content.encode('utf-8')) if file_content else 0,
                description=f'通过MCP工具创建的文件{parent_info_msg}',
                created_at=datetime.now(),
                updated_at=datetime.now(),
                is_deleted=False
            )
            
            db.session.add(new_file)
            db.session.commit()
            
            success_message = f"✅ 成功创建文件 '{file_name}'{parent_info_msg}"
            logger.info(success_message)
            
            return MCPToolCall(
                'create_file',
                {
                    'name': file_name,
                    'parent_folder': parent_folder_name,
                    'content': file_content,
                    'file_id': new_file.id
                },
                result=success_message
            )
            
        except Exception as e:
            error_message = f"创建文件失败: {str(e)}"
            logger.error(error_message)
            return MCPToolCall('create_file', {'name': file_name}, error=error_message)
    
    async def _create_folder_via_api(self, folder_name: str, parent_folder_name: str = None) -> MCPToolCall:
        """通过后端API创建文件夹"""
        try:
            logger.info(f"🚀 使用LLM分析结果创建文件夹: {folder_name}, 父目录: {parent_folder_name}")
            
            # 导入必要的模块
            from app.models import DocumentNode
            from app import db
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
                    logger.warning(f"⚠️ 未找到父目录 '{parent_folder_name}'，将在根目录下创建文件夹")
            
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
                return MCPToolCall(
                    'create_folder',
                    {'name': folder_name, 'parent_folder': parent_folder_name},
                    error=error_message
                )
            
            # 创建新文件夹节点 - 不设置id，让数据库自动生成
            new_folder = DocumentNode(
                name=folder_name,
                type='folder',
                parent_id=parent_id,
                description=f'通过MCP工具创建的文件夹{parent_info_msg}',
                created_at=datetime.now(),
                updated_at=datetime.now(),
                is_deleted=False
            )
            
            db.session.add(new_folder)
            db.session.commit()
            
            success_message = f"✅ 成功创建文件夹 '{folder_name}'{parent_info_msg}"
            logger.info(success_message)
            
            return MCPToolCall(
                'create_folder',
                {
                    'name': folder_name,
                    'parent_folder': parent_folder_name,
                    'folder_id': new_folder.id
                },
                result=success_message
            )
            
        except Exception as e:
            error_message = f"创建文件夹失败: {str(e)}"
            logger.error(error_message)
            return MCPToolCall('create_folder', {'name': folder_name}, error=error_message)
    
    def _get_file_type(self, file_name: str) -> str:
        """根据文件名获取文件类型"""
        if '.' not in file_name:
            return 'unknown'
        
        extension = file_name.split('.')[-1].lower()
        
        type_mapping = {
            'txt': 'text',
            'md': 'markdown',
            'doc': 'document',
            'docx': 'document',
            'pdf': 'pdf',
            'xls': 'spreadsheet',
            'xlsx': 'spreadsheet',
            'jpg': 'image',
            'jpeg': 'image',
            'png': 'image',
            'gif': 'image',
            'mp4': 'video',
            'avi': 'video',
            'json': 'data',
            'csv': 'data',
            'html': 'web',
            'htm': 'web',
            'py': 'code',
            'js': 'code',
            'css': 'code',
        }
        
        return type_mapping.get(extension, 'unknown')

# 创建全局实例
mcp_tool_executor = MCPToolExecutor() 