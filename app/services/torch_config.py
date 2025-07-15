"""
Torch配置模块
专门用于解决torch DataLoader pin_memory警告问题
"""
import os
import warnings
import logging

logger = logging.getLogger(__name__)

def configure_torch_for_cpu_gpu_compatibility():
    """配置torch以确保CPU和GPU环境都能正常工作"""
    try:
        import torch
        
        # 设置基本环境变量
        os.environ['TOKENIZERS_PARALLELISM'] = 'false'
        
        # 检查GPU可用性（包括CUDA和MPS）
        has_cuda = torch.cuda.is_available()
        has_mps = hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()
        has_gpu = has_cuda or has_mps
        
        if not has_gpu:
            # CPU环境配置
            os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:128'
            os.environ['PYTORCH_DISABLE_PIN_MEMORY'] = '1'
            
            # 修补torch DataLoader以禁用pin_memory
            _patch_dataloader_pin_memory()
            
            logger.info("🔧 Configured torch for CPU-only environment")
        else:
            # GPU环境配置
            if has_cuda:
                logger.info("🔧 Configured torch for CUDA GPU environment")
            elif has_mps:
                logger.info("🔧 Configured torch for MPS (Metal) GPU environment")
                # 为MPS设置特定配置
                os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
            
        # 通用设置
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        
        # 抑制相关警告
        warnings.filterwarnings('ignore', message='.*pin_memory.*')
        warnings.filterwarnings('ignore', message='.*device pinned memory.*')
        
        return True
        
    except ImportError:
        logger.warning("torch not available, skipping torch configuration")
        return False
    except Exception as e:
        logger.error(f"Failed to configure torch: {e}")
        return False

def _patch_dataloader_pin_memory():
    """修补DataLoader以禁用pin_memory"""
    try:
        import torch
        from torch.utils.data import DataLoader
        
        # 保存原始__init__方法
        original_init = DataLoader.__init__
        
        def patched_init(self, *args, **kwargs):
            # 在非CUDA环境中强制禁用pin_memory
            if not torch.cuda.is_available():
                kwargs['pin_memory'] = False
            return original_init(self, *args, **kwargs)
        
        # 应用补丁
        DataLoader.__init__ = patched_init
        
        logger.info("🔧 Patched DataLoader to disable pin_memory on CPU")
        
    except Exception as e:
        logger.error(f"Failed to patch DataLoader: {e}")

def setup_sentence_transformers_environment():
    """专门为sentence-transformers设置环境"""
    try:
        # 在导入sentence-transformers之前设置环境
        configure_torch_for_cpu_gpu_compatibility()
        
        # 设置sentence-transformers特定的环境变量
        os.environ['SENTENCE_TRANSFORMERS_HOME'] = os.path.expanduser('~/.cache/sentence_transformers')
        
        # 抑制sentence-transformers相关警告
        warnings.filterwarnings('ignore', category=UserWarning, module='sentence_transformers')
        
        logger.info("✅ sentence-transformers environment configured")
        
    except Exception as e:
        logger.error(f"Failed to setup sentence-transformers environment: {e}")

# 在模块加载时自动配置
configure_torch_for_cpu_gpu_compatibility() 