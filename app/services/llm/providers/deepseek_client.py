"""
DeepSeek客户端实现

提供DeepSeek模型的完整功能实现
"""

import logging
import re
from typing import List, Dict
from config import Config
from ..base_client import BaseLLMClient

logger = logging.getLogger(__name__)


class DeepSeekClient(BaseLLMClient):
    """DeepSeek客户端实现"""
    
    def __init__(self, model: str):
        provider_config = Config.LLM_PROVIDERS['deepseek']
        super().__init__(
            model=model,
            api_key=provider_config['api_key'],
            base_url=provider_config['base_url']
        )
    
    def optimize_query(self, query: str, scenario: str = None, template: str = None) -> str:
        """使用DeepSeek优化查询"""
        prompt = f"""请将以下自然语言查询优化为适合文档检索的关键词组合。提取核心概念，用空格分隔：

查询：{query}

关键词："""

        try:
            data = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 100,
                "temperature": 0.3
            }
            
            response = self._make_request(data)
            optimized_query = response['choices'][0]['message']['content'].strip()
            
            logger.info(f"DeepSeek查询优化完成 - 原查询: {query}, 优化后: {optimized_query}")
            return optimized_query
            
        except Exception as e:
            logger.error(f"DeepSeek查询优化失败: {e}")
            return query
    
    def rerank_results(self, query: str, results: List[Dict]) -> List[Dict]:
        """DeepSeek结果重排序"""
        if not results:
            return results
        
        # 简化版重排序
        try:
            batch_size = min(len(results), 5)  # 限制处理数量
            results_to_rank = results[:batch_size]
            
            # 构建简化的提示
            items = []
            for i, result in enumerate(results_to_rank):
                doc_name = result.get('document', {}).get('name', '未知')
                content = result.get('chunk_text', '')[:100]
                items.append(f"{i+1}. {doc_name}: {content}")
            
            prompt = f"""任务：按查询相关性对文档重新排序

查询：{query}

文档列表：
{chr(10).join(items)}

重要：只输出排序后的数字序号，用逗号分隔，不要任何其他文字！
格式示例：2,1,3,4,5

排序结果："""
            
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 20,
                "temperature": 0.1
            }
            
            response = self._make_request(data)
            rank_str = response['choices'][0]['message']['content'].strip()
            
            # 清理响应，移除非数字字符（除了逗号）
            rank_str = re.sub(r'[^\d,]', '', rank_str)
            
            # 解析和重排序
            if rank_str and ',' in rank_str:
                ranks = [int(x.strip()) - 1 for x in rank_str.split(',') if x.strip().isdigit()]
                reranked = []
                for rank in ranks:
                    if 0 <= rank < len(results_to_rank):
                        reranked.append(results_to_rank[rank])
                
                reranked.extend(results[batch_size:])
                logger.info(f"DeepSeek重排序成功 - 原序列: 1-{len(results_to_rank)}, 新序列: {rank_str}")
                return reranked
            else:
                logger.warning(f"DeepSeek返回格式异常: {rank_str}")
                return results
            
        except Exception as e:
            logger.error(f"DeepSeek重排序失败: {e}")
            return results
    
    def generate_answer(self, query: str, context: str, scenario: str = None, style: str = None) -> str:
        """DeepSeek答案生成"""
        
        # 判断是否是普通聊天模式（context为空或style为conversational）
        is_conversational = not context.strip() or style == "conversational"
        
        if is_conversational:
            # 普通聊天模式
            prompt = f"""你是一个友好、专业的AI助手。请直接回答用户的问题，进行自然的对话交流。

用户问题：{query}

请提供友好、准确的回答："""
        else:
            # 文档检索模式
            prompt = f"""基于文档内容回答问题：

问题：{query}
文档：{context[:1000]}

答案："""

        try:
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.7
            }
            
            response = self._make_request(data)
            return response['choices'][0]['message']['content'].strip()
            
        except Exception as e:
            logger.error(f"DeepSeek答案生成失败: {e}")
            if is_conversational:
                return "抱歉，我暂时无法回答您的问题。请稍后再试。"
            else:
                return "无法生成答案，请查看文档内容。" 