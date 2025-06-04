"""
文档向量化路由
处理各种类型文档的向量化操作，支持内容识别和预览编辑
"""
from flask import Blueprint, request, jsonify
from app import db
from app.models import DocumentNode
from app.services.vectorization import VectorizationFactory
from app.services.minio_service import MinIOService
from app.services.image_recognition_service import ImageRecognitionService
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
image_recognition_service = ImageRecognitionService()

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
        
        # 获取请求参数
        request_data = request.get_json() or {}
        
        # 提取参数
        extract_params = {}
        
        # 通用参数
        chunk_size = request_data.get('chunk_size', 1000)
        overlap = request_data.get('overlap', 200)
        
        # 图片相关参数
        if file_type == 'image':
            extract_params['recognition_options'] = {
                'engine': request_data.get('recognition_engine', 'auto'),
                'languages': request_data.get('recognition_languages', ['zh', 'en'])
            }
        
        # PDF相关参数
        elif file_type == 'pdf':
            extract_params['extract_images'] = request_data.get('extract_images', True)
            extract_params['recognition_options'] = {
                'engine': request_data.get('recognition_engine', 'auto'),
                'languages': request_data.get('recognition_languages', ['zh', 'en'])
            }
        
        # Word相关参数
        elif file_type == 'word':
            extract_params['extract_images'] = request_data.get('extract_images', True)
            extract_params['recognition_options'] = {
                'engine': request_data.get('recognition_engine', 'auto'),
                'languages': request_data.get('recognition_languages', ['zh', 'en'])
            }
        
        # Excel相关参数
        elif file_type == 'excel':
            extract_params['analyze_data'] = request_data.get('analyze_data', True)
        
        # 提取文档内容
        extract_result = vectorizer.extract_text(document.file_path, **extract_params)
        
        if not extract_result['success']:
            return jsonify({
                'success': False,
                'error': f'文档处理失败: {extract_result.get("error", "未知错误")}'
            }), 500
        
        # 重新分段（如果用户指定了不同的参数）
        if request_data and ('chunk_size' in request_data or 'overlap' in request_data):
            chunks = vectorizer.chunk_text(
                extract_result['text'], 
                chunk_size=chunk_size, 
                overlap=overlap
            )
        else:
            chunks = extract_result.get('chunks', [])
        
        # 为每个分段生成ID和编辑状态
        chunks_with_id = []
        for i, chunk in enumerate(chunks):
            chunks_with_id.append({
                'id': f"chunk_{i}",
                'content': chunk,
                'editable': True,
                'original_content': chunk,  # 保存原始内容
                'modified': False
            })
        
        # 构建返回数据
        response_data = {
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
            'overlap': overlap,
            'extraction_options': extract_params
        }
        
        # 添加特定文件类型的额外信息
        if file_type == 'image':
            response_data['image_info'] = extract_result.get('recognition_result', {}).get('image_info', {})
            response_data['recognition_confidence'] = extract_result.get('recognition_result', {}).get('confidence', 0)
            response_data['recognition_engine'] = extract_result.get('recognition_result', {}).get('engine_used', '未知')
            response_data['available_engines'] = image_recognition_service.get_available_engines()
            response_data['supported_languages'] = image_recognition_service.get_supported_languages()
        
        elif file_type in ['pdf', 'word']:
            if extract_result.get('metadata', {}).get('total_images', 0) > 0:
                response_data['image_extraction_info'] = {
                    'total_images': extract_result['metadata'].get('total_images', 0),
                    'images_with_text': extract_result['metadata'].get('images_with_text', 0)
                }
            response_data['available_engines'] = image_recognition_service.get_available_engines()
            response_data['supported_languages'] = image_recognition_service.get_supported_languages()
        
        elif file_type == 'excel':
            if extract_result.get('metadata', {}).get('has_data_analysis'):
                response_data['data_analysis'] = extract_result['metadata'].get('data_summary', {})
        
        return jsonify({
            'success': True,
            'data': response_data
        })
        
    except Exception as e:
        logger.error(f"预览文档向量化失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@vectorize_bp.route('/recognition/options', methods=['GET'])
def get_recognition_options():
    """获取图像识别选项"""
    try:
        return jsonify({
            'success': True,
            'data': {
                'engines': image_recognition_service.get_available_engines(),
                'languages': image_recognition_service.get_supported_languages(),
                'default_engine': 'auto',
                'default_languages': ['zh', 'en']
            }
        })
    except Exception as e:
        logger.error(f"获取识别选项失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@vectorize_bp.route('/extract/image', methods=['POST'])
def extract_image_content():
    """单独提取图片内容（用于测试或预览）"""
    try:
        data = request.get_json()
        if not data or 'file_path' not in data:
            return jsonify({
                'success': False,
                'error': '缺少文件路径参数'
            }), 400
        
        file_path = data['file_path']
        engine = data.get('engine', 'auto')
        languages = data.get('languages', ['zh', 'en'])
        
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'error': '文件不存在'
            }), 404
        
        # 执行图像识别
        result = image_recognition_service.recognize_image(
            file_path, 
            engine=engine, 
            languages=languages
        )
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        logger.error(f"提取图片内容失败: {str(e)}")
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
        
        # 4. 更新文档状态
        if vector_insert_success:
            document.vectorized = True
            document.vectorized_at = datetime.now()
            db.session.commit()
            
            logger.info(f"文档向量化完成: {document.name}")
            
            return jsonify({
                'success': True,
                'data': {
                    'document_id': doc_id,
                    'document_name': document.name,
                    'minio_object': object_name,
                    'chunks_count': len(text_chunks),
                    'vectors_count': len(vectors_data),
                    'file_type': file_type,
                    'metadata': metadata,
                    'vectorized_at': document.vectorized_at.isoformat()
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': '向量数据插入失败'
            }), 500
            
    except Exception as e:
        logger.error(f"执行文档向量化失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@vectorize_bp.route('/status/<int:doc_id>', methods=['GET'])
def get_vectorization_status(doc_id):
    """获取文档向量化状态"""
    try:
        document = DocumentNode.query.get_or_404(doc_id)
        
        # 获取向量化器以检查向量数据库中的状态
        if document.file_path and vectorization_factory.is_supported_file(document.file_path):
            vectorizer = vectorization_factory.get_vectorizer(document.file_path)
            if vectorizer:
                vectorizer.initialize_vector_service()
                
                # 检查向量数据库中是否存在该文档的向量
                try:
                    from pymilvus import Collection
                    collection = Collection(vectorizer.collection_name)
                    
                    # 查询该文档ID的向量数量
                    results = collection.query(
                        expr=f'document_id == "{doc_id}"',
                        output_fields=["document_id"]
                    )
                    vector_count = len(results)
                except Exception as e:
                    logger.warning(f"查询向量数据失败: {e}")
                    vector_count = 0
            else:
                vector_count = 0
        else:
            vector_count = 0
        
        return jsonify({
            'success': True,
            'data': {
                'document_id': doc_id,
                'document_name': document.name,
                'file_type': vectorization_factory.get_file_type(document.file_path) if document.file_path else 'unknown',
                'is_vectorized': document.vectorized,
                'vectorized_at': document.vectorized_at.isoformat() if document.vectorized_at else None,
                'vector_count': vector_count,
                'is_supported': vectorization_factory.is_supported_file(document.file_path) if document.file_path else False
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
    """获取支持的文件类型"""
    try:
        supported_types = {}
        
        # 获取各个向量化器支持的扩展名
        for file_type, vectorizer_class in vectorization_factory._vectorizers.items():
            vectorizer = vectorizer_class()
            supported_types[file_type] = {
                'extensions': vectorizer.get_supported_extensions(),
                'vectorizer': vectorizer_class.__name__,
                'description': f'{file_type.upper()}文档向量化器'
            }
        
        return jsonify({
            'success': True,
            'data': {
                'supported_types': supported_types,
                'all_extensions': vectorization_factory.get_all_supported_extensions(),
                'image_recognition': {
                    'available_engines': image_recognition_service.get_available_engines(),
                    'supported_languages': image_recognition_service.get_supported_languages()
                }
            }
        })
        
    except Exception as e:
        logger.error(f"获取支持的文件类型失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 