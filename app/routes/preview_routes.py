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
        
        # 提取文档内容
        content_data = preview_service.extract_content(document.file_path)
        
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
        
        # 提取文档内容
        content_data = preview_service.extract_content(document.file_path)
        
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
        
        # 提取文档内容
        content_data = preview_service.extract_content(document.file_path)
        
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