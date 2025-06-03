from flask import Blueprint, request, jsonify
from app.models import DocumentNode, SystemConfig
from app.services import VectorService
import logging

logger = logging.getLogger(__name__)

search_bp = Blueprint('search', __name__)

@search_bp.route('/', methods=['POST'])
def semantic_search():
    """语义搜索"""
    try:
        data = request.get_json()
        query_text = data.get('query')
        top_k = data.get('top_k', 10)
        document_id = data.get('document_id')  # 可选，限制在特定文档中搜索
        
        if not query_text:
            return jsonify({
                'success': False,
                'error': '查询文本不能为空'
            }), 400
        
        # 初始化向量服务
        milvus_host = SystemConfig.get_config('milvus_host', 'localhost')
        milvus_port = SystemConfig.get_config('milvus_port', 19530)
        embedding_model = SystemConfig.get_config('embedding_model')
        
        vector_service = VectorService()
        vector_service.initialize(
            host=milvus_host,
            port=milvus_port,
            model_name=embedding_model
        )
        
        # 执行语义搜索
        search_results = vector_service.search_similar(
            query_text=query_text,
            top_k=top_k,
            document_id=document_id
        )
        
        # enriched结果，添加文档信息
        enriched_results = []
        for result in search_results:
            doc_id = result['document_id']
            document = DocumentNode.query.get(doc_id)
            
            if document and not document.is_deleted:
                enriched_result = result.copy()
                enriched_result['document'] = {
                    'id': document.id,
                    'name': document.name,
                    'file_type': document.file_type,
                    'file_path': document.file_path,
                    'description': document.description
                }
                enriched_results.append(enriched_result)
        
        return jsonify({
            'success': True,
            'data': {
                'query': query_text,
                'total_results': len(enriched_results),
                'results': enriched_results
            }
        })
        
    except Exception as e:
        logger.error(f"语义搜索失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@search_bp.route('/documents', methods=['GET'])
def search_documents():
    """文档名称搜索"""
    try:
        query = request.args.get('q', '').strip()
        file_type = request.args.get('type')
        parent_id = request.args.get('parent_id', type=int)
        
        if not query:
            return jsonify({
                'success': False,
                'error': '查询参数不能为空'
            }), 400
        
        # 构建查询
        db_query = DocumentNode.query.filter_by(is_deleted=False)
        
        # 按名称模糊搜索
        db_query = db_query.filter(DocumentNode.name.contains(query))
        
        # 按文件类型过滤
        if file_type:
            db_query = db_query.filter_by(file_type=file_type)
        
        # 按父目录过滤
        if parent_id is not None:
            db_query = db_query.filter_by(parent_id=parent_id)
        
        # 执行查询
        documents = db_query.order_by(DocumentNode.type.desc(), DocumentNode.name).limit(50).all()
        
        results = [doc.to_dict() for doc in documents]
        
        return jsonify({
            'success': True,
            'data': {
                'query': query,
                'total_results': len(results),
                'results': results
            }
        })
        
    except Exception as e:
        logger.error(f"文档搜索失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@search_bp.route('/suggest', methods=['GET'])
def search_suggestions():
    """搜索建议"""
    try:
        query = request.args.get('q', '').strip()
        limit = request.args.get('limit', 10, type=int)
        
        if not query or len(query) < 2:
            return jsonify({
                'success': True,
                'data': []
            })
        
        # 查询匹配的文档名称
        documents = DocumentNode.query.filter(
            DocumentNode.name.contains(query),
            DocumentNode.is_deleted == False
        ).limit(limit).all()
        
        suggestions = []
        for doc in documents:
            suggestions.append({
                'id': doc.id,
                'name': doc.name,
                'type': doc.type,
                'file_type': doc.file_type
            })
        
        return jsonify({
            'success': True,
            'data': suggestions
        })
        
    except Exception as e:
        logger.error(f"搜索建议失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@search_bp.route('/stats', methods=['GET'])
def search_stats():
    """搜索统计信息"""
    try:
        # 初始化向量服务
        milvus_host = SystemConfig.get_config('milvus_host', 'localhost')
        milvus_port = SystemConfig.get_config('milvus_port', 19530)
        embedding_model = SystemConfig.get_config('embedding_model')
        
        vector_service = VectorService()
        vector_service.initialize(
            host=milvus_host,
            port=milvus_port,
            model_name=embedding_model
        )
        
        # 获取向量统计
        vector_stats = vector_service.get_collection_stats()
        
        # 获取文档统计
        total_documents = DocumentNode.query.filter_by(is_deleted=False, type='file').count()
        total_folders = DocumentNode.query.filter_by(is_deleted=False, type='folder').count()
        
        # 按文件类型统计
        file_type_stats = {}
        for doc in DocumentNode.query.filter_by(is_deleted=False, type='file').all():
            file_type = doc.file_type or 'unknown'
            file_type_stats[file_type] = file_type_stats.get(file_type, 0) + 1
        
        return jsonify({
            'success': True,
            'data': {
                'vector_stats': vector_stats,
                'document_stats': {
                    'total_documents': total_documents,
                    'total_folders': total_folders,
                    'file_type_distribution': file_type_stats
                }
            }
        })
        
    except Exception as e:
        logger.error(f"获取搜索统计失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 