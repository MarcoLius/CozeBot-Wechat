FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 使用清华大学镜像源
RUN echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security/ bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    gcc \
    g++ \
    make \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 先复制requirements.txt文件
COPY requirements.txt /app/

# 使用清华大学镜像源安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/

# 复制其余项目文件
COPY . /app/

# 暴露Web界面端口
EXPOSE 8501

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 启动命令
CMD ["sh", "-c", "if [ -f /app/config.json.host ]; then cp /app/config.json.host /app/config.json; fi && cd web && streamlit run Home.py"]