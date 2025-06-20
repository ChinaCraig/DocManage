"""
MCP工具分析器
用于分析用户请求，确定需要调用哪些MCP工具
"""

import json
import logging
import yaml
import os
from typing import Dict, List, Any, Optional
from pathlib import Path

# 导入意图识别配置管理器中的LLM客户端
from app.services.intent_config_manager import IntentLLMClient

logger = logging.getLogger(__name__)

class MCPToolAnalyzer:
    """MCP工具分析器"""
    
    def __init__(self):
        self.config = self._load_config()
        self.llm_client = None  # 延迟初始化
        
    def _load_config(self) -> Dict[str, Any]:
        """加载MCP工具配置"""
        config_path = Path(__file__).parent.parent.parent / "prompts" / "mcp_tools_config.yaml"
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                logger.info("MCP工具配置加载成功")
                return config
        except Exception as e:
            logger.error(f"MCP工具配置加载失败: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "supported_tools": {
                "create_file": {"enabled": True},
                "create_folder": {"enabled": True}
            },
            "error_handling": {
                "tool_not_found": {
                    "message": "抱歉，您请求的操作暂不支持。",
                    "suggestion": "当前支持的操作包括：文件创建、文件夹创建。"
                },
                "tool_disabled": {
                    "message": "工具当前已被禁用。",
                    "suggestion": "请联系管理员启用此功能。"
                },
                "mcp_disabled": {
                    "message": "MCP功能当前已关闭，无法执行系统操作。",
                    "suggestion": "请在页面上打开MCP开关后重试。"
                }
            }
        }
    
    def analyze_tools_needed(self, query: str) -> Dict[str, Any]:
        """分析用户请求，确定需要的工具"""
        try:
            # 尝试使用LLM分析
            return self._analyze_with_llm(query)
        except Exception as e:
            logger.warning(f"LLM工具分析失败，使用关键词分析: {e}")
            # 降级到关键词分析
            return self._analyze_with_keywords(query)
    
    def _analyze_with_llm(self, query: str) -> Dict[str, Any]:
        """使用LLM分析工具需求"""
        # 初始化LLM客户端
        if self.llm_client is None:
            self._init_llm_client()
        
        prompts = self.config.get("prompts", {})
        system_prompt = prompts.get("system", "")
        user_template = prompts.get("user_template", "请分析用户请求：{query}")
        
        user_prompt = user_template.format(query=query)
        
        # 调用LLM
        if self.llm_client is None:
            raise Exception("LLM客户端未初始化")
        
        model_params = self.config.get("llm_analysis", {}).get("model_params", {})
        response = self.llm_client.analyze_intent(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            params=model_params
        )
        
        # 解析LLM响应
        try:
            # 直接处理字符串响应
            llm_result = response
            if isinstance(llm_result, str):
                # 清理响应文本
                cleaned_text = llm_result.strip()
                if cleaned_text.startswith('```json'):
                    cleaned_text = cleaned_text[7:]
                if cleaned_text.endswith('```'):
                    cleaned_text = cleaned_text[:-3]
                cleaned_text = cleaned_text.strip()
                
                result = json.loads(cleaned_text)
            else:
                result = llm_result
                
            # 验证结果格式
            if self._validate_analysis_result(result):
                result["analysis_method"] = "llm"
                return result
            else:
                logger.warning("LLM返回格式不正确，使用关键词分析")
                return self._analyze_with_keywords(query)
                
        except json.JSONDecodeError as e:
            logger.warning(f"LLM响应JSON解析失败: {e}")
            return self._analyze_with_keywords(query)
        except Exception as e:
            logger.warning(f"LLM调用失败: {e}")
            return self._analyze_with_keywords(query)
    
    def _analyze_with_keywords(self, query: str) -> Dict[str, Any]:
        """使用关键词分析工具需求"""
        query_lower = query.lower()
        tools_needed = []
        confidence = 0.0
        reasoning = "使用关键词分析"
        
        # 文件创建分析
        file_keywords = ["文件", ".txt", ".doc", ".pdf", ".md", ".json", ".csv"]
        create_keywords = ["创建", "新建", "生成", "制作"]
        
        has_file_keyword = any(keyword in query_lower for keyword in file_keywords)
        has_create_keyword = any(keyword in query_lower for keyword in create_keywords)
        
        # 文件夹创建分析
        folder_keywords = ["文件夹", "目录", "folder"]
        has_folder_keyword = any(keyword in query_lower for keyword in folder_keywords)
        
        if has_create_keyword:
            if has_file_keyword and not has_folder_keyword:
                tools_needed.append("create_file")
                confidence = 0.8
                reasoning = "检测到文件创建关键词"
            elif has_folder_keyword:
                tools_needed.append("create_folder")
                confidence = 0.8
                reasoning = "检测到文件夹创建关键词"
            elif not has_file_keyword and not has_folder_keyword:
                # 只有创建关键词，默认为文件夹
                tools_needed.append("create_folder")
                confidence = 0.6
                reasoning = "检测到创建关键词，默认为文件夹创建"
        
        # 如果没有检测到明确的工具需求
        if not tools_needed:
            tools_needed = ["unknown"]
            confidence = 0.1
            reasoning = "无法确定具体工具需求"
        
        return {
            "tools_needed": tools_needed,
            "confidence": confidence,
            "reasoning": reasoning,
            "analysis_method": "keyword",
            "execution_sequence": self._build_execution_sequence(tools_needed, query)
        }
    
    def _validate_analysis_result(self, result: Dict[str, Any]) -> bool:
        """验证分析结果格式"""
        required_fields = ["tools_needed", "confidence", "reasoning"]
        return all(field in result for field in required_fields)
    
    def _build_execution_sequence(self, tools_needed: List[str], query: str) -> List[Dict[str, Any]]:
        """构建工具执行序列"""
        sequence = []
        
        for tool_name in tools_needed:
            if tool_name == "create_file":
                sequence.append({
                    "tool_name": "create_file",
                    "description": "创建文件",
                    "parameters": self._extract_file_parameters(query)
                })
            elif tool_name == "create_folder":
                sequence.append({
                    "tool_name": "create_folder", 
                    "description": "创建文件夹",
                    "parameters": self._extract_folder_parameters(query)
                })
        
        return sequence
    
    def _extract_file_parameters(self, query: str) -> Dict[str, str]:
        """从查询中提取文件参数"""
        # 简单的参数提取逻辑
        return {
            "file_name": "从查询中提取的文件名",
            "content": "从查询中提取的文件内容",
            "parent_folder": "从查询中提取的父目录"
        }
    
    def _extract_folder_parameters(self, query: str) -> Dict[str, str]:
        """从查询中提取文件夹参数"""
        return {
            "folder_name": "从查询中提取的文件夹名",
            "parent_folder": "从查询中提取的父目录"
        }
    
    def get_supported_tools(self) -> Dict[str, Any]:
        """获取支持的工具列表"""
        return self.config.get("supported_tools", {})
    
    def is_tool_supported(self, tool_name: str) -> bool:
        """检查工具是否支持"""
        supported_tools = self.get_supported_tools()
        tool_config = supported_tools.get(tool_name, {})
        return tool_config.get("enabled", False)
    
    def get_error_message(self, error_type: str, **kwargs) -> Dict[str, str]:
        """获取错误消息"""
        error_config = self.config.get("error_handling", {}).get(error_type, {})
        
        message = error_config.get("message", "发生未知错误")
        suggestion = error_config.get("suggestion", "请稍后重试")
        
        # 格式化消息
        try:
            message = message.format(**kwargs)
            suggestion = suggestion.format(**kwargs)
        except:
            pass
        
        return {
            "message": message,
            "suggestion": suggestion
        }
    
    def _init_llm_client(self):
        """初始化LLM客户端"""
        try:
            from app.services.intent_config_manager import IntentConfigManager
            config_manager = IntentConfigManager()
            
            # 获取当前配置
            current_provider = config_manager.config['service']['current_provider']
            current_model = config_manager.get_current_model()
            provider_config = config_manager.get_current_provider_config()
            
            # 创建LLM客户端
            from app.services.intent_config_manager import IntentLLMClient
            self.llm_client = IntentLLMClient(current_provider, current_model, provider_config)
            
        except Exception as e:
            logger.error(f"LLM客户端初始化失败: {e}")
            self.llm_client = None
    
    def validate_tools(self, tools_needed: List[str]) -> Dict[str, Any]:
        """验证工具是否可用"""
        result = {
            "valid_tools": [],
            "invalid_tools": [],
            "disabled_tools": [],
            "errors": []
        }
        
        supported_tools = self.get_supported_tools()
        
        for tool_name in tools_needed:
            if tool_name == "unknown":
                continue
                
            if tool_name not in supported_tools:
                result["invalid_tools"].append(tool_name)
                error_msg = self.get_error_message("tool_not_found", tool_name=tool_name)
                result["errors"].append(error_msg)
            elif not supported_tools[tool_name].get("enabled", False):
                result["disabled_tools"].append(tool_name)
                error_msg = self.get_error_message("tool_disabled", tool_name=tool_name)
                result["errors"].append(error_msg)
            else:
                result["valid_tools"].append(tool_name)
        
        return result

# 创建全局实例
mcp_tool_analyzer = MCPToolAnalyzer() 