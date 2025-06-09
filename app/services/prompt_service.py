import yaml
import os
import logging
from typing import Dict, Any, Optional, List
from string import Template
import json
from config import Config

logger = logging.getLogger(__name__)

class PromptService:
    """智能检索提示词管理服务"""
    
    def __init__(self):
        self.prompts = {}
        self.load_prompts()
    
    def load_prompts(self):
        """加载提示词配置"""
        try:
            prompt_file = os.path.join(
                os.path.dirname(__file__), '..', '..', 
                'prompts', 'intelligent_search_prompts.yaml'
            )
            
            if os.path.exists(prompt_file):
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    self.prompts = yaml.safe_load(f)
                logger.info("智能检索提示词配置加载成功")
            else:
                logger.warning("提示词配置文件不存在，使用默认配置")
                self.prompts = self._get_default_prompts()
                
        except Exception as e:
            logger.error(f"加载提示词配置失败: {e}")
            self.prompts = self._get_default_prompts()
    
    def get_query_optimization_prompt(self, query: str, 
                                    scenario: str = None, 
                                    template: str = 'comprehensive') -> Dict[str, Any]:
        """获取查询优化提示词"""
        try:
            # 优先使用场景特定提示词
            if scenario and scenario in self.prompts.get('scenario_prompts', {}):
                scenario_config = self.prompts['scenario_prompts'][scenario]
                if 'query_optimization' in scenario_config:
                    template_content = scenario_config['query_optimization']
                    system_prompt = f"你是{scenario}文档检索专家。"
                else:
                    template_content = self.prompts['query_optimization']['templates'][template]
                    system_prompt = self.prompts['query_optimization']['system_prompt']
            else:
                template_content = self.prompts['query_optimization']['templates'][template]
                system_prompt = self.prompts['query_optimization']['system_prompt']
            
            # 格式化提示词
            formatted_prompt = template_content.replace('{query}', query)
            
            return {
                'system_prompt': system_prompt,
                'user_prompt': formatted_prompt,
                'parameters': self.prompts['query_optimization']['parameters']
            }
            
        except Exception as e:
            logger.error(f"获取查询优化提示词失败: {e}")
            return self._get_fallback_query_prompt(query)
    
    def get_result_assembly_prompt(self, query: str, context: str,
                                 scenario: str = None,
                                 template: str = 'structured_answer') -> Dict[str, Any]:
        """获取结果组装提示词"""
        try:
            # 优先使用场景特定提示词
            if scenario and scenario in self.prompts.get('scenario_prompts', {}):
                scenario_config = self.prompts['scenario_prompts'][scenario]
                if 'result_assembly' in scenario_config:
                    template_content = scenario_config['result_assembly']
                    system_prompt = f"你是{scenario}信息整合专家。"
                else:
                    template_content = self.prompts['result_assembly']['templates'][template]
                    system_prompt = self.prompts['result_assembly']['system_prompt']
            else:
                template_content = self.prompts['result_assembly']['templates'][template]
                system_prompt = self.prompts['result_assembly']['system_prompt']
            
            # 格式化提示词
            formatted_prompt = template_content.replace('{query}', query).replace('{context}', context)
            
            return {
                'system_prompt': system_prompt,
                'user_prompt': formatted_prompt,
                'parameters': self.prompts['result_assembly']['parameters']
            }
            
        except Exception as e:
            logger.error(f"获取结果组装提示词失败: {e}")
            return self._get_fallback_assembly_prompt(query, context)
    
    def analyze_query_intent(self, query: str) -> Dict[str, Any]:
        """分析查询意图，推荐最佳提示词配置"""
        try:
            # 简单的意图分析逻辑
            query_lower = query.lower()
            
            # 检测场景类型
            scenario = None
            if any(word in query_lower for word in ['合同', '法律', '法规', '条款', '协议', '合规']):
                scenario = 'legal_document'
            elif any(word in query_lower for word in ['财务', '会计', '审计', '税务', '报表', '成本', '预算']):
                scenario = 'financial_document'
            elif any(word in query_lower for word in ['人事', '薪酬', '绩效', '培训', '招聘', '员工', '考核']):
                scenario = 'hr_document'
            
            # 检测查询类型
            query_type = 'comprehensive'  # 默认
            if any(word in query_lower for word in ['流程', '步骤', '如何', '怎样', '程序', '操作']):
                query_type = 'business_focused'
            elif any(word in query_lower for word in ['技术', '配置', '参数', '代码', '系统', '开发']):
                query_type = 'technical_focused'
            elif len(query.split()) <= 3:  # 短查询使用简单模板
                query_type = 'simple'
            
            # 检测答案风格偏好
            answer_style = 'structured_answer'  # 默认
            if any(word in query_lower for word in ['简单', '简洁', '概要', '快速']):
                answer_style = 'concise_answer'
            elif any(word in query_lower for word in ['详细', '分析', '深入', '全面']):
                answer_style = 'analytical_answer'
            
            return {
                'scenario': scenario,
                'query_template': query_type,
                'answer_template': answer_style,
                'confidence': self._calculate_confidence(query, scenario, query_type)
            }
            
        except Exception as e:
            logger.error(f"查询意图分析失败: {e}")
            return {
                'scenario': None,
                'query_template': 'comprehensive',
                'answer_template': 'structured_answer',
                'confidence': 0.5
            }
    
    def _calculate_confidence(self, query: str, scenario: str, query_type: str) -> float:
        """计算推荐配置的置信度"""
        confidence = 0.5  # 基础置信度
        
        if scenario:
            confidence += 0.3  # 场景识别成功
        
        if len(query.split()) > 3:
            confidence += 0.2  # 查询足够详细
        
        return min(confidence, 1.0)
    
    def get_available_templates(self) -> Dict[str, List[str]]:
        """获取可用的模板列表"""
        try:
            return {
                'query_optimization': list(self.prompts['query_optimization']['templates'].keys()),
                'result_assembly': list(self.prompts['result_assembly']['templates'].keys()),
                'scenarios': list(self.prompts.get('scenario_prompts', {}).keys())
            }
        except Exception as e:
            logger.error(f"获取模板列表失败: {e}")
            return {
                'query_optimization': ['comprehensive', 'simple'],
                'result_assembly': ['structured_answer', 'default'],
                'scenarios': []
            }
    
    def _get_default_prompts(self) -> Dict:
        """获取默认提示词配置"""
        return {
            'query_optimization': {
                'system_prompt': '你是专业的文档检索查询优化助手。',
                'templates': {
                    'comprehensive': '请优化查询并提取关键信息：{query}\n关键词：',
                    'simple': '提取查询关键词：{query}\n关键词：'
                },
                'parameters': {'max_tokens': 200, 'temperature': 0.3}
            },
            'result_assembly': {
                'system_prompt': '你是专业的信息整合助手。',
                'templates': {
                    'structured_answer': '基于文档回答问题：\n问题：{query}\n文档：{context}\n答案：',
                    'default': '问题：{query}\n文档：{context}\n回答：'
                },
                'parameters': {'max_tokens': 800, 'temperature': 0.7}
            }
        }
    
    def _get_fallback_query_prompt(self, query: str) -> Dict[str, Any]:
        """获取备用查询优化提示词"""
        return {
            'system_prompt': '你是查询优化助手',
            'user_prompt': f'优化查询：{query}',
            'parameters': {'max_tokens': 100, 'temperature': 0.3}
        }
    
    def _get_fallback_assembly_prompt(self, query: str, context: str) -> Dict[str, Any]:
        """获取备用结果组装提示词"""
        return {
            'system_prompt': '你是问答助手',
            'user_prompt': f'问题：{query}\n文档：{context}\n回答：',
                            'parameters': {'max_tokens': Config.LLM_MAX_TOKENS, 'temperature': Config.LLM_TEMPERATURE}
        }

# 全局实例
prompt_service = PromptService() 