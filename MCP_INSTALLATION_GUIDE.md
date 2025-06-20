# MCP服务安装检查和自动安装指南

## 概述

本项目现在支持自动检查和安装MCP服务，确保在执行MCP工具之前，所需的服务已经正确安装和配置。

## 核心功能

### 1. 自动服务检查
- 根据用户请求的工具，自动确定需要的MCP服务
- 检查配置文件中是否已添加相应服务
- 验证服务是否已正确安装

### 2. 自动服务安装
- 支持npm包的自动全局安装
- 智能识别不同类型的服务依赖
- 提供详细的安装状态反馈

### 3. 完整的处理流程
按照您要求的思路实现：
1. **意图识别** → 分析出需要MCP操作
2. **工具分析** → 确定需要哪些具体工具
3. **服务检查** → 检查配置文件中是否添加了相应MCP服务
4. **安装检查** → 验证服务是否已安装
5. **自动安装** → 如果未安装则自动安装
6. **工具执行** → 执行具体的MCP工具

## 技术实现

### 核心模块

#### 1. MCPInstaller (`app/services/mcp/servers/mcp_installer.py`)
- **功能**: 负责检查和安装MCP服务
- **支持的服务类型**:
  - npm包服务 (如 `@modelcontextprotocol/server-filesystem`)
  - Python服务 (如内置的 `document-management`)
  - Node.js服务 (如 `puppeteer`)

#### 2. 工具到服务的映射
```python
tool_service_mapping = {
    "create_file": ["filesystem", "document-management"],
    "create_folder": ["filesystem", "document-management"],
    "read_file": ["filesystem", "document-management"],
    "write_file": ["filesystem", "document-management"],
    "delete_file": ["filesystem", "document-management"],
    "list_directory": ["filesystem", "document-management"],
    "search_web": ["brave-search"],
    "query_database": ["sqlite"],
    "browser_automation": ["puppeteer"],
    "web_scraping": ["puppeteer"]
}
```

#### 3. 集成到工具执行器
`MCPToolExecutor` 现在会在执行工具前自动：
1. 检查所需服务
2. 安装缺失的服务
3. 报告安装状态
4. 执行工具

### API端点

#### 检查服务安装状态
```http
POST /api/mcp/v2/installation/check
Content-Type: application/json

{
    "tools_needed": ["create_file", "create_folder"]
}
```

#### 检查单个服务
```http
GET /api/mcp/v2/installation/service/filesystem/check
```

#### 安装单个服务
```http
POST /api/mcp/v2/installation/service/filesystem/install
```

#### 获取服务安装要求
```http
GET /api/mcp/v2/installation/service/filesystem/requirements
```

#### 清除安装缓存
```http
POST /api/mcp/v2/installation/cache/clear
```

## 使用示例

### 1. 用户请求创建文件
```
用户: "帮我创建一个名为test.txt的文件"
```

**系统处理流程:**
1. 意图识别 → `mcp_action`
2. 工具分析 → 需要 `create_file` 工具
3. 服务映射 → 需要 `document-management` 或 `filesystem` 服务
4. 检查配置 → `document-management` 已启用
5. 检查安装 → `document-management` 已安装 (内置服务)
6. 执行工具 → 创建文件成功

### 2. 用户请求网页搜索
```
用户: "帮我搜索一下最新的AI新闻"
```

**系统处理流程:**
1. 意图识别 → `mcp_action`
2. 工具分析 → 需要 `search_web` 工具
3. 服务映射 → 需要 `brave-search` 服务
4. 检查配置 → `brave-search` 已配置但未启用
5. 跳过安装 → 服务已禁用
6. 返回错误 → 提示用户启用服务

### 3. 启用并安装新服务
```http
# 1. 启用服务
POST /api/mcp/v2/servers/brave-search/enable

# 2. 检查安装状态
GET /api/mcp/v2/installation/service/brave-search/check

# 3. 如果未安装，自动安装
POST /api/mcp/v2/installation/service/brave-search/install
```

## 支持的服务类型

### 1. npm包服务
- **检查方式**: `npm list -g <package-name>`
- **安装方式**: `npm install -g <package-name>`
- **示例**: `@modelcontextprotocol/server-filesystem`

### 2. Python服务
- **检查方式**: 验证Python模块是否存在
- **安装方式**: 通常不需要额外安装
- **示例**: 内置的 `document-management` 服务

### 3. Node.js服务
- **检查方式**: 尝试执行 `--help` 命令
- **安装方式**: 需要手动安装依赖
- **示例**: `puppeteer` 服务

## 配置管理

### 配置文件结构 (`config/mcp_config.yaml`)
```yaml
servers:
  filesystem:
    command: npx
    args: ["@modelcontextprotocol/server-filesystem", "/tmp"]
    description: "本地文件系统操作"
    enabled: false
    
  brave-search:
    command: npx
    args: ["@modelcontextprotocol/server-brave-search"]
    description: "Brave搜索引擎"
    enabled: false
    env:
      BRAVE_API_KEY: "your-api-key-here"
      
  document-management:
    command: python
    args: ["-m", "app.services.mcp.servers.document_server"]
    description: "内置文档管理服务器"
    enabled: true
    working_directory: "."
```

### 重要原则
1. **配置驱动**: 所有MCP服务都从配置文件获取，不在代码中硬编码
2. **按需安装**: 只有在实际需要时才检查和安装服务
3. **优先级选择**: 优先使用内置服务，然后是第三方服务
4. **错误处理**: 安装失败时提供清晰的错误信息

## 系统要求

### 基础环境
- Python 3.8+
- Node.js 16+ (用于npm包服务)
- npm (用于包管理)

### 可选依赖
- 特定MCP服务可能需要额外的系统依赖
- 某些服务需要API密钥或配置

## 故障排除

### 常见问题

#### 1. npm包安装失败
```
错误: npm包 @modelcontextprotocol/server-filesystem 安装失败
解决: 检查网络连接和npm配置
```

#### 2. 服务启动失败
```
错误: 服务 filesystem 检查失败
解决: 确保npm包已正确安装，检查参数配置
```

#### 3. 权限问题
```
错误: npm命令不存在，无法安装npm包
解决: 确保Node.js和npm已正确安装
```

### 调试命令
```bash
# 检查系统环境
which npm
which node
which npx

# 检查npm全局包
npm list -g --depth=0

# 手动测试MCP服务
npx @modelcontextprotocol/server-filesystem --help
```

## 最佳实践

1. **预先配置**: 在配置文件中添加常用的MCP服务
2. **按需启用**: 只启用实际需要的服务
3. **定期清理**: 使用缓存清理API清除过期的安装状态
4. **监控日志**: 关注安装和执行日志，及时发现问题
5. **备份配置**: 定期备份MCP配置文件

## 总结

现在系统完全按照您的要求实现了：
- ✅ 从配置文件获取所有MCP服务信息
- ✅ 在执行前检查服务是否已添加到配置
- ✅ 验证服务是否已安装
- ✅ 自动安装缺失的服务
- ✅ 提供完整的API管理接口
- ✅ 集成到现有的工具执行流程

这确保了MCP功能的稳定性和可维护性，同时提供了良好的用户体验。 