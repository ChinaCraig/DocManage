"""
全新意图识别服务
版本: v2.0
架构: LLM主要分析 + 关键词降级分析
"""

import os
import re
import json
import yaml
import logging
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from config import Config

logger = logging.getLogger(__name__)

class IntentRecognitionService:
    """
    意图识别服务 - 新架构设计
    
    功能特性:
    1. 支持多种LLM提供商 (DeepSeek/豆包/智谱AI等)
    2. LLM主要分析 + 关键词降级分析双层架构
    3. 智能降级处理机制
    4. 结果缓存优化
    5. 完整的错误处理
    """
    
    def __init__(self):
        self.config = None
        self.config_file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            'prompts', 
            'intent_config.yaml'
        )
        self.cache = {}  # 简单内存缓存
        self.load_config()
        
    def load_config(self):
        """加载意图识别配置"""
        try:
            if os.path.exists(self.config_file_path):
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f)
                logger.info(f"意图识别配置加载成功: {self.config_file_path}")
            else:
                logger.error(f"意图识别配置文件不存在: {self.config_file_path}")
                self.config = self._get_default_config()
        except Exception as e:
            logger.error(f"加载意图识别配置失败: {e}")
            self.config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置（降级方案）"""
        return {
            'llm_config': {
                'service_mode': 'remote',
                'current_provider': 'deepseek',
                'current_model': 'deepseek-chat',
                'parameters': {
                    'max_tokens': 300,
                    'temperature': 0.1,
                    'timeout': 30
                }
            },
            'intent_prompts': {
                'confidence_threshold': 0.6
            },
            'fallback_config': {
                'enabled': True,
                'default_intent': 'normal_chat',
                'default_confidence': 0.5
            },
            'keyword_analysis': {
                'enabled': True
            }
        }
    
    def analyze_intent(self, query: str, scenario: str = None) -> Dict[str, Any]:
        """
        分析用户意图 - 主入口函数
        
        Args:
            query: 用户输入查询
            scenario: 场景类型（可选）
            
        Returns:
            Dict: 意图分析结果
        """
        if not query or not query.strip():
            return self._create_error_result("查询内容为空")
        
        query = query.strip()
        
        # 检查缓存
        cache_key = self._generate_cache_key(query, scenario)
        if self._is_cache_enabled() and cache_key in self.cache:
            cached_result = self.cache[cache_key]
            if self._is_cache_valid(cached_result):
                logger.info(f"使用缓存结果: {query[:50]}")
                return cached_result['result']
        
        # 尝试LLM分析
        llm_result = self._analyze_with_llm(query, scenario)
        
        # 检查LLM结果是否需要降级
        if self._should_fallback(llm_result):
            logger.info(f"LLM分析结果不满足要求，启动降级处理: {query[:50]}")
            fallback_result = self._analyze_with_fallback(query, scenario, llm_result)
            final_result = fallback_result
        else:
            final_result = llm_result
        
        # 缓存结果
        if self._is_cache_enabled():
            self._cache_result(cache_key, final_result)
        
        # 记录分析指标
        self._log_analysis_metrics(query, final_result)
        
        return final_result
    
    def _analyze_with_llm(self, query: str, scenario: str = None) -> Dict[str, Any]:
        """使用LLM进行意图分析"""
        try:
            # 获取LLM客户端
            client = self._create_llm_client()
            if not client:
                return self._create_error_result("无法创建LLM客户端", "llm_client_error")
            
            # 获取提示词
            system_prompt = self._get_system_prompt(scenario)
            user_prompt = self._get_user_prompt(query)
            parameters = self._get_llm_parameters()
            
            # 调用LLM
            response = self._call_llm(client, system_prompt, user_prompt, parameters)
            
            # 解析响应
            parsed_result = self._parse_llm_response(response)
            
            # 添加元数据
            parsed_result.update({
                'analysis_method': 'llm',
                'model_used': self._get_current_model(),
                'scenario': scenario,
                'timestamp': datetime.now().isoformat()
            })
            
            return parsed_result
            
        except Exception as e:
            logger.error(f"LLM意图分析失败: {e}")
            return self._create_error_result(f"LLM分析失败: {str(e)}", "llm_analysis_error")
    
    def _analyze_with_fallback(self, query: str, scenario: str = None, llm_result: Dict = None) -> Dict[str, Any]:
        """使用降级方法进行意图分析"""
        if not self._is_fallback_enabled():
            return llm_result or self._create_error_result("降级处理已禁用")
        
        # 选择降级策略
        strategy = self.config.get('fallback_config', {}).get('strategy', 'keyword_analysis')
        
        if strategy == 'keyword_analysis':
            return self._analyze_with_keywords(query, scenario)
        elif strategy == 'fixed_response':
            return self._create_fixed_fallback_result(query, scenario)
        elif strategy == 'hybrid':
            # 先尝试关键词，再固定响应
            keyword_result = self._analyze_with_keywords(query, scenario)
            if keyword_result.get('confidence', 0) > 0.4:
                return keyword_result
            return self._create_fixed_fallback_result(query, scenario)
        else:
            return self._create_fixed_fallback_result(query, scenario)
    
    def _analyze_with_keywords(self, query: str, scenario: str = None) -> Dict[str, Any]:
        """基于关键词的意图分析"""
        try:
            if not self._is_keyword_analysis_enabled():
                return self._create_fixed_fallback_result(query, scenario)
            
            query_lower = query.lower()
            keyword_config = self.config.get('keyword_analysis', {})
            intent_keywords = keyword_config.get('intent_keywords', {})
            weights = keyword_config.get('weights', {})
            
            # 分析各个意图的得分
            intent_scores = {}
            
            for intent_type, keyword_sets in intent_keywords.items():
                score = 0.0
                base_confidence = keyword_sets.get('confidence_base', 0.5)
                
                # 主要关键词匹配
                primary_keywords = keyword_sets.get('primary', [])
                for keyword_group in primary_keywords:
                    for keyword in keyword_group:
                        if keyword in query_lower:
                            score += weights.get('exact_match', 1.0)
                
                # 次要关键词匹配
                secondary_keywords = keyword_sets.get('secondary', [])
                for keyword_group in secondary_keywords:
                    for keyword in keyword_group:
                        if keyword in query_lower:
                            score += weights.get('partial_match', 0.7)
                
                # 计算最终置信度
                confidence = min(0.9, base_confidence + (score * 0.1))
                intent_scores[intent_type] = confidence
            
            # 应用上下文增强规则
            intent_scores = self._apply_context_rules(query, intent_scores)
            
            # 应用文件类型检测
            intent_scores = self._apply_file_detection(query, intent_scores)
            
            # 按优先级顺序选择意图（MCP > knowledge_search > normal_chat）
            if intent_scores:
                # 定义优先级顺序
                priority_order = ['mcp_action', 'knowledge_search', 'normal_chat']
                
                # 按优先级和置信度选择最佳意图
                best_intent = None
                best_confidence = 0
                
                for intent_type in priority_order:
                    if intent_type in intent_scores:
                        confidence = intent_scores[intent_type]
                        # 对于高优先级意图，较低的置信度阈值也接受
                        min_threshold = 0.3 if intent_type == 'mcp_action' else 0.4 if intent_type == 'knowledge_search' else 0.2
                        
                        if confidence > min_threshold and confidence > best_confidence:
                            best_intent = (intent_type, confidence)
                            best_confidence = confidence
                            break  # 找到符合条件的高优先级意图就停止
                
                # 如果没有找到合适的意图，使用最高分意图
                if not best_intent:
                    best_intent = max(intent_scores.items(), key=lambda x: x[1])
                
                intent_type, confidence = best_intent
                
                # 确定操作类型和参数
                action_type, parameters = self._determine_action_and_parameters(intent_type, query)
                
                return {
                    'intent_type': intent_type,
                    'confidence': confidence,
                    'action_type': action_type,
                    'parameters': parameters,
                    'reasoning': f'基于关键词分析，匹配{intent_type}意图',
                    'analysis_method': 'keyword',
                    'scenario': scenario,
                    'keyword_scores': intent_scores,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                return self._create_fixed_fallback_result(query, scenario)
                
        except Exception as e:
            logger.error(f"关键词意图分析失败: {e}")
            return self._create_fixed_fallback_result(query, scenario)
    
    def _apply_context_rules(self, query: str, intent_scores: Dict[str, float]) -> Dict[str, float]:
        """应用上下文增强规则"""
        try:
            context_rules = self.config.get('keyword_analysis', {}).get('context_rules', {})
            
            for rule_name, rule_config in context_rules.items():
                patterns = rule_config.get('patterns', [])
                intent_boost = rule_config.get('intent_boost', {})
                
                # 检查模式匹配
                for pattern in patterns:
                    if re.search(pattern, query, re.IGNORECASE):
                        # 应用增强
                        for intent_type, boost in intent_boost.items():
                            if intent_type in intent_scores:
                                intent_scores[intent_type] = min(0.95, intent_scores[intent_type] + boost)
                        break
            
            return intent_scores
            
        except Exception as e:
            logger.error(f"应用上下文规则失败: {e}")
            return intent_scores
    
    def _apply_file_detection(self, query: str, intent_scores: Dict[str, float]) -> Dict[str, float]:
        """应用文件类型检测"""
        try:
            file_detection = self.config.get('keyword_analysis', {}).get('file_detection', {})
            extensions = file_detection.get('extensions', [])
            confidence_boost = file_detection.get('confidence_boost', 0.2)
            
            query_lower = query.lower()
            
            # 检查文件扩展名
            for ext_group in extensions:
                for ext in ext_group:
                    if ext in query_lower:
                        # 增强MCP操作意图
                        if 'mcp_action' in intent_scores:
                            intent_scores['mcp_action'] = min(0.95, intent_scores['mcp_action'] + confidence_boost)
                        break
            
            return intent_scores
            
        except Exception as e:
            logger.error(f"应用文件类型检测失败: {e}")
            return intent_scores
    
    def _determine_action_and_parameters(self, intent_type: str, query: str) -> Tuple[str, Dict[str, Any]]:
        """根据意图类型确定操作类型和参数"""
        parameters = {}
        
        if intent_type == 'normal_chat':
            action_type = 'chat'
            parameters['chat_topic'] = self._extract_chat_topic(query)
            
        elif intent_type == 'knowledge_search':
            action_type = 'search_documents'
            parameters['search_keywords'] = self._extract_search_keywords(query)
            
        elif intent_type == 'mcp_action':
            # 判断是创建文件还是文件夹
            if self._is_file_creation(query):
                action_type = 'create_file'
                parameters['file_name'] = self._extract_file_name(query)
            elif self._is_folder_creation(query):
                action_type = 'create_folder'
                parameters['folder_name'] = self._extract_folder_name(query)
            else:
                action_type = 'other'
                
            parameters['parent_folder'] = self._extract_parent_folder(query)
        else:
            action_type = 'other'
        
        return action_type, parameters
    
    def _create_llm_client(self):
        """创建LLM客户端"""
        try:
            provider = self.config.get('llm_config', {}).get('current_provider', 'deepseek')
            model = self.config.get('llm_config', {}).get('current_model', 'deepseek-chat')
            
            # 调用LLMClientFactory创建客户端
            from app.services.llm import LLMClientFactory
            
            client = LLMClientFactory.create_client(f"{provider}:{model}")
            return client
            
        except Exception as e:
            logger.error(f"创建LLM客户端失败: {e}")
            return None
    
    def _call_llm(self, client, system_prompt: str, user_prompt: str, parameters: Dict) -> str:
        """调用LLM"""
        try:
            response = client._call_llm_with_prompt(system_prompt, user_prompt, parameters)
            return response
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            raise e
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应"""
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
            
            # 解析JSON
            result = json.loads(cleaned_response)
            
            # 验证必需字段
            required_fields = ['intent_type', 'confidence', 'action_type', 'parameters', 'reasoning']
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"缺少必需字段: {field}")
            
            return result
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"解析LLM响应失败: {e}, 原始响应: {response[:200]}")
            raise Exception(f"JSON解析失败: {str(e)}")
    
    def _should_fallback(self, llm_result: Dict[str, Any]) -> bool:
        """判断是否需要降级处理 - 仅当LLM分析真正失败时才降级"""
        if not llm_result:
            return True
        
        # 检查是否是错误结果（真正的LLM失败）
        if 'error' in llm_result:
            logger.info(f"LLM分析出现错误，触发降级处理: {llm_result.get('error')}")
            return True
        
        # 移除置信度检查 - 不再因为置信度低而降级
        # 只要LLM正常返回结果，就信任其判断，不进行降级
        
        return False
    
    def _create_error_result(self, error_message: str, error_type: str = "unknown_error") -> Dict[str, Any]:
        """创建错误结果"""
        fallback_config = self.config.get('fallback_config', {})
        
        return {
            'intent_type': fallback_config.get('default_intent', 'normal_chat'),
            'confidence': fallback_config.get('default_confidence', 0.5),
            'action_type': 'chat',
            'parameters': {'chat_topic': error_message},
            'reasoning': f'发生错误: {error_message}',
            'error': error_message,
            'error_type': error_type,
            'analysis_method': 'error_fallback',
            'timestamp': datetime.now().isoformat()
        }
    
    def _create_fixed_fallback_result(self, query: str, scenario: str = None) -> Dict[str, Any]:
        """创建固定的降级结果"""
        fallback_config = self.config.get('fallback_config', {})
        
        return {
            'intent_type': fallback_config.get('default_intent', 'normal_chat'),
            'confidence': fallback_config.get('default_confidence', 0.5),
            'action_type': 'chat',
            'parameters': {'chat_topic': query},
            'reasoning': '使用固定降级策略',
            'analysis_method': 'fixed_fallback',
            'scenario': scenario,
            'timestamp': datetime.now().isoformat()
        }
    
    # 辅助方法
    def _get_system_prompt(self, scenario: str = None) -> str:
        """获取系统提示词"""
        return self.config.get('intent_prompts', {}).get('system_prompt', '')
    
    def _get_user_prompt(self, query: str) -> str:
        """获取用户提示词"""
        template = self.config.get('intent_prompts', {}).get('user_prompt_template', '')
        return template.format(query=query)
    
    def _get_llm_parameters(self) -> Dict[str, Any]:
        """获取LLM参数"""
        return self.config.get('llm_config', {}).get('parameters', {})
    
    def _get_current_model(self) -> str:
        """获取当前模型"""
        provider = self.config.get('llm_config', {}).get('current_provider', 'deepseek')
        model = self.config.get('llm_config', {}).get('current_model', 'deepseek-chat')
        return f"{provider}:{model}"
    
    def _is_fallback_enabled(self) -> bool:
        """检查是否启用降级处理"""
        return self.config.get('fallback_config', {}).get('enabled', True)
    
    def _is_keyword_analysis_enabled(self) -> bool:
        """检查是否启用关键词分析"""
        return self.config.get('keyword_analysis', {}).get('enabled', True)
    
    def _is_cache_enabled(self) -> bool:
        """检查是否启用缓存"""
        return self.config.get('performance', {}).get('cache', {}).get('enabled', True)
    
    def _generate_cache_key(self, query: str, scenario: str = None) -> str:
        """生成缓存键"""
        key_data = f"{query}_{scenario or 'default'}"
        return hashlib.md5(key_data.encode('utf-8')).hexdigest()
    
    def _is_cache_valid(self, cached_item: Dict) -> bool:
        """检查缓存是否有效"""
        ttl = self.config.get('performance', {}).get('cache', {}).get('ttl', 3600)
        timestamp = cached_item.get('timestamp')
        if not timestamp:
            return False
        
        cache_time = datetime.fromisoformat(timestamp)
        return datetime.now() - cache_time < timedelta(seconds=ttl)
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any]):
        """缓存结果"""
        max_entries = self.config.get('performance', {}).get('cache', {}).get('max_entries', 1000)
        
        if len(self.cache) >= max_entries:
            # 简单的LRU：删除最旧的条目
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]['timestamp'])
            del self.cache[oldest_key]
        
        self.cache[cache_key] = {
            'result': result,
            'timestamp': datetime.now().isoformat()
        }
    
    def _log_analysis_metrics(self, query: str, result: Dict[str, Any]):
        """记录分析指标"""
        if self.config.get('performance', {}).get('monitoring', {}).get('enabled', True):
            logger.info(f"意图分析完成 - 查询: {query[:50]}, "
                       f"意图: {result.get('intent_type')}, "
                       f"置信度: {result.get('confidence'):.3f}, "
                       f"方法: {result.get('analysis_method')}")
    
    # 参数提取方法
    def _extract_chat_topic(self, query: str) -> str:
        """提取聊天主题"""
        return query[:50]
    
    def _extract_search_keywords(self, query: str) -> str:
        """提取搜索关键词"""
        stop_words = ['的', '了', '是', '在', '有', '和', '就', '不', '人', '都', '一', '一个']
        words = query.split()
        keywords = [word for word in words if word not in stop_words]
        return ' '.join(keywords)
    
    def _is_file_creation(self, query: str) -> bool:
        """判断是否是文件创建"""
        file_keywords = ['文件', '文档']
        file_extensions = ['.txt', '.doc', '.docx', '.pdf', '.xls', '.xlsx']
        query_lower = query.lower()
        
        return (any(keyword in query_lower for keyword in file_keywords) or 
                any(ext in query_lower for ext in file_extensions))
    
    def _is_folder_creation(self, query: str) -> bool:
        """判断是否是文件夹创建"""
        folder_keywords = ['文件夹', '目录', '分类', '归档']
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in folder_keywords)
    
    def _extract_file_name(self, query: str) -> Optional[str]:
        """提取文件名"""
        # 查找引号中的内容
        quoted = re.search(r'["\'"](.*?)["\'""]', query)
        if quoted:
            return quoted.group(1)
        
        # 查找文件扩展名前的内容
        ext_match = re.search(r'(\w+\.\w+)', query)
        if ext_match:
            return ext_match.group(1)
        
        return None
    
    def _extract_folder_name(self, query: str) -> Optional[str]:
        """提取文件夹名"""
        quoted = re.search(r'["\'"](.*?)["\'""]', query)
        if quoted:
            return quoted.group(1)
        return None
    
    def _extract_parent_folder(self, query: str) -> Optional[str]:
        """提取父目录"""
        pattern = re.search(r'在(.+?)[中里]|到(.+?)[中里]', query)
        if pattern:
            return pattern.group(1) or pattern.group(2)
        return None

# 创建全局实例
intent_service = IntentRecognitionService() 