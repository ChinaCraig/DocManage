# 兼容性修复：为新版本Pillow添加ANTIALIAS别名
# 必须在其他导入之前执行，以确保所有依赖库都能使用
try:
    from PIL import Image
    if not hasattr(Image, 'ANTIALIAS'):
        Image.ANTIALIAS = Image.LANCZOS
except Exception:
    pass

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
    
    # 简化MCP服务已在模块导入时初始化
    pass
    
    # 注册蓝图
    from app.routes.document_routes import document_bp
    from app.routes.search_routes import search_bp
    from app.routes.upload_routes import upload_bp
    from app.routes.vectorize_routes import vectorize_bp
    from app.routes.preview_routes import preview_bp
    from app.routes.tag_routes import tag_bp
    from app.routes.config_routes import config_bp
    from app.routes.prompt_routes import prompt_routes
    from app.routes.llm_routes import llm_bp
    from app.routes.mcp_routes import mcp_bp
    from app.routes.intent_routes import intent_bp
    
    app.register_blueprint(document_bp, url_prefix='/api/documents')
    app.register_blueprint(search_bp, url_prefix='/api/search')
    app.register_blueprint(upload_bp, url_prefix='/api/upload')
    app.register_blueprint(vectorize_bp, url_prefix='/api/vectorize')
    app.register_blueprint(preview_bp, url_prefix='/api/preview')
    app.register_blueprint(tag_bp, url_prefix='/api/tags')
    app.register_blueprint(config_bp, url_prefix='/api/config')
    app.register_blueprint(llm_bp, url_prefix='/api/llm')
    app.register_blueprint(mcp_bp, url_prefix='/api/mcp')
    app.register_blueprint(intent_bp, url_prefix='/api/intent')
    app.register_blueprint(prompt_routes)
    
    # 注册主页路由 - 重定向到语义搜索
    @app.route('/')
    def index():
        return app.send_static_file('semantic_search.html')
    
    # 语义搜索页面路由（保持兼容性）
    @app.route('/semantic-search')
    def semantic_search_page():
        return app.send_static_file('semantic_search.html')
    
    # LLM功能测试页面
    @app.route('/test_llm.html')
    def test_llm_page():
        return app.send_static_file('test_llm.html')
    
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