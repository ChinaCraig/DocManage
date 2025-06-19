"""
文件夹分析服务
用于分析文件夹内容的完整性，检查缺失文件等
"""

import logging
import re
from typing import Dict, List, Any, Optional
from app.models.document_models import DocumentNode, Tag
from app.services.llm import LLMService, LLMClientFactory

logger = logging.getLogger(__name__)

class FolderAnalysisService:
    """文件夹分析服务"""
    
    @staticmethod
    def extract_folder_name(query: str) -> Optional[str]:
        """从用户查询中提取文件夹名称"""
        try:
            # 定义匹配文件夹名称的正则表达式模式
            patterns = [
                # 匹配"分析XX文件夹"
                r'分析\s*([a-zA-Z0-9\u4e00-\u9fff\-_\s]+?)\s*(?:文件夹|目录)',
                # 匹配"检查XX文件夹"
                r'检查\s*([a-zA-Z0-9\u4e00-\u9fff\-_\s]+?)\s*(?:文件夹|目录)',
                # 匹配"确认XX文件夹"
                r'确认\s*([a-zA-Z0-9\u4e00-\u9fff\-_\s]+?)\s*(?:文件夹|目录)',
                # 匹配"分析XX缺少"、"分析XX还缺少"等模式
                r'分析\s*([a-zA-Z0-9\u4e00-\u9fff\-_\s]+?)\s*(?:缺少|缺失|还缺少|还缺失|下缺少|下缺失)',
                # 匹配"检查XX缺少"等模式
                r'检查\s*([a-zA-Z0-9\u4e00-\u9fff\-_\s]+?)\s*(?:缺少|缺失|还缺少|还缺失|下缺少|下缺失)',
                # 匹配"XX文件夹"（直接提及）
                r'([a-zA-Z0-9\u4e00-\u9fff\-_\s]+?)\s*(?:文件夹|目录)',
                # 匹配引号中的名称
                r'["\'""]([a-zA-Z0-9\u4e00-\u9fff\-_\s]+?)["\'""]',
                # 匹配"XX下"或"XX中"
                r'([a-zA-Z0-9\u4e00-\u9fff\-_\s]+?)\s*(?:下|中)',
                # 匹配包含数字开头的文件夹名（如"01所有权证"）
                r'(?:分析|检查|确认)\s*([0-9]+[a-zA-Z0-9\u4e00-\u9fff\-_\s]*?)(?:\s*(?:缺少|缺失|还缺少|内容|下|中|的))',
                # 更宽泛的匹配：分析/检查 + 任何字符 + 特定结尾词
                r'(?:分析|检查|确认|对比)\s*([a-zA-Z0-9\u4e00-\u9fff\-_]+(?:\s+[a-zA-Z0-9\u4e00-\u9fff\-_]+)*?)\s*(?:缺少|缺失|还缺少|哪些|内容|完整|是否)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, query)
                if match:
                    folder_name = match.group(1).strip()
                    # 过滤掉太短或包含无关词汇的匹配
                    if (len(folder_name) > 0 and 
                        folder_name not in ['的', '了', '在', '是', '有', '下', '中', '哪些', '内容'] and
                        len(folder_name) <= 50):  # 防止匹配过长的文本
                        logger.info(f"提取到文件夹名称: '{folder_name}' (来源: {query}, 模式: {pattern})")
                        return folder_name
            
            logger.warning(f"无法从查询中提取文件夹名称: {query}")
            return None
            
        except Exception as e:
            logger.error(f"提取文件夹名称失败: {e}")
            return None
    
    @staticmethod
    def find_folder_by_name(folder_name: str) -> Optional[DocumentNode]:
        """根据名称查找文件夹"""
        try:
            # 精确匹配
            folder = DocumentNode.query.filter_by(
                name=folder_name,
                type='folder',
                is_deleted=False
            ).first()
            
            if folder:
                logger.info(f"找到文件夹: {folder_name} (ID: {folder.id})")
                return folder
            
            # 模糊匹配
            folders = DocumentNode.query.filter(
                DocumentNode.name.ilike(f'%{folder_name}%'),
                DocumentNode.type == 'folder',
                DocumentNode.is_deleted == False
            ).all()
            
            if folders:
                # 如果有多个匹配，选择名称最相似的
                best_match = min(folders, key=lambda f: abs(len(f.name) - len(folder_name)))
                logger.info(f"模糊匹配到文件夹: {best_match.name} (ID: {best_match.id})")
                return best_match
            
            logger.warning(f"未找到名称为 '{folder_name}' 的文件夹")
            return None
            
        except Exception as e:
            logger.error(f"查找文件夹失败: {e}")
            return None
    
    @staticmethod
    def get_folder_contents(folder: DocumentNode) -> List[Dict]:
        """获取文件夹内的所有文件"""
        try:
            files = DocumentNode.query.filter_by(
                parent_id=folder.id,
                type='file',
                is_deleted=False
            ).all()
            
            content_list = []
            for file in files:
                content_list.append({
                    'id': file.id,
                    'name': file.name,
                    'file_type': file.file_type,
                    'file_size': file.file_size,
                    'description': file.description,
                    'tags': [tag.name for tag in file.tags] if file.tags else [],
                    'created_at': file.created_at
                })
            
            logger.info(f"文件夹 '{folder.name}' 包含 {len(content_list)} 个文件")
            return content_list
            
        except Exception as e:
            logger.error(f"获取文件夹内容失败: {e}")
            return []
    
    @staticmethod
    def analyze_folder_expectations(folder: DocumentNode, llm_model: str = None) -> Dict[str, Any]:
        """使用LLM分析文件夹应该包含的内容"""
        try:
            if not llm_model:
                from app.config import Config
                llm_model = f"{Config.DEFAULT_LLM_PROVIDER}:{Config.DEFAULT_LLM_MODEL}"
            
            client = LLMClientFactory.create_client(llm_model)
            if not client:
                logger.warning(f"无法创建LLM客户端: {llm_model}")
                return {"expected_files": [], "analysis": "LLM客户端不可用"}
            
            # 构建分析提示词
            folder_info = {
                'name': folder.name,
                'description': folder.description or '',
                'tags': [tag.name for tag in folder.tags] if folder.tags else [],
                'current_files': [child.name for child in folder.children if child.type == 'file' and not child.is_deleted]
            }
            
            system_prompt = """你是一个专业的文档管理和组织专家。请分析给定的文件夹信息，预测该文件夹应该包含哪些类型和名称的文件。

请严格按照以下JSON格式返回分析结果（不要添加markdown格式或其他文本）：
{
  "expected_files": [
    {
      "name": "期望的文件名",
      "type": "文件类型",
      "description": "文件用途说明",
      "priority": "high|medium|low",
      "reason": "为什么需要这个文件"
    }
  ],
  "folder_purpose": "文件夹的主要用途",
  "organization_suggestions": [
    "组织建议1",
    "组织建议2"
  ],
  "analysis": "详细的分析说明"
}

分析原则：
1. 根据文件夹名称和标签推断用途
2. 考虑常见的文档组织模式
3. 基于已有文件推断缺失内容
4. 优先级high表示必需文件，medium表示建议文件，low表示可选文件
5. 文件名应该具体且实用"""

            user_prompt = f"""请分析以下文件夹的信息：

文件夹名称：{folder_info['name']}
文件夹描述：{folder_info['description']}
文件夹标签：{', '.join(folder_info['tags']) if folder_info['tags'] else '无'}
当前已有文件：{', '.join(folder_info['current_files']) if folder_info['current_files'] else '无'}

请分析该文件夹应该包含哪些文件，并提供组织建议："""

            # 调用LLM进行分析
            response = client._call_llm_with_prompt(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                parameters={
                    "max_tokens": 800,
                    "temperature": 0.3
                }
            )
            
            # 解析JSON响应
            try:
                import json
                # 清理响应文本
                cleaned_response = response.strip()
                
                # 处理可能的markdown代码块
                if '```json' in cleaned_response:
                    json_start = cleaned_response.find('```json') + 7
                    json_end = cleaned_response.find('```', json_start)
                    if json_end != -1:
                        cleaned_response = cleaned_response[json_start:json_end].strip()
                elif '```' in cleaned_response:
                    json_start = cleaned_response.find('```') + 3
                    json_end = cleaned_response.find('```', json_start)
                    if json_end != -1:
                        cleaned_response = cleaned_response[json_start:json_end].strip()
                
                # 找到JSON对象
                if not cleaned_response.startswith('{'):
                    brace_start = cleaned_response.find('{')
                    if brace_start != -1:
                        cleaned_response = cleaned_response[brace_start:]
                
                if not cleaned_response.endswith('}'):
                    brace_end = cleaned_response.rfind('}')
                    if brace_end != -1:
                        cleaned_response = cleaned_response[:brace_end + 1]
                
                analysis_result = json.loads(cleaned_response)
                logger.info(f"文件夹 '{folder.name}' LLM分析完成")
                return analysis_result
                
            except json.JSONDecodeError as e:
                logger.warning(f"LLM分析结果JSON解析失败: {e}, 原始响应: {response[:200]}...")
                return {
                    "expected_files": [],
                    "analysis": f"LLM分析结果解析失败: {response[:200]}..."
                }
                
        except Exception as e:
            logger.error(f"LLM文件夹分析失败: {e}")
            return {
                "expected_files": [],
                "analysis": f"LLM分析失败: {str(e)}"
            }
    
    @staticmethod
    def compare_folder_contents(current_files: List[Dict], expected_files: List[Dict]) -> Dict[str, Any]:
        """对比当前文件与期望文件，找出缺失和多余的内容"""
        try:
            current_names = {file['name'].lower() for file in current_files}
            expected_names = {file['name'].lower() for file in expected_files}
            
            # 找出缺失的文件
            missing_files = []
            for expected in expected_files:
                expected_name = expected['name'].lower()
                if expected_name not in current_names:
                    # 检查是否有类似的文件（模糊匹配）
                    similar_found = False
                    for current_name in current_names:
                        if (expected_name in current_name or current_name in expected_name or
                            any(word in current_name for word in expected_name.split() if len(word) > 2)):
                            similar_found = True
                            break
                    
                    if not similar_found:
                        missing_files.append(expected)
            
            # 找出额外的文件（当前有但期望中没有的）
            extra_files = []
            for current in current_files:
                current_name = current['name'].lower()
                if current_name not in expected_names:
                    # 检查是否与期望文件类似
                    similar_found = False
                    for expected_name in expected_names:
                        if (current_name in expected_name or expected_name in current_name or
                            any(word in expected_name for word in current_name.split() if len(word) > 2)):
                            similar_found = True
                            break
                    
                    if not similar_found:
                        extra_files.append(current)
            
            # 找出匹配的文件
            matched_files = []
            for current in current_files:
                current_name = current['name'].lower()
                for expected in expected_files:
                    expected_name = expected['name'].lower()
                    if (current_name == expected_name or 
                        current_name in expected_name or expected_name in current_name or
                        any(word in expected_name for word in current_name.split() if len(word) > 2)):
                        matched_files.append({
                            'current': current,
                            'expected': expected
                        })
                        break
            
            comparison_result = {
                'total_current': len(current_files),
                'total_expected': len(expected_files),
                'missing_files': missing_files,
                'extra_files': extra_files,
                'matched_files': matched_files,
                'completion_rate': len(matched_files) / len(expected_files) * 100 if expected_files else 100,
                'missing_count': len(missing_files),
                'extra_count': len(extra_files),
                'matched_count': len(matched_files)
            }
            
            logger.info(f"文件夹内容对比完成 - 匹配: {len(matched_files)}, 缺失: {len(missing_files)}, 额外: {len(extra_files)}")
            return comparison_result
            
        except Exception as e:
            logger.error(f"对比文件夹内容失败: {e}")
            return {
                'total_current': len(current_files),
                'total_expected': 0,
                'missing_files': [],
                'extra_files': [],
                'matched_files': [],
                'completion_rate': 0,
                'error': str(e)
            }
    
    @staticmethod
    def generate_analysis_summary(folder: DocumentNode, expectations: Dict, comparison: Dict, llm_model: str = None) -> str:
        """生成AI分析总结"""
        try:
            if not llm_model:
                from app.config import Config
                llm_model = f"{Config.DEFAULT_LLM_PROVIDER}:{Config.DEFAULT_LLM_MODEL}"
            
            client = LLMClientFactory.create_client(llm_model)
            if not client:
                return f"文件夹 '{folder.name}' 分析完成，但无法生成AI总结（LLM客户端不可用）"
            
            system_prompt = """你是一个专业的文档管理顾问。请基于文件夹分析结果，生成一份简洁明了的分析报告。

报告应该包含：
1. 文件夹整体评估
2. 主要发现（缺失的重要文件）
3. 优化建议
4. 总结

语言要专业但易懂，重点突出关键问题和建议。"""

            user_prompt = f"""请基于以下分析数据，为文件夹 '{folder.name}' 生成分析报告：

文件夹信息：
- 名称：{folder.name}
- 描述：{folder.description or '无'}
- 标签：{', '.join([tag.name for tag in folder.tags]) if folder.tags else '无'}

分析结果：
- 当前文件数：{comparison.get('total_current', 0)}
- 期望文件数：{comparison.get('total_expected', 0)}
- 完整度：{comparison.get('completion_rate', 0):.1f}%
- 缺失文件数：{comparison.get('missing_count', 0)}
- 额外文件数：{comparison.get('extra_count', 0)}

缺失的重要文件：
{chr(10).join([f"- {file['name']} ({file.get('priority', 'unknown')}优先级): {file.get('reason', '无原因')}" for file in comparison.get('missing_files', [])[:5]])}

文件夹用途：{expectations.get('folder_purpose', '未知')}

请生成一份200-300字的分析报告："""

            response = client._call_llm_with_prompt(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                parameters={
                    "max_tokens": 400,
                    "temperature": 0.5
                }
            )
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"生成AI分析总结失败: {e}")
            return f"文件夹 '{folder.name}' 分析完成，但生成AI总结时出现错误：{str(e)}"
    
    @staticmethod
    def analyze_folder_completeness(query: str, llm_model: str = None, intent_analysis: Dict = None) -> Dict[str, Any]:
        """完整的文件夹分析流程"""
        try:
            # 1. 优先使用LLM分析结果中的文件夹名称
            folder_name = None
            if intent_analysis and 'parameters' in intent_analysis:
                folder_name = intent_analysis['parameters'].get('folder_name')
                if folder_name:
                    logger.info(f"使用LLM分析结果中的文件夹名称: {folder_name}")
            
            # 2. 如果LLM没有提供，则使用正则表达式提取
            if not folder_name:
                folder_name = FolderAnalysisService.extract_folder_name(query)
                if folder_name:
                    logger.info(f"使用正则表达式提取的文件夹名称: {folder_name}")
            
            if not folder_name:
                return {
                    'success': False,
                    'error': '无法从查询中提取文件夹名称（LLM和正则表达式都未能识别）',
                    'query': query
                }
            
            # 2. 查找文件夹
            folder = FolderAnalysisService.find_folder_by_name(folder_name)
            if not folder:
                return {
                    'success': False,
                    'error': f'未找到名称为 "{folder_name}" 的文件夹',
                    'extracted_name': folder_name,
                    'query': query
                }
            
            # 3. 获取当前文件夹内容
            current_files = FolderAnalysisService.get_folder_contents(folder)
            
            # 4. LLM分析期望内容
            expectations = FolderAnalysisService.analyze_folder_expectations(folder, llm_model)
            
            # 5. 对比分析
            comparison = FolderAnalysisService.compare_folder_contents(
                current_files, 
                expectations.get('expected_files', [])
            )
            
            # 6. 生成AI总结
            ai_summary = FolderAnalysisService.generate_analysis_summary(
                folder, expectations, comparison, llm_model
            )
            
            # 7. 组装完整结果
            result = {
                'success': True,
                'query': query,
                'folder': {
                    'id': folder.id,
                    'name': folder.name,
                    'description': folder.description,
                    'tags': [tag.to_dict() for tag in folder.tags] if folder.tags else [],
                    'path': folder.file_path
                },
                'current_files': current_files,
                'expectations': expectations,
                'comparison': comparison,
                'ai_summary': ai_summary,
                'analysis_type': 'folder_completeness'
            }
            
            logger.info(f"文件夹 '{folder.name}' 完整性分析完成")
            return result
            
        except Exception as e:
            logger.error(f"文件夹分析失败: {e}")
            return {
                'success': False,
                'error': f'文件夹分析过程中出现错误: {str(e)}',
                'query': query
            } 