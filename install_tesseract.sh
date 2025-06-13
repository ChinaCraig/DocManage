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

# 7. 安装Python OCR依赖
echo "🐍 安装Python OCR依赖..."
if command -v pip &> /dev/null; then
    pip install pytesseract Pillow
elif command -v pip3 &> /dev/null; then
    pip3 install pytesseract Pillow
else
    echo "⚠️  警告: 未找到pip，请手动安装Python依赖"
    echo "   运行: pip install pytesseract Pillow"
fi

# 8. 测试OCR功能
echo "🧪 测试OCR功能..."
python3 << 'EOF'
try:
    import pytesseract
    print("✅ pytesseract导入成功")
    
    # 测试tesseract命令
    langs = pytesseract.get_languages()
    print(f"✅ 可用语言: {langs}")
    
    print("🎉 OCR环境设置完成！")
except Exception as e:
    print(f"❌ OCR测试失败: {e}")
    print("请检查是否已正确安装Python依赖")
EOF

echo "✨ 安装完成！"
echo ""
echo "📝 下一步："
echo "   1. 重新启动终端或运行: source ~/.bashrc"
echo "   2. 启动项目: python run.py"
echo "   3. 查看详细配置说明: 参考 Ubuntu_Tesseract_OCR_安装指南.md" 