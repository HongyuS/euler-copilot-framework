set -euo pipefail

# 颜色定义
RED='\e[31m'
GREEN='\e[32m'
YELLOW='\e[33m'
BLUE='\e[34m'
NC='\e[0m' # 重置颜色

# 配置参数
readonly MODEL_NAME="bge-m3"
readonly MODEL_URL="https://modelscope.cn/models/gpustack/bge-m3-GGUF/resolve/master/bge-m3-Q4_K_M.gguf"
readonly MODEL_FILE="bge-m3-Q4_K_M.gguf"
readonly MODELLEFILE="Modelfile"
readonly TIMEOUT_DURATION=45
readonly MODEL_DIR="/home/eulercopilot/models"

# 网络检查函数（保持不变）
check_network() {
    echo -e "${BLUE}步骤1/5：检查网络连接...${NC}"
    local test_url="https://modelscope.cn"
    if curl --silent --head --fail --max-time 5 "$test_url" >/dev/null 2>&1; then
        echo -e "${GREEN}[SUCCESS] 网络连接正常${NC}"
        return 0
    else
        echo -e "${YELLOW}[WARNING] 无法连接网络，切换到离线模式${NC}"
        return 1
    fi
}

# 服务检查（保持不变）
check_service() {
    echo -e "${BLUE}步骤2/5：检查服务状态...${NC}"
    if ! systemctl is-active --quiet ollama; then
        echo -e "${RED}[ERROR] Ollama服务未运行${NC}"
        echo -e "${YELLOW}可能原因："
        echo "1. 服务未安装"
        echo "2. 系统未启用服务"
        echo -e "请先执行ollama-install.sh安装服务${NC}"
        exit 1
    fi
}

handle_model() {
    echo -e "${BLUE}步骤3/5：处理模型文件...${NC}"
    local model_path="${MODEL_DIR}/${MODEL_FILE}"

    # 离线模式处理
    if ! check_network; then
        if [[ -f "$model_path" ]]; then
            echo -e "${YELLOW}检测到本地模型文件 ${model_path}${NC}"
            return 0
        else
            echo -e "${RED}[ERROR] 找不到本地模型文件,请手动下载 bge-m3 模型,并保存至$MODEL_DIR${NC}"
            ls -l "$MODEL_DIR"/*.gguf 2>/dev/null || echo "目录内容：$(ls -l $MODEL_DIR)"
            exit 1
        fi
    fi

    # 在线模式处理
    echo -e "${YELLOW}开始在线下载模型...${NC}"

    local download_cmd
    if command -v wget &>/dev/null; then
        download_cmd="wget --tries=3 --content-disposition -O '${MODEL_DIR}/${MODEL_FILE}' '${MODEL_URL}'"
    elif command -v curl &>/dev/null; then
        download_cmd="curl -# -L -o '${MODEL_DIR}/${MODEL_FILE}' '${MODEL_URL}'"
    else
        echo -e "${RED}错误：需要wget或curl来下载模型文件${NC}"
        exit 1
    fi

    if ! eval "$download_cmd"; then
        echo -e "${RED}模型下载失败，删除不完整文件...${NC}"
        rm -f "${MODEL_DIR}/${MODEL_FILE}"
        exit 1
    fi

    echo -e "${GREEN}模型下载完成（文件大小：$(du -h "${MODEL_DIR}/${MODEL_FILE}" | cut -f1)）${NC}"
}

create_modelfile() {
    echo -e "${BLUE}步骤4/5：创建模型配置...${NC}"
    cat > "$MODELLEFILE" <<EOF
FROM ${MODEL_DIR}/${MODEL_FILE}
PARAMETER num_ctx 4096
PARAMETER num_gpu 1
EOF
    echo -e "${GREEN}[SUCCESS] Modelfile创建成功（路径：$(pwd)/${MODELLEFILE}）${NC}"
}

create_model() {
    echo -e "${BLUE}步骤5/5：导入模型...${NC}"
    if ollama list | grep -q "${MODEL_NAME}"; then
        echo -e "${GREEN}[SUCCESS] 模型已存在，跳过创建${NC}"
        return 0
    fi

    if ! ollama create "${MODEL_NAME}" -f "${MODELLEFILE}"; then
        echo -e "${RED}[ERROR] 模型创建失败${NC}"
        echo -e "${YELLOW}可能原因："
        echo "1. Modelfile格式错误（当前路径：$(pwd)/${MODELLEFILE}）"
        echo "2. 模型文件损坏（MD5校验：$(md5sum ${MODEL_DIR}/${MODEL_FILE} | awk '{print $1}')）"
        exit 1
    fi
    echo -e "${GREEN}[SUCCESS] 模型导入成功${NC}"
}

verify_deployment() {
    echo -e "${BLUE}验证部署结果...${NC}"
    local retries=3
    local wait_seconds=15
    local test_output=$(mktemp)
    local INTERVAL=5

    # 基础验证
    if ! ollama list | grep -q "${MODEL_NAME}"; then
        echo -e "${RED}[ERROR] 基础验证失败 - 未找到模型 ${MODEL_NAME}${NC}"
        echo -e "${YELLOW}排查建议："
        echo "1. 检查服务状态：systemctl status ollama"
        echo -e "2. 查看创建日志：journalctl -u ollama | tail -n 50${NC}"
        exit 1
    fi

    # 增强验证：通过API获取嵌入向量
    echo -e "${YELLOW}执行API测试（最多尝试${retries}次）...${NC}"
    for ((i=1; i<=retries; i++)); do
        local http_code=$(curl -k -o /dev/null -w "%{http_code}" -X POST http://localhost:11434/v1/embeddings \
            -H "Content-Type: application/json" \
            -d '{"input": "The food was delicious and the waiter...", "model": "bge-m3", "encoding_format": "float"}' -s -m $TIMEOUT_DURATION)

        if [[ "$http_code" == "200" ]]; then
            echo -e "${GREEN}[SUCCESS] API测试成功（HTTP状态码：200）${NC}"
            return 0
        else
            echo -e "${YELLOW}[WARNING] 第${i}次尝试失败（HTTP状态码：${http_code}）${NC}"
            sleep $INTERVAL
        fi
    done

    echo -e "${RED}[ERROR] API测试失败，已达到最大尝试次数${NC}"
    echo -e "${YELLOW}可能原因："
    echo "1. 模型未正确加载"
    echo "2. 服务响应超时（当前超时设置：${TIMEOUT_DURATION}秒）"
    echo -e "3. 系统资源不足（检查GPU内存使用情况）${NC}"
    exit 1
}

### 主执行流程 ###
echo -e "${BLUE}=== 开始模型部署 ===${NC}"
{
    check_service
    handle_model
    create_modelfile
    create_model
    verify_deployment
}
echo -e "${BLUE}=== 模型部署成功 ===${NC}"
cat << EOF
${GREEN}使用说明：${NC}
1. 启动交互模式：ollama run $MODEL_NAME
2. API访问示例：
curl -k -X POST http://localhost:11434/v1/embeddings \\
-H "Content-Type: application/json" \\
-d '{"input": "The food was delicious and the waiter...", "model": "bge-m3", "encoding_format": "float"}'
EOF
