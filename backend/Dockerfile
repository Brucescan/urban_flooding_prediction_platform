# 使用地理空间专用镜像
FROM rocker/geospatial:4.3.2
RUN sudo sed -i 's/archive.ubuntu.com/mirrors.163.com/g' /etc/apt/sources.list
# 1. 安装系统依赖（Alpine兼容性调整）
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
    postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/python3 /usr/bin/python \
    && ln -sf /usr/lib/x86_64-linux-gnu/libgeos_c.so* /usr/lib/ \
    && ln -sf /usr/lib/x86_64-linux-gnu/libgdal.so* /usr/lib/ \
    && ln -sf /usr/lib/x86_64-linux-gnu/libproj.so* /usr/lib/ \
    && ldconfig
#设置动态库路径
ENV LD_LIBRARY_PATH="/usr/lib:/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"

RUN curl -sSL https://sdk.cloud.google.com | bash
ENV PATH="$PATH:/root/google-cloud-sdk/bin"
# 2. 安装rgee
RUN R -e 'install.packages("remotes"); remotes::install_github("r-spatial/rgee")'

# 3. 配置Python环境（修正参数名）
RUN python3 -m venv /opt/rgee-venv && \
    /opt/rgee-venv/bin/pip install --upgrade pip earthengine-api && \
    echo 'RETICULATE_PYTHON="/opt/rgee-venv/bin/python"' >> /etc/environment

## 4. 设置Python虚拟环境
#ENV PATH="/root/.virtualenvs/rgee/bin:$PATH"
#RUN pip3 install --upgrade pip earthengine-api

# 5. 认证文件配置
RUN mkdir -p /root/.config/earthengine && chmod 700 /root/.config/earthengine
COPY service-account.json /root/.config/earthengine/
RUN gcloud auth activate-service-account --key-file=/root/.config/earthengine/service-account.json
# 6. 项目依赖安装
WORKDIR /app
COPY requirements.txt .
RUN /opt/rgee-venv/bin/pip install --upgrade pip setuptools wheel
RUN /opt/rgee-venv/bin/pip install numpy==1.23.5  # 显式优先安装numpy
RUN /opt/rgee-venv/bin/pip install --no-cache-dir -r requirements.txt

# 7. 应用部署
COPY . .
COPY wait-for-db.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/wait-for-db.sh

EXPOSE 8000
ENTRYPOINT ["sh", "/usr/local/bin/wait-for-db.sh"]