from flask import Blueprint, jsonify
from config import Config
import logging

logger = logging.getLogger(__name__)

config_bp = Blueprint('config', __name__)

@config_bp.route('/llm-models', methods=['GET'])
def get_llm_models():
    """获取可用的LLM模型配置"""
    try:
        available_models = []
        
        for provider_key, provider_config in Config.LLM_PROVIDERS.items():
            # 检查provider是否可用（简单检查是否有必要的配置）
            is_available = True
            if provider_key == 'openai' and not provider_config.get('api_key'):
                is_available = False
            elif provider_key == 'claude' and not provider_config.get('api_key'):
                is_available = False
            elif provider_key == 'zhipu' and not provider_config.get('api_key'):
                is_available = False
            elif provider_key == 'deepseek' and not provider_config.get('api_key'):
                is_available = False
            
            for model_key, model_name in provider_config['models'].items():
                available_models.append({
                    'provider': provider_key,
                    'provider_name': provider_config['name'],
                    'model_key': model_key,
                    'model_name': model_name,
                    'display_name': f"{provider_config['name']} - {model_name}",
                    'full_key': f"{provider_key}:{model_key}",
                    'is_available': is_available
                })
        
        # 获取默认选择
        default_selection = f"{Config.DEFAULT_LLM_PROVIDER}:{Config.DEFAULT_LLM_MODEL}"
        
        return jsonify({
            'success': True,
            'data': {
                'models': available_models,
                'default': default_selection,
                'features': {
                    'query_optimization': Config.ENABLE_LLM_QUERY_OPTIMIZATION,
                    'result_reranking': Config.ENABLE_LLM_RESULT_RERANKING,
                    'answer_generation': Config.ENABLE_LLM_ANSWER_GENERATION
                }
            }
        })
        
    except Exception as e:
        logger.error(f"获取LLM模型配置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@config_bp.route('/llm-features', methods=['GET'])
def get_llm_features():
    """获取LLM功能开关状态"""
    try:
        return jsonify({
            'success': True,
            'data': {
                'query_optimization': Config.ENABLE_LLM_QUERY_OPTIMIZATION,
                'result_reranking': Config.ENABLE_LLM_RESULT_RERANKING,
                'answer_generation': Config.ENABLE_LLM_ANSWER_GENERATION,
                'timeout': Config.LLM_TIMEOUT,
                'max_context_length': Config.LLM_MAX_CONTEXT_LENGTH
            }
        })
        
    except Exception as e:
        logger.error(f"获取LLM功能配置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 