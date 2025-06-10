# LLM意图分析功能实现说明

## 概述

我们已经成功实现了基于大语言模型的智能意图分析功能，用于判断用户输入是应该执行MCP调用还是向量库检索。

## 核心特性

### 1. 智能意图分析
- **主要方法**: 使用LLM分析用户真实意图
- **备用方案**: 基于关键词的规则匹配
- **兼容性**: 向后兼容原有功能

### 2. 双重保障机制
- **优先级**: LLM分析 → 关键词匹配 → 默认搜索
- **容错性**: LLM失败时自动降级到关键词分析
- **可靠性**: 确保系统在任何情况下都能正常响应

## 实现细节

### 新增方法

#### `LLMService.analyze_user_intent(query, llm_model)`
```python
"""
使用LLM分析用户输入的意图，判断是MCP调用还是向量库检索

返回格式:
{
  "intent_type": "mcp_action|vector_search",
  "confidence": 0.0-1.0,
  "action_type": "create_file|create_folder|search_documents|other",
  "parameters": {...},
  "reasoning": "判断依据"
}
"""
```

#### `LLMService._fallback_intent_analysis(query)`
```python
"""
备用的基于关键词的意图分析
- 优先检测搜索关键词
- 文件扩展名判断文件创建
- 文件夹+创建关键词判断文件夹创建
"""
```

### 修改的路由

#### `semantic_search()` 
- 添加了`llm_model`参数支持
- 集成LLM意图分析
- 在响应中包含意图分析结果

#### `hybrid_search()`
- 同样集成LLM意图分析
- 保持原有搜索功能完整性
- 添加意图分析信息到响应

## 决策流程

```
用户输入
    ↓
LLM意图分析
    ↓
置信度 > 0.6 且为 MCP 操作？
    ↓ 是
执行 MCP 调用
    ↓ 否
LLM 分析失败？
    ↓ 是
关键词匹配分析
    ↓
检测到操作意图？
    ↓ 是
执行 MCP 调用
    ↓ 否
执行向量库搜索
```

## 使用示例

### API 调用
```javascript
// 语义搜索
POST /api/search/
{
  "query": "创建项目文档文件夹",
  "llm_model": "openai:gpt-3.5-turbo",
  "enable_mcp": true
}

// 混合搜索
POST /api/search/hybrid
{
  "query": "帮我找合同模板",
  "llm_model": "deepseek:deepseek-chat",
  "enable_llm": true,
  "enable_mcp": true
}
```

### 响应格式
```json
{
  "success": true,
  "data": {
    "query": "创建项目文档文件夹",
    "intent_analysis": {
      "intent_type": "mcp_action",
      "confidence": 0.95,
      "action_type": "create_folder",
      "reasoning": "用户明确要求创建文件夹",
      "used_llm": true
    },
    "mcp_results": [...],
    "search_type": "semantic"
  }
}
```

## 意图分类

### MCP 操作 (`mcp_action`)
- `create_file`: 创建文件
- `create_folder`: 创建文件夹
- `other`: 其他操作

### 向量搜索 (`vector_search`)
- `search_documents`: 搜索文档内容

## 关键词规则 (备用分析)

### 搜索意图
**关键词**: `['找', '搜索', '查找', '寻找', '在哪里', '哪里有', '搜', '查', '检索']`
**示例**: "找一下合同资料"

### 文件创建
**判断条件**: 包含文件扩展名
**扩展名**: `['.txt', '.doc', '.docx', '.pdf', '.xls', '.xlsx', '.jpg', '.png', '.mp4', '.md']`
**示例**: "创建readme.md"

### 文件夹创建
**判断条件**: 包含"文件夹"+"创建"关键词
**关键词**: 文件夹关键词 + 创建关键词
**示例**: "建立项目文件夹"

## 配置要求

### LLM 模型支持
- OpenAI GPT 系列
- DeepSeek Chat 系列  
- Ollama 本地模型

### 必要配置
```python
# config.py
MCP_CONFIG = {
    'enabled': True,
    # ... 其他配置
}

# LLM 提供商配置
LLM_PROVIDERS = {
    'openai': {
        'api_key': 'your-api-key',
        'base_url': 'https://api.openai.com/v1'
    }
}
```

## 优势

1. **智能化**: LLM 能理解自然语言的复杂表达
2. **准确性**: 比单纯关键词匹配更准确
3. **灵活性**: 支持多种语言表达方式
4. **可靠性**: 多层次降级保障机制
5. **透明性**: 提供分析过程和置信度
6. **扩展性**: 易于添加新的意图类型

## 注意事项

1. **API 成本**: LLM 调用会产生 API 费用
2. **网络依赖**: 需要稳定的网络连接
3. **响应时间**: LLM 分析会增加少量延迟
4. **配置要求**: 需要正确配置 LLM 模型和 API 密钥

## 测试建议

1. 使用不同的自然语言表达测试意图识别准确性
2. 验证降级机制在 LLM 不可用时的表现
3. 测试各种边缘情况和模糊表达
4. 监控 API 调用成本和响应时间 