# sysHAX部署指南

sysHAX当前处于快速迭代阶段，基于vllm v0.6.6+npu进行验证。vllm上游发布的正式支持npu的版本为v0.7.1rc1，而当前用的vllm版本处于验证阶段，未合入主线。因此，在当前创新版本中暂不以源码形式发布，而是以容器化的形式为大家提供技术尝鲜。也欢迎开发者在使用过程中有任何问题和建议，可以在sig-Intelligence组中进行充分交流。

vllm是一款**高吞吐、低内存占用**的**大语言模型（LLM）推理与服务引擎**，支持**CPU 计算加速**，提供高效的算子下发机制，包括：

- **Schedule（调度）**：优化任务分发，提高并行计算效率
- **Prepare Input（准备数据）**：高效的数据预处理，加速输入构建
- **Ray 框架**：利用分布式计算提升推理吞吐
- **Sample（模型后处理）**：优化采样策略，提升生成质量
- **框架后处理**：融合多种优化策略，提升整体推理性能

该引擎结合**高效计算调度与优化策略**，为 LLM 推理提供**更快、更稳定、更可扩展**的解决方案。

## 环境准备

| 服务器型号  | Atlas 800T/I A2 训练/推理服务器                      |
| --------------- | --------------------------------------------------------- |
| 操作系统    | openEuler 22.03 LTS及以上                              |
| NPU驱动版本 | Ascend-hdk-910b-npu-driver_24.1.rc3_linux-aarch64.run |
| 固件版本    | Ascend-hdk-910b-firmware_7.5.0.1.129.run              |

### **安装驱动固件**

- 创建驱动运行用户HwHiAiUser（运行驱动进程的用户），安装驱动时无需指定运行用户，默认即为HwHiAiUser。

```shell
groupadd -g 1000 HwHiAiUser
useradd -g HwHiAiUser -u 1000 -d /home/HwHiAiUser -m HwHiAiUser -s /bin/bash
```

- 将驱动包和固件包上传到服务器任意目录如“/home”。
- 执行如下命令，增加驱动和固件包的可执行权限。

```shell
chmod +x Ascend-hdk-910b-npu-driver_24.1.rc3_linux-aarch64.run
chmod +x Ascend-hdk-910b-firmware_7.5.0.1.129.run
```

- 安装驱动

```shell
./Ascend-hdk-910b-npu-driver_24.1.rc3_linux-aarch64.run --full --install-for-all

# 若执行上述安装命令出现类似如下回显信息
# [ERROR]The list of missing tools: lspci,ifconfig,
# 请执行yum install -y net-tools pciutils

# 若系统出现如下关键回显信息，则表示驱动安装成功。
# Driver package installed successfully!
```

- 安装固件

```shell
./Ascend-hdk-910b-firmware_7.5.0.1.129.run --full

# 若系统出现如下关键回显信息，表示固件安装成功。
# Firmware package installed successfully! Reboot now or after driver installation for the installation/upgrade to take effect
```

- 执行reboot命令重启系统。
- 执行npu-smi info查看驱动加载是否成功。

## 容器部署场景

### 部署Ascend-Docker（容器引擎插件）

- 参考版本："Ascend-docker-runtime_6.0.RC3.1_linux-aarch64.run"

```shell
# 将软件包”Ascend-docker-runtime_6.0.RC3.1_linux-aarch64.run”上传到服务器任意目录（如“/home”）。
chmod +x Ascend-docker-runtime_6.0.RC3.1_linux-aarch64.run
```

```shell
./Ascend-docker-runtime_6.0.RC3.1_linux-aarch64.run --install
# 安装完成后，若显示类似如下信息，则说明软件安装成功:
xxx install success
```

- 执行systemctl restart docker命令重启docker，使容器引擎插件在docker配置文件中添加的内容生效。

### 容器场景vllm搭建

```shell
docker pull hub.oepkgs.net/neocopilot/vllm@sha256:c72a0533b8f34ebd4d352ddac3a969d57638c3d0c9c4af9b78c88400c6edff7a

# /home路径不要全部映射，防止覆盖/home/HwHiAiUser
docker run -itd \
    -p 1111:22 \
    --name vllm_oe \
    --shm-size 16G \
    --device /dev/davinci0 \
    --device /dev/davinci1 \
    --device /dev/davinci2 \
    --device /dev/davinci3 \
    --device /dev/davinci4 \
    --device /dev/davinci5 \
    --device /dev/davinci6 \
    --device /dev/davinci7 \
    --device /dev/davinci_manager \
    --device /dev/devmm_svm \
    --device /dev/hisi_hdc \
    -v /usr/local/dcmi:/usr/local/dcmi \
    -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi \
    -v /usr/local/Ascend/driver:/usr/local/Ascend/driver \
    -w /home \
    hub.oepkgs.net/neocopilot/vllm:0.6.6-aarch64-910B-oe2203-sp3 bash

# 启动vllm，模型自行下载
vllm serve /home/models/DeepSeek-R1-Distill-Llama-70B --distributed-executor-backend ray --tensor-parallel-size 8 --block-size 32 --preemption_mode swap
```

## 纯CPU推理环境部署

- 模型文件准备

1. 准备模型文件，放在`/home/model/`路径下

    - **注意**：当前镜像版本支持DeepSeek 7B、32B以及Qwen系列模型

2. 拉取镜像，镜像地址：docker pull hub.oepkgs.net/neocopilot/syshax/vllm-cpu@sha256:3983071e1928b9fddc037a51f2fc6b044d41a35d5c1e75ff62c8c5e6b1c157a3

3. 启动容器：

```bash
docker run --name vllm_server_sysHAX \
    -p 7001:7001 \
    -v /home/model:/home/model/ \
    -itd hub.oepkgs.net/neocopilot/syshax/vllm-cpu:0.1.2.4 bash
```

- 在容器中启动服务

```bash
cd /home/vllm_syshax
python3 vllm/entrypoints/openai/api_server.py \
    --model /home/model/DeepSeek-R1-Distill-Qwen-7B \
    --served-model-name=ds7b \
    --host 0.0.0.0 \
    --port 7001 \
    --dtype=half \
    --swap_space=16 \
    --block_size=16 \
    --preemption_mode=swap \
    --max_model_len=8192 &
```

**注意**：`--model`使用实际模型路径，`--served-model-name`可自己指定模型名字，端口两个需要对应，可不用7001
部署完成，然后向7001端口发送请求即可，请求需满足OpenAPI格式。
