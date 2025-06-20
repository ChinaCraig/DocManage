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
    
    # 意图识别专用LLM配置
    INTENT_ANALYSIS_LLM_PROVIDER = os.environ.get('INTENT_ANALYSIS_LLM_PROVIDER') or 'deepseek'
    INTENT_ANALYSIS_LLM_MODEL = os.environ.get('INTENT_ANALYSIS_LLM_MODEL') or 'deepseek-chat'
    ENABLE_INTENT_ANALYSIS = os.environ.get('ENABLE_INTENT_ANALYSIS', 'true').lower() == 'true'
    
    # 意图识别提示词模板配置
    INTENT_ANALYSIS_SYSTEM_PROMPT = os.environ.get('INTENT_ANALYSIS_SYSTEM_PROMPT') or """你是一个专业的用户意图分析助手。你需要分析用户的输入，判断用户想要执行什么操作。

请严格按照以下JSON格式返回分析结果（不要添加markdown格式或其他文本）：
{
  "intent_type": "mcp_action|vector_search|folder_analysis",
  "confidence": 0.0-1.0之间的数字,
  "action_type": "create_file|create_folder|search_documents|analyze_folder|other",
  "parameters": {
    "file_name": "如果是创建文件，提取文件名",
    "folder_name": "如果是创建文件夹或分析文件夹，提取文件夹名",
    "parent_folder": "如果指定了父目录，提取父目录名",
    "search_keywords": "如果是搜索，提取关键词",
    "analysis_type": "如果是分析操作，提取分析类型（如：缺失内容、完整性检查等）"
  },
  "reasoning": "简要说明判断依据"
}

意图分类说明：
- mcp_action: 用户想要执行操作（如创建文件、创建文件夹等）
- vector_search: 用户想要搜索或查找信息
- folder_analysis: 用户想要分析文件夹内容完整性

操作类型说明：
- create_file: 创建文件（包含文件扩展名或明确说明是文件）
- create_folder: 创建文件夹/目录
- search_documents: 搜索文档内容
- analyze_folder: 分析文件夹内容（检查缺失文件、内容完整性等）
- other: 其他操作

特别注意：
1. 当用户询问"分析XX缺少哪些内容"、"检查XX文件夹"、"确认XX目录"等时，应识别为folder_analysis意图
2. 文件夹分析关键词包括：分析、检查、确认、缺少、完整性、内容等
3. 务必准确提取文件夹名称到parameters.folder_name字段中
4. 意图识别要求高精度，置信度低于0.6时应降级到向量搜索"""

    INTENT_ANALYSIS_USER_PROMPT_TEMPLATE = os.environ.get('INTENT_ANALYSIS_USER_PROMPT_TEMPLATE') or """请分析以下用户输入的意图：

用户输入："{query}"

请返回JSON格式的分析结果："""

    # 意图识别模型参数配置
    INTENT_ANALYSIS_MAX_TOKENS = int(os.environ.get('INTENT_ANALYSIS_MAX_TOKENS') or 300)
    INTENT_ANALYSIS_TEMPERATURE = float(os.environ.get('INTENT_ANALYSIS_TEMPERATURE') or 0.1)
    INTENT_ANALYSIS_CONFIDENCE_THRESHOLD = float(os.environ.get('INTENT_ANALYSIS_CONFIDENCE_THRESHOLD') or 0.6)
    
    # LLM功能开关
    ENABLE_LLM_QUERY_OPTIMIZATION = os.environ.get('ENABLE_LLM_QUERY_OPTIMIZATION', 'true').lower() == 'true'
    ENABLE_LLM_RESULT_RERANKING = os.environ.get('ENABLE_LLM_RESULT_RERANKING', 'true').lower() == 'true'
    ENABLE_LLM_ANSWER_GENERATION = os.environ.get('ENABLE_LLM_ANSWER_GENERATION', 'false').lower() == 'true'
    
    # LLM性能参数
    LLM_TIMEOUT = int(os.environ.get('LLM_TIMEOUT') or 30)
    LLM_MAX_CONTEXT_LENGTH = int(os.environ.get('LLM_MAX_CONTEXT_LENGTH') or 4000)
    LLM_RERANK_BATCH_SIZE = int(os.environ.get('LLM_RERANK_BATCH_SIZE') or 20)
    LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS') or 500)
    LLM_TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE') or 0.7)
    
    # 应用服务配置
    APP_HOST = os.environ.get('APP_HOST') or '0.0.0.0'
    APP_PORT = int(os.environ.get('APP_PORT') or 5001)
    
    # MCP配置
    MCP_CONFIG = {
        'enabled': os.environ.get('MCP_ENABLED', 'true').lower() == 'true',
        'timeout': int(os.environ.get('MCP_TIMEOUT') or 30),  # 工具调用超时时间（秒）
        'max_concurrent_tools': int(os.environ.get('MCP_MAX_CONCURRENT_TOOLS') or 3),  # 最大并发工具数
        'app_url': os.environ.get('MCP_APP_URL') or f'http://localhost:{int(os.environ.get("APP_PORT") or 5001)}',
        'playwright': {
            'element_timeout': int(os.environ.get('MCP_ELEMENT_TIMEOUT') or 5000),  # 元素等待超时（毫秒）
            'modal_timeout': int(os.environ.get('MCP_MODAL_TIMEOUT') or 10000),  # 模态框等待超时（毫秒）
            'wait_timeout': int(os.environ.get('MCP_WAIT_TIMEOUT') or 500),  # 一般等待时间（毫秒）
        },
        'servers': {
            'playwright': {
                'name': 'Playwright Web自动化',
                'description': '自动化Web浏览器操作，可以点击按钮、填写表单、导航页面等',
                'enabled': os.environ.get('MCP_PLAYWRIGHT_ENABLED', 'true').lower() == 'true',
                'capabilities': [
                    'navigate',      # 页面导航
                    'click',         # 点击元素
                    'fill',          # 填写表单
                    'screenshot',    # 截图
                    'wait',          # 等待元素
                    'scroll',        # 页面滚动
                    'evaluate'       # 执行JavaScript
                ]
            },
            # 预留扩展空间
            'search': {
                'name': '网络搜索',
                'description': '执行网络搜索，获取实时信息',
                'enabled': os.environ.get('MCP_SEARCH_ENABLED', 'false').lower() == 'true',
                'capabilities': [
                    'web_search',
                    'content_extract'
                ]
            },
            'file_system': {
                'name': '文件系统操作',
                'description': '本地文件系统读写操作',
                'enabled': os.environ.get('MCP_FILESYSTEM_ENABLED', 'false').lower() == 'true',
                'capabilities': [
                    'read_file',
                    'write_file',
                    'list_directory'
                ]
            }
        }
    }
    
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