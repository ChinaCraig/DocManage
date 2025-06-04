"""
路由模块
包含文档管理、搜索、上传和向量化功能的路由
"""

from .document_routes import document_bp
from .search_routes import search_bp
from .upload_routes import upload_bp
from .vectorize_routes import vectorize_bp

__all__ = ['document_bp', 'search_bp', 'upload_bp', 'vectorize_bp'] 