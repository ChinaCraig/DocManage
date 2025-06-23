"""
文档生成服务 - 基于现有文件/文件夹生成新文档
版本: v1.0
功能: 支持基于文件夹或文件内容生成txt文档，使用模块化设计便于扩展
"""

import os
import re
import json
import logging
import time
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from sqlalchemy import and_, or_

from app.models.document_models import DocumentNode, DocumentContent, db
from app.services.llm import LLMService
from app.services.image_recognition_service import ImageRecognitionService

logger = logging.getLogger(__name__)

class DocumentGenerationService:
    """文档生成服务"""
    
    # 支持的输出格式
    SUPPORTED_FORMATS = ['txt']  # 当前只支持txt，后续可扩展
    
    # 支持的文档类型
    DOCUMENT_TYPES = {
        'summary': '总结汇总',
        'report': '分析报告', 
        'analysis': '深度分析',
        'documentation': '说明文档',
        'other': '其他类型'
    }
    
    @staticmethod
    def generate_document(source_path: str, output_format: str = 'txt', 
                         document_type: str = 'summary', 
                         query_text: str = '',
                         llm_model: str = None) -> Dict[str, Any]:
        """
        生成文档主入口
        
        Args:
            source_path: 源文件或文件夹路径/名称
            output_format: 输出格式 (当前只支持txt)
            document_type: 文档类型
            query_text: 原始查询文本
            llm_model: LLM模型
            
        Returns:
            Dict: 生成结果
        """
        try:
            # 1. 验证输出格式
            if output_format not in DocumentGenerationService.SUPPORTED_FORMATS:
                return {
                    'success': False,
                    'error': f'暂不支持 {output_format} 格式，当前只支持: {", ".join(DocumentGenerationService.SUPPORTED_FORMATS)}',
                    'query': query_text
                }
            
            # 2. 查找源文件或文件夹
            source_node = DocumentGenerationService._find_source_node(source_path)
            if not source_node:
                return {
                    'success': False,
                    'error': f'未找到源文件或文件夹: "{source_path}"',
                    'query': query_text,
                    'source_path': source_path
                }
            
            # 3. 根据源类型处理
            if source_node.type == 'folder':
                return DocumentGenerationService._generate_from_folder(
                    source_node, output_format, document_type, query_text, llm_model
                )
            else:
                return DocumentGenerationService._generate_from_file(
                    source_node, output_format, document_type, query_text, llm_model
                )
                
        except Exception as e:
            logger.error(f"文档生成失败: {e}")
            return {
                'success': False,
                'error': f'文档生成过程中出现错误: {str(e)}',
                'query': query_text,
                'source_path': source_path
            }
    
    @staticmethod
    def _find_source_node(source_path: str) -> Optional[DocumentNode]:
        """查找源文件或文件夹节点"""
        try:
            # 清理路径名称
            source_name = source_path.strip()
            
            # 移除常见的修饰词
            source_name = re.sub(r'^(?:这个|那个|该|此)', '', source_name)
            source_name = re.sub(r'(?:文件夹|文件|目录)$', '', source_name).strip()
            
            # 按优先级查找：完全匹配 -> 包含匹配 -> 模糊匹配
            search_conditions = [
                DocumentNode.name == source_name,  # 完全匹配
                DocumentNode.name.like(f'%{source_name}%'),  # 包含匹配
            ]
            
            for condition in search_conditions:
                nodes = DocumentNode.query.filter(
                    and_(condition, DocumentNode.is_deleted == False)
                ).all()
                
                if nodes:
                    # 如果有多个匹配，优先返回文件夹
                    for node in nodes:
                        if node.type == 'folder':
                            return node
                    # 如果没有文件夹，返回第一个文件
                    return nodes[0]
            
            return None
            
        except Exception as e:
            logger.error(f"查找源节点失败: {e}")
            return None
    
    @staticmethod
    def _generate_from_folder(folder: DocumentNode, output_format: str, 
                             document_type: str, query_text: str, 
                             llm_model: str = None) -> Dict[str, Any]:
        """基于文件夹生成文档"""
        try:
            logger.info(f"开始基于文件夹 '{folder.name}' 生成 {document_type} 文档")
            
            # 1. 获取文件夹下的所有文件
            files = DocumentGenerationService._get_folder_files(folder)
            if not files:
                return {
                    'success': False,
                    'error': f'文件夹 "{folder.name}" 中没有找到文件',
                    'query': query_text,
                    'folder_info': folder.to_dict()
                }
            
            # 2. 提取文件内容
            file_contents = []
            processed_count = 0
            
            for file_node in files:
                try:
                    content = DocumentGenerationService._extract_file_content(file_node)
                    if content:
                        file_contents.append({
                            'file_name': file_node.name,
                            'file_type': file_node.file_type,
                            'content': content[:2000]  # 限制内容长度避免token过多
                        })
                        processed_count += 1
                        
                        # 暂时限制处理文件数量，避免token超限
                        if processed_count >= 10:
                            break
                except Exception as e:
                    logger.warning(f"提取文件 {file_node.name} 内容失败: {e}")
                    continue
            
            if not file_contents:
                return {
                    'success': False,
                    'error': f'文件夹 "{folder.name}" 中的文件内容无法提取',
                    'query': query_text,
                    'folder_info': folder.to_dict(),
                    'total_files': len(files)
                }
            
            # 3. 使用LLM生成文档
            generated_content = DocumentGenerationService._generate_content_with_llm(
                source_type='folder',
                source_name=folder.name,
                source_contents=file_contents,
                document_type=document_type,
                query_text=query_text,
                llm_model=llm_model
            )
            
            # 4. 保存生成的文档（当前只支持txt）
            saved_file = DocumentGenerationService._save_generated_document(
                content=generated_content,
                source_name=folder.name,
                document_type=document_type,
                output_format=output_format,
                parent_folder=folder,
                query_text=query_text
            )
            
            return {
                'success': True,
                'query': query_text,
                'source_type': 'folder',
                'source_info': folder.to_dict(),
                'processed_files_count': processed_count,
                'total_files_count': len(files),
                'document_type': document_type,
                'output_format': output_format,
                'generated_content': generated_content,
                'saved_file': saved_file.to_dict() if saved_file else None,
                'generation_method': 'llm_folder_analysis',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"基于文件夹生成文档失败: {e}")
            return {
                'success': False,
                'error': f'基于文件夹生成文档失败: {str(e)}',
                'query': query_text,
                'folder_info': folder.to_dict() if folder else None
            }
    
    @staticmethod
    def _generate_from_file(file: DocumentNode, output_format: str, 
                           document_type: str, query_text: str,
                           llm_model: str = None) -> Dict[str, Any]:
        """基于单个文件生成文档"""
        try:
            logger.info(f"开始基于文件 '{file.name}' 生成 {document_type} 文档")
            
            # 1. 提取文件内容
            content = DocumentGenerationService._extract_file_content(file)
            if not content:
                return {
                    'success': False,
                    'error': f'无法提取文件 "{file.name}" 的内容',
                    'query': query_text,
                    'file_info': file.to_dict()
                }
            
            # 2. 准备文件内容数据
            file_contents = [{
                'file_name': file.name,
                'file_type': file.file_type,
                'content': content[:3000]  # 单文件可以允许更多内容
            }]
            
            # 3. 使用LLM生成文档
            generated_content = DocumentGenerationService._generate_content_with_llm(
                source_type='file',
                source_name=file.name,
                source_contents=file_contents,
                document_type=document_type,
                query_text=query_text,
                llm_model=llm_model
            )
            
            # 4. 保存生成的文档
            saved_file = DocumentGenerationService._save_generated_document(
                content=generated_content,
                source_name=file.name,
                document_type=document_type,
                output_format=output_format,
                parent_folder=file.parent if file.parent else None,
                query_text=query_text
            )
            
            return {
                'success': True,
                'query': query_text,
                'source_type': 'file',
                'source_info': file.to_dict(),
                'document_type': document_type,
                'output_format': output_format,
                'generated_content': generated_content,
                'saved_file': saved_file.to_dict() if saved_file else None,
                'generation_method': 'llm_file_analysis',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"基于文件生成文档失败: {e}")
            return {
                'success': False,
                'error': f'基于文件生成文档失败: {str(e)}',
                'query': query_text,
                'file_info': file.to_dict() if file else None
            }
    
    @staticmethod
    def _get_folder_files(folder: DocumentNode, max_depth: int = 2) -> List[DocumentNode]:
        """获取文件夹下的所有文件（递归）"""
        try:
            files = []
            
            def collect_files(node: DocumentNode, current_depth: int = 0):
                if current_depth >= max_depth:
                    return
                
                for child in node.children:
                    if child.is_deleted:
                        continue
                        
                    if child.type == 'file':
                        files.append(child)
                    elif child.type == 'folder':
                        collect_files(child, current_depth + 1)
            
            collect_files(folder)
            return files
            
        except Exception as e:
            logger.error(f"获取文件夹文件失败: {e}")
            return []
    
    @staticmethod
    def _extract_file_content(file: DocumentNode) -> Optional[str]:
        """提取文件内容 - 支持多种文件格式"""
        try:
            # 优先从DocumentContent表获取已提取的内容
            content_record = DocumentContent.query.filter_by(
                document_id=file.id
            ).first()
            
            if content_record and content_record.content_text:
                return content_record.content_text
            
            # 检查文件路径是否存在
            if not file.file_path or not os.path.exists(file.file_path):
                logger.warning(f"文件路径不存在: {file.file_path}")
                return None
            
            file_type = file.file_type.lower() if file.file_type else ''
            
            try:
                # 1. PDF文件处理
                if file_type in ['pdf']:
                    return DocumentGenerationService._extract_pdf_content(file.file_path)
                
                # 2. Word文档处理
                elif file_type in ['doc', 'docx']:
                    return DocumentGenerationService._extract_word_content(file.file_path)
                
                # 3. Excel文件处理
                elif file_type in ['xls', 'xlsx']:
                    return DocumentGenerationService._extract_excel_content(file.file_path)
                
                # 4. PowerPoint文件处理
                elif file_type in ['ppt', 'pptx']:
                    return DocumentGenerationService._extract_ppt_content(file.file_path)
                
                # 5. 图片文件OCR识别
                elif file_type in ['jpg', 'jpeg', 'png', 'bmp', 'tiff', 'gif']:
                    ocr_result = ImageRecognitionService.recognize_text(file.file_path)
                    if ocr_result and ocr_result.get('success'):
                        return ocr_result.get('text', '')
                    return None
                
                # 6. 文本文件直接读取
                elif file_type in ['txt', 'md', 'csv', 'json', 'xml', 'html', 'css', 'js', 'py', 'java', 'cpp', 'h']:
                    return DocumentGenerationService._extract_text_content(file.file_path)
                
                # 7. 其他文本类型文件尝试读取
                else:
                    # 对于未知类型，尝试当作文本文件读取
                    try:
                        return DocumentGenerationService._extract_text_content(file.file_path)
                    except:
                        logger.warning(f"无法识别文件类型: {file.name} ({file_type})")
                        return None
                        
            except Exception as extract_error:
                logger.warning(f"提取文件内容失败 {file.name}: {extract_error}")
                return None
            
        except Exception as e:
            logger.error(f"提取文件内容失败 {file.name}: {e}")
            return None
    
    @staticmethod
    def _generate_content_with_llm(source_type: str, source_name: str, 
                                  source_contents: List[Dict], document_type: str,
                                  query_text: str, llm_model: str = None) -> str:
        """使用LLM生成文档内容"""
        try:
            # 构建系统提示词
            system_prompt = f"""你是一个专业的文档整理专家。你的任务是基于提供的{source_type}内容，生成一份{DocumentGenerationService.DOCUMENT_TYPES.get(document_type, '通用')}类型的文档。

要求：
1. 仔细分析所有提供的内容，提取关键信息
2. 按照{document_type}类型的要求组织内容结构
3. 语言要专业、准确、简洁
4. 保持逻辑清晰，条理分明
5. 输出纯文本格式，不要使用markdown或其他格式标记

请直接输出生成的文档内容，不要添加任何解释或说明。"""

            # 构建用户提示词
            user_prompt = f"""请基于以下{source_type} "{source_name}" 的内容，生成一份{DocumentGenerationService.DOCUMENT_TYPES.get(document_type, '通用')}文档：

用户需求：{query_text}

{source_type}内容：
"""
            
            # 添加文件内容
            for i, file_content in enumerate(source_contents, 1):
                user_prompt += f"""
文件{i}: {file_content['file_name']} ({file_content['file_type']})
内容摘要:
{file_content['content'][:1500]}
{'...(内容过长已截断)' if len(file_content['content']) > 1500 else ''}

"""
            
            user_prompt += f"\n请基于以上内容生成{DocumentGenerationService.DOCUMENT_TYPES.get(document_type, '通用')}文档："
            
            # 调用LLM生成内容
            if not llm_model:
                from config import Config
                llm_model = f"{Config.DEFAULT_LLM_PROVIDER}:{Config.DEFAULT_LLM_MODEL}"
            
            logger.info(f"调用LLM生成文档，模型: {llm_model}")
            logger.debug(f"系统提示词长度: {len(system_prompt)} 字符")
            logger.debug(f"用户提示词长度: {len(user_prompt)} 字符")
            
            # 将系统提示词和用户提示词合并
            combined_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            response = LLMService.generate_answer(
                query=combined_prompt,
                context="",  # 上下文已在prompt中提供
                llm_model=llm_model,
                scenario="document_generation"
            )
            
            if response and response.strip():
                logger.info(f"LLM生成成功，内容长度: {len(response)} 字符")
                return response.strip()
            else:
                logger.warning("LLM返回空响应，触发降级处理")
                return DocumentGenerationService._generate_simple_summary(source_contents, document_type)
            
        except Exception as e:
            logger.error(f"LLM生成内容失败: {e}")
            logger.error(f"错误详情: {str(e)}")
            # 降级处理：生成简单的汇总
            logger.info("触发降级处理：生成简化汇总")
            return DocumentGenerationService._generate_simple_summary(source_contents, document_type)
    
    @staticmethod
    def _generate_simple_summary(source_contents: List[Dict], document_type: str) -> str:
        """生成简单汇总（LLM失败时的降级方案）"""
        try:
            logger.info(f"生成简化汇总，文档类型: {document_type}, 文件数量: {len(source_contents)}")
            
            summary_lines = [
                f"# {DocumentGenerationService.DOCUMENT_TYPES.get(document_type, '文档汇总')}",
                f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                "## 内容概述",
                f"本文档基于 {len(source_contents)} 个文件生成，包含以下内容：",
                ""
            ]
            
            # 统计文件类型
            file_types = {}
            total_chars = 0
            
            for file_content in source_contents:
                file_type = file_content.get('file_type', '未知')
                file_types[file_type] = file_types.get(file_type, 0) + 1
                total_chars += len(file_content.get('content', ''))
            
            # 添加统计信息
            summary_lines.append("### 文件统计")
            for file_type, count in file_types.items():
                summary_lines.append(f"- {file_type}文件: {count} 个")
            summary_lines.append(f"- 总内容长度: {total_chars:,} 字符")
            summary_lines.append("")
            
            # 详细文件列表
            summary_lines.append("## 文件详情")
            
            for i, file_content in enumerate(source_contents, 1):
                file_name = file_content.get('file_name', '未知文件')
                file_type = file_content.get('file_type', '未知')
                content = file_content.get('content', '')
                
                summary_lines.append(f"### {i}. {file_name}")
                summary_lines.append(f"**文件类型:** {file_type}")
                summary_lines.append(f"**内容长度:** {len(content)} 字符")
                
                # 提取关键内容片段
                if content:
                    # 取开头部分
                    content_preview = content[:200].replace('\n', ' ').strip()
                    if content_preview:
                        summary_lines.append(f"**内容预览:** {content_preview}...")
                    
                    # 如果内容较长，也显示一些中间部分
                    if len(content) > 400:
                        middle_content = content[len(content)//2:len(content)//2+150].replace('\n', ' ').strip()
                        if middle_content:
                            summary_lines.append(f"**中间片段:** ...{middle_content}...")
                else:
                    summary_lines.append("**内容预览:** (文件内容为空)")
                
                summary_lines.append("")
            
            # 添加建议性说明
            summary_lines.extend([
                "## 使用建议",
                "本文档为基础汇总版本，包含了源文件的主要信息和内容预览。",
                "您可以根据以上信息了解文档的基本结构和内容概况。",
                "",
                "---",
                f"*文档生成于 {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}*"
            ])
            
            result = '\n'.join(summary_lines)
            logger.info(f"简化汇总生成完成，长度: {len(result)} 字符")
            return result
            
        except Exception as e:
            logger.error(f"生成简单汇总失败: {e}")
            return f"""# 文档生成失败

生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 错误信息
文档生成过程中遇到问题：{str(e)}

## 建议
请检查源文件是否存在，或联系系统管理员。"""
    
    @staticmethod
    def _save_generated_document(content: str, source_name: str, document_type: str,
                               output_format: str, parent_folder: DocumentNode = None, 
                               query_text: str = '') -> Optional[DocumentNode]:
        """保存生成的文档"""
        try:
            # 生成语义化文件名
            filename = DocumentGenerationService._generate_semantic_filename(
                source_name, document_type, output_format, query_text)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # 为生成的文档创建虚拟路径（用于预览系统识别）
            import uuid
            virtual_path = f"mcp_created/{uuid.uuid4()}_{filename}"
            
            # 创建DocumentNode记录
            new_doc = DocumentNode(
                name=filename,
                type='file',
                parent_id=parent_folder.id if parent_folder else None,
                file_type=output_format,
                file_size=len(content.encode('utf-8')),
                file_path=virtual_path,  # 设置虚拟路径用于预览
                mime_type='text/plain',
                description=f"基于 {source_name} 生成的{DocumentGenerationService.DOCUMENT_TYPES.get(document_type, '文档')}",
                created_by='document_generation_service',
                doc_metadata={
                    'generated_from': source_name,
                    'generation_type': document_type,
                    'generation_time': datetime.now().isoformat(),
                    'output_format': output_format
                }
            )
            
            db.session.add(new_doc)
            db.session.flush()  # 获取ID
            
            # 创建DocumentContent记录
            doc_content = DocumentContent(
                document_id=new_doc.id,
                content_text=content,
                page_number=1,
                chunk_index=0,
                chunk_text=content[:1000]  # 保存前1000个字符作为chunk
            )
            
            db.session.add(doc_content)
            db.session.commit()
            
            logger.info(f"成功保存生成的文档: {filename} (ID: {new_doc.id})")
            return new_doc
            
        except Exception as e:
            logger.error(f"保存生成文档失败: {e}")
            db.session.rollback()
            return None
    
    @staticmethod
    def _generate_semantic_filename(source_name: str, document_type: str, 
                                   output_format: str, query_text: str = '') -> str:
        """生成语义化的文件名"""
        try:
            # 清理源文件名（去掉扩展名）
            clean_source = re.sub(r'\.[a-zA-Z0-9]+$', '', source_name)
            
            # 从查询文本中提取语义关键词
            semantic_suffix = DocumentGenerationService._extract_semantic_suffix(query_text, document_type)
            
            # 构建语义化文件名
            if semantic_suffix:
                filename = f"{clean_source}{semantic_suffix}.{output_format}"
            else:
                # 使用默认的文档类型名称
                type_name = DocumentGenerationService.DOCUMENT_TYPES.get(document_type, '文档')
                filename = f"{clean_source}{type_name}.{output_format}"
            
            # 确保文件名不超过255个字符
            if len(filename) > 255:
                max_source_len = 255 - len(semantic_suffix or type_name) - len(output_format) - 2
                clean_source = clean_source[:max_source_len]
                filename = f"{clean_source}{semantic_suffix or type_name}.{output_format}"
            
            return filename
            
        except Exception as e:
            logger.error(f"生成语义化文件名失败: {e}")
            # 返回简单的默认名称
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            return f"{source_name}_{document_type}_{timestamp}.{output_format}"
    
    @staticmethod
    def _extract_semantic_suffix(query_text: str, document_type: str) -> str:
        """从查询文本中提取语义化后缀"""
        try:
            # 定义语义关键词映射
            semantic_patterns = {
                # 价格相关
                r'价格(?:预测|分析|评估|估算)': '价格预测报告',
                r'(?:房价|价值)(?:预测|分析|评估)': '价格预测报告',
                r'市场(?:价格|行情)(?:分析|预测)': '市场行情分析',
                
                # 分析相关
                r'(?:数据|内容|情况)分析': '数据分析报告',
                r'(?:市场|行业|竞争)分析': '市场分析报告',
                r'(?:财务|经营|业务)分析': '财务分析报告',
                r'(?:风险|安全)(?:分析|评估)': '风险评估报告',
                
                # 总结相关
                r'(?:工作|项目|业务)总结': '工作总结',
                r'(?:会议|活动|事件)总结': '会议总结',
                r'(?:学习|培训)总结': '学习总结',
                
                # 报告相关
                r'(?:调研|调查)报告': '调研报告',
                r'(?:测试|评测)报告': '测试报告',
                r'(?:进展|进度)报告': '进度报告',
                r'(?:年度|月度|季度)报告': '定期报告',
                
                # 计划相关
                r'(?:工作|项目|营销)计划': '工作计划',
                r'(?:发展|战略)规划': '发展规划',
                
                # 方案相关
                r'(?:解决|实施|优化)方案': '解决方案',
                r'(?:改进|提升)方案': '改进方案'
            }
            
            query_lower = query_text.lower()
            
            # 按优先级检查语义模式
            for pattern, suffix in semantic_patterns.items():
                if re.search(pattern, query_text):
                    return suffix
            
            # 如果没有找到特定模式，尝试提取动词+名词组合
            action_patterns = {
                r'(预测|分析|评估|估算)(.{1,8}?)(?:报告|文档|资料)': r'\1\2报告',
                r'(总结|汇总|梳理)(.{1,8}?)(?:文档|资料|内容)': r'\1\2',
                r'(制作|生成|编写)(.{1,15}?)(?:报告|文档)': r'\2报告'
            }
            
            for pattern, replacement in action_patterns.items():
                match = re.search(pattern, query_text)
                if match:
                    return re.sub(pattern, replacement, match.group(0))
            
            # 默认根据文档类型返回
            type_mappings = {
                'report': '分析报告',
                'summary': '总结报告', 
                'analysis': '分析文档',
                'documentation': '说明文档',
                'other': '文档'
            }
            
            return type_mappings.get(document_type, '文档')
            
        except Exception as e:
            logger.error(f"提取语义后缀失败: {e}")
            return DocumentGenerationService.DOCUMENT_TYPES.get(document_type, '文档')
    
    @staticmethod
    def _extract_text_content(file_path: str) -> Optional[str]:
        """提取文本文件内容"""
        try:
            # 尝试UTF-8编码读取
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            for encoding in ['gbk', 'gb2312', 'latin1', 'iso-8859-1']:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read()
                except:
                    continue
            logger.warning(f"无法识别文本文件编码: {file_path}")
            return None
        except Exception as e:
            logger.error(f"读取文本文件失败 {file_path}: {e}")
            return None
    
    @staticmethod
    def _extract_pdf_content(file_path: str) -> Optional[str]:
        """提取PDF文件内容"""
        try:
            # 优先使用项目中的PDF服务
            from app.services.pdf_service import PDFService
            result = PDFService.extract_text(file_path)
            if result and result.get('success'):
                return result.get('text', '')
            
            # 如果PDF服务失败，尝试使用PyPDF2
            try:
                import PyPDF2
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                    return text.strip()
            except ImportError:
                logger.warning("PyPDF2未安装，请安装：pip install PyPDF2")
            except Exception as pypdf_error:
                logger.warning(f"PyPDF2提取失败: {pypdf_error}")
            
            # 尝试使用pdfplumber
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    text = ""
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                    return text.strip()
            except ImportError:
                logger.warning("pdfplumber未安装，请安装：pip install pdfplumber")
            except Exception as plumber_error:
                logger.warning(f"pdfplumber提取失败: {plumber_error}")
            
            return None
            
        except Exception as e:
            logger.error(f"提取PDF内容失败 {file_path}: {e}")
            return None
    
    @staticmethod
    def _extract_word_content(file_path: str) -> Optional[str]:
        """提取Word文档内容"""
        try:
            # 优先使用项目中的Word服务
            from app.services.word_service import WordService
            result = WordService.extract_text(file_path)
            if result and result.get('success'):
                return result.get('text', '')
            
            # 如果Word服务失败，尝试使用python-docx
            try:
                import docx
                doc = docx.Document(file_path)
                text = ""
                for paragraph in doc.paragraphs:
                    text += paragraph.text + "\n"
                
                # 提取表格内容
                for table in doc.tables:
                    for row in table.rows:
                        row_text = []
                        for cell in row.cells:
                            row_text.append(cell.text.strip())
                        text += "\t".join(row_text) + "\n"
                
                return text.strip()
            except ImportError:
                logger.warning("python-docx未安装，请安装：pip install python-docx")
            except Exception as docx_error:
                logger.warning(f"python-docx提取失败: {docx_error}")
            
            return None
            
        except Exception as e:
            logger.error(f"提取Word内容失败 {file_path}: {e}")
            return None
    
    @staticmethod
    def _extract_excel_content(file_path: str) -> Optional[str]:
        """提取Excel文件内容"""
        try:
            # 优先使用项目中的Excel服务
            from app.services.excel_service import ExcelService
            result = ExcelService.extract_text(file_path)
            if result and result.get('success'):
                return result.get('text', '')
            
            # 如果Excel服务失败，尝试使用openpyxl和pandas
            try:
                import pandas as pd
                
                # 读取所有工作表
                excel_file = pd.ExcelFile(file_path)
                text = ""
                
                for sheet_name in excel_file.sheet_names:
                    text += f"=== 工作表: {sheet_name} ===\n"
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    
                    # 转换为文本格式
                    text += df.to_string(index=False, na_rep='') + "\n\n"
                
                return text.strip()
            except ImportError:
                logger.warning("pandas或openpyxl未安装，请安装：pip install pandas openpyxl")
            except Exception as excel_error:
                logger.warning(f"pandas提取Excel失败: {excel_error}")
            
            # 尝试使用xlrd（对于老版本的.xls文件）
            try:
                import xlrd
                workbook = xlrd.open_workbook(file_path)
                text = ""
                
                for sheet_name in workbook.sheet_names():
                    sheet = workbook.sheet_by_name(sheet_name)
                    text += f"=== 工作表: {sheet_name} ===\n"
                    
                    for row_idx in range(sheet.nrows):
                        row_values = []
                        for col_idx in range(sheet.ncols):
                            cell_value = sheet.cell_value(row_idx, col_idx)
                            row_values.append(str(cell_value))
                        text += "\t".join(row_values) + "\n"
                    text += "\n"
                
                return text.strip()
            except ImportError:
                logger.warning("xlrd未安装，请安装：pip install xlrd")
            except Exception as xlrd_error:
                logger.warning(f"xlrd提取失败: {xlrd_error}")
            
            return None
            
        except Exception as e:
            logger.error(f"提取Excel内容失败 {file_path}: {e}")
            return None
    
    @staticmethod
    def _extract_ppt_content(file_path: str) -> Optional[str]:
        """提取PowerPoint文件内容"""
        try:
            # 尝试使用python-pptx
            try:
                import pptx
                presentation = pptx.Presentation(file_path)
                text = ""
                
                for slide_num, slide in enumerate(presentation.slides, 1):
                    text += f"=== 幻灯片 {slide_num} ===\n"
                    
                    # 提取所有形状中的文本
                    for shape in slide.shapes:
                        if hasattr(shape, "text"):
                            if shape.text.strip():
                                text += shape.text + "\n"
                    
                    text += "\n"
                
                return text.strip()
            except ImportError:
                logger.warning("python-pptx未安装，请安装：pip install python-pptx")
            except Exception as pptx_error:
                logger.warning(f"python-pptx提取失败: {pptx_error}")
            
            return None
            
        except Exception as e:
            logger.error(f"提取PowerPoint内容失败 {file_path}: {e}")
            return None 