-- =====================================================
-- 用户认证系统 - 数据库设置脚本
-- =====================================================
-- 添加到现有的document_management数据库中

USE document_management;

-- =====================================================
-- 1. 用户表
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    email VARCHAR(100) NOT NULL UNIQUE COMMENT '邮箱',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
    real_name VARCHAR(100) COMMENT '真实姓名',
    phone VARCHAR(20) COMMENT '手机号',
    department VARCHAR(100) COMMENT '部门',
    position VARCHAR(100) COMMENT '职位',
    
    -- 用户状态
    is_active TINYINT(1) DEFAULT 1 COMMENT '是否激活：0-禁用，1-正常',
    is_admin TINYINT(1) DEFAULT 0 COMMENT '是否管理员：0-普通用户，1-管理员',
    login_attempts INT DEFAULT 0 COMMENT '登录失败次数',
    locked_until TIMESTAMP NULL COMMENT '账户锁定到期时间',
    
    -- 时间字段
    last_login_at TIMESTAMP NULL COMMENT '最后登录时间',
    password_changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '密码修改时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- 索引
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_is_active (is_active),
    INDEX idx_last_login (last_login_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- =====================================================
-- 2. 用户会话表
-- =====================================================
CREATE TABLE IF NOT EXISTS user_sessions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id VARCHAR(255) NOT NULL UNIQUE COMMENT '会话ID',
    user_id BIGINT NOT NULL COMMENT '用户ID',
    ip_address VARCHAR(45) COMMENT 'IP地址',
    user_agent TEXT COMMENT 'User Agent',
    
    -- 会话状态
    is_active TINYINT(1) DEFAULT 1 COMMENT '是否活跃',
    expires_at TIMESTAMP NOT NULL COMMENT '过期时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- 索引
    INDEX idx_session_id (session_id),
    INDEX idx_user_id (user_id),
    INDEX idx_expires_at (expires_at),
    
    -- 外键约束
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户会话表';

-- =====================================================
-- 3. 用户权限表
-- =====================================================
CREATE TABLE IF NOT EXISTS user_permissions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL COMMENT '用户ID',
    
    -- 文档权限
    can_upload TINYINT(1) DEFAULT 1 COMMENT '可以上传文档',
    can_delete TINYINT(1) DEFAULT 0 COMMENT '可以删除文档',
    can_edit TINYINT(1) DEFAULT 1 COMMENT '可以编辑文档',
    can_share TINYINT(1) DEFAULT 1 COMMENT '可以分享文档',
    
    -- 系统权限
    can_manage_users TINYINT(1) DEFAULT 0 COMMENT '可以管理用户',
    can_manage_config TINYINT(1) DEFAULT 0 COMMENT '可以管理系统配置',
    can_view_logs TINYINT(1) DEFAULT 0 COMMENT '可以查看系统日志',
    can_manage_tags TINYINT(1) DEFAULT 1 COMMENT '可以管理标签',
    
    -- 高级功能权限
    can_use_llm TINYINT(1) DEFAULT 1 COMMENT '可以使用LLM功能',
    can_use_mcp TINYINT(1) DEFAULT 0 COMMENT '可以使用MCP工具',
    can_vectorize TINYINT(1) DEFAULT 1 COMMENT '可以向量化文档',
    
    -- 时间字段
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- 索引
    INDEX idx_user_id (user_id),
    
    -- 外键约束
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户权限表';

-- =====================================================
-- 4. 登录日志表
-- =====================================================
CREATE TABLE IF NOT EXISTS login_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT COMMENT '用户ID（登录失败时可能为空）',
    username VARCHAR(50) COMMENT '尝试登录的用户名',
    ip_address VARCHAR(45) COMMENT 'IP地址',
    user_agent TEXT COMMENT 'User Agent',
    
    -- 登录结果
    login_result ENUM('success', 'failed', 'locked') NOT NULL COMMENT '登录结果',
    failure_reason VARCHAR(100) COMMENT '失败原因',
    
    -- 时间字段
    login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 索引
    INDEX idx_user_id (user_id),
    INDEX idx_username (username),
    INDEX idx_login_time (login_time),
    INDEX idx_login_result (login_result),
    
    -- 外键约束
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='登录日志表';

-- =====================================================
-- 5. 更新现有表结构 - 添加创建人追踪
-- =====================================================
-- 为现有表添加user_id字段，关联到用户
ALTER TABLE document_nodes 
ADD COLUMN user_id BIGINT COMMENT '创建用户ID' AFTER created_by,
ADD INDEX idx_user_id (user_id);

-- 添加外键约束（可选，如果需要严格的数据完整性）
-- ALTER TABLE document_nodes 
-- ADD FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;

-- =====================================================
-- 6. 插入默认管理员用户
-- =====================================================
-- 密码：admin123 (使用werkzeug的密码哈希)
INSERT IGNORE INTO users (username, email, password_hash, real_name, is_admin, is_active) VALUES 
('admin', 'admin@docmanage.com', 'pbkdf2:sha256:260000$salt123$hash', '系统管理员', 1, 1);

-- 为管理员分配所有权限
INSERT IGNORE INTO user_permissions (
    user_id, can_upload, can_delete, can_edit, can_share,
    can_manage_users, can_manage_config, can_view_logs, can_manage_tags,
    can_use_llm, can_use_mcp, can_vectorize
) VALUES (
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1
);

-- =====================================================
-- 7. 插入系统配置
-- =====================================================
INSERT IGNORE INTO system_configs (config_key, config_value, config_type, description) VALUES 
-- 认证配置
('auth_enabled', 'true', 'string', '是否启用用户认证'),
('session_timeout', '3600', 'int', '会话超时时间（秒）'),
('max_login_attempts', '5', 'int', '最大登录尝试次数'),
('account_lock_duration', '1800', 'int', '账户锁定时长（秒）'),
('password_min_length', '6', 'int', '密码最小长度'),
('require_email_verification', 'false', 'string', '是否需要邮箱验证'),

-- 安全配置
('enable_remember_me', 'true', 'string', '是否启用记住我功能'),
('remember_me_duration', '604800', 'int', '记住我持续时间（秒，默认7天）'),
('enable_two_factor', 'false', 'string', '是否启用双因子认证'),
('force_password_change', 'false', 'string', '是否强制定期修改密码'); 