# LLM集成功能说明

## 🚀 功能概述

为智能检索助手新增了大语言模型(LLM)选择功能，支持多种主流LLM提供商，为用户提供更智能的文档检索体验。

## 📊 支持的LLM提供商

### 1. OpenAI GPT 系列
- **GPT-3.5 Turbo**: 性价比最高的选择
- **GPT-4**: 更强的理解和推理能力
- **GPT-4 Turbo**: 最新的大容量模型

### 2. Anthropic Claude 系列
- **Claude 3 Haiku**: 快速响应模型
- **Claude 3 Sonnet**: 平衡性能模型
- **Claude 3 Opus**: 最强性能模型

### 3. Ollama (本地部署)
- **Llama 2**: Meta开源大模型
- **Qwen 2**: 阿里巴巴通义千问
- **ChatGLM3**: 清华智谱GLM系列
- **Baichuan 2**: 百川智能大模型

### 4. 智谱AI
- **GLM-4**: 最新一代模型
- **GLM-3 Turbo**: 快速版本

### 5. DeepSeek
- **DeepSeek Chat**: 通用对话模型
- **DeepSeek Coder**: 专业代码模型
- **DeepSeek V3**: 最新版本模型

## 🔧 配置说明

### 1. 环境变量配置 (config.env)

```bash
# OpenAI配置
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_BASE_URL=https://api.openai.com/v1

# Claude配置
ANTHROPIC_API_KEY=sk-ant-your-claude-key

# Ollama配置 (本地部署)
OLLAMA_BASE_URL=http://localhost:11434

# 智谱AI配置
ZHIPU_API_KEY=your-zhipu-api-key

# DeepSeek配置
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 默认LLM设置
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-3.5-turbo

# 功能开关
ENABLE_LLM_QUERY_OPTIMIZATION=true     # 查询优化
ENABLE_LLM_RESULT_RERANKING=true       # 结果重排序
ENABLE_LLM_ANSWER_GENERATION=false     # 答案生成

# 性能参数
LLM_TIMEOUT=30                         # 超时时间(秒)
LLM_MAX_CONTEXT_LENGTH=4000           # 最大上下文长度
LLM_RERANK_BATCH_SIZE=20              # 重排序批量大小
```

### 2. 前端界面

在智能检索助手界面的右上角，现在有两个下拉选择器：

1. **相关性要求**: 控制搜索结果的相似度阈值
   - 高相关性 (≥60%)
   - 中等相关性 (≥30%)
   - 低相关性 (≥10%)
   - 显示所有结果

2. **大语言模型**: 选择用于智能优化的LLM模型
   - 按提供商分组显示
   - 显示模型可用性状态
   - 自动选择默认模型

## 🎯 功能特性

### 1. 查询优化 (Query Optimization)
- **功能**: LLM分析用户查询意图，生成更适合向量检索的查询
- **场景**: 自然语言查询转换为检索友好的关键词
- **示例**: "关于合同的文档" → ["合同", "协议", "法律文件"]

### 2. 结果重排序 (Result Reranking)
- **功能**: 使用LLM对初步检索结果进行语义相关性重排
- **场景**: 提高最相关结果的排序位置
- **优势**: 结合向量相似度和语义理解

### 3. 答案生成 (Answer Generation)
- **功能**: 基于检索结果生成自然语言答案
- **场景**: 直接回答用户问题，无需浏览多个文档
- **状态**: 默认关闭，可通过配置启用

### 4. 智能降级
- **自动检测**: 如果LLM服务不可用，自动降级到传统检索
- **错误处理**: 优雅处理API调用失败
- **性能保障**: 确保基础功能正常工作

## 📝 使用指南

### 1. 基础使用
1. 打开智能检索助手页面
2. 在右上角选择合适的LLM模型
3. 设置相关性要求
4. 输入查询并开始搜索

### 2. 模型选择建议

**开发/测试环境:**
- 推荐: Ollama + Llama 2 (本地免费)
- 配置: 安装Ollama并拉取模型

**生产环境:**
- 推荐: OpenAI GPT-3.5 Turbo (性价比)
- 高质量需求: Claude 3 Sonnet
- 中文优化: 智谱GLM-4

### 3. 性能优化建议

**提高响应速度:**
```bash
ENABLE_LLM_QUERY_OPTIMIZATION=true
ENABLE_LLM_RESULT_RERANKING=false  # 关闭重排序
LLM_TIMEOUT=15                     # 减少超时时间
```

**提高结果质量:**
```bash
ENABLE_LLM_QUERY_OPTIMIZATION=true
ENABLE_LLM_RESULT_RERANKING=true   # 启用重排序
LLM_RERANK_BATCH_SIZE=10          # 减少批量大小
```

## 🔍 API接口

### 1. 获取可用模型
```bash
GET /api/config/llm-models
```

**响应示例:**
```json
{
  "success": true,
  "data": {
    "models": [
      {
        "provider": "openai",
        "provider_name": "OpenAI GPT",
        "model_key": "gpt-3.5-turbo",
        "model_name": "GPT-3.5 Turbo",
        "display_name": "OpenAI GPT - GPT-3.5 Turbo",
        "full_key": "openai:gpt-3.5-turbo",
        "is_available": true
      }
    ],
    "default": "openai:gpt-3.5-turbo",
    "features": {
      "query_optimization": true,
      "result_reranking": true,
      "answer_generation": false
    }
  }
}
```

### 2. 增强搜索请求
```bash
POST /api/search/
```

**请求示例:**
```json
{
  "query": "合同管理相关文档",
  "top_k": 5,
  "similarity_level": "medium",
  "llm_model": "openai:gpt-3.5-turbo",
  "enable_llm": true
}
```

## 🚨 注意事项

### 1. API密钥安全
- 不要在代码中硬编码API密钥
- 使用环境变量存储敏感信息
- 定期轮换API密钥

### 2. 成本控制
- 监控API调用量和费用
- 设置合理的超时时间
- 考虑使用本地模型降低成本

### 3. 隐私保护
- 敏感文档内容可能发送到第三方API
- 考虑使用本地部署的Ollama模型
- 查看各提供商的隐私政策

### 4. 性能考虑
- LLM调用会增加响应时间
- 可根据需要关闭部分功能
- 使用缓存减少重复调用

## 🔄 更新日志

### v1.0.0 (当前版本)
- ✅ 多LLM提供商支持
- ✅ 动态模型选择界面
- ✅ 查询优化功能
- ✅ 结果重排序功能
- ✅ 智能降级机制
- ✅ 配置管理系统

### 计划功能
- 🔄 答案生成功能完善
- 🔄 对话历史记忆
- 🔄 自定义Prompt模板
- 🔄 LLM性能统计
- 🔄 批量处理优化

## 🔧 添加新的LLM提供商

如果您想添加其他LLM提供商（如DeepSeek、Moonshot等），请按以下步骤操作：

### 1. 修改配置文件 (config.py)

在 `LLM_PROVIDERS` 字典中添加新的提供商配置：

```python
'deepseek': {
    'name': 'DeepSeek',
    'models': {
        'deepseek-chat': 'DeepSeek Chat',
        'deepseek-coder': 'DeepSeek Coder',
        'deepseek-v3': 'DeepSeek V3'
    },
    'api_key': os.environ.get('DEEPSEEK_API_KEY'),
    'base_url': os.environ.get('DEEPSEEK_BASE_URL') or 'https://api.deepseek.com'
}
```

### 2. 添加环境变量 (config.env)

```bash
# DeepSeek Configuration
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### 3. 更新API检查逻辑 (app/routes/config_routes.py)

在可用性检查中添加新提供商：

```python
elif provider_key == 'deepseek' and not provider_config.get('api_key'):
    is_available = False
```

### 4. 测试配置

1. 重启应用
2. 访问 `/api/config/llm-models` 检查新模型是否出现
3. 在前端界面确认新的模型选项

### 5. 注意事项

- **API兼容性**: 如果新提供商的API格式与OpenAI不兼容，可能需要在LLM客户端代码中添加适配器
- **认证方式**: 不同提供商可能有不同的认证方式（API Key、Token等）
- **请求格式**: 确认请求参数和响应格式是否需要特殊处理

## 📞 技术支持

如果在使用过程中遇到问题，请参考：

1. **检查配置**: 确认API密钥和服务地址正确
2. **查看日志**: 检查应用日志中的错误信息
3. **测试连接**: 使用浏览器访问 `/api/config/llm-models`
4. **降级模式**: 确保传统检索功能正常

---

*本文档会随着功能更新持续完善，建议定期查看最新版本。* 