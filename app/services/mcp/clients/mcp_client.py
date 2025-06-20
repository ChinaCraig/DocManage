"""
标准MCP客户端实现
支持与MCP服务器进行JSON-RPC通信
"""

import asyncio
import json
import logging
import subprocess
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
import uuid
import time

logger = logging.getLogger(__name__)

@dataclass
class MCPTool:
    """MCP工具定义"""
    name: str
    description: str
    inputSchema: Dict[str, Any]
    server_name: str = ""

@dataclass
class MCPResource:
    """MCP资源定义"""
    uri: str
    name: str
    description: str = ""
    mimeType: str = ""

@dataclass
class MCPPrompt:
    """MCP提示定义"""
    name: str
    description: str
    arguments: List[Dict[str, Any]] = None

@dataclass
class MCPToolResult:
    """MCP工具执行结果"""
    tool_name: str
    content: List[Dict[str, Any]]
    isError: bool = False
    server_name: str = ""

class MCPServerConnection:
    """MCP服务器连接"""
    
    def __init__(self, server_name: str, command: str, args: List[str], 
                 env: Dict[str, str] = None, working_directory: str = None, timeout: int = 30):
        self.server_name = server_name
        self.command = command
        self.args = args
        self.env = env or {}
        self.working_directory = working_directory
        self.timeout = timeout
        self.process: Optional[subprocess.Popen] = None
        self.request_id = 0
        self.connected = False
        self.tools: Dict[str, MCPTool] = {}
        self.resources: Dict[str, MCPResource] = {}
        self.prompts: Dict[str, MCPPrompt] = {}
    
    async def connect(self) -> bool:
        """连接到MCP服务器"""
        try:
            logger.info(f"正在连接MCP服务器: {self.server_name}")
            
            # 启动MCP服务器进程
            self.process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, **self.env} if self.env else None,
                cwd=self.working_directory,
                text=True,
                bufsize=0
            )
            
            # 发送初始化请求
            init_request = {
                "jsonrpc": "2.0",
                "id": self._next_request_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                        "resources": {},
                        "prompts": {}
                    },
                    "clientInfo": {
                        "name": "DocManage-MCP-Client",
                        "version": "1.0.0"
                    }
                }
            }
            
            response = await self._send_request(init_request)
            if response and not response.get("error"):
                self.connected = True
                logger.info(f"成功连接到MCP服务器: {self.server_name}")
                
                # 获取可用工具列表
                await self._discover_capabilities()
                return True
            else:
                logger.error(f"MCP服务器初始化失败: {response.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"连接MCP服务器失败 {self.server_name}: {e}")
            return False
    
    async def disconnect(self):
        """断开MCP服务器连接"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
        self.connected = False
        logger.info(f"已断开MCP服务器连接: {self.server_name}")
    
    async def _discover_capabilities(self):
        """发现服务器能力"""
        # 获取工具列表
        tools_request = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "tools/list"
        }
        
        tools_response = await self._send_request(tools_request)
        if tools_response and not tools_response.get("error"):
            tools_data = tools_response.get("result", {}).get("tools", [])
            for tool_data in tools_data:
                tool = MCPTool(
                    name=tool_data["name"],
                    description=tool_data.get("description", ""),
                    inputSchema=tool_data.get("inputSchema", {}),
                    server_name=self.server_name
                )
                self.tools[tool.name] = tool
            logger.info(f"发现 {len(self.tools)} 个工具在服务器 {self.server_name}")
        
        # 获取资源列表
        resources_request = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "resources/list"
        }
        
        resources_response = await self._send_request(resources_request)
        if resources_response and not resources_response.get("error"):
            resources_data = resources_response.get("result", {}).get("resources", [])
            for resource_data in resources_data:
                resource = MCPResource(
                    uri=resource_data["uri"],
                    name=resource_data["name"],
                    description=resource_data.get("description", ""),
                    mimeType=resource_data.get("mimeType", "")
                )
                self.resources[resource.uri] = resource
            logger.info(f"发现 {len(self.resources)} 个资源在服务器 {self.server_name}")
        
        # 获取提示列表
        prompts_request = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "prompts/list"
        }
        
        prompts_response = await self._send_request(prompts_request)
        if prompts_response and not prompts_response.get("error"):
            prompts_data = prompts_response.get("result", {}).get("prompts", [])
            for prompt_data in prompts_data:
                prompt = MCPPrompt(
                    name=prompt_data["name"],
                    description=prompt_data.get("description", ""),
                    arguments=prompt_data.get("arguments", [])
                )
                self.prompts[prompt.name] = prompt
            logger.info(f"发现 {len(self.prompts)} 个提示在服务器 {self.server_name}")
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> MCPToolResult:
        """调用MCP工具"""
        if not self.connected:
            return MCPToolResult(
                tool_name=tool_name,
                content=[{"type": "text", "text": "服务器未连接"}],
                isError=True,
                server_name=self.server_name
            )
        
        if tool_name not in self.tools:
            return MCPToolResult(
                tool_name=tool_name,
                content=[{"type": "text", "text": f"工具 {tool_name} 不存在"}],
                isError=True,
                server_name=self.server_name
            )
        
        try:
            request = {
                "jsonrpc": "2.0",
                "id": self._next_request_id(),
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            response = await self._send_request(request)
            
            if response and not response.get("error"):
                result_data = response.get("result", {})
                return MCPToolResult(
                    tool_name=tool_name,
                    content=result_data.get("content", []),
                    isError=False,
                    server_name=self.server_name
                )
            else:
                error_msg = response.get("error", {}).get("message", "Unknown error") if response else "No response"
                return MCPToolResult(
                    tool_name=tool_name,
                    content=[{"type": "text", "text": f"工具执行错误: {error_msg}"}],
                    isError=True,
                    server_name=self.server_name
                )
                
        except Exception as e:
            logger.error(f"调用工具失败 {tool_name}: {e}")
            return MCPToolResult(
                tool_name=tool_name,
                content=[{"type": "text", "text": f"工具执行异常: {str(e)}"}],
                isError=True,
                server_name=self.server_name
            )
    
    async def _send_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """发送JSON-RPC请求"""
        if not self.process or not self.process.stdin:
            return None
        
        try:
            request_json = json.dumps(request) + "\n"
            self.process.stdin.write(request_json)
            self.process.stdin.flush()
            
            # 读取响应
            response_line = self.process.stdout.readline()
            if response_line:
                return json.loads(response_line.strip())
            return None
            
        except Exception as e:
            logger.error(f"发送MCP请求失败: {e}")
            return None
    
    def _next_request_id(self) -> int:
        """获取下一个请求ID"""
        self.request_id += 1
        return self.request_id

class MCPClient:
    """MCP客户端管理器"""
    
    def __init__(self):
        self.connections: Dict[str, MCPServerConnection] = {}
        self.is_initialized = False
    
    async def initialize(self, config):
        """初始化MCP客户端"""
        try:
            from ..config.mcp_config import MCPConfig
            
            if isinstance(config, str):
                mcp_config = MCPConfig(config)
            elif hasattr(config, 'get_enabled_servers'):
                mcp_config = config
            else:
                mcp_config = MCPConfig()
            
            enabled_servers = mcp_config.get_enabled_servers()
            
            for server_name, server_config in enabled_servers.items():
                connection = MCPServerConnection(
                    server_name=server_name,
                    command=server_config.command,
                    args=server_config.args,
                    env=server_config.env,
                    working_directory=server_config.working_directory,
                    timeout=server_config.timeout
                )
                
                if await connection.connect():
                    self.connections[server_name] = connection
                    logger.info(f"MCP服务器 {server_name} 已连接")
                else:
                    logger.error(f"无法连接到MCP服务器 {server_name}")
            
            self.is_initialized = True
            logger.info(f"MCP客户端初始化完成，连接了 {len(self.connections)} 个服务器")
            
        except Exception as e:
            logger.error(f"MCP客户端初始化失败: {e}")
    
    async def shutdown(self):
        """关闭MCP客户端"""
        for connection in self.connections.values():
            await connection.disconnect()
        self.connections.clear()
        self.is_initialized = False
        logger.info("MCP客户端已关闭")
    
    def get_available_tools(self) -> List[MCPTool]:
        """获取所有可用工具"""
        tools = []
        for connection in self.connections.values():
            tools.extend(connection.tools.values())
        return tools
    
    def get_tools_by_server(self, server_name: str) -> List[MCPTool]:
        """获取指定服务器的工具"""
        if server_name in self.connections:
            return list(self.connections[server_name].tools.values())
        return []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any], server_name: str = None) -> MCPToolResult:
        """调用MCP工具"""
        if not self.is_initialized:
            return MCPToolResult(
                tool_name=tool_name,
                content=[{"type": "text", "text": "MCP客户端未初始化"}],
                isError=True
            )
        
        # 如果指定了服务器名称
        if server_name:
            if server_name in self.connections:
                return await self.connections[server_name].call_tool(tool_name, arguments)
            else:
                return MCPToolResult(
                    tool_name=tool_name,
                    content=[{"type": "text", "text": f"服务器 {server_name} 不存在"}],
                    isError=True
                )
        
        # 否则在所有连接中查找工具
        for connection in self.connections.values():
            if tool_name in connection.tools:
                return await connection.call_tool(tool_name, arguments)
        
        return MCPToolResult(
            tool_name=tool_name,
            content=[{"type": "text", "text": f"工具 {tool_name} 不存在"}],
            isError=True
        )
    
    def get_server_status(self) -> Dict[str, bool]:
        """获取服务器连接状态"""
        return {name: conn.connected for name, conn in self.connections.items()}

# 需要导入os模块
import os 