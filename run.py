#!/usr/bin/env python3
"""
律师案件案宗文档管理系统启动文件
"""
import os
import logging
from app import create_app, db

def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('app.log'),
            logging.StreamHandler()
        ]
    )

def main():
    """主函数"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # 创建Flask应用
        app = create_app()
        
        # 启动应用
        logger.info("启动文档管理系统...")
        logger.info("访问地址: http://0.0.0.0:5001")
        
        app.run(
            host='0.0.0.0',
            port=5001,
            debug=True
        )
        
    except Exception as e:
        logger.error(f"应用启动失败: {e}")
        raise

if __name__ == '__main__':
    main() 