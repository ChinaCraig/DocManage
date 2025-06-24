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
        # DeepSeek专用配置：增加超时时间，因为服务器响应较慢
        self.timeout = 45  # 增加到45秒，比默认的30秒更长
    
    def optimize_query(self, query: str, scenario: str = None, template: str = None) -> str:
        """使用DeepSeek优化查询"""
        # 简化提示词，减少处理时间
        prompt = f"""提取关键词：{query}

关键词："""

        try:
            data = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 50,  # 减少token数量
                "temperature": 0.1  # 降低温度提高稳定性
            }
            
            response = self._make_request(data)
            optimized_query = response['choices'][0]['message']['content'].strip()
            
            logger.info(f"DeepSeek查询优化完成 - 原查询: {query}, 优化后: {optimized_query}")
            return optimized_query
            
        except Exception as e:
            logger.error(f"DeepSeek查询优化失败: {e}")
            # 超时时直接返回原查询，避免影响整体流程
            return query
    
    def rerank_results(self, query: str, results: List[Dict]) -> List[Dict]:
        """DeepSeek智能结果重排序"""
        if not results:
            return results
        
        # 为DeepSeek使用更简化的重排序逻辑，避免超时
        try:
            batch_size = min(len(results), 3)  # 进一步减少处理数量
            results_to_rank = results[:batch_size]
            
            # 快速意图检测，不使用复杂分析
            intent = self._get_quick_intent(query)
            
            # 构建极简的文档描述
            items = []
            for i, result in enumerate(results_to_rank):
                doc_name = result.get('document', {}).get('name', '未知')
                content = result.get('chunk_text', '')[:100]  # 进一步缩短内容
                items.append(f"{i+1}. {doc_name}: {content}")
            
            # 极简化的排序提示
            prompt = f"""排序任务：按相关性排序

查询：{query}
{self._get_simple_guidance(intent)}

文档：
{chr(10).join(items)}

输出格式：数字,数字,数字（如：2,1,3）
结果："""
            
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 15,  # 进一步减少token
                "temperature": 0.0  # 最稳定的设置
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
                logger.info(f"DeepSeek简化重排序成功 - 意图: {intent}, 新序列: {rank_str}")
                return reranked
            else:
                logger.warning(f"DeepSeek返回格式异常，跳过重排序: {rank_str}")
                return results
            
        except Exception as e:
            logger.error(f"DeepSeek重排序失败，返回原序列: {e}")
            return results
    
    def _get_quick_intent(self, query: str) -> str:
        """快速意图检测，避免复杂分析"""
        if '个人信息' in query or '人员信息' in query:
            return 'personal_info'
        elif '财务' in query or '贷款' in query:
            return 'financial_data'
        else:
            return 'general'
    
    def _get_simple_guidance(self, intent: str) -> str:
        """获取简化的排序指导"""
        guidance_map = {
            'personal_info': "优先：完整个人信息",
            'financial_data': "优先：具体金额数据", 
            'general': "优先：内容相关性"
        }
        return guidance_map.get(intent, guidance_map['general'])
    
    def _analyze_query_intent(self, query: str) -> Dict:
        """分析查询意图 - 已弃用，保留兼容性"""
        return {'intent': self._get_quick_intent(query), 'keywords': []}
    
    def _get_intent_guidance(self, intent: str) -> str:
        """获取意图相关的排序指导 - 已弃用，保留兼容性"""
        return self._get_simple_guidance(intent)
    
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