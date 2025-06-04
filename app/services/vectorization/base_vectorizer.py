"""
基础向量化器
定义所有向量化器的通用接口和功能
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import os
import uuid
from datetime import datetime
import threading

logger = logging.getLogger(__name__)

# 全局模型实例和锁，避免重复加载
_model_instance = None
_model_lock = threading.Lock()

class BaseVectorizer(ABC):
    """基础向量化器抽象类"""
    
    def __init__(self):
        """初始化基础向量化器"""
        self.collection_name = "document_vectors"
        self.dimension = 384  # all-MiniLM-L6-v2 模型的维度
        self.model = None
        self.is_available = False
        self.enabled = os.getenv('ENABLE_VECTOR_SERVICE', 'false').lower() == 'true'
        
        # 从配置文件获取Milvus连接信息
        self.milvus_host = os.getenv('MILVUS_HOST', 'localhost')
        self.milvus_port = int(os.getenv('MILVUS_PORT', '19530'))
        
        if not self.enabled:
            logger.warning("Vector service is disabled by configuration")
    
    def _load_embedding_model(self, model_name: str = 'all-MiniLM-L6-v2'):
        """安全地加载嵌入模型（单例模式）"""
        global _model_instance, _model_lock
        
        with _model_lock:
            # 如果已有实例，直接使用
            if _model_instance is not None:
                logger.info("Using existing embedding model instance")
                return _model_instance
            
            try:
                logger.info(f"Loading text embedding model: {model_name}")
                from sentence_transformers import SentenceTransformer
                
                # 设置环境变量避免并发问题
                os.environ['TOKENIZERS_PARALLELISM'] = 'false'
                
                # 加载模型
                _model_instance = SentenceTransformer(model_name)
                logger.info("✅ Embedding model loaded successfully")
                return _model_instance
                
            except ImportError:
                logger.warning("sentence-transformers not available, will use mock vectors")
                return None
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                # 清除可能损坏的实例
                _model_instance = None
                return None
    
    def initialize_vector_service(self, host: str = None, port: int = None, model_name: str = None):
        """初始化向量数据库连接和模型"""
        if not self.enabled:
            logger.info("Vector service initialization skipped - disabled by configuration")
            return True
            
        try:
            # 使用传入的参数或配置文件中的值
            host = host or self.milvus_host
            port = port or self.milvus_port
            model_name = model_name or os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
            
            logger.info(f"Initializing vector service - connecting to {host}:{port}")
            
            from pymilvus import connections, utility
            
            # 检查是否已存在连接，如果存在且配置不同则先断开
            if connections.has_connection("default"):
                try:
                    # 尝试断开现有连接
                    connections.disconnect("default")
                    logger.info("Disconnected existing Milvus connection")
                except Exception as e:
                    logger.warning(f"Failed to disconnect existing connection: {e}")
            
            # 建立新连接
            connections.connect(
                alias="default",
                host=host,
                port=str(port)
            )
            
            # 验证连接
            if not connections.has_connection("default"):
                raise Exception("Failed to establish Milvus connection")
            
            # 初始化集合
            self._initialize_collection()
            
            # 初始化模型（使用新的安全加载方法）
            if not self.model:
                self.model = self._load_embedding_model(model_name)
                if self.model:
                    logger.info("✅ Vector service initialized successfully")
                else:
                    logger.warning("⚠️ Vector service initialized without embedding model (will use mock vectors)")
                    
            self.is_available = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize vector service: {e}")
            self.is_available = False
            return False
    
    def _initialize_collection(self):
        """初始化Milvus集合"""
        try:
            from pymilvus import Collection, FieldSchema, CollectionSchema, DataType, utility
            
            # 检查集合是否存在
            if utility.has_collection(self.collection_name):
                logger.info(f"Collection '{self.collection_name}' already exists")
                return True
            
            # 定义字段
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.dimension)
            ]
            
            # 创建集合架构
            schema = CollectionSchema(fields, f"Document vectors collection")
            
            # 创建集合
            collection = Collection(self.collection_name, schema)
            
            # 创建索引
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128}
            }
            
            collection.create_index("vector", index_params)
            logger.info(f"✅ Created collection '{self.collection_name}' with index")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize collection: {e}")
            return False
    
    def encode_text(self, text: str) -> Optional[List[float]]:
        """将文本编码为向量"""
        global _model_instance
        
        # 首先检查是否有本地模型实例
        current_model = self.model or _model_instance
        
        if not self.is_available or not current_model:
            logger.warning(f"Text encoding skipped - service available: {self.is_available}, model loaded: {current_model is not None}")
            # 返回模拟向量
            return [0.0] * self.dimension
            
        try:
            logger.debug(f"Encoding text with model: {type(current_model).__name__}")
            # 使用sentence-transformers编码文本
            vector = current_model.encode(text, normalize_embeddings=True)
            result_vector = vector.tolist()
            
            # 验证向量是否为零向量
            vector_sum = sum(abs(v) for v in result_vector)
            if vector_sum < 1e-6:
                logger.error(f"Generated zero vector! Text: {text[:50]}...")
                logger.error(f"Model type: {type(current_model)}")
                logger.error(f"Vector shape: {vector.shape if hasattr(vector, 'shape') else 'unknown'}")
            else:
                logger.info(f"✅ Generated valid vector, sum: {vector_sum:.6f}, range: [{min(result_vector):.4f}, {max(result_vector):.4f}]")
            
            return result_vector
        except Exception as e:
            logger.error(f"Failed to encode text: {e}")
            logger.error(f"Model instance: {current_model}")
            logger.error(f"Text sample: {text[:100]}...")
            return [0.0] * self.dimension
    
    def insert_vectors(self, vectors_data: List[Dict[str, Any]]) -> bool:
        """插入向量数据到Milvus"""
        if not self.is_available:
            logger.info(f"Vector insertion skipped for {len(vectors_data)} items - service not available")
            return True
            
        try:
            from pymilvus import Collection
            
            collection = Collection(self.collection_name)
            
            # 直接使用字典列表格式 - pymilvus 2.5.x 的正确格式
            result = collection.insert(vectors_data)
            collection.flush()
            
            logger.info(f"✅ Inserted {len(vectors_data)} vectors into collection")
            return True
            
        except Exception as e:
            logger.error(f"Failed to insert vectors: {e}")
            return False
    
    def search_similar(self, query_text: str, top_k: int = 10, document_id: str = None) -> List[Dict[str, Any]]:
        """搜索相似文档"""
        if not self.is_available:
            logger.info("Vector search skipped - service not available")
            return []
            
        try:
            from pymilvus import Collection
            
            # 编码查询文本
            query_vector = self.encode_text(query_text)
            if not query_vector:
                return []
            
            collection = Collection(self.collection_name)
            collection.load()
            
            # 搜索参数
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }
            
            # 构建过滤表达式
            expr = None
            if document_id:
                expr = f'document_id == "{document_id}"'
            
            # 执行搜索
            results = collection.search(
                data=[query_vector],
                anns_field="vector",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["document_id", "chunk_id", "text"]
            )
            
            # 处理结果
            similar_docs = []
            for hits in results:
                for hit in hits:
                    similar_docs.append({
                        "document_id": hit.entity.get("document_id"),
                        "chunk_id": hit.entity.get("chunk_id"), 
                        "text": hit.entity.get("text"),
                        "score": float(hit.score)
                    })
            
            logger.info(f"Found {len(similar_docs)} similar documents")
            return similar_docs
            
        except Exception as e:
            logger.error(f"Failed to search similar documents: {e}")
            return []

    def delete_vectors(self, document_id: str) -> bool:
        """删除指定文档的向量"""
        if not self.is_available:
            logger.info(f"Vector deletion skipped for document {document_id} - service not available")
            return True
            
        try:
            from pymilvus import Collection
            
            collection = Collection(self.collection_name)
            
            # 删除指定文档的所有向量
            expr = f'document_id == "{document_id}"'
            collection.delete(expr)
            collection.flush()
            
            logger.info(f"✅ Deleted vectors for document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete vectors for document {document_id}: {e}")
            return False

    def get_collection_stats(self) -> Dict[str, Any]:
        """获取集合统计信息"""
        if not self.is_available:
            logger.info("Collection stats retrieval skipped - service not available")
            return {
                "total_entities": 0,
                "index_type": "unknown",
                "metric_type": "unknown",
                "collection_name": self.collection_name,
                "status": "unavailable"
            }
            
        try:
            from pymilvus import Collection, utility
            
            if not utility.has_collection(self.collection_name):
                return {
                    "total_entities": 0,
                    "index_type": "none",
                    "metric_type": "none",
                    "collection_name": self.collection_name,
                    "status": "not_created"
                }
            
            collection = Collection(self.collection_name)
            collection.load()
            
            # 获取统计信息
            stats = {
                "total_entities": collection.num_entities,
                "collection_name": self.collection_name,
                "status": "loaded"
            }
            
            # 尝试获取索引信息
            try:
                indexes = collection.indexes
                if indexes:
                    index_info = indexes[0]
                    stats["index_type"] = index_info.params.get("index_type", "unknown")
                    stats["metric_type"] = index_info.params.get("metric_type", "unknown")
                else:
                    stats["index_type"] = "none"
                    stats["metric_type"] = "none"
            except:
                stats["index_type"] = "unknown"
                stats["metric_type"] = "unknown"
            
            logger.info(f"Collection stats: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {
                "total_entities": 0,
                "index_type": "error",
                "metric_type": "error",
                "collection_name": self.collection_name,
                "status": "error",
                "error": str(e)
            }
    
    def generate_vectors_data(self, document_id: str, text_chunks: List[str]) -> List[Dict[str, Any]]:
        """生成向量数据"""
        vectors_data = []
        
        for i, chunk in enumerate(text_chunks):
            if not chunk.strip():
                continue
                
            chunk_id = f"chunk_{i}_{str(uuid.uuid4())[:8]}"
            vector = self.encode_text(chunk.strip())
            
            if vector:
                vectors_data.append({
                    'document_id': str(document_id),
                    'chunk_id': chunk_id,
                    'text': chunk.strip(),
                    'vector': vector
                })
        
        return vectors_data
    
    @abstractmethod
    def extract_text(self, file_path: str) -> Dict[str, Any]:
        """
        提取文件内容
        
        Args:
            file_path: 文件路径
            
        Returns:
            Dict包含:
            - success: bool, 是否成功
            - text: str, 提取的文本内容
            - metadata: dict, 文件元数据
            - chunks: list, 文本分块
            - error: str, 错误信息（如果失败）
        """
        pass
    
    @abstractmethod
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        文本分块
        
        Args:
            text: 原始文本
            chunk_size: 块大小
            overlap: 重叠大小
            
        Returns:
            文本块列表
        """
        pass
    
    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """
        获取支持的文件扩展名
        
        Returns:
            支持的扩展名列表
        """
        pass
    
    def vectorize_document(self, file_path: str, document_id: str, chunk_size: int = 1000, overlap: int = 200) -> Dict[str, Any]:
        """
        完整的文档向量化流程
        
        Args:
            file_path: 文件路径
            document_id: 文档ID
            chunk_size: 分块大小
            overlap: 重叠大小
            
        Returns:
            处理结果字典
        """
        try:
            # 1. 提取文本
            extract_result = self.extract_text(file_path)
            if not extract_result['success']:
                return extract_result
            
            # 2. 文本分块
            if chunk_size != 1000 or overlap != 200:
                # 重新分块
                chunks = self.chunk_text(extract_result['text'], chunk_size, overlap)
            else:
                chunks = extract_result.get('chunks', [])
            
            # 3. 生成向量数据
            vectors_data = self.generate_vectors_data(document_id, chunks)
            
            # 4. 插入向量数据库
            insert_success = self.insert_vectors(vectors_data)
            
            return {
                'success': True,
                'text': extract_result['text'],
                'metadata': extract_result['metadata'],
                'chunks': [{'id': f'chunk_{i}', 'content': chunk} for i, chunk in enumerate(chunks)],
                'vectors_count': len(vectors_data),
                'vector_insert_success': insert_success,
                'chunk_size': chunk_size,
                'overlap': overlap
            }
            
        except Exception as e:
            logger.error(f"Document vectorization failed: {e}")
            return {
                'success': False,
                'error': str(e)
            } 