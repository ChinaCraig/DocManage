from flask import Blueprint, request, jsonify
from app.models import DocumentNode, SystemConfig
from app.services.vectorization import VectorServiceAdapter
from app.services.llm_service import LLMService
from config import Config
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
        
        # 新增：获取相似度阈值参数
        similarity_level = data.get('similarity_level', 'medium')  # 默认中等相关性
        
        # 新增：LLM相关参数
        use_llm = data.get('enable_llm', data.get('use_llm', False))  # 兼容两种参数名
        llm_model = data.get('llm_model')
        
        # 添加调试日志
        logger.info(f"收到搜索请求 - query: {query_text}, similarity_level: {similarity_level}, use_llm: {use_llm}, llm_model: {llm_model}")
        
        # 根据用户选择的相关性等级设置阈值
        similarity_thresholds = {
            'high': 0.6,      # 高相关性
            'medium': 0.3,    # 中等相关性
            'low': 0.1,       # 低相关性
            'any': 0.0        # 基本不相关（显示所有结果）
        }
        min_score = similarity_thresholds.get(similarity_level, 0.3)
        
        logger.info(f"设置相似度阈值 - level: {similarity_level}, min_score: {min_score}")
        
        if not query_text:
            return jsonify({
                'success': False,
                'error': '查询文本不能为空'
            }), 400
        
        # LLM步骤1：查询优化（使用智能提示词系统）
        original_query = query_text
        optimized_query = query_text
        if use_llm and llm_model:
            try:
                optimized_query = LLMService.optimize_query(
                    query_text, 
                    llm_model=llm_model,
                    scenario=None,  # 让系统自动分析
                    template=None   # 让系统自动推荐
                )
                logger.info(f"智能LLM查询优化 - 原查询: {query_text}, 优化后: {optimized_query}")
            except Exception as e:
                logger.warning(f"LLM查询优化失败: {e}")
                optimized_query = query_text
        
        # 初始化向量服务
        milvus_host = SystemConfig.get_config('milvus_host', 'localhost')
        milvus_port = SystemConfig.get_config('milvus_port', 19530)
        embedding_model = SystemConfig.get_config('embedding_model')
        
        vector_service = VectorServiceAdapter(
            milvus_host=milvus_host,
            milvus_port=milvus_port,
            embedding_model=embedding_model
        )
        
        # 执行语义搜索，使用优化后的查询
        search_results = vector_service.search_similar(
            query_text=optimized_query,
            top_k=top_k,
            document_id=document_id,
            min_score=min_score
        )
        
        # 按文件聚合结果
        file_results = aggregate_results_by_file(search_results)
        
        # LLM步骤2：结果重排序（基于文件）
        reranked = False
        if use_llm and llm_model and file_results:
            try:
                file_results = LLMService.rerank_file_results(original_query, file_results, llm_model)
                reranked = True
                logger.info(f"LLM文件结果重排序完成 - 处理了 {len(file_results)} 个文件")
            except Exception as e:
                logger.warning(f"LLM结果重排序失败: {e}")
        
        # LLM步骤3：答案生成（使用智能提示词系统）
        llm_answer = None
        if use_llm and llm_model and file_results:
            try:
                # 准备上下文文本
                context_texts = []
                for file_result in file_results[:5]:  # 只使用前5个文件结果生成答案
                    doc_name = file_result['document']['name']
                    # 合并该文件的所有匹配片段
                    chunks = [chunk['text'] for chunk in file_result['chunks'][:3]]  # 每个文件最多3个片段
                    combined_text = '\n'.join(chunks)
                    context_texts.append(f"文档《{doc_name}》：{combined_text}")
                
                context = '\n\n'.join(context_texts)
                llm_answer = LLMService.generate_answer(
                    original_query, 
                    context, 
                    llm_model=llm_model,
                    scenario=None,  # 让系统自动分析
                    style=None      # 让系统自动推荐
                )
                logger.info(f"智能LLM答案生成完成 - 查询: {original_query}")
            except Exception as e:
                logger.warning(f"LLM答案生成失败: {e}")
        
        response_data = {
            'query': query_text,
            'similarity_level': similarity_level,
            'min_score': min_score,
            'total_files': len(file_results),
            'file_results': file_results
        }
        
        # 添加LLM处理信息
        if use_llm:
            response_data['llm_info'] = {
                'used': True,
                'model': llm_model,
                'original_query': original_query,
                'optimized_query': optimized_query,
                'query_optimized': optimized_query != original_query,
                'reranked': reranked,
                'answer': llm_answer
            }
        else:
            response_data['llm_info'] = {
                'used': False
            }
        
        logger.info(f"返回搜索结果 - similarity_level: {response_data['similarity_level']}, min_score: {response_data['min_score']}, files: {response_data['total_files']}")
        
        return jsonify({
            'success': True,
            'data': response_data
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
        
        vector_service = VectorServiceAdapter(
            milvus_host=milvus_host,
            milvus_port=milvus_port,
            embedding_model=embedding_model
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

@search_bp.route('/hybrid', methods=['POST'])
def hybrid_search():
    """混合搜索：语义搜索 + 关键词搜索"""
    try:
        data = request.get_json()
        query_text = data.get('query')
        top_k = data.get('top_k', 10)
        document_id = data.get('document_id')
        similarity_level = data.get('similarity_level', 'medium')
        
        # LLM相关参数
        use_llm = data.get('enable_llm', data.get('use_llm', False))  # 兼容两种参数名
        llm_model = data.get('llm_model')
        
        logger.info(f"收到混合搜索请求 - query: {query_text}, similarity_level: {similarity_level}, use_llm: {use_llm}, llm_model: {llm_model}")
        
        if not query_text:
            return jsonify({
                'success': False,
                'error': '查询文本不能为空'
            }), 400
        
        # LLM查询优化（使用智能提示词系统）
        original_query = query_text
        optimized_query = query_text
        if use_llm and llm_model:
            try:
                optimized_query = LLMService.optimize_query(
                    query_text, 
                    llm_model=llm_model,
                    scenario=None,  # 让系统自动分析
                    template=None   # 让系统自动推荐
                )
                logger.info(f"混合搜索智能LLM查询优化 - 原查询: {query_text}, 优化后: {optimized_query}")
            except Exception as e:
                logger.warning(f"混合搜索LLM查询优化失败: {e}")
                optimized_query = query_text
        
        # 设置相似度阈值（针对银行等特定查询提高阈值）
        similarity_thresholds = {
            'high': 0.6, 'medium': 0.3, 'low': 0.1, 'any': 0.0
        }
        min_score = similarity_thresholds.get(similarity_level, 0.3)
        
        # 对特定查询类型动态调整阈值
        if any(word in query_text.lower() for word in ['银行', '金融机构', '贷款']):
            min_score = max(min_score, 0.4)  # 银行相关查询提高最低阈值
            logger.info(f"检测到银行相关查询，提高阈值到: {min_score}")
        
        # 初始化向量服务
        milvus_host = SystemConfig.get_config('milvus_host', 'localhost')
        milvus_port = SystemConfig.get_config('milvus_port', 19530)
        embedding_model = SystemConfig.get_config('embedding_model')
        
        vector_service = VectorServiceAdapter(
            milvus_host=milvus_host,
            milvus_port=milvus_port,
            embedding_model=embedding_model
        )
        
        # 1. 执行语义搜索（使用优化后的查询）
        semantic_results = vector_service.search_similar(
            query_text=optimized_query,
            top_k=top_k,
            document_id=document_id,
            min_score=min_score
        )
        
        # 2. 执行关键词搜索（使用优化后的查询）
        keyword_results = vector_service.search_by_keywords(
            query_text=optimized_query,
            top_k=top_k,
            document_id=document_id
        )
        
        # 3. 合并和去重结果
        combined_results = merge_search_results(semantic_results, keyword_results, query_text)
        
        # 4. 丰富结果信息并按文件聚合
        file_results = aggregate_results_by_file(combined_results)
        
        # 5. LLM结果重排序（基于文件）
        reranked = False
        if use_llm and llm_model and file_results:
            try:
                file_results = LLMService.rerank_file_results(original_query, file_results, llm_model)
                reranked = True
                logger.info(f"混合搜索LLM文件结果重排序完成 - 处理了 {len(file_results)} 个文件")
            except Exception as e:
                logger.warning(f"混合搜索LLM结果重排序失败: {e}")
        
        # 6. LLM答案生成（使用智能提示词系统）
        llm_answer = None
        if use_llm and llm_model and file_results:
            try:
                # 准备上下文文本
                context_texts = []
                for file_result in file_results[:5]:  # 只使用前5个文件结果生成答案
                    doc_name = file_result['document']['name']
                    # 合并该文件的所有匹配片段
                    chunks = [chunk['text'] for chunk in file_result['chunks'][:3]]  # 每个文件最多3个片段
                    combined_text = '\n'.join(chunks)
                    context_texts.append(f"文档《{doc_name}》：{combined_text}")
                
                context = '\n\n'.join(context_texts)
                llm_answer = LLMService.generate_answer(
                    original_query, 
                    context, 
                    llm_model=llm_model,
                    scenario=None,  # 让系统自动分析
                    style=None      # 让系统自动推荐
                )
                logger.info(f"混合搜索智能LLM答案生成完成 - 查询: {original_query}")
            except Exception as e:
                logger.warning(f"混合搜索LLM答案生成失败: {e}")
        
        response_data = {
            'query': query_text,
            'similarity_level': similarity_level,
            'min_score': min_score,
            'semantic_count': len(semantic_results),
            'keyword_count': len(keyword_results),
            'total_files': len(file_results),
            'file_results': file_results,
            'search_type': 'hybrid'
        }
        
        # 添加LLM处理信息
        if use_llm:
            response_data['llm_info'] = {
                'used': True,
                'model': llm_model,
                'original_query': original_query,
                'optimized_query': optimized_query,
                'query_optimized': optimized_query != original_query,
                'reranked': reranked,
                'answer': llm_answer
            }
        else:
            response_data['llm_info'] = {
                'used': False
            }
        
        logger.info(f"混合搜索完成 - semantic: {len(semantic_results)}, keyword: {len(keyword_results)}, files: {len(file_results)}")
        
        return jsonify({
            'success': True,
            'data': response_data
        })
        
    except Exception as e:
        logger.error(f"混合搜索失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def merge_search_results(semantic_results, keyword_results, query_text):
    """合并语义搜索和关键词搜索结果"""
    try:
        # 使用文档ID+chunk_id作为唯一标识符
        seen_results = {}
        merged_results = []
        
        # 处理语义搜索结果（优先级更高）
        for result in semantic_results:
            key = f"{result['document_id']}_{result.get('chunk_id', '')}"
            result['search_type'] = 'semantic'
            seen_results[key] = result
            merged_results.append(result)
        
        # 处理关键词搜索结果
        for result in keyword_results:
            key = f"{result['document_id']}_{result.get('chunk_id', '')}"
            if key not in seen_results:
                result['search_type'] = 'keyword'
                merged_results.append(result)
            else:
                # 如果已存在，更新搜索类型为混合
                seen_results[key]['search_type'] = 'hybrid'
        
        # 按相关度排序
        merged_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        return merged_results
        
    except Exception as e:
        logger.error(f"合并搜索结果失败: {str(e)}")
        return semantic_results  # fallback到语义搜索结果

def aggregate_results_by_file(chunk_results):
    """将chunk级别的搜索结果聚合为文件级别"""
    try:
        file_groups = {}
        
        # 按文档ID分组
        for result in chunk_results:
            doc_id = str(result['document_id'])
            if doc_id not in file_groups:
                file_groups[doc_id] = []
            file_groups[doc_id].append(result)
        
        file_results = []
        
        # 为每个文件创建聚合结果
        for doc_id, chunks in file_groups.items():
            document = DocumentNode.query.get(doc_id)
            if not document or document.is_deleted:
                continue
            
            # 计算文件级别的综合得分
            scores = [chunk.get('score', 0) for chunk in chunks]
            max_score = max(scores) if scores else 0
            avg_score = sum(scores) / len(scores) if scores else 0
            combined_score = max_score * 0.7 + avg_score * 0.3  # 权重组合
            
            # 按得分对chunks排序
            chunks.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            # 创建文件级别的结果
            file_result = {
                'document': {
                    'id': document.id,
                    'name': document.name,
                    'file_type': document.file_type,
                    'file_path': document.file_path,
                    'description': document.description,
                    'file_size': document.file_size,
                    'parent_id': document.parent_id
                },
                'score': combined_score,
                'max_chunk_score': max_score,
                'chunk_count': len(chunks),
                'chunks': [
                    {
                        'chunk_id': chunk.get('chunk_id'),
                        'text': chunk.get('text', ''),
                        'score': chunk.get('score', 0),
                        'search_type': chunk.get('search_type', 'unknown')
                    }
                    for chunk in chunks
                ],
                'search_types': list(set(chunk.get('search_type', 'unknown') for chunk in chunks))
            }
            
            file_results.append(file_result)
        
        # 按综合得分排序
        file_results.sort(key=lambda x: x['score'], reverse=True)
        
        logger.info(f"文件聚合完成 - 从 {len(chunk_results)} 个chunk聚合为 {len(file_results)} 个文件")
        return file_results
        
    except Exception as e:
        logger.error(f"文件聚合失败: {str(e)}")
        return [] 