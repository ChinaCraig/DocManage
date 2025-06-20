"""
标准MCP系统API路由
提供MCP配置管理、工具调用等功能
"""

from flask import Blueprint, request, jsonify
import asyncio
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# 创建蓝图
mcp_v2_bp = Blueprint('mcp_v2', __name__, url_prefix='/api/mcp/v2')

# 全局MCP管理器实例
mcp_manager = None

def get_mcp_manager():
    """获取MCP管理器实例"""
    global mcp_manager
    if mcp_manager is None:
        from app.services.mcp.servers.mcp_manager import MCPManager
        mcp_manager = MCPManager()
    return mcp_manager

@mcp_v2_bp.route('/status', methods=['GET'])
def get_mcp_status():
    """获取MCP系统状态"""
    try:
        manager = get_mcp_manager()
        
        status = {
            "is_initialized": manager.is_initialized,
            "server_status": manager.get_server_status() if manager.is_initialized else {},
            "enabled_servers": list(manager.get_enabled_servers().keys()),
            "available_tools_count": len(manager.get_available_tools()) if manager.is_initialized else 0
        }
        
        return jsonify({
            "success": True,
            "data": status
        })
        
    except Exception as e:
        logger.error(f"获取MCP状态失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_v2_bp.route('/initialize', methods=['POST'])
def initialize_mcp():
    """初始化MCP系统"""
    try:
        manager = get_mcp_manager()
        
        # 在后台运行异步初始化
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(manager.initialize())
        loop.close()
        
        if success:
            return jsonify({
                "success": True,
                "message": "MCP系统初始化成功",
                "data": {
                    "server_count": len(manager.get_enabled_servers()),
                    "tool_count": len(manager.get_available_tools())
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": "MCP系统初始化失败"
            }), 500
            
    except Exception as e:
        logger.error(f"初始化MCP系统失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_v2_bp.route('/servers', methods=['GET'])
def get_servers():
    """获取服务器配置列表"""
    try:
        manager = get_mcp_manager()
        config_info = manager.get_config_info()
        
        servers = []
        for server_name, server_config in config_info["servers"].items():
            servers.append({
                "name": server_name,
                "description": server_config.get("description", ""),
                "enabled": server_config.get("enabled", False),
                "command": server_config.get("command", ""),
                "args": server_config.get("args", []),
                "connected": manager.get_server_status().get(server_name, False) if manager.is_initialized else False
            })
        
        return jsonify({
            "success": True,
            "data": servers
        })
        
    except Exception as e:
        logger.error(f"获取服务器列表失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_v2_bp.route('/servers/<server_name>/enable', methods=['POST'])
def enable_server(server_name):
    """启用服务器"""
    try:
        manager = get_mcp_manager()
        
        if manager.enable_server(server_name):
            return jsonify({
                "success": True,
                "message": f"服务器 {server_name} 已启用"
            })
        else:
            return jsonify({
                "success": False,
                "error": f"无法启用服务器 {server_name}"
            }), 400
            
    except Exception as e:
        logger.error(f"启用服务器失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_v2_bp.route('/servers/<server_name>/disable', methods=['POST'])
def disable_server(server_name):
    """禁用服务器"""
    try:
        manager = get_mcp_manager()
        
        if manager.disable_server(server_name):
            return jsonify({
                "success": True,
                "message": f"服务器 {server_name} 已禁用"
            })
        else:
            return jsonify({
                "success": False,
                "error": f"无法禁用服务器 {server_name}"
            }), 400
            
    except Exception as e:
        logger.error(f"禁用服务器失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_v2_bp.route('/tools', methods=['GET'])
def get_tools():
    """获取可用工具列表"""
    try:
        manager = get_mcp_manager()
        
        if not manager.is_initialized:
            return jsonify({
                "success": False,
                "error": "MCP系统未初始化"
            }), 400
        
        tools = manager.get_available_tools()
        tools_data = []
        
        for tool in tools:
            tools_data.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema,
                "server_name": tool.server_name
            })
        
        return jsonify({
            "success": True,
            "data": tools_data
        })
        
    except Exception as e:
        logger.error(f"获取工具列表失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_v2_bp.route('/tools/search', methods=['GET'])
def search_tools():
    """搜索工具"""
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify({
                "success": False,
                "error": "搜索查询不能为空"
            }), 400
        
        manager = get_mcp_manager()
        
        if not manager.is_initialized:
            return jsonify({
                "success": False,
                "error": "MCP系统未初始化"
            }), 400
        
        tools = manager.search_tools(query)
        tools_data = []
        
        for tool in tools:
            tools_data.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema,
                "server_name": tool.server_name
            })
        
        return jsonify({
            "success": True,
            "data": tools_data,
            "query": query,
            "total": len(tools_data)
        })
        
    except Exception as e:
        logger.error(f"搜索工具失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_v2_bp.route('/tools/call', methods=['POST'])
def call_tool():
    """调用MCP工具"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "请求数据不能为空"
            }), 400
        
        tool_name = data.get('tool_name')
        arguments = data.get('arguments', {})
        server_name = data.get('server_name')
        
        if not tool_name:
            return jsonify({
                "success": False,
                "error": "tool_name 参数是必需的"
            }), 400
        
        manager = get_mcp_manager()
        
        if not manager.is_initialized:
            return jsonify({
                "success": False,
                "error": "MCP系统未初始化"
            }), 400
        
        # 在后台运行异步工具调用
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(manager.call_tool(tool_name, arguments, server_name))
        loop.close()
        
        return jsonify({
            "success": not result.isError,
            "data": {
                "tool_name": result.tool_name,
                "content": result.content,
                "server_name": result.server_name,
                "isError": result.isError
            }
        })
        
    except Exception as e:
        logger.error(f"调用工具失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_v2_bp.route('/servers/add', methods=['POST'])
def add_server():
    """添加新的MCP服务器配置"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "请求数据不能为空"
            }), 400
        
        required_fields = ['name', 'command', 'args', 'description']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "success": False,
                    "error": f"缺少必需字段: {field}"
                }), 400
        
        from app.services.mcp.config.mcp_config import MCPServerConfig
        
        server_config = MCPServerConfig(
            name=data['name'],
            command=data['command'],
            args=data['args'],
            description=data['description'],
            enabled=data.get('enabled', False),
            env=data.get('env', {}),
            working_directory=data.get('working_directory'),
            timeout=data.get('timeout', 30)
        )
        
        manager = get_mcp_manager()
        
        if manager.add_server(server_config):
            return jsonify({
                "success": True,
                "message": f"服务器 {data['name']} 添加成功"
            })
        else:
            return jsonify({
                "success": False,
                "error": "添加服务器失败"
            }), 500
            
    except Exception as e:
        logger.error(f"添加服务器失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_v2_bp.route('/servers/<server_name>', methods=['DELETE'])
def remove_server(server_name):
    """移除MCP服务器配置"""
    try:
        manager = get_mcp_manager()
        
        if manager.remove_server(server_name):
            return jsonify({
                "success": True,
                "message": f"服务器 {server_name} 已移除"
            })
        else:
            return jsonify({
                "success": False,
                "error": f"无法移除服务器 {server_name}"
            }), 400
            
    except Exception as e:
        logger.error(f"移除服务器失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_v2_bp.route('/reload', methods=['POST'])
def reload_config():
    """重新加载MCP配置"""
    try:
        manager = get_mcp_manager()
        
        # 在后台运行异步重新加载
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(manager.reload_config())
        loop.close()
        
        if success:
            return jsonify({
                "success": True,
                "message": "MCP配置重新加载成功",
                "data": {
                    "server_count": len(manager.get_enabled_servers()),
                    "tool_count": len(manager.get_available_tools())
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": "MCP配置重新加载失败"
            }), 500
            
    except Exception as e:
        logger.error(f"重新加载MCP配置失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500 