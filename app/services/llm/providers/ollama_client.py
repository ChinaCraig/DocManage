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
            # 对于Ollama，使用简化的意图感知重排序
            batch_size = min(len(results), 3)  # 限制为3个结果，避免token过多
            results_to_rank = results[:batch_size]
            
            # 基础意图分析
            intent = self._get_basic_intent(query)
            
            # 构建简化的排序提示
            items = []
            for i, result in enumerate(results_to_rank):
                doc_name = result.get('document', {}).get('name', '未知')
                content = result.get('chunk_text', '')[:150]  # 保持较短以节省token
                items.append(f"{i+1}. {doc_name}: {content}")
            
            # 简化的排序指导
            guidance = self._get_simple_guidance(intent)
            
            prompt = f"""请对文档按相关性重新排序：

查询：{query}
{guidance}

文档：
{chr(10).join(items)}

只输出排序序号，用逗号分隔（如：2,1,3）："""

            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            }
            
            response = self._make_request(data)
            rank_str = response['message']['content'].strip()
            
            # 解析排序结果
            if ',' in rank_str:
                try:
                    ranks = [int(x.strip()) - 1 for x in rank_str.split(',') if x.strip().isdigit()]
                    reranked = []
                    for rank in ranks:
                        if 0 <= rank < len(results_to_rank):
                            reranked.append(results_to_rank[rank])
                    
                    reranked.extend(results[batch_size:])
                    logger.info(f"Ollama重排序成功 - 意图: {intent}, 新序列: {rank_str}")
                    return reranked
                except (ValueError, IndexError):
                    logger.warning(f"Ollama排序结果解析失败: {rank_str}")
                    return results
            else:
                return results
            
        except Exception as e:
            logger.error(f"Ollama重排序失败: {e}")
            return results
    
    def _get_basic_intent(self, query: str) -> str:
        """获取基础查询意图"""
        if any(keyword in query for keyword in ['个人信息', '人员信息', '身份信息', '联系方式']):
            return 'personal_info'
        elif any(keyword in query for keyword in ['财务', '贷款', '金融', '收入', '负债']):
            return 'financial_data'
        elif any(keyword in query for keyword in ['总结', '概述', '摘要']):
            return 'summary'
        else:
            return 'general'
    
    def _get_simple_guidance(self, intent: str) -> str:
        """获取简化的排序指导"""
        guidance_map = {
            'personal_info': "优先排序包含完整个人信息的文档",
            'financial_data': "优先排序包含具体金额和财务数据的文档",
            'summary': "优先排序包含概述信息的文档",
            'general': "优先排序内容最相关的文档"
        }
        return guidance_map.get(intent, guidance_map['general'])
    
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