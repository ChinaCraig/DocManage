from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app
from app import db
import secrets

class User(db.Model):
    """用户模型"""
    __tablename__ = 'users'
    
    id = db.Column(db.BigInteger, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True, comment='用户名')
    email = db.Column(db.String(100), nullable=False, unique=True, comment='邮箱')
    password_hash = db.Column(db.String(255), nullable=False, comment='密码哈希')
    real_name = db.Column(db.String(100), comment='真实姓名')
    phone = db.Column(db.String(20), comment='手机号')
    department = db.Column(db.String(100), comment='部门')
    position = db.Column(db.String(100), comment='职位')
    
    # 用户状态
    is_active = db.Column(db.Boolean, default=True, comment='是否激活')
    is_admin = db.Column(db.Boolean, default=False, comment='是否管理员')
    login_attempts = db.Column(db.Integer, default=0, comment='登录失败次数')
    locked_until = db.Column(db.DateTime, nullable=True, comment='账户锁定到期时间')
    
    # 时间字段
    last_login_at = db.Column(db.DateTime, nullable=True, comment='最后登录时间')
    password_changed_at = db.Column(db.DateTime, default=datetime.utcnow, comment='密码修改时间')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    sessions = db.relationship('UserSession', backref='user', cascade='all, delete-orphan')
    permissions = db.relationship('UserPermission', backref='user', uselist=False, cascade='all, delete-orphan')
    login_logs = db.relationship('LoginLog', backref='user', cascade='all, delete-orphan')
    # 暂时注释掉文档关系，避免循环依赖问题
    # documents = db.relationship('DocumentNode', backref='creator', foreign_keys='DocumentNode.user_id')
    
    def set_password(self, password):
        """设置密码"""
        self.password_hash = generate_password_hash(password)
        self.password_changed_at = datetime.utcnow()
    
    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)
    
    def is_account_locked(self):
        """检查账户是否被锁定"""
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False
    
    def lock_account(self, duration_seconds=1800):
        """锁定账户"""
        self.locked_until = datetime.utcnow() + timedelta(seconds=duration_seconds)
        self.login_attempts = 0  # 重置尝试次数
    
    def unlock_account(self):
        """解锁账户"""
        self.locked_until = None
        self.login_attempts = 0
    
    def increment_login_attempts(self):
        """增加登录失败次数"""
        self.login_attempts += 1
        max_attempts = int(current_app.config.get('MAX_LOGIN_ATTEMPTS', 5))
        if self.login_attempts >= max_attempts:
            lock_duration = int(current_app.config.get('ACCOUNT_LOCK_DURATION', 1800))
            self.lock_account(lock_duration)
    
    def reset_login_attempts(self):
        """重置登录失败次数"""
        self.login_attempts = 0
        self.last_login_at = datetime.utcnow()
    
    def get_permissions(self):
        """获取用户权限"""
        if not self.permissions:
            # 创建默认权限
            self.permissions = UserPermission(user_id=self.id)
            db.session.add(self.permissions)
            db.session.commit()
        return self.permissions
    
    def has_permission(self, permission_name):
        """检查用户是否有特定权限"""
        if self.is_admin:
            return True
        permissions = self.get_permissions()
        return getattr(permissions, permission_name, False)
    
    def to_dict(self, include_sensitive=False):
        """转换为字典格式"""
        data = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'real_name': self.real_name,
            'phone': self.phone,
            'department': self.department,
            'position': self.position,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_sensitive:
            data.update({
                'login_attempts': self.login_attempts,
                'locked_until': self.locked_until.isoformat() if self.locked_until else None,
                'is_locked': self.is_account_locked()
            })
        
        return data

class UserSession(db.Model):
    """用户会话模型"""
    __tablename__ = 'user_sessions'
    
    id = db.Column(db.BigInteger, primary_key=True)
    session_id = db.Column(db.String(255), nullable=False, unique=True, comment='会话ID')
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.id'), nullable=False, comment='用户ID')
    ip_address = db.Column(db.String(45), comment='IP地址')
    user_agent = db.Column(db.Text, comment='User Agent')
    
    # 会话状态
    is_active = db.Column(db.Boolean, default=True, comment='是否活跃')
    expires_at = db.Column(db.DateTime, nullable=False, comment='过期时间')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def create_session(cls, user_id, ip_address=None, user_agent=None, remember_me=False):
        """创建新会话"""
        session_id = secrets.token_urlsafe(32)
        
        # 设置过期时间
        if remember_me:
            duration = int(current_app.config.get('REMEMBER_ME_DURATION', 604800))  # 7天
        else:
            duration = int(current_app.config.get('SESSION_TIMEOUT', 3600))  # 1小时
        
        expires_at = datetime.utcnow() + timedelta(seconds=duration)
        
        session = cls(
            session_id=session_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at
        )
        
        return session
    
    def is_expired(self):
        """检查会话是否过期"""
        return datetime.utcnow() > self.expires_at
    
    def extend_session(self, duration_seconds=3600):
        """延长会话时间"""
        self.expires_at = datetime.utcnow() + timedelta(seconds=duration_seconds)
        self.updated_at = datetime.utcnow()
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'ip_address': self.ip_address,
            'is_active': self.is_active,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_expired': self.is_expired()
        }

class UserPermission(db.Model):
    """用户权限模型"""
    __tablename__ = 'user_permissions'
    
    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.id'), nullable=False, comment='用户ID')
    
    # 文档权限
    can_upload = db.Column(db.Boolean, default=True, comment='可以上传文档')
    can_delete = db.Column(db.Boolean, default=False, comment='可以删除文档')
    can_edit = db.Column(db.Boolean, default=True, comment='可以编辑文档')
    can_share = db.Column(db.Boolean, default=True, comment='可以分享文档')
    
    # 系统权限
    can_manage_users = db.Column(db.Boolean, default=False, comment='可以管理用户')
    can_manage_config = db.Column(db.Boolean, default=False, comment='可以管理系统配置')
    can_view_logs = db.Column(db.Boolean, default=False, comment='可以查看系统日志')
    can_manage_tags = db.Column(db.Boolean, default=True, comment='可以管理标签')
    
    # 高级功能权限
    can_use_llm = db.Column(db.Boolean, default=True, comment='可以使用LLM功能')
    can_use_mcp = db.Column(db.Boolean, default=False, comment='可以使用MCP工具')
    can_vectorize = db.Column(db.Boolean, default=True, comment='可以向量化文档')
    
    # 时间字段
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'can_upload': self.can_upload,
            'can_delete': self.can_delete,
            'can_edit': self.can_edit,
            'can_share': self.can_share,
            'can_manage_users': self.can_manage_users,
            'can_manage_config': self.can_manage_config,
            'can_view_logs': self.can_view_logs,
            'can_manage_tags': self.can_manage_tags,
            'can_use_llm': self.can_use_llm,
            'can_use_mcp': self.can_use_mcp,
            'can_vectorize': self.can_vectorize,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class LoginLog(db.Model):
    """登录日志模型"""
    __tablename__ = 'login_logs'
    
    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey('users.id'), nullable=True, comment='用户ID')
    username = db.Column(db.String(50), comment='尝试登录的用户名')
    ip_address = db.Column(db.String(45), comment='IP地址')
    user_agent = db.Column(db.Text, comment='User Agent')
    
    # 登录结果
    login_result = db.Column(db.Enum('success', 'failed', 'locked'), nullable=False, comment='登录结果')
    failure_reason = db.Column(db.String(100), comment='失败原因')
    
    # 时间字段
    login_time = db.Column(db.DateTime, default=datetime.utcnow)
    
    @classmethod
    def log_login_attempt(cls, username, ip_address, user_agent, result, user_id=None, failure_reason=None):
        """记录登录尝试"""
        log = cls(
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            login_result=result,
            failure_reason=failure_reason
        )
        db.session.add(log)
        return log
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'ip_address': self.ip_address,
            'login_result': self.login_result,
            'failure_reason': self.failure_reason,
            'login_time': self.login_time.isoformat() if self.login_time else None
        } 