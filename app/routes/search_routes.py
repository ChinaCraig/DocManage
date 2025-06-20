import os
import json
import time
import logging
from flask import Blueprint, request, jsonify
from sqlalchemy import or_, and_, desc
from app.models.document_models import DocumentNode, db
from app.services.vectorization.vector_service_adapter import VectorServiceAdapter
from app.services.llm import LLMService
# 旧的MCP服务已移除
from config import Config
import asyncio

logger = logging.getLogger(__name__)

search_bp = Blueprint('search', __name__)

@search_bp.route('/create-folder', methods=['POST'])
def create_folder():
    """创建文件夹（MCP功能）"""
    try:
        data = request.get_json()
        folder_name = data.get('name', '新文件夹').strip()
        parent_id = data.get('parent_id')
        
        if not folder_name:
            return jsonify({
                'success': False,
                'error': '文件夹名称不能为空'
            }), 400
        
        # 创建文件夹
        from app.models import DocumentNode
        from app import db
        
        new_folder = DocumentNode(
            name=folder_name,
            type='folder',
            parent_id=parent_id,
            description=f"由MCP工具创建的文件夹: {folder_name}"
        )
        
        db.session.add(new_folder)
        db.session.commit()
        
        logger.info(f"MCP成功创建文件夹: {folder_name} (ID: {new_folder.id})")
        
        return jsonify({
            'success': True,
            'data': {
                'id': new_folder.id,
                'name': new_folder.name,
                'parent_id': new_folder.parent_id,
                'message': f"成功创建文件夹: {folder_name}"
            }
        })
        
    except Exception as e:
        logger.error(f"创建文件夹失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@search_bp.route('/', methods=['POST'])
def semantic_search():
    """语义搜索接口"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据为空'
            }), 400
        
        query_text = data.get('query', '').strip()
        top_k = data.get('top_k', 10)
        enable_mcp = data.get('enable_mcp', False)
        
        if not query_text:
            return jsonify({
                'success': False,
                'error': '查询内容不能为空'
            }), 400
        
        llm_model = data.get('llm_model')  # 获取LLM模型参数
        
        logger.info(f"接收到语义搜索请求: {query_text}, top_k: {top_k}, enable_mcp: {enable_mcp}, llm_model: {llm_model}")
        
        # 初始化结果
        search_results = []
        mcp_tool_results = []
        skip_search = False
        intent_analysis = None
        
        # 使用专用的意图识别模型进行智能意图分析
        if Config.ENABLE_INTENT_ANALYSIS and enable_mcp:
            try:
                from app.services.llm import LLMService
                # 使用专用的意图识别模型
                intent_llm_model = f"{Config.INTENT_ANALYSIS_LLM_PROVIDER}:{Config.INTENT_ANALYSIS_LLM_MODEL}"
                intent_analysis = LLMService.analyze_user_intent(query_text, intent_llm_model)
                logger.info(f"意图分析结果: {intent_analysis}")
                
                # 使用配置的置信度阈值
                confidence_threshold = Config.INTENT_ANALYSIS_CONFIDENCE_THRESHOLD
                intent_type = intent_analysis.get('intent_type', 'knowledge_search')
                confidence = intent_analysis.get('confidence', 0)
                
                # 根据新的意图分类处理
                if intent_type == 'normal_chat' and confidence > confidence_threshold:
                    # 普通聊天：直接LLM问答
                    logger.info(f"执行普通聊天操作: {query_text}")
                    skip_search = True
                    
                    try:
                        # 使用用户选择的LLM模型进行聊天
                        chat_response = LLMService.generate_answer(
                            query=query_text,
                            context="",  # 普通聊天不需要文档上下文
                            llm_model=llm_model or intent_llm_model,
                            style="conversational"
                        )
                        logger.info(f"普通聊天响应生成完成")
                        
                        # 构建聊天响应数据
                        response_data = {
                            'query': query_text,
                            'is_chat': True,
                            'chat_response': chat_response,
                            'search_type': 'normal_chat',
                            'intent_analysis': {
                                'intent_type': intent_analysis.get('intent_type'),
                                'confidence': intent_analysis.get('confidence'),
                                'action_type': intent_analysis.get('action_type'),
                                'reasoning': intent_analysis.get('reasoning'),
                                'used_llm': True,
                                'model': llm_model or intent_llm_model,
                                'prompt_source': intent_analysis.get('prompt_source', 'config_file'),
                                'confidence_threshold': confidence_threshold
                            }
                        }
                        
                        # 转换为标准化消息格式
                        message_content = []
                        
                        # 添加意图识别结果
                        message_content.append({
                            "type": "text", 
                            "data": f"💬 普通对话: {intent_analysis.get('reasoning', '已识别为一般对话交流')}"
                        })
                        
                        # 添加聊天响应
                        message_content.append({
                            "type": "markdown",
                            "data": chat_response
                        })
                        
                        # 构建标准化响应格式
                        standardized_response = {
                            "message_id": f"msg-{int(time.time())}-{hash(query_text) % 1000:03d}",
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "role": "assistant",
                            "content": message_content,
                            "legacy_data": response_data
                        }
                        
                        return jsonify({
                            'success': True,
                            'data': standardized_response
                        })
                        
                    except Exception as chat_error:
                        logger.error(f"普通聊天处理失败: {chat_error}")
                        return jsonify({
                            'success': False,
                            'error': f"聊天处理失败: {str(chat_error)}"
                        }), 500
                
                elif intent_type == 'mcp_action' and confidence > confidence_threshold:
                    # MCP调用：使用标准MCP系统
                    logger.info(f"执行标准MCP操作: {query_text}")
                    skip_search = True
                    
                    # 步骤1：检查MCP开关状态
                    mcp_enabled = request.json.get('enable_mcp', False)
                    if not mcp_enabled:
                        logger.warning("MCP功能已关闭")
                        
                        message_content = [{
                            "type": "text",
                            "data": "⚠️ MCP功能已关闭，无法执行MCP工具操作\n💡 请在设置中启用MCP功能后重试"
                        }]
                        
                        standardized_response = {
                            "message_id": f"msg-{int(time.time())}-{hash(query_text) % 1000:03d}",
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "role": "assistant",
                            "content": message_content
                        }
                        
                        return jsonify({'success': True, 'data': standardized_response})
                    
                    # 步骤2：使用标准MCP系统分析和执行工具
                    try:
                        from app.services.mcp.servers.mcp_manager import MCPManager
                        from app.services.mcp_tool_analyzer import create_mcp_tool_analyzer
                        
                        # 创建MCP管理器实例
                        mcp_manager = MCPManager()
                        
                        # 初始化MCP系统（如果未初始化）
                        if not mcp_manager.is_initialized:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            init_success = loop.run_until_complete(mcp_manager.initialize())
                            loop.close()
                            
                            if not init_success:
                                message_content = [{
                                    "type": "text",
                                    "data": "❌ MCP系统初始化失败，无法执行工具操作"
                                }]
                                
                                standardized_response = {
                                    "message_id": f"msg-{int(time.time())}-{hash(query_text) % 1000:03d}",
                                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                    "role": "assistant",
                                    "content": message_content
                                }
                                
                                return jsonify({'success': True, 'data': standardized_response})
                        
                        # 创建带有MCP管理器的工具分析器
                        mcp_tool_analyzer = create_mcp_tool_analyzer(mcp_manager)
                        
                        # 使用LLM分析需要的工具
                        tool_analysis = mcp_tool_analyzer.analyze_tools_needed(query_text)
                        logger.info(f"工具分析结果: {tool_analysis}")
                        
                        # 获取分析的工具列表
                        tools_needed = tool_analysis.get('tools_needed', [])
                        if not tools_needed:
                            message_content = [{
                                "type": "text",
                                "data": "❌ 未能识别出需要执行的具体工具"
                            }]
                        else:
                            # 执行工具序列
                            message_content = []
                            
                            # 添加工具分析结果
                            message_content.append({
                                "type": "text",
                                "data": f"🎯 识别为MCP操作: {intent_analysis.get('reasoning', '已识别为MCP操作')}"
                            })
                            
                            if tool_analysis.get('reasoning'):
                                message_content.append({
                                    "type": "text",
                                    "data": f"🔧 工具分析: {tool_analysis['reasoning']}"
                                })
                            
                            # 按执行序列执行工具，确保所有工具都能执行
                            execution_sequence = tool_analysis.get('execution_sequence', [])
                            if execution_sequence:
                                # 按序列执行
                                for step in execution_sequence:
                                    tool_name = step.get('tool_name')
                                    tool_arguments = step.get('parameters', {})
                                    
                                    if not tool_name:
                                        continue
                                        
                                    try:
                                        logger.info(f"执行工具: {tool_name}, 参数: {tool_arguments}")
                                        
                                        # 调用标准MCP工具
                                        loop = asyncio.new_event_loop()
                                        asyncio.set_event_loop(loop)
                                        result = loop.run_until_complete(
                                            mcp_manager.call_tool(tool_name, tool_arguments)
                                        )
                                        loop.close()
                                        
                                        # 处理执行结果
                                        if result.isError:
                                            error_msg = result.content[0].get('text', 'Unknown error') if result.content else 'Unknown error'
                                            logger.error(f"工具 {tool_name} 执行失败: {error_msg}")
                                            message_content.append({
                                                "type": "text",
                                                "data": f"❌ 工具 {tool_name} 执行失败: {error_msg}"
                                            })
                                        else:
                                            # 成功执行
                                            tool_output = result.content[0].get('text', '操作完成') if result.content else '操作完成'
                                            logger.info(f"工具 {tool_name} 执行成功: {tool_output}")
                                            message_content.append({
                                                "type": "tool_call",
                                                "data": {
                                                    "tool": tool_name,
                                                    "params": tool_arguments,
                                                    "result": tool_output,
                                                    "user_visible": True
                                                }
                                            })
                                            
                                    except Exception as tool_error:
                                        logger.error(f"执行工具 {tool_name} 异常: {tool_error}")
                                        message_content.append({
                                            "type": "text",
                                            "data": f"❌ 工具 {tool_name} 执行异常: {str(tool_error)}"
                                        })
                            else:
                                # 降级到按工具列表执行
                                for tool_name in tools_needed:
                                    try:
                                        logger.info(f"降级执行工具: {tool_name}")
                                        
                                        # 调用标准MCP工具
                                        loop = asyncio.new_event_loop()
                                        asyncio.set_event_loop(loop)
                                        result = loop.run_until_complete(
                                            mcp_manager.call_tool(tool_name, {})
                                        )
                                        loop.close()
                                        
                                        # 处理执行结果
                                        if result.isError:
                                            error_msg = result.content[0].get('text', 'Unknown error') if result.content else 'Unknown error'
                                            message_content.append({
                                                "type": "text",
                                                "data": f"❌ 工具 {tool_name} 执行失败: {error_msg}"
                                            })
                                        else:
                                            # 成功执行
                                            tool_output = result.content[0].get('text', '操作完成') if result.content else '操作完成'
                                            message_content.append({
                                                "type": "tool_call",
                                                "data": {
                                                    "tool": tool_name,
                                                    "params": {},
                                                    "result": tool_output,
                                                    "user_visible": True
                                                }
                                            })
                                            
                                    except Exception as tool_error:
                                        logger.error(f"执行工具 {tool_name} 失败: {tool_error}")
                                        message_content.append({
                                            "type": "text",
                                            "data": f"❌ 工具 {tool_name} 执行异常: {str(tool_error)}"
                                        })
                        
                        # 收集所有工具执行结果
                        mcp_results = []
                        for i, content_item in enumerate(message_content):
                            if content_item.get("type") == "tool_call":
                                mcp_results.append({
                                    'tool_name': content_item["data"]["tool"],
                                    'arguments': content_item["data"]["params"],
                                    'result': content_item["data"]["result"],
                                    'error': None,
                                    'timestamp': time.time()
                                })
                            elif content_item.get("type") == "text" and "❌" in content_item.get("data", ""):
                                # 处理失败的工具调用
                                tool_name = tools_needed[0] if tools_needed else "unknown"
                                mcp_results.append({
                                    'tool_name': tool_name,
                                    'arguments': {},
                                    'result': None,
                                    'error': content_item["data"],
                                    'timestamp': time.time()
                                })
                        
                        # 构建标准化响应格式
                        standardized_response = {
                            "message_id": f"msg-{int(time.time())}-{hash(query_text) % 1000:03d}",
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "role": "assistant",
                            "content": message_content,
                            "legacy_data": {
                                'query': query_text,
                                'search_type': 'mcp_action',
                                'intent_analysis': intent_analysis,
                                'tool_analysis': tool_analysis,
                                'mcp_system': 'standard',
                                'mcp_results': mcp_results
                            }
                        }
                        
                        return jsonify({
                            'success': True,
                            'data': standardized_response
                        })
                        
                    except Exception as mcp_error:
                        logger.error(f"标准MCP系统执行失败: {mcp_error}")
                        
                        # 错误情况也返回标准化格式
                        message_content = [{
                            "type": "text",
                            "data": f"❌ MCP操作失败: {str(mcp_error)}"
                        }]
                        
                        standardized_response = {
                            "message_id": f"msg-{int(time.time())}-{hash(query_text) % 1000:03d}",
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "role": "assistant",
                            "content": message_content,
                            "legacy_data": {'error': str(mcp_error)}
                        }
                        
                        return jsonify({
                            'success': True,
                            'data': standardized_response
                        })
                        
                # 对于 knowledge_search 意图，继续执行向量检索（不需要特殊处理）
                elif intent_type == 'knowledge_search':
                    logger.info(f"执行知识库检索操作: {query_text}")
                    # 继续向下执行语义搜索逻辑
                    pass
                else:
                    # 置信度不够或未识别的意图，默认执行知识库检索
                    logger.info(f"意图不明确或置信度不足，执行默认知识库检索: {query_text}")
                        
            except Exception as e:
                logger.error(f"意图分析失败: {e}")
                # 降级到知识库检索
                intent_analysis = {
                    "intent_type": "knowledge_search",
                    "confidence": 0.5,
                    "reasoning": f"意图分析失败，降级到知识库检索: {str(e)}",
                    "used_llm": False,
                    "error": str(e),
                    "model_used": f"{Config.INTENT_ANALYSIS_LLM_PROVIDER}:{Config.INTENT_ANALYSIS_LLM_MODEL}",
                    "prompt_source": "config_file"
                }
        
        # 只有在没有特殊处理时才执行语义搜索（知识库检索）
        if not skip_search:
            try:
                # 进行关键词提取以优化搜索
                keyword_extraction = None
                search_query = query_text  # 默认使用原查询
                
                if llm_model:
                    try:
                        keyword_extraction = LLMService.extract_search_keywords(query_text, llm_model)
                        search_query = keyword_extraction.get('optimized_query', query_text)
                        logger.info(f"关键词提取完成 - 原查询: {query_text}, 优化查询: {search_query}")
                    except Exception as e:
                        logger.warning(f"关键词提取失败，使用原查询: {e}")
                        search_query = query_text
                
                # 设置合理的相似度阈值（避免返回太多低质量结果）
                min_score = 0.2  # 语义搜索的默认最低相似度阈值
                
                # 对人名等专有名词查询适当降低阈值
                if len(search_query.strip().split()) <= 2 and not any(word in search_query.lower() for word in ['创建', '新建', '帮我', '找到', '搜索']):
                    min_score = 0.15  # 简短查询（如人名）降低阈值
                    logger.info(f"检测到简短查询，降低相似度阈值到: {min_score}")
                
                # 使用优化后的查询进行向量搜索
                vector_service = VectorServiceAdapter()
                raw_results = vector_service.search_similar(
                    query_text=search_query, 
                    top_k=top_k,
                    min_score=min_score
                )
                
                # 补充文档信息，确保前端能正确显示结果
                search_results = []
                for result in raw_results:
                    document_id = result.get('document_id')
                    if document_id:
                        document = DocumentNode.query.get(document_id)
                        if document and not document.is_deleted:
                            # 为每个结果添加完整的document对象
                            enriched_result = {
                                'id': result.get('chunk_id', ''),
                                'document_id': document_id,
                                'chunk_id': result.get('chunk_id', ''),
                                'text': result.get('text', ''),
                                'score': result.get('score', 0),
                                'search_type': 'semantic',  # 添加搜索类型标识
                                'document': {
                                    'id': document.id,
                                    'name': document.name,
                                    'file_type': document.file_type,
                                    'file_size': document.file_size,
                                    'created_at': document.created_at.isoformat() if document.created_at else None,
                                    'description': document.description
                                }
                            }
                            search_results.append(enriched_result)
                
                logger.info(f"语义搜索完成，找到 {len(search_results)} 个结果")
                
                # 如果有LLM模型，进行结果聚合和智能分析
                file_results = []
                llm_answer = None
                reranked = False
                
                if llm_model and search_results:
                    try:
                        # 将chunk级别结果聚合为文件级别（复用混合搜索的聚合逻辑）
                        file_results = aggregate_results_by_file(search_results)
                        
                        # LLM结果重排序
                        if file_results:
                            try:
                                file_results = LLMService.rerank_file_results(query_text, file_results, llm_model)
                                reranked = True
                                logger.info(f"语义搜索LLM文件结果重排序完成 - 处理了 {len(file_results)} 个文件")
                            except Exception as e:
                                logger.warning(f"语义搜索LLM结果重排序失败: {e}")
                        
                        # LLM智能答案生成
                        if file_results:
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
                                    query_text, 
                                    context, 
                                    llm_model=llm_model,
                                    scenario=None,  # 让系统自动分析
                                    style=None      # 让系统自动推荐
                                )
                                logger.info(f"语义搜索智能LLM答案生成完成 - 查询: {query_text}")
                            except Exception as e:
                                logger.warning(f"语义搜索LLM答案生成失败: {e}")
                    except Exception as e:
                        logger.warning(f"语义搜索LLM处理失败: {e}")
                
            except Exception as e:
                logger.error(f"语义搜索失败: {str(e)}")
                search_results = []
                keyword_extraction = None
                file_results = []
                llm_answer = None
                reranked = False
        
        # 构建响应数据
        response_data = {
            'query': query_text,
            'results': file_results,
            'file_results': file_results,  # 保持向后兼容
            'total_results': len(file_results),
            'search_type': 'semantic',
            'similarity_level': 'medium',  # 默认相似度级别
            'min_score': min_score if not skip_search else 0.0,
            'optimized_query': search_query if not skip_search else query_text,
            'original_query': query_text,
            'reranked': reranked,
            'mcp_results': mcp_tool_results if mcp_tool_results else [],
            'llm_info': {
                'model': llm_model,
                'answer': llm_answer if 'llm_answer' in locals() else None,
                'enabled': llm_model is not None
            } if 'llm_answer' in locals() and llm_answer else None
        }
        
        # 添加意图分析结果
        if intent_analysis:
            response_data['intent_analysis'] = {
                'intent_type': intent_analysis.get('intent_type'),
                'confidence': intent_analysis.get('confidence'),
                'action_type': intent_analysis.get('action_type'),
                'reasoning': intent_analysis.get('reasoning'),
                'used_llm': True,
                'model': intent_analysis.get('model_used'),
                'prompt_source': intent_analysis.get('prompt_source', 'config_file')
            }
        
        # 添加关键词提取信息
        if 'keyword_extraction' in locals() and keyword_extraction:
            response_data['keyword_extraction'] = keyword_extraction
        
        # 转换为标准化消息格式
        message_content = []
        
        # 1. 添加意图分析结果（如果有）
        if intent_analysis and intent_analysis.get('confidence', 0) > Config.INTENT_ANALYSIS_CONFIDENCE_THRESHOLD:
            message_content.append({
                "type": "text",
                "data": f"🎯 意图识别: {intent_analysis.get('reasoning', '已识别用户意图')}"
            })
        
        # 2. 添加LLM答案（如果有）
        if 'llm_answer' in locals() and llm_answer:
            message_content.append({
                "type": "markdown",
                "data": llm_answer
            })
        
        # 3. 添加MCP工具执行结果（如果有）
        if mcp_tool_results:
            for mcp_result in mcp_tool_results:
                # 处理dataclass对象或字典
                error = getattr(mcp_result, 'error', None) if hasattr(mcp_result, 'error') else mcp_result.get('error') if isinstance(mcp_result, dict) else None
                if error:
                    message_content.append({
                        "type": "text",
                        "data": f"❌ 工具执行失败: {error}"
                    })
                else:
                    tool_name = getattr(mcp_result, 'tool_name', None) if hasattr(mcp_result, 'tool_name') else mcp_result.get('tool_name', 'unknown') if isinstance(mcp_result, dict) else 'unknown'
                    arguments = getattr(mcp_result, 'arguments', {}) if hasattr(mcp_result, 'arguments') else mcp_result.get('arguments', {}) if isinstance(mcp_result, dict) else {}
                    result = getattr(mcp_result, 'result', None) if hasattr(mcp_result, 'result') else mcp_result.get('result') if isinstance(mcp_result, dict) else None
                    
                    message_content.append({
                        "type": "tool_call",
                        "data": {
                            "tool": tool_name,
                            "params": arguments,
                            "result": result,
                            "user_visible": True
                        }
                    })
        
        # 4. 添加搜索结果表格（如果有文件结果）
        if file_results:
            # 构建搜索结果表格
            table_headers = ["文档", "相关度", "搜索类型", "内容预览"]
            table_rows = []
            
            for file_result in file_results[:5]:  # 限制显示前5个结果
                document = file_result.get('document', {})
                
                # 计算平均相关度
                score = file_result.get('score', 0)
                score_display = f"{score:.2f}" if score > 0 else "N/A"
                
                # 搜索类型
                search_types = file_result.get('search_types', ['unknown'])
                search_type_display = "+".join(search_types)
                
                # 内容预览（使用最佳chunk）
                chunks = file_result.get('chunks', [])
                content_preview = chunks[0].get('text', '')[:100] + "..." if chunks else "无预览"
                
                # 创建可点击的文件名（带文档ID用于前端点击处理）
                file_name_with_link = {
                    "text": document.get('name', '未知文档'),
                    "document_id": document.get('id')
                }
                
                table_rows.append([
                    file_name_with_link,
                    score_display,
                    search_type_display,
                    content_preview
                ])
            
            if table_rows:
                message_content.append({
                    "type": "table",
                    "data": {
                        "headers": table_headers,
                        "rows": table_rows
                    }
                })
        
        # 6. 如果没有找到结果，添加建议
        if not file_results and not mcp_tool_results:
            message_content.append({
                "type": "text",
                "data": "😔 未找到相关内容，建议："
            })
            message_content.append({
                "type": "markdown",
                "data": f"""
## 💡 搜索建议

- **调整关键词**: 尝试使用更具体的词汇
- **降低相似度**: 当前设置为 `medium`，可尝试 `low` 或 `any`
- **检查拼写**: 确认搜索词拼写正确
- **使用同义词**: 尝试相关的同义词或近义词

**原始查询**: `{query_text}`  
**优化查询**: `{search_query if not skip_search else query_text}`
"""
            })
        
        # 构建标准化响应格式
        standardized_response = {
            "message_id": f"msg-{int(time.time())}-{hash(query_text) % 1000:03d}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "role": "assistant",
            "content": message_content,
            # 保持原有数据结构以确保向后兼容
            "legacy_data": response_data
        }
        
        return jsonify({
            'success': True,
            'data': standardized_response
        })
        
    except Exception as e:
        logger.error(f"语义搜索请求处理失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'搜索失败: {str(e)}'
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
        # 直接使用配置文件中的设置
        vector_service = VectorServiceAdapter()
        
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
        enable_intent_analysis = data.get('enable_intent_analysis', True)
        
        logger.info(f"收到混合搜索请求 - query: {query_text}, similarity_level: {similarity_level}, use_llm: {use_llm}, llm_model: {llm_model}")
        
        if not query_text:
            return jsonify({
                'success': False,
                'error': '查询文本不能为空'
            }), 400
        
        # 初始化结果变量
        semantic_results = []
        keyword_results = []
        combined_results = []
        file_results = []
        mcp_tool_results = []
        skip_search = False
        intent_analysis = None
        
        # 使用专用的意图识别模型进行智能意图分析
        if Config.ENABLE_INTENT_ANALYSIS and enable_intent_analysis:
            try:
                from app.services.llm import LLMService
                # 使用专用的意图识别模型
                intent_llm_model = f"{Config.INTENT_ANALYSIS_LLM_PROVIDER}:{Config.INTENT_ANALYSIS_LLM_MODEL}"
                intent_analysis = LLMService.analyze_user_intent(query_text, intent_llm_model)
                logger.info(f"意图分析结果: {intent_analysis}")
                
                # 使用配置的置信度阈值
                confidence_threshold = Config.INTENT_ANALYSIS_CONFIDENCE_THRESHOLD
                
                # 根据意图分析结果决定处理方式
                if (intent_analysis.get('intent_type') == 'folder_analysis' and 
                    intent_analysis.get('confidence', 0) > confidence_threshold and
                    intent_analysis.get('action_type') == 'analyze_folder'):
                    
                    logger.info(f"执行文件夹分析操作: {query_text}")
                    skip_search = True
                    
                    # 执行文件夹分析
                    from app.services.folder_analysis_service import FolderAnalysisService
                    
                    try:
                        # 使用用户选择的LLM模型进行分析，而不是意图识别模型
                        analysis_result = FolderAnalysisService.analyze_folder_completeness(
                            query_text, llm_model or intent_llm_model, intent_analysis
                        )
                        logger.info(f"文件夹分析完成")
                        
                        # 构建分析响应
                        response_data = {
                            'query': query_text,
                            'is_analysis': True,
                            'analysis_result': analysis_result,
                            'search_type': 'folder_analysis',
                            'intent_analysis': {
                                'intent_type': intent_analysis.get('intent_type'),
                                'confidence': intent_analysis.get('confidence'),
                                'action_type': intent_analysis.get('action_type'),
                                'reasoning': intent_analysis.get('reasoning'),
                                'used_llm': True,
                                'model': intent_analysis.get('model_used', intent_llm_model),
                                'prompt_source': intent_analysis.get('prompt_source', 'config_file'),
                                'confidence_threshold': confidence_threshold
                            }
                        }
                        
                        return jsonify({
                            'success': True,
                            'data': response_data
                        })
                        
                    except Exception as analysis_error:
                        logger.error(f"文件夹分析失败: {analysis_error}")
                        return jsonify({
                            'success': False,
                            'error': f"文件夹分析失败: {str(analysis_error)}"
                        }), 500
                
                elif (intent_analysis.get('intent_type') == 'mcp_action' and 
                    intent_analysis.get('confidence', 0) > confidence_threshold and
                    intent_analysis.get('action_type') in ['create_file', 'create_folder']):
                    
                    logger.info(f"执行MCP操作: {query_text}")
                    skip_search = True
                    
                    # 使用完整的MCP工具分析和执行流程
                    from app.services.mcp_tool_analyzer import create_mcp_tool_analyzer
                    from app.services.mcp_tool_executor import mcp_tool_executor
                    
                    # 创建工具分析器实例
                    mcp_tool_analyzer = create_mcp_tool_analyzer()
                    
                    # 1. 分析需要的工具
                    tool_analysis = mcp_tool_analyzer.analyze_tools_needed(query_text)
                    
                    # 2. 验证工具可用性
                    tool_validation = mcp_tool_analyzer.validate_tools(tool_analysis.get('tools_needed', []))
                    
                    if not tool_validation['all_valid']:
                        # 有不可用的工具，返回错误信息
                        error_msg = mcp_tool_analyzer.get_error_message(tool_validation['error_type'], tool_validation.get('invalid_tools', []))
                        mcp_tool_results = [{'tool_name': 'error', 'arguments': {}, 'result': None, 'error': error_msg, 'timestamp': time.time()}]
                        logger.warning(f"MCP工具验证失败: {error_msg}")
                    else:
                        # 3. 执行工具
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            mcp_tool_results = loop.run_until_complete(
                                mcp_tool_executor.execute_tools_from_analysis(query_text, tool_analysis)
                            )
                            logger.info(f"基于LLM分析的MCP工具执行完成，共 {len(mcp_tool_results)} 个步骤")
                        except Exception as mcp_error:
                            logger.error(f"MCP工具执行失败: {mcp_error}")
                            mcp_tool_results = [{
                                'tool_name': 'error',
                                'arguments': {},
                                'result': None,
                                'error': f"MCP工具执行失败: {str(mcp_error)}",
                                'timestamp': time.time()
                            }]
                        finally:
                            loop.close()
                        
            except Exception as e:
                logger.error(f"意图分析失败: {e}")
                # 降级到向量搜索
                intent_analysis = {
                    "intent_type": "vector_search",
                    "confidence": 0.5,
                    "action_type": "search_documents",
                    "reasoning": f"意图分析失败，降级到向量搜索: {str(e)}",
                    "used_llm": False,
                    "error": str(e),
                    "model_used": f"{Config.INTENT_ANALYSIS_LLM_PROVIDER}:{Config.INTENT_ANALYSIS_LLM_MODEL}",
                    "prompt_source": "config_file"
                }
        
        # 只有在没有MCP操作时才执行搜索
        if not skip_search:
            # 进行关键词提取以优化搜索
            original_query = query_text
            optimized_query = query_text
            keyword_extraction = None
            
            if use_llm and llm_model:
                try:
                    # 使用专门的关键词提取功能
                    keyword_extraction = LLMService.extract_search_keywords(query_text, llm_model)
                    optimized_query = keyword_extraction.get('optimized_query', query_text)
                    logger.info(f"混合搜索关键词提取完成 - 原查询: {query_text}, 优化查询: {optimized_query}")
                except Exception as e:
                    logger.warning(f"混合搜索关键词提取失败，使用原查询: {e}")
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
        else:
            # 如果跳过搜索，初始化变量以避免后续处理中的错误
            original_query = query_text
            optimized_query = query_text
            min_score = 0.0
            file_results = []  # 初始化空的文件结果列表
            semantic_results = []  # 初始化空的语义搜索结果
            keyword_results = []   # 初始化空的关键词搜索结果
        
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

        # 7. MCP工具调用已在前面处理
        
        response_data = {
            'query': query_text,
            'similarity_level': similarity_level,
            'total_files': len(file_results),
            'file_results': file_results,
            'search_type': 'hybrid'
        }
        
        # 只在执行了搜索时才添加这些信息
        if not skip_search:
            response_data.update({
                'min_score': min_score,
                'semantic_count': len(semantic_results),
                'keyword_count': len(keyword_results)
            })
        
        # 添加意图分析结果
        if intent_analysis:
            response_data['intent_analysis'] = {
                'intent_type': intent_analysis.get('intent_type'),
                'confidence': intent_analysis.get('confidence'),
                'action_type': intent_analysis.get('action_type'),
                'reasoning': intent_analysis.get('reasoning'),
                'used_llm': True
            }
        
        # 添加关键词提取结果
        if not skip_search and 'keyword_extraction' in locals() and keyword_extraction:
            response_data['keyword_extraction'] = {
                'original_query': keyword_extraction.get('original_query'),
                'keywords': keyword_extraction.get('keywords'),
                'optimized_query': keyword_extraction.get('optimized_query'),
                'reasoning': keyword_extraction.get('reasoning'),
                'used_llm': keyword_extraction.get('used_llm', False)
            }
        
        # 添加LLM处理信息
        if use_llm:
            response_data['llm_info'] = {
                'used': True,
                'model': llm_model,
                'original_query': original_query if not skip_search else query_text,
                'optimized_query': optimized_query if not skip_search else query_text,
                'query_optimized': (optimized_query != original_query) if not skip_search else False,
                'reranked': reranked,
                'answer': llm_answer
            }
        else:
            response_data['llm_info'] = {
                'used': False
            }
        
        # 添加MCP工具结果
        if mcp_tool_results:
            response_data['mcp_results'] = [{
                'tool_name': result.tool_name if hasattr(result, 'tool_name') else result.get('tool_name'),
                'arguments': result.arguments if hasattr(result, 'arguments') else result.get('arguments', {}),
                'result': result.result if hasattr(result, 'result') else result.get('result'),
                'error': result.error if hasattr(result, 'error') else result.get('error'),
                'timestamp': result.timestamp if hasattr(result, 'timestamp') else result.get('timestamp')
            } for result in mcp_tool_results]
        
        logger.info(f"混合搜索完成 - semantic: {len(semantic_results)}, keyword: {len(keyword_results)}, files: {len(file_results)}")
        
        # 转换为标准化消息格式
        message_content = []
        
        # 1. 添加意图分析结果（如果有）
        if intent_analysis and intent_analysis.get('confidence', 0) > Config.INTENT_ANALYSIS_CONFIDENCE_THRESHOLD:
            message_content.append({
                "type": "text",
                "data": f"🎯 意图识别: {intent_analysis.get('reasoning', '已识别用户意图')}"
            })
        
        # 2. 添加LLM答案（如果有）
        if 'llm_answer' in locals() and llm_answer:
            message_content.append({
                "type": "markdown",
                "data": llm_answer
            })
        
        # 3. 添加MCP工具执行结果（如果有）
        if mcp_tool_results:
            for mcp_result in mcp_tool_results:
                # 处理dataclass对象或字典
                error = getattr(mcp_result, 'error', None) if hasattr(mcp_result, 'error') else mcp_result.get('error') if isinstance(mcp_result, dict) else None
                if error:
                    message_content.append({
                        "type": "text",
                        "data": f"❌ 工具执行失败: {error}"
                    })
                else:
                    tool_name = getattr(mcp_result, 'tool_name', None) if hasattr(mcp_result, 'tool_name') else mcp_result.get('tool_name', 'unknown') if isinstance(mcp_result, dict) else 'unknown'
                    arguments = getattr(mcp_result, 'arguments', {}) if hasattr(mcp_result, 'arguments') else mcp_result.get('arguments', {}) if isinstance(mcp_result, dict) else {}
                    result = getattr(mcp_result, 'result', None) if hasattr(mcp_result, 'result') else mcp_result.get('result') if isinstance(mcp_result, dict) else None
                    
                    message_content.append({
                        "type": "tool_call",
                        "data": {
                            "tool": tool_name,
                            "params": arguments,
                            "result": result,
                            "user_visible": True
                        }
                    })
        
        # 4. 添加搜索结果表格（如果有文件结果）
        if file_results:
            # 构建搜索结果表格
            table_headers = ["文档", "相关度", "搜索类型", "内容预览"]
            table_rows = []
            
            for file_result in file_results[:5]:  # 限制显示前5个结果
                document = file_result.get('document', {})
                
                # 计算平均相关度
                score = file_result.get('score', 0)
                score_display = f"{score:.2f}" if score > 0 else "N/A"
                
                # 搜索类型
                search_types = file_result.get('search_types', ['unknown'])
                search_type_display = "+".join(search_types)
                
                # 内容预览（使用最佳chunk）
                chunks = file_result.get('chunks', [])
                content_preview = chunks[0].get('text', '')[:100] + "..." if chunks else "无预览"
                
                # 创建可点击的文件名（带文档ID用于前端点击处理）
                file_name_with_link = {
                    "text": document.get('name', '未知文档'),
                    "document_id": document.get('id')
                }
                
                table_rows.append([
                    file_name_with_link,
                    score_display,
                    search_type_display,
                    content_preview
                ])
            
            if table_rows:
                message_content.append({
                    "type": "table",
                    "data": {
                        "headers": table_headers,
                        "rows": table_rows
                    }
                })
        
        # 6. 如果没有找到结果，添加建议
        if not file_results and not mcp_tool_results:
            message_content.append({
                "type": "text",
                "data": "😔 未找到相关内容，建议："
            })
            message_content.append({
                "type": "markdown",
                "data": f"""
## 💡 搜索建议

- **调整关键词**: 尝试使用更具体的词汇
- **降低相似度**: 当前设置为 `{similarity_level}`，可尝试 `low` 或 `any`
- **检查拼写**: 确认搜索词拼写正确
- **使用同义词**: 尝试相关的同义词或近义词

**原始查询**: `{original_query}`  
**优化查询**: `{optimized_query}`
"""
            })
        
        # 构建标准化响应格式
        standardized_response = {
            "message_id": f"msg-{int(time.time())}-{hash(query_text) % 1000:03d}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "role": "assistant",
            "content": message_content,
            # 保持原有数据结构以确保向后兼容
            "legacy_data": response_data
        }
        
        return jsonify({
            'success': True,
            'data': standardized_response
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

def detect_analysis_intent(query_text):
    """检测查询中是否包含文档分析意图"""
    import re
    
    # 分析意图关键词 - 扩展更多模式
    analysis_keywords = [
        # 基本分析模式
        r'分析.*?文档', r'分析.*?文件', r'分析.*?资料',
        r'文档.*?分析', r'文件.*?分析', r'资料.*?分析',
        r'分析.*?目录', r'目录.*?分析',
        r'分析.*?文件夹', r'文件夹.*?分析',
        
        # 检查和评估类
        r'检查.*?文档', r'检查.*?文件', r'检查.*?结构', r'检查.*?文件夹',
        r'评估.*?文档', r'评估.*?文件', r'评估.*?结构', r'评估.*?文件夹',
        
        # 缺失分析类 - 新增
        r'.*?缺少.*?内容', r'.*?缺失.*?内容', r'.*?还需要.*?',
        r'.*?还缺.*?', r'.*?少.*?内容', r'.*?不足.*?',
        
        # 完整性检查类 - 新增  
        r'.*?完整.*?检查', r'.*?完整.*?分析', r'.*?齐全.*?',
        r'.*?内容.*?完整', r'.*?材料.*?齐全',
        
        # 直接分析模式 - 新增
        r'^分析\s*[^\s]{1,30}$',  # 分析XXX（简短文档名）
        r'^分析\s*.{1,50}$'       # 分析任意内容（中等长度）
    ]
    
    query_lower = query_text.lower().strip()
    
    # 检查是否匹配分析意图
    for pattern in analysis_keywords:
        if re.search(pattern, query_lower):
            # 尝试提取文档名称
            doc_name = extract_document_name(query_text, pattern)
            return {
                'is_analysis': True,
                'document_name': doc_name,
                'original_query': query_text,
                'matched_pattern': pattern
            }
    
    return {'is_analysis': False}

def extract_document_name(query_text, matched_pattern):
    """从查询文本中提取文档名称"""
    import re
    
    # 常见的文档名称提取模式 - 扩展更多模式
    patterns = [
        # 引用格式
        r'分析["\']([^"\']+)["\']',  # 分析"文档名"
        r'分析《([^》]+)》',         # 分析《文档名》
        
        # 基本分析格式
        r'分析(?:文档|文件|资料|文件夹)?[：:]?\s*([^\s，。！？]+)',  # 分析文档：名称 或 分析 名称
        r'([^\s，。！？]+)(?:文档|文件|资料|文件夹)?.*?分析',  # 名称文档分析
        r'分析.*?([^\s，。！？]{2,20})(?:文档|文件|资料|目录|文件夹)',  # 分析XX文档
        
        # 缺失分析类 - 新增
        r'([^，。！？\s]+).*?(?:缺少|缺失|还需要|还缺|少|不足).*?内容',  # XX缺少内容
        r'.*?缺少.*?([^，。！？\s]+).*?内容',  # 缺少XX内容
        
        # 完整性检查类
        r'([^，。！？\s]+).*?(?:完整|齐全)',  # XX完整
        r'(?:完整|齐全).*?([^，。！？\s]+)',  # 完整XX
        
        # 通用模式 - 匹配文档ID或名称
        r'分析\s*([0-9]+[^\s，。！？]*)',  # 分析01毕磊
        r'分析\s*([^\s，。！？]{2,30})',    # 分析任意名称
        
        # 从文件夹描述中提取
        r'([^，。！？\s]+)\s*(?:这个|那个|该|此)?\s*(?:文件夹|目录)',  # XX文件夹
    ]
    
    # 按优先级尝试提取
    for pattern in patterns:
        match = re.search(pattern, query_text)
        if match:
            doc_name = match.group(1).strip()
            
            # 清理常见的停用词和无意义词汇
            doc_name = re.sub(r'^(这个|那个|该|此|一下|下|的)\s*', '', doc_name)
            doc_name = re.sub(r'\s*(的|吧|呢|啊|吗|文档|文件|资料|文件夹|目录)$', '', doc_name)
            
            # 确保提取的名称有意义（长度>=1，不全是标点符号）
            if len(doc_name) >= 1 and re.search(r'[a-zA-Z0-9\u4e00-\u9fff]', doc_name):
                return doc_name
    
    # 如果以上都没匹配，尝试简单的空格分割
    words = query_text.split()
    if len(words) >= 2 and words[0] in ['分析', '检查', '评估']:
        # 从第二个词开始组合可能的文档名
        for i in range(1, len(words)):
            candidate = ''.join(words[1:i+1])
            if re.search(r'[a-zA-Z0-9\u4e00-\u9fff]', candidate) and len(candidate) >= 1:
                return candidate
    
    return None

def handle_document_analysis(analysis_intent, llm_model):
    """处理文档分析请求"""
    try:
        doc_name = analysis_intent.get('document_name')
        original_query = analysis_intent.get('original_query')
        
        if not doc_name:
            return jsonify({
                'success': True,
                'data': {
                    'query': original_query,
                    'is_analysis': True,
                    'analysis_result': {
                        'type': 'error',
                        'message': '未能从查询中识别出具体的文档名称。请明确指定要分析的文档，例如："分析项目文档"或"分析《合同管理》文件"。'
                    }
                }
            })
        
        # 搜索匹配的文档
        documents = DocumentNode.query.filter(
            DocumentNode.name.contains(doc_name),
            DocumentNode.is_deleted == False
        ).limit(10).all()
        
        if not documents:
            return jsonify({
                'success': True,
                'data': {
                    'query': original_query,
                    'is_analysis': True,
                    'analysis_result': {
                        'type': 'not_found',
                        'message': f'未找到名称包含"{doc_name}"的文档。请检查文档名称是否正确，或者使用文档搜索功能查看可用的文档列表。',
                        'searched_name': doc_name
                    }
                }
            })
        
        # 如果找到多个文档，让用户选择
        if len(documents) > 1:
            doc_list = []
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
                doc_list.append(doc_data)
            
            return jsonify({
                'success': True,
                'data': {
                    'query': original_query,
                    'is_analysis': True,
                    'analysis_result': {
                        'type': 'multiple_found',
                        'message': f'找到{len(documents)}个包含"{doc_name}"的文档，请明确指定要分析的文档：',
                        'documents': doc_list,
                        'searched_name': doc_name
                    }
                }
            })
        
        # 找到唯一文档，执行分析
        document = documents[0]
        
        if not llm_model:
            return jsonify({
                'success': True,
                'data': {
                    'query': original_query,
                    'is_analysis': True,
                    'analysis_result': {
                        'type': 'no_model',
                        'message': '文档分析需要选择AI模型。请在设置中选择一个可用的AI模型后重试。',
                        'document': document.to_dict()
                    }
                }
            })
        
        # 执行文档分析
        try:
            # 获取文档标签信息
            document_tags = [tag.to_dict() for tag in document.tags]
            
            # 构建文档树结构
            def build_document_tree(node):
                result = {
                    'id': node.id,
                    'name': node.name,
                    'type': node.type,
                    'file_type': node.file_type,
                    'description': node.description,
                    'children': []
                }
                
                children = DocumentNode.query.filter_by(
                    parent_id=node.id,
                    is_deleted=False
                ).order_by(DocumentNode.type.desc(), DocumentNode.name).all()
                
                for child in children:
                    result['children'].append(build_document_tree(child))
                
                return result
            
            document_tree = build_document_tree(document)
            
            # 调用LLM分析服务
            analysis_result = LLMService.analyze_document_structure(
                document_name=document.name,
                document_tags=document_tags,
                document_tree=document_tree,
                llm_model=llm_model
            )
            
            if not analysis_result:
                return jsonify({
                    'success': True,
                    'data': {
                        'query': original_query,
                        'is_analysis': True,
                        'analysis_result': {
                            'type': 'analysis_failed',
                            'message': 'AI模型分析失败，请稍后重试或尝试其他AI模型。',
                            'document': document.to_dict()
                        }
                    }
                })
            
            # 返回分析结果
            return jsonify({
                'success': True,
                'data': {
                    'query': original_query,
                    'is_analysis': True,
                    'analysis_result': {
                        'type': 'success',
                        'message': f'已完成对文档《{document.name}》的智能分析：',
                        'document': document.to_dict(),
                        'analysis': analysis_result,
                        'llm_model': llm_model
                    }
                }
            })
            
        except Exception as e:
            logger.error(f"文档分析执行失败: {e}")
            return jsonify({
                'success': True,
                'data': {
                    'query': original_query,
                    'is_analysis': True,
                    'analysis_result': {
                        'type': 'error',
                        'message': f'文档分析过程中发生错误：{str(e)}',
                        'document': document.to_dict()
                    }
                }
            })
            
    except Exception as e:
        logger.error(f"处理文档分析请求失败: {e}")
        return jsonify({
            'success': False,
            'error': f'处理文档分析请求失败: {str(e)}'
        }), 500


def _extract_tool_arguments(tool_info: dict, query_text: str) -> dict:
    """从查询文本中提取工具参数"""
    tool_name = tool_info.get('name', '')
    parameters = tool_info.get('parameters', {})
    arguments = {}
    
    try:
        # 根据工具类型和参数定义提取参数
        if tool_name == 'navigate':
            # 提取URL
            import re
            url_pattern = r'https?://[^\s]+'
            url_match = re.search(url_pattern, query_text)
            if url_match:
                arguments['url'] = url_match.group()
            else:
                # 如果没有找到完整URL，可能需要用户补充
                arguments['url'] = 'https://www.example.com'
        
        elif tool_name == 'web_search':
            # 对于网络搜索，直接使用查询文本
            arguments['query'] = query_text
            arguments['num_results'] = 5
        
        elif tool_name == 'screenshot':
            # 截图工具通常不需要特定参数
            arguments['full_page'] = True
        
        elif tool_name == 'click':
            # 点击需要选择器，从查询中提取
            if '按钮' in query_text:
                arguments['selector'] = 'button'
            elif '链接' in query_text:
                arguments['selector'] = 'a'
            else:
                arguments['selector'] = '*'
        
        elif tool_name == 'fill_form':
            # 表单填写需要选择器和值
            arguments['selector'] = 'input'
            arguments['value'] = '示例值'
        
        elif tool_name == 'get_page_content':
            # 获取页面内容
            import re
            url_pattern = r'https?://[^\s]+'
            url_match = re.search(url_pattern, query_text)
            if url_match:
                arguments['url'] = url_match.group()
            else:
                arguments['url'] = 'https://www.example.com'
        
        # 如果工具有必需参数但未提取到，使用默认值
        for param_name, param_info in parameters.items():
            if param_name not in arguments and not param_info.get('optional', False):
                if param_info.get('type') == 'string':
                    arguments[param_name] = f"从查询提取: {query_text[:50]}"
                elif param_info.get('type') == 'integer':
                    arguments[param_name] = param_info.get('default', 1)
                elif param_info.get('type') == 'boolean':
                    arguments[param_name] = param_info.get('default', True)
        
        logger.info(f"提取工具参数 - 工具: {tool_name}, 参数: {arguments}")
        return arguments
        
    except Exception as e:
        logger.warning(f"提取工具参数失败: {e}")
        return {} 