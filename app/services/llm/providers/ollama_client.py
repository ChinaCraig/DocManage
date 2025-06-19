"""
Ollama客户端实现

提供Ollama本地模型的完整功能实现
"""

import logging
import requests
from typing import List, Dict
from config import Config
from ..base_client import BaseLLMClient

logger = logging.getLogger(__name__)


class OllamaClient(BaseLLMClient):
    """Ollama客户端实现"""
    
    def __init__(self, model: str):
        provider_config = Config.LLM_PROVIDERS['ollama']
        super().__init__(
            model=model,
            api_key="",  # Ollama不需要API密钥
            base_url=provider_config['base_url']
        )
    
    def _make_request(self, data: Dict, headers: Dict = None) -> Dict:
        """Ollama专用的HTTP请求方法"""
        try:
            default_headers = {
                'Content-Type': 'application/json'
            }
            if headers:
                default_headers.update(headers)
            
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=data,
                headers=default_headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama请求失败: {e}")
            raise Exception(f"Ollama服务调用失败: {str(e)}")
    
    def optimize_query(self, query: str, scenario: str = None, template: str = None) -> str:
        """使用Ollama优化查询"""
        try:
            prompt = f"""请将用户查询优化为适合文档检索的关键词：

用户查询：{query}

输出关键词（空格分隔）："""

            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "你是文档检索查询优化助手。"},
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            }
            
            response = self._make_request(data)
            return response['message']['content'].strip()
            
        except Exception as e:
            logger.error(f"Ollama查询优化失败: {e}")
            return query
    
    def rerank_results(self, query: str, results: List[Dict]) -> List[Dict]:
        """使用Ollama重排序结果"""
        if not results:
            return results
        
        try:
            # 简化重排序逻辑，直接返回原结果
            # Ollama模型对于复杂的重排序任务可能表现不稳定
            return results
        except Exception as e:
            logger.error(f"Ollama重排序失败: {e}")
            return results
    
    def generate_answer(self, query: str, context: str, scenario: str = None, style: str = None) -> str:
        """使用Ollama生成答案"""
        try:
            # 判断是否是普通聊天模式（context为空或style为conversational）
            is_conversational = not context.strip() or style == "conversational"
            
            if is_conversational:
                # 普通聊天模式
                prompt = f"""你是一个友好、专业的AI助手。请直接回答用户的问题，进行自然的对话交流。

用户问题：{query}

请提供友好、准确的回答："""
                system_content = "你是一个友好、专业的AI助手，可以回答各种问题并进行自然对话。"
            else:
                # 文档检索模式
                prompt = f"""基于以下文档内容回答用户问题：

文档内容：
{context}

用户问题：{query}

请提供准确、简洁的回答："""
                system_content = "你是一个专业的文档分析助手。"

            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            }
            
            response = self._make_request(data)
            return response['message']['content'].strip()
            
        except Exception as e:
            logger.error(f"Ollama答案生成失败: {e}")
            if is_conversational:
                return "抱歉，我暂时无法回答您的问题。请稍后再试。"
            else:
                return "抱歉，无法生成答案。" 