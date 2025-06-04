#!/usr/bin/env python3
"""
Milvus设置和测试脚本
用于配置和验证向量数据库连接
"""
import os
import sys
import socket
from dotenv import load_dotenv
from pathlib import Path

# 加载环境变量
load_dotenv("config.env")

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.vectorization import VectorServiceAdapter

def test_network_connection(host, port):
    """测试网络连接"""
    try:
        print(f"正在测试网络连接到 {host}:{port}...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print("✅ 网络连接成功!")
            return True
        else:
            print(f"❌ 网络连接失败，端口 {port} 不可达")
            return False
    except Exception as e:
        print(f"❌ 网络连接测试失败: {e}")
        return False

def test_milvus_dependencies():
    """测试Milvus相关依赖"""
    dependencies = {
        'pymilvus': '用于连接Milvus向量数据库',
        'sentence_transformers': '用于文本向量化'
    }
    
    results = {}
    
    for package, description in dependencies.items():
        try:
            exec(f"import {package}")
            print(f"✅ {package}: 已安装 ({description})")
            results[package] = True
        except ImportError:
            print(f"❌ {package}: 未安装 ({description})")
            results[package] = False
    
    return results

def setup_vector_service():
    """设置向量服务"""
    print("\n=== 设置向量服务 ===")
    
    # 获取配置
    host = os.getenv('MILVUS_HOST', 'localhost')
    port = int(os.getenv('MILVUS_PORT', '19530'))
    model_name = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
    
    print(f"Milvus服务器: {host}:{port}")
    print(f"嵌入模型: {model_name}")
    
    # 初始化向量服务
    vector_service = VectorServiceAdapter(
        milvus_host=host,
        milvus_port=port,
        embedding_model=model_name
    )
    
    if vector_service.initialize(host, port, model_name):
        print("✅ 向量服务初始化成功")
        
        # 创建集合
        if vector_service.create_collection():
            print("✅ 向量集合创建成功")
            
            # 获取集合统计
            stats = vector_service.get_collection_stats()
            print(f"📊 集合统计: {stats}")
            
            return True
        else:
            print("❌ 向量集合创建失败")
            return False
    else:
        print("❌ 向量服务初始化失败")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("🔧 Milvus向量数据库设置和测试")
    print("=" * 60)
    
    # 检查配置
    host = os.getenv('MILVUS_HOST', 'localhost')
    port = int(os.getenv('MILVUS_PORT', '19530'))
    enabled = os.getenv('ENABLE_VECTOR_SERVICE', 'false').lower() == 'true'
    
    print(f"📋 配置信息:")
    print(f"   Milvus地址: {host}:{port}")
    print(f"   向量服务启用: {enabled}")
    print(f"   嵌入模型: {os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')}")
    
    if not enabled:
        print("\n⚠️  向量服务在配置中被禁用")
        print("要启用向量服务，请在config.env中设置: ENABLE_VECTOR_SERVICE=true")
        return False
    
    # 测试网络连接
    print(f"\n1. 测试网络连接...")
    network_ok = test_network_connection(host, port)
    
    if not network_ok:
        print("\n❌ 网络连接失败!")
        print("请检查:")
        print("1. Milvus服务是否在指定地址运行")
        print("2. 防火墙设置")
        print("3. 网络连通性")
        return False
    
    # 测试依赖
    print(f"\n2. 检查Python依赖...")
    deps = test_milvus_dependencies()
    
    missing_deps = [pkg for pkg, installed in deps.items() if not installed]
    if missing_deps:
        print(f"\n❌ 缺少依赖包: {', '.join(missing_deps)}")
        print("请安装缺少的包:")
        for pkg in missing_deps:
            print(f"   pip install {pkg}")
        return False
    
    # 初始化服务
    print(f"\n3. 初始化向量服务...")
    service_ok = setup_vector_service()
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总:")
    print(f"网络连接: {'✅ 正常' if network_ok else '❌ 失败'}")
    print(f"Python依赖: {'✅ 正常' if not missing_deps else '❌ 缺失'}")
    print(f"向量服务: {'✅ 正常' if service_ok else '❌ 失败'}")
    
    if network_ok and not missing_deps and service_ok:
        print("\n🎉 Milvus向量数据库配置完成!")
        print("现在可以使用文档向量化和语义搜索功能了。")
        return True
    else:
        print("\n⚠️  配置过程中遇到问题，请按照上述提示解决。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 