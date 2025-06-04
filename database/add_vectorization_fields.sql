-- =====================================================
-- 律师案件案宗文档管理系统 - 向量化字段更新脚本
-- =====================================================
-- 
-- 使用说明：
-- 1. 连接到数据库：mysql -u root -p
-- 2. 使用数据库：USE document_management;
-- 3. 执行此脚本：source /path/to/database/add_vectorization_fields.sql
--
-- 或者直接执行：
-- mysql -h 192.168.16.199 -u root -p document_management < database/add_vectorization_fields.sql
--
-- =====================================================

-- 设置数据库
USE document_management;

-- =====================================================
-- 1. 添加向量化相关字段到 document_nodes 表
-- =====================================================

-- 检查并添加 is_vectorized 字段
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
     WHERE table_name = 'document_nodes' 
     AND table_schema = 'document_management' 
     AND column_name = 'is_vectorized') > 0,
    'SELECT "Column is_vectorized already exists"',
    'ALTER TABLE document_nodes ADD COLUMN is_vectorized TINYINT(1) DEFAULT 0 COMMENT "是否已向量化"'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 检查并添加 vector_status 字段
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
     WHERE table_name = 'document_nodes' 
     AND table_schema = 'document_management' 
     AND column_name = 'vector_status') > 0,
    'SELECT "Column vector_status already exists"',
    'ALTER TABLE document_nodes ADD COLUMN vector_status VARCHAR(50) DEFAULT "not_started" COMMENT "向量化状态"'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 检查并添加 vectorized_at 字段
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
     WHERE table_name = 'document_nodes' 
     AND table_schema = 'document_management' 
     AND column_name = 'vectorized_at') > 0,
    'SELECT "Column vectorized_at already exists"',
    'ALTER TABLE document_nodes ADD COLUMN vectorized_at TIMESTAMP NULL COMMENT "向量化完成时间"'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 检查并添加 minio_path 字段
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
     WHERE table_name = 'document_nodes' 
     AND table_schema = 'document_management' 
     AND column_name = 'minio_path') > 0,
    'SELECT "Column minio_path already exists"',
    'ALTER TABLE document_nodes ADD COLUMN minio_path VARCHAR(500) NULL COMMENT "MinIO存储路径"'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 检查并添加 doc_metadata 字段
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
     WHERE table_name = 'document_nodes' 
     AND table_schema = 'document_management' 
     AND column_name = 'doc_metadata') > 0,
    'SELECT "Column doc_metadata already exists"',
    'ALTER TABLE document_nodes ADD COLUMN doc_metadata JSON NULL COMMENT "元数据（JSON格式）"'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- =====================================================
-- 2. 添加索引以提高查询性能
-- =====================================================

-- 向量化状态索引 - 使用条件创建避免重复
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS 
     WHERE table_name = 'document_nodes' 
     AND table_schema = 'document_management' 
     AND index_name = 'idx_is_vectorized') > 0,
    'SELECT "Index idx_is_vectorized already exists"',
    'CREATE INDEX idx_is_vectorized ON document_nodes(is_vectorized)'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS 
     WHERE table_name = 'document_nodes' 
     AND table_schema = 'document_management' 
     AND index_name = 'idx_vector_status') > 0,
    'SELECT "Index idx_vector_status already exists"',
    'CREATE INDEX idx_vector_status ON document_nodes(vector_status)'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS 
     WHERE table_name = 'document_nodes' 
     AND table_schema = 'document_management' 
     AND index_name = 'idx_vectorized_at') > 0,
    'SELECT "Index idx_vectorized_at already exists"',
    'CREATE INDEX idx_vectorized_at ON document_nodes(vectorized_at)'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- =====================================================
-- 3. 添加向量化相关的系统配置
-- =====================================================

INSERT IGNORE INTO system_configs (config_key, config_value, config_type, description) VALUES 
('minio_endpoint', 'localhost:9000', 'string', 'MinIO服务器地址'),
('minio_access_key', 'minioadmin', 'string', 'MinIO访问密钥'),
('minio_secret_key', 'minioadmin', 'string', 'MinIO秘密密钥'),
('minio_bucket', 'document-storage', 'string', 'MinIO存储桶名称'),
('vectorization_enabled', 'true', 'string', '是否启用向量化功能'),
('default_chunk_size', '1000', 'int', '默认文本分块大小'),
('default_chunk_overlap', '200', 'int', '默认文本分块重叠大小');

-- =====================================================
-- 4. 验证更新结果
-- =====================================================

-- 显示 document_nodes 表结构
DESCRIBE document_nodes;

-- 显示新增的配置
SELECT * FROM system_configs WHERE config_key IN (
    'minio_endpoint', 'minio_access_key', 'minio_secret_key', 
    'minio_bucket', 'vectorization_enabled', 'default_chunk_size', 
    'default_chunk_overlap'
);

-- 显示向量化字段信息
SELECT 
    column_name, 
    data_type, 
    is_nullable, 
    column_default, 
    column_comment
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE table_name = 'document_nodes' 
AND table_schema = 'document_management' 
AND column_name IN ('is_vectorized', 'vector_status', 'vectorized_at', 'minio_path', 'doc_metadata')
ORDER BY ordinal_position;