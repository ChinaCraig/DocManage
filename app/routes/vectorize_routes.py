"""
文档向量化路由
处理各种类型文档的向量化操作
"""
from flask import Blueprint, request, jsonify
from app import db
from app.models import DocumentNode
from app.services.vectorization import VectorizationFactory
from app.services.minio_service import MinIOService
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

vectorize_bp = Blueprint('vectorize', __name__)

# 初始化服务
vectorization_factory = VectorizationFactory()
minio_service = MinIOService()

@vectorize_bp.route('/preview/<int:doc_id>', methods=['POST'])
def preview_document_vectorization(doc_id):
    """
    预览文档向量化内容
    提取文档文本和分段信息，供用户编辑确认
    """
    try:
        # 获取文档信息
        document = DocumentNode.query.get_or_404(doc_id)
        
        if document.type != 'file' or not document.file_path:
            return jsonify({
                'success': False,
                'error': '文档类型不正确或文件路径为空'
            }), 400
        
        # 检查文件是否存在
        if not os.path.exists(document.file_path):
            return jsonify({
                'success': False,
                'error': '文件不存在'
            }), 404
        
        # 检查文件类型是否支持
        if not vectorization_factory.is_supported_file(document.file_path):
            file_ext = os.path.splitext(document.file_path)[1]
            supported_exts = vectorization_factory.get_all_supported_extensions()
            return jsonify({
                'success': False,
                'error': f'不支持的文件类型: {file_ext}。支持的类型: {", ".join(supported_exts)}'
            }), 400
        
        # 获取对应的向量化器
        vectorizer = vectorization_factory.get_vectorizer(document.file_path)
        if not vectorizer:
            return jsonify({
                'success': False,
                'error': '无法获取合适的向量化器'
            }), 500
        
        # 初始化向量服务
        vectorizer.initialize_vector_service()
        
        # 处理文档文件
        file_type = vectorization_factory.get_file_type(document.file_path)
        logger.info(f"开始处理{file_type}文件: {document.file_path}")
        
        # 提取文档内容
        extract_result = vectorizer.extract_text(document.file_path)
        
        if not extract_result['success']:
            return jsonify({
                'success': False,
                'error': f'文档处理失败: {extract_result.get("error", "未知错误")}'
            }), 500
        
        # 获取分段参数
        chunk_size = request.json.get('chunk_size', 1000) if request.json else 1000
        overlap = request.json.get('overlap', 200) if request.json else 200
        
        # 重新分段（如果用户指定了不同的参数）
        if request.json and ('chunk_size' in request.json or 'overlap' in request.json):
            chunks = vectorizer.chunk_text(
                extract_result['text'], 
                chunk_size=chunk_size, 
                overlap=overlap
            )
        else:
            chunks = extract_result.get('chunks', [])
        
        # 为每个分段生成ID
        chunks_with_id = []
        for i, chunk in enumerate(chunks):
            chunks_with_id.append({
                'id': f"chunk_{i}",
                'content': chunk,
                'editable': True
            })
        
        return jsonify({
            'success': True,
            'data': {
                'document_id': doc_id,
                'document_name': document.name,
                'file_type': file_type,
                'vectorizer_used': vectorizer.__class__.__name__,
                'metadata': extract_result['metadata'],
                'full_text': extract_result['text'],
                'chunks': chunks_with_id,
                'chunk_count': len(chunks_with_id),
                'text_length': len(extract_result['text']),
                'chunk_size': chunk_size,
                'overlap': overlap
            }
        })
        
    except Exception as e:
        logger.error(f"预览文档向量化失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@vectorize_bp.route('/execute/<int:doc_id>', methods=['POST'])
def execute_vectorization(doc_id):
    """
    执行文档向量化
    将编辑后的内容存入向量数据库，并上传原文件到MinIO
    """
    try:
        # 获取文档信息
        document = DocumentNode.query.get_or_404(doc_id)
        
        if document.type != 'file' or not document.file_path:
            return jsonify({
                'success': False,
                'error': '文档类型不正确或文件路径为空'
            }), 400
        
        # 获取用户编辑后的数据
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '缺少请求数据'
            }), 400
        
        chunks = data.get('chunks', [])
        metadata = data.get('metadata', {})
        
        if not chunks:
            return jsonify({
                'success': False,
                'error': '没有可向量化的文本块'
            }), 400
        
        # 获取向量化器
        vectorizer = vectorization_factory.get_vectorizer(document.file_path)
        if not vectorizer:
            return jsonify({
                'success': False,
                'error': '无法获取合适的向量化器'
            }), 500
        
        # 初始化向量服务
        vectorizer.initialize_vector_service()
        
        # 1. 上传文件到MinIO
        logger.info(f"准备上传文件到MinIO: {document.file_path}")
        
        # 确保MinIO服务已初始化
        if not minio_service.is_available:
            minio_service.initialize()
        
        # 生成对象名称
        filename = document.name
        timestamp = datetime.now().strftime('%Y/%m/%d')
        unique_id = str(uuid.uuid4())
        file_type = vectorization_factory.get_file_type(document.file_path)
        object_name = f"documents/{file_type}/{timestamp}/{unique_id}_{filename}"
        
        minio_result = minio_service.upload_file(document.file_path, object_name)
        
        if not minio_result['success']:
            return jsonify({
                'success': False,
                'error': f'文件上传失败: {minio_result.get("error", "未知错误")}'
            }), 500
        
        # 2. 生成向量数据
        text_chunks = [chunk.get('content', '').strip() for chunk in chunks if chunk.get('content', '').strip()]
        vectors_data = vectorizer.generate_vectors_data(str(doc_id), text_chunks)
        
        # 3. 插入向量数据到数据库
        vector_insert_success = False
        if vectors_data:
            vector_insert_success = vectorizer.insert_vectors(vectors_data)
            if not vector_insert_success:
                logger.warning("向量数据插入失败，但继续执行")
        
        # 4. 更新文档状态
        document.is_vectorized = True
        document.vector_status = 'completed'
        document.vectorized_at = datetime.now()
        document.minio_path = object_name
        
        # 更新元数据，包含文件类型信息
        if document.doc_metadata:
            document.doc_metadata.update({
                'vectorization': {
                    'file_type': file_type,
                    'vectorizer_used': vectorizer.__class__.__name__,
                    'chunk_count': len(vectors_data),
                    'vector_insert_success': vector_insert_success
                }
            })
        else:
            document.doc_metadata = {
                'vectorization': {
                    'file_type': file_type,
                    'vectorizer_used': vectorizer.__class__.__name__,
                    'chunk_count': len(vectors_data),
                    'vector_insert_success': vector_insert_success
                }
            }
        
        # 如果有额外的元数据，也添加进去
        if metadata:
            document.doc_metadata.update(metadata)
        
        db.session.commit()
        
        logger.info(f"✅ 文档向量化完成: {document.name}")
        
        return jsonify({
            'success': True,
            'data': {
                'document_id': doc_id,
                'document_name': document.name,
                'file_type': file_type,
                'vectorizer_used': vectorizer.__class__.__name__,
                'minio_path': object_name,
                'chunk_count': len(vectors_data),
                'vector_insert_success': vector_insert_success,
                'vectorized_at': document.vectorized_at.isoformat()
            }
        })
        
    except Exception as e:
        # 回滚数据库操作
        db.session.rollback()
        
        logger.error(f"文档向量化执行失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@vectorize_bp.route('/status/<int:doc_id>', methods=['GET'])
def get_vectorization_status(doc_id):
    """
    获取文档向量化状态
    """
    try:
        document = DocumentNode.query.get_or_404(doc_id)
        
        return jsonify({
            'success': True,
            'data': {
                'document_id': doc_id,
                'document_name': document.name,
                'is_vectorized': document.is_vectorized,
                'vector_status': document.vector_status,
                'vectorized_at': document.vectorized_at.isoformat() if document.vectorized_at else None,
                'minio_path': document.minio_path,
                'metadata': document.doc_metadata or {}
            }
        })
        
    except Exception as e:
        logger.error(f"获取向量化状态失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@vectorize_bp.route('/supported-types', methods=['GET'])
def get_supported_file_types():
    """
    获取支持的文件类型
    """
    try:
        info = vectorization_factory.get_vectorizer_info()
        
        return jsonify({
            'success': True,
            'data': info
        })
        
    except Exception as e:
        logger.error(f"获取支持的文件类型失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 