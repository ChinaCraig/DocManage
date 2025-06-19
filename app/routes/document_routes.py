from flask import Blueprint, request, jsonify, send_file, abort
from app import db
from app.models import DocumentNode, SystemConfig, Tag, DocumentTag
import logging
import os

logger = logging.getLogger(__name__)

document_bp = Blueprint('documents', __name__)

@document_bp.route('/', methods=['GET'])
def get_documents():
    """获取文档树结构"""
    try:
        parent_id = request.args.get('parent_id', type=int)
        
        # 查询文档节点
        query = DocumentNode.query.filter_by(is_deleted=False)
        if parent_id is not None:
            query = query.filter_by(parent_id=parent_id)
        else:
            query = query.filter_by(parent_id=None)
        
        documents = query.order_by(DocumentNode.type.desc(), DocumentNode.name).all()
        
        result = [doc.to_dict() for doc in documents]
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        logger.error(f"获取文档列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@document_bp.route('/tree', methods=['GET'])
def get_document_tree():
    """获取完整文档树"""
    try:
        # 获取所有活跃节点
        all_active_nodes = DocumentNode.query.filter_by(is_deleted=False).all()
        
        # 构建有效节点集合（父文件夹存在且未删除的节点）
        valid_nodes = []
        active_node_ids = {node.id for node in all_active_nodes}
        
        for node in all_active_nodes:
            # 根节点总是有效的
            if node.parent_id is None:
                valid_nodes.append(node)
            # 非根节点需要检查父节点是否存在且未删除
            elif node.parent_id in active_node_ids:
                valid_nodes.append(node)
            else:
                # 记录孤儿节点（可选，用于调试）
                logger.warning(f"发现孤儿节点: ID={node.id}, 名称={node.name}, 父ID={node.parent_id}")
        
        # 获取根节点
        root_nodes = [node for node in valid_nodes if node.parent_id is None]
        root_nodes.sort(key=lambda x: (x.type != 'folder', x.name))
        
        # 构建树形结构
        def build_tree_dict(node):
            """构建树形字典，只包含有效的子节点"""
            result = node.to_dict()
            # 获取直接子节点（只包括有效节点）
            children = [child for child in valid_nodes if child.parent_id == node.id]
            children.sort(key=lambda x: (x.type != 'folder', x.name))
            result['children'] = [build_tree_dict(child) for child in children]
            return result
        
        result = [build_tree_dict(node) for node in root_nodes]
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        logger.error(f"获取文档树失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@document_bp.route('/folder', methods=['POST'])
def create_folder():
    """创建文件夹"""
    try:
        data = request.get_json()
        name = data.get('name')
        parent_id = data.get('parent_id')
        description = data.get('description', '')
        tag_ids = data.get('tag_ids', [])
        
        if not name:
            return jsonify({
                'success': False,
                'error': '文件夹名称不能为空'
            }), 400
        
        # 检查父节点是否存在且为文件夹类型
        if parent_id:
            parent = DocumentNode.query.get(parent_id)
            if not parent or parent.type != 'folder':
                return jsonify({
                    'success': False,
                    'error': '父节点必须是文件夹类型'
                }), 400
        
        # 检查同级是否有重名
        existing = DocumentNode.query.filter_by(
            name=name,
            parent_id=parent_id,
            is_deleted=False
        ).first()
        
        if existing:
            return jsonify({
                'success': False,
                'error': '同级目录下已存在相同名称的文件夹'
            }), 400
        
        # 验证标签（如果提供了标签）
        if tag_ids:
            existing_tags = Tag.query.filter(
                Tag.id.in_(tag_ids),
                Tag.is_deleted == False
            ).all()
            
            existing_tag_ids = [tag.id for tag in existing_tags]
            invalid_tag_ids = set(tag_ids) - set(existing_tag_ids)
            
            if invalid_tag_ids:
                return jsonify({
                    'success': False,
                    'error': f'标签ID {list(invalid_tag_ids)} 不存在或已删除'
                }), 400
        
        # 创建文件夹
        folder = DocumentNode(
            name=name,
            type='folder',
            parent_id=parent_id,
            description=description
        )
        
        db.session.add(folder)
        db.session.flush()  # 获取文件夹ID但不提交
        
        # 添加标签关联
        for tag_id in tag_ids:
            doc_tag = DocumentTag(document_id=folder.id, tag_id=tag_id)
            db.session.add(doc_tag)
        
        db.session.commit()
        
        # 重新查询以获取完整的文件夹信息（包括标签）
        created_folder = DocumentNode.query.get(folder.id)
        
        return jsonify({
            'success': True,
            'data': created_folder.to_dict()
        })
        
    except Exception as e:
        logger.error(f"创建文件夹失败: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@document_bp.route('/<int:doc_id>', methods=['PUT'])
def update_document(doc_id):
    """更新文档信息"""
    try:
        doc = DocumentNode.query.get_or_404(doc_id)
        data = request.get_json()
        
        # 更新基本信息
        if 'name' in data:
            # 检查重名
            existing = DocumentNode.query.filter_by(
                name=data['name'],
                parent_id=doc.parent_id,
                is_deleted=False
            ).filter(DocumentNode.id != doc_id).first()
            
            if existing:
                return jsonify({
                    'success': False,
                    'error': '同级目录下已存在相同名称的文件'
                }), 400
            
            doc.name = data['name']
        
        if 'description' in data:
            doc.description = data['description']
        
        if 'parent_id' in data:
            new_parent_id = data['parent_id']
            
            # 如果有新的父节点，检查其是否为文件夹
            if new_parent_id:
                parent = DocumentNode.query.get(new_parent_id)
                if not parent or parent.type != 'folder':
                    return jsonify({
                        'success': False,
                        'error': '父节点必须是文件夹类型'
                    }), 400
                
                # 检查是否会形成循环引用（文件夹类型）
                if doc.type == 'folder' and _would_create_cycle(doc.id, new_parent_id):
                    return jsonify({
                        'success': False,
                        'error': '不能移动到自己的子目录下'
                    }), 400
            
            doc.parent_id = new_parent_id
        
        # 处理标签更新
        if 'tag_ids' in data:
            tag_ids = data['tag_ids']
            if isinstance(tag_ids, list):
                # 验证标签是否存在
                existing_tags = Tag.query.filter(
                    Tag.id.in_(tag_ids),
                    Tag.is_deleted == False
                ).all()
                
                existing_tag_ids = [tag.id for tag in existing_tags]
                invalid_tag_ids = set(tag_ids) - set(existing_tag_ids)
                
                if invalid_tag_ids:
                    return jsonify({
                        'success': False,
                        'error': f'标签ID {list(invalid_tag_ids)} 不存在或已删除'
                    }), 400
                
                # 清除现有标签关联
                DocumentTag.query.filter_by(document_id=doc_id).delete()
                
                # 添加新的标签关联
                for tag_id in tag_ids:
                    doc_tag = DocumentTag(document_id=doc_id, tag_id=tag_id)
                    db.session.add(doc_tag)
        
        db.session.commit()
        
        # 重新查询以获取更新后的标签信息
        updated_doc = DocumentNode.query.get(doc_id)
        
        return jsonify({
            'success': True,
            'data': updated_doc.to_dict()
        })
        
    except Exception as e:
        logger.error(f"更新文档失败: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@document_bp.route('/<int:doc_id>/tags', methods=['POST'])
def update_document_tags(doc_id):
    """更新文档标签"""
    try:
        doc = DocumentNode.query.get_or_404(doc_id)
        data = request.get_json()
        
        tag_ids = data.get('tag_ids', [])
        
        if tag_ids:
            # 验证标签是否存在
            existing_tags = Tag.query.filter(
                Tag.id.in_(tag_ids),
                Tag.is_deleted == False
            ).all()
            
            existing_tag_ids = [tag.id for tag in existing_tags]
            invalid_tag_ids = set(tag_ids) - set(existing_tag_ids)
            
            if invalid_tag_ids:
                return jsonify({
                    'success': False,
                    'error': f'标签ID {list(invalid_tag_ids)} 不存在或已删除'
                }), 400
        
        # 清除现有标签关联
        DocumentTag.query.filter_by(document_id=doc_id).delete()
        
        # 添加新的标签关联
        for tag_id in tag_ids:
            doc_tag = DocumentTag(document_id=doc_id, tag_id=tag_id)
            db.session.add(doc_tag)
        
        db.session.commit()
        
        # 重新查询以获取更新后的标签信息
        updated_doc = DocumentNode.query.get(doc_id)
        
        return jsonify({
            'success': True,
            'data': updated_doc.to_dict(),
            'message': '标签更新成功'
        })
        
    except Exception as e:
        logger.error(f"更新文档标签失败: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@document_bp.route('/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """删除文档（软删除）"""
    try:
        doc = DocumentNode.query.get_or_404(doc_id)
        
        # 标记为删除
        doc.is_deleted = True
        
        # 如果是文件夹，递归删除子项
        if doc.type == 'folder':
            _mark_children_deleted(doc.id)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '删除成功'
        })
        
    except Exception as e:
        logger.error(f"删除文档失败: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@document_bp.route('/<int:doc_id>/detail', methods=['GET'])
def get_document_detail(doc_id):
    """获取文档详细信息"""
    try:
        doc = DocumentNode.query.get_or_404(doc_id)
        
        result = doc.to_dict()
        
        # 如果是文件，添加内容信息
        if doc.type == 'file' and doc.contents:
            result['content_info'] = {
                'total_contents': len(doc.contents),
                'total_chunks': sum(len(content.chunk_text.split('\n')) if content.chunk_text else 0 for content in doc.contents),
                'vector_status': [record.vector_status for record in doc.vector_records]
            }
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        logger.error(f"获取文档详情失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@document_bp.route('/<int:doc_id>/children', methods=['GET'])
def get_document_children_info(doc_id):
    """获取文档的子项信息，用于删除确认"""
    try:
        doc = DocumentNode.query.get_or_404(doc_id)
        
        if doc.type != 'folder':
            return jsonify({
                'success': True,
                'data': {
                    'has_children': False,
                    'children_count': 0,
                    'children_summary': []
                }
            })
        
        # 查询直接子项
        children = DocumentNode.query.filter_by(
            parent_id=doc_id, 
            is_deleted=False
        ).all()
        
        # 统计子项类型
        children_summary = {}
        for child in children:
            child_type = '文件夹' if child.type == 'folder' else '文件'
            children_summary[child_type] = children_summary.get(child_type, 0) + 1
        
        # 递归统计所有后代
        def count_all_descendants(parent_id):
            descendants = DocumentNode.query.filter_by(
                parent_id=parent_id, 
                is_deleted=False
            ).all()
            
            total = len(descendants)
            for desc in descendants:
                if desc.type == 'folder':
                    total += count_all_descendants(desc.id)
            return total
        
        total_descendants = count_all_descendants(doc_id)
        
        return jsonify({
            'success': True,
            'data': {
                'has_children': len(children) > 0,
                'children_count': len(children),
                'total_descendants': total_descendants,
                'children_summary': [f"{count}个{type_name}" for type_name, count in children_summary.items()]
            }
        })
        
    except Exception as e:
        logger.error(f"获取文档子项信息失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def _would_create_cycle(node_id, target_parent_id):
    """检查是否会创建循环引用"""
    current_id = target_parent_id
    while current_id:
        if current_id == node_id:
            return True
        parent = DocumentNode.query.get(current_id)
        current_id = parent.parent_id if parent else None
    return False

def _mark_children_deleted(parent_id):
    """递归标记子节点为已删除"""
    children = DocumentNode.query.filter_by(parent_id=parent_id, is_deleted=False).all()
    for child in children:
        child.is_deleted = True
        if child.type == 'folder':
            _mark_children_deleted(child.id)

@document_bp.route('/<int:doc_id>/download', methods=['GET'])
def download_document(doc_id):
    """下载文档原文件"""
    try:
        logger.info(f"开始处理文档下载请求 - 文档ID: {doc_id}")
        
        # 获取文档信息
        document = DocumentNode.query.get_or_404(doc_id)
        logger.info(f"找到文档: {document.name}, 类型: {document.file_type}")
        
        if document.is_deleted or document.type != 'file':
            logger.warning(f"文档已删除或不是文件 - ID: {doc_id}")
            abort(404)
        
        # 检查文件是否存在
        logger.info(f"检查文件路径: {document.file_path}")
        if not document.file_path or not os.path.exists(document.file_path):
            logger.error(f"文件不存在: {document.file_path}")
            abort(404)
        
        logger.info(f"文件存在，准备下载: {document.file_path}")
        
        try:
            # 使用绝对路径
            abs_path = os.path.abspath(document.file_path)
            logger.info(f"使用绝对路径: {abs_path}")
            
            # 设置下载文件名为原始文件名
            download_name = document.name
            
            return send_file(
                abs_path, 
                as_attachment=True,
                download_name=download_name,
                mimetype=document.mime_type
            )
            
        except Exception as send_error:
            logger.error(f"send_file失败: {send_error}")
            raise
        
    except Exception as e:
        logger.error(f"文档下载失败 - 文档ID: {doc_id}, 错误: {str(e)}")
        logger.error(f"错误详情: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"堆栈跟踪: {traceback.format_exc()}")
        abort(500)

@document_bp.route('/<int:doc_id>/analyze', methods=['POST'])
def analyze_document_structure(doc_id):
    """分析文档结构并提供改进建议"""
    try:
        # 获取请求参数
        data = request.get_json() or {}
        llm_model = data.get('llm_model')
        
        if not llm_model:
            return jsonify({
                'success': False,
                'error': 'LLM模型参数是必需的'
            }), 400
        
        # 获取文档信息
        document = DocumentNode.query.get_or_404(doc_id)
        
        if document.is_deleted:
            return jsonify({
                'success': False,
                'error': '文档已删除'
            }), 404
        
        # 获取文档标签信息
        document_tags = [tag.to_dict() for tag in document.tags]
        
        # 构建文档树结构
        def build_document_tree(node):
            """递归构建文档树"""
            result = {
                'id': node.id,
                'name': node.name,
                'type': node.type,
                'file_type': node.file_type,
                'description': node.description,
                'children': []
            }
            
            # 获取子节点
            children = DocumentNode.query.filter_by(
                parent_id=node.id,
                is_deleted=False
            ).order_by(DocumentNode.type.desc(), DocumentNode.name).all()
            
            for child in children:
                result['children'].append(build_document_tree(child))
            
            return result
        
        document_tree = build_document_tree(document)
        
        # 调用LLM分析服务
        from app.services.llm import LLMService
        
        analysis_result = LLMService.analyze_document_structure(
            document_name=document.name,
            document_tags=document_tags,
            document_tree=document_tree,
            llm_model=llm_model
        )
        
        if not analysis_result:
            return jsonify({
                'success': False,
                'error': '文档结构分析失败'
            }), 500
        
        return jsonify({
            'success': True,
            'data': {
                'document_info': {
                    'id': document.id,
                    'name': document.name,
                    'type': document.type,
                    'tags': document_tags
                },
                'analysis': analysis_result,
                'llm_model': llm_model
            }
        })
        
    except Exception as e:
        logger.error(f"文档结构分析失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@document_bp.route('/search-by-name', methods=['GET'])
def search_documents_by_name():
    """根据文档名称搜索文档"""
    try:
        query = request.args.get('query', '').strip()
        
        if not query:
            return jsonify({
                'success': False,
                'error': '搜索查询不能为空'
            }), 400
        
        # 模糊搜索文档名称
        documents = DocumentNode.query.filter(
            DocumentNode.name.contains(query),
            DocumentNode.is_deleted == False
        ).limit(10).all()
        
        results = []
        for doc in documents:
            doc_data = doc.to_dict()
            
            # 添加路径信息
            path_parts = []
            current = doc
            while current.parent_id:
                parent = DocumentNode.query.get(current.parent_id)
                if parent and not parent.is_deleted:
                    path_parts.append(parent.name)
                    current = parent
                else:
                    break
            
            doc_data['path'] = ' > '.join(reversed(path_parts)) if path_parts else '根目录'
            results.append(doc_data)
        
        return jsonify({
            'success': True,
            'data': results
        })
        
    except Exception as e:
        logger.error(f"搜索文档失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 