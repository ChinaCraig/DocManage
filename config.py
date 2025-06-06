"""
应用配置文件
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv('config.env')  # 从config.env文件加载
load_dotenv()  # 从.env文件加载（如果存在）

class Config:
    """基础配置类"""
    
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # 数据库配置
    DB_HOST = os.environ.get('DB_HOST') or 'localhost'
    DB_PORT = int(os.environ.get('DB_PORT') or 3306)
    DB_USER = os.environ.get('DB_USER') or 'root'
    DB_PASSWORD = os.environ.get('DB_PASSWORD') or ''
    DB_NAME = os.environ.get('DB_NAME') or 'document_management'
    
    # 构建数据库URI
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'connect_args': {
            'charset': 'utf8mb4',
            'connect_timeout': 60,
            'read_timeout': 60,
            'write_timeout': 60
        }
    }
    
    # 文件上传配置
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or 'uploads'
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH') or 100) * 1024 * 1024  # MB转字节
    ALLOWED_EXTENSIONS = {
        'pdf', 'doc', 'docx', 'xls', 'xlsx', 
        'jpg', 'jpeg', 'png', 'gif', 'bmp',
        'mp4', 'avi', 'mov', 'wmv', 'flv'
    }
    
    # 向量数据库配置
    MILVUS_HOST = os.environ.get('MILVUS_HOST') or 'localhost'
    MILVUS_PORT = int(os.environ.get('MILVUS_PORT') or 19530)
    
    # 模型配置
    EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL') or 'all-MiniLM-L6-v2'
    
    # LLM配置
    LLM_PROVIDERS = {
        'openai': {
            'name': 'OpenAI GPT',
            'models': {
                'gpt-3.5-turbo': 'GPT-3.5 Turbo',
                'gpt-4': 'GPT-4',
                'gpt-4-turbo': 'GPT-4 Turbo'
            },
            'api_key': os.environ.get('OPENAI_API_KEY'),
            'base_url': os.environ.get('OPENAI_BASE_URL')
        },
        'ollama': {
            'name': 'Ollama (本地)',
            'models': {
                'llama2': 'Llama 2',
                'qwen2': 'Qwen 2',
                'chatglm3': 'ChatGLM3',
                'baichuan2': 'Baichuan 2'
            },
            'base_url': os.environ.get('OLLAMA_BASE_URL') or 'http://localhost:11434'
        },
        'claude': {
            'name': 'Anthropic Claude',
            'models': {
                'claude-3-haiku': 'Claude 3 Haiku',
                'claude-3-sonnet': 'Claude 3 Sonnet',
                'claude-3-opus': 'Claude 3 Opus'
            },
            'api_key': os.environ.get('ANTHROPIC_API_KEY')
        },
        'zhipu': {
            'name': '智谱AI',
            'models': {
                'glm-4': 'GLM-4',
                'glm-3-turbo': 'GLM-3 Turbo'
            },
            'api_key': os.environ.get('ZHIPU_API_KEY')
        },
        'deepseek': {
            'name': 'DeepSeek',
            'models': {
                'deepseek-chat': 'DeepSeek Chat',
                'deepseek-coder': 'DeepSeek Coder',
                'deepseek-v3': 'DeepSeek V3'
            },
            'api_key': os.environ.get('DEEPSEEK_API_KEY'),
            'base_url': os.environ.get('DEEPSEEK_BASE_URL') or 'https://api.deepseek.com'
        }
    }
    
    # 默认LLM配置
    DEFAULT_LLM_PROVIDER = os.environ.get('DEFAULT_LLM_PROVIDER') or 'openai'
    DEFAULT_LLM_MODEL = os.environ.get('DEFAULT_LLM_MODEL') or 'gpt-3.5-turbo'
    
    # LLM功能开关
    ENABLE_LLM_QUERY_OPTIMIZATION = os.environ.get('ENABLE_LLM_QUERY_OPTIMIZATION', 'true').lower() == 'true'
    ENABLE_LLM_RESULT_RERANKING = os.environ.get('ENABLE_LLM_RESULT_RERANKING', 'true').lower() == 'true'
    ENABLE_LLM_ANSWER_GENERATION = os.environ.get('ENABLE_LLM_ANSWER_GENERATION', 'false').lower() == 'true'
    
    # LLM性能参数
    LLM_TIMEOUT = int(os.environ.get('LLM_TIMEOUT') or 30)
    LLM_MAX_CONTEXT_LENGTH = int(os.environ.get('LLM_MAX_CONTEXT_LENGTH') or 4000)
    LLM_RERANK_BATCH_SIZE = int(os.environ.get('LLM_RERANK_BATCH_SIZE') or 20)
    
    # 日志配置
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    
    @staticmethod
    def init_app(app):
        """初始化应用配置"""
        pass

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    FLASK_ENV = 'development'

class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    FLASK_ENV = 'production'
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # 生产环境特定配置
        import logging
        from logging.handlers import RotatingFileHandler
        
        if not app.debug:
            if not os.path.exists('logs'):
                os.mkdir('logs')
            
            file_handler = RotatingFileHandler(
                'logs/document_management.log',
                maxBytes=10240000,
                backupCount=10
            )
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
            ))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)
            
            app.logger.setLevel(logging.INFO)
            app.logger.info('Document Management System startup')

class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

# 配置字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
} 