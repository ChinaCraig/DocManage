# LLM服务模块化架构

## 📁 项目结构

```
app/services/llm/
├── __init__.py              # 主要导出接口
├── base_client.py           # BaseLLMClient抽象基类  
├── factory.py               # LLMClientFactory工厂类
├── service.py               # LLMService统一服务接口
├── providers/               # 各个提供商的实现
│   ├── __init__.py
│   ├── openai_client.py     # OpenAI完整实现
│   ├── deepseek_client.py   # DeepSeek完整实现
│   ├── ollama_client.py     # Ollama完整实现
│   └── claude_client.py     # Claude示例实现（未启用）
└── utils/                   # 公共工具函数目录
    └── __init__.py
```

## 🎯 设计原则

### 1. 单一职责原则
- 每个模块只负责特定功能
- `base_client.py`：定义抽象接口
- `factory.py`：负责客户端创建
- `service.py`：提供统一服务接口
- `providers/`：各提供商的具体实现

### 2. 开闭原则
- 对扩展开放，对修改封闭
- 新增LLM提供商无需修改现有代码
- 只需实现`BaseLLMClient`接口

### 3. 依赖倒置原则
- 高层模块不依赖低层模块
- 都依赖于抽象（`BaseLLMClient`）

## 🚀 使用方式

### 基本导入（与原来完全兼容）
```python
from app.services.llm import LLMService

# 所有原有功能保持不变
models = LLMService.get_available_models()
answer = LLMService.generate_answer(query, context, llm_model)
```

### 高级使用
```python
from app.services.llm import LLMClientFactory, BaseLLMClient

# 直接创建特定客户端
client = LLMClientFactory.create_client('openai:gpt-4')
optimized_query = client.optimize_query(user_query)
```

## 🔧 扩展新的LLM提供商

### 步骤1：创建客户端实现
在`providers/`目录创建新文件，例如`gemini_client.py`：

```python
from ..base_client import BaseLLMClient

class GeminiClient(BaseLLMClient):
    def __init__(self, model: str):
        provider_config = Config.LLM_PROVIDERS['gemini']
        super().__init__(
            model=model,
            api_key=provider_config['api_key'],
            base_url=provider_config['base_url']
        )
    
    def optimize_query(self, query: str, scenario: str = None, template: str = None) -> str:
        # 实现查询优化逻辑
        pass
    
    def rerank_results(self, query: str, results: List[Dict]) -> List[Dict]:
        # 实现结果重排序逻辑
        pass
    
    def generate_answer(self, query: str, context: str, scenario: str = None, style: str = None) -> str:
        # 实现答案生成逻辑
        pass
```

### 步骤2：注册到工厂类
在`factory.py`中添加：

```python
from .providers import GeminiClient

# 在create_client方法中添加
elif provider == 'gemini':
    return GeminiClient(model)
```

### 步骤3：更新导出
在`providers/__init__.py`中添加：

```python
from .gemini_client import GeminiClient

__all__ = [
    'OpenAIClient',
    'DeepSeekClient', 
    'OllamaClient',
    'GeminiClient'  # 新增
]
```

## 📋 必须实现的接口

继承`BaseLLMClient`时必须实现以下抽象方法：

```python
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
```

## 🔨 可选重写的方法

根据需要可以重写以下方法：

```python
def _make_request(self, data: Dict, headers: Dict = None) -> Dict:
    """HTTP请求方法，用于自定义API调用格式"""
    pass

def _call_llm_with_prompt(self, system_prompt: str, user_prompt: str, parameters: Dict) -> str:
    """使用提示词调用LLM的通用方法"""
    pass
```

## ✅ 已完成的功能

- ✅ 完全模块化重构
- ✅ 保持100%向后兼容
- ✅ OpenAI客户端完整实现
- ✅ DeepSeek客户端完整实现  
- ✅ Ollama客户端完整实现
- ✅ 工厂模式管理客户端创建
- ✅ 抽象基类定义统一接口
- ✅ 统一服务接口保持原有API
- ✅ 完整的错误处理和日志记录

## 🧪 测试验证

运行以下命令验证模块正常工作：

```bash
python -c "
from app.services.llm import LLMService, LLMClientFactory
print('✅ 模块导入成功')
models = LLMService.get_available_models()
print(f'✅ 获取到 {len(models)} 个可用模型')
client = LLMClientFactory.create_client('deepseek:deepseek-chat')
print('✅ 客户端创建成功' if client else '⚠️ 客户端创建失败')
"
```

## 📈 性能优化

- 延迟加载：客户端只在需要时创建
- 连接复用：复用HTTP连接减少开销
- 批量处理：重排序等操作支持批量处理
- 错误恢复：优雅降级，避免单点失败

## 🛡️ 错误处理

- 网络错误：自动重试和降级
- API错误：记录日志并返回默认值
- 配置错误：启动时检查并警告
- 运行时错误：隔离错误，不影响其他功能 