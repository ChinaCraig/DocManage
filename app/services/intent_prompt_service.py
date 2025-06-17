import os
import yaml
import logging
from typing import Dict, Any, Optional, List
from config import Config

logger = logging.getLogger(__name__)

class IntentPromptService:
    """意图识别提示词服务"""
    
    def __init__(self):
        self.config = None
        self.config_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'prompts', 'intent_analysis_prompts.yaml')
        self.load_config()
    
    def load_config(self):
        """加载意图识别提示词配置"""
        try:
            if os.path.exists(self.config_file_path):
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f)
                logger.info(f"意图识别提示词配置加载成功: {self.config_file_path}")
            else:
                logger.warning(f"意图识别提示词配置文件不存在: {self.config_file_path}")
                self.config = self._get_default_config()
        except Exception as e:
            logger.error(f"加载意图识别提示词配置失败: {e}")
            self.config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置（降级方案）"""
        return {
            'intent_analysis': {
                'system_prompt': Config.INTENT_ANALYSIS_SYSTEM_PROMPT,
                'user_prompt_template': Config.INTENT_ANALYSIS_USER_PROMPT_TEMPLATE,
                'parameters': {
                    'max_tokens': Config.INTENT_ANALYSIS_MAX_TOKENS,
                    'temperature': Config.INTENT_ANALYSIS_TEMPERATURE,
                    'confidence_threshold': Config.INTENT_ANALYSIS_CONFIDENCE_THRESHOLD
                }
            }
        }
    
    def get_system_prompt(self, scenario: Optional[str] = None) -> str:
        """获取系统提示词"""
        try:
            if scenario and scenario in self.config.get('scenario_prompts', {}):
                return self.config['scenario_prompts'][scenario]['system_prompt']
            else:
                return self.config['intent_analysis']['system_prompt']
        except Exception as e:
            logger.error(f"获取系统提示词失败: {e}")
            return Config.INTENT_ANALYSIS_SYSTEM_PROMPT
    
    def get_user_prompt_template(self) -> str:
        """获取用户提示词模板"""
        try:
            return self.config['intent_analysis']['user_prompt_template']
        except Exception as e:
            logger.error(f"获取用户提示词模板失败: {e}")
            return Config.INTENT_ANALYSIS_USER_PROMPT_TEMPLATE
    
    def get_model_parameters(self) -> Dict[str, Any]:
        """获取模型参数"""
        try:
            return self.config['intent_analysis']['parameters']
        except Exception as e:
            logger.error(f"获取模型参数失败: {e}")
            return {
                'max_tokens': Config.INTENT_ANALYSIS_MAX_TOKENS,
                'temperature': Config.INTENT_ANALYSIS_TEMPERATURE,
                'confidence_threshold': Config.INTENT_ANALYSIS_CONFIDENCE_THRESHOLD
            }
    
    def get_enhanced_keywords(self, scenario: Optional[str] = None) -> Dict[str, List[str]]:
        """获取增强关键词"""
        try:
            if scenario and scenario in self.config.get('scenario_prompts', {}):
                scenario_config = self.config['scenario_prompts'][scenario]
                if 'enhanced_keywords' in scenario_config:
                    return scenario_config['enhanced_keywords']
            
            # 返回通用关键词增强配置
            return self.config.get('keyword_enhancement', {}).get('action_verbs', {})
        except Exception as e:
            logger.error(f"获取增强关键词失败: {e}")
            return {}
    
    def get_confidence_boost(self, query: str, intent_type: str) -> float:
        """根据查询内容和意图类型计算置信度提升"""
        try:
            boost = 0.0
            confidence_rules = self.config.get('confidence_rules', {})
            
            # 检查高置信度规则
            for rule in confidence_rules.get('high_confidence', []):
                if self._match_condition(query, rule['condition']) and rule['intent_type'] == intent_type:
                    boost += rule['boost']
            
            # 检查中等置信度规则
            for rule in confidence_rules.get('medium_confidence', []):
                if self._match_condition(query, rule['condition']) and rule['intent_type'] == intent_type:
                    boost += rule['boost']
            
            # 检查低置信度规则
            for rule in confidence_rules.get('low_confidence', []):
                if self._match_condition(query, rule['condition']):
                    boost += rule['boost']
            
            return boost
        except Exception as e:
            logger.error(f"计算置信度提升失败: {e}")
            return 0.0
    
    def _match_condition(self, query: str, condition: str) -> bool:
        """匹配条件规则"""
        query_lower = query.lower()
        
        if "包含明确的文件扩展名" in condition:
            extensions = ['.txt', '.doc', '.docx', '.pdf', '.xls', '.xlsx', '.jpg', '.png', '.mp4']
            return any(ext in query_lower for ext in extensions)
        
        elif "包含'创建'和'文件夹'关键词" in condition:
            create_words = ['创建', '新建', '建立']
            folder_words = ['文件夹', '目录']
            return (any(word in query_lower for word in create_words) and 
                   any(word in query_lower for word in folder_words))
        
        elif "包含'分析'和'文件夹'关键词" in condition:
            analyze_words = ['分析', '检查', '确认']
            folder_words = ['文件夹', '目录']
            return (any(word in query_lower for word in analyze_words) and 
                   any(word in query_lower for word in folder_words))
        
        elif "包含搜索关键词但无明确对象" in condition:
            search_words = ['搜索', '查找', '寻找', '检索']
            return any(word in query_lower for word in search_words)
        
        elif "查询过于模糊或包含多种意图" in condition:
            return len(query.strip()) < 5 or '或者' in query_lower or '还是' in query_lower
        
        return False
    
    def get_error_handling_config(self, error_type: str) -> Dict[str, Any]:
        """获取错误处理配置"""
        try:
            error_config = self.config.get('error_handling', {})
            return error_config.get(error_type, {
                'fallback_intent': 'vector_search',
                'confidence': 0.5,
                'reasoning': f'处理{error_type}错误，使用默认降级策略'
            })
        except Exception as e:
            logger.error(f"获取错误处理配置失败: {e}")
            return {
                'fallback_intent': 'vector_search',
                'confidence': 0.5,
                'reasoning': '配置获取失败，使用默认降级策略'
            }
    
    def get_extended_intent_info(self, intent_type: str) -> Optional[Dict[str, Any]]:
        """获取扩展意图类型信息"""
        try:
            extended_intents = self.config.get('extended_intents', {})
            return extended_intents.get(intent_type)
        except Exception as e:
            logger.error(f"获取扩展意图信息失败: {e}")
            return None
    
    def analyze_query_complexity(self, query: str) -> Dict[str, Any]:
        """分析查询复杂度和特征"""
        try:
            query_lower = query.lower()
            
            # 获取关键词增强配置
            keyword_config = self.config.get('keyword_enhancement', {})
            action_verbs = keyword_config.get('action_verbs', {})
            object_nouns = keyword_config.get('object_nouns', {})
            modifiers = keyword_config.get('modifiers', {})
            
            # 分析查询特征
            features = {
                'length': len(query),
                'has_action_verb': False,
                'has_object_noun': False,
                'has_modifier': False,
                'complexity_score': 0,
                'suggested_intent': None
            }
            
            # 检查动作动词
            for action, verbs in action_verbs.items():
                if any(verb in query_lower for verb in verbs):
                    features['has_action_verb'] = True
                    features['complexity_score'] += 1
                    if not features['suggested_intent']:
                        features['suggested_intent'] = action
            
            # 检查对象名词
            for obj, nouns in object_nouns.items():
                if any(noun in query_lower for noun in nouns):
                    features['has_object_noun'] = True
                    features['complexity_score'] += 1
            
            # 检查修饰词
            for modifier_type, words in modifiers.items():
                if any(word in query_lower for word in words):
                    features['has_modifier'] = True
                    features['complexity_score'] += 0.5
            
            return features
        except Exception as e:
            logger.error(f"分析查询复杂度失败: {e}")
            return {'complexity_score': 0, 'suggested_intent': None}
    
    def get_prompt_version(self, version: str = "v1") -> Dict[str, str]:
        """获取指定版本的提示词（用于A/B测试）"""
        try:
            ab_config = self.config.get('ab_testing', {})
            versions = ab_config.get('prompt_versions', {})
            
            if version in versions:
                # 这里可以扩展为返回不同版本的具体提示词
                logger.info(f"使用提示词版本: {version} - {versions[version]}")
            
            # 目前返回默认提示词，后续可扩展为版本化提示词
            return {
                'system_prompt': self.get_system_prompt(),
                'user_prompt_template': self.get_user_prompt_template()
            }
        except Exception as e:
            logger.error(f"获取提示词版本失败: {e}")
            return {
                'system_prompt': self.get_system_prompt(),
                'user_prompt_template': self.get_user_prompt_template()
            }
    
    def reload_config(self):
        """重新加载配置文件"""
        self.load_config()
        logger.info("意图识别提示词配置已重新加载")

# 创建全局实例
intent_prompt_service = IntentPromptService() 