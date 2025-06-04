# 律师案件案宗文档管理系统

基于Flask的智能文档管理系统，支持多种文件格式处理、向量化存储和自然语义检索。

## 🌟 功能特性

### 📁 文档管理
- ✅ 可编辑文档结构树（文件夹+文件）
- ✅ 支持多种文件格式上传：PDF、Word、Excel、图片、视频
- ✅ 文件夹层级管理，只有文件夹可作为父节点
- ✅ 可编辑文本内容和描述

### 🤖 智能向量化功能
- ✅ **多格式支持**: PDF、Word、Excel、图片、视频文件向量化
- ✅ **智能文档分析**: 自动提取文本内容，支持OCR识别
- ✅ **可视化预览**: 文档信息展示（名称、分段数量、文本长度）
- ✅ **灵活分段配置**: 可调整分段大小（100-5000字符）和重叠长度（0-1000字符）
- ✅ **实时重新分段**: 即时调整参数并预览分段效果
- ✅ **分段内容编辑**: 用户可编辑或删除特定文本分段
- ✅ **MinIO对象存储**: 自动上传原文件到MinIO存储
- ✅ **向量数据库集成**: 文本向量存储到Milvus数据库
- ✅ **状态跟踪**: 完整的向量化状态和元数据管理
- ✅ **现代化UI**: 响应式界面，支持Bootstrap模态框和交互

### 🔍 智能检索
- ✅ 自然语义检索（基于向量相似度）
- ✅ 文档名称搜索
- ✅ 多格式文档内容提取和分块处理
- ✅ 支持文本型和扫描图像型文档

### 🏗️ 技术架构
- **后端**: Python Flask + SQLAlchemy
- **数据库**: MySQL 
- **向量数据库**: Milvus
- **对象存储**: MinIO
- **文档处理**: PyMuPDF, pdfplumber, pytesseract, python-docx, pandas
- **文本嵌入**: sentence-transformers
- **前端**: Bootstrap 5 + Vanilla JavaScript

## 🚀 快速开始

### 📋 环境要求
- Python 3.12+ (推荐，已解决Python 3.13兼容性问题)
- MySQL 5.7+
- Milvus 2.0+ (可选)
- MinIO (可选)
- Tesseract OCR

### ⚡ 5分钟快速启动

#### 1. 克隆项目并安装依赖
```bash
git clone <repository-url>
cd DocManage2

# 创建虚拟环境
python3.12 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\\Scripts\\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

#### 2. 配置环境变量
```bash
# 复制配置文件
cp config.env.example config.env

# 编辑配置文件
vim config.env
```

配置示例：
```env
# 数据库配置
MYSQL_HOST=192.168.16.199
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=document_management

# Milvus配置（可选）
MILVUS_HOST=192.168.16.199
MILVUS_PORT=19530
ENABLE_VECTOR_SERVICE=true

# MinIO配置（可选）
MINIO_ENDPOINT=192.168.16.199:9000
MINIO_ACCESS_KEY=your_access_key
MINIO_SECRET_KEY=your_secret_key
MINIO_BUCKET=documents
ENABLE_MINIO_SERVICE=true
```

#### 3. 数据库初始化
```bash
# 连接MySQL并创建数据库
mysql -h 192.168.16.199 -u root -p
mysql> CREATE DATABASE document_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
mysql> exit;

# 执行建表脚本
mysql -h 192.168.16.199 -u root -p document_management < database/create_tables.sql
mysql -h 192.168.16.199 -u root -p document_management < database/add_vectorization_fields.sql
```

#### 4. 启动应用
```bash
# 设置环境变量避免并发问题
export TOKENIZERS_PARALLELISM=false

# 启动应用
python run.py
```

✅ 访问地址：http://localhost:5001

#### 5. 测试向量化功能
1. 上传一个PDF文件
2. 在文档详情中点击"向量化"按钮
3. 调整分段参数并预览
4. 确认向量化并查看结果

## 📖 详细使用指南

### 🔄 向量化工作流程

#### 步骤1：上传文档
1. 打开浏览器访问 http://localhost:5001
2. 点击 **"上传文件"** 按钮
3. 选择支持的文件格式：
   - **PDF**: `.pdf`
   - **Word**: `.doc`, `.docx`
   - **Excel**: `.xls`, `.xlsx`
   - **图片**: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.tiff`, `.webp`
   - **视频**: `.mp4`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`, `.mkv`, `.m4v`

#### 步骤2：启动向量化
1. 在文档树中选择已上传的文件
2. 在文档详情面板中找到 **"向量化"** 按钮
3. 点击按钮开始文档分析

#### 步骤3：预览和编辑
1. **查看文档信息**：
   - 文档名称和类型
   - 分段数量
   - 文本长度

2. **调整分段参数**：
   - 分段大小：1000字符（推荐）
   - 重叠长度：200字符（推荐）
   - 点击"重新分段"查看效果

3. **编辑分段内容**：
   - 可以修改任何分段的文本内容
   - 删除不需要的分段（清空内容）
   - 每个分段独立可编辑

#### 步骤4：执行向量化
1. 确认分段内容无误
2. 点击 **"确认向量化"** 按钮
3. 系统执行：
   - 上传原文件到MinIO
   - 生成文本向量
   - 存储到向量数据库
   - 更新文档状态

#### 步骤5：查看结果
- 文档详情显示向量化状态
- 查看处理统计信息
- 支持语义搜索

### 🎯 不同文件类型的处理特点

#### PDF文档
- **文本型PDF**: 直接提取文本内容
- **图像型PDF**: 使用OCR识别文字
- **混合型PDF**: 智能识别并处理

#### Word文档
- **`.docx`**: 使用python-docx库处理
- **`.doc`**: 使用docx2txt转换
- **表格内容**: 自动提取并转换为文本

#### Excel表格
- **多工作表**: 分别处理每个工作表
- **结构化数据**: 转换为可搜索的文本格式
- **表头保留**: 保持数据结构信息

#### 图片文件
- **OCR识别**: 使用pytesseract和easyocr
- **多语言支持**: 中英文混合识别
- **元数据提取**: 图片属性信息

#### 视频文件
- **元数据提取**: 视频基本信息
- **字幕处理**: 自动查找同名SRT字幕文件
- **音频转文字**: 预留接口支持

## 🏗️ 系统架构

### 📁 项目结构
```
DocManage2/
├── app/                          # 应用主目录
│   ├── __init__.py              # Flask应用工厂
│   ├── models/                  # 数据模型
│   │   ├── __init__.py
│   │   └── document_models.py   # 文档相关模型
│   ├── services/                # 业务服务层
│   │   ├── __init__.py
│   │   ├── pdf_service.py       # PDF处理服务
│   │   ├── word_service.py      # Word处理服务
│   │   ├── excel_service.py     # Excel处理服务
│   │   ├── image_service.py     # 图片处理服务
│   │   ├── video_service.py     # 视频处理服务
│   │   ├── vectorization/       # 模块化向量化服务
│   │   │   ├── __init__.py
│   │   │   ├── base_vectorizer.py        # 基础向量化器
│   │   │   ├── pdf_vectorizer.py         # PDF向量化器
│   │   │   ├── word_vectorizer.py        # Word向量化器
│   │   │   ├── excel_vectorizer.py       # Excel向量化器
│   │   │   ├── image_vectorizer.py       # 图片向量化器
│   │   │   ├── video_vectorizer.py       # 视频向量化器
│   │   │   ├── vectorization_factory.py  # 向量化工厂
│   │   │   └── vector_service_adapter.py # 向量服务适配器
│   │   └── minio_service.py     # MinIO对象存储服务
│   ├── routes/                  # 路由控制器
│   │   ├── __init__.py
│   │   ├── document_routes.py   # 文档管理路由
│   │   ├── upload_routes.py     # 文件上传路由
│   │   ├── search_routes.py     # 搜索路由
│   │   └── vectorize_routes.py  # 向量化路由
│   └── static/                  # 静态文件
│       ├── index.html           # 主页面
│       └── js/
│           └── app.js           # 前端JavaScript
├── database/                    # 数据库相关
│   ├── create_tables.sql        # 数据库建表脚本
│   └── add_vectorization_fields.sql  # 向量化字段更新脚本
├── uploads/                     # 文件上传目录
├── .venv/                       # Python虚拟环境
├── config.py                    # 应用配置
├── config.env                   # 环境变量配置
├── requirements.txt             # Python依赖
├── run.py                       # 应用启动入口
├── setup_milvus.py             # Milvus设置脚本
└── README.md                    # 项目说明
```

### 🎨 向量化架构设计

#### 设计模式
1. **工厂模式**: `VectorizationFactory` 根据文件类型自动选择向量化器
2. **策略模式**: 每种文件类型有独立的处理策略
3. **模板方法模式**: `BaseVectorizer` 定义通用流程，子类实现特定逻辑

#### 核心组件
- **BaseVectorizer**: 基础向量化器抽象类
- **专门向量化器**: 针对不同文件类型的处理器
- **VectorizationFactory**: 向量化工厂类
- **VectorServiceAdapter**: 向量数据库操作适配器

### 🗄️ 数据库设计

#### 主要表结构
1. **document_nodes** - 文档节点表
   - 基础字段：id, name, type, parent_id, file_path, created_at, updated_at
   - 向量化字段：is_vectorized, vector_status, vectorized_at, minio_path, doc_metadata

2. **document_contents** - 文档内容表
   - 存储提取的文本内容和分块信息

3. **vector_records** - 向量化记录表
   - 记录向量化状态和Milvus向量ID

4. **system_configs** - 系统配置表
   - 动态配置参数，包括MinIO和向量化配置

## 🔌 API接口

### 文档管理
- `GET /api/documents/` - 获取文档列表
- `GET /api/documents/tree` - 获取文档树
- `POST /api/documents/folder` - 创建文件夹
- `PUT /api/documents/{id}` - 更新文档信息
- `DELETE /api/documents/{id}` - 删除文档
- `GET /api/documents/{id}/detail` - 获取文档详情

### 文件上传
- `POST /api/upload/` - 上传文件
- `POST /api/upload/process/{doc_id}` - 处理上传的文件

### 向量化功能
- `POST /api/vectorize/preview/{doc_id}` - 预览向量化内容
- `POST /api/vectorize/execute/{doc_id}` - 执行向量化
- `GET /api/vectorize/status/{doc_id}` - 查询向量化状态
- `GET /api/vectorize/supported-types` - 获取支持的文件类型

### 搜索功能
- `GET /api/search/` - 文档搜索
- `GET /api/search/stats` - 搜索统计信息

## ⚙️ 配置说明

### 环境变量配置
```env
# 数据库配置
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=password
MYSQL_DATABASE=document_management

# Milvus向量数据库配置
MILVUS_HOST=localhost
MILVUS_PORT=19530
ENABLE_VECTOR_SERVICE=true

# MinIO对象存储配置
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=documents
ENABLE_MINIO_SERVICE=true

# 向量化配置
EMBEDDING_MODEL=all-MiniLM-L6-v2
DEFAULT_CHUNK_SIZE=1000
DEFAULT_CHUNK_OVERLAP=200
TOKENIZERS_PARALLELISM=false
```

### 系统配置项
可在数据库`system_configs`表中动态调整：
- `vectorization_enabled`: 是否启用向量化
- `default_chunk_size`: 默认分段大小
- `default_chunk_overlap`: 默认重叠长度
- `minio_endpoint`: MinIO服务器地址
- `minio_access_key`: MinIO访问密钥

## 🛠️ 故障排除

### 常见问题解决

#### 1. Python版本兼容性问题
**问题**: Python 3.13.3 与机器学习库不兼容
**解决方案**: 
```bash
# 安装Python 3.12
brew install python@3.12

# 重新创建虚拟环境
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 2. 向量化失败
**问题**: "Cannot copy out of meta tensor; no data!"
**解决方案**:
```bash
# 清理模型缓存
rm -rf ~/.cache/torch/sentence_transformers
rm -rf ~/.cache/huggingface

# 设置环境变量
export TOKENIZERS_PARALLELISM=false

# 重启应用
python run.py
```

#### 3. 前端显示"undefined"
**问题**: 文本块显示undefined
**解决方案**: 已在`app/static/js/app.js`中添加null检查

#### 4. Milvus连接问题
**检查步骤**:
```bash
# 测试连接
python setup_milvus.py

# 检查配置
grep MILVUS config.env

# 查看日志
tail -f app.log | grep -i milvus
```

#### 5. 数据库连接问题
**检查步骤**:
```bash
# 测试MySQL连接
mysql -h $MYSQL_HOST -u $MYSQL_USER -p

# 检查表结构
mysql -h $MYSQL_HOST -u $MYSQL_USER -p $MYSQL_DATABASE -e "SHOW TABLES;"
```

### 日志检查
```bash
# 查看应用日志
tail -f app.log

# 过滤特定错误
grep -i "error\|failed" app.log

# 查看向量化相关日志
grep -i "vector\|embedding" app.log
```

## 📊 性能优化

### 推荐配置
- **分段大小**: 1000-2000字符（平衡检索精度和性能）
- **重叠长度**: 10-20%的分段大小
- **批量处理**: 避免同时处理大量文档

### 处理能力
- **小文档** (< 10页): 2-5秒
- **中文档** (10-50页): 5-15秒
- **大文档** (50+页): 15-60秒

### 资源使用
- **内存**: ~100MB per document
- **存储**: 原文件 + 向量数据
- **CPU**: 处理期间中等负载

## 🔧 开发指南

### 添加新文件类型支持

1. **创建新的向量化器**:
```python
from .base_vectorizer import BaseVectorizer

class NewFileVectorizer(BaseVectorizer):
    def __init__(self):
        super().__init__()
        self.file_type = "newtype"
    
    def get_supported_extensions(self):
        return ['.ext1', '.ext2']
    
    def extract_text(self, file_path):
        # 实现文本提取逻辑
        pass
    
    def chunk_text(self, text, chunk_size=1000, overlap=200):
        # 实现文本分块逻辑
        pass
```

2. **注册到工厂**:
```python
# 在vectorization_factory.py中注册
factory.register_vectorizer('newtype', NewFileVectorizer)
```

### 扩展API接口
```python
# 在routes中添加新的端点
@vectorize_bp.route('/api/vectorize/custom/<int:doc_id>', methods=['POST'])
def custom_vectorize(doc_id):
    # 自定义向量化逻辑
    pass
```

## 📚 技术栈详情

### 后端依赖
```txt
Flask==3.0.0                    # Web框架
SQLAlchemy==2.0.23             # ORM
PyMySQL==1.1.0                 # MySQL驱动
pymilvus==2.5.10               # Milvus客户端
sentence-transformers==4.1.0   # 文本嵌入
torch==2.2.2                   # 深度学习框架
PyMuPDF==1.23.8               # PDF处理
pdfplumber==0.10.3            # PDF文本提取
pytesseract==0.3.10           # OCR
python-docx==1.1.0            # Word文档处理
pandas==2.1.4                 # Excel处理
opencv-python==4.8.1.78      # 视频处理
easyocr==1.7.0                # OCR备选方案
minio==7.2.0                  # 对象存储客户端
```

### 前端技术
- **Bootstrap 5**: 响应式UI框架
- **Vanilla JavaScript**: 原生JS，无额外依赖
- **Font Awesome**: 图标库

## 🎯 后续计划

### v1.1 计划
- [ ] 批量向量化功能
- [ ] 向量化任务队列
- [ ] 高级搜索过滤器
- [ ] 文档相似度分析

### v1.2 计划
- [ ] 多语言支持
- [ ] 用户权限管理
- [ ] API认证和授权
- [ ] 性能监控面板

### v2.0 计划
- [ ] 微服务架构重构
- [ ] 分布式向量存储
- [ ] 机器学习模型优化
- [ ] 企业级部署方案

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🤝 贡献指南

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📞 支持与反馈

如果您在使用过程中遇到问题或有改进建议，请：

1. 查看本文档的故障排除部分
2. 检查应用日志文件
3. 提交 Issue 或 Pull Request

---

**注意**: 向量化功能是可选的，即使不安装Milvus和MinIO，系统的基础文档管理功能仍然可以正常工作。 