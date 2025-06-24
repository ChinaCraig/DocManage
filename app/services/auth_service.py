from flask import request, session, current_app, g
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from app import db
from app.models.user_models import User, UserSession, UserPermission, LoginLog
from app.models.document_models import SystemConfig
import re
import logging

logger = logging.getLogger(__name__)

class AuthService:
    """用户认证服务"""
    
    @staticmethod
    def login(username, password, remember_me=False):
        """用户登录"""
        try:
            # 获取用户
            user = User.query.filter(
                db.or_(User.username == username, User.email == username)
            ).first()
            
            ip_address = request.remote_addr
            user_agent = request.headers.get('User-Agent', '')
            
            # 用户不存在
            if not user:
                LoginLog.log_login_attempt(
                    username, ip_address, user_agent, 'failed', 
                    failure_reason='用户不存在'
                )
                db.session.commit()
                return {'success': False, 'message': '用户名或密码错误'}
            
            # 检查账户是否被锁定
            if user.is_account_locked():
                LoginLog.log_login_attempt(
                    username, ip_address, user_agent, 'locked', 
                    user_id=user.id, failure_reason='账户被锁定'
                )
                db.session.commit()
                return {'success': False, 'message': '账户已被锁定，请稍后再试'}
            
            # 检查账户是否激活
            if not user.is_active:
                LoginLog.log_login_attempt(
                    username, ip_address, user_agent, 'failed', 
                    user_id=user.id, failure_reason='账户未激活'
                )
                db.session.commit()
                return {'success': False, 'message': '账户未激活'}
            
            # 验证密码
            if not user.check_password(password):
                user.increment_login_attempts()
                LoginLog.log_login_attempt(
                    username, ip_address, user_agent, 'failed', 
                    user_id=user.id, failure_reason='密码错误'
                )
                db.session.commit()
                
                # 返回相应的错误信息
                if user.is_account_locked():
                    return {'success': False, 'message': '密码错误次数过多，账户已被锁定'}
                else:
                    remaining = AuthService._get_max_attempts() - user.login_attempts
                    return {'success': False, 'message': f'密码错误，还有{remaining}次尝试机会'}
            
            # 登录成功
            user.reset_login_attempts()
            
            # 创建会话
            user_session = UserSession.create_session(
                user.id, ip_address, user_agent, remember_me
            )
            db.session.add(user_session)
            
            # 记录登录日志
            LoginLog.log_login_attempt(
                username, ip_address, user_agent, 'success', user_id=user.id
            )
            
            db.session.commit()
            
            # 设置Flask会话
            session['user_id'] = user.id
            session['session_id'] = user_session.session_id
            session.permanent = remember_me
            
            logger.info(f"用户 {user.username} 登录成功，IP: {ip_address}")
            
            return {
                'success': True, 
                'message': '登录成功',
                'user': user.to_dict(),
                'session_id': user_session.session_id
            }
            
        except Exception as e:
            logger.error(f"登录过程中发生错误: {e}")
            db.session.rollback()
            return {'success': False, 'message': '登录失败，请稍后重试'}
    
    @staticmethod
    def logout(session_id=None):
        """用户登出"""
        try:
            # 获取会话ID
            if not session_id:
                session_id = session.get('session_id')
            
            if session_id:
                # 删除数据库中的会话
                user_session = UserSession.query.filter_by(session_id=session_id).first()
                if user_session:
                    user_session.is_active = False
                    db.session.commit()
                    logger.info(f"用户会话 {session_id} 已注销")
            
            # 清除Flask会话
            session.clear()
            
            return {'success': True, 'message': '登出成功'}
            
        except Exception as e:
            logger.error(f"登出过程中发生错误: {e}")
            return {'success': False, 'message': '登出失败'}
    
    @staticmethod
    def register(username, email, password, real_name=None, **kwargs):
        """用户注册"""
        try:
            # 验证输入
            validation = AuthService._validate_registration_data(username, email, password)
            if not validation['valid']:
                return {'success': False, 'message': validation['message']}
            
            # 检查用户名和邮箱是否已存在
            existing_user = User.query.filter(
                db.or_(User.username == username, User.email == email)
            ).first()
            
            if existing_user:
                if existing_user.username == username:
                    return {'success': False, 'message': '用户名已存在'}
                else:
                    return {'success': False, 'message': '邮箱已被注册'}
            
            # 创建新用户
            user = User(
                username=username,
                email=email,
                real_name=real_name,
                phone=kwargs.get('phone'),
                department=kwargs.get('department'),
                position=kwargs.get('position')
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.flush()  # 获取用户ID
            
            # 创建默认权限
            permissions = UserPermission(user_id=user.id)
            db.session.add(permissions)
            
            db.session.commit()
            
            logger.info(f"新用户注册成功: {username}")
            
            return {
                'success': True, 
                'message': '注册成功',
                'user': user.to_dict()
            }
            
        except Exception as e:
            logger.error(f"注册过程中发生错误: {e}")
            db.session.rollback()
            return {'success': False, 'message': '注册失败，请稍后重试'}
    
    @staticmethod
    def get_current_user():
        """获取当前登录用户"""
        user_id = session.get('user_id')
        session_id = session.get('session_id')
        
        if not user_id or not session_id:
            return None
        
        # 验证会话
        user_session = UserSession.query.filter_by(
            session_id=session_id,
            user_id=user_id,
            is_active=True
        ).first()
        
        if not user_session or user_session.is_expired():
            # 会话无效或过期，清除Flask会话
            session.clear()
            return None
        
        # 获取用户信息
        user = User.query.get(user_id)
        if not user or not user.is_active:
            session.clear()
            return None
        
        # 更新会话活跃时间
        user_session.updated_at = datetime.utcnow()
        db.session.commit()
        
        return user
    
    @staticmethod
    def require_auth():
        """检查用户是否已登录（装饰器使用）"""
        current_user = AuthService.get_current_user()
        if not current_user:
            return {'success': False, 'message': '请先登录', 'require_login': True}
        
        # 将用户信息存储到g对象中，供其他地方使用
        g.current_user = current_user
        return {'success': True, 'user': current_user}
    
    @staticmethod
    def require_permission(permission_name):
        """检查用户权限"""
        auth_result = AuthService.require_auth()
        if not auth_result['success']:
            return auth_result
        
        user = g.current_user
        if not user.has_permission(permission_name):
            return {'success': False, 'message': '权限不足'}
        
        return {'success': True, 'user': user}
    
    @staticmethod
    def change_password(user_id, old_password, new_password):
        """修改密码"""
        try:
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'message': '用户不存在'}
            
            # 验证旧密码
            if not user.check_password(old_password):
                return {'success': False, 'message': '原密码错误'}
            
            # 验证新密码格式
            if not AuthService._validate_password(new_password):
                min_length = AuthService._get_password_min_length()
                return {'success': False, 'message': f'密码长度至少{min_length}位'}
            
            # 设置新密码
            user.set_password(new_password)
            db.session.commit()
            
            logger.info(f"用户 {user.username} 修改密码成功")
            
            return {'success': True, 'message': '密码修改成功'}
            
        except Exception as e:
            logger.error(f"修改密码过程中发生错误: {e}")
            db.session.rollback()
            return {'success': False, 'message': '密码修改失败'}
    
    @staticmethod
    def reset_password(user_id, new_password):
        """重置密码（管理员功能）"""
        try:
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'message': '用户不存在'}
            
            # 验证密码格式
            if not AuthService._validate_password(new_password):
                min_length = AuthService._get_password_min_length()
                return {'success': False, 'message': f'密码长度至少{min_length}位'}
            
            # 设置新密码
            user.set_password(new_password)
            user.unlock_account()  # 解锁账户
            db.session.commit()
            
            logger.info(f"管理员重置用户 {user.username} 的密码")
            
            return {'success': True, 'message': '密码重置成功'}
            
        except Exception as e:
            logger.error(f"重置密码过程中发生错误: {e}")
            db.session.rollback()
            return {'success': False, 'message': '密码重置失败'}
    
    @staticmethod
    def _validate_registration_data(username, email, password):
        """验证注册数据"""
        # 验证用户名
        if not username or len(username) < 3 or len(username) > 50:
            return {'valid': False, 'message': '用户名长度必须在3-50个字符之间'}
        
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            return {'valid': False, 'message': '用户名只能包含字母、数字和下划线'}
        
        # 验证邮箱
        if not email or not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            return {'valid': False, 'message': '邮箱格式不正确'}
        
        # 验证密码
        if not AuthService._validate_password(password):
            min_length = AuthService._get_password_min_length()
            return {'valid': False, 'message': f'密码长度至少{min_length}位'}
        
        return {'valid': True}
    
    @staticmethod
    def _validate_password(password):
        """验证密码格式"""
        min_length = AuthService._get_password_min_length()
        return password and len(password) >= min_length
    
    @staticmethod
    def _get_password_min_length():
        """获取密码最小长度配置"""
        try:
            config = SystemConfig.get_config('password_min_length', '6')
            return int(config)
        except:
            return 6
    
    @staticmethod
    def _get_max_attempts():
        """获取最大登录尝试次数"""
        try:
            config = SystemConfig.get_config('max_login_attempts', '5')
            return int(config)
        except:
            return 5
    
    @staticmethod
    def cleanup_expired_sessions():
        """清理过期会话"""
        try:
            expired_sessions = UserSession.query.filter(
                UserSession.expires_at < datetime.utcnow()
            ).all()
            
            for session_obj in expired_sessions:
                session_obj.is_active = False
            
            db.session.commit()
            logger.info(f"清理了 {len(expired_sessions)} 个过期会话")
            
        except Exception as e:
            logger.error(f"清理过期会话时发生错误: {e}")
            db.session.rollback()
    
    @staticmethod
    def is_auth_enabled():
        """检查是否启用了用户认证"""
        try:
            # 从数据库获取配置，默认为true（启用认证）以确保安全
            config = SystemConfig.get_config('auth_enabled', 'true')
            return config.lower() == 'true'
        except:
            # 如果无法读取配置，默认启用认证以确保系统安全
            return True 