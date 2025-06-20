# 意图识别独立配置系统说明

## 概述

意图识别系统现已实现完全独立的配置架构，与全局LLM配置完全隔离，专门为意图识别模块提供配置和服务。

## 架构特点

### ✅ 完全隔离
- **独立配置文件**: `prompts/intent_recognition_config.yaml`
- **独立配置管理器**: `app/services/intent_config_manager.py`
- **独立LLM客户端**: 专用的`IntentLLMClient`类
- **不依赖全局配置**: 与全局`LLMClientFactory`完全分离

### ✅ 精简配置
- **支持模型**: 仅支持DeepSeek和豆包两个提供商
- **远程/本地**: 支持远程API和本地模型配置
- **降级机制**: LLM失败时自动降级到关键词分析
- **缓存优化**: 独立的缓存配置和管理

## 配置文件结构

### 1. 服务模式配置
```yaml
service:
  mode: "remote"              # remote/local
  current_provider: "deepseek" # deepseek/doubao
  current_model: "deepseek-chat"
```

### 2. LLM提供商配置
```yaml
providers:
  deepseek:
    enabled: true
    api_key_env: "DEEPSEEK_API_KEY"
    base_url: "https://api.deepseek.com"
    models:
      deepseek-chat: "DeepSeek Chat"
      deepseek-coder: "DeepSeek Coder"
      deepseek-v3: "DeepSeek V3"
    
  doubao:
    enabled: true
    api_key_env: "DOUBAO_API_KEY"
    base_url: "https://ark.cn-beijing.volces.com"
    models:
      doubao-lite-4k: "豆包 Lite 4K"
      doubao-pro-4k: "豆包 Pro 4K"
      doubao-pro-32k: "豆包 Pro 32K"
```

### 3. 意图识别提示词
```yaml
prompts:
  system: |
    你是一个专业的用户意图识别专家...
  user_template: |
    请分析以下用户输入的意图：
    用户输入："{query}"
  confidence_threshold: 0.6
```

### 4. 降级处理配置
```yaml
fallback:
  enabled: true
  triggers:
    - "llm_api_error"
    - "json_parse_error"  
    - "timeout_error"
  strategy: "keyword_analysis"
  default_intent: "normal_chat"
```

### 5. 关键词分析配置
```yaml
keyword_analysis:
  enabled: true
  intent_keywords:
    mcp_action:
      primary:
        - ["创建", "新建", "建立", "生成", "制作"]
        - ["添加", "增加", "建", "做一个", "写个"]
    knowledge_search:
      primary:
        - ["查找", "搜索", "寻找", "检索", "查询"]
        - ["分析", "检查", "审查", "评估", "对比"]
    normal_chat:
      primary:
        - ["什么是", "如何", "为什么", "请解释"]
        - ["你是谁", "你好", "介绍自己"]
```

## 使用方式

### 导入方式
```python
# 导入意图识别服务（推荐）
from app.services.intent_service import intent_service

# 或者导入配置管理器
from app.services.intent_config_manager import intent_config
```

### 基本用法
```python
# 分析用户意图
result = intent_service.analyze_intent("创建一个新文档")

# 结果格式
{
    'intent_type': 'mcp_action',
    'confidence': 0.9,
    'action_type': 'create_file',
    'parameters': {...},
    'reasoning': '基于关键词分析，匹配mcp_action意图',
    'analysis_method': 'llm',  # or 'keyword'
    'timestamp': '2025-06-19T14:48:07.830550'
}
```

### 配置管理
```python
# 获取服务状态
status = intent_config.get_service_status()

# 获取可用模型
models = intent_config.get_available_models()

# 更新当前模型
intent_config.update_current_model('doubao', 'doubao-pro-4k')
```

## 环境变量配置

### 必须设置的环境变量
```bash
# DeepSeek API密钥（如果使用DeepSeek）
export DEEPSEEK_API_KEY="your_deepseek_api_key"

# 豆包API密钥（如果使用豆包）
export DOUBAO_API_KEY="your_doubao_api_key"
```

## 支持的意图类型

1. **mcp_action**: MCP操作
   - 文件创建：`create_file`
   - 文件夹创建：`create_folder`
   - 其他操作：`other`

2. **knowledge_search**: 知识库检索
   - 文档搜索：`search_documents`

3. **normal_chat**: 普通聊天
   - 一般对话：`chat`

## 降级机制

当LLM分析失败时，系统会自动降级到关键词分析：

1. **触发条件**:
   - LLM API调用失败
   - JSON解析失败
   - 请求超时

2. **降级流程**:
   - LLM分析 → 关键词分析 → 固定兜底

3. **优先级顺序**:
   - mcp_action（最高优先级）
   - knowledge_search（中等优先级）
   - normal_chat（兜底优先级）

## 性能特性

- **缓存机制**: 3600秒TTL，最大1000条缓存
- **超时控制**: 30秒API调用超时
- **重试机制**: 最大2次重试
- **内存优化**: LRU缓存清理机制

## 与全局配置的隔离

### ✅ 完全隔离的部分
- 配置文件独立
- LLM客户端独立
- 提示词独立
- 降级机制独立
- 缓存系统独立

### ✅ 保持的兼容性
- 返回格式与现有系统兼容
- 导入方式保持不变
- API接口保持不变

## 总结

意图识别系统现已实现完全独立的配置架构，满足了以下需求：

1. ✅ **配置完全隔离**: 与全局LLM配置互不干扰
2. ✅ **支持远程/本地**: 灵活的部署模式
3. ✅ **精简模型支持**: 仅支持DeepSeek和豆包
4. ✅ **完整降级机制**: LLM失败时自动降级
5. ✅ **独立客户端**: 专用的LLM客户端实现
6. ✅ **保持兼容性**: 现有代码无需修改

这个独立配置系统为意图识别提供了专门优化的配置管理，为可能使用本地模型奠定了基础。 