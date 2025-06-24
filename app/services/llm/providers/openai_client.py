"""
OpenAI客户端实现

提供OpenAI GPT模型的完整功能实现
"""

import logging
from typing import List, Dict
from config import Config
from ..base_client import BaseLLMClient

logger = logging.getLogger(__name__)


class OpenAIClient(BaseLLMClient):
    """OpenAI客户端实现"""
    
    def __init__(self, model: str):
        provider_config = Config.LLM_PROVIDERS['openai']
        super().__init__(
            model=model,
            api_key=provider_config['api_key'],
            base_url=provider_config['base_url']
        )
    
    def optimize_query(self, query: str, scenario: str = None, template: str = None) -> str:
        """使用GPT优化查询"""
        try:
            if self.prompt_service:
                # 使用智能意图分析推荐最佳配置
                if not scenario and not template:
                    intent_analysis = self.prompt_service.analyze_query_intent(query)
                    scenario = intent_analysis.get('scenario')
                    template = intent_analysis.get('query_template', 'comprehensive')
                    logger.info(f"智能推荐 - 场景: {scenario}, 模板: {template}, 置信度: {intent_analysis.get('confidence', 0):.2f}")
                
                # 获取配置化提示词
                prompt_config = self.prompt_service.get_query_optimization_prompt(
                    query, scenario=scenario, template=template or 'comprehensive'
                )
                
                optimized_query = self._call_llm_with_prompt(
                    prompt_config['system_prompt'],
                    prompt_config['user_prompt'],
                    prompt_config['parameters']
                )
                
                # 提取最终的关键词（处理结构化输出）
                if '检索优化:' in optimized_query:
                    optimized_query = optimized_query.split('检索优化:')[-1].strip()
                elif '关键词:' in optimized_query:
                    optimized_query = optimized_query.split('关键词:')[-1].strip()
                
                logger.info(f"智能查询优化完成 - 原查询: {query}, 优化后: {optimized_query}")
                return optimized_query
            else:
                # 降级到原始逻辑
                return self._fallback_optimize_query(query)
                
        except Exception as e:
            logger.error(f"查询优化失败: {e}")
            return query  # 降级返回原查询
    
    def _fallback_optimize_query(self, query: str) -> str:
        """备用查询优化方法"""
        prompt = f"""请将用户查询优化为适合文档检索的关键词：

用户查询：{query}

输出关键词（空格分隔）："""

        try:
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "你是文档检索查询优化助手。"},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 100,
                "temperature": 0.3
            }
            
            response = self._make_request(data)
            return response['choices'][0]['message']['content'].strip()
            
        except Exception as e:
            logger.error(f"备用查询优化失败: {e}")
            return query
    
    def rerank_results(self, query: str, results: List[Dict]) -> List[Dict]:
        """使用GPT重排序结果"""
        if not results:
            return results
        
        # 限制重排序的结果数量
        batch_size = min(len(results), Config.LLM_RERANK_BATCH_SIZE)
        results_to_rank = results[:batch_size]
        
        # 构建结果描述
        result_descriptions = []
        for i, result in enumerate(results_to_rank):
            desc = f"{i+1}. 文档: {result.get('document', {}).get('name', '未知文档')}\n"
            desc += f"   内容: {result.get('chunk_text', '无内容')[:300]}...\n"  # 增加内容长度
            desc += f"   相似度: {result.get('score', 0):.3f}"
            result_descriptions.append(desc)
        
        # 分析查询意图，生成智能化重排提示词
        intent_analysis = self._analyze_query_intent(query)
        
        system_prompt = self._generate_rerank_system_prompt(intent_analysis)
        user_prompt = self._generate_rerank_user_prompt(query, result_descriptions, intent_analysis)

        try:
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 100,
                "temperature": 0.1
            }
            
            response = self._make_request(data)
            rank_str = response['choices'][0]['message']['content'].strip()
            
            # 解析排序结果
            try:
                ranks = [int(x.strip()) - 1 for x in rank_str.split(',')]  # 转为0索引
                reranked_results = []
                
                # 按新排序重组结果
                for rank in ranks:
                    if 0 <= rank < len(results_to_rank):
                        result = results_to_rank[rank].copy()
                        result['rerank_score'] = len(ranks) - ranks.index(rank)  # 添加重排序分数
                        reranked_results.append(result)
                
                # 添加未参与重排序的结果
                reranked_results.extend(results[batch_size:])
                
                logger.info(f"智能重排序完成 - 查询意图: {intent_analysis.get('intent', '未知')}, 新序列: {rank_str}")
                return reranked_results
                
            except (ValueError, IndexError) as e:
                logger.error(f"解析重排序结果失败: {e}")
                return results
                
        except Exception as e:
            logger.error(f"结果重排序失败: {e}")
            return results  # 降级返回原结果
    
    def _analyze_query_intent(self, query: str) -> Dict:
        """分析查询意图"""
        intent_patterns = {
            'personal_info': ['个人信息', '人员信息', '身份信息', '联系方式', '个人资料', '基本信息'],
            'financial_data': ['财务数据', '贷款信息', '金融数据', '收入', '负债', '资产'],
            'document_summary': ['总结', '概述', '简介', '摘要', '内容', '主要'],
            'specific_details': ['详细', '具体', '明细', '细节', '详情'],
            'comparison': ['比较', '对比', '差异', '区别', '相同'],
            'time_related': ['时间', '日期', '期间', '历史', '记录']
        }
        
        for intent, keywords in intent_patterns.items():
            if any(keyword in query for keyword in keywords):
                return {
                    'intent': intent,
                    'keywords': [kw for kw in keywords if kw in query]
                }
        
        return {'intent': 'general', 'keywords': []}
    
    def _generate_rerank_system_prompt(self, intent_analysis: Dict) -> str:
        """根据查询意图生成系统提示词"""
        intent = intent_analysis.get('intent', 'general')
        
        base_prompt = "你是一个智能文档相关性排序专家。你需要根据用户的具体查询需求，对文档片段进行精准排序。"
        
        intent_specific_prompts = {
            'personal_info': """
你专门处理个人信息查询。排序时请优先考虑：
1. 包含完整个人信息字段的文档（姓名、身份证、联系方式、地址等）
2. 结构化的个人资料表格或表单
3. 信息完整度和准确性
4. 避免只有姓名提及而无其他信息的片段排在前面""",
            
            'financial_data': """
你专门处理财务数据查询。排序时请优先考虑：
1. 包含具体数字和金额的文档
2. 结构化的财务表格或报表
3. 贷款、收入、资产等相关数据的完整性
4. 数据的时效性和准确性""",
            
            'document_summary': """
你专门处理文档总结查询。排序时请优先考虑：
1. 包含概述性信息的段落
2. 文档开头或结尾的总结性内容
3. 标题和关键要点
4. 内容的全面性和代表性""",
            
            'specific_details': """
你专门处理具体细节查询。排序时请优先考虑：
1. 包含详细描述和具体数据的片段
2. 技术细节或操作步骤
3. 明细列表或详细说明
4. 信息的准确性和可操作性""",
            
            'general': """
你处理一般性查询。排序时请优先考虑：
1. 内容与查询关键词的匹配程度
2. 信息的完整性和准确性
3. 上下文的相关性
4. 内容的实用性"""
        }
        
        return base_prompt + intent_specific_prompts.get(intent, intent_specific_prompts['general'])
    
    def _generate_rerank_user_prompt(self, query: str, result_descriptions: List[str], intent_analysis: Dict) -> str:
        """根据查询意图生成用户提示词"""
        intent = intent_analysis.get('intent', 'general')
        keywords = intent_analysis.get('keywords', [])
        
        base_prompt = f"""请根据用户的具体查询需求对以下文档片段进行重新排序，按相关性从高到低排列。

用户查询：{query}
查询意图：{intent}
关键要素：{', '.join(keywords) if keywords else '通用查询'}

文档片段：
{chr(10).join(result_descriptions)}

排序指导原则：
"""
        
        ranking_guidelines = {
            'personal_info': """
- 优先排序包含多个个人信息字段的文档
- 结构化的个人资料（如申请表、登记表）排在前面
- 仅有姓名提及但无其他信息的文档排在后面
- 考虑信息的完整性和实用性""",
            
            'financial_data': """
- 优先排序包含具体金额和财务数据的文档
- 表格化的财务信息排在前面
- 考虑数据的准确性和相关性
- 综合性财务报告优于单一数据点""",
            
            'general': """
- 优先排序内容完整、信息丰富的文档
- 考虑与查询关键词的匹配度
- 结构化信息优于零散信息
- 准确性和实用性并重"""
        }
        
        guideline = ranking_guidelines.get(intent, ranking_guidelines['general'])
        
        return base_prompt + guideline + "\n\n请仅返回重新排序后的序号列表，用逗号分隔（如：3,1,4,2,5）："
    
    def generate_answer(self, query: str, context: str, scenario: str = None, style: str = None) -> str:
        """基于检索结果生成答案"""
        try:
            if self.prompt_service:
                # 使用智能意图分析推荐最佳配置
                if not scenario and not style:
                    intent_analysis = self.prompt_service.analyze_query_intent(query)
                    scenario = intent_analysis.get('scenario')
                    style = intent_analysis.get('answer_template', 'structured_answer')
                    logger.info(f"智能推荐答案风格 - 场景: {scenario}, 风格: {style}")
                
                # 获取配置化提示词
                prompt_config = self.prompt_service.get_result_assembly_prompt(
                    query, context, scenario=scenario, template=style or 'structured_answer'
                )
                
                answer = self._call_llm_with_prompt(
                    prompt_config['system_prompt'],
                    prompt_config['user_prompt'],
                    prompt_config['parameters']
                )
                
                logger.info(f"智能答案生成完成 - 查询: {query}")
                return answer
            else:
                # 降级到原始逻辑
                return self._fallback_generate_answer(query, context)
                
        except Exception as e:
            logger.error(f"答案生成失败: {e}")
            return f"抱歉，生成答案时出现错误：{str(e)}"
    
    def _fallback_generate_answer(self, query: str, context: str) -> str:
        """备用答案生成方法"""
        
        # 判断是否是普通聊天模式（context为空）
        is_conversational = not context.strip()
        
        if is_conversational:
            # 普通聊天模式
            prompt = f"""你是一个友好、专业的AI助手。请直接回答用户的问题，进行自然的对话交流。

用户问题：{query}

请提供友好、准确的回答："""
            system_content = "你是一个友好、专业的AI助手，可以回答各种问题并进行自然对话。"
        else:
            # 文档检索模式
            prompt = f"""基于文档内容回答问题：

问题：{query}
文档内容：{context}

请提供准确的答案："""
            system_content = "你是文档问答助手，只基于提供的文档内容回答问题。"

        try:
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": Config.LLM_MAX_TOKENS,
                "temperature": Config.LLM_TEMPERATURE
            }
            
            response = self._make_request(data)
            return response['choices'][0]['message']['content'].strip()
            
        except Exception as e:
            logger.error(f"备用答案生成失败: {e}")
            if is_conversational:
                return "抱歉，我暂时无法回答您的问题。请稍后再试。"
            else:
                return "抱歉，无法生成答案，请查看检索到的文档内容。" 