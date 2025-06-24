#!/usr/bin/env python3
"""
用户认证系统初始化脚本
用于创建数据库表、初始化默认管理员账户和配置认证系统
"""

import os
import sys
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.user_models import User, UserPermission
from app.models.document_models import SystemConfig

def check_database_tables():
    """检查数据库表是否存在"""
    print("正在检查数据库表...")
    
    try:
        # 检查关键表是否存在
        tables = [
            ('users', User),
            ('user_permissions', UserPermission),
            ('system_configs', SystemConfig)
        ]
        
        missing_tables = []
        for table_name, model_class in tables:
            try:
                model_class.query.count()
                print(f"✓ 表 {table_name} 存在")
            except Exception as e:
                print(f"✗ 表 {table_name} 不存在或有问题: {e}")
                missing_tables.append(table_name)
        
        if missing_tables:
            print(f"\n缺少以下表：{', '.join(missing_tables)}")
            print("请先运行数据库初始化SQL脚本：database/user_auth_setup.sql")
            return False
        
        print("所有必需的数据库表都存在 ✓")
        return True
        
    except Exception as e:
        print(f"检查数据库表时发生错误: {e}")
        return False

def create_default_admin():
    """创建默认管理员账户"""
    print("\n正在检查默认管理员账户...")
    
    # 检查是否已存在管理员
    admin = User.query.filter_by(username='admin').first()
    if admin:
        print("默认管理员账户已存在 ✓")
        return admin
    
    # 创建管理员账户
    try:
        admin = User(
            username='admin',
            email='admin@docmanage.local',
            real_name='系统管理员',
            is_admin=True,
            is_active=True
        )
        admin.set_password('admin123')
        
        db.session.add(admin)
        db.session.flush()  # 获取用户ID
        
        # 创建管理员权限（所有权限都启用）
        permissions = UserPermission(
            user_id=admin.id,
            can_upload=True,
            can_edit=True,
            can_delete=True,
            can_share=True,
            can_manage_users=True,
            can_view_logs=True,
            can_manage_config=True,
            can_manage_tags=True,
            can_use_llm=True,
            can_use_mcp=True,
            can_vectorize=True
        )
        
        db.session.add(permissions)
        db.session.commit()
        
        print("✓ 默认管理员账户创建成功")
        print("  用户名: admin")
        print("  密码: admin123")
        print("  邮箱: admin@docmanage.local")
        
        return admin
        
    except Exception as e:
        print(f"创建管理员账户时发生错误: {e}")
        db.session.rollback()
        return None

def setup_auth_config():
    """设置认证系统配置 - 强制启用认证"""
    print("\n正在配置认证系统...")
    
    configs = [
        ('auth_enabled', 'true', 'boolean', '是否启用用户认证'),
        ('session_timeout', '3600', 'int', '会话超时时间（秒）'),
        ('remember_me_days', '7', 'int', '"记住我"功能有效期（天）'),
        ('password_min_length', '6', 'int', '密码最小长度'),
        ('max_login_attempts', '5', 'int', '最大登录尝试次数'),
        ('account_lock_duration', '1800', 'int', '账户锁定时长（秒）'),
        ('allow_registration', 'false', 'boolean', '是否允许用户注册')
    ]
    
    try:
        for key, value, config_type, description in configs:
            # 检查配置是否已存在
            existing_config = SystemConfig.query.filter_by(config_key=key).first()
            if existing_config:
                # 如果是auth_enabled，强制设置为true
                if key == 'auth_enabled' and existing_config.config_value != 'true':
                    existing_config.config_value = 'true'
                    db.session.commit()
                    print(f"  ✓ 强制启用认证: {key} = true")
                else:
                    print(f"  配置 {key} 已存在: {existing_config.config_value}")
                continue
            
            # 创建新配置
            config = SystemConfig(
                config_key=key,
                config_value=value,
                config_type=config_type,
                description=description
            )
            db.session.add(config)
            print(f"  ✓ 创建配置 {key}: {value}")
        
        db.session.commit()
        print("认证系统配置完成 ✓")
        return True
        
    except Exception as e:
        print(f"配置认证系统时发生错误: {e}")
        db.session.rollback()
        return False

def create_custom_admin():
    """创建自定义管理员账户"""
    print("\n创建自定义管理员账户")
    print("请输入管理员信息（直接回车使用默认管理员）：")
    
    username = input("用户名 [admin]: ").strip() or 'admin'
    email = input("邮箱 [admin@docmanage.local]: ").strip() or 'admin@docmanage.local'
    real_name = input("真实姓名 [系统管理员]: ").strip() or '系统管理员'
    
    # 检查用户名是否已存在
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        print(f"用户名 {username} 已存在")
        return existing_user
    
    # 设置密码
    while True:
        password = input("密码（至少6位）: ").strip()
        if len(password) >= 6:
            break
        print("密码长度至少6位，请重新输入")
    
    try:
        # 创建用户
        user = User(
            username=username,
            email=email,
            real_name=real_name,
            is_admin=True,
            is_active=True
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.flush()
        
        # 创建权限
        permissions = UserPermission(
            user_id=user.id,
            can_upload=True,
            can_edit=True,
            can_delete=True,
            can_share=True,
            can_manage_users=True,
            can_view_logs=True,
            can_manage_config=True,
            can_manage_tags=True,
            can_use_llm=True,
            can_use_mcp=True,
            can_vectorize=True
        )
        
        db.session.add(permissions)
        db.session.commit()
        
        print(f"✓ 管理员账户 {username} 创建成功")
        return user
        
    except Exception as e:
        print(f"创建管理员账户时发生错误: {e}")
        db.session.rollback()
        return None

def enable_auth_immediately():
    """立即启用认证功能"""
    print("\n立即启用认证功能...")
    
    try:
        # 检查是否存在auth_enabled配置
        auth_config = SystemConfig.query.filter_by(config_key='auth_enabled').first()
        
        if auth_config:
            # 更新为true
            auth_config.config_value = 'true'
            print("✓ 更新认证配置为启用状态")
        else:
            # 创建新配置
            auth_config = SystemConfig(
                config_key='auth_enabled',
                config_value='true',
                config_type='boolean',
                description='是否启用用户认证'
            )
            db.session.add(auth_config)
            print("✓ 创建认证配置并设为启用状态")
        
        db.session.commit()
        return True
        
    except Exception as e:
        print(f"启用认证功能时发生错误: {e}")
        db.session.rollback()
        return False

def main():
    """主函数"""
    print("DocManage 用户认证系统初始化")
    print("=" * 50)
    
    # 创建Flask应用上下文
    app = create_app()
    with app.app_context():
        
        # 1. 检查数据库表
        if not check_database_tables():
            print("\n初始化失败：数据库表不完整")
            return False
        
        # 2. 立即启用认证功能
        if not enable_auth_immediately():
            print("\n警告：无法启用认证功能")
        
        # 3. 设置完整的认证配置
        if not setup_auth_config():
            print("\n初始化失败：无法配置认证系统")
            return False
        
        # 4. 创建默认管理员
        admin = create_default_admin()
        
        # 5. 询问是否创建自定义管理员
        while True:
            choice = input("\n是否创建自定义管理员账户？ (y/n) [n]: ").strip().lower()
            if choice in ['', 'n', 'no']:
                break
            elif choice in ['y', 'yes']:
                create_custom_admin()
                break
            else:
                print("请输入 y 或 n")
        
        print("\n" + "=" * 50)
        print("认证系统初始化完成！")
        print("✓ 认证功能已强制启用")
        print("✓ 现在访问系统需要登录")
        
        if admin:
            print("\n默认管理员账户信息：")
            print("  用户名: admin")
            print("  密码: admin123")
            print("  登录URL: http://localhost:5000/login")
            print("\n请重启应用程序以使认证生效！")
        
        return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1) 