import os
from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from config import config

db = SQLAlchemy()

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
    
    # 注册蓝图
    from app.routes.document_routes import document_bp
    from app.routes.search_routes import search_bp
    from app.routes.upload_routes import upload_bp
    
    app.register_blueprint(document_bp, url_prefix='/api/documents')
    app.register_blueprint(search_bp, url_prefix='/api/search')
    app.register_blueprint(upload_bp, url_prefix='/api/upload')
    
    # 注册主页路由
    @app.route('/')
    def index():
        return app.send_static_file('index.html')
    
    # 静态文件路由
    @app.route('/js/<path:filename>')
    def static_js(filename):
        return send_from_directory(os.path.join(app.static_folder, 'js'), filename)
    
    return app 