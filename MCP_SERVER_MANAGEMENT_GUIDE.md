# MCP服务器管理指南

本文档详细介绍如何在DocManage系统中添加和管理MCP（Model Context Protocol）服务器。

## 📋 目录

1. [系统概述](#系统概述)
2. [添加第三方MCP服务器](#添加第三方mcp服务器)
3. [创建自定义MCP服务器](#创建自定义mcp服务器)
4. [配置文件管理](#配置文件管理)
5. [API管理方式](#api管理方式)
6. [故障排除](#故障排除)
7. [最佳实践](#最佳实践)

## 🎯 系统概述

DocManage系统支持两种类型的MCP服务器：

- **第三方MCP服务器**: 使用现有的开源MCP服务器（如文件系统、搜索引擎等）
- **自定义MCP服务器**: 为特定需求开发的内置服务器

### 当前系统架构
```
app/services/mcp/
├── __init__.py              # 模块导出
├── config/
│   └── mcp_config.py        # 配置管理器
├── clients/
│   └── mcp_client.py        # JSON-RPC客户端
├── servers/
│   ├── mcp_manager.py       # MCP管理器
│   └── document_server.py   # 内置文档服务器
└── tools/
    └── tool_registry.py     # 工具注册表
```

## 🌐 添加第三方MCP服务器

### 步骤1: 选择MCP服务器

常用的第三方MCP服务器：

| 服务器名称 | 功能描述 | npm包名 |
|------------|----------|---------|
| Filesystem | 文件系统操作 | `@modelcontextprotocol/server-filesystem` |
| Brave Search | 网络搜索 | `@modelcontextprotocol/server-brave-search` |
| SQLite | 数据库操作 | `@modelcontextprotocol/server-sqlite` |
| Puppeteer | 浏览器自动化 | `@modelcontextprotocol/server-puppeteer` |
| GitHub | GitHub集成 | `@modelcontextprotocol/server-github` |

### 步骤2: 安装依赖（如果需要）

```bash
# 对于Node.js基础的MCP服务器，确保已安装Node.js
node --version
npm --version

# 对于Python基础的MCP服务器，确保已安装Python
python --version
pip --version
```

### 步骤3: 配置文件方式添加

编辑 `config/mcp_config.yaml` 文件：

```yaml
servers:
  # 添加Brave搜索服务器
  brave-search:
    command: npx
    args:
      - '@modelcontextprotocol/server-brave-search'
    description: Brave搜索引擎集成
    enabled: true
    env:
      BRAVE_API_KEY: "your-brave-api-key-here"
    timeout: 30
  
  # 添加文件系统服务器
  filesystem:
    command: npx
    args:
      - '@modelcontextprotocol/server-filesystem'
      - '/Users/username/Documents'  # 允许访问的目录
      - '/Users/username/Desktop'
    description: 本地文件系统操作
    enabled: true
    timeout: 30
  
  # 添加SQLite数据库服务器
  sqlite-db:
    command: npx
    args:
      - '@modelcontextprotocol/server-sqlite'
      - '/path/to/your/database.db'
    description: SQLite数据库操作
    enabled: true
    timeout: 30
  
  # 添加GitHub集成服务器
  github:
    command: npx
    args:
      - '@modelcontextprotocol/server-github'
    description: GitHub仓库集成
    enabled: true
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "your-github-token-here"
    timeout: 60
```

### 步骤4: 重新加载配置

```bash
# 方式1: 重启应用
python run.py

# 方式2: 通过API重新加载（推荐）
curl -X POST http://localhost:5000/api/mcp/v2/reload \
  -H "Content-Type: application/json"
```

### 步骤5: 验证服务器状态

```bash
# 检查MCP状态
curl http://localhost:5000/api/mcp/v2/status

# 查看所有服务器
curl http://localhost:5000/api/mcp/v2/servers

# 查看可用工具
curl http://localhost:5000/api/mcp/v2/tools
```

## 🏠 创建自定义MCP服务器

### 步骤1: 创建服务器文件

在 `app/services/mcp/servers/` 目录下创建新的服务器文件：

```python
# app/services/mcp/servers/custom_server.py
#!/usr/bin/env python3
"""
自定义MCP服务器示例
提供自定义业务逻辑的MCP工具
"""

import asyncio
import json
import sys
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)

@dataclass
class MCPRequest:
    """MCP请求数据结构"""
    jsonrpc: str
    id: Any
    method: str
    params: Dict[str, Any] = None

@dataclass
class MCPResponse:
    """MCP响应数据结构"""
    jsonrpc: str
    id: Any
    result: Any = None
    error: Dict[str, Any] = None

class CustomMCPServer:
    """自定义MCP服务器"""
    
    def __init__(self):
        self.tools = {
            "custom_hello": {
                "name": "custom_hello",
                "description": "自定义问候工具",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "要问候的人的名字"
                        }
                    },
                    "required": ["name"]
                }
            },
            "custom_calculate": {
                "name": "custom_calculate",
                "description": "自定义计算工具",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["add", "subtract", "multiply", "divide"],
                            "description": "计算操作类型"
                        },
                        "a": {
                            "type": "number",
                            "description": "第一个数字"
                        },
                        "b": {
                            "type": "number",
                            "description": "第二个数字"
                        }
                    },
                    "required": ["operation", "a", "b"]
                }
            }
        }
    
    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """处理MCP请求"""
        try:
            if request.method == "tools/list":
                return MCPResponse(
                    jsonrpc="2.0",
                    id=request.id,
                    result={
                        "tools": list(self.tools.values())
                    }
                )
            
            elif request.method == "tools/call":
                tool_name = request.params.get("name")
                arguments = request.params.get("arguments", {})
                
                if tool_name == "custom_hello":
                    result = await self._handle_hello(arguments)
                elif tool_name == "custom_calculate":
                    result = await self._handle_calculate(arguments)
                else:
                    raise ValueError(f"未知工具: {tool_name}")
                
                return MCPResponse(
                    jsonrpc="2.0",
                    id=request.id,
                    result={
                        "content": [
                            {
                                "type": "text",
                                "text": result
                            }
                        ]
                    }
                )
            
            else:
                raise ValueError(f"未知方法: {request.method}")
        
        except Exception as e:
            logger.error(f"处理请求失败: {e}")
            return MCPResponse(
                jsonrpc="2.0",
                id=request.id,
                error={
                    "code": -1,
                    "message": str(e)
                }
            )
    
    async def _handle_hello(self, arguments: Dict[str, Any]) -> str:
        """处理问候工具"""
        name = arguments.get("name", "朋友")
        return f"你好，{name}！欢迎使用自定义MCP服务器！"
    
    async def _handle_calculate(self, arguments: Dict[str, Any]) -> str:
        """处理计算工具"""
        operation = arguments.get("operation")
        a = arguments.get("a")
        b = arguments.get("b")
        
        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            if b == 0:
                return "错误：除数不能为零"
            result = a / b
        else:
            return f"错误：不支持的操作 {operation}"
        
        return f"计算结果：{a} {operation} {b} = {result}"

async def main():
    """主函数"""
    server = CustomMCPServer()
    
    # 读取标准输入并处理请求
    while True:
        try:
            line = input()
            if not line.strip():
                continue
            
            request_data = json.loads(line)
            request = MCPRequest(
                jsonrpc=request_data["jsonrpc"],
                id=request_data["id"],
                method=request_data["method"],
                params=request_data.get("params")
            )
            
            response = await server.handle_request(request)
            
            # 输出响应
            response_dict = {
                "jsonrpc": response.jsonrpc,
                "id": response.id
            }
            
            if response.result is not None:
                response_dict["result"] = response.result
            if response.error is not None:
                response_dict["error"] = response.error
            
            print(json.dumps(response_dict))
            
        except EOFError:
            break
        except Exception as e:
            logger.error(f"主循环错误: {e}")
            break

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 运行服务器
    asyncio.run(main())
```

### 步骤2: 添加配置

在 `config/mcp_config.yaml` 中添加自定义服务器：

```yaml
servers:
  custom-server:
    command: python
    args:
      - '-m'
      - 'app.services.mcp.servers.custom_server'
    description: 自定义业务逻辑服务器
    enabled: true
    working_directory: '.'
    timeout: 30
    env:
      PYTHONPATH: '.'
```

### 步骤3: 测试自定义服务器

```bash
# 直接测试服务器
python -m app.services.mcp.servers.custom_server

# 测试工具列表请求
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python -m app.services.mcp.servers.custom_server

# 测试工具调用
echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"custom_hello","arguments":{"name":"张三"}}}' | python -m app.services.mcp.servers.custom_server
```

## ⚙️ 配置文件管理

### 配置文件结构

```yaml
# config/mcp_config.yaml

client:
  # 客户端配置
  default_timeout: 30              # 默认超时时间（秒）
  max_concurrent_requests: 10      # 最大并发请求数
  retry_attempts: 3                # 重试次数
  retry_delay: 1.0                 # 重试延迟（秒）

servers:
  # 服务器配置
  server-name:
    command: npx                   # 启动命令
    args:                          # 命令参数
      - '@package/server'
      - 'arg1'
      - 'arg2'
    description: "服务器描述"       # 服务器描述
    enabled: true                  # 是否启用
    working_directory: "."         # 工作目录
    timeout: 30                    # 超时时间
    env:                          # 环境变量
      API_KEY: "your-key"
      DEBUG: "1"
```

### 配置参数说明

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `command` | string | ✅ | 启动服务器的命令 |
| `args` | array | ✅ | 命令行参数列表 |
| `description` | string | ❌ | 服务器描述信息 |
| `enabled` | boolean | ❌ | 是否启用（默认true） |
| `working_directory` | string | ❌ | 工作目录（默认当前目录） |
| `timeout` | integer | ❌ | 超时时间秒数（默认30） |
| `env` | object | ❌ | 环境变量键值对 |

## 🔧 API管理方式

### 查看系统状态

```bash
# 获取MCP系统状态
curl http://localhost:5000/api/mcp/v2/status

# 响应示例
{
  "success": true,
  "data": {
    "initialized": true,
    "server_count": 3,
    "enabled_servers": 2,
    "tool_count": 8
  }
}
```

### 管理服务器

```bash
# 获取所有服务器列表
curl http://localhost:5000/api/mcp/v2/servers

# 启用服务器
curl -X POST http://localhost:5000/api/mcp/v2/servers/server-name/enable

# 禁用服务器
curl -X POST http://localhost:5000/api/mcp/v2/servers/server-name/disable

# 添加新服务器
curl -X POST http://localhost:5000/api/mcp/v2/servers/add \
  -H "Content-Type: application/json" \
  -d '{
    "name": "new-server",
    "command": "npx",
    "args": ["@package/server"],
    "description": "新服务器",
    "enabled": true,
    "env": {
      "API_KEY": "your-key"
    }
  }'

# 删除服务器
curl -X DELETE http://localhost:5000/api/mcp/v2/servers/server-name
```

### 管理工具

```bash
# 获取所有可用工具
curl http://localhost:5000/api/mcp/v2/tools

# 搜索工具
curl "http://localhost:5000/api/mcp/v2/tools/search?q=file"

# 调用工具
curl -X POST http://localhost:5000/api/mcp/v2/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "create_file",
    "arguments": {
      "path": "/tmp/test.txt",
      "content": "Hello World"
    },
    "server_name": "filesystem"
  }'
```

### 配置管理

```bash
# 重新加载配置
curl -X POST http://localhost:5000/api/mcp/v2/reload

# 响应示例
{
  "success": true,
  "message": "MCP配置重新加载成功",
  "data": {
    "server_count": 3,
    "tool_count": 8
  }
}
```

## 🔍 故障排除

### 常见问题及解决方案

#### 1. 服务器启动失败

**问题**: 服务器状态显示为未连接
```bash
# 检查服务器状态
curl http://localhost:5000/api/mcp/v2/servers
```

**解决方案**:
```bash
# 1. 检查命令是否存在
which npx
which python

# 2. 手动测试服务器启动
npx @modelcontextprotocol/server-filesystem /tmp

# 3. 检查环境变量
echo $NODE_PATH
echo $PYTHONPATH

# 4. 查看日志
tail -f logs/app.log
```

#### 2. 工具调用失败

**问题**: 工具调用返回错误
```bash
# 测试工具调用
curl -X POST http://localhost:5000/api/mcp/v2/tools/call \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "test_tool", "arguments": {}}'
```

**解决方案**:
```bash
# 1. 检查工具是否存在
curl http://localhost:5000/api/mcp/v2/tools | grep "test_tool"

# 2. 检查参数格式
curl http://localhost:5000/api/mcp/v2/tools | jq '.data[] | select(.name=="test_tool")'

# 3. 检查服务器连接
curl http://localhost:5000/api/mcp/v2/servers | jq '.data[] | select(.enabled==true)'
```

#### 3. 配置文件错误

**问题**: 配置文件语法错误
```
yaml.scanner.ScannerError: mapping values are not allowed here
```

**解决方案**:
```bash
# 1. 验证YAML语法
python -c "import yaml; yaml.safe_load(open('config/mcp_config.yaml'))"

# 2. 使用在线YAML验证器
# 访问: https://yaml-online-parser.appspot.com/

# 3. 检查缩进和特殊字符
cat -A config/mcp_config.yaml
```

### 调试工具

```bash
# 启用调试模式
export DEBUG=1
python run.py

# 查看详细日志
tail -f logs/mcp.log

# 测试单个服务器
python -m app.services.mcp.servers.document_server
```

## 📚 最佳实践

### 1. 服务器命名规范

```yaml
# 推荐命名方式
servers:
  filesystem-home:          # 功能-范围
    description: "家目录文件操作"
  
  search-brave:             # 功能-提供商
    description: "Brave搜索引擎"
  
  db-sqlite-main:           # 类型-技术-用途
    description: "主数据库操作"
```

### 2. 环境变量管理

```yaml
# 使用环境变量文件
servers:
  github:
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"  # 从环境变量读取
    
  brave-search:
    env:
      BRAVE_API_KEY: "${BRAVE_API_KEY}"
```

```bash
# .env 文件
GITHUB_TOKEN=your_github_token_here
BRAVE_API_KEY=your_brave_api_key_here
```

### 3. 安全考虑

```yaml
# 限制文件系统访问范围
servers:
  filesystem:
    args:
      - '@modelcontextprotocol/server-filesystem'
      - '/Users/username/Documents'    # 仅允许访问特定目录
      - '/Users/username/Projects'     # 避免访问系统目录
    # 不要使用 '/' 或 '/Users'
```

### 4. 性能优化

```yaml
client:
  max_concurrent_requests: 5    # 根据系统性能调整
  default_timeout: 15           # 较短的超时时间
  retry_attempts: 2             # 减少重试次数

servers:
  heavy-server:
    timeout: 60                 # 为耗时操作设置更长超时
```

### 5. 监控和日志

```python
# 在自定义服务器中添加日志
import logging

logger = logging.getLogger(__name__)

async def _handle_tool(self, arguments):
    logger.info(f"处理工具调用: {arguments}")
    try:
        result = await self.process(arguments)
        logger.info(f"工具调用成功: {result}")
        return result
    except Exception as e:
        logger.error(f"工具调用失败: {e}")
        raise
```

## 📖 参考资源

### 官方文档
- [Model Context Protocol 官方文档](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

### 示例服务器
- [官方示例服务器](https://github.com/modelcontextprotocol/servers)
- [社区服务器列表](https://github.com/modelcontextprotocol/servers#community-servers)

### 开发工具
- [MCP Inspector](https://github.com/modelcontextprotocol/inspector) - MCP调试工具
- [YAML在线验证器](https://yaml-online-parser.appspot.com/)

---

## 🤝 支持

如果您在使用过程中遇到问题，请：

1. 查看[故障排除](#故障排除)部分
2. 检查系统日志: `logs/app.log`
3. 提交Issue并提供详细的错误信息和配置文件

---

*最后更新: 2024年12月* 