import logging
from flask import Blueprint, request, jsonify
from app.services.intent_prompt_service import intent_prompt_service
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

intent_bp = Blueprint('intent', __name__)

@intent_bp.route('/config', methods=['GET'])
def get_intent_config():
    """获取意图识别配置信息"""
    try:
        config_info = {
            'system_prompt_length': len(intent_prompt_service.get_system_prompt()),
            'user_prompt_template': intent_prompt_service.get_user_prompt_template(),
            'model_parameters': intent_prompt_service.get_model_parameters(),
            'available_scenarios': list(intent_prompt_service.config.get('scenario_prompts', {}).keys()) if intent_prompt_service.config else [],
            'extended_intents': list(intent_prompt_service.config.get('extended_intents', {}).keys()) if intent_prompt_service.config else [],
            'confidence_rules_count': {
                'high_confidence': len(intent_prompt_service.config.get('confidence_rules', {}).get('high_confidence', [])) if intent_prompt_service.config else 0,
                'medium_confidence': len(intent_prompt_service.config.get('confidence_rules', {}).get('medium_confidence', [])) if intent_prompt_service.config else 0,
                'low_confidence': len(intent_prompt_service.config.get('confidence_rules', {}).get('low_confidence', [])) if intent_prompt_service.config else 0
            }
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
        scenarios = {}
        if intent_prompt_service.config and 'scenario_prompts' in intent_prompt_service.config:
            for scenario_name, config in intent_prompt_service.config['scenario_prompts'].items():
                scenarios[scenario_name] = {
                    'name': scenario_name,
                    'description': config.get('system_prompt', '')[:100] + '...' if len(config.get('system_prompt', '')) > 100 else config.get('system_prompt', ''),
                    'enhanced_keywords': config.get('enhanced_keywords', {})
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
        
        # 获取查询复杂度分析
        query_features = intent_prompt_service.analyze_query_complexity(query)
        
        # 获取置信度提升信息
        confidence_boost = intent_prompt_service.get_confidence_boost(
            query, intent_result.get('intent_type', '')
        )
        
        response_data = {
            'query': query,
            'scenario': scenario,
            'intent_result': intent_result,
            'query_features': query_features,
            'confidence_boost': confidence_boost,
            'model_used': intent_result.get('model_used'),
            'prompt_source': intent_result.get('prompt_source')
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
        intent_prompt_service.reload_config()
        
        return jsonify({
            'success': True,
            'message': '意图识别配置已重新加载',
            'timestamp': intent_prompt_service.load_config.__name__
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
        
        response_data = {
            'system_prompt': intent_prompt_service.get_system_prompt(scenario),
            'user_prompt_template': intent_prompt_service.get_user_prompt_template(),
            'scenario': scenario,
            'model_parameters': intent_prompt_service.get_model_parameters()
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
        
        enhanced_keywords = intent_prompt_service.get_enhanced_keywords(scenario)
        
        # 获取通用关键词配置
        keyword_config = intent_prompt_service.config.get('keyword_enhancement', {}) if intent_prompt_service.config else {}
        
        response_data = {
            'scenario_keywords': enhanced_keywords,
            'general_keywords': keyword_config,
            'scenario': scenario
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
        confidence_rules = intent_prompt_service.config.get('confidence_rules', {}) if intent_prompt_service.config else {}
        
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