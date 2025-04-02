#!/bin/bash
set -euo pipefail

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # 重置颜色

# 配置参数
readonly MODEL_NAME="deepseek-llm-7b-chat"
readonly MODEL_URL="https://modelscope.cn/models/second-state/Deepseek-LLM-7B-Chat-GGUF/resolve/master/deepseek-llm-7b-chat-Q4_K_M.gguf"
readonly MODEL_FILE="deepseek-llm-7b-chat-Q4_K_M.gguf"
readonly MODEL_DIR="/home/eulercopilot/models"
readonly MODELLEFILE="Modelfile"
readonly TIMEOUT_DURATION=45

# 初始化工作目录
readonly WORK_DIR=$(pwd)
mkdir -p "$MODEL_DIR"

check_service() {
    echo -e "${BLUE}步骤1/5：检查服务状态...${NC}"
    if ! systemctl is-active --quiet ollama; then
        echo -e "${RED}Ollama服务未运行${NC}"
        echo -e "${YELLOW}请先执行ollama-install.sh安装服务${NC}"
        exit 1
    fi
    echo -e "${GREEN}服务状态正常${NC}"
}

check_network() {
    local url="https://modelscope.cn"
    echo -e "${BLUE}步骤2/5：检查网络连接...${NC}"
    if curl --silent --head --fail --max-time 5 "$url" >/dev/null 2>&1; then
        echo -e "${GREEN}网络连接正常${NC}"
        return 0
    else
        echo -e "${YELLOW}无法连接网络，进入离线安装模式${NC}"
        return 1
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
            echo -e "${RED}[ERROR] 找不到本地模型文件${NC}"
            ls -l "$MODEL_DIR"/*.gguf 2>/dev/null || echo "目录内容：$(ls -l $MODEL_DIR)"
            exit 1
        fi
    fi

    # 在线模式处理
    echo -e "${YELLOW}开始在线下载模型...${NC}"

    # 创建临时文件记录wget输出
    local wget_output=$(mktemp)

    # 执行下载并显示动态进度条
    (
        wget --tries=3 --content-disposition -O "$model_path" "$MODEL_URL" --progress=dot:binary 2>&1 | \
        while IFS= read -r line; do
            # 提取百分比
            if [[ "$line" =~ ([0-9]{1,3})% ]]; then
                local percent=${BASH_REMATCH[1]}
                # 计算进度条长度（基于终端宽度-20）
                local cols=$(tput cols)
                local bar_width=$((cols - 20))
                local filled=$((percent * bar_width / 100))
                local empty=$((bar_width - filled))

                # 构建进度条
                local progress_bar=$(printf "%${filled}s" | tr ' ' '=')
                local remaining_bar=$(printf "%${empty}s" | tr ' ' ' ')

                # 显示进度（使用回车覆盖）
                printf "\r[%s%s] %3d%%" "$progress_bar" "$remaining_bar" "$percent"
            fi
        done
        echo  # 换行
    ) | tee "$wget_output"

    # 检查下载结果
    if grep -q "100%" "$wget_output"; then
        echo -e "${GREEN}[SUCCESS] 模型下载完成（文件大小：$(du -h "$model_path" | awk '{print $1}')）${NC}"
        rm -f "$wget_output"
    else
        echo -e "${RED}[ERROR] 模型下载失败${NC}"
        echo -e "${YELLOW}可能原因："
        echo "1. URL已失效（当前URL: $MODEL_URL）"
        echo "2. 网络连接问题"
        echo -e "3. 磁盘空间不足（当前剩余：$(df -h ${MODEL_DIR} | awk 'NR==2 {print $4}')）${NC}"
        rm -f "$wget_output"
        exit 1
    fi
}

create_modelfile() {
    echo -e "${BLUE}步骤3/5：创建模型配置...${NC}"
    cat > "${WORK_DIR}/${MODELLEFILE}" <<EOF
FROM ${MODEL_DIR}/${MODEL_FILE}
PARAMETER num_ctx 4096
PARAMETER num_gpu 1
EOF
    echo -e "${GREEN}Modelfile创建成功（路径：${WORK_DIR}/${MODELLEFILE}）${NC}"
}

create_model() {
    echo -e "${BLUE}步骤4/5：导入模型...${NC}"
    if ollama list | grep -qw "${MODEL_NAME}"; then
        echo -e "${GREEN}模型已存在，跳过创建${NC}"
        return 0
    fi

    if ! ollama create "${MODEL_NAME}" -f "${WORK_DIR}/${MODELLEFILE}"; then
        echo -e "${RED}模型创建失败${NC}"
        echo -e "${YELLOW}可能原因："
        echo "1. Modelfile格式错误（路径：${WORK_DIR}/${MODELLEFILE}）"
        echo "2. 模型文件损坏（MD5校验：$(md5sum "${MODEL_DIR}/${MODEL_FILE}" | cut -d' ' -f1)）"
        exit 1
    fi
    echo -e "${GREEN}模型导入成功${NC}"
}

verify_deployment() {
    echo -e "${BLUE}步骤5/5：验证部署结果...${NC}"
    if ! command -v jq &> /dev/null; then
        echo -e "${YELLOW}注意：jq未安装，响应解析可能受限，建议安装jq以获得更好的输出。${NC}"
    fi

    local retries=3
    local interval=5
    local attempt=1

    if ! ollama list | grep -qw "${MODEL_NAME}"; then
        echo -e "${RED}基础验证失败 - 未找到模型 ${MODEL_NAME}${NC}"
        exit 1
    fi
    echo -e "${GREEN}基础验证通过 - 检测到模型: ${MODEL_NAME}${NC}"

    echo -e "${YELLOW}执行API测试（超时时间${TIMEOUT_DURATION}秒）...${NC}"

    while [ $attempt -le $retries ]; do
        echo -e "${BLUE}尝试 $attempt: 发送测试请求...${NC}"

        response=$(timeout ${TIMEOUT_DURATION} curl -s http://localhost:11434/v1/chat/completions \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer sk-123456" \
            -d '{
                "model": "'"${MODEL_NAME}"'",
                "messages": [
                    {"role": "system", "content": "你是一个AI助手"},
                    {"role": "user", "content": "你好，请说一首中文古诗"}
                ],
                "stream": false
            }')

        if [[ $? -eq 0 ]] && [[ -n "$response" ]]; then
            echo -e "${GREEN}测试响应成功，收到有效输出："
            if jq -e .choices[0].message.content <<< "$response" &> /dev/null; then
                jq .choices[0].message.content <<< "$response"
            else
                echo "$response"
            fi
            return 0
        else
            echo -e "${YELLOW}请求未得到有效响应，重试中...${NC}"
            ((attempt++))
            sleep $interval
        fi
    done

    echo -e "${RED}验证失败：经过 ${retries} 次重试仍未收到有效响应${NC}"
    return 1
}

### 主执行流程 ###
echo -e "${BLUE}=== 开始模型部署 ===${NC}"
{
    check_service
    handle_model
    create_modelfile
    create_model
    verify_deployment || true
}

echo -e "${GREEN}=== 模型部署成功 ===${NC}"

cat << EOF
${YELLOW}
使用说明：
1. 启动交互模式：ollama run $MODEL_NAME
${BLUE}2. API访问示例：${NC}
curl http://localhost:11434/v1/chat/completions \\
-H "Content-Type: application/json" \\
-H "Authorization: Bearer sk-123456" \\
-d '{
    "model": "$MODEL_NAME",
    "messages": [
        {"role": "system", "content": "你是一个AI助手"},
        {"role": "user", "content": "你好"}
    ],
    "stream": false,
    "n": 1,
    "max_tokens": 2048
}'

${BLUE}3. 流式对话模式：${NC}
将上述请求中的 "stream": false 改为 "stream": true
${NC}
EOF
