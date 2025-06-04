"""
Excel文档向量化器
专门处理Excel文件(.xls, .xlsx)的内容提取和向量化，支持智能数据分析
"""

import logging
import os
import re
from typing import List, Dict, Any, Optional
from .base_vectorizer import BaseVectorizer

logger = logging.getLogger(__name__)

class ExcelVectorizer(BaseVectorizer):
    """Excel文档向量化器，支持智能数据分析"""
    
    def __init__(self):
        """初始化Excel向量化器"""
        super().__init__()
        self.file_type = "excel"
    
    def get_supported_extensions(self) -> List[str]:
        """获取支持的文件扩展名"""
        return ['.xls', '.xlsx', '.xlsm', '.xlsb']
    
    def extract_text(self, file_path: str, analyze_data: bool = True) -> Dict[str, Any]:
        """
        从Excel文件提取文本内容和数据分析
        
        Args:
            file_path: Excel文件路径
            analyze_data: 是否进行数据分析
            
        Returns:
            包含提取结果的字典
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return {
                    'success': False,
                    'error': f'Excel文件不存在: {file_path}'
                }
            
            # 检查文件扩展名
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext not in self.get_supported_extensions():
                return {
                    'success': False,
                    'error': f'不支持的文件格式: {file_ext}'
                }
            
            try:
                import pandas as pd
                import numpy as np
                
                # 读取Excel文件的所有工作表
                excel_file = pd.ExcelFile(file_path)
                
                # 获取基本元数据
                metadata = {
                    'file_size': os.path.getsize(file_path),
                    'file_type': file_ext.replace('.', ''),
                    'sheet_names': excel_file.sheet_names,
                    'total_sheets': len(excel_file.sheet_names),
                    'extraction_method': 'pandas'
                }
                
                # 构建内容
                content_parts = []
                filename = os.path.basename(file_path)
                
                content_parts.append(f"Excel文档: {filename}")
                content_parts.append(f"文件大小: {self._format_file_size(metadata['file_size'])}")
                content_parts.append(f"工作表数量: {metadata['total_sheets']}")
                content_parts.append(f"工作表名称: {', '.join(excel_file.sheet_names)}")
                
                # 提取所有工作表的内容
                text_parts = []
                sheet_contents = {}
                total_rows = 0
                total_columns = 0
                all_data_analysis = {}
                
                for sheet_name in excel_file.sheet_names:
                    try:
                        # 读取工作表
                        df = pd.read_excel(file_path, sheet_name=sheet_name)
                        
                        if df.empty:
                            continue
                        
                        # 基本信息
                        rows, cols = df.shape
                        total_rows += rows
                        total_columns = max(total_columns, cols)
                        
                        # 提取工作表信息
                        sheet_info = {
                            'rows': rows,
                            'columns': cols,
                            'column_names': list(df.columns),
                            'non_empty_cells': df.count().sum(),
                            'empty_cells': df.isna().sum().sum()
                        }
                        
                        # 数据分析
                        sheet_analysis = {}
                        if analyze_data:
                            sheet_analysis = self._analyze_sheet_data(df, sheet_name)
                            all_data_analysis[sheet_name] = sheet_analysis
                        
                        # 转换为文本格式
                        sheet_text = self._dataframe_to_text(df, sheet_name, sheet_analysis)
                        
                        if sheet_text:
                            text_parts.append(sheet_text)
                            sheet_contents[sheet_name] = {
                                'text': sheet_text,
                                'info': sheet_info,
                                'analysis': sheet_analysis
                            }
                        
                    except Exception as e:
                        logger.warning(f"Failed to process sheet '{sheet_name}': {e}")
                        continue
                
                # 添加文档级别的分析
                if analyze_data and sheet_contents:
                    doc_analysis = self._analyze_document_data(all_data_analysis, total_rows, total_columns)
                    content_parts.append(f"\n=== 数据分析摘要 ===")
                    content_parts.append(doc_analysis)
                
                # 添加工作表内容
                if text_parts:
                    content_parts.append(f"\n=== 工作表内容 ===")
                    content_parts.extend(text_parts)
                
                # 合并所有文本
                comprehensive_text = '\n'.join(content_parts)
                
                # 关键词提取
                keywords = self._extract_keywords(comprehensive_text, filename, metadata, all_data_analysis)
                if keywords:
                    content_parts.append(f"\n=== 检索关键词 ===")
                    content_parts.append(" ".join(keywords))
                    comprehensive_text = '\n'.join(content_parts)
                
                if not comprehensive_text.strip():
                    return {
                        'success': False,
                        'error': 'Excel文件中没有可提取的文本内容'
                    }
                
                # 更新元数据
                metadata.update({
                    'sheet_contents': sheet_contents,
                    'total_rows': total_rows,
                    'total_columns': total_columns,
                    'has_data_analysis': analyze_data,
                    'content_length': len(comprehensive_text),
                    'data_summary': all_data_analysis
                })
                
                # 进行文本分块
                chunks = self.chunk_text(comprehensive_text)
                
                return {
                    'success': True,
                    'text': comprehensive_text,
                    'metadata': metadata,
                    'chunks': chunks,
                    'file_type': 'excel'
                }
                
            except ImportError:
                return {
                    'success': False,
                    'error': 'pandas库未安装，请运行: pip install pandas openpyxl xlrd'
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Excel文件处理失败: {str(e)}'
                }
                
        except Exception as e:
            logger.error(f"Excel text extraction failed: {e}")
            return {
                'success': False,
                'error': f'Excel文本提取失败: {str(e)}'
            }
    
    def _analyze_sheet_data(self, df, sheet_name: str) -> Dict[str, Any]:
        """分析工作表数据"""
        try:
            import pandas as pd
            import numpy as np
            
            analysis = {
                'data_types': {},
                'statistics': {},
                'patterns': {},
                'quality': {}
            }
            
            # 数据类型分析
            for col in df.columns:
                col_data = df[col].dropna()
                if len(col_data) == 0:
                    continue
                
                # 尝试推断数据类型
                data_type = 'text'
                sample_values = []
                
                # 数值型
                if pd.api.types.is_numeric_dtype(col_data):
                    data_type = 'numeric'
                    analysis['statistics'][col] = {
                        'mean': float(col_data.mean()) if not col_data.empty else 0,
                        'std': float(col_data.std()) if not col_data.empty else 0,
                        'min': float(col_data.min()) if not col_data.empty else 0,
                        'max': float(col_data.max()) if not col_data.empty else 0,
                        'count': int(col_data.count())
                    }
                
                # 日期时间型
                elif pd.api.types.is_datetime64_any_dtype(col_data):
                    data_type = 'datetime'
                    analysis['statistics'][col] = {
                        'earliest': str(col_data.min()) if not col_data.empty else '',
                        'latest': str(col_data.max()) if not col_data.empty else '',
                        'count': int(col_data.count())
                    }
                
                # 文本型
                else:
                    # 尝试转换为数值
                    try:
                        numeric_data = pd.to_numeric(col_data, errors='coerce')
                        if not numeric_data.isna().all():
                            data_type = 'mixed_numeric'
                    except:
                        pass
                    
                    # 检查特殊模式
                    sample_values = list(col_data.astype(str)[:10])
                    
                    # 检查是否包含特殊数据
                    text_values = col_data.astype(str)
                    
                    # 电话号码模式
                    phone_pattern = text_values.str.match(r'1[3-9]\d{9}')
                    if phone_pattern.any():
                        analysis['patterns'][col] = 'phone_numbers'
                    
                    # 身份证号模式
                    id_pattern = text_values.str.match(r'\d{17}[\dX]')
                    if id_pattern.any():
                        analysis['patterns'][col] = 'id_numbers'
                    
                    # 车牌号模式
                    license_pattern = text_values.str.match(r'[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领][A-Z][A-Z0-9]{5}')
                    if license_pattern.any():
                        analysis['patterns'][col] = 'license_plates'
                    
                    analysis['statistics'][col] = {
                        'unique_count': int(col_data.nunique()),
                        'most_common': str(col_data.mode().iloc[0]) if not col_data.mode().empty else '',
                        'count': int(col_data.count()),
                        'sample_values': sample_values
                    }
                
                analysis['data_types'][col] = data_type
            
            # 数据质量分析
            analysis['quality'] = {
                'total_cells': int(df.size),
                'non_empty_cells': int(df.count().sum()),
                'empty_cells': int(df.isna().sum().sum()),
                'completeness': float(df.count().sum() / df.size) if df.size > 0 else 0
            }
            
            return analysis
            
        except Exception as e:
            logger.warning(f"Data analysis failed for sheet {sheet_name}: {e}")
            return {}
    
    def _analyze_document_data(self, all_analysis: Dict, total_rows: int, total_columns: int) -> str:
        """生成文档级别的数据分析摘要"""
        analysis_parts = []
        
        analysis_parts.append(f"总计 {len(all_analysis)} 个工作表，{total_rows} 行数据")
        
        # 数据类型统计
        all_data_types = {}
        all_patterns = {}
        total_cells = 0
        total_empty = 0
        
        for sheet_name, analysis in all_analysis.items():
            if 'data_types' in analysis:
                for col, dtype in analysis['data_types'].items():
                    all_data_types[dtype] = all_data_types.get(dtype, 0) + 1
            
            if 'patterns' in analysis:
                for col, pattern in analysis['patterns'].items():
                    all_patterns[pattern] = all_patterns.get(pattern, 0) + 1
            
            if 'quality' in analysis:
                total_cells += analysis['quality'].get('total_cells', 0)
                total_empty += analysis['quality'].get('empty_cells', 0)
        
        if all_data_types:
            type_summary = [f"{dtype}: {count}列" for dtype, count in all_data_types.items()]
            analysis_parts.append(f"数据类型分布: {', '.join(type_summary)}")
        
        if all_patterns:
            pattern_summary = [f"{pattern}: {count}列" for pattern, count in all_patterns.items()]
            analysis_parts.append(f"特殊数据模式: {', '.join(pattern_summary)}")
        
        if total_cells > 0:
            completeness = (total_cells - total_empty) / total_cells
            analysis_parts.append(f"数据完整性: {completeness:.1%} ({total_cells - total_empty}/{total_cells} 个非空单元格)")
        
        return '\n'.join(analysis_parts)
    
    def _dataframe_to_text(self, df, sheet_name: str, analysis: Dict = None) -> str:
        """将DataFrame转换为文本格式"""
        text_parts = []
        
        text_parts.append(f"=== 工作表: {sheet_name} ===")
        
        # 基本信息
        rows, cols = df.shape
        text_parts.append(f"尺寸: {rows}行 x {cols}列")
        
        # 数据分析摘要
        if analysis and 'quality' in analysis:
            quality = analysis['quality']
            completeness = quality.get('completeness', 0)
            text_parts.append(f"数据完整性: {completeness:.1%}")
        
        # 列信息
        if not df.columns.empty:
            headers = [str(col) for col in df.columns if pd.notna(col)]
            if headers:
                text_parts.append(f"列名: {' | '.join(headers)}")
        
        # 数据类型和模式信息
        if analysis and 'data_types' in analysis:
            type_info = []
            for col, dtype in analysis['data_types'].items():
                pattern_info = ""
                if 'patterns' in analysis and col in analysis['patterns']:
                    pattern_info = f"({analysis['patterns'][col]})"
                type_info.append(f"{col}: {dtype}{pattern_info}")
            
            if type_info:
                text_parts.append(f"数据类型: {' | '.join(type_info[:5])}")  # 限制显示数量
        
        # 统计信息
        if analysis and 'statistics' in analysis:
            stats_info = []
            for col, stats in list(analysis['statistics'].items())[:3]:  # 只显示前3列的统计
                if 'mean' in stats:
                    stats_info.append(f"{col}: 均值{stats['mean']:.2f}")
                elif 'unique_count' in stats:
                    stats_info.append(f"{col}: {stats['unique_count']}个不同值")
            
            if stats_info:
                text_parts.append(f"统计信息: {' | '.join(stats_info)}")
        
        # 数据内容（采样）
        if not df.empty:
            text_parts.append(f"\n数据内容（前{min(10, len(df))}行）:")
            
            # 提取前几行作为示例
            for index, row in df.head(10).iterrows():
                row_text = []
                
                for col_name, value in row.items():
                    if pd.notna(value) and str(value).strip():
                        # 清理单元格内容
                        cell_value = str(value).strip()
                        if cell_value and cell_value not in ['nan', 'NaN', 'None']:
                            # 限制单元格内容长度
                            if len(cell_value) > 50:
                                cell_value = cell_value[:47] + "..."
                            row_text.append(f"{col_name}: {cell_value}")
                
                if row_text:
                    text_parts.append(' | '.join(row_text))
        
        return '\n'.join(text_parts)
    
    def _extract_keywords(self, text: str, filename: str, metadata: Dict, data_analysis: Dict) -> List[str]:
        """提取关键词用于检索优化"""
        keywords = []
        
        # 文件名关键词
        base_name = os.path.splitext(filename)[0]
        filename_words = base_name.replace('_', ' ').replace('-', ' ').split()
        keywords.extend([word for word in filename_words if len(word) > 1])
        
        # 工作表名关键词
        sheet_names = metadata.get('sheet_names', [])
        for sheet_name in sheet_names:
            sheet_words = sheet_name.replace('_', ' ').replace('-', ' ').split()
            keywords.extend([word for word in sheet_words if len(word) > 1])
        
        # 列名关键词
        for sheet_name, analysis in data_analysis.items():
            if 'data_types' in analysis:
                for col_name in analysis['data_types'].keys():
                    col_words = str(col_name).replace('_', ' ').replace('-', ' ').split()
                    keywords.extend([word for word in col_words if len(word) > 1])
        
        # 特殊模式关键词
        for sheet_name, analysis in data_analysis.items():
            if 'patterns' in analysis:
                for pattern in analysis['patterns'].values():
                    keywords.append(pattern)
        
        # 文本内容关键词
        if text:
            import re
            # 提取中文词汇（2个或以上连续汉字）
            chinese_words = re.findall(r'[\u4e00-\u9fff]{2,}', text)
            keywords.extend(chinese_words[:30])  # 限制数量
            
            # 提取英文单词（2个或以上字符）
            english_words = re.findall(r'[a-zA-Z]{2,}', text)
            keywords.extend(english_words[:30])  # 限制数量
            
            # 提取数字模式
            numbers = re.findall(r'\d{2,}', text)
            keywords.extend(numbers[:20])  # 限制数量
            
            # 提取特殊模式
            license_plates = re.findall(r'[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领][A-Z][A-Z0-9]{5}', text)
            keywords.extend(license_plates)
            
            id_numbers = re.findall(r'\d{17}[\dX]', text)
            keywords.extend(id_numbers)
            
            phone_numbers = re.findall(r'1[3-9]\d{9}', text)
            keywords.extend(phone_numbers)
        
        # 去重并过滤
        unique_keywords = list(set(keywords))
        return [kw for kw in unique_keywords if len(kw) > 1 and not kw.isspace()][:100]  # 限制总数
    
    def _format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f}MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"
    
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        将Excel文本进行智能分块
        
        Args:
            text: 原始文本
            chunk_size: 块大小
            overlap: 重叠大小
            
        Returns:
            文本块列表
        """
        if not text or not text.strip():
            return []
        
        # 清理文本
        text = self._clean_text(text)
        
        chunks = []
        
        # 首先按重要段落分隔符分割
        major_sections = re.split(r'\n\s*===\s*[^=]+\s*===\s*\n', text)
        
        for section in major_sections:
            section = section.strip()
            if not section:
                continue
            
            # 如果段落本身就很长，需要进一步分割
            if len(section) <= chunk_size:
                chunks.append(section)
            else:
                # 按工作表内容分割
                section_chunks = self._chunk_sheet_content(section, chunk_size, overlap)
                chunks.extend(section_chunks)
        
        logger.info(f"Excel text split into {len(chunks)} chunks")
        return chunks
    
    def _chunk_sheet_content(self, content: str, chunk_size: int, overlap: int) -> List[str]:
        """对工作表内容进行分块"""
        chunks = []
        
        # 按行分割内容
        lines = content.split('\n')
        current_chunk = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 如果添加这行会超过块大小
            if len(current_chunk) + len(line) > chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    
                    # 处理重叠
                    if overlap > 0 and len(current_chunk) > overlap:
                        overlap_text = current_chunk[-overlap:]
                        current_chunk = overlap_text + "\n" + line
                    else:
                        current_chunk = line
                else:
                    # 如果单行就超过块大小，强制添加
                    if len(line) > chunk_size:
                        # 截断长行
                        chunks.append(line[:chunk_size])
                        current_chunk = ""
                    else:
                        current_chunk = line
            else:
                if current_chunk:
                    current_chunk += "\n" + line
                else:
                    current_chunk = line
        
        # 添加最后一个块
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """清理Excel文本"""
        # 移除多余的空白字符
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        # 移除行末的多余空格
        text = re.sub(r' +\n', '\n', text)
        # 移除多余的空格
        text = re.sub(r' {2,}', ' ', text)
        return text.strip() 