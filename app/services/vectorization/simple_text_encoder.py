"""
简单文本编码器
在没有sentence-transformers的情况下提供基础的文本向量化功能
"""

import hashlib
import re
from typing import List, Optional
import numpy as np

class SimpleTextEncoder:
    """简单的文本编码器，生成基础的文本特征向量"""
    
    def __init__(self, dimension: int = 384):
        """初始化编码器"""
        self.dimension = dimension
        self.vocab = set()
        self._init_basic_vocab()
    
    def _init_basic_vocab(self):
        """初始化基础词汇"""
        # 添加一些常见的中文和英文词汇
        basic_words = [
            '文档', '管理', '系统', '向量', '搜索', '数据', '文件', '内容',
            'document', 'management', 'system', 'vector', 'search', 'data', 'file', 'content',
            '项目', '功能', '实现', '处理', '结果', '信息', '技术', '方法',
            'project', 'function', 'implement', 'process', 'result', 'information', 'technology', 'method'
        ]
        self.vocab.update(basic_words)
    
    def _extract_features(self, text: str) -> List[float]:
        """从文本中提取特征"""
        # 清理文本
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text.lower())
        words = text.split()
        
        if not words:
            return [0.1] * self.dimension  # 返回小的非零值而不是全零
        
        # 基础特征
        features = []
        
        # 1. 文本长度特征
        text_length = min(len(text) / 1000.0, 1.0)  # 归一化到0-1
        features.append(text_length)
        
        # 2. 词汇数量特征
        word_count = min(len(words) / 100.0, 1.0)  # 归一化到0-1
        features.append(word_count)
        
        # 3. 平均词长
        avg_word_length = sum(len(word) for word in words) / len(words) / 10.0
        features.append(min(avg_word_length, 1.0))
        
        # 4. 词汇哈希特征 (简单的词袋模型)
        vocab_hash_features = [0.0] * 50
        for word in words:
            if word in self.vocab:
                # 使用词汇的哈希值确定特征位置
                hash_val = int(hashlib.md5(word.encode()).hexdigest(), 16)
                idx = hash_val % 50
                vocab_hash_features[idx] += 0.1
        
        # 归一化词汇哈希特征
        max_val = max(vocab_hash_features) if max(vocab_hash_features) > 0 else 1.0
        vocab_hash_features = [f / max_val for f in vocab_hash_features]
        features.extend(vocab_hash_features)
        
        # 5. 字符级特征
        char_features = [0.0] * 26  # 英文字母频率
        chinese_features = [0.0] * 10  # 中文字符特征
        
        for char in text:
            if 'a' <= char <= 'z':
                char_features[ord(char) - ord('a')] += 0.1
            elif '\u4e00' <= char <= '\u9fff':  # 中文字符
                hash_val = int(hashlib.md5(char.encode()).hexdigest(), 16)
                idx = hash_val % 10
                chinese_features[idx] += 0.1
        
        # 归一化字符特征
        if sum(char_features) > 0:
            char_features = [f / sum(char_features) for f in char_features]
        if sum(chinese_features) > 0:
            chinese_features = [f / sum(chinese_features) for f in chinese_features]
        
        features.extend(char_features)
        features.extend(chinese_features)
        
        # 6. 文本哈希特征
        text_hash = hashlib.md5(text.encode()).digest()
        hash_features = []
        for byte in text_hash:
            hash_features.append(byte / 255.0)  # 归一化到0-1
        features.extend(hash_features)
        
        # 7. 填充到目标维度
        while len(features) < self.dimension:
            # 使用文本内容生成更多特征
            extra_hash = hashlib.sha256(f"{text}_{len(features)}".encode()).digest()
            for byte in extra_hash:
                if len(features) >= self.dimension:
                    break
                features.append((byte / 255.0) * 0.5 + 0.1)  # 0.1-0.6范围
        
        # 截断到目标维度
        features = features[:self.dimension]
        
        # 确保没有全零向量
        if all(f == 0 for f in features):
            features = [0.1 + i * 0.001 for i in range(self.dimension)]
        
        return features
    
    def encode(self, text: str, normalize_embeddings: bool = True) -> List[float]:
        """编码文本为向量"""
        if not text or not text.strip():
            # 返回随机小值而不是全零
            return [0.1 + i * 0.001 for i in range(self.dimension)]
        
        features = self._extract_features(text.strip())
        
        if normalize_embeddings:
            # L2归一化
            norm = sum(f * f for f in features) ** 0.5
            if norm > 0:
                features = [f / norm for f in features]
            else:
                features = [1.0 / (self.dimension ** 0.5)] * self.dimension
        
        return features
    
    def encode_batch(self, texts: List[str], normalize_embeddings: bool = True) -> List[List[float]]:
        """批量编码文本"""
        return [self.encode(text, normalize_embeddings) for text in texts] 