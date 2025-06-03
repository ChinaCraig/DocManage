# 律师案件案宗文档管理系统

基于Flask的文档管理系统，支持自然语义检索和多种文件格式处理。

## 功能特性

### 文档管理
- ✅ 可编辑文档结构树（文件夹+文件）
- ✅ 支持多种文件格式上传：PDF、Word、Excel、图片、视频
- ✅ 文件夹层级管理，只有文件夹可作为父节点
- ✅ 可编辑文本内容和描述

### 智能检索
- ✅ 自然语义检索（基于向量相似度）
- ✅ 文档名称搜索
- ✅ PDF文档内容提取和分块处理
- ✅ 支持文本型和扫描图像型PDF

### 技术架构
- **后端**: Python Flask + SQLAlchemy
- **数据库**: MySQL 
- **向量数据库**: Milvus
- **文档处理**: PyMuPDF, pdfplumber, pytesseract
- **文本嵌入**: sentence-transformers
- **前端**: Bootstrap 5 + Vanilla JavaScript

## 安装部署

### 1. 环境要求
- Python 3.8+
- MySQL 5.7+
- Milvus 2.0+
- Tesseract OCR

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置环境变量
复制 `env_example.txt` 为 `.env` 并修改配置：
```bash
cp env_example.txt .env
```

### 4. 数据库初始化

**重要**: 需要手动创建数据库和表结构，不依赖代码自动创建。

#### 方法一：命令行执行
```bash
# 1. 连接MySQL并创建数据库
mysql -h 192.168.16.108 -u root -p
mysql> CREATE DATABASE document_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
mysql> exit;

# 2. 执行建表脚本
mysql -h 192.168.16.108 -u root -p document_management < database/create_tables.sql
```

#### 方法二：直接导入
```bash
# 创建数据库并导入表结构（一条命令）
mysql -h 192.168.16.108 -u root -p -e "CREATE DATABASE IF NOT EXISTS document_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -h 192.168.16.108 -u root -p document_management < database/create_tables.sql
```

详细的数据库设置说明请参考 [DATABASE_SETUP.md](DATABASE_SETUP.md)

### 5. 启动服务
```bash
python run.py
```

访问 http://localhost:5001

## 系统架构

### 目录结构
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
│   │   ├── word_service.py      # Word处理服务（待实现）
│   │   ├── excel_service.py     # Excel处理服务（待实现）
│   │   ├── image_service.py     # 图片处理服务（待实现）
│   │   ├── video_service.py     # 视频处理服务（待实现）
│   │   └── vector_service.py    # 向量化服务
│   ├── routes/                  # 路由控制器
│   │   ├── __init__.py
│   │   ├── document_routes.py   # 文档管理路由
│   │   ├── upload_routes.py     # 文件上传路由
│   │   └── search_routes.py     # 搜索路由
│   └── static/                  # 静态文件
│       ├── index.html           # 主页面
│       └── js/
│           └── app.js           # 前端JavaScript
├── database/
│   └── create_tables.sql        # 数据库建表脚本
├── DATABASE_SETUP.md            # 数据库设置指南
├── config.py                    # 配置文件
├── run.py                       # 启动文件
├── requirements.txt             # Python依赖
├── env_example.txt              # 环境变量示例
└── README.md                    # 项目说明
```

### 数据库设计

#### 主要表结构
1. **document_nodes** - 文档节点表（统一管理文件夹和文件）
2. **document_contents** - 文档内容表（存储提取的文本内容和分块）
3. **vector_records** - 向量化记录表（记录向量化状态和Milvus向量ID）
4. **system_configs** - 系统配置表（动态配置参数）

**注意**: 系统启动时不会自动创建数据库表，需要手动执行建表脚本。

### 服务模块设计

#### 文件处理服务
- **PDFService**: PDF文档处理（✅ 已实现）
  - 文本型PDF直接提取
  - 图像型PDF使用OCR识别
  - 智能分块和向量化
- **WordService**: Word文档处理（🔄 待实现）
- **ExcelService**: Excel文档处理（🔄 待实现）
- **ImageService**: 图片处理（🔄 待实现）
- **VideoService**: 视频处理（🔄 待实现）

#### 向量化服务
- **VectorService**: 向量数据库操作
  - 基于sentence-transformers的文本嵌入
  - Milvus向量存储和检索
  - 相似度搜索

## API接口

### 文档管理
- `GET /api/documents/` - 获取文档列表
- `GET /api/documents/tree` - 获取文档树
- `POST /api/documents/folder` - 创建文件夹
- `PUT /api/documents/{id}` - 更新文档信息
- `DELETE /api/documents/{id}` - 删除文档
- `GET /api/documents/{id}/detail` - 获取文档详情

### 文件上传
- `POST /api/upload/` - 上传文件
- `POST /api/upload/process/{id}` - 处理文档内容
- `POST /api/upload/vectorize/{id}` - 向量化文档

### 搜索功能
- `POST /api/search/` - 语义搜索
- `GET /api/search/documents` - 文档名称搜索
- `GET /api/search/suggest` - 搜索建议
- `GET /api/search/stats` - 搜索统计

## 配置说明

### 模型配置
系统使用动态配置，可在 `system_configs` 表中修改：
- `embedding_model`: 文本嵌入模型路径
- `chunk_size`: 文本分块大小
- `chunk_overlap`: 分块重叠大小
- `milvus_host`: Milvus服务器地址
- `milvus_port`: Milvus服务器端口

### 文件存储
- 本地文件存储，路径可配置
- 文件重命名为UUID避免冲突
- 支持的文件类型可扩展

## 扩展说明

### 添加新文件类型支持
1. 在 `upload_routes.py` 中添加文件扩展名映射
2. 创建对应的Service类
3. 实现 `extract_text_content` 和 `split_into_chunks` 方法

### 自定义嵌入模型
1. 修改 `system_configs` 表中的 `embedding_model` 配置
2. 确保模型兼容 sentence-transformers 接口

## 注意事项

1. **数据库初始化**: 必须手动执行建表脚本，系统不会自动创建数据库
2. **数据库连接**: 确保MySQL服务器可访问，配置正确的连接参数
3. **Milvus服务**: 需要先启动Milvus向量数据库
4. **OCR依赖**: 处理扫描PDF需要安装Tesseract OCR
5. **模型下载**: 首次运行会自动下载嵌入模型，需要网络连接
6. **文件权限**: 确保文件存储目录有写入权限

## 后续优化

- [ ] 实现Word、Excel、图片、视频文件处理
- [ ] 添加用户权限管理
- [ ] 优化前端UI交互
- [ ] 支持批量文件上传
- [ ] 添加文档预览功能
- [ ] 实现文档版本管理
- [ ] 支持全文检索
- [ ] 添加API文档（Swagger）

## 技术支持

如有问题，请查看日志文件 `app.log` 获取详细错误信息。 