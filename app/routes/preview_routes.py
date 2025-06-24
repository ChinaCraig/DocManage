from flask import Blueprint, jsonify, send_file, abort
from app.models import DocumentNode
from app.services.preview import PreviewServiceFactory
import logging
import os

logger = logging.getLogger(__name__)

preview_bp = Blueprint('preview', __name__)

@preview_bp.route('/pdf/<int:doc_id>', methods=['GET'])
def preview_pdf(doc_id):
    """PDF文档预览（文本提取）"""
    try:
        # 获取文档信息
        document = DocumentNode.query.get_or_404(doc_id)
        
        if document.is_deleted or document.type != 'file':
            abort(404)
        
        # 检查文件类型
        if document.file_type.lower() != 'pdf':
            return jsonify({
                'success': False,
                'error': '文档类型不匹配'
            }), 400
        
        # 获取预览服务
        preview_service = PreviewServiceFactory.get_service('pdf')
        
        # 提取文档内容，对于MCP创建的文件传递document_id
        content_data = preview_service.extract_content(document.file_path, document.id)
        
        return jsonify({
            'success': True,
            'data': {
                'content': content_data.get('text', ''),
                'pages': content_data.get('pages', 0),
                'metadata': content_data.get('metadata', {})
            }
        })
        
    except Exception as e:
        logger.error(f"PDF预览失败 - 文档ID: {doc_id}, 错误: {str(e)}")
        return jsonify({
            'success': False,
            'error': '预览失败'
        }), 500

@preview_bp.route('/pdf/raw/<int:doc_id>', methods=['GET'])
def preview_pdf_raw(doc_id):
    """PDF文档原始文件预览"""
    try:
        logger.info(f"开始处理PDF原始文件预览请求 - 文档ID: {doc_id}")
        
        # 获取文档信息
        document = DocumentNode.query.get_or_404(doc_id)
        logger.info(f"找到文档: {document.name}, 类型: {document.file_type}")
        
        if document.is_deleted or document.type != 'file':
            logger.warning(f"文档已删除或不是文件 - ID: {doc_id}")
            abort(404)
        
        # 检查文件类型
        file_type = document.file_type.lower()
        logger.info(f"文件类型: {file_type}")
        
        if file_type != 'pdf':
            logger.warning(f"文件类型不匹配 - 期望PDF，实际: {file_type}")
            abort(400)
        
        # 检查文件是否存在
        logger.info(f"检查文件路径: {document.file_path}")
        if not os.path.exists(document.file_path):
            logger.error(f"文件不存在: {document.file_path}")
            abort(404)
        
        logger.info(f"文件存在，准备返回PDF文件: {document.file_path}")
        
        # 直接返回PDF文件
        try:
            # 使用绝对路径
            abs_path = os.path.abspath(document.file_path)
            logger.info(f"使用绝对路径: {abs_path}")
            
            return send_file(abs_path, 
                           as_attachment=False,
                           mimetype='application/pdf')
        except Exception as send_error:
            logger.error(f"send_file失败: {send_error}")
            raise
        
    except Exception as e:
        logger.error(f"PDF原始文件预览失败 - 文档ID: {doc_id}, 错误: {str(e)}")
        logger.error(f"错误详情: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"堆栈跟踪: {traceback.format_exc()}")
        abort(500)

@preview_bp.route('/word/<int:doc_id>', methods=['GET'])
def preview_word(doc_id):
    """Word文档预览（文本提取）"""
    try:
        # 获取文档信息
        document = DocumentNode.query.get_or_404(doc_id)
        
        if document.is_deleted or document.type != 'file':
            abort(404)
        
        # 检查文件类型
        file_type = document.file_type.lower()
        if file_type not in ['word', 'docx', 'doc']:
            return jsonify({
                'success': False,
                'error': '文档类型不匹配'
            }), 400
        
        # 获取预览服务
        preview_service = PreviewServiceFactory.get_service('word')
        
        # 提取文档内容，对于MCP创建的文件传递document_id
        content_data = preview_service.extract_content(document.file_path, document.id)
        
        return jsonify({
            'success': True,
            'data': {
                'content': content_data.get('text', ''),
                'images': content_data.get('images', []),
                'metadata': content_data.get('metadata', {})
            }
        })
        
    except Exception as e:
        logger.error(f"Word预览失败 - 文档ID: {doc_id}, 错误: {str(e)}")
        return jsonify({
            'success': False,
            'error': '预览失败'
        }), 500

@preview_bp.route('/word/raw/<int:doc_id>', methods=['GET'])
def preview_word_raw(doc_id):
    """Word文档原始文件预览"""
    try:
        logger.info(f"开始处理Word原始文件预览请求 - 文档ID: {doc_id}")
        
        # 获取文档信息
        document = DocumentNode.query.get_or_404(doc_id)
        logger.info(f"找到文档: {document.name}, 类型: {document.file_type}")
        
        if document.is_deleted or document.type != 'file':
            logger.warning(f"文档已删除或不是文件 - ID: {doc_id}")
            abort(404)
        
        # 检查文件类型
        file_type = document.file_type.lower()
        logger.info(f"文件类型: {file_type}")
        
        if file_type not in ['word', 'docx', 'doc']:
            logger.warning(f"文件类型不匹配 - 期望Word文档，实际: {file_type}")
            abort(400)
        
        # 检查文件是否存在
        logger.info(f"检查文件路径: {document.file_path}")
        if not os.path.exists(document.file_path):
            logger.error(f"文件不存在: {document.file_path}")
            abort(404)
        
        logger.info(f"文件存在，准备返回Word文件: {document.file_path}")
        
        # 直接返回Word文件
        try:
            # 使用绝对路径
            abs_path = os.path.abspath(document.file_path)
            logger.info(f"使用绝对路径: {abs_path}")
            
            # 根据文件扩展名设置MIME类型
            if file_type in ['docx', 'word']:
                mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            else:  # doc
                mimetype = 'application/msword'
            
            return send_file(abs_path, 
                           as_attachment=False,
                           mimetype=mimetype)
        except Exception as send_error:
            logger.error(f"send_file失败: {send_error}")
            raise
        
    except Exception as e:
        logger.error(f"Word原始文件预览失败 - 文档ID: {doc_id}, 错误: {str(e)}")
        logger.error(f"错误详情: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"堆栈跟踪: {traceback.format_exc()}")
        abort(500)

@preview_bp.route('/excel/<int:doc_id>', methods=['GET'])
def preview_excel(doc_id):
    """Excel文档预览（文本提取）"""
    try:
        # 获取文档信息
        document = DocumentNode.query.get_or_404(doc_id)
        
        if document.is_deleted or document.type != 'file':
            abort(404)
        
        # 检查文件类型
        file_type = document.file_type.lower()
        if file_type not in ['excel', 'xlsx', 'xls']:
            return jsonify({
                'success': False,
                'error': '文档类型不匹配'
            }), 400
        
        # 获取预览服务
        preview_service = PreviewServiceFactory.get_service('excel')
        
        # 提取文档内容，对于MCP创建的文件传递document_id
        content_data = preview_service.extract_content(document.file_path, document.id)
        
        return jsonify({
            'success': True,
            'data': {
                'sheets': content_data.get('sheets', []),
                'metadata': content_data.get('metadata', {})
            }
        })
        
    except Exception as e:
        logger.error(f"Excel预览失败 - 文档ID: {doc_id}, 错误: {str(e)}")
        return jsonify({
            'success': False,
            'error': '预览失败'
        }), 500

@preview_bp.route('/excel/raw/<int:doc_id>', methods=['GET'])
def preview_excel_raw(doc_id):
    """Excel文档原始文件预览"""
    try:
        logger.info(f"开始处理Excel原始文件预览请求 - 文档ID: {doc_id}")
        
        # 获取文档信息
        document = DocumentNode.query.get_or_404(doc_id)
        logger.info(f"找到文档: {document.name}, 类型: {document.file_type}")
        
        if document.is_deleted or document.type != 'file':
            logger.warning(f"文档已删除或不是文件 - ID: {doc_id}")
            abort(404)
        
        # 检查文件类型
        file_type = document.file_type.lower()
        logger.info(f"文件类型: {file_type}")
        
        if file_type not in ['excel', 'xlsx', 'xls']:
            logger.warning(f"文件类型不匹配 - 期望Excel文档，实际: {file_type}")
            abort(400)
        
        # 检查文件是否存在
        logger.info(f"检查文件路径: {document.file_path}")
        if not os.path.exists(document.file_path):
            logger.error(f"文件不存在: {document.file_path}")
            abort(404)
        
        logger.info(f"文件存在，准备返回Excel文件: {document.file_path}")
        
        # 直接返回Excel文件
        try:
            # 使用绝对路径
            abs_path = os.path.abspath(document.file_path)
            logger.info(f"使用绝对路径: {abs_path}")
            
            # 根据文件扩展名设置MIME类型
            if file_type in ['xlsx', 'excel']:
                mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            else:  # xls
                mimetype = 'application/vnd.ms-excel'
            
            return send_file(abs_path, 
                           as_attachment=False,
                           mimetype=mimetype)
        except Exception as send_error:
            logger.error(f"send_file失败: {send_error}")
            raise
        
    except Exception as e:
        logger.error(f"Excel原始文件预览失败 - 文档ID: {doc_id}, 错误: {str(e)}")
        logger.error(f"错误详情: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"堆栈跟踪: {traceback.format_exc()}")
        abort(500)

@preview_bp.route('/image/<int:doc_id>', methods=['GET'])
def preview_image(doc_id):
    """图片文件预览"""
    try:
        logger.info(f"开始处理图片预览请求 - 文档ID: {doc_id}")
        
        # 获取文档信息
        document = DocumentNode.query.get_or_404(doc_id)
        logger.info(f"找到文档: {document.name}, 类型: {document.file_type}")
        
        if document.is_deleted or document.type != 'file':
            logger.warning(f"文档已删除或不是文件 - ID: {doc_id}")
            abort(404)
        
        # 检查文件类型 - 支持通用类型和具体扩展名
        file_type = document.file_type.lower()
        logger.info(f"文件类型: {file_type}")
        
        if file_type not in ['image', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp']:
            logger.warning(f"文件类型不匹配 - 期望图片类型，实际: {file_type}")
            return jsonify({
                'success': False,
                'error': '文档类型不匹配'
            }), 400
        
        # 检查文件是否存在
        logger.info(f"检查文件路径: {document.file_path}")
        if not os.path.exists(document.file_path):
            logger.error(f"文件不存在: {document.file_path}")
            abort(404)
        
        logger.info(f"文件存在，准备返回文件: {document.file_path}")
        
        # 直接返回图片文件
        try:
            # 使用绝对路径
            abs_path = os.path.abspath(document.file_path)
            logger.info(f"使用绝对路径: {abs_path}")
            
            return send_file(abs_path, as_attachment=False)
        except Exception as send_error:
            logger.error(f"send_file失败: {send_error}")
            raise
        
    except Exception as e:
        logger.error(f"图片预览失败 - 文档ID: {doc_id}, 错误: {str(e)}")
        logger.error(f"错误详情: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"堆栈跟踪: {traceback.format_exc()}")
        abort(500)

@preview_bp.route('/video/<int:doc_id>', methods=['GET'])
def preview_video(doc_id):
    """视频文件预览"""
    try:
        logger.info(f"开始处理视频预览请求 - 文档ID: {doc_id}")
        
        # 获取文档信息
        document = DocumentNode.query.get_or_404(doc_id)
        logger.info(f"找到文档: {document.name}, 类型: {document.file_type}")
        
        if document.is_deleted or document.type != 'file':
            logger.warning(f"文档已删除或不是文件 - ID: {doc_id}")
            abort(404)
        
        # 检查文件类型 - 支持通用类型和具体扩展名
        file_type = document.file_type.lower()
        logger.info(f"文件类型: {file_type}")
        
        if file_type not in ['video', 'mp4', 'avi', 'mov', 'wmv', 'mkv', 'flv', 'webm']:
            logger.warning(f"文件类型不匹配 - 期望视频类型，实际: {file_type}")
            return jsonify({
                'success': False,
                'error': '文档类型不匹配'
            }), 400
        
        # 检查文件是否存在
        logger.info(f"检查文件路径: {document.file_path}")
        if not os.path.exists(document.file_path):
            logger.error(f"文件不存在: {document.file_path}")
            abort(404)
        
        logger.info(f"文件存在，准备返回文件: {document.file_path}")
        
        # 直接返回视频文件
        try:
            # 使用绝对路径
            abs_path = os.path.abspath(document.file_path)
            logger.info(f"使用绝对路径: {abs_path}")
            
            return send_file(abs_path, as_attachment=False)
        except Exception as send_error:
            logger.error(f"send_file失败: {send_error}")
            raise
        
    except Exception as e:
        logger.error(f"视频预览失败 - 文档ID: {doc_id}, 错误: {str(e)}")
        logger.error(f"错误详情: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"堆栈跟踪: {traceback.format_exc()}")
        abort(500)

@preview_bp.route('/thumbnail/<int:doc_id>', methods=['GET'])
def get_thumbnail(doc_id):
    """获取文档缩略图"""
    try:
        # 获取文档信息
        document = DocumentNode.query.get_or_404(doc_id)
        
        if document.is_deleted or document.type != 'file':
            abort(404)
        
        # 获取预览服务
        file_type = document.file_type.lower()
        
        # 图片类型直接返回缩放版本
        if file_type in ['image', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp']:
            preview_service = PreviewServiceFactory.get_service('image')
            thumbnail_path = preview_service.generate_thumbnail(document.file_path)
            
            if thumbnail_path and os.path.exists(thumbnail_path):
                return send_file(thumbnail_path)
        
        # PDF生成缩略图
        elif file_type == 'pdf':
            preview_service = PreviewServiceFactory.get_service('pdf')
            thumbnail_path = preview_service.generate_thumbnail(document.file_path)
            
            if thumbnail_path and os.path.exists(thumbnail_path):
                return send_file(thumbnail_path)
        
        # 其他类型返回默认图标
        else:
            # 返回默认文件图标
            abort(404)
        
    except Exception as e:
        logger.error(f"缩略图生成失败 - 文档ID: {doc_id}, 错误: {str(e)}")
        abort(500)

@preview_bp.route('/metadata/<int:doc_id>', methods=['GET'])
def get_document_metadata(doc_id):
    """获取文档元数据"""
    try:
        # 获取文档信息
        document = DocumentNode.query.get_or_404(doc_id)
        
        if document.is_deleted or document.type != 'file':
            abort(404)
        
        # 获取预览服务
        file_type = document.file_type.lower()
        
        # 根据文件类型获取相应的预览服务
        service_type = None
        if file_type == 'pdf':
            service_type = 'pdf'
        elif file_type in ['word', 'docx', 'doc']:
            service_type = 'word'
        elif file_type in ['excel', 'xlsx', 'xls']:
            service_type = 'excel'
        elif file_type in ['image', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp']:
            service_type = 'image'
        elif file_type in ['video', 'mp4', 'avi', 'mov', 'wmv', 'mkv', 'flv', 'webm']:
            service_type = 'video'
        elif file_type in ['txt', 'text', 'log', 'md', 'markdown', 'csv', 'json', 'xml', 'py', 'js', 'html', 'css', 'sql']:
            service_type = 'text'
        
        if service_type:
            preview_service = PreviewServiceFactory.get_service(service_type)
            metadata = preview_service.get_metadata(document.file_path)
            
            return jsonify({
                'success': True,
                'data': metadata
            })
        else:
            return jsonify({
                'success': False,
                'error': '不支持的文件类型'
            }), 400
        
    except Exception as e:
        logger.error(f"获取元数据失败 - 文档ID: {doc_id}, 错误: {str(e)}")
        return jsonify({
            'success': False,
            'error': '获取元数据失败'
        }), 500

@preview_bp.route('/text/<int:doc_id>', methods=['GET'])
def preview_text(doc_id):
    """文本文件预览（内容提取）"""
    try:
        # 获取文档信息
        document = DocumentNode.query.get_or_404(doc_id)
        
        if document.is_deleted or document.type != 'file':
            abort(404)
        
        # 检查文件类型
        file_type = document.file_type.lower()
        if file_type not in ['txt', 'text', 'log', 'md', 'markdown', 'csv', 'json', 'xml', 'py', 'js', 'html', 'css', 'sql']:
            return jsonify({
                'success': False,
                'error': '文档类型不匹配'
            }), 400
        
        # 获取预览服务
        preview_service = PreviewServiceFactory.get_service('text')
        
        # 提取文档内容，对于MCP创建的文件传递document_id
        content_data = preview_service.extract_content(document.file_path, document.id)
        
        return jsonify({
            'success': True,
            'data': {
                'content': content_data.get('content', ''),
                'encoding': content_data.get('encoding', 'utf-8'),
                'is_truncated': content_data.get('is_truncated', False),
                'metadata': content_data.get('metadata', {})
            }
        })
        
    except Exception as e:
        logger.error(f"文本文件预览失败 - 文档ID: {doc_id}, 错误: {str(e)}")
        return jsonify({
            'success': False,
            'error': '预览失败'
        }), 500

@preview_bp.route('/text/raw/<int:doc_id>', methods=['GET'])
def preview_text_raw(doc_id):
    """文本文件原始文件预览"""
    try:
        logger.info(f"开始处理文本文件原始预览请求 - 文档ID: {doc_id}")
        
        # 获取文档信息
        document = DocumentNode.query.get_or_404(doc_id)
        logger.info(f"找到文档: {document.name}, 类型: {document.file_type}")
        
        if document.is_deleted or document.type != 'file':
            logger.warning(f"文档已删除或不是文件 - ID: {doc_id}")
            abort(404)
        
        # 检查文件类型
        file_type = document.file_type.lower()
        logger.info(f"文件类型: {file_type}")
        
        if file_type not in ['txt', 'text', 'log', 'md', 'markdown', 'csv', 'json', 'xml', 'py', 'js', 'html', 'css', 'sql']:
            logger.warning(f"文件类型不匹配 - 期望文本类型，实际: {file_type}")
            abort(400)
        
        # 检查文件是否存在，对于MCP创建的文件特殊处理
        logger.info(f"检查文件路径: {document.file_path}")
        
        # 如果是MCP创建的虚拟文件，从数据库获取内容
        if document.file_path.startswith('mcp_created/'):
            logger.info(f"检测到MCP创建的文件，从数据库获取内容: {document.file_path}")
            
            from app.models.document_models import DocumentContent
            from flask import Response
            
            content_record = DocumentContent.query.filter_by(document_id=document.id).first()
            
            if content_record and content_record.content_text:
                content = content_record.content_text
                
                # 根据文件扩展名设置MIME类型
                import mimetypes
                mime_type, _ = mimetypes.guess_type(document.name)
                if not mime_type:
                    mime_type = 'text/plain'
                
                return Response(
                    content,
                    mimetype=mime_type,
                    headers={
                        'Content-Disposition': f'inline; filename="{document.name}"',
                        'Content-Type': f'{mime_type}; charset=utf-8'
                    }
                )
            else:
                logger.warning(f"MCP文件没有内容记录: {document.file_path}")
                return Response(
                    "",  # 空内容
                    mimetype='text/plain',
                    headers={
                        'Content-Disposition': f'inline; filename="{document.name}"',
                        'Content-Type': 'text/plain; charset=utf-8'
                    }
                )
        
        if not os.path.exists(document.file_path):
            logger.error(f"文件不存在: {document.file_path}")
            abort(404)
        
        logger.info(f"文件存在，准备返回文本文件: {document.file_path}")
        
        # 直接返回文本文件
        try:
            # 使用绝对路径
            abs_path = os.path.abspath(document.file_path)
            logger.info(f"使用绝对路径: {abs_path}")
            
            # 根据文件扩展名设置MIME类型
            import mimetypes
            mime_type, _ = mimetypes.guess_type(abs_path)
            if not mime_type:
                mime_type = 'text/plain'
            
            return send_file(abs_path, 
                           as_attachment=False,
                           mimetype=mime_type)
        except Exception as send_error:
            logger.error(f"send_file失败: {send_error}")
            raise
        
    except Exception as e:
        logger.error(f"文本文件原始预览失败 - 文档ID: {doc_id}, 错误: {str(e)}")
        logger.error(f"错误详情: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"堆栈跟踪: {traceback.format_exc()}")
        abort(500)

@preview_bp.route('/text/<int:doc_id>', methods=['POST'])
def save_text(doc_id):
    """保存文本文件内容"""
    try:
        from flask import request
        from app import db
        from datetime import datetime
        
        # 获取请求数据
        data = request.get_json()
        if not data or 'content' not in data:
            return jsonify({
                'success': False,
                'error': '缺少文件内容'
            }), 400
        
        content = data['content']
        
        # 获取文档信息
        document = DocumentNode.query.get_or_404(doc_id)
        
        if document.is_deleted or document.type != 'file':
            abort(404)
        
        # 检查文件类型
        file_type = document.file_type.lower()
        if file_type not in ['txt', 'text', 'log', 'md', 'markdown', 'csv', 'json', 'xml', 'py', 'js', 'html', 'css', 'sql']:
            return jsonify({
                'success': False,
                'error': '该文件类型不支持编辑'
            }), 400
        
        # 保存文件内容，对于MCP创建的文件特殊处理
        try:
            if document.file_path.startswith('mcp_created/'):
                # MCP创建的文件，保存到数据库
                logger.info(f"保存MCP文件到数据库: {document.file_path}")
                
                from app.models.document_models import DocumentContent
                
                # 查找或创建内容记录
                content_record = DocumentContent.query.filter_by(document_id=document.id).first()
                
                if content_record:
                    # 更新现有记录
                    content_record.content_text = content
                    content_record.chunk_text = content
                    content_record.updated_at = datetime.utcnow()
                else:
                    # 创建新记录
                    content_record = DocumentContent(
                        document_id=document.id,
                        content_text=content,
                        page_number=1,
                        chunk_index=0,
                        chunk_text=content
                    )
                    db.session.add(content_record)
                
                # 更新文件大小
                new_size = len(content.encode('utf-8'))
                document.file_size = new_size
                
                # 更新修改时间
                document.updated_at = datetime.utcnow()
                
                # 保存到数据库
                db.session.commit()
                
                logger.info(f"MCP文本文件保存成功 - 文档ID: {doc_id}, 新大小: {new_size} 字节")
                
                return jsonify({
                    'success': True,
                    'data': {
                        'message': '文件保存成功',
                        'file_size': new_size,
                        'updated_at': document.updated_at.isoformat(),
                        'source': 'mcp_database'
                    }
                })
            else:
                # 普通文件，保存到文件系统
                if not os.path.exists(document.file_path):
                    return jsonify({
                        'success': False,
                        'error': '文件不存在'
                    }), 404
                
                with open(document.file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                # 更新文件大小
                new_size = os.path.getsize(document.file_path)
                document.file_size = new_size
                
                # 更新修改时间
                document.updated_at = datetime.utcnow()
                
                # 保存到数据库
                db.session.commit()
                
                logger.info(f"文本文件保存成功 - 文档ID: {doc_id}, 新大小: {new_size} 字节")
                
                return jsonify({
                    'success': True,
                    'data': {
                        'message': '文件保存成功',
                        'file_size': new_size,
                        'updated_at': document.updated_at.isoformat(),
                        'source': 'filesystem'
                    }
                })
            
        except Exception as write_error:
            logger.error(f"写入文件失败 - 文档ID: {doc_id}, 错误: {str(write_error)}")
            return jsonify({
                'success': False,
                'error': '文件保存失败'
            }), 500
        
    except Exception as e:
        logger.error(f"保存文本文件失败 - 文档ID: {doc_id}, 错误: {str(e)}")
        return jsonify({
            'success': False,
            'error': '保存失败'
        }), 500