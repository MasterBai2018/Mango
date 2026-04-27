# ============================================================
# Mango 自动化测试框架 Docker镜像
# 基于 mango:v3.6.0 基础镜像，集成所有测试框架代码
# ============================================================
# 构建命令: docker build -t mango-app:v3.6.0 -f docker/whole/Dockerfile --build-arg BASE_IMAGE=mango:v3.6.0 .
# ============================================================

ARG BASE_IMAGE=mango:v3.6.0
FROM ${BASE_IMAGE}

LABEL maintainer="huidong.bai <MasterBai2018@outlook.com>"
LABEL version="3.6.0"
LABEL description="Mango自动化测试框架"

# 设置工作目录
WORKDIR /mango

# ============================================================
# 复制框架核心代码（这些代码不需要外部挂载）
# ============================================================

# 复制入口文件和配置文件
COPY Run_Mongo.py /mango/
COPY conftest.py /mango/
COPY pytest.ini /mango/

# 复制配置目录
COPY conf/ /mango/conf/

# 复制核心源代码
COPY src/ /mango/src/

# 复制工具目录
COPY tools/ /mango/tools/

# 复制插件目录
COPY plugins/ /mango/plugins/

# ============================================================
# 创建挂载点目录（用户外部挂载）
# ============================================================

# 创建挂载点目录和缓存目录，设置合适的权限
# 注意：/mango目录需要777权限，因为pytest会在该目录下创建临时缓存文件
RUN mkdir -p /mango/lib \
    && mkdir -p /mango/.pytest_cache \
    && mkdir -p /mango/workspace \
    && mkdir -p /mango/TestAudio \
    && mkdir -p /mango/TestCase \
    && mkdir -p /mango/TestResource \
    && chmod 777 /mango

# ============================================================
# 环境变量配置
# ============================================================

# 设置Python环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/mango:$PYTHONPATH

# 设置时区
ENV TZ=Asia/Shanghai

# ============================================================
# 入口配置
# ============================================================

# 默认入口点：直接运行测试框架
ENTRYPOINT ["python3", "Run_Mongo.py"]

# 默认参数（可被运行时参数覆盖）
CMD ["--help"]
