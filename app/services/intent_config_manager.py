"""
意图识别专用配置管理器
完全独立于全局LLM配置，专门为意图识别模块提供配置和LLM客户端
"""

import os
import yaml
import json
import logging
import requests
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class IntentLLMClient:
    """意图识别专用LLM客户端"""
    
    def __init__(self, provider: str, model: str, config: Dict[str, Any]):
        self.provider = provider
        self.model = model
        self.config = config
        self.api_key = self._get_api_key()
        self.base_url = config.get('base_url', '')
        
    def _get_api_key(self) -> Optional[str]:
        """获取API密钥"""
        api_key_env = self.config.get('api_key_env')
        if api_key_env:
            return os.environ.get(api_key_env)
        return None
    
    def analyze_intent(self, system_prompt: str, user_prompt: str, params: Dict[str, Any]) -> str:
        """分析意图 - 调用LLM API"""
        if self.provider == 'deepseek':
            return self._call_deepseek_api(system_prompt, user_prompt, params)
        elif self.provider == 'doubao':
            return self._call_doubao_api(system_prompt, user_prompt, params)
        else:
            raise ValueError(f"不支持的LLM提供商: {self.provider}")
    
    def _call_deepseek_api(self, system_prompt: str, user_prompt: str, params: Dict[str, Any]) -> str:
        """调用DeepSeek API"""
        if not self.api_key:
            raise ValueError("DeepSeek API密钥未配置")
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            'max_tokens': params.get('max_tokens', 300),
            'temperature': params.get('temperature', 0.1),
            'stream': False
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=params.get('timeout', 30)
            )
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except requests.exceptions.RequestException as e:
            logger.error(f"DeepSeek API调用失败: {e}")
            raise
    
    def _call_doubao_api(self, system_prompt: str, user_prompt: str, params: Dict[str, Any]) -> str:
        """调用豆包API"""
        if not self.api_key:
            raise ValueError("豆包API密钥未配置")
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            'max_tokens': params.get('max_tokens', 300),
            'temperature': params.get('temperature', 0.1)
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=params.get('timeout', 30)
            )
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except requests.exceptions.RequestException as e:
            logger.error(f"豆包API调用失败: {e}")
            raise


class IntentConfigManager:
    """意图识别专用配置管理器"""
    
    def __init__(self):
        self.config = None
        self.config_file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            'prompts', 
            'intent_recognition_config.yaml'
        )
        self.load_config()
        
    def load_config(self):
        """加载意图识别配置"""
        try:
            if os.path.exists(self.config_file_path):
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f)
                logger.info(f"意图识别独立配置加载成功: {self.config_file_path}")
            else:
                logger.error(f"意图识别配置文件不存在: {self.config_file_path}")
                self.config = self._get_default_config()
        except Exception as e:
            logger.error(f"加载意图识别配置失败: {e}")
            self.config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'service': {
                'mode': 'remote',
                'current_provider': 'deepseek',
                'current_model': 'deepseek-chat'
            },
            'providers': {
                'deepseek': {
                    'enabled': True,
                    'name': 'DeepSeek',
                    'api_key_env': 'DEEPSEEK_API_KEY',
                    'base_url': 'https://api.deepseek.com',
                    'models': {
                        'deepseek-chat': 'DeepSeek Chat'
                    },
                    'default_model': 'deepseek-chat'
                }
            },
            'model_params': {
                'max_tokens': 300,
                'temperature': 0.1,
                'timeout': 30,
                'max_retries': 2
            },
            'prompts': {
                'confidence_threshold': 0.6
            },
            'fallback': {
                'enabled': True,
                'default_intent': 'normal_chat',
                'default_confidence': 0.5
            },
            'keyword_analysis': {
                'enabled': True
            }
        }
    
    def get_current_provider_config(self) -> Dict[str, Any]:
        """获取当前提供商配置"""
        current_provider = self.config['service']['current_provider']
        return self.config['providers'].get(current_provider, {})
    
    def get_current_model(self) -> str:
        """获取当前模型"""
        return self.config['service']['current_model']
    
    def get_model_params(self) -> Dict[str, Any]:
        """获取模型调用参数"""
        return self.config.get('model_params', {})
    
    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        return self.config.get('prompts', {}).get('system', '')
    
    def get_user_prompt_template(self) -> str:
        """获取用户提示词模板"""
        return self.config.get('prompts', {}).get('user_template', '')
    
    def get_confidence_threshold(self) -> float:
        """获取置信度阈值"""
        return self.config.get('prompts', {}).get('confidence_threshold', 0.6)
    
    def get_fallback_config(self) -> Dict[str, Any]:
        """获取降级处理配置"""
        return self.config.get('fallback', {})
    
    def get_keyword_analysis_config(self) -> Dict[str, Any]:
        """获取关键词分析配置"""
        return self.config.get('keyword_analysis', {})
    
    def is_cache_enabled(self) -> bool:
        """检查是否启用缓存"""
        return self.config.get('performance', {}).get('cache', {}).get('enabled', True)
    
    def get_cache_config(self) -> Dict[str, Any]:
        """获取缓存配置"""
        return self.config.get('performance', {}).get('cache', {})
    
    def create_llm_client(self) -> IntentLLMClient:
        """创建意图识别专用LLM客户端"""
        current_provider = self.config['service']['current_provider']
        current_model = self.config['service']['current_model']
        provider_config = self.get_current_provider_config()
        
        if not provider_config.get('enabled', False):
            raise ValueError(f"LLM提供商 {current_provider} 未启用")
        
        return IntentLLMClient(current_provider, current_model, provider_config)
    
    def is_provider_available(self, provider: str) -> bool:
        """检查提供商是否可用"""
        provider_config = self.config['providers'].get(provider, {})
        if not provider_config.get('enabled', False):
            return False
        
        # 检查API密钥是否配置
        api_key_env = provider_config.get('api_key_env')
        if api_key_env:
            api_key = os.environ.get(api_key_env)
            return bool(api_key)
        
        return True
    
    def get_available_models(self) -> list:
        """获取可用的模型列表"""
        models = []
        for provider_name, provider_config in self.config['providers'].items():
            if not provider_config.get('enabled', False):
                continue
            
            is_available = self.is_provider_available(provider_name)
            
            for model_key, model_name in provider_config.get('models', {}).items():
                models.append({
                    'provider': provider_name,
                    'provider_name': provider_config.get('name', provider_name),
                    'model_key': model_key,
                    'model_name': model_name,
                    'display_name': f"{provider_config.get('name', provider_name)} - {model_name}",
                    'full_key': f"{provider_name}:{model_key}",
                    'is_available': is_available
                })
        
        return models
    
    def update_current_model(self, provider: str, model: str) -> bool:
        """更新当前使用的模型"""
        try:
            if provider not in self.config['providers']:
                return False
            
            provider_config = self.config['providers'][provider]
            if model not in provider_config.get('models', {}):
                return False
            
            self.config['service']['current_provider'] = provider
            self.config['service']['current_model'] = model
            
            # 可以选择是否保存到文件
            # self._save_config()
            
            logger.info(f"意图识别模型已更新为: {provider}:{model}")
            return True
            
        except Exception as e:
            logger.error(f"更新意图识别模型失败: {e}")
            return False
    
    def get_service_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        try:
            models = self.get_available_models()
            available_count = sum(1 for model in models if model['is_available'])
            
            return {
                'service_mode': self.config['service']['mode'],
                'current_provider': self.config['service']['current_provider'],
                'current_model': self.config['service']['current_model'],
                'total_models': len(models),
                'available_models': available_count,
                'fallback_enabled': self.config['fallback']['enabled'],
                'keyword_analysis_enabled': self.config['keyword_analysis']['enabled'],
                'cache_enabled': self.is_cache_enabled(),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"获取意图识别服务状态失败: {e}")
            return {
                'error': str(e),
                'status': 'error'
            }


# 创建全局实例
intent_config = IntentConfigManager() 