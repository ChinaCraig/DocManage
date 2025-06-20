"""
MCP配置管理器
支持动态加载和管理多个MCP服务器配置
"""

import json
import yaml
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class MCPServerConfig:
    """MCP服务器配置"""
    name: str
    command: str
    args: List[str]
    description: str = ""
    enabled: bool = True
    env: Dict[str, str] = None
    working_directory: str = None
    timeout: int = 30
    
    def __post_init__(self):
        if self.env is None:
            self.env = {}

@dataclass
class MCPClientConfig:
    """MCP客户端配置"""
    max_concurrent_requests: int = 10
    default_timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0

class MCPConfig:
    """MCP配置管理器"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or self._get_default_config_path()
        self.servers: Dict[str, MCPServerConfig] = {}
        self.client_config = MCPClientConfig()
        self.load_config()
    
    def _get_default_config_path(self) -> str:
        """获取默认配置文件路径"""
        return str(Path(__file__).parent.parent.parent.parent.parent / "config" / "mcp_config.yaml")
    
    def load_config(self) -> None:
        """加载配置文件"""
        try:
            config_file = Path(self.config_path)
            if not config_file.exists():
                logger.warning(f"MCP配置文件不存在: {self.config_path}，将创建默认配置")
                self._create_default_config()
                return
            
            with open(config_file, 'r', encoding='utf-8') as f:
                if config_file.suffix.lower() == '.yaml' or config_file.suffix.lower() == '.yml':
                    config_data = yaml.safe_load(f)
                else:
                    config_data = json.load(f)
            
            # 解析服务器配置
            servers_data = config_data.get('servers', {})
            for server_name, server_config in servers_data.items():
                self.servers[server_name] = MCPServerConfig(
                    name=server_name,
                    **server_config
                )
            
            # 解析客户端配置
            client_data = config_data.get('client', {})
            if client_data:
                self.client_config = MCPClientConfig(**client_data)
            
            logger.info(f"成功加载MCP配置，包含 {len(self.servers)} 个服务器")
            
        except Exception as e:
            logger.error(f"加载MCP配置失败: {e}")
            self._create_default_config()
    
    def _create_default_config(self) -> None:
        """创建默认配置文件"""
        default_config = {
            "client": {
                "max_concurrent_requests": 10,
                "default_timeout": 30,
                "retry_attempts": 3,
                "retry_delay": 1.0
            },
            "servers": {
                "filesystem": {
                    "command": "npx",
                    "args": ["@modelcontextprotocol/server-filesystem", "/tmp"],
                    "description": "本地文件系统操作",
                    "enabled": False
                },
                "brave-search": {
                    "command": "npx",
                    "args": ["@modelcontextprotocol/server-brave-search"],
                    "description": "Brave搜索引擎",
                    "enabled": False,
                    "env": {
                        "BRAVE_API_KEY": "your-api-key-here"
                    }
                },
                "sqlite": {
                    "command": "npx", 
                    "args": ["@modelcontextprotocol/server-sqlite", "/path/to/database.db"],
                    "description": "SQLite数据库操作",
                    "enabled": False
                },
                "puppeteer": {
                    "command": "node",
                    "args": ["/path/to/puppeteer-mcp-server/build/index.js"],
                    "description": "浏览器自动化操作",
                    "enabled": False
                },
                "document-management": {
                    "command": "python",
                    "args": ["-m", "app.services.mcp.servers.document_server"],
                    "description": "内置文档管理服务器",
                    "enabled": True,
                    "working_directory": "."
                }
            }
        }
        
        try:
            config_file = Path(self.config_path)
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"已创建默认MCP配置文件: {self.config_path}")
            
            # 重新加载配置
            self.load_config()
            
        except Exception as e:
            logger.error(f"创建默认配置文件失败: {e}")
    
    def get_enabled_servers(self) -> Dict[str, MCPServerConfig]:
        """获取已启用的服务器配置"""
        return {name: config for name, config in self.servers.items() if config.enabled}
    
    def get_server_config(self, server_name: str) -> Optional[MCPServerConfig]:
        """获取指定服务器配置"""
        return self.servers.get(server_name)
    
    def add_server(self, server_config: MCPServerConfig) -> None:
        """添加服务器配置"""
        self.servers[server_config.name] = server_config
        self.save_config()
    
    def remove_server(self, server_name: str) -> bool:
        """移除服务器配置"""
        if server_name in self.servers:
            del self.servers[server_name]
            self.save_config()
            return True
        return False
    
    def enable_server(self, server_name: str) -> bool:
        """启用服务器"""
        if server_name in self.servers:
            self.servers[server_name].enabled = True
            self.save_config()
            return True
        return False
    
    def disable_server(self, server_name: str) -> bool:
        """禁用服务器"""
        if server_name in self.servers:
            self.servers[server_name].enabled = False
            self.save_config()
            return True
        return False
    
    def save_config(self) -> None:
        """保存配置到文件"""
        try:
            config_data = {
                "client": asdict(self.client_config),
                "servers": {}
            }
            
            for server_name, server_config in self.servers.items():
                config_data["servers"][server_name] = asdict(server_config)
                # 移除name字段，因为它是key
                del config_data["servers"][server_name]["name"]
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
            
            logger.info("MCP配置已保存")
            
        except Exception as e:
            logger.error(f"保存MCP配置失败: {e}")
    
    def reload_config(self) -> None:
        """重新加载配置"""
        self.servers.clear()
        self.load_config()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "client": asdict(self.client_config),
            "servers": {name: asdict(config) for name, config in self.servers.items()}
        } 