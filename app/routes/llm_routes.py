from flask import Blueprint, jsonify
from config import Config
import logging

logger = logging.getLogger(__name__)

llm_bp = Blueprint('llm', __name__)

@llm_bp.route('/config', methods=['GET'])
def get_llm_config():
    """获取LLM配置信息 - 兼容前端调用"""
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
        logger.error(f"获取LLM配置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@llm_bp.route('/models', methods=['GET'])
def get_llm_models():
    """获取可用的LLM模型"""
    try:
        from app.services.llm_service import LLMService
        
        llm_service = LLMService()
        models = llm_service.get_available_models()
        
        return jsonify({
            'success': True,
            'data': {
                'models': models,
                'default_provider': Config.DEFAULT_LLM_PROVIDER
            }
        })
    except Exception as e:
        logger.error(f"获取LLM模型失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取LLM模型失败: {str(e)}'
        }), 500

@llm_bp.route('/status', methods=['GET'])
def get_llm_status():
    """获取LLM服务状态"""
    try:
        from app.services.llm_service import LLMService
        
        llm_service = LLMService()
        status = llm_service.get_service_status()
        
        return jsonify({
            'success': True,
            'data': status
        })
    except Exception as e:
        logger.error(f"获取LLM状态失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取LLM状态失败: {str(e)}'
        }), 500 