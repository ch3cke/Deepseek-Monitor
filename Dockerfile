FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置时区为亚洲/上海，确保日志和数据库时间戳准确
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 复制依赖配置并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目所有代码
COPY . .

# 暴露 FastAPI 前端端口
EXPOSE 8000

