-- =====================================================
-- 律师案件案宗文档管理系统 - 数据库建表脚本
-- =====================================================
-- 
-- 使用说明：
-- 1. 先创建数据库：CREATE DATABASE document_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- 2. 使用数据库：USE document_management;
-- 3. 执行此脚本：mysql -u root -p document_management < database/create_tables.sql
--
-- 或者直接在MySQL命令行中执行：
-- mysql -h 192.168.16.199 -u root -p
-- mysql> CREATE DATABASE document_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- mysql> USE document_management;
-- mysql> source /path/to/database/create_tables.sql;
--
-- =====================================================

-- 设置数据库
USE document_management;

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
-- 4. 系统配置表
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
-- 5. 插入默认配置数据
-- =====================================================
INSERT IGNORE INTO system_configs (config_key, config_value, config_type, description) VALUES 
('file_storage_path', 'uploads', 'string', '文件存储路径'),
('embedding_model', 'all-MiniLM-L6-v2', 'string', '文本嵌入模型'),
('chunk_size', '1000', 'int', '文本分块大小'),
('chunk_overlap', '200', 'int', '文本分块重叠大小'),
('milvus_host', '192.168.16.199', 'string', 'Milvus服务器地址'),
('milvus_port', '19530', 'int', 'Milvus服务器端口'),
('max_file_size', '104857600', 'int', '最大文件大小（100MB）');

-- =====================================================
-- 6. 验证表结构
-- =====================================================
-- 显示所有表
SHOW TABLES;

-- 查看表结构
-- DESCRIBE document_nodes;
-- DESCRIBE document_contents;
-- DESCRIBE vector_records;
-- DESCRIBE system_configs; 