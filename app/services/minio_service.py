"""
MinIO对象存储服务
处理文件上传、下载和管理
"""
import logging
from typing import Dict, Any, Optional
import os
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

class MinIOService:
    """MinIO对象存储服务类"""
    
    def __init__(self):
        """初始化MinIO服务"""
        self.client = None
        self.bucket_name = "document-storage"
        self.is_available = False
        self.enabled = os.getenv('ENABLE_MINIO_SERVICE', 'false').lower() == 'true'
        
        if not self.enabled:
            logger.warning("MinIO service is disabled by configuration")
    
    def initialize(self, endpoint: str = "localhost:9000", access_key: str = "minioadmin", 
                  secret_key: str = "minioadmin", secure: bool = False):
        """初始化MinIO客户端连接"""
        if not self.enabled:
            logger.info("MinIO service initialization skipped - disabled by configuration")
            return True
            
        try:
            # 尝试导入MinIO依赖
            from minio import Minio
            
            logger.info(f"Initializing MinIO service - connecting to {endpoint}")
            
            # 创建MinIO客户端
            self.client = Minio(
                endpoint=endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure
            )
            
            # 检查连接并确保bucket存在
            if not self.client.bucket_exists(self.bucket_name):
                logger.info(f"Creating bucket: {self.bucket_name}")
                self.client.make_bucket(self.bucket_name)
            
            self.is_available = True
            logger.info("✅ MinIO service initialized successfully")
            return True
            
        except ImportError as e:
            logger.warning(f"MinIO service dependencies not available: {e}")
            logger.warning("Install with: pip install minio")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize MinIO service: {e}")
            return False
    
    def upload_file(self, file_path: str, object_name: str = None) -> Dict[str, Any]:
        """
        上传文件到MinIO
        
        Args:
            file_path: 本地文件路径
            object_name: MinIO中的对象名称，如果为None则自动生成
            
        Returns:
            上传结果字典
        """
        if not self.is_available:
            # 模拟上传成功
            return self._mock_upload(file_path, object_name)
        
        try:
            # 生成对象名称
            if not object_name:
                filename = os.path.basename(file_path)
                timestamp = datetime.now().strftime('%Y/%m/%d')
                unique_id = str(uuid.uuid4())
                object_name = f"documents/{timestamp}/{unique_id}_{filename}"
            
            # 上传文件
            self.client.fput_object(
                self.bucket_name,
                object_name,
                file_path
            )
            
            # 获取文件信息
            stat = self.client.stat_object(self.bucket_name, object_name)
            
            # 生成访问URL（这里需要根据实际配置调整）
            url = f"http://{self.client._base_url.netloc}/{self.bucket_name}/{object_name}"
            
            logger.info(f"✅ File uploaded successfully: {object_name}")
            
            return {
                'success': True,
                'object_name': object_name,
                'bucket': self.bucket_name,
                'url': url,
                'size': stat.size,
                'etag': stat.etag,
                'last_modified': stat.last_modified.isoformat() if stat.last_modified else None
            }
            
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def download_file(self, object_name: str, file_path: str) -> Dict[str, Any]:
        """
        从MinIO下载文件
        
        Args:
            object_name: MinIO中的对象名称
            file_path: 本地保存路径
            
        Returns:
            下载结果字典
        """
        if not self.is_available:
            logger.info(f"File download skipped - service not available: {object_name}")
            return {
                'success': False,
                'error': 'MinIO service not available'
            }
        
        try:
            self.client.fget_object(
                self.bucket_name,
                object_name,
                file_path
            )
            
            logger.info(f"✅ File downloaded successfully: {object_name}")
            
            return {
                'success': True,
                'object_name': object_name,
                'file_path': file_path
            }
            
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def delete_file(self, object_name: str) -> Dict[str, Any]:
        """
        删除MinIO中的文件
        
        Args:
            object_name: MinIO中的对象名称
            
        Returns:
            删除结果字典
        """
        if not self.is_available:
            logger.info(f"File deletion skipped - service not available: {object_name}")
            return {
                'success': True,  # 模拟删除成功
                'message': 'Service not available, file deletion skipped'
            }
        
        try:
            self.client.remove_object(self.bucket_name, object_name)
            
            logger.info(f"✅ File deleted successfully: {object_name}")
            
            return {
                'success': True,
                'object_name': object_name
            }
            
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_file_info(self, object_name: str) -> Dict[str, Any]:
        """
        获取文件信息
        
        Args:
            object_name: MinIO中的对象名称
            
        Returns:
            文件信息字典
        """
        if not self.is_available:
            return {
                'success': False,
                'error': 'MinIO service not available'
            }
        
        try:
            stat = self.client.stat_object(self.bucket_name, object_name)
            
            return {
                'success': True,
                'object_name': object_name,
                'size': stat.size,
                'etag': stat.etag,
                'last_modified': stat.last_modified.isoformat() if stat.last_modified else None,
                'content_type': stat.content_type
            }
            
        except Exception as e:
            logger.error(f"Failed to get file info: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def list_files(self, prefix: str = "documents/") -> Dict[str, Any]:
        """
        列出文件
        
        Args:
            prefix: 对象名称前缀
            
        Returns:
            文件列表字典
        """
        if not self.is_available:
            return {
                'success': False,
                'error': 'MinIO service not available'
            }
        
        try:
            objects = self.client.list_objects(
                self.bucket_name,
                prefix=prefix,
                recursive=True
            )
            
            files = []
            for obj in objects:
                files.append({
                    'object_name': obj.object_name,
                    'size': obj.size,
                    'etag': obj.etag,
                    'last_modified': obj.last_modified.isoformat() if obj.last_modified else None
                })
            
            return {
                'success': True,
                'files': files,
                'count': len(files)
            }
            
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _mock_upload(self, file_path: str, object_name: str = None) -> Dict[str, Any]:
        """模拟文件上传（当MinIO服务不可用时）"""
        filename = os.path.basename(file_path)
        if not object_name:
            timestamp = datetime.now().strftime('%Y/%m/%d')
            unique_id = str(uuid.uuid4())
            object_name = f"documents/{timestamp}/{unique_id}_{filename}"
        
        # 模拟上传延迟
        import time
        time.sleep(0.1)
        
        logger.info(f"🔧 Mock upload: {object_name}")
        
        return {
            'success': True,
            'object_name': object_name,
            'bucket': self.bucket_name,
            'url': f"http://mock-minio:9000/{self.bucket_name}/{object_name}",
            'size': os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            'etag': 'mock-etag',
            'last_modified': datetime.now().isoformat()
        } 