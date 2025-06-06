from flask import Blueprint, jsonify, request
import logging
from app.services.prompt_service import prompt_service

logger = logging.getLogger(__name__)

prompt_routes = Blueprint('prompt_routes', __name__)

@prompt_routes.route('/api/prompts/templates', methods=['GET'])
def get_available_templates():
    """获取可用的提示词模板"""
    try:
        templates = prompt_service.get_available_templates()
        return jsonify({
            'success': True,
            'data': templates
        })
    except Exception as e:
        logger.error(f"获取提示词模板失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@prompt_routes.route('/api/prompts/analyze-intent', methods=['POST'])
def analyze_query_intent():
    """分析查询意图并推荐配置"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        
        if not query:
            return jsonify({
                'success': False,
                'error': '查询内容不能为空'
            }), 400
        
        intent_analysis = prompt_service.analyze_query_intent(query)
        
        return jsonify({
            'success': True,
            'data': {
                'query': query,
                'analysis': intent_analysis
            }
        })
        
    except Exception as e:
        logger.error(f"查询意图分析失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@prompt_routes.route('/api/prompts/preview', methods=['POST'])
def preview_prompt():
    """预览格式化的提示词"""
    try:
        data = request.get_json()
        prompt_type = data.get('type', 'query_optimization')  # query_optimization 或 result_assembly
        query = data.get('query', '')
        context = data.get('context', '')
        scenario = data.get('scenario')
        template = data.get('template')
        
        if not query:
            return jsonify({
                'success': False,
                'error': '查询内容不能为空'
            }), 400
        
        if prompt_type == 'query_optimization':
            prompt_config = prompt_service.get_query_optimization_prompt(
                query, scenario=scenario, template=template
            )
        elif prompt_type == 'result_assembly':
            if not context:
                return jsonify({
                    'success': False,
                    'error': '结果组装需要提供文档内容'
                }), 400
            prompt_config = prompt_service.get_result_assembly_prompt(
                query, context, scenario=scenario, template=template
            )
        else:
            return jsonify({
                'success': False,
                'error': '不支持的提示词类型'
            }), 400
        
        return jsonify({
            'success': True,
            'data': {
                'type': prompt_type,
                'config': prompt_config
            }
        })
        
    except Exception as e:
        logger.error(f"提示词预览失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@prompt_routes.route('/api/prompts/reload', methods=['POST'])
def reload_prompts():
    """重新加载提示词配置"""
    try:
        prompt_service.load_prompts()
        return jsonify({
            'success': True,
            'message': '提示词配置已重新加载'
        })
    except Exception as e:
        logger.error(f"重新加载提示词配置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 