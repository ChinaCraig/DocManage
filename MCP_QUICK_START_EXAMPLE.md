# MCP快速开始示例

本文档通过具体示例展示如何在DocManage系统中添加MCP服务器。

## 🚀 示例1：添加文件系统MCP服务器

### 步骤1：检查Node.js环境

```bash
# 检查Node.js是否已安装
node --version
# 输出示例: v18.17.0

npm --version  
# 输出示例: 9.6.7
```

### 步骤2：编辑配置文件

打开 `config/mcp_config.yaml`，添加文件系统服务器：

```yaml
servers:
  # 现有配置...
  document-management:
    args:
    - -m
    - app.services.mcp.servers.document_server
    command: python
    description: 内置文档管理服务器
    enabled: true
    working_directory: .
  
  # 新添加的文件系统服务器
  filesystem-documents:
    command: npx
    args:
      - '@modelcontextprotocol/server-filesystem'
      - '/Users/craig-mac/Documents'  # 替换为您的实际路径
      - '/Users/craig-mac/Desktop'
    description: 本地文件系统操作
    enabled: true
    timeout: 30
```

### 步骤3：重新加载配置

```bash
# 通过API重新加载配置
curl -X POST http://localhost:5000/api/mcp/v2/reload
```

### 步骤4：验证服务器

```bash
# 检查服务器状态
curl http://localhost:5000/api/mcp/v2/servers | jq '.data[] | select(.name=="filesystem-documents")'

# 查看新增的工具
curl http://localhost:5000/api/mcp/v2/tools | jq '.data[] | select(.server_name=="filesystem-documents")'
```

### 步骤5：测试工具调用

```bash
# 创建一个测试文件
curl -X POST http://localhost:5000/api/mcp/v2/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "write_file",
    "arguments": {
      "path": "/Users/craig-mac/Documents/test_mcp.txt",
      "content": "Hello from MCP!"
    },
    "server_name": "filesystem-documents"
  }'

# 读取文件内容
curl -X POST http://localhost:5000/api/mcp/v2/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "read_file",
    "arguments": {
      "path": "/Users/craig-mac/Documents/test_mcp.txt"
    },
    "server_name": "filesystem-documents"
  }'
```

## 🔍 示例2：添加Brave搜索MCP服务器

### 步骤1：获取API密钥

1. 访问 [Brave Search API](https://api.search.brave.com/)
2. 注册账号并获取API密钥

### 步骤2：配置服务器

```yaml
servers:
  brave-search:
    command: npx
    args:
      - '@modelcontextprotocol/server-brave-search'
    description: Brave搜索引擎集成
    enabled: true
    env:
      BRAVE_API_KEY: "your-actual-api-key-here"  # 替换为真实的API密钥
    timeout: 30
```

### 步骤3：测试搜索功能

```bash
# 重新加载配置
curl -X POST http://localhost:5000/api/mcp/v2/reload

# 执行搜索
curl -X POST http://localhost:5000/api/mcp/v2/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "brave_web_search",
    "arguments": {
      "query": "Model Context Protocol MCP"
    },
    "server_name": "brave-search"
  }'
```

## 🛠️ 示例3：创建自定义计算器MCP服务器

### 步骤1：创建服务器文件

```python
# app/services/mcp/servers/calculator_server.py
#!/usr/bin/env python3
"""
计算器MCP服务器
提供基本数学运算功能
"""

import asyncio
import json
import sys
import logging
from typing import Dict, Any
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)

class CalculatorMCPServer:
    """计算器MCP服务器"""
    
    def __init__(self):
        self.tools = {
            "calculate": {
                "name": "calculate",
                "description": "执行基本数学运算",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "数学表达式，如 '2 + 3 * 4'"
                        }
                    },
                    "required": ["expression"]
                }
            }
        }
    
    async def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理MCP请求"""
        try:
            method = request_data.get("method")
            request_id = request_data.get("id")
            
            if method == "tools/list":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": list(self.tools.values())
                    }
                }
            
            elif method == "tools/call":
                params = request_data.get("params", {})
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                if tool_name == "calculate":
                    result = await self._calculate(arguments)
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": result
                                }
                            ]
                        }
                    }
                else:
                    raise ValueError(f"未知工具: {tool_name}")
            
            else:
                raise ValueError(f"未知方法: {method}")
        
        except Exception as e:
            logger.error(f"处理请求失败: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_data.get("id"),
                "error": {
                    "code": -1,
                    "message": str(e)
                }
            }
    
    async def _calculate(self, arguments: Dict[str, Any]) -> str:
        """执行计算"""
        expression = arguments.get("expression", "")
        
        try:
            # 安全的数学表达式求值（仅允许基本运算）
            allowed_chars = set("0123456789+-*/.() ")
            if not all(c in allowed_chars for c in expression):
                return "错误：表达式包含不允许的字符"
            
            # 使用eval进行计算（在受控环境中）
            result = eval(expression, {"__builtins__": {}}, {})
            return f"计算结果：{expression} = {result}"
            
        except Exception as e:
            return f"计算错误：{str(e)}"

async def main():
    """主函数"""
    server = CalculatorMCPServer()
    
    while True:
        try:
            line = input()
            if not line.strip():
                continue
            
            request_data = json.loads(line)
            response = await server.handle_request(request_data)
            print(json.dumps(response))
            
        except EOFError:
            break
        except Exception as e:
            logger.error(f"主循环错误: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
```

### 步骤2：添加配置

```yaml
servers:
  calculator:
    command: python
    args:
      - '-m'
      - 'app.services.mcp.servers.calculator_server'
    description: 基本数学计算器
    enabled: true
    working_directory: '.'
    timeout: 30
```

### 步骤3：测试计算器

```bash
# 重新加载配置
curl -X POST http://localhost:5000/api/mcp/v2/reload

# 测试计算
curl -X POST http://localhost:5000/api/mcp/v2/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "calculate",
    "arguments": {
      "expression": "2 + 3 * 4"
    },
    "server_name": "calculator"
  }'
```

## 🔧 常用调试命令

### 检查系统状态

```bash
# 查看MCP系统状态
curl http://localhost:5000/api/mcp/v2/status | jq

# 查看所有服务器
curl http://localhost:5000/api/mcp/v2/servers | jq '.data[] | {name: .name, enabled: .enabled, connected: .connected}'

# 查看所有工具
curl http://localhost:5000/api/mcp/v2/tools | jq '.data[] | {name: .name, server: .server_name, description: .description}'
```

### 手动测试MCP服务器

```bash
# 测试文件系统服务器
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | npx @modelcontextprotocol/server-filesystem /tmp

# 测试自定义服务器
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python -m app.services.mcp.servers.calculator_server
```

### 查看日志

```bash
# 查看应用日志
tail -f logs/app.log

# 查看MCP相关日志
grep -i mcp logs/app.log | tail -20
```

## 📝 配置模板

### 完整的mcp_config.yaml示例

```yaml
client:
  default_timeout: 30
  max_concurrent_requests: 10
  retry_attempts: 3
  retry_delay: 1.0

servers:
  # 内置文档管理服务器
  document-management:
    command: python
    args:
      - '-m'
      - 'app.services.mcp.servers.document_server'
    description: 内置文档管理服务器
    enabled: true
    working_directory: '.'
    
  # 文件系统服务器
  filesystem-documents:
    command: npx
    args:
      - '@modelcontextprotocol/server-filesystem'
      - '/Users/username/Documents'
      - '/Users/username/Desktop'
    description: 本地文件系统操作
    enabled: true
    timeout: 30
    
  # Brave搜索服务器
  brave-search:
    command: npx
    args:
      - '@modelcontextprotocol/server-brave-search'
    description: Brave搜索引擎
    enabled: false  # 需要API密钥才能启用
    env:
      BRAVE_API_KEY: "your-api-key-here"
    timeout: 30
    
  # 自定义计算器服务器
  calculator:
    command: python
    args:
      - '-m'
      - 'app.services.mcp.servers.calculator_server'
    description: 基本数学计算器
    enabled: true
    working_directory: '.'
    timeout: 30
```

## 🎯 下一步

1. **阅读完整文档**: 查看 `MCP_SERVER_MANAGEMENT_GUIDE.md` 获取详细信息
2. **探索更多服务器**: 访问 [MCP服务器库](https://github.com/modelcontextprotocol/servers)
3. **创建自定义工具**: 根据业务需求开发专用MCP服务器
4. **集成到工作流**: 将MCP工具集成到日常工作流程中

---

*快速开始示例 - 2024年12月* 