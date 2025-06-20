"""
MCP工具注册表
用于注册、发现和管理MCP工具
"""

import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from ..clients.mcp_client import MCPTool, MCPToolResult

logger = logging.getLogger(__name__)

@dataclass
class ToolCategory:
    """工具分类"""
    name: str
    description: str
    tools: List[str]

class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}
        self.tool_handlers: Dict[str, Callable] = {}
        self.categories: Dict[str, ToolCategory] = {}
        self._init_default_categories()
    
    def _init_default_categories(self):
        """初始化默认工具分类"""
        self.categories = {
            "file_management": ToolCategory(
                name="文件管理",
                description="文件和文件夹操作工具",
                tools=["create_file", "create_folder", "delete_file", "move_file", "list_files"]
            ),
            "web_automation": ToolCategory(
                name="网页自动化",
                description="浏览器自动化和网页操作工具",
                tools=["puppeteer_navigate", "puppeteer_click", "puppeteer_type"]
            ),
            "system_operations": ToolCategory(
                name="系统操作",
                description="系统级操作和管理工具",
                tools=["filesystem_read", "filesystem_write", "filesystem_list"]
            ),
            "search_tools": ToolCategory(
                name="搜索工具",
                description="网络搜索和信息检索工具",
                tools=["brave_search", "google_search"]
            ),
            "database_tools": ToolCategory(
                name="数据库工具",
                description="数据库查询和操作工具",
                tools=["sqlite_query", "mysql_query"]
            )
        }
    
    def register_tool(self, tool: MCPTool, handler: Callable = None):
        """注册工具"""
        self.tools[tool.name] = tool
        if handler:
            self.tool_handlers[tool.name] = handler
        
        # 自动分类
        self._auto_categorize_tool(tool)
        
        logger.info(f"已注册工具: {tool.name}")
    
    def unregister_tool(self, tool_name: str):
        """注销工具"""
        if tool_name in self.tools:
            del self.tools[tool_name]
        if tool_name in self.tool_handlers:
            del self.tool_handlers[tool_name]
        
        # 从分类中移除
        for category in self.categories.values():
            if tool_name in category.tools:
                category.tools.remove(tool_name)
        
        logger.info(f"已注销工具: {tool_name}")
    
    def get_tool(self, tool_name: str) -> Optional[MCPTool]:
        """获取工具"""
        return self.tools.get(tool_name)
    
    def get_all_tools(self) -> List[MCPTool]:
        """获取所有工具"""
        return list(self.tools.values())
    
    def get_tools_by_category(self, category_name: str) -> List[MCPTool]:
        """按分类获取工具"""
        if category_name not in self.categories:
            return []
        
        category = self.categories[category_name]
        return [self.tools[tool_name] for tool_name in category.tools if tool_name in self.tools]
    
    def search_tools(self, query: str) -> List[MCPTool]:
        """搜索工具"""
        query_lower = query.lower()
        matching_tools = []
        
        for tool in self.tools.values():
            if (query_lower in tool.name.lower() or 
                query_lower in tool.description.lower()):
                matching_tools.append(tool)
        
        return matching_tools
    
    def get_tool_categories(self) -> Dict[str, ToolCategory]:
        """获取工具分类"""
        return self.categories
    
    def add_category(self, category_name: str, category: ToolCategory):
        """添加工具分类"""
        self.categories[category_name] = category
        logger.info(f"已添加工具分类: {category_name}")
    
    def _auto_categorize_tool(self, tool: MCPTool):
        """自动分类工具"""
        tool_name = tool.name.lower()
        tool_desc = tool.description.lower()
        
        # 文件管理工具
        if any(keyword in tool_name or keyword in tool_desc 
               for keyword in ['file', 'folder', 'create', 'delete', 'move', 'list']):
            if tool.name not in self.categories["file_management"].tools:
                self.categories["file_management"].tools.append(tool.name)
        
        # 网页自动化工具
        elif any(keyword in tool_name or keyword in tool_desc 
                 for keyword in ['puppeteer', 'browser', 'web', 'navigate', 'click']):
            if tool.name not in self.categories["web_automation"].tools:
                self.categories["web_automation"].tools.append(tool.name)
        
        # 系统操作工具
        elif any(keyword in tool_name or keyword in tool_desc 
                 for keyword in ['filesystem', 'system', 'process', 'command']):
            if tool.name not in self.categories["system_operations"].tools:
                self.categories["system_operations"].tools.append(tool.name)
        
        # 搜索工具
        elif any(keyword in tool_name or keyword in tool_desc 
                 for keyword in ['search', 'query', 'find', 'brave', 'google']):
            if tool.name not in self.categories["search_tools"].tools:
                self.categories["search_tools"].tools.append(tool.name)
        
        # 数据库工具
        elif any(keyword in tool_name or keyword in tool_desc 
                 for keyword in ['sqlite', 'mysql', 'database', 'sql', 'query']):
            if tool.name not in self.categories["database_tools"].tools:
                self.categories["database_tools"].tools.append(tool.name)
    
    def get_tool_stats(self) -> Dict[str, Any]:
        """获取工具统计信息"""
        stats = {
            "total_tools": len(self.tools),
            "total_categories": len(self.categories),
            "tools_by_category": {},
            "tools_with_handlers": len(self.tool_handlers),
            "popular_tools": []
        }
        
        for category_name, category in self.categories.items():
            available_tools = [tool_name for tool_name in category.tools if tool_name in self.tools]
            stats["tools_by_category"][category_name] = {
                "name": category.name,
                "description": category.description,
                "tool_count": len(available_tools),
                "tools": available_tools
            }
        
        return stats
    
    def validate_tool_schema(self, tool: MCPTool) -> bool:
        """验证工具schema"""
        try:
            # 检查必要字段
            if not tool.name or not tool.description:
                return False
            
            # 检查inputSchema格式
            if tool.inputSchema:
                if not isinstance(tool.inputSchema, dict):
                    return False
                
                # 检查是否包含type字段
                if "type" not in tool.inputSchema:
                    return False
            
            return True
        except Exception as e:
            logger.error(f"工具schema验证失败: {e}")
            return False
    
    def export_tool_definitions(self) -> Dict[str, Any]:
        """导出工具定义"""
        return {
            "tools": {
                tool_name: {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema,
                    "server_name": tool.server_name
                }
                for tool_name, tool in self.tools.items()
            },
            "categories": {
                category_name: {
                    "name": category.name,
                    "description": category.description,
                    "tools": category.tools
                }
                for category_name, category in self.categories.items()
            }
        } 