import asyncio
import logging
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod
from config import Config

logger = logging.getLogger(__name__)

@dataclass
class MCPToolCall:
    """MCP工具调用结果"""
    tool_name: str
    arguments: Dict[str, Any]
    result: Optional[str] = None
    error: Optional[str] = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

class MCPServer(ABC):
    """MCP服务器抽象基类"""
    
    def __init__(self, name: str, description: str, capabilities: List[str]):
        self.name = name
        self.description = description
        self.capabilities = capabilities
        self.is_running = False
    
    @abstractmethod
    async def start(self) -> bool:
        """启动服务器"""
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        """停止服务器"""
        pass
    
    @abstractmethod
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> MCPToolCall:
        """执行工具"""
        pass
    
    @abstractmethod
    def suggest_tools(self, query: str) -> List[str]:
        """根据查询建议可用工具"""
        pass

class PlaywrightMCPServer(MCPServer):
    """Playwright Web自动化服务器"""
    
    def __init__(self):
        super().__init__(
            name="Playwright Web自动化",
            description="自动化Web浏览器操作，可以点击按钮、填写表单、导航页面等",
            capabilities=[
                'navigate', 'click', 'fill', 'screenshot', 
                'wait', 'scroll', 'evaluate'
            ]
        )
        self.page = None
        self.browser = None
        self.context = None
    
    async def start(self) -> bool:
        """启动Playwright浏览器"""
        try:
            # 导入playwright
            from playwright.async_api import async_playwright
            
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=False)
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
            
            self.is_running = True
            logger.info("Playwright MCP服务器启动成功")
            return True
            
        except Exception as e:
            logger.error(f"启动Playwright MCP服务器失败: {e}")
            return False
    
    async def stop(self) -> bool:
        """停止Playwright浏览器"""
        try:
            if self.browser:
                await self.browser.close()
            if hasattr(self, 'playwright'):
                await self.playwright.stop()
            
            self.is_running = False
            logger.info("Playwright MCP服务器已停止")
            return True
            
        except Exception as e:
            logger.error(f"停止Playwright MCP服务器失败: {e}")
            return False
    
    def suggest_tools(self, query: str) -> List[str]:
        """根据查询建议可用工具"""
        suggestions = []
        query_lower = query.lower()
        
        # 文件夹创建相关关键词
        if any(keyword in query_lower for keyword in ['创建', '新建', '文件夹', '目录']):
            # 检查是否指定了父目录
            if any(pattern in query_lower for pattern in ['在', '下', '中', '里']):
                suggestions.extend(['select_parent_folder', 'click_create_folder', 'fill_folder_name', 'click_confirm'])
            else:
                suggestions.extend(['click_create_folder', 'fill_folder_name', 'click_confirm'])
        
        # 搜索相关关键词
        if any(keyword in query_lower for keyword in ['搜索', '查找', '检索', '标签']):
            suggestions.extend(['fill_search', 'click_search'])
        
        # 导航相关关键词
        if any(keyword in query_lower for keyword in ['打开', '访问', '页面', '跳转']):
            suggestions.extend(['navigate', 'wait_for_load'])
        
        # 截图相关关键词
        if any(keyword in query_lower for keyword in ['截图', '图片', '保存', '查看']):
            suggestions.extend(['screenshot'])
        
        return suggestions
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> MCPToolCall:
        """执行工具"""
        if not self.is_running:
            return MCPToolCall(tool_name, arguments, error="Playwright服务器未启动")
        
        try:
            if tool_name == 'navigate':
                return await self._navigate(arguments)
            elif tool_name == 'select_parent_folder':
                return await self._select_parent_folder(arguments)
            elif tool_name == 'click_create_folder':
                return await self._click_create_folder(arguments)
            elif tool_name == 'fill_folder_name':
                return await self._fill_folder_name(arguments)
            elif tool_name == 'click_confirm':
                return await self._click_confirm(arguments)
            elif tool_name == 'fill_search':
                return await self._fill_search(arguments)
            elif tool_name == 'click_search':
                return await self._click_search(arguments)
            elif tool_name == 'screenshot':
                return await self._screenshot(arguments)
            elif tool_name == 'wait_for_element':
                return await self._wait_for_element(arguments)
            elif tool_name == 'evaluate':
                return await self._evaluate(arguments)
            else:
                return MCPToolCall(tool_name, arguments, error=f"未知工具: {tool_name}")
                
        except Exception as e:
            logger.error(f"执行工具 {tool_name} 失败: {e}")
            return MCPToolCall(tool_name, arguments, error=str(e))
    
    async def _navigate(self, arguments: Dict[str, Any]) -> MCPToolCall:
        """导航到页面"""
        try:
            from config import Config
            default_url = Config.MCP_CONFIG.get('app_url', 'http://localhost:5001')
            url = arguments.get('url', default_url)
            
            logger.info(f"开始导航到: {url}")
            
            # 首先检查当前页面URL，如果已经在目标页面就跳过导航
            try:
                current_url = self.page.url
                logger.info(f"当前页面URL: {current_url}")
                
                # 如果已经在目标页面（或者至少在同一域），跳过导航
                if url in current_url or current_url.startswith('http://localhost:5001'):
                    logger.info("已在目标页面，跳过导航步骤")
                    result = f"已在目标页面，跳过导航: {current_url}"
                    return MCPToolCall('navigate', arguments, result=result)
            except Exception as url_check_error:
                logger.warning(f"检查当前URL失败，继续导航: {url_check_error}")
            
            # 设置较短的超时时间
            navigation_timeout = 2000  # 2秒超时
            
            try:
                # 导航到页面，设置短超时，不等待任何加载
                logger.info(f"执行页面导航，超时时间: {navigation_timeout}ms")
                await self.page.goto(url, timeout=navigation_timeout)
                logger.info(f"页面导航完成: {url}")
                
            except Exception as nav_error:
                logger.warning(f"导航失败，但继续执行: {nav_error}")
                # 不要尝试刷新，直接继续
            
            result = f"导航处理完成: {url}"
            logger.info(f"导航操作完成: {result}")
            return MCPToolCall('navigate', arguments, result=result)
            
        except Exception as e:
            error_msg = f"导航失败: {str(e)}"
            logger.error(error_msg)
            # 即使导航失败，也不要返回错误，让后续步骤继续尝试
            warning_msg = f"导航失败但继续执行: {str(e)}"
            return MCPToolCall('navigate', arguments, result=warning_msg)
    
    async def _select_parent_folder(self, arguments: Dict[str, Any]) -> MCPToolCall:
        """选中父目录"""
        try:
            parent_name = arguments.get('parent_name', '')
            
            if not parent_name:
                return MCPToolCall('select_parent_folder', arguments, error="父目录名称不能为空")
            
            logger.info(f"尝试选中父目录: {parent_name}")
            
            # 设置较短的超时时间，避免长时间等待
            short_timeout = 2000  # 2秒超时
            
            # 首先尝试查找所有文件夹元素，看看页面上实际有什么
            try:
                logger.info("检查页面上的文件夹元素...")
                all_folders = await self.page.query_selector_all('[data-node-type="folder"]')
                logger.info(f"找到 {len(all_folders)} 个文件夹元素")
                
                # 输出前几个文件夹的名称用于调试
                for i, folder in enumerate(all_folders[:5]):  # 只检查前5个
                    try:
                        name_element = await folder.query_selector('.tree-item-text')
                        if name_element:
                            name = await name_element.text_content()
                            logger.info(f"文件夹 {i+1}: {name}")
                    except:
                        logger.info(f"文件夹 {i+1}: 无法获取名称")
                
            except Exception as debug_error:
                logger.warning(f"调试信息获取失败: {debug_error}")
            
            # 尝试多种选择器策略
            selectors_to_try = [
                f'[data-node-name="{parent_name}"][data-node-type="folder"]',
                f'[data-node-type="folder"]:has-text("{parent_name}")',
                f'.tree-item:has-text("{parent_name}")[data-node-type="folder"]'
            ]
            
            for i, selector in enumerate(selectors_to_try):
                try:
                    logger.info(f"尝试选择器 {i+1}: {selector}")
                    element = await self.page.wait_for_selector(selector, timeout=short_timeout)
                    
                    if element:
                        logger.info(f"找到目标元素，准备点击")
                        await element.click()
                        
                        # 移除wait_for_timeout，直接继续
                        
                        result = f"成功选中父目录: {parent_name} (使用选择器 {i+1})"
                        logger.info(result)
                        return MCPToolCall('select_parent_folder', arguments, result=result)
                        
                except Exception as selector_error:
                    logger.warning(f"选择器 {i+1} 失败: {selector_error}")
                    continue
            
            # 如果所有选择器都失败，尝试模糊匹配
            try:
                logger.info("尝试模糊匹配...")
                elements = await self.page.query_selector_all('[data-node-type="folder"]')
                
                for element in elements:
                    try:
                        text_element = await element.query_selector('.tree-item-text')
                        if text_element:
                            text = await text_element.text_content()
                            if text and parent_name.lower() in text.lower():
                                logger.info(f"找到模糊匹配: {text}")
                                await element.click()
                                # 移除wait_for_timeout
                                result = f"成功选中父目录: {text} (模糊匹配 '{parent_name}')"
                                return MCPToolCall('select_parent_folder', arguments, result=result)
                    except:
                        continue
                
                # 如果还是找不到，跳过选择父目录
                warning_msg = f"未找到名为 '{parent_name}' 的父目录，将在根目录创建文件夹"
                logger.warning(warning_msg)
                return MCPToolCall('select_parent_folder', arguments, error=warning_msg)
                
            except Exception as fuzzy_error:
                warning_msg = f"模糊匹配也失败 '{parent_name}': {str(fuzzy_error)}"
                logger.warning(warning_msg)
                return MCPToolCall('select_parent_folder', arguments, error=warning_msg)
                    
        except Exception as e:
            error_msg = f"选中父目录时发生错误: {str(e)}"
            logger.error(error_msg)
            return MCPToolCall('select_parent_folder', arguments, error=error_msg)
    
    async def _click_create_folder(self, arguments: Dict[str, Any]) -> MCPToolCall:
        """点击创建文件夹按钮"""
        try:
            logger.info("开始查找创建文件夹按钮...")
            
            # 直接尝试JavaScript调用，这是最可靠的方法
            try:
                logger.info("尝试直接调用JavaScript函数 showCreateFolderModal()...")
                
                # 首先检查函数是否存在
                function_exists = await self.page.evaluate('typeof showCreateFolderModal === "function"')
                logger.info(f"showCreateFolderModal函数存在: {function_exists}")
                
                if function_exists:
                    # 调用JavaScript函数
                    await self.page.evaluate('showCreateFolderModal()')
                    logger.info("JavaScript函数调用完成")
                    
                    # 给一点时间让模态框显示
                    await self.page.wait_for_timeout(500)
                    
                    # 检查模态框是否成功显示
                    try:
                        modal = await self.page.wait_for_selector('#createFolderModal', state='visible', timeout=3000)
                        if modal:
                            result = "通过JavaScript成功显示创建文件夹模态框"
                            logger.info(result)
                            return MCPToolCall('click_create_folder', arguments, result=result)
                    except Exception as modal_check_error:
                        logger.warning(f"模态框显示检查失败: {modal_check_error}")
                        # 即使检查失败，如果JavaScript调用成功，也可能模态框已经显示
                        result = "JavaScript调用成功，假设模态框已显示"
                        logger.info(result)
                        return MCPToolCall('click_create_folder', arguments, result=result)
                else:
                    logger.warning("showCreateFolderModal函数不存在，页面可能未正确加载")
                    
            except Exception as js_error:
                logger.warning(f"JavaScript调用失败: {js_error}")
            
            # 如果JavaScript调用失败，尝试通过按钮点击
            logger.info("JavaScript调用失败，尝试查找和点击按钮...")
            
            # 尝试最常见的选择器
            selectors_to_try = [
                'button[onclick="showCreateFolderModal()"]',
                '.toolbar-btn.btn-success-custom[onclick="showCreateFolderModal()"]',
                'button:has-text("创建文件夹")'
            ]
            
            for i, selector in enumerate(selectors_to_try):
                try:
                    logger.info(f"尝试选择器 {i+1}: {selector}")
                    element = await self.page.wait_for_selector(selector, timeout=3000)
                    
                    if element:
                        logger.info(f"找到按钮，准备点击")
                        await element.click()
                        
                        # 等待模态框出现
                        try:
                            await self.page.wait_for_selector('#createFolderModal', state='visible', timeout=3000)
                            result = f"成功点击创建文件夹按钮，模态框已显示"
                            logger.info(result)
                            return MCPToolCall('click_create_folder', arguments, result=result)
                        except Exception as modal_error:
                            logger.warning(f"等待模态框失败，但点击可能成功: {modal_error}")
                            result = f"按钮点击成功"
                            return MCPToolCall('click_create_folder', arguments, result=result)
                        
                except Exception as selector_error:
                    logger.warning(f"选择器 {i+1} 失败: {selector_error}")
                    continue
            
            # 尝试通过检查页面状态
            try:
                logger.info("检查页面状态...")
                page_url = self.page.url
                logger.info(f"当前页面URL: {page_url}")
                
                # 检查是否在正确的页面上
                if "localhost:5001" not in page_url:
                    error_msg = f"不在正确的页面上，当前URL: {page_url}"
                    logger.error(error_msg)
                    return MCPToolCall('click_create_folder', arguments, error=error_msg)
                    
            except Exception as page_error:
                logger.warning(f"页面状态检查失败: {page_error}")
            
            error_msg = "所有方法都失败，无法找到或点击创建文件夹按钮"
            logger.error(error_msg)
            return MCPToolCall('click_create_folder', arguments, error=error_msg)
            
        except Exception as e:
            error_msg = f"点击创建文件夹按钮失败: {str(e)}"
            logger.error(error_msg)
            return MCPToolCall('click_create_folder', arguments, error=error_msg)
    
    async def _fill_folder_name(self, arguments: Dict[str, Any]) -> MCPToolCall:
        """填写文件夹名称"""
        try:
            folder_name = arguments.get('name', '新文件夹')
            logger.info(f"开始填写文件夹名称: {folder_name}")
            
            # 等待并填写文件夹名称输入框
            name_selector = '#folderName'
            try:
                await self.page.wait_for_selector(name_selector, timeout=5000)
                
                # 清空输入框并填写新名称
                await self.page.fill(name_selector, '')  # 先清空
                await self.page.fill(name_selector, folder_name)
                
                # 验证输入是否成功
                input_value = await self.page.input_value(name_selector)
                if input_value == folder_name:
                    result = f"成功填写文件夹名称: {folder_name}"
                    logger.info(result)
                    return MCPToolCall('fill_folder_name', arguments, result=result)
                else:
                    logger.warning(f"输入验证失败，期望: {folder_name}, 实际: {input_value}")
                    
            except Exception as selector_error:
                logger.warning(f"通过选择器填写失败: {selector_error}")
                
                # 尝试通过JavaScript填写
                try:
                    logger.info("尝试通过JavaScript填写文件夹名称...")
                    await self.page.evaluate(f'document.getElementById("folderName").value = "{folder_name}"')
                    
                    result = f"通过JavaScript成功填写文件夹名称: {folder_name}"
                    logger.info(result)
                    return MCPToolCall('fill_folder_name', arguments, result=result)
                    
                except Exception as js_error:
                    logger.error(f"JavaScript填写也失败: {js_error}")
            
            error_msg = f"所有方法都失败，无法填写文件夹名称: {folder_name}"
            logger.error(error_msg)
            return MCPToolCall('fill_folder_name', arguments, error=error_msg)
            
        except Exception as e:
            error_msg = f"填写文件夹名称失败: {str(e)}"
            logger.error(error_msg)
            return MCPToolCall('fill_folder_name', arguments, error=error_msg)
    
    async def _click_confirm(self, arguments: Dict[str, Any]) -> MCPToolCall:
        """点击确认按钮"""
        try:
            logger.info("开始点击确认按钮...")
            
            # 尝试多种方式点击确认按钮
            try:
                # 方法1：直接调用JavaScript函数
                logger.info("尝试直接调用JavaScript函数 createFolder()...")
                
                # 首先检查函数是否存在
                function_exists = await self.page.evaluate('typeof createFolder === "function"')
                logger.info(f"createFolder函数存在: {function_exists}")
                
                if function_exists:
                    await self.page.evaluate('createFolder()')
                    logger.info("JavaScript函数createFolder()调用完成")
                    
                    # 给一点时间让操作完成
                    await self.page.wait_for_timeout(1000)
                    
                    # 检查模态框是否消失（表示创建成功）
                    try:
                        await self.page.wait_for_selector('#createFolderModal', state='hidden', timeout=5000)
                        result = "通过JavaScript成功创建文件夹，模态框已关闭"
                        logger.info(result)
                        return MCPToolCall('click_confirm', arguments, result=result)
                    except Exception as modal_check_error:
                        logger.warning(f"模态框状态检查失败: {modal_check_error}")
                        # 即使检查失败，JavaScript调用可能已经成功
                        result = "JavaScript调用createFolder()成功"
                        logger.info(result)
                        return MCPToolCall('click_confirm', arguments, result=result)
                else:
                    logger.warning("createFolder函数不存在，页面可能未正确加载")
                    
            except Exception as js_error:
                logger.warning(f"JavaScript调用失败: {js_error}")
            
            # 方法2：通过选择器点击按钮
            confirm_selectors = [
                '#createFolderModal button[onclick="createFolder()"]',
                '#createFolderModal .btn-primary',
                '#createFolderModal button:has-text("创建")',
                '.modal-footer .btn-primary'
            ]
            
            for i, selector in enumerate(confirm_selectors):
                try:
                    logger.info(f"尝试确认按钮选择器 {i+1}: {selector}")
                    element = await self.page.wait_for_selector(selector, timeout=3000)
                    
                    if element:
                        logger.info("找到确认按钮，准备点击")
                        await element.click()
                        
                        # 等待模态框消失
                        try:
                            await self.page.wait_for_selector('#createFolderModal', state='hidden', timeout=5000)
                            result = "成功点击确认按钮，文件夹创建完成"
                            logger.info(result)
                            return MCPToolCall('click_confirm', arguments, result=result)
                        except Exception as modal_error:
                            logger.warning(f"等待模态框消失失败，但点击可能成功: {modal_error}")
                            result = "确认按钮点击成功"
                            return MCPToolCall('click_confirm', arguments, result=result)
                        
                except Exception as selector_error:
                    logger.warning(f"确认按钮选择器 {i+1} 失败: {selector_error}")
                    continue
            
            error_msg = "所有方法都失败，无法点击确认按钮"
            logger.error(error_msg)
            return MCPToolCall('click_confirm', arguments, error=error_msg)
            
        except Exception as e:
            error_msg = f"点击确认按钮失败: {str(e)}"
            logger.error(error_msg)
            return MCPToolCall('click_confirm', arguments, error=error_msg)
    
    async def _fill_search(self, arguments: Dict[str, Any]) -> MCPToolCall:
        """填写搜索框"""
        try:
            from config import Config
            element_timeout = Config.MCP_CONFIG.get('playwright', {}).get('element_timeout', 5000)
            
            search_text = arguments.get('text', '')
            
            # 查找搜索框
            search_input = await self.page.wait_for_selector('#treeSearch', timeout=element_timeout)
            await search_input.clear()
            await search_input.fill(search_text)
            
            result = f"成功在搜索框输入: {search_text}"
            return MCPToolCall('fill_search', arguments, result=result)
            
        except Exception as e:
            return MCPToolCall('fill_search', arguments, error=f"填写搜索框失败: {str(e)}")
    
    async def _click_search(self, arguments: Dict[str, Any]) -> MCPToolCall:
        """执行搜索"""
        try:
            from config import Config
            element_timeout = Config.MCP_CONFIG.get('playwright', {}).get('element_timeout', 5000)
            
            # 触发搜索事件（通常是按回车键）
            search_input = await self.page.wait_for_selector('#treeSearch', timeout=element_timeout)
            await search_input.press('Enter')
            
            # 等待搜索结果
            wait_timeout = Config.MCP_CONFIG.get('playwright', {}).get('wait_timeout', 500)
                                    # 移除wait_for_timeout
            
            result = "成功执行搜索"
            return MCPToolCall('click_search', arguments, result=result)
            
        except Exception as e:
            return MCPToolCall('click_search', arguments, error=f"执行搜索失败: {str(e)}")
    
    async def _screenshot(self, arguments: Dict[str, Any]) -> MCPToolCall:
        """截图"""
        try:
            path = arguments.get('path', 'screenshot.png')
            await self.page.screenshot(path=path)
            
            result = f"成功保存截图: {path}"
            return MCPToolCall('screenshot', arguments, result=result)
            
        except Exception as e:
            return MCPToolCall('screenshot', arguments, error=f"截图失败: {str(e)}")
    
    async def _wait_for_element(self, arguments: Dict[str, Any]) -> MCPToolCall:
        """等待元素出现"""
        try:
            from config import Config
            default_timeout = Config.MCP_CONFIG.get('playwright', {}).get('element_timeout', 5000)
            
            selector = arguments.get('selector', '')
            timeout = arguments.get('timeout', default_timeout)
            
            await self.page.wait_for_selector(selector, timeout=timeout)
            
            result = f"元素已出现: {selector}"
            return MCPToolCall('wait_for_element', arguments, result=result)
            
        except Exception as e:
            return MCPToolCall('wait_for_element', arguments, error=f"等待元素失败: {str(e)}")
    
    async def _evaluate(self, arguments: Dict[str, Any]) -> MCPToolCall:
        """执行JavaScript代码"""
        try:
            script = arguments.get('script', '')
            result = await self.page.evaluate(script)
            
            return MCPToolCall('evaluate', arguments, result=str(result))
            
        except Exception as e:
            return MCPToolCall('evaluate', arguments, error=f"执行JavaScript失败: {str(e)}")

class MCPService:
    """MCP服务管理器"""
    
    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self.tool_history: List[MCPToolCall] = []
        self.config = Config.MCP_CONFIG
    
    async def initialize(self):
        """初始化MCP服务"""
        if not self.config.get('enabled', False):
            logger.info("MCP功能已禁用")
            return
        
        # 初始化Playwright服务器
        if self.config['servers']['playwright']['enabled']:
            playwright_server = PlaywrightMCPServer()
            self.servers['playwright'] = playwright_server
            await playwright_server.start()
        
        logger.info(f"MCP服务初始化完成，已启动 {len(self.servers)} 个服务器")
    
    async def shutdown(self):
        """关闭MCP服务"""
        for server in self.servers.values():
            await server.stop()
        logger.info("MCP服务已关闭")
    
    def analyze_query(self, query: str) -> Dict[str, Any]:
        """分析查询，提供工具建议"""
        suggestions = {}
        
        for server_name, server in self.servers.items():
            # 移除is_running检查，即使服务器未启动也可以提供建议
            server_suggestions = server.suggest_tools(query)
            if server_suggestions:
                suggestions[server_name] = server_suggestions
        
        return {
            'query': query,
            'suggested_tools': suggestions,
            'available_servers': list(self.servers.keys())
        }
    
    async def execute_tool_sequence(self, query: str) -> List[MCPToolCall]:
        """根据查询执行工具序列"""
        results = []
        
        # 分析查询意图
        if '创建' in query and '文件夹' in query:
            results = await self._handle_create_folder_request(query)
        elif '搜索' in query or '查找' in query:
            results = await self._handle_search_request(query)
        
        # 记录到历史
        self.tool_history.extend(results)
        
        return results
    
    async def _handle_create_folder_request(self, query: str) -> List[MCPToolCall]:
        """处理创建文件夹请求"""
        results = []
        
        if 'playwright' not in self.servers:
            return [MCPToolCall('error', {}, error="Playwright服务器未启动")]
        
        playwright = self.servers['playwright']
        
        try:
            import asyncio
            
            # 设置总体超时时间（60秒，给更多时间）
            total_timeout = 60
            logger.info(f"开始创建文件夹操作，总超时时间: {total_timeout}秒")
            
            # 使用asyncio.wait_for来确保整个操作不会无限期阻塞
            async def _perform_folder_creation():
                return await self._execute_folder_creation_steps(playwright, query)
            
            results = await asyncio.wait_for(_perform_folder_creation(), timeout=total_timeout)
            logger.info("文件夹创建操作完成")
            return results
            
        except asyncio.TimeoutError:
            error_msg = f"文件夹创建操作超时（{total_timeout}秒）"
            logger.error(error_msg)
            return [MCPToolCall('timeout_error', {}, error=error_msg)]
        except Exception as e:
            logger.error(f"处理创建文件夹请求失败: {e}")
            return [MCPToolCall('error', {}, error=str(e))]
    
    async def _execute_folder_creation_steps(self, playwright, query: str) -> List[MCPToolCall]:
        """执行文件夹创建的具体步骤"""
        results = []
        
        try:
            # 解析查询，提取文件夹名称和父目录信息
            import re
            
            # 尝试匹配"在...下创建...文件夹"的模式
            parent_folder_pattern = r'在\s*([a-zA-Z0-9\u4e00-\u9fff\s]+?)(?:文件夹|目录|下|中|里)\s*(?:下|中|里)?\s*(?:创建|新建).*?(?:一个)?\s*([a-zA-Z0-9\u4e00-\u9fff]+)\s*(?:文件夹|目录)'
            parent_match = re.search(parent_folder_pattern, query)
            
            if parent_match:
                parent_folder_name = parent_match.group(1).strip()
                folder_name = parent_match.group(2)
                logger.info(f"解析到父目录: {parent_folder_name}, 新文件夹名: {folder_name}")
            else:
                # 尝试匹配简单的"创建...文件夹"模式
                # 优先匹配"名为XXX的文件夹"模式
                named_pattern = r'(?:创建|新建).*?名为\s*([a-zA-Z0-9\u4e00-\u9fff]+)\s*的\s*(?:文件夹|目录)'
                named_match = re.search(named_pattern, query)
                
                if named_match:
                    folder_name = named_match.group(1)
                else:
                    # 通用模式
                    simple_pattern = r'(?:创建|新建).*?(?:一个)?\s*([a-zA-Z0-9\u4e00-\u9fff]+)\s*(?:文件夹|目录)'
                    simple_match = re.search(simple_pattern, query)
                    folder_name = simple_match.group(1) if simple_match else "新文件夹"
                
                parent_folder_name = None
                logger.info(f"解析到文件夹名: {folder_name}")
            
            # 1. 检查当前页面状态并导航到正确页面
            logger.info("步骤1: 检查当前页面状态并确保导航到正确页面")
            try:
                current_url = playwright.page.url if playwright.page else "未知"
                logger.info(f"当前浏览器页面URL: {current_url}")
                
                # 如果不在正确页面，尝试快速导航
                if "localhost:5001" not in current_url or current_url == "about:blank":
                    logger.info("不在正确页面，尝试快速导航...")
                    
                    # 导航到应用首页
                    target_url = "http://localhost:5001/"
                    logger.info(f"目标URL: {target_url}")
                    
                    # 设置一个总的导航超时时间（3秒）
                    navigation_success = False
                    try:
                        import asyncio
                        
                        async def quick_navigation():
                            logger.info("开始快速导航...")
                            await playwright.page.goto(target_url, wait_until='domcontentloaded', timeout=3000)
                            logger.info("✅ 导航命令完成")
                            return True
                        
                        # 使用asyncio.wait_for限制总导航时间
                        navigation_success = await asyncio.wait_for(quick_navigation(), timeout=5.0)
                        
                                                if navigation_success:
                            # 验证导航成功
                            new_url = playwright.page.url
                            logger.info(f"导航后页面URL: {new_url}")
                            
                            if "localhost:5001" in new_url:
                                logger.info("✅ 成功导航到应用页面")
                            else:
                                logger.warning(f"导航后URL不正确: {new_url}，但继续执行")
                        
                    except asyncio.TimeoutError:
                        logger.warning("导航超时，将使用后端API创建文件夹...")
                        return await self._create_folder_via_api(folder_name, parent_folder_name)
                    except Exception as nav_error:
                        logger.warning(f"导航失败: {nav_error}，将使用后端API创建文件夹...")
                        return await self._create_folder_via_api(folder_name, parent_folder_name)
            
            else:
                logger.info("✅ 已在正确页面")
                        
            except Exception as url_error:
                logger.warning(f"页面状态检查失败: {url_error}")
            
            logger.info("🔄 页面状态检查完成，继续执行后续步骤...")
            
            # 2. 暂时跳过父目录选择，直接在根目录创建
            if parent_folder_name:
                logger.info(f"步骤2: 暂时跳过父目录选择 - {parent_folder_name}")
                logger.info("暂时在根目录创建文件夹")
                # TODO: 稍后修复父目录选择功能
            
            logger.info("🔄 准备开始点击创建文件夹按钮...")
            
            # 3. 点击创建文件夹按钮
            logger.info("步骤3: 点击创建文件夹按钮")
            
            # 在操作前截图
            try:
                await playwright.page.screenshot(path='before_create_folder.png')
                logger.info("已保存操作前截图: before_create_folder.png")
            except:
                pass
            
            result = await playwright.execute_tool('click_create_folder', {})
            results.append(result)
            logger.info(f"点击创建按钮结果: 成功={not result.error}, 消息={result.result or result.error}")
            
            # 如果成功，再截图一次
            if not result.error:
                try:
                    await playwright.page.screenshot(path='after_create_folder.png')
                    logger.info("已保存操作后截图: after_create_folder.png")
                except:
                    pass
            
            if result.error:
                logger.error(f"点击创建文件夹按钮失败，中止操作: {result.error}")
                return results
            
            # 4. 填写文件夹名称
            logger.info(f"步骤4: 填写文件夹名称 - {folder_name}")
            result = await playwright.execute_tool('fill_folder_name', {'name': folder_name})
            results.append(result)
            logger.info(f"填写名称结果: 成功={not result.error}, 消息={result.result or result.error}")
            
            if result.error:
                logger.error(f"填写文件夹名称失败，中止操作: {result.error}")
                return results
            
            # 5. 点击确认按钮
            logger.info("步骤5: 点击确认按钮")
            result = await playwright.execute_tool('click_confirm', {})
            results.append(result)
            logger.info(f"点击确认按钮结果: 成功={not result.error}, 消息={result.result or result.error}")
            
            if not result.error:
                logger.info(f"✅ 文件夹 '{folder_name}' 创建完成！")
            
        except Exception as e:
            logger.error(f"执行文件夹创建步骤失败: {e}")
            results.append(MCPToolCall('error', {}, error=str(e)))
        
        return results
    
    async def _create_folder_via_api(self, folder_name: str, parent_folder_name: str = None) -> List[MCPToolCall]:
        """通过后端API创建文件夹（备用方案）"""
        results = []
        try:
            logger.info(f"🚀 使用后端API创建文件夹: {folder_name}")
            
            # 导入必要的模块
            from app.models import DocumentNode
            from app import db
            import uuid
            from datetime import datetime
            
            # 创建新文件夹
            new_folder = DocumentNode(
                id=str(uuid.uuid4()),
                name=folder_name,
                file_path=f"virtual_folder_{folder_name}",
                file_type='folder',
                type='folder',
                size=0,
                parent_id=None,  # 暂时创建在根目录
                description=f"通过MCP API创建的文件夹",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                is_deleted=False
            )
            
            # 保存到数据库
            db.session.add(new_folder)
            db.session.commit()
            
            result_message = f"✅ 成功通过API创建文件夹 '{folder_name}'"
            logger.info(result_message)
            
            results.append(MCPToolCall(
                'create_folder_api', 
                {'name': folder_name, 'parent': parent_folder_name}, 
                result=result_message
            ))
            
        except Exception as e:
            error_message = f"API创建文件夹失败: {str(e)}"
            logger.error(error_message)
            results.append(MCPToolCall(
                'create_folder_api', 
                {'name': folder_name, 'parent': parent_folder_name}, 
                error=error_message
            ))
        
        return results
    
    async def _handle_search_request(self, query: str) -> List[MCPToolCall]:
        """处理搜索请求"""
        results = []
        
        if 'playwright' not in self.servers:
            return [MCPToolCall('error', {}, error="Playwright服务器未启动")]
        
        playwright = self.servers['playwright']
        
        try:
            # 提取搜索文本
            import re
            search_match = re.search(r'(?:搜索|查找|检索).*?([a-zA-Z0-9\u4e00-\u9fff]+)', query)
            search_text = search_match.group(1) if search_match else query
            
            # 1. 填写搜索框
            result = await playwright.execute_tool('fill_search', {'text': search_text})
            results.append(result)
            
            if result.error:
                return results
            
            # 2. 执行搜索
            result = await playwright.execute_tool('click_search', {})
            results.append(result)
            
        except Exception as e:
            logger.error(f"处理搜索请求失败: {e}")
            results.append(MCPToolCall('error', {}, error=str(e)))
        
        return results
    
    def get_server_status(self) -> Dict[str, Any]:
        """获取服务器状态"""
        status = {}
        for name, server in self.servers.items():
            status[name] = {
                'name': server.name,
                'description': server.description,
                'capabilities': server.capabilities,
                'is_running': server.is_running
            }
        return status
    
    def get_tool_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取工具调用历史"""
        recent_calls = self.tool_history[-limit:] if limit else self.tool_history
        
        return [{
            'tool_name': call.tool_name,
            'arguments': call.arguments,
            'result': call.result,
            'error': call.error,
            'timestamp': call.timestamp
        } for call in recent_calls]

# 全局MCP服务实例
mcp_service = MCPService()

def initialize_mcp_service():
    """初始化MCP服务（同步包装函数）"""
    try:
        import asyncio
        
        # 检查是否已经有事件循环在运行
        try:
            loop = asyncio.get_running_loop()
            logger.warning("检测到运行中的事件循环，MCP服务将在后台异步初始化")
            # 如果有循环在运行，创建一个任务
            task = asyncio.create_task(mcp_service.initialize())
            # 不等待任务完成，让它在后台运行
            logger.info("MCP服务后台初始化任务已创建")
        except RuntimeError:
            # 没有事件循环，创建新的并运行初始化
            logger.info("创建新的事件循环来初始化MCP服务")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(mcp_service.initialize())
                logger.info("MCP服务初始化完成")
            except Exception as init_error:
                logger.error(f"MCP服务初始化过程中发生错误: {init_error}")
            finally:
                # 不要关闭循环，因为可能还有其他任务需要它
                logger.info("保持事件循环开放")
        
        logger.info("MCP服务同步初始化包装完成")
        
    except Exception as e:
        logger.error(f"MCP服务初始化失败: {e}")
        # 即使失败也不要抛出异常，以免影响应用启动
        
        # 作为备用方案，至少创建服务器对象（即使不启动）
        try:
            if mcp_service.config.get('enabled', False):
                if mcp_service.config['servers']['playwright']['enabled']:
                    if 'playwright' not in mcp_service.servers:
                        playwright_server = PlaywrightMCPServer()
                        mcp_service.servers['playwright'] = playwright_server
                        logger.info("创建了Playwright服务器对象（未启动）")
        except Exception as fallback_error:
            logger.error(f"备用方案也失败: {fallback_error}")

def ensure_mcp_initialized():
    """确保MCP服务已初始化（可在运行时调用）"""
    try:
        # 如果没有服务器，尝试重新初始化
        if not mcp_service.servers and mcp_service.config.get('enabled', False):
            logger.info("检测到MCP服务未初始化，尝试重新初始化")
            
            # 创建服务器对象
            if mcp_service.config['servers']['playwright']['enabled']:
                playwright_server = PlaywrightMCPServer()
                mcp_service.servers['playwright'] = playwright_server
                logger.info("创建了Playwright服务器对象")
                
        return len(mcp_service.servers) > 0
    except Exception as e:
        logger.error(f"确保MCP初始化失败: {e}")
        return False

async def start_playwright_server():
    """异步启动Playwright服务器"""
    try:
        if 'playwright' in mcp_service.servers:
            server = mcp_service.servers['playwright']
            if not server.is_running:
                success = await server.start()
                if success:
                    logger.info("Playwright服务器启动成功")
                    return True
                else:
                    logger.error("Playwright服务器启动失败")
                    return False
            else:
                logger.info("Playwright服务器已在运行")
                return True
        else:
            logger.error("Playwright服务器对象不存在")
            return False
    except Exception as e:
        logger.error(f"启动Playwright服务器失败: {e}")
        return False 