# sysHAX Deployment Guide

sysHAX is currently in a rapid iteration phase, validated based on vllm v0.6.6+npu. The officially released version from vllm upstream that supports NPU is v0.7.1rc1, while the current vllm version is in the validation phase and has not been merged into the mainline. Therefore, in the current innovation version, it is not released in source code form, but rather in a containerized form to provide technical preview for everyone. We also welcome developers to fully communicate any issues and suggestions during use in the sig-Intelligence group.

vllm is a **high-throughput, low-memory consumption** **Large Language Model (LLM) inference and service engine** that supports **CPU computation acceleration**, providing efficient operator dispatch mechanisms, including:

- **Schedule**: Optimizes task distribution and improves parallel computation efficiency
- **Prepare Input**: Efficient data preprocessing to accelerate input construction
- **Ray Framework**: Utilizes distributed computing to improve inference throughput
- **Sample (Model Post-processing)**: Optimizes sampling strategies to improve generation quality
- **Framework Post-processing**: Integrates multiple optimization strategies to improve overall inference performance

This engine combines **efficient computation scheduling and optimization strategies** to provide **faster, more stable, and more scalable** solutions for LLM inference.

## Environment Preparation

| Server Model | Atlas 800T/I A2 Training/Inference Server |
| ------------ | ------------------------------------------ |
| Operating System | openEuler 22.03 LTS and above |
| NPU Driver Version | Ascend-hdk-910b-npu-driver_24.1.rc3_linux-aarch64.run |
| Firmware Version | Ascend-hdk-910b-firmware_7.5.0.1.129.run |

### **Installing Driver and Firmware**

- Create the driver runtime user HwHiAiUser (the user running the driver process). When installing the driver, there's no need to specify the runtime user, as it defaults to HwHiAiUser.

```shell
groupadd -g 1000 HwHiAiUser
useradd -g HwHiAiUser -u 1000 -d /home/HwHiAiUser -m HwHiAiUser -s /bin/bash
```

- Upload the driver package and firmware package to any directory on the server, such as "/home".
- Execute the following commands to add executable permissions to the driver and firmware packages.

```shell
chmod +x Ascend-hdk-910b-npu-driver_24.1.rc3_linux-aarch64.run
chmod +x Ascend-hdk-910b-firmware_7.5.0.1.129.run
```

- Install the driver

```shell
./Ascend-hdk-910b-npu-driver_24.1.rc3_linux-aarch64.run --full --install-for-all

# If the above installation command shows error messages similar to:
# [ERROR]The list of missing tools: lspci,ifconfig,
# Please execute: yum install -y net-tools pciutils

# If the system shows the following key output information, it indicates successful driver installation.
# Driver package installed successfully!
```

- Install the firmware

```shell
./Ascend-hdk-910b-firmware_7.5.0.1.129.run --full

# If the system shows the following key output information, it indicates successful firmware installation.
# Firmware package installed successfully! Reboot now or after driver installation for the installation/upgrade to take effect
```

- Execute the reboot command to restart the system.
- Execute `npu-smi info` to check if the driver loaded successfully.

## Container Deployment Scenarios

### Deploying Ascend-Docker (Container Engine Plugin)

- Reference version: "Ascend-docker-runtime_6.0.RC3.1_linux-aarch64.run"

```shell
# Upload the software package "Ascend-docker-runtime_6.0.RC3.1_linux-aarch64.run" to any directory on the server (such as "/home").
chmod +x Ascend-docker-runtime_6.0.RC3.1_linux-aarch64.run
```

```shell
./Ascend-docker-runtime_6.0.RC3.1_linux-aarch64.run --install
# After installation, if it displays information similar to the following, it indicates successful software installation:
xxx install success
```

- Execute the `systemctl restart docker` command to restart docker, making the content added by the container engine plugin in the docker configuration file take effect.

### Container Scenario vllm Setup

```shell
docker pull hub.oepkgs.net/neocopilot/vllm@sha256:c72a0533b8f34ebd4d352ddac3a969d57638c3d0c9c4af9b78c88400c6edff7a

# Do not map the entire /home path to prevent overwriting /home/HwHiAiUser
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

# Start vllm, model will be downloaded automatically
vllm serve /home/models/DeepSeek-R1-Distill-Llama-70B --distributed-executor-backend ray --tensor-parallel-size 8 --block-size 32 --preemption_mode swap
```

## Pure CPU Inference Environment Deployment

- Model File Preparation

1. Prepare model files and place them in the `/home/model/` path

    - **Note**: The current image version supports DeepSeek 7B, 32B, and Qwen series models

2. Pull the image, image address: `docker pull hub.oepkgs.net/neocopilot/syshax/vllm-cpu@sha256:3983071e1928b9fddc037a51f2fc6b044d41a35d5c1e75ff62c8c5e6b1c157a3`

3. Start the container:

```bash
docker run --name vllm_server_sysHAX \
    -p 7001:7001 \
    -v /home/model:/home/model/ \
    -itd hub.oepkgs.net/neocopilot/syshax/vllm-cpu:0.1.2.4 bash
```

- Start the service in the container

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

**Note**: Use the actual model path for `--model`, `--served-model-name` can be specified by yourself, and the two ports need to correspond (you don't have to use 7001).

After deployment is complete, you can send requests to port 7001. The requests need to comply with the OpenAPI format.
