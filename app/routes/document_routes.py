from flask import Blueprint, request, jsonify
from app import db
from app.models import DocumentNode, SystemConfig
import logging

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
        
        # 创建文件夹
        folder = DocumentNode(
            name=name,
            type='folder',
            parent_id=parent_id,
            description=description
        )
        
        db.session.add(folder)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': folder.to_dict()
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
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': doc.to_dict()
        })
        
    except Exception as e:
        logger.error(f"更新文档失败: {str(e)}")
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
    """递归标记子项为删除状态"""
    children = DocumentNode.query.filter_by(parent_id=parent_id, is_deleted=False).all()
    for child in children:
        child.is_deleted = True
        if child.type == 'folder':
            _mark_children_deleted(child.id) 