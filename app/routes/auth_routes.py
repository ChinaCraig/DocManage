from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from app.services.auth_service import AuthService
from app.models.user_models import User, LoginLog
from app.models.document_models import SystemConfig
from app import db
from functools import wraps
import logging

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

def auth_required(f):
    """认证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AuthService.is_auth_enabled():
            return f(*args, **kwargs)
        
        auth_result = AuthService.require_auth()
        if not auth_result['success']:
            return jsonify({
                'success': False,
                'message': auth_result['message'],
                'require_login': auth_result.get('require_login', False)
            }), 401
        
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission_name):
    """权限检查装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not AuthService.is_auth_enabled():
                return f(*args, **kwargs)
            
            perm_result = AuthService.require_permission(permission_name)
            if not perm_result['success']:
                return jsonify({
                    'success': False,
                    'message': perm_result['message']
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录"""
    try:
        data = request.get_json()
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        remember_me = data.get('remember_me', False)
        
        if not username or not password:
            return jsonify({
                'success': False,
                'message': '用户名和密码不能为空'
            }), 400
        
        result = AuthService.login(username, password, remember_me)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"登录接口错误: {e}")
        return jsonify({
            'success': False,
            'message': '登录失败，请稍后重试'
        }), 500

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """用户登出"""
    try:
        result = AuthService.logout()
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"登出接口错误: {e}")
        return jsonify({
            'success': False,
            'message': '登出失败'
        }), 500

@auth_bp.route('/register', methods=['POST'])
def register():
    """用户注册"""
    try:
        # 检查是否允许注册
        allow_register = SystemConfig.get_config('allow_register', 'false')
        if allow_register.lower() != 'true':
            return jsonify({
                'success': False,
                'message': '系统不允许注册新用户'
            }), 403
        
        data = request.get_json()
        
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        real_name = data.get('real_name', '').strip()
        
        if not all([username, email, password]):
            return jsonify({
                'success': False,
                'message': '用户名、邮箱和密码不能为空'
            }), 400
        
        result = AuthService.register(
            username=username,
            email=email,
            password=password,
            real_name=real_name,
            phone=data.get('phone', '').strip(),
            department=data.get('department', '').strip(),
            position=data.get('position', '').strip()
        )
        
        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"注册接口错误: {e}")
        return jsonify({
            'success': False,
            'message': '注册失败，请稍后重试'
        }), 500

@auth_bp.route('/current-user', methods=['GET'])
@auth_required
def get_current_user():
    """获取当前用户信息"""
    try:
        user = AuthService.get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '未登录'
            }), 401
        
        return jsonify({
            'success': True,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"获取当前用户信息错误: {e}")
        return jsonify({
            'success': False,
            'message': '获取用户信息失败'
        }), 500

@auth_bp.route('/change-password', methods=['POST'])
@auth_required
def change_password():
    """修改密码"""
    try:
        data = request.get_json()
        
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')
        
        if not old_password or not new_password:
            return jsonify({
                'success': False,
                'message': '原密码和新密码不能为空'
            }), 400
        
        user = AuthService.get_current_user()
        if not user:
            return jsonify({
                'success': False,
                'message': '未登录'
            }), 401
        
        result = AuthService.change_password(user.id, old_password, new_password)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"修改密码接口错误: {e}")
        return jsonify({
            'success': False,
            'message': '密码修改失败'
        }), 500

@auth_bp.route('/check-auth', methods=['GET'])
def check_auth():
    """检查认证状态"""
    try:
        # 检查是否启用认证
        auth_enabled = AuthService.is_auth_enabled()
        
        if not auth_enabled:
            return jsonify({
                'success': True,
                'auth_enabled': False,
                'message': '认证未启用'
            }), 200
        
        # 检查当前用户
        user = AuthService.get_current_user()
        
        if user:
            return jsonify({
                'success': True,
                'auth_enabled': True,
                'authenticated': True,
                'user': user.to_dict()
            }), 200
        else:
            return jsonify({
                'success': True,
                'auth_enabled': True,
                'authenticated': False,
                'message': '未登录'
            }), 200
            
    except Exception as e:
        logger.error(f"检查认证状态错误: {e}")
        return jsonify({
            'success': False,
            'message': '检查认证状态失败'
        }), 500

# 管理员路由
@auth_bp.route('/admin/users', methods=['GET'])
@permission_required('can_manage_users')
def list_users():
    """获取用户列表（管理员）"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        users = User.query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'success': True,
            'users': [user.to_dict(include_sensitive=True) for user in users.items],
            'pagination': {
                'page': users.page,
                'pages': users.pages,
                'per_page': users.per_page,
                'total': users.total
            }
        }), 200
        
    except Exception as e:
        logger.error(f"获取用户列表错误: {e}")
        return jsonify({
            'success': False,
            'message': '获取用户列表失败'
        }), 500

@auth_bp.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
@permission_required('can_manage_users')
def reset_user_password(user_id):
    """重置用户密码（管理员）"""
    try:
        data = request.get_json()
        new_password = data.get('new_password', '')
        
        if not new_password:
            return jsonify({
                'success': False,
                'message': '新密码不能为空'
            }), 400
        
        result = AuthService.reset_password(user_id, new_password)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"重置用户密码错误: {e}")
        return jsonify({
            'success': False,
            'message': '重置密码失败'
        }), 500

@auth_bp.route('/admin/users/<int:user_id>/toggle-status', methods=['POST'])
@permission_required('can_manage_users')
def toggle_user_status(user_id):
    """切换用户状态（启用/禁用）"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'success': False,
                'message': '用户不存在'
            }), 404
        
        user.is_active = not user.is_active
        db.session.commit()
        
        status = '启用' if user.is_active else '禁用'
        logger.info(f"管理员{status}用户: {user.username}")
        
        return jsonify({
            'success': True,
            'message': f'用户已{status}',
            'user': user.to_dict(include_sensitive=True)
        }), 200
        
    except Exception as e:
        logger.error(f"切换用户状态错误: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': '操作失败'
        }), 500

@auth_bp.route('/admin/login-logs', methods=['GET'])
@permission_required('can_view_logs')
def get_login_logs():
    """获取登录日志（管理员）"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        logs = LoginLog.query.order_by(LoginLog.login_time.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'success': True,
            'logs': [log.to_dict() for log in logs.items],
            'pagination': {
                'page': logs.page,
                'pages': logs.pages,
                'per_page': logs.per_page,
                'total': logs.total
            }
        }), 200
        
    except Exception as e:
        logger.error(f"获取登录日志错误: {e}")
        return jsonify({
            'success': False,
            'message': '获取登录日志失败'
        }), 500

# 页面路由
@auth_bp.route('/login-page')
def login_page():
    """登录页面"""
    return render_template('login.html')

@auth_bp.route('/register-page')
def register_page():
    """注册页面"""
    allow_register = SystemConfig.get_config('allow_register', 'false')
    if allow_register.lower() != 'true':
        return redirect(url_for('auth.login_page'))
    
    return render_template('register.html')
 