import os
import uuid
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import DocumentNode, DocumentContent, VectorRecord, SystemConfig, Tag, DocumentTag
import logging
from app.services.vectorization import VectorServiceAdapter
from app.services.vectorization.vectorization_factory import VectorizationFactory

logger = logging.getLogger(__name__)

upload_bp = Blueprint('upload', __name__)

# 文件类型映射
FILE_TYPE_MAPPING = {
    '.pdf': 'pdf',
    '.doc': 'word',
    '.docx': 'word',
    '.xls': 'excel',
    '.xlsx': 'excel',
    '.jpg': 'image',
    '.jpeg': 'image',
    '.png': 'image',
    '.gif': 'image',
    '.bmp': 'image',
    '.mp4': 'video',
    '.avi': 'video',
    '.mov': 'video',
    '.wmv': 'video',
    '.flv': 'video',
    '.mkv': 'video',
    '.txt': 'pdf'  # 临时将txt文件当作pdf处理
}

# 隐藏文件列表
HIDDEN_FILES = {
    '.DS_Store',
    'Thumbs.db',
    '.gitignore',
    '.git',
    '__MACOSX',
    '.svn',
    '.htaccess',
    'desktop.ini'
}

def is_hidden_file(filename):
    """检查是否为隐藏文件"""
    # 检查文件名是否在隐藏文件列表中
    if filename in HIDDEN_FILES:
        return True
    
    # 检查是否以点开头（Unix隐藏文件）
    if filename.startswith('.'):
        return True
    
    # 检查是否以~结尾（临时文件）
    if filename.endswith('~'):
        return True
    
    return False

def get_file_service(file_type):
    """根据文件类型获取对应的向量化器（替代空实现的service）"""
    # 创建向量化工厂
    factory = VectorizationFactory()
    
    # 根据文件类型获取对应的向量化器
    vectorizer = factory.get_vectorizer_by_type(file_type)
    
    if vectorizer:
        # 为向量化器添加兼容的方法，以便与现有代码兼容
        def extract_text_content_wrapper(file_path):
            return vectorizer.extract_text(file_path)
        
        def split_into_chunks_wrapper(text, chunk_size=512, overlap=50):
            return vectorizer.chunk_text(text, chunk_size, overlap)
        
        # 创建一个包装对象
        class VectorizerWrapper:
            def __init__(self, vectorizer):
                self.vectorizer = vectorizer
            
            def extract_text_content(self, file_path):
                return self.vectorizer.extract_text(file_path)
            
            def split_into_chunks(self, text, chunk_size=512, overlap=50):
                return self.vectorizer.chunk_text(text, chunk_size, overlap)
        
        return VectorizerWrapper(vectorizer)
    
    # 降级处理：如果没有找到对应的vectorizer，返回None
    logger.warning(f"未找到文件类型 {file_type} 对应的处理器")
    return None

def _add_tags_to_document(document_id, tag_ids):
    """为文档添加标签"""
    if not tag_ids:
        return
    
    # 验证标签是否存在
    existing_tags = Tag.query.filter(
        Tag.id.in_(tag_ids),
        Tag.is_deleted == False
    ).all()
    
    existing_tag_ids = [tag.id for tag in existing_tags]
    
    # 检查已经关联的标签，避免重复
    existing_associations = DocumentTag.query.filter(
        DocumentTag.document_id == document_id,
        DocumentTag.tag_id.in_(existing_tag_ids)
    ).all()
    
    already_associated_tag_ids = [assoc.tag_id for assoc in existing_associations]
    
    # 只添加还没有关联的标签
    for tag_id in existing_tag_ids:
        if tag_id not in already_associated_tag_ids:
            doc_tag = DocumentTag(document_id=document_id, tag_id=tag_id)
            db.session.add(doc_tag)

@upload_bp.route('/', methods=['POST'])
def upload_file():
    """上传文件"""
    try:
        # 检查请求中是否有文件
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': '没有选择文件'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': '没有选择文件'
            }), 400
        
        # 检查是否为隐藏文件
        if is_hidden_file(file.filename):
            return jsonify({
                'success': False,
                'error': f'不允许上传隐藏文件: {file.filename}'
            }), 400
        
        # 获取其他参数
        parent_id = request.form.get('parent_id', type=int)
        description = request.form.get('description', '')
        tag_ids_str = request.form.get('tag_ids', '')
        
        # 解析标签ID
        tag_ids = []
        if tag_ids_str:
            try:
                tag_ids = [int(x) for x in tag_ids_str.split(',') if x.strip()]
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': '标签ID格式错误'
                }), 400
        
        # 检查父节点
        if parent_id:
            parent = DocumentNode.query.get(parent_id)
            if not parent or parent.type != 'folder':
                return jsonify({
                    'success': False,
                    'error': '父节点必须是文件夹类型'
                }), 400
        
        # 获取文件信息
        original_filename = file.filename
        secure_name = secure_filename(file.filename)
        
        # 从原始文件名获取扩展名
        file_ext = os.path.splitext(original_filename)[1].lower()
        
        # 如果没有扩展名，尝试从secure_filename获取
        if not file_ext and secure_name:
            file_ext = os.path.splitext(secure_name)[1].lower()
        
        # 检查文件类型
        if file_ext not in FILE_TYPE_MAPPING:
            return jsonify({
                'success': False,
                'error': f'不支持的文件类型: {file_ext}'
            }), 400
        
        file_type = FILE_TYPE_MAPPING[file_ext]
        
        # 生成唯一文件名
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        
        # 保存文件
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        # 获取文件大小
        file_size = os.path.getsize(file_path)
        
        # 创建文档记录 - 使用原始文件名
        document = DocumentNode(
            name=original_filename,
            type='file',
            parent_id=parent_id,
            file_path=file_path,
            file_type=file_type,
            file_size=file_size,
            mime_type=file.mimetype,
            description=description
        )
        
        db.session.add(document)
        db.session.flush()  # 获取document.id
        
        # 添加标签
        _add_tags_to_document(document.id, tag_ids)
        
        db.session.commit()
        
        # 异步处理文件内容提取（这里简化为同步处理）
        try:
            _process_file_content(document.id, file_path, file_type)
        except Exception as e:
            logger.warning(f"文件内容处理失败: {str(e)}")
        
        # 重新查询以获取标签信息
        updated_doc = DocumentNode.query.get(document.id)
        
        # 自动触发后台向量化
        try:
            from app.routes.vectorize_routes import start_background_vectorization
            start_background_vectorization()
            logger.info("文件上传完成，已自动启动后台索引任务")
        except Exception as e:
            logger.warning(f"启动后台索引失败: {str(e)}")
        
        return jsonify({
            'success': True,
            'data': updated_doc.to_dict(),
            'message': '文件上传成功，已启动自动索引'
        })
        
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        db.session.rollback()
        # 清理已保存的文件
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@upload_bp.route('/process/<int:doc_id>', methods=['POST'])
def process_document(doc_id):
    """手动触发文档内容处理"""
    try:
        document = DocumentNode.query.get_or_404(doc_id)
        
        if document.type != 'file':
            return jsonify({
                'success': False,
                'error': '只能处理文件类型的文档'
            }), 400
        
        # 处理文件内容
        result = _process_file_content(document.id, document.file_path, document.file_type)
        
        return jsonify({
            'success': True,
            'data': result,
            'message': '文档处理完成'
        })
        
    except Exception as e:
        logger.error(f"文档处理失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@upload_bp.route('/vectorize/<int:doc_id>', methods=['POST'])
def vectorize_document():
    """向量化文档"""
    try:
        document = DocumentNode.query.get(doc_id)
        if not document:
            return jsonify({
                'success': False,
                'error': '文档不存在'
            }), 404
        
        if not document.contents:
            return jsonify({
                'success': False,
                'error': '文档还没有提取内容，请先处理文档'
            }), 400
        
        # 初始化向量服务
        milvus_host = SystemConfig.get_config('milvus_host', 'localhost')
        milvus_port = SystemConfig.get_config('milvus_port', 19530)
        embedding_model = SystemConfig.get_config('embedding_model')
        
        vector_service = VectorServiceAdapter(
            milvus_host=milvus_host,
            milvus_port=milvus_port,
            embedding_model=embedding_model
        )
        
        # 向量化每个内容块
        vectorized_count = 0
        for content in document.contents:
            if content.chunk_text:
                chunks = content.chunk_text.split('\n')
                chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
                
                if chunks:
                    try:
                        vector_ids = vector_service.insert_vectors(
                            document_id=document.id,
                            content_id=content.id,
                            chunks=chunks
                        )
                        
                        # 创建向量记录
                        for i, vector_id in enumerate(vector_ids):
                            vector_record = VectorRecord(
                                document_id=document.id,
                                content_id=content.id,
                                vector_id=vector_id,
                                embedding_model=embedding_model,
                                vector_status='completed'
                            )
                            db.session.add(vector_record)
                        
                        vectorized_count += len(vector_ids)
                        
                    except Exception as e:
                        logger.error(f"向量化内容块失败: {str(e)}")
                        # 创建失败记录
                        vector_record = VectorRecord(
                            document_id=document.id,
                            content_id=content.id,
                            embedding_model=embedding_model,
                            vector_status='failed',
                            error_message=str(e)
                        )
                        db.session.add(vector_record)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': {
                'vectorized_count': vectorized_count,
                'total_contents': len(document.contents)
            },
            'message': f'成功向量化 {vectorized_count} 个文本块'
        })
        
    except Exception as e:
        logger.error(f"向量化失败: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@upload_bp.route('/batch', methods=['POST'])
def upload_batch():
    """批量上传文件（支持文件夹上传）"""
    try:
        # 检查请求中是否有文件
        if 'files' not in request.files:
            return jsonify({
                'success': False,
                'error': '没有选择文件'
            }), 400
        
        files = request.files.getlist('files')
        if not files or len(files) == 0:
            return jsonify({
                'success': False,
                'error': '没有选择文件'
            }), 400
        
        # 获取其他参数
        parent_id = request.form.get('parent_id', type=int)
        description = request.form.get('description', '')
        file_paths = request.form.getlist('file_paths[]')  # 文件相对路径
        tag_ids_str = request.form.get('tag_ids', '')
        
        # 解析标签ID
        tag_ids = []
        if tag_ids_str:
            try:
                tag_ids = [int(x) for x in tag_ids_str.split(',') if x.strip()]
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': '标签ID格式错误'
                }), 400
        
        # 检查父节点
        if parent_id:
            parent = DocumentNode.query.get(parent_id)
            if not parent or parent.type != 'folder':
                return jsonify({
                    'success': False,
                    'error': '父节点必须是文件夹类型'
                }), 400
        
        uploaded_files = []
        created_folders = {}  # 缓存已创建的文件夹
        skipped_files = []  # 记录跳过的文件
        
        # 过滤隐藏文件并按文件路径深度排序，确保父文件夹先创建
        file_data = []
        for file, file_path in zip(files, file_paths):
            filename = file_path.split('/')[-1] if file_path else file.filename
            
            # 检查是否为隐藏文件
            if is_hidden_file(filename):
                skipped_files.append({
                    'name': filename,
                    'reason': '隐藏文件，已跳过'
                })
                continue
            
            file_data.append((file, file_path))
        
        file_data.sort(key=lambda x: x[1].count('/') if x[1] else 0)
        
        for file, file_path in file_data:
            try:
                # 解析文件路径
                path_parts = file_path.split('/') if file_path else [file.filename]
                filename = path_parts[-1]
                folder_path_parts = path_parts[:-1]
                
                # 再次检查文件名，防止路径中包含隐藏文件
                if is_hidden_file(filename):
                    skipped_files.append({
                        'name': filename,
                        'reason': '隐藏文件，已跳过'
                    })
                    continue
                
                # 创建文件夹层级
                current_parent_id = parent_id
                current_path = ""
                
                for folder_name in folder_path_parts:
                    if not folder_name:  # 跳过空名称
                        continue
                    
                    # 跳过隐藏文件夹
                    if is_hidden_file(folder_name):
                        break
                        
                    current_path = f"{current_path}/{folder_name}" if current_path else folder_name
                    
                    # 检查是否已创建该文件夹
                    if current_path not in created_folders:
                        # 检查数据库中是否已存在同名文件夹（必须过滤已删除的记录）
                        existing_folder = DocumentNode.query.filter_by(
                            name=folder_name,
                            type='folder',
                            parent_id=current_parent_id,
                            is_deleted=False  # 重要：过滤已删除的记录
                        ).first()
                        
                        if existing_folder:
                            folder_id = existing_folder.id
                            # 如果文件夹已存在，为其添加标签（合并标签）
                            if tag_ids:
                                _add_tags_to_document(existing_folder.id, tag_ids)
                        else:
                            # 创建新文件夹
                            folder = DocumentNode(
                                name=folder_name,
                                type='folder',
                                parent_id=current_parent_id,
                                description=f"从文件夹上传自动创建"
                            )
                            db.session.add(folder)
                            db.session.flush()  # 获取ID但不提交
                            folder_id = folder.id
                            
                            # 为新创建的文件夹添加标签
                            if tag_ids:
                                _add_tags_to_document(folder_id, tag_ids)
                        
                        created_folders[current_path] = folder_id
                    else:
                        folder_id = created_folders[current_path]
                    
                    current_parent_id = folder_id
                
                # 处理文件
                if file.filename and filename:
                    # 获取文件信息
                    original_filename = filename
                    secure_name = secure_filename(filename)
                    
                    # 从原始文件名获取扩展名
                    file_ext = os.path.splitext(original_filename)[1].lower()
                    
                    # 检查文件类型
                    if file_ext not in FILE_TYPE_MAPPING:
                        skipped_files.append({
                            'name': original_filename,
                            'reason': f'不支持的文件类型: {file_ext}'
                        })
                        continue
                    
                    file_type = FILE_TYPE_MAPPING[file_ext]
                    
                    # 生成唯一文件名
                    unique_filename = f"{uuid.uuid4()}{file_ext}"
                    
                    # 保存文件
                    upload_folder = current_app.config['UPLOAD_FOLDER']
                    os.makedirs(upload_folder, exist_ok=True)
                    file_save_path = os.path.join(upload_folder, unique_filename)
                    file.save(file_save_path)
                    
                    # 获取文件大小
                    file_size = os.path.getsize(file_save_path)
                    
                    # 创建文档记录
                    document = DocumentNode(
                        name=original_filename,
                        type='file',
                        parent_id=current_parent_id,
                        file_path=file_save_path,
                        file_type=file_type,
                        file_size=file_size,
                        mime_type=file.mimetype,
                        description=description
                    )
                    
                    db.session.add(document)
                    db.session.flush()  # 获取ID但不提交
                    
                    # 添加标签
                    _add_tags_to_document(document.id, tag_ids)
                    
                    uploaded_files.append({
                        'id': document.id,
                        'name': original_filename,
                        'path': file_path,
                        'size': file_size,
                        'type': file_type
                    })
                    
                    # 异步处理文件内容提取
                    try:
                        _process_file_content(document.id, file_save_path, file_type)
                    except Exception as e:
                        logger.warning(f"文件内容处理失败 {original_filename}: {str(e)}")
            
            except Exception as e:
                logger.error(f"处理文件失败 {file.filename}: {str(e)}")
                skipped_files.append({
                    'name': file.filename,
                    'reason': f'处理失败: {str(e)}'
                })
                continue
        
        # 提交所有更改
        db.session.commit()
        
        # 自动触发后台向量化
        try:
            from app.routes.vectorize_routes import start_background_vectorization
            start_background_vectorization()
            logger.info("批量上传完成，已自动启动后台索引任务")
        except Exception as e:
            logger.warning(f"启动后台索引失败: {str(e)}")
        
        result_message = f'批量上传完成，共上传 {len(uploaded_files)} 个文件，创建 {len(created_folders)} 个文件夹'
        if skipped_files:
            result_message += f'，跳过 {len(skipped_files)} 个文件'
        result_message += '，已启动自动索引'
        
        return jsonify({
            'success': True,
            'data': {
                'uploaded_files': uploaded_files,
                'created_folders': len(created_folders),
                'total_files': len(uploaded_files),
                'skipped_files': skipped_files
            },
            'message': result_message
        })
        
    except Exception as e:
        logger.error(f"批量上传失败: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def _process_file_content(document_id, file_path, file_type):
    """处理文件内容"""
    service = get_file_service(file_type)
    if not service:
        return {'success': False, 'error': f'不支持的文件类型: {file_type}'}
    
    # 提取文件内容
    extraction_result = service.extract_text_content(file_path)
    
    if not extraction_result.get('success'):
        return extraction_result
    
    # 保存提取的内容
    document = DocumentNode.query.get(document_id)
    
    # 清理旧内容
    DocumentContent.query.filter_by(document_id=document_id).delete()
    
    # 保存新内容
    if file_type == 'pdf':
        # PDF按页面保存
        pages = extraction_result.get('pages', [])
        for page_data in pages:
            content = DocumentContent(
                document_id=document_id,
                content_text=page_data['content'],
                page_number=page_data['page_number']
            )
            
            # 分块
            chunk_size = SystemConfig.get_config('chunk_size', 512)
            chunk_overlap = SystemConfig.get_config('chunk_overlap', 50)
            chunks = service.split_into_chunks(page_data['content'], chunk_size, chunk_overlap)
            
            if chunks:
                content.chunk_text = '\n'.join(chunks)
                
                # 为每个chunk创建记录
                for i, chunk in enumerate(chunks):
                    chunk_content = DocumentContent(
                        document_id=document_id,
                        page_number=page_data['page_number'],
                        chunk_index=i,
                        chunk_text=chunk
                    )
                    db.session.add(chunk_content)
            
            db.session.add(content)
    else:
        # 其他文件类型保存完整内容
        content = DocumentContent(
            document_id=document_id,
            content_text=extraction_result.get('content', '')
        )
        db.session.add(content)
    
    db.session.commit()
    
    return {
        'success': True,
        'extraction_result': extraction_result,
        'content_saved': True
    } 