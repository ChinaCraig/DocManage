-- =====================================================
-- 智能文档 - 完整数据库设置脚本
-- =====================================================
-- 
-- 使用说明：
-- 1. 先创建数据库：CREATE DATABASE document_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- 2. 使用数据库：USE document_management;
-- 3. 执行此脚本：mysql -u root -p document_management < database/merged_database_setup.sql
--
-- 或者直接在MySQL命令行中执行：
-- mysql -h 192.168.16.199 -u root -p
-- mysql> CREATE DATABASE document_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- mysql> USE document_management;
-- mysql> source /path/to/database/merged_database_setup.sql;
--
-- 此脚本包含：
-- - 创建所有数据表（已包含向量化字段）
-- - 插入默认配置和标签数据（包含向量化配置）
-- - 创建必要的索引
-- - 验证和检查
--
-- =====================================================

-- 设置数据库
USE document_management;

-- =====================================================
-- 第一部分：创建表结构（已整合向量化字段）
-- =====================================================

-- =====================================================
-- 1. 文档节点表（文件夹和文件统一管理）
-- =====================================================
CREATE TABLE IF NOT EXISTS document_nodes (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL COMMENT '节点名称',
    type ENUM('folder', 'file') NOT NULL COMMENT '节点类型：folder-文件夹，file-文件',
    parent_id BIGINT DEFAULT NULL COMMENT '父节点ID，NULL表示根节点',
    file_path VARCHAR(500) DEFAULT NULL COMMENT '文件路径（仅文件类型有效）',
    file_type VARCHAR(50) DEFAULT NULL COMMENT '文件类型：pdf,word,excel,image,video',
    file_size BIGINT DEFAULT NULL COMMENT '文件大小（字节）',
    mime_type VARCHAR(100) DEFAULT NULL COMMENT 'MIME类型',
    description TEXT COMMENT '描述信息',
    
    -- 向量化相关字段
    is_vectorized TINYINT(1) DEFAULT 0 COMMENT '是否已向量化',
    vector_status VARCHAR(50) DEFAULT 'not_started' COMMENT '向量化状态',
    vectorized_at TIMESTAMP NULL COMMENT '向量化完成时间',
    minio_path VARCHAR(500) NULL COMMENT 'MinIO存储路径',
    doc_metadata JSON NULL COMMENT '元数据（JSON格式）',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by VARCHAR(100) DEFAULT 'system' COMMENT '创建人',
    is_deleted TINYINT(1) DEFAULT 0 COMMENT '是否删除：0-未删除，1-已删除',
    
    -- 索引
    INDEX idx_parent_id (parent_id),
    INDEX idx_type (type),
    INDEX idx_file_type (file_type),
    INDEX idx_created_at (created_at),
    INDEX idx_name (name),
    INDEX idx_is_vectorized (is_vectorized),
    INDEX idx_vector_status (vector_status),
    INDEX idx_vectorized_at (vectorized_at),
    
    -- 外键约束
    FOREIGN KEY (parent_id) REFERENCES document_nodes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档节点表';

-- =====================================================
-- 2. 文档内容表（存储文档提取的文本内容）
-- =====================================================
CREATE TABLE IF NOT EXISTS document_contents (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    document_id BIGINT NOT NULL COMMENT '文档节点ID',
    content_text LONGTEXT COMMENT '提取的文本内容',
    page_number INT DEFAULT NULL COMMENT '页码（PDF等分页文档）',
    chunk_index INT DEFAULT NULL COMMENT 'chunk索引',
    chunk_text TEXT COMMENT 'chunk文本片段',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- 索引
    INDEX idx_document_id (document_id),
    INDEX idx_page_number (page_number),
    INDEX idx_chunk_index (chunk_index),
    
    -- 外键约束
    FOREIGN KEY (document_id) REFERENCES document_nodes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档内容表';

-- =====================================================
-- 3. 向量化记录表（记录向量化处理状态）
-- =====================================================
CREATE TABLE IF NOT EXISTS vector_records (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    document_id BIGINT NOT NULL COMMENT '文档节点ID',
    content_id BIGINT NOT NULL COMMENT '文档内容ID',
    vector_id VARCHAR(100) COMMENT 'Milvus中的向量ID',
    embedding_model VARCHAR(100) COMMENT '使用的嵌入模型',
    vector_status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending' COMMENT '向量化状态',
    error_message TEXT COMMENT '错误信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- 索引
    INDEX idx_document_id (document_id),
    INDEX idx_content_id (content_id),
    INDEX idx_vector_status (vector_status),
    INDEX idx_vector_id (vector_id),
    
    -- 外键约束
    FOREIGN KEY (document_id) REFERENCES document_nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (content_id) REFERENCES document_contents(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='向量化记录表';

-- =====================================================
-- 4. 标签表
-- =====================================================
CREATE TABLE IF NOT EXISTS tags (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE COMMENT '标签名称',
    color VARCHAR(7) DEFAULT '#007bff' COMMENT '标签颜色（十六进制色值）',
    description TEXT COMMENT '标签描述',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_by VARCHAR(100) DEFAULT 'system' COMMENT '创建人',
    is_deleted TINYINT(1) DEFAULT 0 COMMENT '是否删除：0-未删除，1-已删除',
    
    -- 索引
    INDEX idx_name (name),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='标签表';

-- =====================================================
-- 5. 文档标签关联表
-- =====================================================
CREATE TABLE IF NOT EXISTS document_tags (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    document_id BIGINT NOT NULL COMMENT '文档节点ID',
    tag_id BIGINT NOT NULL COMMENT '标签ID',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100) DEFAULT 'system' COMMENT '创建人',
    
    -- 索引
    INDEX idx_document_id (document_id),
    INDEX idx_tag_id (tag_id),
    UNIQUE KEY uk_document_tag (document_id, tag_id),
    
    -- 外键约束
    FOREIGN KEY (document_id) REFERENCES document_nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档标签关联表';

-- =====================================================
-- 6. 系统配置表
-- =====================================================
CREATE TABLE IF NOT EXISTS system_configs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    config_key VARCHAR(100) NOT NULL UNIQUE COMMENT '配置键',
    config_value TEXT COMMENT '配置值',
    config_type VARCHAR(50) DEFAULT 'string' COMMENT '配置类型：string,int,float,json',
    description VARCHAR(255) COMMENT '配置描述',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- 索引
    INDEX idx_config_key (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置表';

-- =====================================================
-- 第二部分：插入默认数据
-- =====================================================

-- =====================================================
-- 7. 插入完整的系统配置数据
-- =====================================================
INSERT IGNORE INTO system_configs (config_key, config_value, config_type, description) VALUES 
-- 基础配置
('file_storage_path', 'uploads', 'string', '文件存储路径'),
('embedding_model', 'all-MiniLM-L6-v2', 'string', '文本嵌入模型'),
('chunk_size', '1000', 'int', '文本分块大小'),
('chunk_overlap', '200', 'int', '文本分块重叠大小'),
('milvus_host', '192.168.16.199', 'string', 'Milvus服务器地址'),
('milvus_port', '19530', 'int', 'Milvus服务器端口'),
('max_file_size', '104857600', 'int', '最大文件大小（100MB）'),

-- 向量化和MinIO配置
('minio_endpoint', 'localhost:9000', 'string', 'MinIO服务器地址'),
('minio_access_key', 'minioadmin', 'string', 'MinIO访问密钥'),
('minio_secret_key', 'minioadmin', 'string', 'MinIO秘密密钥'),
('minio_bucket', 'document-storage', 'string', 'MinIO存储桶名称'),
('vectorization_enabled', 'true', 'string', '是否启用向量化功能'),
('default_chunk_size', '1000', 'int', '默认文本分块大小'),
('default_chunk_overlap', '200', 'int', '默认文本分块重叠大小');

-- =====================================================
-- 8. 插入默认标签数据
-- =====================================================
INSERT IGNORE INTO tags (name, color, description) VALUES 
('重要', '#dc3545', '重要文档标签'),
('紧急', '#fd7e14', '紧急处理文档'),
('合同', '#28a745', '合同类文档'),
('案例', '#17a2b8', '案例分析文档'),
('法规', '#6f42c1', '法规条文文档'),
('研究', '#20c997', '研究资料文档'),
('草稿', '#6c757d', '草稿文档'),
('已完成', '#007bff', '已完成的文档');

-- =====================================================
-- 第三部分：验证和状态检查
-- =====================================================

-- =====================================================
-- 9. 验证数据库设置
-- =====================================================

-- 显示所有表
SHOW TABLES;

-- 验证表的创建状态
SELECT 
    TABLE_NAME as '表名',
    TABLE_COMMENT as '表注释',
    CREATE_TIME as '创建时间'
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_SCHEMA = 'document_management' 
ORDER BY TABLE_NAME;

-- 显示系统配置
SELECT 
    config_key as '配置键', 
    config_value as '配置值', 
    config_type as '类型', 
    description as '描述' 
FROM system_configs 
ORDER BY config_key;

-- 显示默认标签
SELECT 
    id as '标签ID', 
    name as '标签名', 
    color as '颜色', 
    description as '描述' 
FROM tags 
WHERE is_deleted = 0 
ORDER BY id;

-- 验证向量化字段是否正确创建
SELECT 
    column_name as '字段名', 
    data_type as '数据类型', 
    is_nullable as '可空', 
    column_default as '默认值', 
    column_comment as '注释'
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE table_name = 'document_nodes' 
AND table_schema = 'document_management' 
AND column_name IN ('is_vectorized', 'vector_status', 'vectorized_at', 'minio_path', 'doc_metadata')
ORDER BY ordinal_position;

-- 检查索引创建情况
SELECT 
    TABLE_NAME as '表名',
    INDEX_NAME as '索引名',
    COLUMN_NAME as '列名',
    INDEX_TYPE as '索引类型'
FROM INFORMATION_SCHEMA.STATISTICS 
WHERE TABLE_SCHEMA = 'document_management' 
AND INDEX_NAME != 'PRIMARY'
ORDER BY TABLE_NAME, INDEX_NAME;

-- =====================================================
-- 脚本执行完成状态
-- =====================================================
SELECT 
    '数据库设置完成！' as '状态',
    NOW() as '完成时间',
    DATABASE() as '当前数据库',
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'document_management') as '表数量',
    (SELECT COUNT(*) FROM system_configs) as '配置项数量',
    (SELECT COUNT(*) FROM tags WHERE is_deleted = 0) as '标签数量'; 