import os
from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from config import config
import atexit
import threading
import time

db = SQLAlchemy()

def cleanup_temp_images():
    """清理临时图片"""
    try:
        from app.services.preview.word_preview import WordPreviewService
        word_service = WordPreviewService()
        word_service.cleanup_temp_images()
    except Exception as e:
        print(f"清理临时图片时出错: {e}")

def start_cleanup_scheduler():
    """启动定期清理任务"""
    def cleanup_task():
        while True:
            time.sleep(3600)  # 每小时执行一次
            cleanup_temp_images()
    
    cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
    cleanup_thread.start()

def create_app(config_name=None):
    """Flask应用工厂函数"""
    app = Flask(__name__)
    
    # 配置
    config_name = config_name or os.getenv('FLASK_CONFIG') or 'default'
    app.config.from_object(config[config_name])
    
    # 初始化扩展
    db.init_app(app)
    CORS(app)
    
    # 创建上传目录
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # 启动临时文件清理任务
    start_cleanup_scheduler()
    
    # 程序退出时清理临时图片
    atexit.register(cleanup_temp_images)
    
    # 注册蓝图
    from app.routes.document_routes import document_bp
    from app.routes.search_routes import search_bp
    from app.routes.upload_routes import upload_bp
    from app.routes.vectorize_routes import vectorize_bp
    from app.routes.preview_routes import preview_bp
    
    app.register_blueprint(document_bp, url_prefix='/api/documents')
    app.register_blueprint(search_bp, url_prefix='/api/search')
    app.register_blueprint(upload_bp, url_prefix='/api/upload')
    app.register_blueprint(vectorize_bp, url_prefix='/api/vectorize')
    app.register_blueprint(preview_bp, url_prefix='/api/preview')
    
    # 注册主页路由
    @app.route('/')
    def index():
        return app.send_static_file('index.html')
    
    # 语义检索页面路由
    @app.route('/semantic-search')
    def semantic_search_page():
        return app.send_static_file('semantic_search.html')
    
    # 静态文件路由
    @app.route('/js/<path:filename>')
    def static_js(filename):
        return send_from_directory(os.path.join(app.static_folder, 'js'), filename)
    
    # 文件预览路由
    @app.route('/api/files/preview/<int:doc_id>')
    def preview_file(doc_id):
        from app.models import DocumentNode
        document = DocumentNode.query.get_or_404(doc_id)
        
        if document.is_deleted or document.type != 'file':
            return "文件不存在", 404
        
        if not os.path.exists(document.file_path):
            return "文件不存在", 404
        
        return send_from_directory(
            os.path.dirname(document.file_path),
            os.path.basename(document.file_path)
        )
    
    return app 