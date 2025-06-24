"""
意图识别服务 - 独立配置版本
版本: v3.0
架构: 使用独立配置管理器 + LLM主要分析 + 关键词降级分析
特点: 完全独立于全局LLM配置
"""

import re
import json
import logging
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from .intent_config_manager import intent_config

logger = logging.getLogger(__name__)

class IntentRecognitionService:
    """
    意图识别服务 - 独立配置版本
    
    功能特性:
    1. 使用独立的配置管理器，与全局LLM配置完全隔离
    2. 支持DeepSeek和豆包两个LLM提供商
    3. LLM主要分析 + 关键词降级分析双层架构
    4. 智能降级处理机制
    5. 结果缓存优化
    6. 完整的错误处理
    """
    
    def __init__(self):
        self.config_manager = intent_config
        self.cache = {}  # 简单内存缓存

    
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
        if self.config_manager.is_cache_enabled() and cache_key in self.cache:
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
        if self.config_manager.is_cache_enabled():
            self._cache_result(cache_key, final_result)
        
        # 记录分析指标
        self._log_analysis_metrics(query, final_result)
        
        return final_result
    
    def _analyze_with_llm(self, query: str, scenario: str = None) -> Dict[str, Any]:
        """使用LLM进行意图分析"""
        try:
            # 创建意图识别专用LLM客户端
            client = self.config_manager.create_llm_client()
            
            # 获取提示词
            system_prompt = self.config_manager.get_system_prompt()
            user_prompt_template = self.config_manager.get_user_prompt_template()
            user_prompt = user_prompt_template.format(query=query)
            
            # 获取模型参数
            model_params = self.config_manager.get_model_params()
            
            # 调用LLM
            response = client.analyze_intent(system_prompt, user_prompt, model_params)
            
            # 解析响应
            parsed_result = self._parse_llm_response(response)
            
            # 添加元数据
            parsed_result.update({
                'analysis_method': 'llm',
                'model_used': f"{self.config_manager.config['service']['current_provider']}:{self.config_manager.get_current_model()}",
                'scenario': scenario,
                'timestamp': datetime.now().isoformat()
            })
            
            return parsed_result
            
        except Exception as e:
            logger.error(f"LLM意图分析失败: {e}")
            return self._create_error_result(f"LLM分析失败: {str(e)}", "llm_analysis_error")
    
    def _analyze_with_fallback(self, query: str, scenario: str = None, llm_result: Dict = None) -> Dict[str, Any]:
        """使用降级方法进行意图分析"""
        fallback_config = self.config_manager.get_fallback_config()
        
        if not fallback_config.get('enabled', True):
            return llm_result or self._create_error_result("降级处理已禁用")
        
        # 选择降级策略
        strategy = fallback_config.get('strategy', 'keyword_analysis')
        
        if strategy == 'keyword_analysis':
            return self._analyze_with_keywords(query, scenario)
        elif strategy == 'fixed_response':
            return self._create_fixed_fallback_result(query, scenario)
        else:
            return self._create_fixed_fallback_result(query, scenario)
    
    def _analyze_with_keywords(self, query: str, scenario: str = None) -> Dict[str, Any]:
        """基于关键词的意图分析"""
        try:
            keyword_config = self.config_manager.get_keyword_analysis_config()
            
            if not keyword_config.get('enabled', True):
                return self._create_fixed_fallback_result(query, scenario)
            
            query_lower = query.lower()
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
            
                            # 按优先级顺序选择意图（document_generation > mcp_action > knowledge_search > normal_chat）
            if intent_scores:
                # 定义优先级顺序
                priority_order = ['document_generation', 'mcp_action', 'knowledge_search', 'normal_chat']
                
                # 按优先级和置信度选择最佳意图
                best_intent = None
                best_confidence = 0
                
                for intent_type in priority_order:
                    if intent_type in intent_scores:
                        confidence = intent_scores[intent_type]
                        # 对于高优先级意图，较低的置信度阈值也接受
                        min_threshold = (0.25 if intent_type == 'document_generation' else 
                                       0.3 if intent_type == 'mcp_action' else 
                                       0.4 if intent_type == 'knowledge_search' else 0.2)
                        
                        if confidence > min_threshold and confidence > best_confidence:
                            best_intent = (intent_type, confidence)
                            best_confidence = confidence
                            break  # 找到符合条件的高优先级意图就停止
                
                # 如果没有找到合适的意图，使用最高分意图
                if not best_intent:
                    best_intent = max(intent_scores.items(), key=lambda x: x[1])
                
                intent_type, confidence = best_intent
                
                # 简化返回格式，移除详细参数提取
                return {
                    'intent_type': intent_type,
                    'confidence': confidence,
                    'reasoning': f'基于关键词分析，匹配{intent_type}意图',
                    'used_llm': False,
                    'analysis_method': 'keyword',
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
            keyword_config = self.config_manager.get_keyword_analysis_config()
            context_rules = keyword_config.get('context_rules', {})
            
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
            keyword_config = self.config_manager.get_keyword_analysis_config()
            file_detection = keyword_config.get('file_detection', {})
            extensions = file_detection.get('extensions', [])
            confidence_boost = file_detection.get('confidence_boost', 0.2)
            
            query_lower = query.lower()
            
            # 检查文件扩展名
            for ext in extensions:
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
            
        elif intent_type == 'document_generation':
            action_type = 'generate_document'
            parameters['source_path'] = self._extract_source_path(query)
            parameters['output_format'] = self._extract_output_format(query)
            parameters['document_type'] = self._extract_document_type(query)
            
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
    
    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """解析LLM响应"""
        try:
            # 清理响应文本
            cleaned_text = response_text.strip()
            if cleaned_text.startswith('```json'):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith('```'):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
            # 解析JSON
            result = json.loads(cleaned_text)
            
            # 验证必需字段
            required_fields = ['intent_type', 'confidence', 'reasoning']
            if not all(field in result for field in required_fields):
                raise ValueError(f"响应缺少必需字段，需要: {required_fields}")
            
            # 验证意图类型
            valid_intents = ['normal_chat', 'knowledge_search', 'mcp_action', 'document_generation']
            if result['intent_type'] not in valid_intents:
                raise ValueError(f"无效的意图类型: {result['intent_type']}")
            
            # 验证置信度
            confidence = float(result['confidence'])
            if not (0.0 <= confidence <= 1.0):
                raise ValueError(f"置信度必须在0.0-1.0之间: {confidence}")
            
            # 标准化返回格式
            return {
                'intent_type': result['intent_type'],
                'confidence': confidence,
                'reasoning': result['reasoning'],
                'used_llm': True,
                'model_used': getattr(self, '_current_model', 'unknown'),
                'prompt_source': 'config_file'
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}, 原始响应: {response_text}")
            raise
        except Exception as e:
            logger.error(f"LLM响应解析失败: {e}")
            raise
    
    def _should_fallback(self, llm_result: Dict[str, Any]) -> bool:
        """判断是否需要降级处理"""
        fallback_config = self.config_manager.get_fallback_config()
        triggers = fallback_config.get('triggers', [])
        
        # 检查是否有错误
        if 'error_type' in llm_result:
            error_type = llm_result['error_type']
            return error_type in triggers
        
        # LLM分析成功，不需要降级
        return False
    
    def _create_error_result(self, error_message: str, error_type: str = "unknown_error") -> Dict[str, Any]:
        """创建错误结果"""
        fallback_config = self.config_manager.get_fallback_config()
        
        return {
            'intent_type': fallback_config.get('default_intent', 'normal_chat'),
            'confidence': fallback_config.get('default_confidence', 0.5),
            'reasoning': f'错误处理: {error_message}',
            'used_llm': False,
            'analysis_method': 'error_fallback',
            'error_type': error_type,
            'error_message': error_message,
            'timestamp': datetime.now().isoformat()
        }
    
    def _create_fixed_fallback_result(self, query: str, scenario: str = None) -> Dict[str, Any]:
        """创建固定的降级结果"""
        fallback_config = self.config_manager.get_fallback_config()
        
        return {
            'intent_type': fallback_config.get('default_intent', 'normal_chat'),
            'confidence': fallback_config.get('default_confidence', 0.5),
            'reasoning': '降级到固定响应',
            'used_llm': False,
            'analysis_method': 'fixed_fallback',
            'scenario': scenario,
            'timestamp': datetime.now().isoformat()
        }
    
    # 缓存相关方法
    
    def _generate_cache_key(self, query: str, scenario: str = None) -> str:
        """生成缓存键"""
        key_data = f"{query}_{scenario or 'default'}"
        return hashlib.md5(key_data.encode('utf-8')).hexdigest()
    
    def _is_cache_valid(self, cached_item: Dict) -> bool:
        """检查缓存是否有效"""
        cache_config = self.config_manager.get_cache_config()
        ttl = cache_config.get('ttl', 3600)
        timestamp = cached_item.get('timestamp')
        
        if not timestamp:
            return False
        
        cache_time = datetime.fromisoformat(timestamp)
        return datetime.now() - cache_time < timedelta(seconds=ttl)
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any]):
        """缓存结果"""
        cache_config = self.config_manager.get_cache_config()
        max_entries = cache_config.get('max_entries', 1000)
        
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
    
    def _extract_source_path(self, query: str) -> Optional[str]:
        """提取源文件或文件夹路径 - LLM增强版"""
        # 首先尝试LLM提取
        llm_result = self._extract_source_path_with_llm(query)
        if llm_result:
            logger.info(f"LLM成功提取源路径: {llm_result}")
            return llm_result
        
        # LLM失败时降级到正则表达式
        logger.info("LLM提取失败，降级到正则表达式")
        return self._extract_source_path_with_regex(query)
    
    def _extract_source_path_with_llm(self, query: str) -> Optional[str]:
        """使用LLM提取源路径"""
        try:
            # 检查配置是否启用LLM参数提取
            param_config = self.config_manager.config.get('parameter_extraction', {})
            if not param_config.get('enabled', False):
                return None
            
            # 获取LLM提示词配置
            prompts = param_config.get('prompts', {})
            source_extraction = prompts.get('source_path_extraction', {})
            
            if not source_extraction:
                logger.warning("未找到源路径提取提示词配置")
                return None
            
            # 构建提示词
            system_prompt = source_extraction.get('system', '')
            user_template = source_extraction.get('user_template', '')
            
            if not system_prompt or not user_template:
                logger.warning("源路径提取提示词配置不完整")
                return None
            
            user_prompt = user_template.format(query=query)
            combined_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            # 获取LLM配置
            llm_config = param_config.get('llm_config', {})
            provider = llm_config.get('provider', 'deepseek')
            model = llm_config.get('model', 'deepseek-chat')
            llm_model = f"{provider}:{model}"
            
            # 调用LLM
            from app.services.llm import LLMService
            
            response = LLMService.generate_answer(
                query=combined_prompt,
                context="",
                llm_model=llm_model,
                scenario="parameter_extraction"
            )
            
            if response and response.strip():
                # 清理响应
                extracted_path = response.strip()
                
                # 检查是否是错误响应
                error_indicators = [
                    '抱歉', '无法', '暂时', '稍后', '失败', 
                    'sorry', 'cannot', 'unable', 'failed'
                ]
                
                if any(indicator in extracted_path.lower() for indicator in error_indicators):
                    logger.warning(f"LLM返回错误响应: {extracted_path}")
                    return None
                
                # 如果返回"无"，表示没有找到
                if extracted_path.lower() in ['无', 'none', 'null', '']:
                    return None
                
                # 基本清理
                extracted_path = re.sub(r'^["\'"](.*)["\'""]$', r'\1', extracted_path)
                extracted_path = extracted_path.strip()
                
                if extracted_path and len(extracted_path) > 0:
                    logger.info(f"LLM提取源路径成功: '{extracted_path}'")
                    return extracted_path
            
            return None
            
        except Exception as e:
            logger.error(f"LLM提取源路径失败: {e}")
            return None
    
    def _extract_source_path_with_regex(self, query: str) -> Optional[str]:
        """使用正则表达式提取源路径（降级方案）"""
        patterns = [
            # 分析类查询
            r'分析(?:下|一下)?(.+?)(?:表格|文件|这个)',
            r'分析(?:下|一下)?(.+?)(?:，|,|。|根据)',
            
            # 基于/根据类查询（扩展动词）
            r'基于(.+?)(?:生成|制作|写|做|总结|汇总|整理)',
            r'根据(.+?)(?:生成|制作|写|做|总结|汇总|整理)',
            r'利用(.+?)(?:生成|制作|写|做|总结|汇总|整理)',
            r'使用(.+?)(?:生成|制作|写|做|总结|汇总|整理)',
            r'参考(.+?)(?:生成|制作|写|做|总结|汇总|整理)',
            r'从(.+?)(?:中|里)(?:生成|制作|写|做|总结|汇总|整理)',
            
            # 文件名模式
            r'(.+?\.(?:xlsx?|docx?|pdf|txt|pptx?))(?:\s|，|,|这个|文件|表格)',
            
            # 文件夹模式（增强版，包含更多动词）
            r'(.+?)(?:文件夹|文件|目录)(?:的|中|里|下)?.*?(?:生成|制作|写|做|分析|总结|汇总|整理)',
            
            # 数字开头的文件夹名（针对"02王赛"这种格式）
            r'((?:\d+|[0-9]+)[^\s，,。]*?)(?:文件夹|目录)(?:的|中|里|下)?.*?(?:生成|制作|写|做|分析|总结|汇总|整理)',
            
            # 通用文件引用
            r'(.+?)(?:这个|该|此)(?:文件|表格|文档)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                source = match.group(1).strip()
                
                # 清理提取的路径
                source = re.sub(r'^(?:这个|那个|该|此)', '', source)
                source = re.sub(r'(?:表格|文件|文档)$', '', source)
                source = source.strip()
                
                if source and len(source) > 1:  # 至少要有2个字符
                    return source
        return None
    
    def _extract_output_format(self, query: str) -> str:
        """提取输出格式 - LLM增强版，默认为txt"""
        # 首先检查是否有明确的格式指定
        regex_result = self._extract_output_format_with_regex(query)
        
        # 如果正则检测到明确格式（非默认txt），直接使用
        if regex_result != 'txt':
            logger.info(f"正则表达式检测到明确格式: {regex_result}")
            return regex_result
        
        # 否则尝试LLM提取
        llm_result = self._extract_output_format_with_llm(query)
        if llm_result and llm_result in ['excel', 'pdf', 'doc', 'ppt']:  # 只接受非默认格式
            logger.info(f"LLM成功提取输出格式: {llm_result}")
            return llm_result
        
        # 默认返回txt
        logger.info(f"使用默认输出格式: txt")
        return 'txt'
    
    def _extract_output_format_with_llm(self, query: str) -> Optional[str]:
        """使用LLM提取输出格式"""
        try:
            # 检查配置是否启用LLM参数提取
            param_config = self.config_manager.config.get('parameter_extraction', {})
            if not param_config.get('enabled', False):
                return None
            
            # 获取LLM提示词配置
            prompts = param_config.get('prompts', {})
            format_extraction = prompts.get('output_format_extraction', {})
            
            if not format_extraction:
                return None
            
            # 构建提示词
            system_prompt = format_extraction.get('system', '')
            user_template = format_extraction.get('user_template', '')
            
            if not system_prompt or not user_template:
                return None
            
            user_prompt = user_template.format(query=query)
            combined_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            # 获取LLM配置
            llm_config = param_config.get('llm_config', {})
            provider = llm_config.get('provider', 'deepseek')
            model = llm_config.get('model', 'deepseek-chat')
            llm_model = f"{provider}:{model}"
            
            # 调用LLM
            from app.services.llm import LLMService
            
            response = LLMService.generate_answer(
                query=combined_prompt,
                context="",
                llm_model=llm_model,
                scenario="parameter_extraction"
            )
            
            if response and response.strip():
                extracted_format = response.strip().lower()
                
                # 验证格式是否有效
                valid_formats = ['txt', 'doc', 'pdf', 'excel', 'ppt']
                if extracted_format in valid_formats:
                    return extracted_format
            
            return None
            
        except Exception as e:
            logger.error(f"LLM提取输出格式失败: {e}")
            return None
    
    def _extract_output_format_with_regex(self, query: str) -> str:
        """使用正则表达式提取输出格式（降级方案）"""
        # 明确的输出格式关键词（优先级高）
        explicit_formats = {
            'txt': ['生成txt', '输出txt', '保存为txt', '文本格式'],
            'doc': ['生成doc', '输出doc', 'word格式', '保存为word'],
            'pdf': ['生成pdf', '输出pdf', 'pdf格式', '保存为pdf'],
            'excel': ['生成excel', '输出excel', '保存为excel', '表格格式', '预测表格', '数据表格', 'excel表格'],
            'ppt': ['生成ppt', '输出ppt', 'ppt格式', '演示文稿格式']
        }
        
        query_lower = query.lower()
        
        # 首先检查明确的输出格式指令
        for format_type, keywords in explicit_formats.items():
            for keyword in keywords:
                if keyword in query_lower:
                    return format_type
        
        # 检查表格相关关键词（用户要求生成表格时应该输出Excel）
        table_keywords = ['表格', '工作表', '数据表', '统计表', '分析表', '预测表']
        generation_keywords = ['生成', '制作', '创建', '输出', '导出']
        
        # 如果同时包含表格关键词和生成关键词，输出Excel格式
        has_table = any(keyword in query_lower for keyword in table_keywords)
        has_generation = any(keyword in query_lower for keyword in generation_keywords)
        
        if has_table and has_generation:
            logger.info(f"检测到表格生成请求，使用Excel格式: {query}")
            return 'excel'
        
        # 如果没有明确指定，且提到文档分析，默认返回txt
        analysis_keywords = ['分析', '分析下', '分析一下', '查看', '看看']
        if any(keyword in query_lower for keyword in analysis_keywords):
            return 'txt'
        
        # 检查文件扩展名引用（可能是输入文件而非输出格式）
        input_formats = {
            'doc': ['word', 'docx'],
            'excel': ['excel', 'xls', 'xlsx'],
            'pdf': ['pdf'],
            'ppt': ['ppt', 'pptx']
        }
        
        # 默认返回txt格式
        return 'txt'
    
    def _extract_document_type(self, query: str) -> str:
        """提取文档类型 - LLM增强版"""
        # 首先尝试LLM提取
        llm_result = self._extract_document_type_with_llm(query)
        if llm_result:
            logger.info(f"LLM成功提取文档类型: {llm_result}")
            return llm_result
        
        # LLM失败时降级到正则表达式
        regex_result = self._extract_document_type_with_regex(query)
        logger.info(f"使用正则表达式提取文档类型: {regex_result}")
        return regex_result
    
    def _extract_document_type_with_llm(self, query: str) -> Optional[str]:
        """使用LLM提取文档类型"""
        try:
            # 检查配置是否启用LLM参数提取
            param_config = self.config_manager.config.get('parameter_extraction', {})
            if not param_config.get('enabled', False):
                return None
            
            # 获取LLM提示词配置
            prompts = param_config.get('prompts', {})
            type_extraction = prompts.get('document_type_extraction', {})
            
            if not type_extraction:
                return None
            
            # 构建提示词
            system_prompt = type_extraction.get('system', '')
            user_template = type_extraction.get('user_template', '')
            
            if not system_prompt or not user_template:
                return None
            
            user_prompt = user_template.format(query=query)
            combined_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            # 获取LLM配置
            llm_config = param_config.get('llm_config', {})
            provider = llm_config.get('provider', 'deepseek')
            model = llm_config.get('model', 'deepseek-chat')
            llm_model = f"{provider}:{model}"
            
            # 调用LLM
            from app.services.llm import LLMService
            
            response = LLMService.generate_answer(
                query=combined_prompt,
                context="",
                llm_model=llm_model,
                scenario="parameter_extraction"
            )
            
            if response and response.strip():
                extracted_type = response.strip().lower()
                
                # 验证类型是否有效
                valid_types = ['summary', 'report', 'analysis', 'documentation', 'other']
                if extracted_type in valid_types:
                    return extracted_type
            
            return None
            
        except Exception as e:
            logger.error(f"LLM提取文档类型失败: {e}")
            return None
    
    def _extract_document_type_with_regex(self, query: str) -> str:
        """使用正则表达式提取文档类型（降级方案）"""
        document_types = {
            'report': ['报告', '分析报告', '总结报告', '汇报'],
            'summary': ['总结', '汇总', '梳理', '归纳'],
            'analysis': ['分析', '评估', '审查', '检查'],
            'documentation': ['文档', '说明', '手册', '指南'],
            'other': ['其他', '文件', '内容']
        }
        
        query_lower = query.lower()
        for doc_type, keywords in document_types.items():
            for keyword in keywords:
                if keyword in query_lower:
                    return doc_type
        
        # 默认返回通用类型
        return 'summary'

# 创建全局实例
intent_service = IntentRecognitionService() 