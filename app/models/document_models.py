from datetime import datetime
from app import db

class DocumentNode(db.Model):
    """文档节点模型（文件夹和文件统一管理）"""
    __tablename__ = 'document_nodes'
    
    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(255), nullable=False, comment='节点名称')
    type = db.Column(db.Enum('folder', 'file'), nullable=False, comment='节点类型')
    parent_id = db.Column(db.BigInteger, db.ForeignKey('document_nodes.id'), nullable=True, comment='父节点ID')
    file_path = db.Column(db.String(500), nullable=True, comment='文件路径')
    file_type = db.Column(db.String(50), nullable=True, comment='文件类型')
    file_size = db.Column(db.BigInteger, nullable=True, comment='文件大小')
    mime_type = db.Column(db.String(100), nullable=True, comment='MIME类型')
    description = db.Column(db.Text, nullable=True, comment='描述信息')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100), default='system', comment='创建人')
    is_deleted = db.Column(db.Boolean, default=False, comment='是否删除')
    
    # 向量化相关字段
    is_vectorized = db.Column(db.Boolean, default=False, comment='是否已向量化')
    vector_status = db.Column(db.String(50), default='not_started', comment='向量化状态')
    vectorized_at = db.Column(db.DateTime, nullable=True, comment='向量化完成时间')
    minio_path = db.Column(db.String(500), nullable=True, comment='MinIO存储路径')
    doc_metadata = db.Column(db.JSON, nullable=True, comment='元数据（JSON格式）')
    
    # 关系
    children = db.relationship('DocumentNode', backref=db.backref('parent', remote_side=[id]))
    contents = db.relationship('DocumentContent', backref='document', cascade='all, delete-orphan')
    vector_records = db.relationship('VectorRecord', backref='document', cascade='all, delete-orphan')
    
    # 标签关系 - 多对多关系
    tags = db.relationship('Tag', secondary='document_tags', back_populates='documents')
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'parent_id': self.parent_id,
            'file_path': self.file_path,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'is_deleted': self.is_deleted,
            'is_vectorized': self.is_vectorized,
            'vector_status': self.vector_status,
            'vectorized_at': self.vectorized_at.isoformat() if self.vectorized_at else None,
            'minio_path': self.minio_path,
            'doc_metadata': self.doc_metadata,
            'tags': [tag.to_dict() for tag in self.tags] if self.tags else []
        }
    
    def to_tree_dict(self):
        """转换为树形结构字典"""
        result = self.to_dict()
        result['children'] = [child.to_tree_dict() for child in self.children if not child.is_deleted]
        return result

class Tag(db.Model):
    """标签模型"""
    __tablename__ = 'tags'
    
    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, comment='标签名称')
    color = db.Column(db.String(7), default='#007bff', comment='标签颜色')
    description = db.Column(db.Text, nullable=True, comment='标签描述')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100), default='system', comment='创建人')
    is_deleted = db.Column(db.Boolean, default=False, comment='是否删除')
    
    # 关系
    documents = db.relationship('DocumentNode', secondary='document_tags', back_populates='tags')
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'name': self.name,
            'color': self.color,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            'is_deleted': self.is_deleted
        }

class DocumentTag(db.Model):
    """文档标签关联模型"""
    __tablename__ = 'document_tags'
    
    id = db.Column(db.BigInteger, primary_key=True)
    document_id = db.Column(db.BigInteger, db.ForeignKey('document_nodes.id'), nullable=False)
    tag_id = db.Column(db.BigInteger, db.ForeignKey('tags.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100), default='system', comment='创建人')
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'document_id': self.document_id,
            'tag_id': self.tag_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by
        }

class DocumentContent(db.Model):
    """文档内容模型"""
    __tablename__ = 'document_contents'
    
    id = db.Column(db.BigInteger, primary_key=True)
    document_id = db.Column(db.BigInteger, db.ForeignKey('document_nodes.id'), nullable=False)
    content_text = db.Column(db.Text, nullable=True, comment='提取的文本内容')
    page_number = db.Column(db.Integer, nullable=True, comment='页码')
    chunk_index = db.Column(db.Integer, nullable=True, comment='chunk索引')
    chunk_text = db.Column(db.Text, nullable=True, comment='chunk文本片段')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    vector_records = db.relationship('VectorRecord', backref='content', cascade='all, delete-orphan')
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'document_id': self.document_id,
            'content_text': self.content_text,
            'page_number': self.page_number,
            'chunk_index': self.chunk_index,
            'chunk_text': self.chunk_text,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class VectorRecord(db.Model):
    """向量化记录模型"""
    __tablename__ = 'vector_records'
    
    id = db.Column(db.BigInteger, primary_key=True)
    document_id = db.Column(db.BigInteger, db.ForeignKey('document_nodes.id'), nullable=False)
    content_id = db.Column(db.BigInteger, db.ForeignKey('document_contents.id'), nullable=False)
    vector_id = db.Column(db.String(100), nullable=True, comment='Milvus中的向量ID')
    embedding_model = db.Column(db.String(100), nullable=True, comment='使用的嵌入模型')
    vector_status = db.Column(db.Enum('pending', 'processing', 'completed', 'failed'), 
                            default='pending', comment='向量化状态')
    error_message = db.Column(db.Text, nullable=True, comment='错误信息')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'document_id': self.document_id,
            'content_id': self.content_id,
            'vector_id': self.vector_id,
            'embedding_model': self.embedding_model,
            'vector_status': self.vector_status,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class SystemConfig(db.Model):
    """系统配置模型"""
    __tablename__ = 'system_configs'
    
    id = db.Column(db.BigInteger, primary_key=True)
    config_key = db.Column(db.String(100), unique=True, nullable=False, comment='配置键')
    config_value = db.Column(db.Text, nullable=True, comment='配置值')
    config_type = db.Column(db.String(50), default='string', comment='配置类型')
    description = db.Column(db.String(255), nullable=True, comment='配置描述')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'config_key': self.config_key,
            'config_value': self.config_value,
            'config_type': self.config_type,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def get_config(cls, key, default=None):
        """获取配置值"""
        config = cls.query.filter_by(config_key=key).first()
        if config:
            if config.config_type == 'int':
                return int(config.config_value)
            elif config.config_type == 'float':
                return float(config.config_value)
            elif config.config_type == 'json':
                import json
                return json.loads(config.config_value)
            else:
                return config.config_value
        return default 