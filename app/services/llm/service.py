"""
LLM服务统一接口

提供所有LLM相关功能的统一访问入口，保持与现有代码的完全兼容性
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from config import Config
from .factory import LLMClientFactory

logger = logging.getLogger(__name__)


class LLMService:
    """LLM服务统一接口"""
    
    @staticmethod
    def get_available_models() -> List[Dict]:
        """获取可用的LLM模型"""
        models = []
        for provider_key, provider_config in Config.LLM_PROVIDERS.items():
            # 检查provider是否可用
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
                models.append({
                    'provider': provider_key,
                    'provider_name': provider_config['name'],
                    'model_key': model_key,
                    'model_name': model_name,
                    'display_name': f"{provider_config['name']} - {model_name}",
                    'full_key': f"{provider_key}:{model_key}",
                    'is_available': is_available
                })
        return models
    
    @staticmethod
    def get_service_status() -> Dict:
        """获取LLM服务状态"""
        try:
            models = LLMService.get_available_models()
            available_count = sum(1 for model in models if model['is_available'])
            
            return {
                'total_models': len(models),
                'available_models': available_count,
                'features': {
                    'query_optimization': Config.ENABLE_LLM_QUERY_OPTIMIZATION,
                    'result_reranking': Config.ENABLE_LLM_RESULT_RERANKING,
                    'answer_generation': Config.ENABLE_LLM_ANSWER_GENERATION
                },
                'default_provider': Config.DEFAULT_LLM_PROVIDER,
                'default_model': Config.DEFAULT_LLM_MODEL,
                'timeout': Config.LLM_TIMEOUT,
                'max_context_length': Config.LLM_MAX_CONTEXT_LENGTH
            }
        except Exception as e:
            logger.error(f"获取LLM服务状态失败: {e}")
            return {
                'error': str(e),
                'status': 'error'
            }
    
    @staticmethod
    def get_config_info() -> Dict:
        """获取LLM配置信息"""
        try:
            models = LLMService.get_available_models()
            default_selection = f"{Config.DEFAULT_LLM_PROVIDER}:{Config.DEFAULT_LLM_MODEL}"
            
            return {
                'models': models,
                'default': default_selection,
                'features': {
                    'query_optimization': Config.ENABLE_LLM_QUERY_OPTIMIZATION,
                    'result_reranking': Config.ENABLE_LLM_RESULT_RERANKING,
                    'answer_generation': Config.ENABLE_LLM_ANSWER_GENERATION
                }
            }
        except Exception as e:
            logger.error(f"获取LLM配置信息失败: {e}")
            raise e
    
    @staticmethod
    def optimize_query(query: str, llm_model: str = None, scenario: str = None, template: str = None) -> str:
        """查询优化"""
        if not Config.ENABLE_LLM_QUERY_OPTIMIZATION or not llm_model:
            return query
        
        client = LLMClientFactory.create_client(llm_model)
        if not client:
            return query
        
        return client.optimize_query(query, scenario=scenario, template=template)
    
    @staticmethod
    def rerank_results(query: str, results: List[Dict], llm_model: str = None) -> List[Dict]:
        """结果重排序"""
        if not Config.ENABLE_LLM_RESULT_RERANKING or not llm_model or not results:
            return results
        
        client = LLMClientFactory.create_client(llm_model)
        if not client:
            return results
        
        return client.rerank_results(query, results)
    
    @staticmethod
    def rerank_file_results(query: str, file_results: List[Dict], llm_model: str = None) -> List[Dict]:
        """文件级别结果重排序"""
        if not Config.ENABLE_LLM_RESULT_RERANKING or not llm_model or not file_results:
            return file_results
        
        try:
            # 转换文件结果为chunk格式进行重排序
            temp_results = []
            for i, file_result in enumerate(file_results):
                doc_name = file_result['document']['name']
                # 合并该文件的所有相关片段作为摘要
                chunks_text = ' | '.join([chunk['text'][:100] for chunk in file_result['chunks'][:3]])
                temp_results.append({
                    'text': f"文档《{doc_name}》: {chunks_text}",
                    'score': file_result['score'],
                    'original_index': i
                })
            
            # 使用现有的重排序逻辑
            client = LLMClientFactory.create_client(llm_model)
            if client:
                reranked_temp = client.rerank_results(query, temp_results)
                
                # 根据重排序结果重新排列文件结果
                reranked_files = []
                for temp_result in reranked_temp:
                    original_index = temp_result['original_index']
                    reranked_files.append(file_results[original_index])
                
                return reranked_files
            
        except Exception as e:
            logger.error(f"文件级别重排序失败: {e}")
        
        return file_results
    
    @staticmethod
    def generate_answer(query: str, context: str, llm_model: str = None, scenario: str = None, style: str = None) -> Optional[str]:
        """答案生成"""
        if not Config.ENABLE_LLM_ANSWER_GENERATION or not llm_model:
            return None
        
        client = LLMClientFactory.create_client(llm_model)
        if not client:
            return None
        
        return client.generate_answer(query, context, scenario=scenario, style=style)

    @staticmethod
    def analyze_document_structure(document_name: str, document_tags: List[Dict], 
                                   document_tree: Dict, llm_model: str = None) -> Optional[Dict]:
        """分析文档结构并提供改进建议"""
        if not llm_model:
            return None
        
        client = LLMClientFactory.create_client(llm_model)
        if not client:
            return None
        
        # 构建分析提示词
        tags_info = ", ".join([tag['name'] for tag in document_tags]) if document_tags else "无标签"
        
        user_prompt = f"""文档名称：{document_name}
标签信息：{tags_info}
目录结构：
{json.dumps(document_tree, ensure_ascii=False, indent=2)}

请直接返回JSON格式的分析结果："""

        try:
            # 使用客户端的generate_answer方法来生成分析
            analysis_text = client.generate_answer(
                query=user_prompt,
                context="",
                scenario="document_analysis"
            )
            
            # 尝试解析JSON响应
            try:
                # 清理响应文本
                cleaned_text = analysis_text.strip()
                
                # 处理markdown代码块
                if '```json' in cleaned_text:
                    json_start = cleaned_text.find('```json') + 7
                    json_end = cleaned_text.find('```', json_start)
                    if json_end != -1:
                        cleaned_text = cleaned_text[json_start:json_end].strip()
                elif '```' in cleaned_text:
                    # 处理没有指定语言的代码块
                    json_start = cleaned_text.find('```') + 3
                    json_end = cleaned_text.find('```', json_start)
                    if json_end != -1:
                        cleaned_text = cleaned_text[json_start:json_end].strip()
                
                # 尝试找到JSON对象的开始和结束
                if not cleaned_text.startswith('{'):
                    brace_start = cleaned_text.find('{')
                    if brace_start != -1:
                        cleaned_text = cleaned_text[brace_start:]
                
                if not cleaned_text.endswith('}'):
                    brace_end = cleaned_text.rfind('}')
                    if brace_end != -1:
                        cleaned_text = cleaned_text[:brace_end + 1]
                
                logger.info(f"尝试解析JSON: {cleaned_text[:200]}...")
                analysis_result = json.loads(cleaned_text)
                logger.info("JSON解析成功")
                return analysis_result
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON解析失败: {e}, 原始响应: {analysis_text[:200]}...")
                # 如果JSON解析失败，返回原始文本分析
                return {
                    "document_type": "文档类型分析",
                    "confidence": 0.7,
                    "current_structure_analysis": "AI模型返回了详细的分析内容，但未采用标准JSON格式。",
                    "missing_items": ["建议重新分析以获取结构化结果"],
                    "suggestions": [analysis_text if len(analysis_text) < 1000 else analysis_text[:1000] + "..."],
                    "template_recommendation": "标准文档管理模板"
                }
                
        except Exception as e:
            logger.error(f"文档结构分析失败: {e}")
            return None

    @staticmethod
    def analyze_user_intent(query: str, llm_model: str = None, scenario: str = None) -> Dict[str, Any]:
        """
        使用全新的意图识别服务分析用户输入的意图
        
        Args:
            query: 用户查询
            llm_model: LLM模型名称（兼容性参数，新架构从配置文件读取）
            scenario: 场景类型（可选）
        """
        try:
            # 使用新的意图识别服务
            from app.services.intent_service import intent_service
            
            result = intent_service.analyze_intent(query, scenario)
            
            # 兼容性处理：确保返回结果格式符合原有接口
            if 'model_used' not in result:
                result['model_used'] = llm_model or 'intent_service_v2'
            
            if 'prompt_source' not in result:
                result['prompt_source'] = 'intent_config_v2'
                
            logger.info(f"意图识别完成 - 查询: {query[:50]}, "
                       f"意图: {result.get('intent_type')}, "
                       f"置信度: {result.get('confidence'):.3f}, "
                       f"方法: {result.get('analysis_method')}")
            
            return result
            
        except Exception as e:
            logger.error(f"新意图识别服务失败，使用降级处理: {e}")
            # 如果新服务失败，使用兜底方案
            return LLMService._emergency_fallback(query, scenario)
    
    @staticmethod
    def _emergency_fallback(query: str, scenario: str = None) -> Dict[str, Any]:
        """紧急降级处理：当新意图识别服务完全失败时使用"""
        logger.warning(f"使用紧急降级处理: {query[:50]}")
        
        # 简单的关键词匹配降级
        query_lower = query.lower()
        
        # 创建操作关键词
        create_keywords = ['创建', '新建', '建立', '生成', '制作', '添加', '建']
        search_keywords = ['查找', '搜索', '寻找', '检索', '查询', '分析', '检查']
        chat_keywords = ['什么是', '如何', '为什么', '请解释', '建议', '推荐', '你是谁', '你好']
        
        # 判断意图
        if any(keyword in query_lower for keyword in create_keywords):
            return {
                "intent_type": "mcp_action",
                "confidence": 0.6,
                "action_type": "create_file",
                "parameters": {"file_name": None, "folder_name": None},
                "reasoning": "紧急降级：检测到创建关键词",
                "analysis_method": "emergency_fallback",
                "scenario": scenario,
                "timestamp": datetime.now().isoformat()
            }
        elif any(keyword in query_lower for keyword in chat_keywords):
            return {
                "intent_type": "normal_chat",
                "confidence": 0.5,
                "action_type": "chat",
                "parameters": {"chat_topic": query[:50]},
                "reasoning": "紧急降级：检测到对话关键词",
                "analysis_method": "emergency_fallback",
                "scenario": scenario,
                "timestamp": datetime.now().isoformat()
            }
        else:
            # 默认为普通聊天（根据记忆中的修复，这里改为normal_chat作为兜底）
            return {
                "intent_type": "normal_chat",
                "confidence": 0.4,
                "action_type": "chat",
                "parameters": {"chat_topic": query},
                "reasoning": "紧急降级：默认普通聊天",
                "analysis_method": "emergency_fallback",
                "scenario": scenario,
                "timestamp": datetime.now().isoformat()
            }

    @staticmethod
    def extract_search_keywords(query: str, llm_model: str = None) -> Dict[str, Any]:
        """
        使用LLM从用户查询中提取最佳的搜索关键词
        """
        if not llm_model:
            llm_model = f"{Config.DEFAULT_LLM_PROVIDER}:{Config.DEFAULT_LLM_MODEL}"
        
        client = LLMClientFactory.create_client(llm_model)
        if not client:
            logger.warning(f"无法创建LLM客户端: {llm_model}，使用备用关键词提取")
            return LLMService._fallback_keyword_extraction(query)
        
        try:
            system_prompt = """你是一个专业的搜索关键词提取专家。你的任务是从用户的自然语言查询中提取最有效的搜索关键词。

请严格按照以下JSON格式返回结果（不要添加markdown格式或其他文本）：
{
  "keywords": ["关键词1", "关键词2", "关键词3"],
  "optimized_query": "优化后的搜索查询",
  "reasoning": "关键词提取的依据"
}"""

            user_prompt = f"""请从以下用户查询中提取搜索关键词：

用户查询："{query}"

请返回JSON格式的关键词提取结果："""

            # 调用LLM进行关键词提取
            response = client._call_llm_with_prompt(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                parameters={
                    "max_tokens": 200,
                    "temperature": 0.2
                }
            )
            
            # 解析JSON响应
            try:
                # 清理响应文本
                cleaned_response = response.strip()
                
                # 处理可能的markdown代码块
                if '```json' in cleaned_response:
                    json_start = cleaned_response.find('```json') + 7
                    json_end = cleaned_response.find('```', json_start)
                    if json_end != -1:
                        cleaned_response = cleaned_response[json_start:json_end].strip()
                elif '```' in cleaned_response:
                    json_start = cleaned_response.find('```') + 3
                    json_end = cleaned_response.find('```', json_start)
                    if json_end != -1:
                        cleaned_response = cleaned_response[json_start:json_end].strip()
                
                # 找到JSON对象
                if not cleaned_response.startswith('{'):
                    brace_start = cleaned_response.find('{')
                    if brace_start != -1:
                        cleaned_response = cleaned_response[brace_start:]
                
                if not cleaned_response.endswith('}'):
                    brace_end = cleaned_response.rfind('}')
                    if brace_end != -1:
                        cleaned_response = cleaned_response[:brace_end + 1]
                
                keyword_result = json.loads(cleaned_response)
                
                # 构建完整的返回结果
                result = {
                    'original_query': query,
                    'keywords': keyword_result.get('keywords', []),
                    'optimized_query': keyword_result.get('optimized_query', query),
                    'reasoning': keyword_result.get('reasoning', '使用LLM提取关键词'),
                    'used_llm': True
                }
                
                logger.info(f"LLM关键词提取成功 - 原查询: {query}, 关键词: {result['keywords']}")
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"LLM关键词提取JSON解析失败: {e}, 原始响应: {response[:200]}...")
                return LLMService._fallback_keyword_extraction(query)
                
        except Exception as e:
            logger.error(f"LLM关键词提取失败: {e}")
            return LLMService._fallback_keyword_extraction(query)
    
    @staticmethod
    def _fallback_keyword_extraction(query: str) -> Dict[str, Any]:
        """
        备用的基于规则的关键词提取
        """
        import re
        
        try:
            # 尝试导入jieba进行中文分词
            import jieba
            words = list(jieba.cut(query))
        except ImportError:
            # 如果没有jieba，使用简单的空格分词
            words = query.split()
        
        # 定义停用词
        stop_words = {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
            '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看',
            '好', '自己', '这', '那', '里', '时', '把', '为', '但', '与', '及', '或',
            '等', '如', '由', '从', '以', '而', '且', '然后', '因为', '所以'
        }
        
        # 过滤停用词和短词
        keywords = []
        for word in words:
            word = word.strip()
            if (len(word) > 1 and 
                word not in stop_words and 
                not re.match(r'^[^\w\s]+$', word)):  # 排除纯标点
                keywords.append(word)
        
        # 保留前5个关键词
        keywords = keywords[:5] if len(keywords) > 5 else keywords
        
        # 如果没有提取到关键词，使用原查询
        if not keywords:
            keywords = [query]
        
        # 生成优化查询
        optimized_query = ' '.join(keywords) if keywords else query
        
        return {
            'original_query': query,
            'keywords': keywords,
            'optimized_query': optimized_query,
            'reasoning': '使用基础分词和停用词过滤（备用方法）',
            'used_llm': False
        } 