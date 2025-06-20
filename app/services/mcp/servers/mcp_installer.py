"""
MCP服务安装检查和自动安装模块
负责检查MCP服务是否已安装，如果未安装则自动安装
"""

import asyncio
import logging
import subprocess
import shutil
import os
import json
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from ..config.mcp_config import MCPConfig, MCPServerConfig

logger = logging.getLogger(__name__)

class MCPInstaller:
    """MCP服务安装器"""
    
    def __init__(self, config: MCPConfig = None):
        self.config = config or MCPConfig()
        self.installation_cache = {}  # 缓存安装状态
    
    async def check_and_install_required_services(self, tools_needed: List[str]) -> Dict[str, Any]:
        """检查并安装所需的MCP服务"""
        result = {
            "success": True,
            "installed_services": [],
            "failed_services": [],
            "skipped_services": [],
            "details": {}
        }
        
        try:
            # 根据需要的工具确定需要的服务
            required_services = self._map_tools_to_services(tools_needed)
            logger.info(f"需要的MCP服务: {required_services}")
            
            for service_name in required_services:
                service_config = self.config.get_server_config(service_name)
                if not service_config:
                    logger.warning(f"配置中未找到服务: {service_name}")
                    result["skipped_services"].append(service_name)
                    result["details"][service_name] = "配置中未找到该服务"
                    continue
                
                if not service_config.enabled:
                    logger.info(f"服务 {service_name} 已禁用，跳过安装检查")
                    result["skipped_services"].append(service_name)
                    result["details"][service_name] = "服务已禁用"
                    continue
                
                # 检查服务是否已安装
                is_installed = await self._check_service_installed(service_name, service_config)
                
                if is_installed:
                    logger.info(f"服务 {service_name} 已安装")
                    result["details"][service_name] = "已安装"
                else:
                    logger.info(f"服务 {service_name} 未安装，开始自动安装")
                    install_success = await self._install_service(service_name, service_config)
                    
                    if install_success:
                        result["installed_services"].append(service_name)
                        result["details"][service_name] = "安装成功"
                        logger.info(f"服务 {service_name} 安装成功")
                    else:
                        result["failed_services"].append(service_name)
                        result["details"][service_name] = "安装失败"
                        result["success"] = False
                        logger.error(f"服务 {service_name} 安装失败")
            
            return result
            
        except Exception as e:
            logger.error(f"检查和安装MCP服务失败: {e}")
            result["success"] = False
            result["details"]["error"] = str(e)
            return result
    
    def _map_tools_to_services(self, tools_needed: List[str]) -> List[str]:
        """将工具映射到所需的服务"""
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
        
        required_services = set()
        for tool in tools_needed:
            if tool in tool_service_mapping:
                # 优先选择内置服务
                services = tool_service_mapping[tool]
                if "document-management" in services:
                    required_services.add("document-management")
                else:
                    required_services.update(services)
        
        return list(required_services)
    
    async def _check_service_installed(self, service_name: str, service_config: MCPServerConfig) -> bool:
        """检查服务是否已安装"""
        try:
            # 检查缓存
            cache_key = f"{service_name}_{service_config.command}_{'-'.join(service_config.args)}"
            if cache_key in self.installation_cache:
                return self.installation_cache[cache_key]
            
            # 内置服务直接返回True
            if service_name == "document-management":
                self.installation_cache[cache_key] = True
                return True
            
            # 检查命令是否存在
            command_exists = await self._check_command_exists(service_config.command)
            if not command_exists:
                logger.warning(f"命令 {service_config.command} 不存在")
                self.installation_cache[cache_key] = False
                return False
            
            # 对于npm包，检查是否已安装
            if service_config.command == "npx" and service_config.args:
                package_name = service_config.args[0]
                if package_name.startswith("@"):
                    # 检查npm包是否已安装
                    is_installed = await self._check_npm_package_installed(package_name)
                    self.installation_cache[cache_key] = is_installed
                    return is_installed
            
            # 对于其他类型的服务，尝试执行帮助命令
            try:
                # 构建测试命令
                test_cmd = [service_config.command] + service_config.args + ["--help"]
                process = await asyncio.create_subprocess_exec(
                    *test_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    timeout=10
                )
                stdout, stderr = await process.communicate()
                
                # 如果命令执行成功（返回码0或1都可能是正常的）
                is_installed = process.returncode in [0, 1]
                self.installation_cache[cache_key] = is_installed
                return is_installed
                
            except asyncio.TimeoutError:
                logger.warning(f"检查服务 {service_name} 超时")
                self.installation_cache[cache_key] = False
                return False
            except Exception as e:
                logger.warning(f"检查服务 {service_name} 失败: {e}")
                self.installation_cache[cache_key] = False
                return False
                
        except Exception as e:
            logger.error(f"检查服务 {service_name} 是否安装时出错: {e}")
            return False
    
    async def _check_command_exists(self, command: str) -> bool:
        """检查命令是否存在"""
        try:
            # 使用which命令检查
            result = shutil.which(command)
            return result is not None
        except Exception:
            return False
    
    async def _check_npm_package_installed(self, package_name: str) -> bool:
        """检查npm包是否已安装"""
        try:
            # 检查全局安装
            process = await asyncio.create_subprocess_exec(
                "npm", "list", "-g", package_name, "--depth=0",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                timeout=15
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return True
            
            # 检查本地安装
            process = await asyncio.create_subprocess_exec(
                "npm", "list", package_name, "--depth=0",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                timeout=15
            )
            stdout, stderr = await process.communicate()
            
            return process.returncode == 0
            
        except Exception as e:
            logger.warning(f"检查npm包 {package_name} 失败: {e}")
            return False
    
    async def _install_service(self, service_name: str, service_config: MCPServerConfig) -> bool:
        """安装MCP服务"""
        try:
            logger.info(f"开始安装服务: {service_name}")
            
            # 内置服务不需要安装
            if service_name == "document-management":
                return True
            
            # 对于npm包，使用npm安装
            if service_config.command == "npx" and service_config.args:
                package_name = service_config.args[0]
                if package_name.startswith("@"):
                    return await self._install_npm_package(package_name)
            
            # 对于其他类型的服务，记录警告
            logger.warning(f"服务 {service_name} 需要手动安装")
            return False
            
        except Exception as e:
            logger.error(f"安装服务 {service_name} 失败: {e}")
            return False
    
    async def _install_npm_package(self, package_name: str) -> bool:
        """安装npm包"""
        try:
            logger.info(f"正在安装npm包: {package_name}")
            
            # 首先检查npm是否可用
            if not await self._check_command_exists("npm"):
                logger.error("npm命令不存在，无法安装npm包")
                return False
            
            # 全局安装npm包
            process = await asyncio.create_subprocess_exec(
                "npm", "install", "-g", package_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                timeout=300  # 5分钟超时
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"npm包 {package_name} 安装成功")
                # 清除缓存，强制重新检查
                self.installation_cache.clear()
                return True
            else:
                logger.error(f"npm包 {package_name} 安装失败: {stderr.decode()}")
                return False
                
        except asyncio.TimeoutError:
            logger.error(f"安装npm包 {package_name} 超时")
            return False
        except Exception as e:
            logger.error(f"安装npm包 {package_name} 时出错: {e}")
            return False
    
    async def check_single_service(self, service_name: str) -> Dict[str, Any]:
        """检查单个服务的安装状态"""
        try:
            service_config = self.config.get_server_config(service_name)
            if not service_config:
                return {
                    "service_name": service_name,
                    "installed": False,
                    "enabled": False,
                    "error": "配置中未找到该服务"
                }
            
            is_installed = await self._check_service_installed(service_name, service_config)
            
            return {
                "service_name": service_name,
                "installed": is_installed,
                "enabled": service_config.enabled,
                "command": service_config.command,
                "args": service_config.args,
                "description": service_config.description
            }
            
        except Exception as e:
            return {
                "service_name": service_name,
                "installed": False,
                "enabled": False,
                "error": str(e)
            }
    
    async def install_single_service(self, service_name: str) -> Dict[str, Any]:
        """安装单个服务"""
        try:
            service_config = self.config.get_server_config(service_name)
            if not service_config:
                return {
                    "service_name": service_name,
                    "success": False,
                    "message": "配置中未找到该服务"
                }
            
            # 先检查是否已安装
            is_installed = await self._check_service_installed(service_name, service_config)
            if is_installed:
                return {
                    "service_name": service_name,
                    "success": True,
                    "message": "服务已安装"
                }
            
            # 执行安装
            install_success = await self._install_service(service_name, service_config)
            
            return {
                "service_name": service_name,
                "success": install_success,
                "message": "安装成功" if install_success else "安装失败"
            }
            
        except Exception as e:
            return {
                "service_name": service_name,
                "success": False,
                "message": f"安装过程中出错: {e}"
            }
    
    def clear_cache(self):
        """清除安装状态缓存"""
        self.installation_cache.clear()
        logger.info("安装状态缓存已清除")
    
    def get_installation_requirements(self, service_name: str) -> Dict[str, Any]:
        """获取服务的安装要求"""
        service_config = self.config.get_server_config(service_name)
        if not service_config:
            return {"error": "配置中未找到该服务"}
        
        requirements = {
            "service_name": service_name,
            "command": service_config.command,
            "requirements": []
        }
        
        if service_config.command == "npx":
            requirements["requirements"].append("需要Node.js和npm环境")
            if service_config.args:
                package_name = service_config.args[0]
                requirements["requirements"].append(f"将自动安装npm包: {package_name}")
        elif service_config.command == "python":
            requirements["requirements"].append("需要Python环境")
            requirements["requirements"].append("可能需要安装相关Python包")
        elif service_config.command == "node":
            requirements["requirements"].append("需要Node.js环境")
            requirements["requirements"].append("需要手动安装相关依赖")
        else:
            requirements["requirements"].append(f"需要 {service_config.command} 命令可用")
        
        return requirements 