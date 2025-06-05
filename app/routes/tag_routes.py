from flask import Blueprint, request, jsonify
from app import db
from app.models import Tag
import logging

logger = logging.getLogger(__name__)

tag_bp = Blueprint('tags', __name__)

@tag_bp.route('/', methods=['GET'])
def get_tags():
    """获取所有标签"""
    try:
        search = request.args.get('search', '').strip()
        
        # 查询标签
        query = Tag.query.filter_by(is_deleted=False)
        
        if search:
            query = query.filter(Tag.name.ilike(f'%{search}%'))
        
        tags = query.order_by(Tag.name).all()
        
        result = [tag.to_dict() for tag in tags]
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        logger.error(f"获取标签列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@tag_bp.route('/', methods=['POST'])
def create_tag():
    """创建标签"""
    try:
        data = request.get_json()
        
        name = data.get('name', '').strip()
        if not name:
            return jsonify({
                'success': False,
                'error': '标签名称不能为空'
            }), 400
        
        # 检查标签是否已存在
        existing_tag = Tag.query.filter_by(name=name, is_deleted=False).first()
        if existing_tag:
            return jsonify({
                'success': False,
                'error': '标签已存在'
            }), 400
        
        # 创建新标签
        tag = Tag(
            name=name,
            color=data.get('color', '#007bff'),
            description=data.get('description', ''),
            created_by=data.get('created_by', 'system')
        )
        
        db.session.add(tag)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': tag.to_dict(),
            'message': '标签创建成功'
        })
        
    except Exception as e:
        logger.error(f"创建标签失败: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@tag_bp.route('/<int:tag_id>', methods=['PUT'])
def update_tag(tag_id):
    """更新标签"""
    try:
        tag = Tag.query.get_or_404(tag_id)
        data = request.get_json()
        
        name = data.get('name', '').strip()
        if not name:
            return jsonify({
                'success': False,
                'error': '标签名称不能为空'
            }), 400
        
        # 检查标签名称是否与其他标签冲突
        existing_tag = Tag.query.filter(
            Tag.name == name,
            Tag.id != tag_id,
            Tag.is_deleted == False
        ).first()
        
        if existing_tag:
            return jsonify({
                'success': False,
                'error': '标签名称已存在'
            }), 400
        
        # 更新标签信息
        tag.name = name
        tag.color = data.get('color', tag.color)
        tag.description = data.get('description', tag.description)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': tag.to_dict(),
            'message': '标签更新成功'
        })
        
    except Exception as e:
        logger.error(f"更新标签失败: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@tag_bp.route('/<int:tag_id>', methods=['DELETE'])
def delete_tag(tag_id):
    """删除标签（软删除）"""
    try:
        tag = Tag.query.get_or_404(tag_id)
        
        # 标记为删除
        tag.is_deleted = True
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '标签删除成功'
        })
        
    except Exception as e:
        logger.error(f"删除标签失败: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@tag_bp.route('/search', methods=['GET'])
def search_tags():
    """搜索标签"""
    try:
        query = request.args.get('q', '').strip()
        
        if not query:
            return jsonify({
                'success': True,
                'data': []
            })
        
        # 搜索标签
        tags = Tag.query.filter(
            Tag.name.ilike(f'%{query}%'),
            Tag.is_deleted == False
        ).order_by(Tag.name).limit(10).all()
        
        result = [tag.to_dict() for tag in tags]
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        logger.error(f"搜索标签失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@tag_bp.route('/autocomplete', methods=['GET'])
def autocomplete_tags():
    """标签自动完成"""
    try:
        query = request.args.get('q', '').strip()
        
        if not query:
            # 返回最常用的标签
            tags = Tag.query.filter_by(is_deleted=False).order_by(Tag.name).limit(10).all()
        else:
            # 搜索匹配的标签
            tags = Tag.query.filter(
                Tag.name.ilike(f'%{query}%'),
                Tag.is_deleted == False
            ).order_by(Tag.name).limit(10).all()
        
        result = [{'id': tag.id, 'name': tag.name, 'color': tag.color} for tag in tags]
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        logger.error(f"标签自动完成失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 