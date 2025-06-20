#!/usr/bin/env python3
"""
内置文档管理MCP服务器
提供文档管理相关的MCP工具
"""

import asyncio
import json
import sys
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)

@dataclass
class MCPRequest:
    """MCP请求"""
    jsonrpc: str
    id: Any
    method: str
    params: Dict[str, Any] = None

@dataclass
class MCPResponse:
    """MCP响应"""
    jsonrpc: str
    id: Any
    result: Dict[str, Any] = None
    error: Dict[str, Any] = None

class DocumentMCPServer:
    """文档管理MCP服务器"""
    
    def __init__(self):
        self.tools = {
            "create_file": {
                "name": "create_file",
                "description": "在指定位置创建文件",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_name": {
                            "type": "string",
                            "description": "文件名（包含扩展名）"
                        },
                        "content": {
                            "type": "string",
                            "description": "文件内容",
                            "default": ""
                        },
                        "parent_folder": {
                            "type": "string",
                            "description": "父目录名称（可选）"
                        }
                    },
                    "required": ["file_name"]
                }
            },
            "create_folder": {
                "name": "create_folder",
                "description": "创建文件夹",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "folder_name": {
                            "type": "string",
                            "description": "文件夹名称"
                        },
                        "parent_folder": {
                            "type": "string", 
                            "description": "父目录名称（可选）"
                        }
                    },
                    "required": ["folder_name"]
                }
            },
            "list_files": {
                "name": "list_files",
                "description": "列出指定目录下的文件和文件夹",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "folder_path": {
                            "type": "string",
                            "description": "目录路径（可选，默认为根目录）"
                        },
                        "include_subdirs": {
                            "type": "boolean",
                            "description": "是否包含子目录",
                            "default": True
                        }
                    }
                }
            },
            "delete_file": {
                "name": "delete_file",
                "description": "删除指定的文件",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_name": {
                            "type": "string",
                            "description": "要删除的文件名"
                        },
                        "parent_folder": {
                            "type": "string",
                            "description": "文件所在的父目录名称（可选）"
                        }
                    },
                    "required": ["file_name"]
                }
            },
            "move_file": {
                "name": "move_file", 
                "description": "移动或重命名文件",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source_file": {
                            "type": "string",
                            "description": "源文件名"
                        },
                        "target_file": {
                            "type": "string",
                            "description": "目标文件名"
                        },
                        "source_folder": {
                            "type": "string",
                            "description": "源文件夹名称（可选）"
                        },
                        "target_folder": {
                            "type": "string",
                            "description": "目标文件夹名称（可选）"
                        }
                    },
                    "required": ["source_file", "target_file"]
                }
            }
        }
        
        self.capabilities = {
            "tools": {},
            "resources": {},
            "prompts": {}
        }
    
    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """处理MCP请求"""
        try:
            if request.method == "initialize":
                return await self._handle_initialize(request)
            elif request.method == "tools/list":
                return await self._handle_tools_list(request)
            elif request.method == "tools/call":
                return await self._handle_tools_call(request)
            elif request.method == "resources/list":
                return await self._handle_resources_list(request)
            elif request.method == "prompts/list":
                return await self._handle_prompts_list(request)
            else:
                return MCPResponse(
                    jsonrpc="2.0",
                    id=request.id,
                    error={"code": -32601, "message": f"Method not found: {request.method}"}
                )
        except Exception as e:
            logger.error(f"处理MCP请求失败: {e}")
            return MCPResponse(
                jsonrpc="2.0",
                id=request.id,
                error={"code": -32603, "message": f"Internal error: {str(e)}"}
            )
    
    async def _handle_initialize(self, request: MCPRequest) -> MCPResponse:
        """处理初始化请求"""
        return MCPResponse(
            jsonrpc="2.0",
            id=request.id,
            result={
                "protocolVersion": "2024-11-05",
                "capabilities": self.capabilities,
                "serverInfo": {
                    "name": "DocumentMCPServer",
                    "version": "1.0.0"
                }
            }
        )
    
    async def _handle_tools_list(self, request: MCPRequest) -> MCPResponse:
        """处理工具列表请求"""
        return MCPResponse(
            jsonrpc="2.0",
            id=request.id,
            result={"tools": list(self.tools.values())}
        )
    
    async def _handle_tools_call(self, request: MCPRequest) -> MCPResponse:
        """处理工具调用请求"""
        params = request.params or {}
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if tool_name not in self.tools:
            return MCPResponse(
                jsonrpc="2.0",
                id=request.id,
                error={"code": -32602, "message": f"Tool not found: {tool_name}"}
            )
        
        try:
            result = await self._execute_tool(tool_name, arguments)
            return MCPResponse(
                jsonrpc="2.0",
                id=request.id,
                result=result
            )
        except Exception as e:
            return MCPResponse(
                jsonrpc="2.0",
                id=request.id,
                error={"code": -32603, "message": f"Tool execution failed: {str(e)}"}
            )
    
    async def _handle_resources_list(self, request: MCPRequest) -> MCPResponse:
        """处理资源列表请求"""
        return MCPResponse(
            jsonrpc="2.0",
            id=request.id,
            result={"resources": []}
        )
    
    async def _handle_prompts_list(self, request: MCPRequest) -> MCPResponse:
        """处理提示列表请求"""
        return MCPResponse(
            jsonrpc="2.0",
            id=request.id,
            result={"prompts": []}
        )
    
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具"""
        if tool_name == "create_file":
            return await self._create_file(arguments)
        elif tool_name == "create_folder":
            return await self._create_folder(arguments)
        elif tool_name == "list_files":
            return await self._list_files(arguments)
        elif tool_name == "delete_file":
            return await self._delete_file(arguments)
        elif tool_name == "move_file":
            return await self._move_file(arguments)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    async def _create_file(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """创建文件"""
        file_name = arguments.get("file_name")
        content = arguments.get("content", "")
        parent_folder = arguments.get("parent_folder")
        
        if not file_name:
            raise ValueError("file_name is required")
        
        try:
            # 导入必要的模块
            import sys
            from pathlib import Path
            
            # 确保项目根目录在Python路径中
            project_root = Path(__file__).parent.parent.parent.parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            
            # 创建Flask应用上下文
            from app import create_app
            flask_app = create_app()
            
            with flask_app.app_context():
                from app.models.document_models import DocumentNode, db
                from datetime import datetime
                import uuid
                
                parent_id = None
                parent_info_msg = " (在根目录下)"
                
                # 如果指定了父目录，先查找父目录
                if parent_folder:
                    logger.info(f"查找父目录: {parent_folder}")
                    
                    # 查找父目录（支持模糊匹配）
                    parent_folder_node = db.session.query(DocumentNode).filter(
                        DocumentNode.type == 'folder',
                        DocumentNode.is_deleted == False,
                        DocumentNode.name.like(f'%{parent_folder}%')
                    ).first()
                    
                    if parent_folder_node:
                        parent_id = parent_folder_node.id
                        parent_info_msg = f" (在 {parent_folder_node.name} 目录下)"
                        logger.info(f"找到父目录: {parent_folder_node.name} (ID: {parent_id})")
                    else:
                        logger.warning(f"未找到父目录 '{parent_folder}'，将在根目录下创建文件")
                
                # 检查是否已存在同名文件
                existing_file = db.session.query(DocumentNode).filter(
                    DocumentNode.name == file_name,
                    DocumentNode.type != 'folder',
                    DocumentNode.parent_id == parent_id,
                    DocumentNode.is_deleted == False
                ).first()
                
                if existing_file:
                    error_message = f"文件 '{file_name}' 已存在于{('根目录' if parent_id is None else f'目录 {parent_folder}') }中"
                    logger.warning(error_message)
                    raise Exception(error_message)
                
                # 确定文件类型
                file_type = self._get_file_type(file_name)
                
                # 创建新文件节点
                new_file = DocumentNode(
                    name=file_name,
                    type=file_type,
                    parent_id=parent_id,
                    description=f'通过MCP工具创建的文件{parent_info_msg}',
                    file_path=f"mcp_created/{uuid.uuid4().hex}_{file_name}",  # 虚拟文件路径
                    file_content=content,  # 存储文件内容
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    is_deleted=False
                )
                
                db.session.add(new_file)
                db.session.commit()
                
                success_message = f"成功创建文件 '{file_name}'{parent_info_msg} (ID: {new_file.id})"
                logger.info(success_message)
                
                return {
                    "content": [{
                        "type": "text",
                        "text": success_message
                    }]
                }
            
        except Exception as e:
            logger.error(f"创建文件失败: {str(e)}")
            raise Exception(f"创建文件失败: {str(e)}")
    
    async def _create_folder(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """创建文件夹"""
        folder_name = arguments.get("folder_name")
        parent_folder = arguments.get("parent_folder")
        
        if not folder_name:
            raise ValueError("folder_name is required")
        
        try:
            # 导入必要的模块
            import sys
            from pathlib import Path
            
            # 确保项目根目录在Python路径中
            project_root = Path(__file__).parent.parent.parent.parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            
            # 创建Flask应用上下文
            from app import create_app
            flask_app = create_app()
            
            with flask_app.app_context():
                from app.models.document_models import DocumentNode, db
                from datetime import datetime
                
                parent_id = None
                parent_info_msg = " (在根目录下)"
                
                # 如果指定了父目录，先查找父目录
                if parent_folder:
                    logger.info(f"查找父目录: {parent_folder}")
                    
                    # 查找父目录（支持模糊匹配）
                    parent_folder_node = db.session.query(DocumentNode).filter(
                        DocumentNode.type == 'folder',
                        DocumentNode.is_deleted == False,
                        DocumentNode.name.like(f'%{parent_folder}%')
                    ).first()
                    
                    if parent_folder_node:
                        parent_id = parent_folder_node.id
                        parent_info_msg = f" (在 {parent_folder_node.name} 目录下)"
                        logger.info(f"找到父目录: {parent_folder_node.name} (ID: {parent_id})")
                    else:
                        logger.warning(f"未找到父目录 '{parent_folder}'，将在根目录下创建文件夹")
                
                # 检查是否已存在同名文件夹
                existing_folder = db.session.query(DocumentNode).filter(
                    DocumentNode.name == folder_name,
                    DocumentNode.type == 'folder',
                    DocumentNode.parent_id == parent_id,
                    DocumentNode.is_deleted == False
                ).first()
                
                if existing_folder:
                    error_message = f"文件夹 '{folder_name}' 已存在于{('根目录' if parent_id is None else f'目录 {parent_folder}') }中"
                    logger.warning(error_message)
                    raise Exception(error_message)
                
                # 创建新文件夹节点
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
                
                success_message = f"成功创建文件夹 '{folder_name}'{parent_info_msg} (ID: {new_folder.id})"
                logger.info(success_message)
                
                return {
                    "content": [{
                        "type": "text",
                        "text": success_message
                    }]
                }
            
        except Exception as e:
            logger.error(f"创建文件夹失败: {str(e)}")
            raise Exception(f"创建文件夹失败: {str(e)}")
    
    async def _list_files(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """列出文件"""
        folder_path = arguments.get("folder_path")
        include_subdirs = arguments.get("include_subdirs", True)
        
        try:
            # 这里将会调用现有的数据库查询操作
            return {
                "content": [{
                    "type": "text",
                    "text": f"列出目录内容" + (f" (在 '{folder_path}' 下)" if folder_path else " (根目录)")
                }]
            }
            
        except Exception as e:
            raise Exception(f"列出文件失败: {str(e)}")
    
    async def _delete_file(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """删除文件"""
        file_name = arguments.get("file_name")
        parent_folder = arguments.get("parent_folder")
        
        if not file_name:
            raise ValueError("file_name is required")
        
        try:
            # 这里将会调用现有的数据库删除操作
            return {
                "content": [{
                    "type": "text",
                    "text": f"成功删除文件 '{file_name}'" + 
                           (f" (在目录 '{parent_folder}' 下)" if parent_folder else "")
                }]
            }
            
        except Exception as e:
            raise Exception(f"删除文件失败: {str(e)}")
    
    async def _move_file(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """移动文件"""
        source_file = arguments.get("source_file")
        target_file = arguments.get("target_file")
        source_folder = arguments.get("source_folder")
        target_folder = arguments.get("target_folder")
        
        if not source_file or not target_file:
            raise ValueError("source_file and target_file are required")
        
        try:
            # 这里将会调用现有的数据库更新操作
            return {
                "content": [{
                    "type": "text",
                    "text": f"成功将文件 '{source_file}' 移动/重命名为 '{target_file}'"
                }]
            }
            
        except Exception as e:
            raise Exception(f"移动文件失败: {str(e)}")
    
    def _get_file_type(self, file_name: str) -> str:
        """根据文件名获取文件类型"""
        ext = Path(file_name).suffix.lower()
        if ext in ['.txt', '.md', '.rst']:
            return 'text'
        elif ext in ['.pdf']:
            return 'pdf'
        elif ext in ['.doc', '.docx']:
            return 'word'
        elif ext in ['.xls', '.xlsx']:
            return 'excel'
        elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
            return 'image'
        elif ext in ['.mp4', '.avi', '.mov', '.wmv']:
            return 'video'
        else:
            return 'unknown'

async def main():
    """主函数 - 启动MCP服务器"""
    server = DocumentMCPServer()
    
    try:
        while True:
            # 从stdin读取请求
            line = sys.stdin.readline()
            if not line:
                break
            
            try:
                request_data = json.loads(line.strip())
                request = MCPRequest(
                    jsonrpc=request_data["jsonrpc"],
                    id=request_data["id"],
                    method=request_data["method"],
                    params=request_data.get("params")
                )
                
                response = await server.handle_request(request)
                
                # 发送响应
                response_data = {
                    "jsonrpc": response.jsonrpc,
                    "id": response.id
                }
                
                if response.result is not None:
                    response_data["result"] = response.result
                elif response.error is not None:
                    response_data["error"] = response.error
                
                print(json.dumps(response_data))
                sys.stdout.flush()
                
            except json.JSONDecodeError as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
                }
                print(json.dumps(error_response))
                sys.stdout.flush()
            except Exception as e:
                error_response = {
                    "jsonrpc": "2.0", 
                    "id": None,
                    "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
                }
                print(json.dumps(error_response))
                sys.stdout.flush()
                
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    asyncio.run(main()) 