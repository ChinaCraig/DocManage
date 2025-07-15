"""
OCR资源监控API路由
提供OCR资源状态查询、配置管理和性能监控
"""

import logging
from flask import Blueprint, jsonify, request
from app.services.ocr_resource_manager import get_ocr_manager, shutdown_ocr_manager
from app.services.ocr_config_manager import get_ocr_config_manager
from app.services.enhanced_image_recognition_service import get_enhanced_image_service

logger = logging.getLogger(__name__)

# 创建蓝图
ocr_monitor_bp = Blueprint('ocr_monitor', __name__, url_prefix='/api/ocr')

@ocr_monitor_bp.route('/status', methods=['GET'])
def get_ocr_status():
    """获取OCR服务状态"""
    try:
        # 获取OCR管理器状态
        ocr_manager = get_ocr_manager()
        resource_stats = ocr_manager.get_resource_stats()
        
        # 获取配置管理器状态
        config_manager = get_ocr_config_manager()
        config_info = {
            'document_limits': config_manager.get_document_limits(),
            'engine_config': config_manager.get_engine_config(),
            'performance_config': config_manager.get_performance_config()
        }
        
        # 获取增强图像识别服务状态
        try:
            enhanced_service = get_enhanced_image_service()
            service_stats = enhanced_service.get_resource_stats()
            available_engines = enhanced_service.get_available_engines()
        except Exception as e:
            logger.warning(f"获取增强图像识别服务状态失败: {e}")
            service_stats = {'error': str(e)}
            available_engines = []
        
        return jsonify({
            'success': True,
            'data': {
                'resource_stats': resource_stats,
                'config_info': config_info,
                'service_stats': service_stats,
                'available_engines': available_engines,
                'service_status': 'running'
            }
        })
        
    except Exception as e:
        logger.error(f"获取OCR状态失败: {e}")
        return jsonify({
            'success': False,
            'error': f'获取OCR状态失败: {str(e)}'
        }), 500

@ocr_monitor_bp.route('/config', methods=['GET'])
def get_ocr_config():
    """获取OCR配置"""
    try:
        config_manager = get_ocr_config_manager()
        full_config = config_manager.get_full_config()
        
        return jsonify({
            'success': True,
            'data': {
                'config': full_config,
                'config_source': 'unified_manager'
            }
        })
        
    except Exception as e:
        logger.error(f"获取OCR配置失败: {e}")
        return jsonify({
            'success': False,
            'error': f'获取OCR配置失败: {str(e)}'
        }), 500

@ocr_monitor_bp.route('/config', methods=['POST'])
def update_ocr_config():
    """更新OCR配置"""
    try:
        config_manager = get_ocr_config_manager()
        new_config = request.get_json()
        
        if not new_config:
            return jsonify({
                'success': False,
                'error': '配置数据不能为空'
            }), 400
        
        # 更新配置
        config_manager.update_config(new_config)
        
        # 保存配置到文件
        save_to_file = request.args.get('save', 'false').lower() == 'true'
        if save_to_file:
            config_manager.save_config_to_file()
        
        return jsonify({
            'success': True,
            'message': '配置更新成功',
            'saved_to_file': save_to_file
        })
        
    except Exception as e:
        logger.error(f"更新OCR配置失败: {e}")
        return jsonify({
            'success': False,
            'error': f'更新OCR配置失败: {str(e)}'
        }), 500

@ocr_monitor_bp.route('/optimize', methods=['POST'])
def optimize_ocr_resources():
    """优化OCR资源"""
    try:
        # 优化OCR管理器资源
        ocr_manager = get_ocr_manager()
        ocr_manager.optimize_memory()
        
        # 优化增强图像识别服务资源
        try:
            enhanced_service = get_enhanced_image_service()
            enhanced_service.optimize_resources()
        except Exception as e:
            logger.warning(f"优化增强图像识别服务失败: {e}")
        
        return jsonify({
            'success': True,
            'message': 'OCR资源优化完成'
        })
        
    except Exception as e:
        logger.error(f"OCR资源优化失败: {e}")
        return jsonify({
            'success': False,
            'error': f'OCR资源优化失败: {str(e)}'
        }), 500

@ocr_monitor_bp.route('/engines', methods=['GET'])
def get_ocr_engines_info():
    """获取OCR引擎信息"""
    try:
        enhanced_service = get_enhanced_image_service()
        available_engines = enhanced_service.get_available_engines()
        
        # 获取每个引擎的详细信息
        engines_info = {}
        for engine in available_engines:
            engines_info[engine] = {
                'available': True,
                'status': 'ready'
            }
        
        # 获取引擎配置
        config_manager = get_ocr_config_manager()
        engine_config = config_manager.get_engine_config()
        
        return jsonify({
            'success': True,
            'data': {
                'available_engines': available_engines,
                'engines_info': engines_info,
                'engine_config': engine_config
            }
        })
        
    except Exception as e:
        logger.error(f"获取OCR引擎信息失败: {e}")
        return jsonify({
            'success': False,
            'error': f'获取OCR引擎信息失败: {str(e)}'
        }), 500

@ocr_monitor_bp.route('/stats/reset', methods=['POST'])
def reset_ocr_stats():
    """重置OCR统计信息"""
    try:
        ocr_manager = get_ocr_manager()
        # 重置统计信息
        ocr_manager._task_stats = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'timeout_tasks': 0,
            'memory_errors': 0
        }
        
        return jsonify({
            'success': True,
            'message': 'OCR统计信息已重置'
        })
        
    except Exception as e:
        logger.error(f"重置OCR统计失败: {e}")
        return jsonify({
            'success': False,
            'error': f'重置OCR统计失败: {str(e)}'
        }), 500

@ocr_monitor_bp.route('/health', methods=['GET'])
def check_ocr_health():
    """检查OCR服务健康状态"""
    try:
        health_status = {
            'overall': 'healthy',
            'components': {}
        }
        
        # 检查OCR管理器
        try:
            ocr_manager = get_ocr_manager()
            stats = ocr_manager.get_resource_stats()
            
            # 判断健康状态
            if stats.get('memory_usage_percent', 0) > 90:
                health_status['components']['ocr_manager'] = 'warning'
                health_status['overall'] = 'warning'
            else:
                health_status['components']['ocr_manager'] = 'healthy'
                
        except Exception as e:
            health_status['components']['ocr_manager'] = 'error'
            health_status['overall'] = 'error'
            logger.error(f"OCR管理器健康检查失败: {e}")
        
        # 检查增强图像识别服务
        try:
            enhanced_service = get_enhanced_image_service()
            engines = enhanced_service.get_available_engines()
            
            if not engines:
                health_status['components']['image_service'] = 'warning'
                health_status['overall'] = 'warning'
            else:
                health_status['components']['image_service'] = 'healthy'
                
        except Exception as e:
            health_status['components']['image_service'] = 'error'
            health_status['overall'] = 'error'
            logger.error(f"图像识别服务健康检查失败: {e}")
        
        # 检查配置管理器
        try:
            config_manager = get_ocr_config_manager()
            config_manager.get_full_config()
            health_status['components']['config_manager'] = 'healthy'
        except Exception as e:
            health_status['components']['config_manager'] = 'error'
            health_status['overall'] = 'error'
            logger.error(f"配置管理器健康检查失败: {e}")
        
        return jsonify({
            'success': True,
            'data': health_status
        })
        
    except Exception as e:
        logger.error(f"OCR健康检查失败: {e}")
        return jsonify({
            'success': False,
            'error': f'OCR健康检查失败: {str(e)}'
        }), 500

@ocr_monitor_bp.route('/shutdown', methods=['POST'])
def shutdown_ocr_service():
    """关闭OCR服务"""
    try:
        # 关闭OCR管理器
        shutdown_ocr_manager()
        
        return jsonify({
            'success': True,
            'message': 'OCR服务已关闭'
        })
        
    except Exception as e:
        logger.error(f"关闭OCR服务失败: {e}")
        return jsonify({
            'success': False,
            'error': f'关闭OCR服务失败: {str(e)}'
        }), 500 