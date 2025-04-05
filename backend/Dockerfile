# 使用地理空间专用镜像
FROM rocker/geospatial:4.3.2
RUN sudo sed -i 's/archive.ubuntu.com/mirrors.163.com/g' /etc/apt/sources.list

# 1. 安装系统依赖
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    libgdal-dev \
    gdal-bin \
    libgeos-dev \
    libgeos-c1v5 \
    python3-venv \
    libproj-dev \
    proj-bin \
    proj-data \
    curl git \
    cron \
    redis-tools \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/python3 /usr/bin/python \
    && ln -sf /usr/lib/x86_64-linux-gnu/libgeos_c.so* /usr/lib/ \
    && ln -sf /usr/lib/x86_64-linux-gnu/libgdal.so* /usr/lib/ \
    && ln -sf /usr/lib/x86_64-linux-gnu/libproj.so* /usr/lib/ \
    && ldconfig

# 设置动态库路径
ENV LD_LIBRARY_PATH="/usr/lib:/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"

# 安装 Google Cloud SDK
RUN curl -sSL https://sdk.cloud.google.com | bash
ENV PATH="$PATH:/root/google-cloud-sdk/bin"

# 安装 rgee
RUN R -e 'install.packages("remotes"); remotes::install_github("r-spatial/rgee")'

# 配置 Python 环境
RUN python3 -m venv /opt/rgee-venv && \
    /opt/rgee-venv/bin/pip install --upgrade pip earthengine-api && \
    echo 'RETICULATE_PYTHON="/opt/rgee-venv/bin/python"' >> /etc/environment

# 认证文件配置
RUN mkdir -p /root/.config/earthengine && chmod 700 /root/.config/earthengine
COPY service-account.json /root/.config/earthengine/
RUN gcloud auth activate-service-account --key-file=/root/.config/earthengine/service-account.json

# 项目依赖安装
WORKDIR /app
COPY requirements.txt .
RUN /opt/rgee-venv/bin/pip install --upgrade pip setuptools wheel && \
    /opt/rgee-venv/bin/pip install numpy==1.23.5 && \
    /opt/rgee-venv/bin/pip install --no-cache-dir -r requirements.txt

# 设置 PATH（包含系统路径）
ENV PATH="/opt/rgee-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH}"

# 复制应用代码
COPY . .

# 复制并设置 wait-for-db.sh
COPY ./scripts/wait-for-db.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/wait-for-db.sh

EXPOSE 8000