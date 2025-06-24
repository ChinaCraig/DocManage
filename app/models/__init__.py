# 导入所有模型，确保在应用启动时注册到SQLAlchemy中

from .document_models import (
    DocumentNode,
    DocumentContent, 
    VectorRecord,
    Tag,
    DocumentTag,
    SystemConfig
)

from .user_models import (
    User,
    UserSession,
    UserPermission,
    LoginLog
)

__all__ = [
    'DocumentNode',
    'DocumentContent',
    'VectorRecord', 
    'Tag',
    'DocumentTag',
    'SystemConfig',
    'User',
    'UserSession',
    'UserPermission',
    'LoginLog'
] 