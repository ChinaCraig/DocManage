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
        
        # 2. 生成向量数据（包含文档描述信息）
        text_chunks = [chunk.get('content', '').strip() for chunk in chunks if chunk.get('content', '').strip()]
        
        # 如果文档有描述信息，将其包含到向量化中
        if document.description and document.description.strip():
            enhanced_chunks = []
            for chunk in text_chunks:
                # 为每个chunk添加文档描述作为上下文
                enhanced_chunk = f"文档描述: {document.description.strip()}\n\n内容: {chunk}"
                enhanced_chunks.append(enhanced_chunk)
            vectors_data = vectorizer.generate_vectors_data(str(doc_id), text_chunks, enhanced_chunks)
        else:
            vectors_data = vectorizer.generate_vectors_data(str(doc_id), text_chunks)
        
        # 3. 插入向量数据到数据库
        vector_insert_success = False
        if vectors_data:
            vector_insert_success = vectorizer.insert_vectors(vectors_data)
        
        # 4. 更新文档状态
        if vector_insert_success:
            document.is_vectorized = True
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
                'is_vectorized': document.is_vectorized,
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

@vectorize_bp.route('/batch/stats', methods=['GET'])
def get_batch_vectorization_stats():
    """获取批量向量化统计信息"""
    try:
        # 获取节点ID参数，如果有则只查询该节点及其子节点下的文档
        node_id = request.args.get('node_id', type=int)
        
        if node_id:
            # 获取指定节点及其所有子节点的文档
            target_node = DocumentNode.query.get(node_id)
            if not target_node:
                return jsonify({
                    'success': False,
                    'error': '指定的节点不存在'
                }), 404
            
            # 递归获取所有子节点ID
            def get_all_child_ids(node):
                ids = []
                if node.type == 'file':
                    ids.append(node.id)
                else:
                    # 文件夹节点，获取其所有子节点
                    for child in node.children:
                        if not child.is_deleted:
                            ids.extend(get_all_child_ids(child))
                return ids
            
            file_ids = get_all_child_ids(target_node)
            if file_ids:
                all_files = DocumentNode.query.filter(
                    DocumentNode.id.in_(file_ids),
                    DocumentNode.type == 'file',
                    DocumentNode.is_deleted == False
                ).all()
            else:
                all_files = []
        else:
            # 获取所有文件类型的文档
            all_files = DocumentNode.query.filter_by(type='file', is_deleted=False).all()
        
        # 过滤支持向量化的文件
        supported_files = []
        for doc in all_files:
            if doc.file_path and vectorization_factory.is_supported_file(doc.file_path):
                supported_files.append(doc)
        
        # 统计向量化状态
        vectorized_count = sum(1 for doc in supported_files if doc.is_vectorized)
        not_vectorized_count = len(supported_files) - vectorized_count
        
        # 获取未向量化文档列表
        not_vectorized_docs = []
        for doc in supported_files:
            if not doc.is_vectorized:
                not_vectorized_docs.append({
                    'id': doc.id,
                    'name': doc.name,
                    'file_type': vectorization_factory.get_file_type(doc.file_path),
                    'file_size': doc.file_size,
                    'created_at': doc.created_at.isoformat() if doc.created_at else None
                })
        
        return jsonify({
            'success': True,
            'data': {
                'total_files': len(all_files),
                'supported_files': len(supported_files),
                'vectorized_count': vectorized_count,
                'not_vectorized_count': not_vectorized_count,
                'not_vectorized_docs': not_vectorized_docs,
                'supported_types': vectorization_factory.get_all_supported_extensions()
            }
        })
        
    except Exception as e:
        logger.error(f"获取批量向量化统计信息失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@vectorize_bp.route('/batch/execute', methods=['POST'])
def execute_batch_vectorization():
    """执行批量向量化"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '缺少请求数据'
            }), 400
        
        chunk_size = data.get('chunk_size', 1000)
        overlap = data.get('overlap', 200)
        doc_ids = data.get('doc_ids', [])
        node_id = data.get('node_id')
        
        # 验证参数
        if chunk_size < 100 or chunk_size > 5000:
            return jsonify({
                'success': False,
                'error': '分段字符长度必须在100-5000之间'
            }), 400
            
        if overlap < 0 or overlap > 500:
            return jsonify({
                'success': False,
                'error': '重叠字符数必须在0-500之间'
            }), 400
        
        # 如果没有指定文档ID，则获取未向量化的文档
        if not doc_ids:
            if node_id:
                # 获取指定节点及其所有子节点的未向量化文档
                target_node = DocumentNode.query.get(node_id)
                if not target_node:
                    return jsonify({
                        'success': False,
                        'error': '指定的节点不存在'
                    }), 400
                
                # 递归获取所有子节点ID
                def get_all_child_ids(node):
                    ids = []
                    if node.type == 'file':
                        ids.append(node.id)
                    else:
                        # 文件夹节点，获取其所有子节点
                        for child in node.children:
                            if not child.is_deleted:
                                ids.extend(get_all_child_ids(child))
                    return ids
                
                file_ids = get_all_child_ids(target_node)
                if file_ids:
                    all_docs = DocumentNode.query.filter(
                        DocumentNode.id.in_(file_ids),
                        DocumentNode.type == 'file',
                        DocumentNode.is_deleted == False,
                        DocumentNode.is_vectorized == False
                    ).all()
                else:
                    all_docs = []
            else:
                # 获取所有未向量化的文档
                all_docs = DocumentNode.query.filter_by(
                    type='file', 
                    is_deleted=False, 
                    is_vectorized=False
                ).all()
            
            # 过滤支持向量化的文件
            doc_ids = []
            for doc in all_docs:
                if doc.file_path and vectorization_factory.is_supported_file(doc.file_path):
                    doc_ids.append(doc.id)
        
        if not doc_ids:
            return jsonify({
                'success': False,
                'error': '没有找到需要向量化的文档'
            }), 400
        
        # 更新文档状态为处理中
        for doc_id in doc_ids:
            document = DocumentNode.query.get(doc_id)
            if document:
                document.vector_status = 'processing'
        db.session.commit()
        
        # 启动后台任务进行批量向量化
        from threading import Thread
        from flask import current_app
        app = current_app._get_current_object()  # 获取真实的app对象
        thread = Thread(target=process_batch_vectorization, args=(app, doc_ids, chunk_size, overlap))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'data': {
                'total_docs': len(doc_ids),
                'chunk_size': chunk_size,
                'overlap': overlap,
                'message': '批量向量化任务已启动，请等待处理完成'
            }
        })
        
    except Exception as e:
        logger.error(f"启动批量向量化失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@vectorize_bp.route('/batch/progress', methods=['GET'])
def get_batch_progress():
    """获取批量向量化进度"""
    try:
        # 获取正在处理的文档
        processing_docs = DocumentNode.query.filter_by(
            type='file',
            is_deleted=False,
            vector_status='processing'
        ).all()
        
        # 获取已完成和失败的文档
        completed_docs = DocumentNode.query.filter_by(
            type='file',
            is_deleted=False,
            is_vectorized=True
        ).count()
        
        failed_docs = DocumentNode.query.filter_by(
            type='file',
            is_deleted=False,
            vector_status='failed'
        ).all()
        
        return jsonify({
            'success': True,
            'data': {
                'processing_count': len(processing_docs),
                'completed_count': completed_docs,
                'failed_count': len(failed_docs),
                'processing_docs': [
                    {
                        'id': doc.id,
                        'name': doc.name,
                        'file_type': vectorization_factory.get_file_type(doc.file_path) if doc.file_path else 'unknown'
                    }
                    for doc in processing_docs
                ],
                'failed_docs': [
                    {
                        'id': doc.id,
                        'name': doc.name,
                        'file_type': vectorization_factory.get_file_type(doc.file_path) if doc.file_path else 'unknown'
                    }
                    for doc in failed_docs
                ]
            }
        })
        
    except Exception as e:
        logger.error(f"获取批量向量化进度失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def process_batch_vectorization(app, doc_ids, chunk_size, overlap):
    """后台处理批量向量化"""
    with app.app_context():
        for doc_id in doc_ids:
            try:
                document = DocumentNode.query.get(doc_id)
                if not document or document.is_vectorized:
                    continue
                
                logger.info(f"开始向量化文档: {document.name}")
                
                # 获取向量化器
                vectorizer = vectorization_factory.get_vectorizer(document.file_path)
                if not vectorizer:
                    logger.error(f"无法获取向量化器: {document.name}")
                    document.vector_status = 'failed'
                    db.session.commit()
                    continue
                
                # 初始化向量服务
                vectorizer.initialize_vector_service()
                
                # 提取文档内容
                extract_result = vectorizer.extract_text(document.file_path)
                if not extract_result['success']:
                    logger.error(f"提取文档内容失败: {document.name}")
                    document.vector_status = 'failed'
                    db.session.commit()
                    continue
                
                # 分段处理
                chunks = vectorizer.chunk_text(
                    extract_result['text'],
                    chunk_size=chunk_size,
                    overlap=overlap
                )
                
                if not chunks:
                    logger.error(f"文档分段失败: {document.name}")
                    document.vector_status = 'failed'
                    db.session.commit()
                    continue
                
                # 上传文件到MinIO
                if minio_service.is_available:
                    filename = document.name
                    timestamp = datetime.now().strftime('%Y/%m/%d')
                    unique_id = str(uuid.uuid4())
                    file_type = vectorization_factory.get_file_type(document.file_path)
                    object_name = f"documents/{file_type}/{timestamp}/{unique_id}_{filename}"
                    
                    minio_result = minio_service.upload_file(document.file_path, object_name)
                    if minio_result['success']:
                        document.minio_path = object_name
                
                # 生成向量数据
                if document.description and document.description.strip():
                    enhanced_chunks = []
                    for chunk in chunks:
                        enhanced_chunk = f"文档描述: {document.description.strip()}\n\n内容: {chunk}"
                        enhanced_chunks.append(enhanced_chunk)
                    vectors_data = vectorizer.generate_vectors_data(str(doc_id), chunks, enhanced_chunks)
                else:
                    vectors_data = vectorizer.generate_vectors_data(str(doc_id), chunks)
                
                # 插入向量数据
                if vectors_data and vectorizer.insert_vectors(vectors_data):
                    document.is_vectorized = True
                    document.vector_status = 'completed'
                    document.vectorized_at = datetime.now()
                    logger.info(f"文档向量化完成: {document.name}")
                else:
                    document.vector_status = 'failed'
                    logger.error(f"向量数据插入失败: {document.name}")
                
                db.session.commit()
                
            except Exception as e:
                logger.error(f"处理文档向量化失败 {doc_id}: {str(e)}")
                try:
                    document = DocumentNode.query.get(doc_id)
                    if document:
                        document.vector_status = 'failed'
                        db.session.commit()
                except:
                    pass 