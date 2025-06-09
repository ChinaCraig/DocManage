"""
向量服务适配器
提供与旧版 vector_service.py 兼容的接口，内部使用新的向量化系统
"""
import logging
import os
from typing import List, Dict, Any, Optional

from .base_vectorizer import BaseVectorizer
from .pdf_vectorizer import PDFVectorizer

logger = logging.getLogger(__name__)

class VectorServiceAdapter(BaseVectorizer):
    """向量服务适配器，提供兼容旧接口的实现"""
    
    def __init__(self, milvus_host: str = None, milvus_port: int = None, embedding_model: str = None):
        """初始化向量服务适配器"""
        super().__init__()
        
        # 使用配置文件中的值作为默认值
        self.milvus_host = milvus_host or os.getenv('MILVUS_HOST', 'localhost')
        self.milvus_port = milvus_port or int(os.getenv('MILVUS_PORT', '19530'))
        self.embedding_model = embedding_model or os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
        
        # 自动初始化
        self.initialize(self.milvus_host, self.milvus_port, self.embedding_model)
    
    def initialize(self, host: str = None, port: int = None, model_name: str = None):
        """初始化向量数据库连接和模型（兼容旧接口）"""
        # 使用配置值作为默认值
        host = host or self.milvus_host
        port = port or self.milvus_port
        model_name = model_name or self.embedding_model
        
        return self.initialize_vector_service(host, port, model_name)
    
    def create_collection(self):
        """创建向量集合（兼容旧接口）"""
        if not self.is_available:
            logger.info("Vector collection creation skipped - service not available")
            return True
            
        try:
            from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, utility
            
            if utility.has_collection(self.collection_name):
                logger.info(f"Collection {self.collection_name} already exists")
                return True
            
            # 定义字段
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.dimension)
            ]
            
            # 创建schema
            schema = CollectionSchema(fields, f"Document vectors for {self.collection_name}")
            
            # 创建集合
            collection = Collection(self.collection_name, schema)
            
            # 创建索引
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024}
            }
            collection.create_index("vector", index_params)
            
            logger.info(f"✅ Created collection: {self.collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            return False
    
    def insert_vectors(self, document_id: str, content_id: str, chunks: List[str]) -> List[str]:
        """
        插入向量数据（兼容旧接口）
        
        Args:
            document_id: 文档ID
            content_id: 内容ID
            chunks: 文本块列表
            
        Returns:
            向量ID列表
        """
        try:
            # 生成向量数据
            vectors_data = []
            vector_ids = []
            
            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue
                    
                chunk_id = f"{content_id}_chunk_{i}"
                vector = self.encode_text(chunk.strip())
                
                if vector:
                    vectors_data.append({
                        'document_id': str(document_id),
                        'chunk_id': chunk_id,
                        'text': chunk.strip(),
                        'vector': vector
                    })
                    vector_ids.append(chunk_id)
            
            # 插入向量数据库
            success = super().insert_vectors(vectors_data)
            
            if success:
                return vector_ids
            else:
                return []
                
        except Exception as e:
            logger.error(f"Failed to insert vectors: {e}")
            return []
    
    # 以下方法是抽象方法的默认实现，适配器不需要文件处理功能
    def extract_text(self, file_path: str) -> Dict[str, Any]:
        """适配器不提供文件提取功能"""
        return {
            'success': False,
            'error': 'Adapter does not support file extraction'
        }
    
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """简单的文本分块实现"""
        if not text:
            return []
        
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - overlap
            
            if start >= text_length:
                break
        
        return chunks
    
    def get_supported_extensions(self) -> List[str]:
        """适配器支持所有类型"""
        return []
    
    def search(self, query_text: str, top_k: int = 10, document_id: str = None, min_score: float = 0.0) -> List[Dict[str, Any]]:
        """搜索相似文档（兼容旧接口）"""
        return self.search_similar(query_text, top_k, document_id, min_score) 