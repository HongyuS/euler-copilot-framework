# 智能诊断部署指南

## 准备工作

+ 提前安装 [EulerCopilot 命令行（智能 Shell）客户端](../../../quick_start/smart_shell/user_guide/shell.md)

+ 被诊断机器不能安装 crictl 和 isula，只能有 docker 一个容器管理工具

+ 在需要被诊断的机器上安装 gala-gopher 和 gala-anteater

## 部署 gala-gopher

### 1. 准备 BTF 文件

**如果Linux内核支持 BTF，则不需要准备 BTF 文件。**可以通过以下命令来查看Linux内核是否已经支持 BTF：

```bash
cat /boot/config-$(uname -r) | grep CONFIG_DEBUG_INFO_BTF
```

如果输出结果为`CONFIG_DEBUG_INFO_BTF=y`，则表示内核支持BTF。否则表示内核不支持BTF。
如果内核不支持BTF，需要手动制作BTF文件。步骤如下：

1. 获取当前Linux内核版本的 vmlinux 文件

   vmlinux 文件存放在 `kernel-debuginfo` 包里面，存放路径为 `/usr/lib/debug/lib/modules/$(uname -r)/vmlinux`。

   例如，对于 `kernel-debuginfo-5.10.0-136.65.0.145.oe2203sp1.aarch64`，对应的vmlinux路径为`/usr/lib/debug/lib/modules/5.10.0-136.65.0.145.oe2203sp1.aarch64/vmlinux`。

2. 制作 BTF 文件

   基于获取到 vmlinux 文件来制作 BTF 文件。这一步可以在自己的环境里操作。首先，需要安装相关的依赖包：

   ```bash
   # 说明：dwarves 包中包含 pahole 命令，llvm 包中包含 llvm-objcopy 命令
   yum install -y llvm dwarves
   ```

   执行下面的命令行，生成 BTF 文件。

   ```bash
   kernel_version=4.19.90-2112.8.0.0131.oe1.aarch64  # 说明：这里需要替换成目标内核版本，可通过 uname -r 命令获取
   pahole -J vmlinux
   llvm-objcopy --only-section=.BTF --set-section-flags .BTF=alloc,readonly --strip-all vmlinux ${kernel_version}.btf
   strip -x ${kernel_version}.btf
   ```

   生成的 BTF 文件名称为`<kernel_version>.btf`格式，其中 `<kernel_version>`为目标机器的内核版本，可通过 `uname -r` 命令获取。

### 2. 下载 gala-gopher 容器镜像

#### 在线下载

gala-gopher 容器镜像已归档到 <https://hub.oepkgs.net/> 仓库中，可通过如下命令获取。

```bash
# 获取 aarch64 架构的镜像
docker pull hub.oepkgs.net/a-ops/gala-gopher-profiling-aarch64:latest
# 获取 x86_64 架构的镜像
docker pull hub.oepkgs.net/a-ops/gala-gopher-profiling-x86_64:latest
```

#### 离线下载

若无法通过在线下载的方式下载容器镜像，可联系我（何秀军 00465007）获取压缩包。

拿到压缩包后，放到目标机器上，解压并加载容器镜像，命令行如下：

```bash
tar -zxvf gala-gopher-profiling-aarch64.tar.gz
docker load < gala-gopher-profiling-aarch64.tar
```

### 3. 启动 gala-gopher 容器

容器启动命令：

```shell
docker run -d --name gala-gopher-profiling --privileged --pid=host --network=host -v /:/host -v /etc/localtime:/etc/localtime:ro -v /sys:/sys -v /usr/lib/debug:/usr/lib/debug -v /var/lib/docker:/var/lib/docker -v /tmp/$(uname -r).btf:/opt/gala-gopher/btf/$(uname -r).btf -e GOPHER_HOST_PATH=/host gala-gopher-profiling-aarch64:latest
```

启动配置参数说明：

+ `-v /tmp/$(uname -r).btf:/opt/gala-gopher/btf/$(uname -r).btf` ：如果内核支持 BTF，则删除该配置即可。如果内核不支持 BTF，则需要将前面准备好的 BTF 文件拷贝到目标机器上，并将 `/tmp/$(uname -r).btf` 替换为对应的路径。
+ `gala-gopher-profiling-aarch64-0426` ：gala-gopher容器对应的tag，替换成实际下载的tag。

探针启动：

+ `container_id` 为需要观测的容器 id
+ 分别启动 sli 和 container 探针

```bash
curl -X PUT http://localhost:9999/sli -d json='{"cmd":{"check_cmd":""},"snoopers":{"container_id":[""]},"params":{"report_period":5},"state":"running"}'
```

```bash
curl -X PUT http://localhost:9999/container -d json='{"cmd":{"check_cmd":""},"snoopers":{"container_id":[""]},"params":{"report_period":5},"state":"running"}'
```

探针关闭

```bash
curl -X PUT http://localhost:9999/sli -d json='{"state": "stopped"}'
```

```bash
curl -X PUT http://localhost:9999/container -d json='{"state": "stopped"}'
```

## 部署 gala-anteater

源码部署：

```bash
# 请指定分支为 930eulercopilot
git clone https://gitee.com/GS-Stephen_Curry/gala-anteater.git
```

安装部署请参考 <https://gitee.com/openeuler/gala-anteater>
(请留意python版本导致执行setup.sh install报错)

镜像部署：

```bash
docker pull hub.oepkgs.net/a-ops/gala-anteater:2.0.2
```

`/etc/gala-anteater/config/gala-anteater.yaml` 中 Kafka 和 Prometheus 的 `server` 和 `port` 需要按照实际部署修改，`model_topic`、`meta_topic`、`group_id` 自定义

```yaml
Kafka:
  server: "xxxx"
  port: "xxxx"
  model_topic: "xxxx" # 自定义，与rca配置中保持一致
  meta_topic: "xxxx" # 自定义，与rca配置中保持一致
  group_id: "xxxx" # 自定义，与rca配置中保持一致
  # auth_type: plaintext/sasl_plaintext, please set "" for no auth
  auth_type: ""
  username: ""
  password: ""

Prometheus:
  server: "xxxx"
  port: "xxxx"
  steps: "5"
```

gala-anteater 中模型的训练依赖于 gala-gopher 采集的数据，因此请保证 gala-gopher 探针正常运行至少24小时，在运行 gala-anteater。

## 部署 gala-ops

每个中间件的大致介绍：

kafka ： 一个数据库中间件， 分布式数据分流作用， 可以配置为当前的管理节点。

prometheus：性能监控， 配置需要监控的生产节点 ip list。

直接通过yum install安装kafka和prometheus，可参照安装脚本 <https://portrait.gitee.com/openeuler/gala-docs/blob/master/deploy/download_offline_res.sh#>

只需要参照其中 kafka 和 prometheus 的安装即可

## 部署 euler-copilot-rca

镜像拉取

```bash
docker pull hub.oepkgs.net/a-ops/euler-copilot-rca:0.9.1
```

+ 修改 `config/config.json` 文件，配置 gala-gopher 镜像的 `container_id` 以及 `ip`，Kafka 和 Prometheus 的 `ip` 和 `port`（与上述 gala-anteater 配置保持一致）

```yaml
"gopher_container_id": "xxxx", # gala-gopher的容器id
    "remote_host": "xxxx" # gala-gopher的部署机器ip
  },
  "kafka": {
    "server": "xxxx",
    "port": "xxxx",
    "storage_topic": "usad_intermediate_results",
    "anteater_result_topic": "xxxx",
    "rca_result_topic": "xxxx",
    "meta_topic": "xxxx"
  },
  "prometheus": {
    "server": "xxxx",
    "port": "xxxx",
    "steps": 5
  },
```
