"""
MCP工具分析器 v3.0
用于分析用户请求，确定需要调用哪些MCP工具
重构：从MCP管理器动态获取工具信息，不再依赖静态配置文件
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
    """MCP工具分析器 v3.0 - 动态工具获取版本"""
    
    def __init__(self, mcp_manager=None):
        """
        初始化工具分析器
        Args:
            mcp_manager: MCP管理器实例，用于动态获取工具信息
        """
        self.mcp_manager = mcp_manager
        self.config = self._load_config()
        self.llm_client = None  # 延迟初始化
        
    def _load_config(self) -> Dict[str, Any]:
        """加载基础配置（不包含工具列表）"""
        config_path = Path(__file__).parent.parent.parent / "prompts" / "mcp_tools_config.yaml"
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                logger.info("MCP工具分析基础配置加载成功")
                return config
        except Exception as e:
            logger.error(f"MCP工具分析基础配置加载失败: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "llm_analysis": {
                "model_params": {
                    "max_tokens": 500,
                    "temperature": 0.1,
                    "timeout": 30,
                    "max_retries": 2
                }
            },
            "error_handling": {
                "tool_not_found": {
                    "message": "抱歉，您请求的操作暂不支持。",
                    "suggestion": "请检查当前可用的MCP工具。"
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
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """从MCP管理器动态获取可用工具"""
        if not self.mcp_manager or not self.mcp_manager.is_initialized:
            logger.warning("MCP管理器未初始化，返回空工具列表")
            return []
        
        try:
            mcp_tools = self.mcp_manager.get_available_tools()
            tools_info = []
            
            for tool in mcp_tools:
                tool_info = {
                    "name": tool.name,
                    "description": tool.description,
                    "server_name": tool.server_name,
                    "parameters": self._extract_parameters_from_schema(tool.inputSchema)
                }
                tools_info.append(tool_info)
            
            logger.info(f"从MCP管理器获取到 {len(tools_info)} 个工具")
            return tools_info
            
        except Exception as e:
            logger.error(f"获取MCP工具失败: {e}")
            return []
    
    def _extract_parameters_from_schema(self, input_schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从工具的输入模式中提取参数信息"""
        parameters = []
        
        if not input_schema or "properties" not in input_schema:
            return parameters
        
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])
        
        for param_name, param_info in properties.items():
            parameter = {
                "name": param_name,
                "type": param_info.get("type", "string"),
                "required": param_name in required,
                "description": param_info.get("description", "")
            }
            parameters.append(parameter)
        
        return parameters
    
    def _generate_dynamic_system_prompt(self) -> str:
        """动态生成系统提示词，包含当前可用的MCP工具"""
        available_tools = self.get_available_tools()
        
        if not available_tools:
            return self._get_fallback_system_prompt()
        
        # 构建工具列表描述
        tools_description = []
        for i, tool in enumerate(available_tools, 1):
            tool_desc = f"{i}. {tool['name']} - {tool['description']}"
            
            if tool['parameters']:
                tool_desc += "\n   参数："
                for param in tool['parameters']:
                    required_mark = "（必须）" if param['required'] else "（可选）"
                    tool_desc += f"\n   - {param['name']}: {param['description']} {required_mark}"
            
            tools_description.append(tool_desc)
        
        tools_text = "\n\n".join(tools_description)
        
        system_prompt = f"""你是一个专业的MCP工具分析专家。你需要分析用户的操作请求，确定需要调用哪些MCP工具，并从用户请求中提取具体的参数值。

【重要】请严格按照以下JSON格式返回分析结果，确保JSON语法完全正确：

{{
  "tools_needed": ["工具名称1", "工具名称2"],
  "confidence": 0.9,
  "reasoning": "说明选择这些工具的依据",
  "execution_sequence": [
    {{
      "tool_name": "工具名称",
      "description": "执行描述",
      "parameters": {{
        "参数名": "从用户请求中提取的具体参数值"
      }}
    }}
  ]
}}

【格式要求】：
1. 不要添加markdown代码块标记（如```json）
2. 确保每个execution_sequence项目都有完整的"parameters": {{}}结构
3. 所有字符串必须用双引号包围
4. 数组和对象的语法必须正确
5. 每行末尾不要有多余的逗号

当前可用的MCP工具及其参数：

{tools_text}

参数提取要求：
1. 从用户请求中提取具体的参数值，不要返回描述性文字
2. 如果用户没有明确指定某个参数，则不要包含该参数
3. 文件名必须包含扩展名，如果用户没有指定，根据上下文推断合适的扩展名
4. 目录名称要准确提取，不要包含多余的文字
5. 对于复杂请求，按逻辑顺序安排执行序列

【JSON示例】：
对于"在test文件夹下创建test1和test2文件夹，在test1下创建1.txt文件"：
{{
  "tools_needed": ["create_folder", "create_file"],
  "confidence": 0.9,
  "reasoning": "用户需要创建文件夹和文件两个操作，需要分别调用create_folder和create_file工具",
  "execution_sequence": [
    {{
      "tool_name": "create_folder",
      "description": "在test文件夹下创建test1文件夹",
      "parameters": {{
        "folder_name": "test1",
        "parent_folder": "test"
      }}
    }},
    {{
      "tool_name": "create_folder", 
      "description": "在test文件夹下创建test2文件夹",
      "parameters": {{
        "folder_name": "test2",
        "parent_folder": "test"
      }}
    }},
    {{
      "tool_name": "create_file",
      "description": "在test1文件夹下创建1.txt文件",
      "parameters": {{
        "file_name": "1.txt",
        "parent_folder": "test1"
      }}
    }}
  ]
}}"""

        return system_prompt
    
    def _get_fallback_system_prompt(self) -> str:
        """当无可用工具时的降级系统提示词"""
        return """你是一个专业的MCP工具分析专家。当前没有可用的MCP工具，请返回以下格式：

{
  "tools_needed": [],
  "confidence": 0.0,
  "reasoning": "当前没有可用的MCP工具",
  "execution_sequence": []
}"""
    
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
        
        # 动态生成系统提示词
        system_prompt = self._generate_dynamic_system_prompt()
        user_prompt = f"请分析以下用户的操作请求，确定需要调用哪些MCP工具，并提取具体的参数值：\n\n用户请求：\"{query}\"\n\n请返回JSON格式的工具分析结果："
        
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
        """使用关键词分析工具需求（基于动态工具列表）"""
        available_tools = self.get_available_tools()
        
        if not available_tools:
            return {
                "tools_needed": [],
                "confidence": 0.0,
                "reasoning": "没有可用的MCP工具",
                "analysis_method": "keyword",
                "execution_sequence": []
            }
        
        query_lower = query.lower()
        tools_needed = []
        confidence = 0.0
        reasoning = "使用关键词分析"
        
        # 从配置获取关键词
        create_keywords = self.config.get("keyword_matching", {}).get("create_keywords", ["创建", "新建", "生成"])
        file_keywords = self.config.get("keyword_matching", {}).get("file_keywords", ["文件", ".txt", ".doc"])
        folder_keywords = self.config.get("keyword_matching", {}).get("folder_keywords", ["文件夹", "目录", "folder"])
        
        # 基于工具名称和描述进行关键词匹配
        for tool in available_tools:
            tool_name = tool['name'].lower()
            tool_desc = tool['description'].lower()
            
            # 检查是否有创建操作关键词
            if any(keyword in query_lower for keyword in create_keywords):
                # 文件相关工具匹配（更精确的匹配）
                if ('create_file' in tool_name or 'file' in tool_name) and '创建' in tool_desc:
                    if any(keyword in query_lower for keyword in file_keywords):
                        if tool['name'] not in tools_needed:  # 避免重复添加
                            tools_needed.append(tool['name'])
                            confidence = 0.8
                            reasoning = f"检测到文件创建关键词，匹配工具: {tool['name']}"
                        break  # 找到第一个匹配的文件工具就停止
                
                # 文件夹相关工具匹配（更精确的匹配）
                elif ('create_folder' in tool_name or 'folder' in tool_name) and '文件夹' in tool_desc:
                    if any(keyword in query_lower for keyword in folder_keywords):
                        if tool['name'] not in tools_needed:  # 避免重复添加
                            tools_needed.append(tool['name'])
                            confidence = 0.8
                            reasoning = f"检测到文件夹创建关键词，匹配工具: {tool['name']}"
                        break  # 找到第一个匹配的文件夹工具就停止
            
            # 浏览器自动化工具匹配
            elif any(keyword in query_lower for keyword in ['登录', '网站', 'http', 'https', '浏览器', '网页']):
                if 'puppeteer' in tool_name:
                    if 'navigate' in tool_name:  # 优先匹配导航工具
                        if tool['name'] not in tools_needed:
                            tools_needed.append(tool['name'])
                            confidence = 0.8
                            reasoning = f"检测到浏览器操作关键词，匹配工具: {tool['name']}"
                        break
        
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
        available_tools = self.get_available_tools()
        tools_dict = {tool['name']: tool for tool in available_tools}
        
        for tool_name in tools_needed:
            if tool_name == "unknown" or tool_name not in tools_dict:
                continue
                
            tool_info = tools_dict[tool_name]
            sequence.append({
                "tool_name": tool_name,
                "description": f"执行 {tool_info['description']}",
                "parameters": self._extract_parameters_from_query(query, tool_info)
            })
        
        return sequence
    
    def _extract_parameters_from_query(self, query: str, tool_info: Dict[str, Any]) -> Dict[str, str]:
        """从查询中提取工具参数（基于工具的参数定义）"""
        parameters = {}
        
        # 这里可以根据具体的工具参数进行智能提取
        # 暂时保持简单的实现
        if 'file' in tool_info['name'].lower():
            parameters.update(self._extract_file_parameters(query))
        elif 'folder' in tool_info['name'].lower():
            parameters.update(self._extract_folder_parameters(query))
        
        return parameters
    
    def _extract_file_parameters(self, query: str) -> Dict[str, str]:
        """从查询中提取文件参数"""
        import re
        
        params = {}
        
        # 从配置获取文件名提取模式
        file_patterns = self.config.get("parameter_extraction", {}).get("file_name_patterns", [
            r'(?:创建|生成|新建).*?([a-zA-Z0-9\u4e00-\u9fff]+\.[a-zA-Z0-9]+)',
            r'([a-zA-Z0-9\u4e00-\u9fff]+\.[a-zA-Z0-9]+)',
        ])
        
        for pattern in file_patterns:
            match = re.search(pattern, query)
            if match:
                params['file_name'] = match.group(1)
                break
        
        # 从配置获取父目录提取模式
        parent_patterns = self.config.get("parameter_extraction", {}).get("parent_folder_patterns", [
            r'在\s*([a-zA-Z0-9\u4e00-\u9fff]+)\s*(?:文件夹|目录|下)',
            r'([a-zA-Z0-9\u4e00-\u9fff]+)\s*(?:文件夹|目录)\s*下',
        ])
        
        for pattern in parent_patterns:
            match = re.search(pattern, query)
            if match:
                params['parent_folder'] = match.group(1)
                break
        
        return params
    
    def _extract_folder_parameters(self, query: str) -> Dict[str, str]:
        """从查询中提取文件夹参数"""
        import re
        
        params = {}
        
        # 从配置获取文件夹名提取模式
        folder_patterns = self.config.get("parameter_extraction", {}).get("folder_name_patterns", [
            r'(?:创建|新建).*?([a-zA-Z0-9\u4e00-\u9fff]+)(?:文件夹|目录)',
            r'([a-zA-Z0-9\u4e00-\u9fff]+)(?:文件夹|目录)',
        ])
        
        for pattern in folder_patterns:
            match = re.search(pattern, query)
            if match:
                params['folder_name'] = match.group(1)
                break
        
        return params
    
    def get_supported_tools(self) -> Dict[str, Any]:
        """获取支持的工具（从MCP管理器动态获取）"""
        available_tools = self.get_available_tools()
        supported_tools = {}
        
        for tool in available_tools:
            supported_tools[tool['name']] = {
                "enabled": True,  # 从MCP管理器获取的工具默认为启用状态
                "description": tool['description'],
                "server_name": tool['server_name'],
                "parameters": tool['parameters']
            }
        
        return supported_tools
    
    def is_tool_supported(self, tool_name: str) -> bool:
        """检查工具是否支持"""
        supported_tools = self.get_supported_tools()
        return tool_name in supported_tools
    
    def get_error_message(self, error_type: str, **kwargs) -> Dict[str, str]:
        """获取错误消息"""
        error_config = self.config.get("error_handling", {}).get(error_type, {})
        
        message = error_config.get("message", "操作失败")
        suggestion = error_config.get("suggestion", "请重试")
        
        # 格式化消息
        try:
            message = message.format(**kwargs)
            suggestion = suggestion.format(**kwargs)
        except KeyError:
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
            self.llm_client = IntentLLMClient(current_provider, current_model, provider_config)
            logger.info("LLM客户端初始化成功")
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

# 工厂函数，用于创建带有MCP管理器的工具分析器实例
def create_mcp_tool_analyzer(mcp_manager=None):
    """
    创建MCP工具分析器实例
    Args:
        mcp_manager: MCP管理器实例，如果为None则创建一个新的
    Returns:
        MCPToolAnalyzer: 工具分析器实例
    """
    if mcp_manager is None:
        from app.services.mcp.servers.mcp_manager import MCPManager
        mcp_manager = MCPManager()
    
    return MCPToolAnalyzer(mcp_manager)

# 为了保持向后兼容性，创建一个全局实例（但不推荐使用）
# 建议使用 create_mcp_tool_analyzer() 函数创建实例
mcp_tool_analyzer = MCPToolAnalyzer() 