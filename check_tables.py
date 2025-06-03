#!/usr/bin/env python3
"""
检查数据库表结构的脚本
"""
import pymysql

def check_tables():
    """检查数据库表"""
    try:
        # 连接数据库
        conn = pymysql.connect(
            host='192.168.16.108',
            port=3306,
            user='root',
            password='19900114xin',
            database='document_management',
            charset='utf8mb4'
        )
        
        cursor = conn.cursor()
        
        # 检查所有表
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"数据库中的表: {[table[0] for table in tables]}")
        
        # 检查我们需要的表
        required_tables = ['document_nodes', 'document_contents', 'vector_records', 'system_configs']
        
        for table in required_tables:
            try:
                cursor.execute(f"DESCRIBE {table}")
                print(f"\n{table} 表存在")
            except pymysql.err.ProgrammingError:
                print(f"\n{table} 表不存在，需要创建")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"检查表失败: {e}")

if __name__ == "__main__":
    check_tables() 