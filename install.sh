#!/bin/bash

echo "=== DeepSeek-X 安装脚本 ==="
echo "正在检查环境..."

# 检查Python版本
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.8.0"

if [ -z "$python_version" ]; then
    echo "错误: 找不到Python。请确保已安装Python 3.8或更高版本。"
    exit 1
fi

# 比较版本号
if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" = "$required_version" ]; then 
    echo "Python版本检查通过: $python_version"
else
    echo "错误: Python版本必须是3.8或更高。当前版本: $python_version"
    exit 1
fi

# 创建虚拟环境
echo "正在创建虚拟环境..."
python3 -m venv venv
if [ ! -d "venv" ]; then
    echo "错误: 无法创建虚拟环境。请检查您的Python安装。"
    exit 1
fi

# 激活虚拟环境
echo "正在激活虚拟环境..."
source venv/bin/activate

# 安装依赖
echo "正在安装依赖..."
pip install --upgrade pip
pip install -r requirements.txt

# 检查依赖安装是否成功
if [ $? -ne 0 ]; then
    echo "错误: 安装依赖失败。请查看上面的错误消息。"
    exit 1
fi

# 创建配置文件（如果不存在）
if [ ! -f "config.json" ]; then
    echo "正在创建配置文件..."
    if [ -f "config.example.json" ]; then
        cp config.example.json config.json
        echo "已创建配置文件。请编辑config.json设置您的API密钥和其他参数。"
    else
        echo "警告: 找不到config.example.json。请手动创建config.json文件。"
        # 创建基本的config.json
        cat > config.json << EOL
{
  "composite": {
    "DeepSeek X": {
      "Model ID": "deepseek+gemini",
      "Inference Model": "DeepSeek",
      "Target Model": "Gemini2.0Flash",
      "activated": true
    }
  },
  "inference": {
    "DeepSeek": {
      "Model ID": "deepseek-ai/DeepSeek-R1",
      "API Key": "Please set your DeepSeek API key",
      "Base URL": "https://api.siliconflow.cn",
      "API Path": "v1/chat/completions"
    }
  },
  "target": {
    "Gemini2.0Flash": {
      "Model ID": "gemini-2.0-flash",
      "API Key": "Please set your Google AI Studio API key",
      "Base URL": "https://generativelanguage.googleapis.com",
      "API Path": "v1beta/openai/chat/completions",
      "Model Type": "openai"
    }
  },
  "proxy": {
    "address": "127.0.0.1:8118",
    "enabled": false
  },
  "system": {
    "cors": ["*"],
    "logLevel": "INFO",
    "apiKey": "123456",
    "requestTimeout": 180000
  }
}
EOL
        echo "Basic configuration file created. Please edit config.json to set your API keys and other parameters."
    fi
else
    echo "Configuration file already exists, skipping creation step."
fi

# 创建启动脚本
echo "Creating startup script..."
cat > start.sh << EOL
#!/bin/bash
# Activate virtual environment
source venv/bin/activate

# Start service
python main.py
EOL

chmod +x start.sh

echo "========================================"
echo "Installation complete!"
echo "1. Please edit config.json to set your API keys and other parameters"
echo "2. Run ./start.sh to start the service"
echo "3. Visit http://127.0.0.1:8000 to start using DeepSeek-X"
echo "========================================" 