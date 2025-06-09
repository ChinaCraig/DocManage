from flask import Blueprint, request, jsonify
from app.services.mcp_service_simple import simple_mcp_service
from config import Config
import logging
import asyncio

logger = logging.getLogger(__name__)

mcp_bp = Blueprint('mcp', __name__)

@mcp_bp.route('/status', methods=['GET'])
def get_mcp_status():
    """获取MCP服务状态"""
    try:
        status = {"simple_mcp": {"enabled": True, "description": "简化MCP服务"}}
        return jsonify({
            'success': True,
            'data': {
                'enabled': Config.MCP_CONFIG.get('enabled', False),
                'servers': status
            }
        })
    except Exception as e:
        logger.error(f"获取MCP状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@mcp_bp.route('/config', methods=['GET'])
def get_mcp_config():
    """获取MCP配置"""
    try:
        return jsonify({
            'success': True,
            'data': {
                'enabled': Config.MCP_CONFIG.get('enabled', False),
                'timeout': Config.MCP_CONFIG.get('timeout', 30),
                'max_concurrent_tools': Config.MCP_CONFIG.get('max_concurrent_tools', 3),
                'servers': {
                    name: {
                        'name': server_config['name'],
                        'description': server_config['description'],
                        'enabled': server_config['enabled'],
                        'capabilities': server_config['capabilities']
                    }
                    for name, server_config in Config.MCP_CONFIG.get('servers', {}).items()
                }
            }
        })
    except Exception as e:
        logger.error(f"获取MCP配置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@mcp_bp.route('/analyze', methods=['POST'])
def analyze_query():
    """分析查询并建议工具"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        
        if not query:
            return jsonify({
                'success': False,
                'error': '查询内容不能为空'
            }), 400
        
        analysis = simple_mcp_service.analyze_query(query)
        
        return jsonify({
            'success': True,
            'data': analysis
        })
        
    except Exception as e:
        logger.error(f"分析查询失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@mcp_bp.route('/execute', methods=['POST'])
def execute_tool_sequence():
    """执行工具序列"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        
        if not query:
            return jsonify({
                'success': False,
                'error': '查询内容不能为空'
            }), 400
        
        # 异步执行工具序列
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(
                simple_mcp_service.execute_tool_sequence(query)
            )
        finally:
            loop.close()
        
        # 格式化结果
        formatted_results = [{
            'tool_name': result.tool_name,
            'arguments': result.arguments,
            'result': result.result,
            'error': result.error,
            'timestamp': result.timestamp
        } for result in results]
        
        return jsonify({
            'success': True,
            'data': {
                'query': query,
                'results': formatted_results,
                'total_steps': len(formatted_results)
            }
        })
        
    except Exception as e:
        logger.error(f"执行工具序列失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@mcp_bp.route('/history', methods=['GET'])
def get_tool_history():
    """获取工具调用历史"""
    try:
        limit = request.args.get('limit', 10, type=int)
        history = simple_mcp_service.tool_history[-limit:] if simple_mcp_service.tool_history else []
        
        return jsonify({
            'success': True,
            'data': {
                'history': history,
                'total_count': len(history)
            }
        })
        
    except Exception as e:
        logger.error(f"获取工具历史失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@mcp_bp.route('/servers/<server_name>/start', methods=['POST'])
def start_server(server_name):
    """启动指定的MCP服务器"""
    try:
        return jsonify({
            'success': False,
            'error': '简化MCP服务不支持服务器管理'
        }), 400
        
    except Exception as e:
        logger.error(f"启动服务器失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@mcp_bp.route('/servers/<server_name>/stop', methods=['POST'])
def stop_server(server_name):
    """停止指定的MCP服务器"""
    try:
        if server_name not in mcp_service.servers:
            return jsonify({
                'success': False,
                'error': f'服务器 {server_name} 不存在'
            }), 404
        
        server = mcp_service.servers[server_name]
        
        if not server.is_running:
            return jsonify({
                'success': True,
                'message': f'服务器 {server_name} 已停止'
            })
        
        # 异步停止服务器
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(server.stop())
        finally:
            loop.close()
        
        if success:
            return jsonify({
                'success': True,
                'message': f'服务器 {server_name} 停止成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'服务器 {server_name} 停止失败'
            }), 500
        
    except Exception as e:
        logger.error(f"停止服务器失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 