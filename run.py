#!/usr/bin/env python3
"""
律师案件案宗文档管理系统启动文件
"""
import os
import logging
from dotenv import load_dotenv
from app import create_app, db

# 加载环境变量文件
load_dotenv('config.env')

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
        
        # 从配置获取主机和端口
        from config import Config
        host = Config.APP_HOST
        port = Config.APP_PORT
        
        # 启动应用
        logger.info("启动文档管理系统...")
        logger.info(f"访问地址: http://{host}:{port}")
        
        app.run(
            host=host,
            port=port,
            debug=True
        )
        
    except Exception as e:
        logger.error(f"应用启动失败: {e}")
        raise

if __name__ == '__main__':
    main() 