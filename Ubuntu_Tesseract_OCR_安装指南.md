# Ubuntu Tesseract OCR 安装配置指南

## 概述

本文档详细说明如何在Ubuntu系统上安装和配置Tesseract OCR，解决DocManage项目中图像识别功能的依赖问题。

## 问题症状

当您在Ubuntu系统上运行项目时，可能会遇到以下错误：

```
2025-06-10 10:03:56,149 - app.services.image_recognition_service - ERROR - Tesseract OCR失败: tesseract is not installed or it's not in your PATH. See README file for more information.
```

这表明系统缺少Tesseract OCR引擎或PATH配置不正确。

## 安装步骤

### 1. 系统要求

- Ubuntu 18.04 或更高版本
- Python 3.7 或更高版本
- 具有sudo权限的用户账户

### 2. 快速安装脚本

创建安装脚本 `install_tesseract.sh`：

```bash
#!/bin/bash
# Ubuntu Tesseract OCR 完整安装脚本

set -e  # 遇到错误立即退出

echo "🚀 开始安装Tesseract OCR环境..."

# 1. 更新系统包
echo "📦 更新系统包..."
sudo apt-get update

# 2. 安装Tesseract OCR主程序
echo "🔤 安装Tesseract OCR主程序..."
sudo apt-get install -y tesseract-ocr

# 3. 安装中文语言包
echo "🇨🇳 安装中文语言包..."
sudo apt-get install -y tesseract-ocr-chi-sim  # 简体中文
sudo apt-get install -y tesseract-ocr-chi-tra  # 繁体中文

# 4. 安装其他常用语言包
echo "🌐 安装其他语言包..."
sudo apt-get install -y tesseract-ocr-eng      # 英文（通常默认安装）
sudo apt-get install -y tesseract-ocr-jpn      # 日文
sudo apt-get install -y tesseract-ocr-kor      # 韩文

# 5. 安装图像处理依赖
echo "🖼️ 安装图像处理依赖..."
sudo apt-get install -y libtesseract-dev
sudo apt-get install -y libleptonica-dev

# 6. 验证安装
echo "✅ 验证Tesseract安装..."
if command -v tesseract &> /dev/null; then
    echo "Tesseract版本: $(tesseract --version | head -1)"
    echo "可用语言: $(tesseract --list-langs | tr '\n' ' ')"
    echo "🎉 Tesseract OCR安装成功！"
else
    echo "❌ Tesseract安装失败，请检查错误信息"
    exit 1
fi

echo "✨ 安装完成！"
```

### 3. 执行安装

```bash
# 1. 保存上述脚本为文件
nano install_tesseract.sh

# 2. 给脚本执行权限
chmod +x install_tesseract.sh

# 3. 运行安装脚本
./install_tesseract.sh
```

### 4. 手动分步安装（可选）

如果脚本安装遇到问题，可以手动执行以下步骤：

```bash
# 更新包列表
sudo apt-get update

# 安装Tesseract主程序
sudo apt-get install -y tesseract-ocr

# 安装语言包
sudo apt-get install -y tesseract-ocr-chi-sim tesseract-ocr-chi-tra tesseract-ocr-eng

# 安装开发依赖
sudo apt-get install -y libtesseract-dev libleptonica-dev
```

## 环境配置

### 1. 设置环境变量

将以下内容添加到 `~/.bashrc` 或 `~/.profile`：

```bash
# Tesseract OCR配置
export TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata
export PATH=/usr/bin:$PATH
```

### 2. 重新加载环境变量

```bash
source ~/.bashrc
```

### 3. 项目环境配置

在项目的 `config.env` 文件中确保包含：

```bash
# OCR配置
TESSERACT_CMD=/usr/bin/tesseract
TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata
```

## 验证安装

### 1. 基本验证

```bash
# 检查tesseract命令
which tesseract

# 查看版本信息
tesseract --version

# 列出可用语言
tesseract --list-langs
```

期望输出示例：
```
tesseract 4.1.1
 leptonica-1.78.0
  libgif 5.1.4 : libjpeg 8d (libjpeg-turbo 2.0.3) : libpng 1.6.37 : libtiff 4.1.0 : zlib 1.2.11 : libwebp 0.6.1 : libopenjp2 2.3.1

List of available languages (5):
chi_sim
chi_tra
eng
jpn
kor
```

### 2. Python集成验证

创建测试脚本 `test_ocr.py`：

```python
#!/usr/bin/env python3
"""
测试Tesseract OCR功能
"""

import os
import sys

def test_tesseract():
    """测试Tesseract OCR功能"""
    try:
        import pytesseract
        from PIL import Image
        print("✅ 成功导入pytesseract和PIL")
        
        # 测试获取可用语言
        languages = pytesseract.get_languages()
        print(f"✅ 可用语言: {languages}")
        
        # 测试基本功能（需要有测试图片）
        print("✅ Tesseract OCR环境配置正确")
        return True
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("请确保已安装: pip install pytesseract Pillow")
        return False
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

if __name__ == "__main__":
    success = test_tesseract()
    sys.exit(0 if success else 1)
```

运行测试：
```bash
python3 test_ocr.py
```

### 3. 项目集成验证

启动项目并检查日志：

```bash
# 启动项目
python run.py

# 在另一个终端查看日志
tail -f app.log | grep -i tesseract
```

正常情况下应该看到：
```
INFO - Available OCR engines: tesseract, easyocr
INFO - Tesseract OCR 引擎可用
```

## 常见问题解决

### 1. 找不到tesseract命令

**症状：**
```
FileNotFoundError: [Errno 2] No such file or directory: 'tesseract'
```

**解决方案：**
```bash
# 确认tesseract安装位置
which tesseract

# 如果没有输出，重新安装
sudo apt-get install --reinstall tesseract-ocr

# 检查PATH环境变量
echo $PATH
```

### 2. 语言包缺失

**症状：**
```
TesseractError: (1, 'Error opening data file /usr/share/tesseract-ocr/4.00/tessdata/chi_sim.traineddata')
```

**解决方案：**
```bash
# 重新安装语言包
sudo apt-get install --reinstall tesseract-ocr-chi-sim

# 检查语言包文件
ls -la /usr/share/tesseract-ocr/4.00/tessdata/
```

### 3. 权限问题

**症状：**
```
PermissionError: [Errno 13] Permission denied
```

**解决方案：**
```bash
# 检查文件权限
ls -la /usr/bin/tesseract

# 如果需要，修复权限
sudo chmod +x /usr/bin/tesseract
```

### 4. Python绑定问题

**症状：**
```
ImportError: No module named 'pytesseract'
```

**解决方案：**
```bash
# 确保在正确的Python环境中安装
pip install pytesseract

# 如果使用虚拟环境
source venv/bin/activate
pip install pytesseract
```

## 性能优化建议

### 1. 语言包优化

只安装需要的语言包以减少内存使用：

```bash
# 只安装中英文
sudo apt-get install tesseract-ocr-chi-sim tesseract-ocr-eng

# 移除不需要的语言包
sudo apt-get remove tesseract-ocr-jpn tesseract-ocr-kor
```

### 2. OCR配置优化

在项目中配置OCR参数：

```python
# 在image_recognition_service.py中优化
pytesseract.image_to_string(
    image, 
    lang=lang_param,
    config='--oem 3 --psm 6'  # 优化OCR模式
)
```

## 备用方案

如果Tesseract安装仍有问题，项目支持以下备用OCR引擎：

### 1. EasyOCR

```bash
pip install easyocr
```

### 2. PaddleOCR

```bash
pip install paddleocr
```

项目会自动检测可用的OCR引擎并选择最佳方案。

## 支持与反馈

如果遇到安装问题，请：

1. 检查Ubuntu版本：`lsb_release -a`
2. 检查Python版本：`python3 --version`
3. 收集错误日志：`tail -100 app.log`
4. 提供系统信息用于问题诊断

---

## 更新记录

- **2025-06-10**: 初始版本，支持Ubuntu 18.04+
- **最后更新**: 2025-06-10

---

*本文档是DocManage项目的一部分，用于指导Ubuntu环境下的Tesseract OCR配置。* 