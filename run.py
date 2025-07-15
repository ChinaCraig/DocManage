#!/usr/bin/env python3
"""
智能文档启动文件
"""
import os
import logging
import warnings
from dotenv import load_dotenv

# 在导入任何其他模块之前配置torch环境
try:
    from app.services.torch_config import setup_sentence_transformers_environment
    setup_sentence_transformers_environment()
except Exception as e:
    print(f"⚠️ Failed to setup torch environment: {e}")

from app import create_app, db

# 加载环境变量文件
load_dotenv('config.env')

def setup_environment():
    """设置环境变量和警告抑制"""
    # 抑制PIL图像警告
    warnings.filterwarnings('ignore', category=UserWarning, module='PIL')
    warnings.filterwarnings('ignore', message='.*iCCP.*')
    
    # 设置基本环境变量
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    
    print("🔧 Basic environment configured")

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