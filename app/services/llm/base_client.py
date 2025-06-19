"""
LLM客户端基类

定义所有LLM客户端的通用接口和基础功能
"""

import os
import json
import logging
import requests
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from config import Config

# 导入提示词服务
try:
    from app.services.prompt_service import prompt_service
except ImportError:
    logging.warning("提示词服务导入失败，将使用默认提示词")
    prompt_service = None

logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    """LLM客户端基类"""
    
    def __init__(self, model: str, api_key: str, base_url: str = None):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = Config.LLM_TIMEOUT
        self.max_context_length = Config.LLM_MAX_CONTEXT_LENGTH
        self.prompt_service = prompt_service
    
    @abstractmethod
    def optimize_query(self, query: str, scenario: str = None, template: str = None) -> str:
        """查询优化：将自然语言查询优化为更适合检索的形式"""
        pass
    
    @abstractmethod
    def rerank_results(self, query: str, results: List[Dict]) -> List[Dict]:
        """结果重排序：基于查询对检索结果进行重新排序"""
        pass
    
    @abstractmethod
    def generate_answer(self, query: str, context: str, scenario: str = None, style: str = None) -> str:
        """答案生成：基于检索结果生成自然语言答案"""
        pass
    
    def _make_request(self, data: Dict, headers: Dict = None) -> Dict:
        """统一的HTTP请求方法"""
        try:
            default_headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }
            if headers:
                default_headers.update(headers)
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=data,
                headers=default_headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"LLM请求失败: {e}")
            raise Exception(f"LLM服务调用失败: {str(e)}")
    
    def _call_llm_with_prompt(self, system_prompt: str, user_prompt: str, parameters: Dict) -> str:
        """使用提示词调用LLM"""
        try:
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                **parameters
            }
            
            response = self._make_request(data)
            return response['choices'][0]['message']['content'].strip()
            
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            raise e 