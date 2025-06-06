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
    logger.warning("提示词服务导入失败，将使用默认提示词")
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
            desc += f"   内容: {result.get('chunk_text', '无内容')[:200]}...\n"
            desc += f"   相似度: {result.get('score', 0):.3f}"
            result_descriptions.append(desc)
        
        prompt = f"""请根据用户查询对以下文档片段进行重新排序，按相关性从高到低排列。

用户查询：{query}

文档片段：
{chr(10).join(result_descriptions)}

请仅返回重新排序后的序号列表，用逗号分隔（如：3,1,4,2,5）："""

        try:
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "你是一个文档相关性排序专家。"},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 50,
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
                
                logger.info(f"结果重排序完成 - 原序列: 1-{len(results_to_rank)}, 新序列: {rank_str}")
                return reranked_results
                
            except (ValueError, IndexError) as e:
                logger.error(f"解析重排序结果失败: {e}")
                return results
                
        except Exception as e:
            logger.error(f"结果重排序失败: {e}")
            return results  # 降级返回原结果
    
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
        prompt = f"""基于文档内容回答问题：

问题：{query}
文档内容：{context}

请提供准确的答案："""

        try:
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "你是文档问答助手，只基于提供的文档内容回答问题。"},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 500,
                "temperature": 0.7
            }
            
            response = self._make_request(data)
            return response['choices'][0]['message']['content'].strip()
            
        except Exception as e:
            logger.error(f"备用答案生成失败: {e}")
            return "抱歉，无法生成答案，请查看检索到的文档内容。"

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
            import re
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
            return "无法生成答案，请查看文档内容。"

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
            # 简化重排序逻辑
            return results
        except Exception as e:
            logger.error(f"Ollama重排序失败: {e}")
            return results
    
    def generate_answer(self, query: str, context: str, scenario: str = None, style: str = None) -> str:
        """使用Ollama生成答案"""
        try:
            prompt = f"""基于以下文档内容回答用户问题：

文档内容：
{context}

用户问题：{query}

请提供准确、简洁的回答："""

            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "你是一个专业的文档分析助手。"},
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            }
            
            response = self._make_request(data)
            return response['message']['content'].strip()
            
        except Exception as e:
            logger.error(f"Ollama答案生成失败: {e}")
            return "抱歉，无法生成答案。"

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
        
        system_prompt = """你是一个专业的文档管理和项目组织专家。

重要：你必须严格按照JSON格式回复，不要添加任何markdown标记或其他文本。

请仔细分析文档结构，识别已有内容和缺失内容，直接返回以下JSON结构：
{
  "document_type": "具体的文档类型(如：项目文档、法律案件、合同文件、技术文档、财务文档等)",
  "confidence": 0.0到1.0之间的数字,
  "current_structure_analysis": "详细分析当前已有的文件和文件夹，明确指出哪些内容已经存在。格式：已有内容包含：1.xxx文件夹 2.xxx文档 3.xxx资料",
  "missing_items": ["明确列出缺失的关键文件或文件夹，每项要具体说明缺失的内容"],
  "suggestions": ["基于缺失项目的具体改进建议"],
  "template_recommendation": "推荐的标准模板"
}

分析要求：
1. 在current_structure_analysis中要明确说明哪些内容"已有"、"存在"、"包含"
2. 在missing_items中要列出对应文档类型应该有但当前缺失的具体项目
3. 确保已有内容和缺失内容的描述清晰、具体

只返回JSON，不要添加任何解释或markdown格式。"""

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