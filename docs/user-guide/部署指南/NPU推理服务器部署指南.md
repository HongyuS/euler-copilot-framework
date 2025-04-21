以下是为您优化的部署指南，结构更清晰、步骤更完整，并添加了注意事项和验证环节：

# Atlas 800I A2推理服务器部署指南

## 系统环境
- 操作系统：openEuler 22.03 LTS
- 硬件：Atlas 800I A2推理服务器
- 组件：Ascend NPU

## 1. 驱动安装 (优化说明)
```bash
# 安装依赖（使用openEuler官方源）
sudo dnf install -y make dkms gcc kernel-headers-$(uname -r) kernel-devel-$(uname -r)

# 已下载的驱动包为：
# Ascend-hdk-910b-npu-driver_24.1.rc3_linux-aarch64.run
# Ascend-hdk-910b-npu-firmware_7.5.0.1.129.run

# 设置权限并校验
chmod +x Ascend-hdk-*.run
./Ascend-hdk-910b-npu-driver_24.1.rc3_linux-aarch64.run --check
./Ascend-hdk-910b-npu-firmware_7.5.0.1.129.run --check

# 安装驱动（全量安装）
sudo ./Ascend-hdk-910b-npu-driver_24.1.rc3_linux-aarch64.run --full --install-for-all

# 安装固件
sudo ./Ascend-hdk-910b-npu-firmware_7.5.0.1.129.run --full

# 重启服务器
reboot

# 验证安装
npu-smi info -t board -i 0  # 查看0号卡信息
```
> **注意事项**：
> 1. 确保安装前已更新系统：`sudo dnf update -y`
> 2. 若内核升级过，需要重启进入新内核后再安装
> 3. 出现`npu-smi`命令找不到时，检查`/usr/local/Ascend/npu-smi`是否在PATH中

## 2. 容器环境准备
本指南使用昇腾开放的Docker镜像仓库，提供的昇腾软件Docker镜像来部署大模型[昇腾镜像仓库地址](https://www.hiascend.com/developer/ascendhub)
```bash
# 安装Docker运行时
wget https://gitee.com/ascend/mind-cluster/releases/download/v6.0.0.SPC1/Ascend-docker-runtime_6.0.0.SPC1_linux-aarch64.run
sudo ./Ascend-docker-runtime_6.0.0.SPC1_linux-aarch64.run --install

# 登录镜像仓库（需点击申请权限)

docker login -u cn-south-1@HST3UGLECEMTZLJ17RUT swr.cn-south-1.myhuaweicloud.com

# 拉取镜像
docker pull swr.cn-south-1.myhuaweicloud.com/ascendhub/deepseek-r1-distill-llama-70b:0.1.1-arm64
docker pull swr.cn-south-1.myhuaweicloud.com/ascendhub/mis-tei:7.0.RC1-800I-A2-aarch64
```

## 3. 模型部署
```bash
# 创建模型存储目录
sudo mkdir -p /data/models/{MindSDK,Embedding}
sudo chmod -R 777 /data/models  # 按需调整权限

# 下载大模型权重
cd /data/models/MindSDK
pip install modelscope
modelscope download deepseek-ai/DeepSeek-R1-Distill-Llama-70B --revision v1.0.0

# 下载Embedding模型
git lfs clone https://www.modelscope.cn/BAAI/bge-m3.git /data/models/Embedding/bge-m3
```

## 4. 服务启动（优化容器参数）
```bash
# 大模型推理服务
docker run -itd --name=deepseek-70b \
  --privileged \
  --device=/dev/davinci0 --device=/dev/davinci1 \
  --device=/dev/davinci_manager --device=/dev/hisi_hdc \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
  -v /data/models/MindSDK:/model \
  -e ASCEND_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 \
  -p 8000:8000 \
  swr.cn-south-1.myhuaweicloud.com/ascendhub/deepseek-r1-distill-llama-70b:0.1.1-arm64

# Embedding服务
docker run -d --name=tei-embedding \
  --net=host \
  --privileged \
  -v /data/models/Embedding/bge-m3:/app/model \
  --device=/dev/davinci0 \
  --device=/dev/davinci1 \
  swr.cn-south-1.myhuaweicloud.com/ascendhub/mis-tei:7.0.RC1-800I-A2-aarch64 \
  BAAI/bge-m3 0.0.0.0 8090
```

## 5. 服务验证
```bash
# 检查容器状态
docker ps -a --filter "name=deepseek\|tei"

# 测试大模型接口
curl -X POST http://localhost:8000/openai/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "DeepSeek-R1-Distill-Llama-70B",
    "messages": [{"role":"user","content":"你好"}],
    "temperature": 0.6
  }'

# 测试Embedding接口
curl http://localhost:8090/embed \
  -X POST \
  -d '{"inputs":"测试文本"}' \
  -H "Content-Type: application/json"
```

## 配置文件优化建议（values.yaml）
```yaml
models:
  answer:
    url: http://<server_ip>:8000/openai
    key: sk-123456
    name: DeepSeek-R1-Distill-Llama-70B
    ctx_length: 8192
    max_tokens: 2048
    parameters:  # 新增性能参数
      batch_size: 8
      tensor_parallel: 8
  functioncall:
    # 推理框架类型，默认为ollama
    # 可用的框架类型：["vllm", "sglang", "ollama", "openai"]
    backend: vllm
    # 模型地址；不填则与问答模型一致
    url:
    # API Key；不填则与问答模型一致
    key:
    # 模型名称；不填则与问答模型一致
    name:
    # 模型最大上下文数；不填则与问答模型一致
    ctx_length:
    # 模型最大输出长度；不填则与问答模型一致
    max_tokens:
  # 用于数据向量化（Embedding）的模型
  embedding:
    type: mindie
    url: http://<server_ip>:8090/v1  # 注意v1路径
    key: sk-123456
    name: bge-m3
    max_length: 8192  # 添加长度限制
```

## 常见问题排查
1. **驱动加载失败**：
   - 执行`dmesg | grep npu`查看内核日志
   - 确认`npu-smi`输出正常设备信息

2. **容器启动失败**：
   - 检查设备挂载：`ls /dev/davinci*`
   - 查看容器日志：`docker logs -f deepseek-70b`

3. **模型加载缓慢**：
   - 确认权重文件完整：`sha256sum model.bin`
   - 检查存储性能：`hdparm -Tt /dev/sda`

4. **API响应超时**：
   - 调整docker CPU限制：`--cpuset-cpus=0-31`
   - 增加JVM内存：`-e JAVA_OPTS="-Xmx64G"`

> **性能优化提示**：
> - 使用`npu-smi`监控NPU利用率
> - 在docker run时添加`--cpuset-cpus`绑定CPU核心
> - 对大模型服务启用`--tensor-parallel 8`参数