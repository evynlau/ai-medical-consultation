# ============================================================
# uni-app Android 离线打包 Docker 镜像
# 基于 ubuntu:22.04,装 Java 17 + Android SDK + Gradle
# 缓存 node_modules + Android SDK 减少后续构建时间
# ============================================================

FROM ubuntu:22.04

# 避免交互式提示
ENV DEBIAN_FRONTEND=noninteractive
ENV ANDROID_HOME=/opt/android-sdk
ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV GRADLE_USER_HOME=/root/.gradle

# ============= 1. 基础工具 + Java 17 =============
# 一次性装完 + 探测 JAVA_HOME 写 profile.d(后续 RUN source 即可)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget unzip git ca-certificates \
    openjdk-17-jdk-headless \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && JAVA_PATH=$(dirname $(dirname $(readlink -f $(which java)))) \
    && echo "Detected JAVA_HOME=$JAVA_PATH" \
    && echo "export JAVA_HOME=$JAVA_PATH" > /etc/profile.d/java.sh \
    && echo "export PATH=\$JAVA_HOME/bin:\$PATH" >> /etc/profile.d/java.sh

# 关键:把 JAVA_HOME/bin 写进 ENV PATH(Docker 镜像层),让所有后续 RUN 都能 java
# 这里硬编码 arm64 是因为你本机是 arm64,如果换 amd64 系统跑要改这一行
ENV PATH=/usr/lib/jvm/java-17-openjdk-arm64/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH

# ============= 2. Node.js 20 =============
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node -v && npm -v

# ============= 3. Android SDK =============
# 命令行工具
RUN mkdir -p $ANDROID_HOME/cmdline-tools \
    && cd /tmp \
    && wget -q https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -O cmdline.zip \
    && unzip -q cmdline.zip \
    && mv cmdline-tools $ANDROID_HOME/cmdline-tools/latest \
    && rm cmdline.zip

# 接受所有 SDK 许可 + 安装组件(一次 RUN,源 profile.d 拿正确 JAVA_HOME)
RUN . /etc/profile.d/java.sh \
    && echo "Using JAVA_HOME=$JAVA_HOME" \
    && yes | sdkmanager --licenses 2>&1 | tail -3 \
    && sdkmanager --install \
       "platform-tools" \
       "platforms;android-30" \
       "platforms;android-33" \
       "build-tools;33.0.2" \
       "build-tools;30.0.3" \
    && echo "SDK install OK"

# ============= 4. Gradle 8.2 =============
RUN . /etc/profile.d/java.sh \
    && wget -q https://services.gradle.org/distributions/gradle-8.2-bin.zip -O /tmp/gradle.zip \
    && unzip -q /tmp/gradle.zip -d /opt \
    && ln -sf /opt/gradle-8.2/bin/gradle /usr/local/bin/gradle \
    && rm /tmp/gradle.zip \
    && gradle --version | head -5

# ============= 5. 工作目录 =============
WORKDIR /build

# 先 copy package.json 装依赖(利用 Docker 缓存)
COPY package.json ./
RUN . /etc/profile.d/java.sh && npm install --no-audit --no-fund --prefer-offline 2>&1 | tail -5

# 再 copy 全部源码
COPY . .

# ============= 6. 默认 entrypoint =============
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["build"]
