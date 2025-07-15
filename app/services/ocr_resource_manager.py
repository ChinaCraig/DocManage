"""
OCR资源管理器
提供OCR操作的资源控制、并发管理、超时控制和异常处理
"""

import logging
import threading
import time
import os
import psutil
import gc
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from contextlib import contextmanager
import signal

logger = logging.getLogger(__name__)

@dataclass
class OCRResourceConfig:
    """OCR资源配置"""
    max_concurrent_tasks: int = 2  # 最大并发OCR任务数
    single_task_timeout: int = 30  # 单个OCR任务超时时间（秒）
    max_memory_usage_mb: int = 2048  # 最大内存使用（MB）
    max_images_per_document: int = 50  # 每个文档最大处理图片数
    memory_check_interval: int = 5  # 内存检查间隔（秒）
    enable_resource_monitoring: bool = True  # 是否启用资源监控

class OCRResourceManager:
    """OCR资源管理器"""
    
    def __init__(self, config: OCRResourceConfig = None):
        """初始化OCR资源管理器"""
        self.config = config or OCRResourceConfig()
        self._lock = threading.Lock()
        self._active_tasks = 0
        self._executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_tasks)
        self._memory_monitor_thread = None
        self._stop_monitoring = threading.Event()
        self._task_stats = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'timeout_tasks': 0,
            'memory_errors': 0
        }
        
        # 启动资源监控
        if self.config.enable_resource_monitoring:
            self._start_memory_monitoring()
    
    def _start_memory_monitoring(self):
        """启动内存监控线程"""
        def monitor_memory():
            while not self._stop_monitoring.wait(self.config.memory_check_interval):
                try:
                    current_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
                    if current_memory > self.config.max_memory_usage_mb:
                        logger.warning(f"🔥 内存使用过高: {current_memory:.1f}MB > {self.config.max_memory_usage_mb}MB")
                        # 强制垃圾回收
                        gc.collect()
                        logger.info("🗑️ 已执行垃圾回收")
                except Exception as e:
                    logger.error(f"内存监控失败: {e}")
        
        self._memory_monitor_thread = threading.Thread(target=monitor_memory, daemon=True)
        self._memory_monitor_thread.start()
        logger.info("✅ OCR资源监控已启动")
    
    @contextmanager
    def acquire_task_slot(self):
        """获取任务槽位"""
        acquired = False
        try:
            with self._lock:
                if self._active_tasks >= self.config.max_concurrent_tasks:
                    raise ResourceWarning(f"OCR并发任务数已达上限: {self.config.max_concurrent_tasks}")
                self._active_tasks += 1
                acquired = True
                logger.debug(f"🎯 获取OCR任务槽位，当前活跃任务: {self._active_tasks}")
            
            yield
            
        finally:
            if acquired:
                with self._lock:
                    self._active_tasks -= 1
                    logger.debug(f"🔓 释放OCR任务槽位，当前活跃任务: {self._active_tasks}")
    
    def check_memory_available(self) -> bool:
        """检查内存是否可用"""
        try:
            current_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            available = current_memory < self.config.max_memory_usage_mb * 0.8  # 80%阈值
            if not available:
                logger.warning(f"⚠️ 内存不足，当前使用: {current_memory:.1f}MB")
            return available
        except Exception as e:
            logger.error(f"内存检查失败: {e}")
            return True  # 检查失败时假设可用
    
    def execute_ocr_with_control(self, 
                                ocr_func: Callable, 
                                *args, 
                                task_name: str = "OCR任务",
                                **kwargs) -> Dict[str, Any]:
        """
        执行带资源控制的OCR任务
        
        Args:
            ocr_func: OCR函数
            *args: OCR函数参数
            task_name: 任务名称
            **kwargs: OCR函数关键字参数
            
        Returns:
            OCR结果
        """
        start_time = time.time()
        self._task_stats['total_tasks'] += 1
        
        try:
            # 检查内存可用性
            if not self.check_memory_available():
                self._task_stats['memory_errors'] += 1
                return {
                    'success': False,
                    'error': '内存不足，跳过OCR任务',
                    'error_type': 'memory_limit'
                }
            
            # 获取任务槽位
            with self.acquire_task_slot():
                logger.info(f"🚀 开始执行{task_name}")
                
                # 使用线程池执行OCR任务
                future = self._executor.submit(self._safe_ocr_wrapper, ocr_func, *args, **kwargs)
                
                try:
                    # 等待任务完成，设置超时
                    result = future.result(timeout=self.config.single_task_timeout)
                    
                    elapsed_time = time.time() - start_time
                    logger.info(f"✅ {task_name}完成，耗时: {elapsed_time:.2f}秒")
                    
                    if result.get('success'):
                        self._task_stats['successful_tasks'] += 1
                    else:
                        self._task_stats['failed_tasks'] += 1
                    
                    return result
                    
                except TimeoutError:
                    logger.error(f"⏰ {task_name}超时（{self.config.single_task_timeout}秒）")
                    future.cancel()
                    self._task_stats['timeout_tasks'] += 1
                    return {
                        'success': False,
                        'error': f'{task_name}执行超时',
                        'error_type': 'timeout'
                    }
                    
        except ResourceWarning as e:
            logger.warning(f"📊 {task_name}资源限制: {e}")
            self._task_stats['failed_tasks'] += 1
            return {
                'success': False,
                'error': str(e),
                'error_type': 'resource_limit'
            }
            
        except Exception as e:
            logger.error(f"❌ {task_name}执行失败: {e}")
            self._task_stats['failed_tasks'] += 1
            return {
                'success': False,
                'error': f'{task_name}执行失败: {str(e)}',
                'error_type': 'execution_error'
            }
    
    def _safe_ocr_wrapper(self, ocr_func: Callable, *args, **kwargs) -> Dict[str, Any]:
        """安全的OCR包装器"""
        try:
            # 设置信号处理器以防止进程卡死
            original_handler = signal.signal(signal.SIGALRM, self._timeout_handler)
            signal.alarm(self.config.single_task_timeout)
            
            try:
                result = ocr_func(*args, **kwargs)
                return result if isinstance(result, dict) else {'success': True, 'result': result}
                
            finally:
                # 恢复原始信号处理器
                signal.alarm(0)
                signal.signal(signal.SIGALRM, original_handler)
                
        except Exception as e:
            logger.error(f"OCR包装器执行失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': 'wrapper_error'
            }
    
    def _timeout_handler(self, signum, frame):
        """超时信号处理器"""
        raise TimeoutError("OCR任务超时")
    
    def execute_batch_ocr(self, 
                         ocr_tasks: List[Dict[str, Any]], 
                         max_images: int = None) -> List[Dict[str, Any]]:
        """
        批量执行OCR任务，带资源控制
        
        Args:
            ocr_tasks: OCR任务列表，每个任务包含func, args, kwargs, name
            max_images: 最大处理图片数量限制
            
        Returns:
            结果列表
        """
        max_images = max_images or self.config.max_images_per_document
        
        # 限制处理的图片数量
        limited_tasks = ocr_tasks[:max_images]
        if len(ocr_tasks) > max_images:
            logger.warning(f"⚠️ 图片数量过多，限制处理前{max_images}张图片（共{len(ocr_tasks)}张）")
        
        results = []
        successful_count = 0
        failed_count = 0
        
        logger.info(f"📋 开始批量OCR处理，共{len(limited_tasks)}个任务")
        
        # 使用线程池批量处理
        futures = []
        for i, task in enumerate(limited_tasks):
            future = self._executor.submit(
                self.execute_ocr_with_control,
                task['func'],
                *task.get('args', []),
                task_name=task.get('name', f'批量OCR任务{i+1}'),
                **task.get('kwargs', {})
            )
            futures.append(future)
        
        # 收集结果
        for i, future in enumerate(as_completed(futures, timeout=len(limited_tasks) * self.config.single_task_timeout)):
            try:
                result = future.result()
                results.append(result)
                
                if result.get('success'):
                    successful_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"批量OCR任务{i+1}失败: {e}")
                results.append({
                    'success': False,
                    'error': str(e),
                    'error_type': 'batch_error'
                })
                failed_count += 1
        
        logger.info(f"📊 批量OCR完成: 成功{successful_count}, 失败{failed_count}")
        return results
    
    def get_resource_stats(self) -> Dict[str, Any]:
        """获取资源使用统计"""
        try:
            current_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            cpu_percent = psutil.cpu_percent()
            
            return {
                'active_tasks': self._active_tasks,
                'max_concurrent_tasks': self.config.max_concurrent_tasks,
                'current_memory_mb': round(current_memory, 2),
                'max_memory_mb': self.config.max_memory_usage_mb,
                'memory_usage_percent': round((current_memory / self.config.max_memory_usage_mb) * 100, 2),
                'cpu_percent': cpu_percent,
                'task_stats': self._task_stats.copy()
            }
        except Exception as e:
            logger.error(f"获取资源统计失败: {e}")
            return {'error': str(e)}
    
    def optimize_memory(self):
        """优化内存使用"""
        try:
            logger.info("🧹 开始内存优化...")
            
            # 强制垃圾回收
            collected = gc.collect()
            
            # 获取当前内存使用
            current_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            logger.info(f"🧹 内存优化完成，回收对象: {collected}, 当前内存: {current_memory:.1f}MB")
            
        except Exception as e:
            logger.error(f"内存优化失败: {e}")
    
    def shutdown(self):
        """关闭资源管理器"""
        logger.info("🛑 关闭OCR资源管理器...")
        
        # 停止监控
        self._stop_monitoring.set()
        if self._memory_monitor_thread:
            self._memory_monitor_thread.join(timeout=5)
        
        # 关闭线程池
        self._executor.shutdown(wait=True, timeout=30)
        
        # 清理内存
        self.optimize_memory()
        
        logger.info("✅ OCR资源管理器已关闭")

# 全局OCR资源管理器实例
_global_ocr_manager = None
_manager_lock = threading.Lock()

def get_ocr_manager(config: OCRResourceConfig = None) -> OCRResourceManager:
    """获取全局OCR资源管理器实例"""
    global _global_ocr_manager
    
    with _manager_lock:
        if _global_ocr_manager is None:
            _global_ocr_manager = OCRResourceManager(config)
            logger.info("🎛️ 创建全局OCR资源管理器")
        return _global_ocr_manager

def shutdown_ocr_manager():
    """关闭全局OCR资源管理器"""
    global _global_ocr_manager
    
    with _manager_lock:
        if _global_ocr_manager:
            _global_ocr_manager.shutdown()
            _global_ocr_manager = None 