import logging
from app import create_app, db

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# 创建Flask应用实例
app = create_app()

# 创建数据库表（如果不存在）
with app.app_context():
    try:
        db.create_all()
        logger.info("数据库表检查/创建完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")

if __name__ == '__main__':
    logger.info("启动文档管理系统...")
    logger.info("访问地址: http://0.0.0.0:5001")
    app.run(debug=True, host='0.0.0.0', port=5001) 