# 智能文档管理与语义检索系统

## 🎯 项目简介

这是一个集成的智能文档管理和语义检索系统，集成了文档管理、内容识别、向量化处理和语义搜索功能。

## ✨ 主要功能

- **🔍 智能语义搜索**: 自然语言查询，支持多种相似度阈值
- **📁 文档管理**: 文件上传、文件夹管理、文档编辑
- **🤖 智能向量化**: 支持PDF、Word、Excel、图像等多种格式
- **🛠️ MCP自动化**: 通过自然语言创建文件/文件夹
- **🧠 LLM集成**: 支持多种大语言模型优化搜索结果

## 🚀 快速开始

### 1. 环境准备
```bash
# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 安装Playwright（用于MCP功能）
pip install playwright
playwright install chromium
```

### 2. 配置环境
复制并修改 `config.env` 文件中的配置项。

### 3. 启动系统
```bash
python run.py
```

### 4. 访问系统
打开浏览器访问：http://localhost:5001

## 📊 支持的文件格式

| 类型 | 扩展名 | 功能特性 |
|------|--------|----------|
| PDF | .pdf | 文本+图像提取、OCR识别 |
| Word | .doc, .docx | 文本、表格、图像处理 |
| Excel | .xls, .xlsx, .xlsm, .xlsb | 数据分析、模式识别 |
| 图像 | .jpg, .jpeg, .png, .gif, .bmp, .tiff, .webp, .svg | OCR文字识别 |
| 文本 | .txt, .md, .html, .csv, .json, .py, .js, .css, .sql | 内容提取 |

## 📖 详细文档

完整的功能说明、配置方法和使用指南请参考：[完整项目文档.md](完整项目文档.md)

## 🏗️ 项目结构

```
DocManage/
├── app/                         # 应用核心代码
├── database/                    # 数据库脚本
├── prompts/                     # 提示词配置
├── uploads/                     # 上传文件存储
├── venv/                        # Python虚拟环境
├── config.py                    # 配置文件
├── config.env                   # 环境变量配置
├── run.py                       # 启动文件
├── setup_milvus.py              # 向量数据库设置
├── requirements.txt             # 依赖列表
├── 完整项目文档.md              # 详细文档
└── README.md                    # 项目说明（本文件）
```

## 🔧 技术栈

- **后端**: Flask, SQLAlchemy, Milvus
- **前端**: Bootstrap 5, 原生JavaScript
- **AI技术**: SentenceTransformers, OCR引擎, LLM集成
- **自动化**: MCP (Model Context Protocol), Playwright

---

**系统版本**: v2.0  
**最后更新**: 2025年6月 