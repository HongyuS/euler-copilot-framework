#!/bin/bash

MAGENTA='\e[35m'
CYAN='\e[36m'
BLUE='\e[34m'
GREEN='\e[32m'
YELLOW='\e[33m'
RED='\e[31m'
RESET='\e[0m'

# 初始化全局变量
OS_ID=""
ARCH=""
OLLAMA_BIN_PATH="/usr/bin/ollama"
OLLAMA_LIB_DIR="/usr/lib/ollama"
OLLAMA_DATA_DIR="/var/lib/ollama"
SERVICE_FILE="/etc/systemd/system/ollama.service"
LOCAL_DIR="/home/eulercopilot/tools"
LOCAL_TGZ="ollama-linux-${ARCH}.tgz"

# 带时间戳的输出函数
log() {
  local level=$1
  shift
  local color
  case "$level" in
    "INFO") color=${BLUE} ;;
    "SUCCESS") color=${GREEN} ;;
    "WARNING") color=${YELLOW} ;;
    "ERROR") color=${RED} ;;
    *) color=${RESET} ;;
  esac
  echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] $level: $*${RESET}"
}

# 网络连接检查
check_network() {
  local install_url=$(get_ollama_url)
  local domain=$(echo "$install_url" | awk -F/ '{print $3}')
  local test_url="http://$domain"

  log "INFO" "检查网络连接 ($domain)..."
  if curl --silent --head --fail --connect-timeout 5 --max-time 10 "$test_url" >/dev/null 2>&1; then
    log "INFO" "网络连接正常"
    return 0
  else
    log "WARNING" "无法连接互联网"
    return 1
  fi
}

# 操作系统检测
detect_os() {
  log "INFO" "步骤1/8：检测操作系统和架构..."
  if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_ID="${ID}"
    log "INFO" "检测到操作系统: ${PRETTY_NAME}"
  else
    log "ERROR" "无法检测操作系统类型"
    exit 1
  fi

  ARCH=$(uname -m)
  case "$ARCH" in
    x86_64)  ARCH="amd64" ;;
    aarch64) ARCH="arm64" ;;
    armv7l)  ARCH="armv7" ;;
    *)       log "ERROR" "不支持的架构: $ARCH"; exit 1 ;;
  esac
  LOCAL_TGZ="ollama-linux-${ARCH}.tgz"
  log "INFO" "系统架构: $ARCH"
}

# 安装系统依赖
install_dependencies() {
  log "INFO" "步骤2/8：安装系统依赖..."
  local deps=(curl wget tar gzip jq)

  case "$OS_ID" in
    ubuntu|debian)
      if ! apt-get update; then
        log "ERROR" "APT源更新失败"
        exit 1
      fi
      if ! DEBIAN_FRONTEND=noninteractive apt-get install -y "${deps[@]}"; then
        log "ERROR" "APT依赖安装失败"
        exit 1
      fi
      ;;
    centos|rhel|fedora|openEuler|kylin|uos)
      if ! yum install -y "${deps[@]}"; then
        log "ERROR" "YUM依赖安装失败"
        exit 1
      fi
      ;;
    *)
      log "ERROR" "不支持的发行版: $OS_ID"
      exit 1
      ;;
  esac
  log "SUCCESS" "系统依赖安装完成"
}

# 获取Ollama下载地址
get_ollama_url() {
  echo "https://repo.oepkgs.net/openEuler/rpm/openEuler-22.03-LTS/contrib/eulercopilot/tools/$ARCH/ollama-linux-$ARCH.tgz"
}

install_ollama() {
  log "INFO" "步骤3/8：安装Ollama核心..."
  local install_url=$(get_ollama_url)
  local tmp_file="/tmp/ollama-${ARCH}.tgz"
  # 增强清理逻辑
  if [ -x "$OLLAMA_BIN_PATH" ] || [ -x "/usr/local/bin/ollama" ]; then
    log "WARNING" "发现已存在的Ollama安装，版本: $($OLLAMA_BIN_PATH --version)"
    read -p "是否重新安装？[y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log "WARNING" "发现已存在的Ollama安装，正在清理..."
        systemctl stop ollama 2>/dev/null || true
        systemctl disable ollama 2>/dev/null || true
	rm -rf ${SERVICE_FILE} 2>/dev/null
	rm $(which ollama) 2>/dev/null
        rm -rf ${OLLAMA_LIB_DIR} 2>/dev/null
        rm -rf ${OLLAMA_DATA_DIR} 2>/dev/null
        rm -rf /run/ollama 2>/dev/null
        userdel ollama 2>/dev/null || true
	groupdel ollama 2>/dev/null || true
    else
        return 0
    fi
  fi
    # 增强安装包处理
  local actual_tgz_path=""
  if [ -f "${LOCAL_DIR}/${LOCAL_TGZ}" ]; then
    log "INFO" "使用本地安装包: ${LOCAL_DIR}/${LOCAL_TGZ}"
    actual_tgz_path="${LOCAL_DIR}/${LOCAL_TGZ}"
  else
    if ! check_network; then
      log "ERROR" "网络不可用且未找到本地安装包"
      log "INFO" "请预先下载${LOCAL_TGZ}并放置${LOCAL_DIR}"
      exit 1
    fi
    log "INFO" "下载安装包: ${install_url}"
    if ! wget --show-progress -q -O "${tmp_file}" "${install_url}"; then
      log "ERROR" "下载失败，退出码: $?"
      exit 1
    fi
    actual_tgz_path="${tmp_file}"
  fi

  log "INFO" "解压文件到系统目录/usr..."
  if ! tar -xzvf "$actual_tgz_path" -C /usr/; then
    log "ERROR" "解压失败，可能原因：\n1.文件损坏\n2.磁盘空间不足\n3.权限问题"
    exit 1
  fi

  chmod +x "$OLLAMA_BIN_PATH"
  if [ ! -x "$OLLAMA_BIN_PATH" ]; then
    log "ERROR" "安装后验证失败：可执行文件不存在"
    exit 1
  fi
  log "SUCCESS" "Ollama核心安装完成，版本: $($OLLAMA_BIN_PATH --version || echo '未知')"
    # 新增：创建兼容性符号链接
  if [ ! -L "/usr/local/bin/ollama" ]; then
    ln -sf "$OLLAMA_BIN_PATH" "/usr/local/bin/ollama"
    log "INFO" "已创建符号链接：/usr/local/bin/ollama → $OLLAMA_BIN_PATH"
  fi

  # 设置库路径
  echo "${OLLAMA_LIB_DIR}" > /etc/ld.so.conf.d/ollama.conf
  ldconfig
}

fix_user() {
  log "INFO" "步骤4/8: 修复用户配置..."
  
  # 终止所有使用ollama用户的进程
  if pgrep -u ollama >/dev/null; then
    log "WARNING" "发现正在运行的ollama进程，正在终止..."
    pkill -9 -u ollama || true
    sleep 2
    if pgrep -u ollama >/dev/null; then
      log "ERROR" "无法终止ollama用户进程"
      exit 1
    fi
  fi

  # 清理旧用户
  if id ollama &>/dev/null; then
    # 检查用户是否被锁定
    if passwd -S ollama | grep -q 'L'; then
      log "INFO" "发现被锁定的ollama用户，正在解锁并设置随机密码..."
      random_pass=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 16)
      usermod -p "$(openssl passwd -1 "$random_pass")" ollama
    fi
    
    # 删除用户及其主目录
    if ! userdel -r ollama; then
      log "WARNING" "无法删除ollama用户，尝试强制删除..."
      if ! userdel -f -r ollama; then
        log "ERROR" "强制删除用户失败，尝试手动清理..."
        sed -i '/^ollama:/d' /etc/passwd /etc/shadow /etc/group
        rm -rf /var/lib/ollama
        log "WARNING" "已手动清理ollama用户信息"
      fi
    fi
    log "INFO" "已删除旧ollama用户"
  fi

  # 检查组是否存在
  if getent group ollama >/dev/null; then
    log "INFO" "ollama组已存在，将使用现有组"
    existing_group=true
  else
    existing_group=false
  fi

  # 创建系统用户
  if ! useradd -r -g ollama -d /var/lib/ollama -s /bin/false ollama; then
    log "ERROR" "用户创建失败，尝试手动创建..."
    
    # 如果组不存在则创建
    if ! $existing_group; then
      if ! groupadd -r ollama; then
        log "ERROR" "无法创建ollama组"
        exit 1
      fi
    fi
    
    # 再次尝试创建用户
    if ! useradd -r -g ollama -d /var/lib/ollama -s /bin/false ollama; then
      log "ERROR" "手动创建用户失败，请检查以下内容："
      log "ERROR" "1. /etc/passwd 和 /etc/group 文件是否可写"
      log "ERROR" "2. 系统中是否存在冲突的用户/组"
      log "ERROR" "3. 系统用户限制（/etc/login.defs）"
      exit 1
    fi
  fi

  # 创建目录结构
  mkdir -p /var/lib/ollama/.ollama/{models,bin}
  chown -R ollama:ollama /var/lib/ollama
  chmod -R 755 /var/lib/ollama
  log "SUCCESS" "用户配置修复完成"
}

fix_service() {
  log "INFO" "步骤5/8：配置系统服务..."
  cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=Ollama Service
After=network-online.target

[Service]
Environment="OLLAMA_MODELS=${OLLAMA_DATA_DIR}/.ollama/models"
Environment="OLLAMA_HOST=0.0.0.0:11434"
ExecStart=${OLLAMA_BIN_PATH} serve
User=ollama
Group=ollama
Restart=failure
RestartSec=5
WorkingDirectory=/var/lib/ollama
RuntimeDirectory=ollama
RuntimeDirectoryMode=0755
StateDirectory=ollama
StateDirectoryMode=0755
CacheDirectory=ollama
CacheDirectoryMode=0755
LogsDirectory=ollama
LogsDirectoryMode=0755

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  log "SUCCESS" "服务配置更新完成"
}

# 重启服务
restart_service() {
  log "INFO" "步骤6/8: 重启服务..."

  # 确保服务停止
  systemctl stop ollama || true

  # 确保运行时目录存在
  mkdir -p /run/ollama
  chown ollama:ollama /run/ollama
  chmod 755 /run/ollama

  # 启动服务
  systemctl start ollama
  systemctl enable ollama

  log "SUCCESS" "服务重启完成"
}


# 最终验证
final_check() {
  log "INFO" "步骤7/8：执行最终验证..."
  if ! command -v ollama &>/dev/null; then
    log "ERROR" "Ollama未正确安装"
    exit 1
  fi
  if ! ollama list &>/dev/null; then
    log "ERROR" "服务连接失败，请检查：\n1.服务状态: systemctl status ollama\n2.端口监听: ss -tuln | grep 11434"
    exit 1
  fi

  log "SUCCESS" "验证通过，您可以执行以下操作：\n  ollama list          # 查看模型列表\n  ollama run llama2    # 运行示例模型"
}

### 主执行流程 ###
main() {
  if [[ $EUID -ne 0 ]]; then
    log "ERROR" "请使用sudo运行此脚本"
    exit 1
  fi

  detect_os
  install_dependencies
  echo -e "${MAGENTA}=== 开始Ollama安装 ===${RESET}"
  install_ollama
  fix_user
  fix_service
  restart_service
  if final_check; then
      echo -e "${MAGENTA}=== Ollama安装成功 ===${RESET}"
  else
      echo -e "${MAGENTA}=== Ollama安装失败 ===${RESET}"
  fi
}

main
