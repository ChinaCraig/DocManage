"""
MCP管理器
统一管理所有MCP服务器和客户端连接
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from ..config.mcp_config import MCPConfig, MCPServerConfig
from ..clients.mcp_client import MCPClient, MCPTool, MCPToolResult
from .mcp_installer import MCPInstaller

logger = logging.getLogger(__name__)

class MCPManager:
    """MCP管理器"""
    
    def __init__(self, config_path: str = None):
        self.config = MCPConfig(config_path)
        self.client = MCPClient()
        self.installer = MCPInstaller(self.config)
        self.is_initialized = False
    
    async def initialize(self) -> bool:
        """初始化MCP管理器"""
        try:
            await self.client.initialize(self.config)
            self.is_initialized = True
            logger.info("MCP管理器初始化成功")
            return True
        except Exception as e:
            logger.error(f"MCP管理器初始化失败: {e}")
            return False
    
    async def shutdown(self):
        """关闭MCP管理器"""
        if self.is_initialized:
            await self.client.shutdown()
            self.is_initialized = False
            logger.info("MCP管理器已关闭")
    
    def get_available_tools(self) -> List[MCPTool]:
        """获取所有可用工具"""
        if not self.is_initialized:
            return []
        return self.client.get_available_tools()
    
    def get_tools_by_server(self, server_name: str) -> List[MCPTool]:
        """获取指定服务器的工具"""
        if not self.is_initialized:
            return []
        return self.client.get_tools_by_server(server_name)
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any], 
                       server_name: str = None) -> MCPToolResult:
        """调用MCP工具"""
        if not self.is_initialized:
            return MCPToolResult(
                tool_name=tool_name,
                content=[{"type": "text", "text": "MCP管理器未初始化"}],
                isError=True
            )
        
        return await self.client.call_tool(tool_name, arguments, server_name)
    
    def get_server_status(self) -> Dict[str, bool]:
        """获取服务器连接状态"""
        if not self.is_initialized:
            return {}
        return self.client.get_server_status()
    
    def get_enabled_servers(self) -> Dict[str, MCPServerConfig]:
        """获取已启用的服务器配置"""
        return self.config.get_enabled_servers()
    
    def add_server(self, server_config: MCPServerConfig) -> bool:
        """添加服务器配置"""
        try:
            self.config.add_server(server_config)
            return True
        except Exception as e:
            logger.error(f"添加服务器配置失败: {e}")
            return False
    
    def remove_server(self, server_name: str) -> bool:
        """移除服务器配置"""
        return self.config.remove_server(server_name)
    
    def enable_server(self, server_name: str) -> bool:
        """启用服务器"""
        return self.config.enable_server(server_name)
    
    def disable_server(self, server_name: str) -> bool:
        """禁用服务器"""
        return self.config.disable_server(server_name)
    
    async def reload_config(self) -> bool:
        """重新加载配置"""
        try:
            # 关闭现有连接
            if self.is_initialized:
                await self.client.shutdown()
            
            # 重新加载配置
            self.config.reload_config()
            
            # 重新初始化客户端
            await self.client.initialize(self.config)
            self.is_initialized = True
            
            logger.info("MCP配置重新加载成功")
            return True
        except Exception as e:
            logger.error(f"重新加载MCP配置失败: {e}")
            return False
    
    def get_config_info(self) -> Dict[str, Any]:
        """获取配置信息"""
        return self.config.to_dict()
    
    async def test_server_connection(self, server_name: str) -> bool:
        """测试服务器连接"""
        if not self.is_initialized:
            return False
        
        status = self.get_server_status()
        return status.get(server_name, False)
    
    def search_tools(self, query: str) -> List[MCPTool]:
        """搜索工具"""
        if not self.is_initialized:
            return []
        
        tools = self.get_available_tools()
        query_lower = query.lower()
        
        matching_tools = []
        for tool in tools:
            if (query_lower in tool.name.lower() or 
                query_lower in tool.description.lower()):
                matching_tools.append(tool)
        
        return matching_tools
    
    async def check_and_install_services_for_tools(self, tools_needed: List[str]) -> Dict[str, Any]:
        """为指定工具检查并安装所需的MCP服务"""
        return await self.installer.check_and_install_required_services(tools_needed)
    
    async def check_service_installation(self, service_name: str) -> Dict[str, Any]:
        """检查单个服务的安装状态"""
        return await self.installer.check_single_service(service_name)
    
    async def install_service(self, service_name: str) -> Dict[str, Any]:
        """安装单个MCP服务"""
        return await self.installer.install_single_service(service_name)
    
    def get_service_requirements(self, service_name: str) -> Dict[str, Any]:
        """获取服务的安装要求"""
        return self.installer.get_installation_requirements(service_name)
    
    def clear_installation_cache(self):
        """清除安装状态缓存"""
        self.installer.clear_cache()