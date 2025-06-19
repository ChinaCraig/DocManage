"""
LLM客户端工厂

负责根据模型类型创建对应的LLM客户端实例
"""

import logging
from typing import Optional
from .base_client import BaseLLMClient
from .providers import OpenAIClient, DeepSeekClient, OllamaClient

logger = logging.getLogger(__name__)


class LLMClientFactory:
    """LLM客户端工厂"""
    
    @staticmethod
    def create_client(llm_model: str) -> Optional[BaseLLMClient]:
        """创建LLM客户端实例"""
        try:
            if not llm_model or ':' not in llm_model:
                logger.error(f"无效的LLM模型格式: {llm_model}")
                return None
            
            provider, model = llm_model.split(':', 1)
            
            if provider == 'openai':
                return OpenAIClient(model)
            elif provider == 'deepseek':
                return DeepSeekClient(model)
            elif provider == 'ollama':
                return OllamaClient(model)
            else:
                logger.warning(f"LLM提供商 {provider} 暂未完全实现，使用基础功能")
                return None
                
        except Exception as e:
            logger.error(f"创建LLM客户端失败: {e}")
            return None 