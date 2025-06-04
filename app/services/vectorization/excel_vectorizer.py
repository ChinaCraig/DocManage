"""
Excel文档向量化器
专门处理Excel文件(.xls, .xlsx)的内容提取和向量化
"""

import logging
import os
import re
from typing import List, Dict, Any
from .base_vectorizer import BaseVectorizer

logger = logging.getLogger(__name__)

class ExcelVectorizer(BaseVectorizer):
    """Excel文档向量化器"""
    
    def __init__(self):
        """初始化Excel向量化器"""
        super().__init__()
        self.file_type = "excel"
    
    def get_supported_extensions(self) -> List[str]:
        """获取支持的文件扩展名"""
        return ['.xls', '.xlsx']
    
    def extract_text(self, file_path: str) -> Dict[str, Any]:
        """
        从Excel文件提取文本内容
        
        Args:
            file_path: Excel文件路径
            
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
                
                # 读取Excel文件的所有工作表
                excel_file = pd.ExcelFile(file_path)
                
                # 获取基本元数据
                metadata = {
                    'file_size': os.path.getsize(file_path),
                    'file_type': file_ext.replace('.', ''),
                    'sheet_names': excel_file.sheet_names,
                    'total_sheets': len(excel_file.sheet_names)
                }
                
                # 提取所有工作表的内容
                text_parts = []
                sheet_contents = {}
                
                for sheet_name in excel_file.sheet_names:
                    try:
                        # 读取工作表
                        df = pd.read_excel(file_path, sheet_name=sheet_name)
                        
                        if df.empty:
                            continue
                        
                        # 提取工作表信息
                        sheet_info = {
                            'rows': len(df),
                            'columns': len(df.columns),
                            'column_names': list(df.columns)
                        }
                        
                        # 转换为文本格式
                        sheet_text = self._dataframe_to_text(df, sheet_name)
                        
                        if sheet_text:
                            text_parts.append(f"[工作表: {sheet_name}]\n{sheet_text}")
                            sheet_contents[sheet_name] = {
                                'text': sheet_text,
                                'info': sheet_info
                            }
                        
                    except Exception as e:
                        logger.warning(f"Failed to process sheet '{sheet_name}': {e}")
                        continue
                
                # 合并所有工作表的文本
                full_text = '\n\n'.join(text_parts)
                
                if not full_text.strip():
                    return {
                        'success': False,
                        'error': 'Excel文件中没有可提取的文本内容'
                    }
                
                # 更新元数据
                metadata['sheet_contents'] = sheet_contents
                
                # 进行文本分块
                chunks = self.chunk_text(full_text)
                
                return {
                    'success': True,
                    'text': full_text,
                    'metadata': metadata,
                    'chunks': chunks
                }
                
            except ImportError:
                return {
                    'success': False,
                    'error': 'pandas库未安装，请运行: pip install pandas openpyxl'
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
    
    def _dataframe_to_text(self, df, sheet_name: str) -> str:
        """将DataFrame转换为文本格式"""
        text_parts = []
        
        # 添加列标题
        if not df.columns.empty:
            headers = [str(col) for col in df.columns if pd.notna(col)]
            if headers:
                text_parts.append(f"表头: {' | '.join(headers)}")
        
        # 提取每行数据
        for index, row in df.iterrows():
            row_text = []
            
            for col_name, value in row.items():
                if pd.notna(value) and str(value).strip():
                    # 清理单元格内容
                    cell_value = str(value).strip()
                    if cell_value and cell_value != 'nan':
                        row_text.append(f"{col_name}: {cell_value}")
            
            if row_text:
                text_parts.append(' | '.join(row_text))
        
        return '\n'.join(text_parts)
    
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
        
        # 按工作表分割
        sheet_sections = re.split(r'\[工作表:.*?\]', text)
        sheet_names = re.findall(r'\[工作表:(.*?)\]', text)
        
        for i, section in enumerate(sheet_sections):
            section = section.strip()
            if not section:
                continue
            
            # 获取工作表名称
            sheet_name = sheet_names[i-1] if i > 0 and i-1 < len(sheet_names) else "数据"
            
            # 对每个工作表的内容进行分块
            section_chunks = self._chunk_sheet_content(section, chunk_size, overlap, sheet_name)
            chunks.extend(section_chunks)
        
        # 过滤掉太短的块
        chunks = [chunk for chunk in chunks if len(chunk.strip()) > 50]
        
        logger.info(f"Excel text split into {len(chunks)} chunks")
        return chunks
    
    def _chunk_sheet_content(self, content: str, chunk_size: int, overlap: int, sheet_name: str) -> List[str]:
        """对工作表内容进行分块"""
        chunks = []
        
        # 按行分割
        lines = content.split('\n')
        
        current_chunk = f"[{sheet_name}工作表数据]\n"
        header_line = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检测表头行
            if line.startswith('表头:'):
                header_line = line
                current_chunk += line + '\n'
                continue
            
            # 如果添加当前行会超过块大小
            if len(current_chunk) + len(line) > chunk_size:
                if len(current_chunk.strip()) > len(f"[{sheet_name}工作表数据]") + 10:
                    chunks.append(current_chunk.strip())
                    
                    # 处理重叠 - 保留表头和部分数据
                    if overlap > 0:
                        overlap_lines = current_chunk.split('\n')[-3:]  # 保留最后几行
                        current_chunk = f"[{sheet_name}工作表数据]\n"
                        if header_line:
                            current_chunk += header_line + '\n'
                        current_chunk += '\n'.join(overlap_lines) + '\n' + line + '\n'
                    else:
                        current_chunk = f"[{sheet_name}工作表数据]\n"
                        if header_line:
                            current_chunk += header_line + '\n'
                        current_chunk += line + '\n'
                else:
                    current_chunk += line + '\n'
            else:
                current_chunk += line + '\n'
        
        # 添加最后一个块
        if len(current_chunk.strip()) > len(f"[{sheet_name}工作表数据]") + 10:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """清理Excel提取的文本"""
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        
        # 移除重复的分隔符
        text = re.sub(r'\|\s*\|', '|', text)
        
        # 清理数字格式
        text = re.sub(r'\.0+\b', '', text)  # 移除不必要的.0
        
        # 恢复行结构
        text = re.sub(r'\s*\n\s*', '\n', text)
        
        return text.strip() 