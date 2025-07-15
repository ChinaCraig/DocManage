#!/usr/bin/env python3
"""
智能文档启动文件
"""
import os
import logging
import warnings
from dotenv import load_dotenv
from app import create_app, db

# 加载环境变量文件
load_dotenv('config.env')

def setup_environment():
    """设置环境变量和警告抑制"""
    # 抑制PIL图像警告
    warnings.filterwarnings('ignore', category=UserWarning, module='PIL')
    warnings.filterwarnings('ignore', message='.*iCCP.*')
    
    # 设置torch环境变量以避免警告
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    
    # 检查是否有GPU，没有的话设置相应环境变量
    try:
        import torch
        if not torch.cuda.is_available():
            os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:128'
    except ImportError:
        pass

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
    # 设置环境变量和警告抑制
    setup_environment()
    
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
        logger.info("启动智能文档...")
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