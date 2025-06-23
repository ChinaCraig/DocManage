import logging
from flask import Blueprint, request, jsonify
from app.services.intent_service import intent_service
from app.services.llm import LLMService

logger = logging.getLogger(__name__)

intent_bp = Blueprint('intent', __name__)

@intent_bp.route('/config', methods=['GET'])
def get_intent_config():
    """获取意图识别配置信息"""
    try:
        config = intent_service.config or {}
        llm_config = config.get('llm_config', {})
        intent_prompts = config.get('intent_prompts', {})
        fallback_config = config.get('fallback_config', {})
        keyword_analysis = config.get('keyword_analysis', {})
        
        config_info = {
            'service_mode': llm_config.get('service_mode', 'remote'),
            'current_provider': llm_config.get('current_provider', 'deepseek'),
            'current_model': llm_config.get('current_model', 'deepseek-chat'),
            'system_prompt_length': len(intent_prompts.get('system_prompt', '')),
            'user_prompt_template': intent_prompts.get('user_prompt_template', ''),
            'confidence_threshold': intent_prompts.get('confidence_threshold', 0.6),
            'fallback_enabled': fallback_config.get('enabled', True),
            'fallback_strategy': fallback_config.get('strategy', 'keyword_analysis'),
            'keyword_analysis_enabled': keyword_analysis.get('enabled', True),
            'available_providers': list(llm_config.get('providers', {}).keys()),
            'intent_types': ['normal_chat', 'knowledge_search', 'mcp_action', 'document_generation'],
            'cache_enabled': config.get('performance', {}).get('cache', {}).get('enabled', True)
        }
        
        return jsonify({
            'success': True,
            'data': config_info
        })
        
    except Exception as e:
        logger.error(f"获取意图识别配置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@intent_bp.route('/scenarios', methods=['GET'])
def get_available_scenarios():
    """获取可用的意图识别场景"""
    try:
        # 新架构暂时不支持场景特定配置，返回默认场景
        scenarios = {
            'default': {
                'name': 'default',
                'description': '默认意图识别场景',
                'intent_types': ['normal_chat', 'knowledge_search', 'mcp_action', 'document_generation']
            }
        }
        
        return jsonify({
            'success': True,
            'data': scenarios
        })
        
    except Exception as e:
        logger.error(f"获取意图识别场景失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@intent_bp.route('/test', methods=['POST'])
def test_intent_analysis():
    """测试意图识别功能"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据为空'
            }), 400
        
        query = data.get('query', '').strip()
        scenario = data.get('scenario')
        llm_model = data.get('llm_model')
        
        if not query:
            return jsonify({
                'success': False,
                'error': '查询内容不能为空'
            }), 400
        
        # 执行意图分析
        intent_result = LLMService.analyze_user_intent(query, llm_model, scenario)
        
        response_data = {
            'query': query,
            'scenario': scenario,
            'intent_result': intent_result,
            'analysis_method': intent_result.get('analysis_method', 'unknown'),
            'model_used': intent_result.get('model_used'),
            'prompt_source': intent_result.get('prompt_source'),
            'timestamp': intent_result.get('timestamp')
        }
        
        return jsonify({
            'success': True,
            'data': response_data
        })
        
    except Exception as e:
        logger.error(f"意图识别测试失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@intent_bp.route('/reload', methods=['POST'])
def reload_intent_config():
    """重新加载意图识别配置"""
    try:
        intent_service.load_config()
        
        return jsonify({
            'success': True,
            'message': '意图识别配置已重新加载',
            'timestamp': intent_service._log_analysis_metrics.__name__
        })
        
    except Exception as e:
        logger.error(f"重新加载意图识别配置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@intent_bp.route('/prompt', methods=['GET'])
def get_prompt_templates():
    """获取提示词模板"""
    try:
        scenario = request.args.get('scenario')
        
        config = intent_service.config or {}
        intent_prompts = config.get('intent_prompts', {})
        llm_config = config.get('llm_config', {})
        
        response_data = {
            'system_prompt': intent_prompts.get('system_prompt', ''),
            'user_prompt_template': intent_prompts.get('user_prompt_template', ''),
            'scenario': scenario,
            'model_parameters': llm_config.get('parameters', {}),
            'confidence_threshold': intent_prompts.get('confidence_threshold', 0.6)
        }
        
        return jsonify({
            'success': True,
            'data': response_data
        })
        
    except Exception as e:
        logger.error(f"获取提示词模板失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@intent_bp.route('/keywords', methods=['GET'])
def get_enhanced_keywords():
    """获取增强关键词配置"""
    try:
        scenario = request.args.get('scenario')
        
        config = intent_service.config or {}
        keyword_analysis = config.get('keyword_analysis', {})
        
        response_data = {
            'intent_keywords': keyword_analysis.get('intent_keywords', {}),
            'weights': keyword_analysis.get('weights', {}),
            'file_detection': keyword_analysis.get('file_detection', {}),
            'action_verbs': keyword_analysis.get('action_verbs', {}),
            'context_rules': keyword_analysis.get('context_rules', {}),
            'scenario': scenario,
            'enabled': keyword_analysis.get('enabled', True)
        }
        
        return jsonify({
            'success': True,
            'data': response_data
        })
        
    except Exception as e:
        logger.error(f"获取增强关键词配置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@intent_bp.route('/confidence-rules', methods=['GET'])
def get_confidence_rules():
    """获取置信度调整规则"""
    try:
        config = intent_service.config or {}
        
        confidence_rules = {
            'confidence_threshold': config.get('intent_prompts', {}).get('confidence_threshold', 0.6),
            'fallback_config': config.get('fallback_config', {}),
            'error_handling': config.get('error_handling', {}),
            'keyword_weights': config.get('keyword_analysis', {}).get('weights', {})
        }
        
        return jsonify({
            'success': True,
            'data': confidence_rules
        })
        
    except Exception as e:
        logger.error(f"获取置信度调整规则失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@intent_bp.route('/batch-test', methods=['POST'])
def batch_test_intent():
    """批量测试意图识别"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据为空'
            }), 400
        
        test_queries = data.get('queries', [])
        scenario = data.get('scenario')
        llm_model = data.get('llm_model')
        
        if not test_queries:
            return jsonify({
                'success': False,
                'error': '测试查询列表不能为空'
            }), 400
        
        results = []
        for query in test_queries:
            try:
                intent_result = LLMService.analyze_user_intent(query, llm_model, scenario)
                query_features = intent_prompt_service.analyze_query_complexity(query)
                
                results.append({
                    'query': query,
                    'intent_result': intent_result,
                    'query_features': query_features,
                    'success': True
                })
            except Exception as e:
                results.append({
                    'query': query,
                    'error': str(e),
                    'success': False
                })
        
        # 统计结果
        stats = {
            'total': len(results),
            'success': len([r for r in results if r['success']]),
            'failed': len([r for r in results if not r['success']]),
            'intent_distribution': {}
        }
        
        for result in results:
            if result['success']:
                intent_type = result['intent_result'].get('intent_type', 'unknown')
                stats['intent_distribution'][intent_type] = stats['intent_distribution'].get(intent_type, 0) + 1
        
        response_data = {
            'results': results,
            'statistics': stats,
            'scenario': scenario,
            'model_used': llm_model
        }
        
        return jsonify({
            'success': True,
            'data': response_data
        })
        
    except Exception as e:
        logger.error(f"批量意图识别测试失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 