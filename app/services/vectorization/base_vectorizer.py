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
        self.dimension = None  # 改为动态检测，不再硬编码
        self.model = None
        self.is_available = False
        self.enabled = os.getenv('ENABLE_VECTOR_SERVICE', 'false').lower() == 'true'
        
        # 从配置文件获取Milvus连接信息
        self.milvus_host = os.getenv('MILVUS_HOST', 'localhost')
        self.milvus_port = int(os.getenv('MILVUS_PORT', '19530'))
        
        if not self.enabled:
            logger.warning("Vector service is disabled by configuration")
    
    def _detect_model_dimension(self, model) -> int:
        """检测模型的实际维度"""
        try:
            if model is None:
                logger.warning("Model is None, using default dimension 384")
                return 384
            
            # 使用测试文本获取向量维度
            test_text = "This is a test sentence for dimension detection."
            test_vector = model.encode(test_text, normalize_embeddings=True)
            
            if hasattr(test_vector, 'shape'):
                dimension = test_vector.shape[0] if len(test_vector.shape) == 1 else test_vector.shape[-1]
            else:
                dimension = len(test_vector) if isinstance(test_vector, (list, tuple)) else len(test_vector.tolist())
            
            logger.info(f"🔍 检测到嵌入模型维度: {dimension}")
            return dimension
            
        except Exception as e:
            logger.error(f"Failed to detect model dimension: {e}")
            logger.warning("Using default dimension 384")
            return 384
    
    def _get_existing_collection_dimension(self) -> Optional[int]:
        """获取现有集合的向量维度"""
        try:
            from pymilvus import Collection, utility
            
            if not utility.has_collection(self.collection_name):
                return None
            
            collection = Collection(self.collection_name)
            schema = collection.schema
            
            for field in schema.fields:
                if field.name == "vector":
                    dimension = field.params.get('dim')
                    logger.info(f"📊 现有集合 '{self.collection_name}' 向量维度: {dimension}")
                    return dimension
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get existing collection dimension: {e}")
            return None
    
    def _handle_dimension_mismatch(self, model_dim: int, collection_dim: int) -> bool:
        """处理维度不匹配问题"""
        try:
            from pymilvus import utility
            
            logger.warning(f"⚠️ 维度不匹配: 模型维度={model_dim}, 集合维度={collection_dim}")
            logger.info(f"🔄 删除现有集合并重新创建...")
            
            # 删除现有集合
            if utility.has_collection(self.collection_name):
                utility.drop_collection(self.collection_name)
                logger.info(f"✅ 已删除集合 '{self.collection_name}'")
            
            # 更新维度为模型实际维度
            self.dimension = model_dim
            
            # 重新创建集合
            return self._create_collection_with_dimension(model_dim)
            
        except Exception as e:
            logger.error(f"Failed to handle dimension mismatch: {e}")
            return False
    
    def _create_collection_with_dimension(self, dimension: int) -> bool:
        """使用指定维度创建集合"""
        try:
            from pymilvus import Collection, FieldSchema, CollectionSchema, DataType
            
            logger.info(f"🚀 创建新集合，维度: {dimension}")
            
            # 定义字段
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dimension)
            ]
            
            # 创建集合架构
            schema = CollectionSchema(fields, f"Document vectors collection with {dimension}D embeddings")
            
            # 创建集合
            collection = Collection(self.collection_name, schema)
            
            # 创建索引
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128}
            }
            
            collection.create_index("vector", index_params)
            logger.info(f"✅ 创建集合 '{self.collection_name}' 成功，维度: {dimension}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create collection with dimension {dimension}: {e}")
            return False
    
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
                
                # 设置环境变量避免并发问题和警告
                os.environ['TOKENIZERS_PARALLELISM'] = 'false'
                
                # 设置torch环境变量以避免pin_memory警告
                import torch
                if not torch.cuda.is_available():
                    # 如果没有GPU，强制禁用pin_memory
                    os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:128'
                
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
            logger.info(f"🤖 使用嵌入模型: {model_name}")
            
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
            
            # 初始化模型（先加载模型再初始化集合）
            if not self.model:
                self.model = self._load_embedding_model(model_name)
                if not self.model:
                    logger.warning("⚠️ 未能加载嵌入模型，将使用模拟向量")
                    self.dimension = 384  # 使用默认维度
                else:
                    # 检测模型维度
                    self.dimension = self._detect_model_dimension(self.model)
                    logger.info(f"✅ 嵌入模型加载成功，维度: {self.dimension}")
            
            # 智能初始化集合（处理维度匹配）
            collection_initialized = self._initialize_collection_smart()
            
            if collection_initialized:
                logger.info("✅ Vector service initialized successfully")
            else:
                logger.error("❌ Collection initialization failed")
                return False
                    
            self.is_available = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize vector service: {e}")
            self.is_available = False
            return False
    
    def _initialize_collection_smart(self):
        """智能初始化Milvus集合，处理维度匹配问题"""
        try:
            from pymilvus import utility
            
            # 检查集合是否存在
            if utility.has_collection(self.collection_name):
                # 获取现有集合的维度
                existing_dim = self._get_existing_collection_dimension()
                
                if existing_dim is None:
                    logger.error("⚠️ 无法获取现有集合的维度信息")
                    return False
                
                # 检查维度是否匹配
                if existing_dim == self.dimension:
                    logger.info(f"✅ 集合 '{self.collection_name}' 已存在，维度匹配: {existing_dim}")
                    return True
                else:
                    # 维度不匹配，处理冲突
                    logger.warning(f"⚠️ 维度不匹配: 现有集合={existing_dim}, 模型={self.dimension}")
                    return self._handle_dimension_mismatch(self.dimension, existing_dim)
            else:
                # 集合不存在，创建新集合
                logger.info(f"📦 集合 '{self.collection_name}' 不存在，创建新集合...")
                return self._create_collection_with_dimension(self.dimension)
            
        except Exception as e:
            logger.error(f"Failed to smart initialize collection: {e}")
            return False
    
    def _initialize_collection(self):
        """初始化Milvus集合（保留原方法以兼容性）"""
        try:
            from pymilvus import Collection, FieldSchema, CollectionSchema, DataType, utility
            
            # 检查集合是否存在
            if utility.has_collection(self.collection_name):
                logger.info(f"Collection '{self.collection_name}' already exists")
                return True
            
            # 使用当前维度（如果为None则使用默认值）
            dimension = self.dimension or 384
            
            # 定义字段
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dimension)
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
        
        # 确保dimension有值
        dimension = self.dimension or 384
        
        if not self.is_available or not current_model:
            logger.warning(f"Text encoding skipped - service available: {self.is_available}, model loaded: {current_model is not None}")
            # 返回模拟向量
            return [0.0] * dimension
            
        try:
            logger.debug(f"Encoding text with model: {type(current_model).__name__}")
            # 使用sentence-transformers编码文本
            vector = current_model.encode(text, normalize_embeddings=True)
            result_vector = vector.tolist()
            
            # 验证向量维度是否正确
            actual_dim = len(result_vector)
            if actual_dim != dimension:
                logger.warning(f"⚠️ 向量维度不匹配: 期望={dimension}, 实际={actual_dim}")
                # 更新维度设置
                self.dimension = actual_dim
                logger.info(f"🔄 已更新dimension为: {actual_dim}")
            
            # 验证向量是否为零向量
            vector_sum = sum(abs(v) for v in result_vector)
            if vector_sum < 1e-6:
                logger.error(f"Generated zero vector! Text: {text[:50]}...")
                logger.error(f"Model type: {type(current_model)}")
                logger.error(f"Vector shape: {vector.shape if hasattr(vector, 'shape') else 'unknown'}")
            else:
                logger.debug(f"✅ Generated valid vector, dim: {actual_dim}, sum: {vector_sum:.6f}, range: [{min(result_vector):.4f}, {max(result_vector):.4f}]")
            
            return result_vector
        except Exception as e:
            logger.error(f"Failed to encode text: {e}")
            logger.error(f"Model instance: {current_model}")
            logger.error(f"Text sample: {text[:100]}...")
            return [0.0] * dimension
    
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
    
    def search_similar(self, query_text: str, top_k: int = 10, document_id: str = None, min_score: float = 0.0) -> List[Dict[str, Any]]:
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
            
            # 处理结果，添加相似度阈值过滤
            similar_docs = []
            for hits in results:
                for hit in hits:
                    score = float(hit.score)
                    # 只返回相似度大于等于阈值的结果
                    if score >= min_score:
                        similar_docs.append({
                            "document_id": hit.entity.get("document_id"),
                            "chunk_id": hit.entity.get("chunk_id"), 
                            "text": hit.entity.get("text"),
                            "score": score
                        })
            
            logger.info(f"Found {len(similar_docs)} similar documents (filtered by min_score={min_score})")
            return similar_docs
            
        except Exception as e:
            logger.error(f"Failed to search similar documents: {e}")
            return []

    def search_by_keywords(self, query_text: str, top_k: int = 10, document_id: str = None) -> List[Dict[str, Any]]:
        """基于关键词的文本搜索（补充语义搜索）"""
        if not self.is_available:
            logger.info("Keyword search skipped - service not available")
            return []
            
        try:
            from pymilvus import Collection
            
            collection = Collection(self.collection_name)
            collection.load()
            
            # 提取查询关键词
            keywords = self._extract_query_keywords(query_text)
            if not keywords:
                return []
            
            # 构建关键词匹配表达式
            keyword_expressions = []
            for keyword in keywords:
                # 使用LIKE操作符进行文本匹配
                keyword_expressions.append(f'text like "%{keyword}%"')
            
            # 组合表达式
            if len(keyword_expressions) == 1:
                expr = keyword_expressions[0]
            else:
                # 使用OR连接，只要包含任一关键词即可
                expr = f"({' or '.join(keyword_expressions)})"
            
            # 如果指定了文档ID，添加过滤条件
            if document_id:
                expr = f'({expr}) and document_id == "{document_id}"'
            
            logger.info(f"关键词搜索表达式: {expr}")
            
            # 执行查询（使用query而不是search，因为我们要基于文本匹配）
            results = collection.query(
                expr=expr,
                output_fields=["document_id", "chunk_id", "text"],
                limit=top_k
            )
            
            # 处理结果，计算匹配度
            keyword_docs = []
            for result in results:
                # 计算关键词匹配度
                text = result.get("text", "")
                match_score = self._calculate_keyword_match_score(text, keywords)
                
                keyword_docs.append({
                    "document_id": result.get("document_id"),
                    "chunk_id": result.get("chunk_id"),
                    "text": text,
                    "score": match_score,
                    "matched_keywords": self._find_matched_keywords(text, keywords)
                })
            
            # 按匹配度排序
            keyword_docs.sort(key=lambda x: x["score"], reverse=True)
            
            logger.info(f"关键词搜索找到 {len(keyword_docs)} 个匹配结果")
            return keyword_docs[:top_k]
            
        except Exception as e:
            logger.error(f"关键词搜索失败: {e}")
            return []
    
    def _extract_query_keywords(self, query_text: str) -> List[str]:
        """从查询文本中提取关键词"""
        import re
        
        keywords = []
        
        # 1. 提取中文词汇（2个或以上连续汉字）
        chinese_words = re.findall(r'[\u4e00-\u9fff]{2,}', query_text)
        keywords.extend(chinese_words)
        
        # 2. 提取英文单词（2个或以上字符）
        english_words = re.findall(r'[a-zA-Z]{2,}', query_text)
        keywords.extend(english_words)
        
        # 3. 提取数字模式
        numbers = re.findall(r'\d{2,}', query_text)
        keywords.extend(numbers)
        
        # 4. 提取专业术语（包含大小写字母和数字的组合）
        technical_terms = re.findall(r'[a-zA-Z]+\d+|[A-Z]{2,}', query_text)
        keywords.extend(technical_terms)
        
        # 去重并过滤
        unique_keywords = list(set(keywords))
        # 过滤掉过短的词汇
        filtered_keywords = [kw for kw in unique_keywords if len(kw) >= 2]
        
        logger.info(f"提取的关键词: {filtered_keywords}")
        return filtered_keywords
    
    def _calculate_keyword_match_score(self, text: str, keywords: List[str]) -> float:
        """计算关键词匹配度分数"""
        if not text or not keywords:
            return 0.0
        
        text_lower = text.lower()
        total_matches = 0
        unique_matches = 0
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            matches = text_lower.count(keyword_lower)
            if matches > 0:
                total_matches += matches
                unique_matches += 1
        
        # 计算分数：考虑匹配的关键词数量和总匹配次数
        keyword_coverage = unique_matches / len(keywords)  # 关键词覆盖率
        match_density = min(total_matches / len(text.split()), 1.0)  # 匹配密度
        
        # 综合分数
        score = keyword_coverage * 0.7 + match_density * 0.3
        return min(score, 1.0)
    
    def _find_matched_keywords(self, text: str, keywords: List[str]) -> List[str]:
        """找到文本中匹配的关键词"""
        text_lower = text.lower()
        matched = []
        
        for keyword in keywords:
            if keyword.lower() in text_lower:
                matched.append(keyword)
        
        return matched

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
    
    def generate_vectors_data(self, document_id: str, text_chunks: List[str], 
                             enhanced_chunks: List[str] = None) -> List[Dict[str, Any]]:
        """
        生成向量数据
        
        Args:
            document_id: 文档ID
            text_chunks: 原始文本块（用于存储和显示）
            enhanced_chunks: 增强文本块（用于向量化，包含额外上下文）
        """
        vectors_data = []
        
        # 如果没有提供增强文本块，则使用原始文本块
        if enhanced_chunks is None:
            enhanced_chunks = text_chunks
        
        for i, (original_chunk, enhanced_chunk) in enumerate(zip(text_chunks, enhanced_chunks)):
            if not original_chunk.strip():
                continue
                
            chunk_id = f"chunk_{i}_{str(uuid.uuid4())[:8]}"
            # 使用增强文本进行向量化
            vector = self.encode_text(enhanced_chunk.strip())
            
            if vector:
                vectors_data.append({
                    'document_id': str(document_id),
                    'chunk_id': chunk_id,
                    'text': original_chunk.strip(),  # 存储原始文本
                    'vector': vector  # 但向量基于增强文本
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
    
    def chunk_text_smart(self, text: str, chunk_size: int = 800, overlap: int = 150) -> List[str]:
        """智能分段，保持语义完整性"""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        sentences = self._split_sentences(text)
        current_chunk = ""
        
        for sentence in sentences:
            # 如果添加这个句子不会超过限制
            if len(current_chunk + sentence) <= chunk_size:
                current_chunk += sentence
            else:
                # 保存当前chunk
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # 开始新chunk，包含overlap
                if chunks and overlap > 0:
                    overlap_text = current_chunk[-overlap:]
                    current_chunk = overlap_text + sentence
                else:
                    current_chunk = sentence
        
        # 添加最后一个chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        """按句子分割文本"""
        import re
        # 中文句号、英文句号、问号、感叹号
        sentences = re.split(r'[。！？.!?]\s*', text)
        # 为分割后的句子添加句号，保持语义完整
        result = []
        for sentence in sentences:
            if sentence.strip():
                # 检查原句子是否以标点结尾
                if sentence.strip() and not re.search(r'[。！？.!?]$', sentence.strip()):
                    result.append(sentence.strip() + '。')
                else:
                    result.append(sentence.strip())
        return result
    
    def vectorize_document_enhanced(self, file_path: str, document_id: str, chunk_size: int = 800, overlap: int = 150) -> Dict[str, Any]:
        """增强版文档向量化，包含关键词索引"""
        try:
            # 1. 提取文本内容
            extract_result = self.extract_text(file_path)
            if not extract_result['success']:
                return extract_result
            
            text = extract_result['text']
            
            # 2. 提取关键词
            keywords = self._extract_keywords_from_content(text, os.path.basename(file_path))
            
            # 3. 智能分段
            chunks = self.chunk_text_smart(text, chunk_size, overlap)
            
            # 4. 为每个chunk添加关键词增强
            enhanced_chunks = []
            for i, chunk in enumerate(chunks):
                # 找到与此chunk相关的关键词
                chunk_keywords = [kw for kw in keywords if kw.lower() in chunk.lower()]
                
                # 创建增强文本（原文本 + 关键词）
                enhanced_text = chunk
                if chunk_keywords:
                    enhanced_text += f"\n关键词: {', '.join(chunk_keywords)}"
                
                enhanced_chunks.append({
                    'text': chunk,
                    'enhanced_text': enhanced_text,
                    'keywords': chunk_keywords,
                    'chunk_index': i
                })
            
            # 5. 向量化增强文本
            vectors_data = []
            for chunk_data in enhanced_chunks:
                chunk_id = f"chunk_{chunk_data['chunk_index']}_{str(uuid.uuid4())[:8]}"
                vector = self.encode_text(chunk_data['enhanced_text'])
                
                if vector:
                    vectors_data.append({
                        'document_id': str(document_id),
                        'chunk_id': chunk_id,
                        'text': chunk_data['text'],  # 存储原始文本
                        'vector': vector
                    })
            
            # 6. 插入向量数据库
            insert_success = self.insert_vectors(vectors_data)
            
            return {
                'success': True,
                'text': text,
                'metadata': extract_result['metadata'],
                'chunks': [{'id': f'chunk_{i}', 'content': chunk['text']} for i, chunk in enumerate(enhanced_chunks)],
                'vectors_count': len(vectors_data),
                'vector_insert_success': insert_success,
                'keywords': keywords,
                'chunk_size': chunk_size,
                'overlap': overlap,
                'enhancement': 'enabled'
            }
            
        except Exception as e:
            logger.error(f"增强向量化失败: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _extract_keywords_from_content(self, text: str, filename: str) -> List[str]:
        """从内容中提取关键词用于检索优化"""
        keywords = []
        
        # 文件名关键词
        base_name = os.path.splitext(filename)[0]
        filename_words = base_name.replace('_', ' ').replace('-', ' ').split()
        keywords.extend([word for word in filename_words if len(word) > 1])
        
        # 文本内容关键词
        if text:
            import re
            # 提取中文词汇（2个或以上连续汉字）
            chinese_words = re.findall(r'[\u4e00-\u9fff]{2,}', text)
            keywords.extend(chinese_words[:50])  # 限制数量
            
            # 提取英文单词（2个或以上字符）
            english_words = re.findall(r'[a-zA-Z]{2,}', text)
            keywords.extend(english_words[:50])  # 限制数量
            
            # 提取数字模式
            numbers = re.findall(r'\d{2,}', text)
            keywords.extend(numbers[:20])  # 限制数量
            
            # 提取可能的专业术语
            technical_terms = re.findall(r'[A-Z]{2,}|[a-zA-Z]+\d+', text)
            keywords.extend(technical_terms[:30])
        
        # 去重并过滤
        unique_keywords = list(set(keywords))
        return [kw for kw in unique_keywords if len(kw) > 1 and not kw.isspace()][:100]  # 限制总数

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