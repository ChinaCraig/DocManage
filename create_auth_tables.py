#!/usr/bin/env python3
"""
直接通过Python创建认证系统数据库表
"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db

def create_auth_tables():
    """创建认证系统数据库表"""
    print("正在创建认证系统数据库表...")
    
    # 创建Flask应用上下文
    app = create_app()
    with app.app_context():
        try:
            # 创建所有数据库表
            db.create_all()
            print("✓ 所有数据库表创建成功")
            
            # 检查是否创建了认证相关表
            from app.models.user_models import User, UserPermission, UserSession, LoginLog
            from app.models.document_models import SystemConfig
            
            # 测试表是否可以查询
            User.query.count()
            print("✓ users 表创建成功")
            
            UserPermission.query.count()
            print("✓ user_permissions 表创建成功")
            
            UserSession.query.count()
            print("✓ user_sessions 表创建成功")
            
            LoginLog.query.count()
            print("✓ login_logs 表创建成功")
            
            SystemConfig.query.count()
            print("✓ system_configs 表创建成功")
            
            return True
            
        except Exception as e:
            print(f"创建数据库表时发生错误: {e}")
            return False

if __name__ == '__main__':
    success = create_auth_tables()
    if success:
        print("\n数据库表创建完成！现在可以运行 python3 setup_auth.py 来初始化认证系统。")
    else:
        print("\n数据库表创建失败！请检查数据库连接和配置。")
    
    sys.exit(0 if success else 1) 