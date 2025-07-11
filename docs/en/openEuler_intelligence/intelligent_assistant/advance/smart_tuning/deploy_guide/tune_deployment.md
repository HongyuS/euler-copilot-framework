# 智能调优部署指南

## 准备工作

+ 提前安装 [EulerCopilot 命令行（智能 Shell）客户端](../../../quick_start/smart_shell/user_guide/shell.md))

+ 被调优机器需要为 openEuler 22.03 LTS-SP3

+ 在需要被调优的机器上安装依赖

```bash
yum install -y sysstat perf
```

+ 被调优机器需要开启 SSH 22端口

## 编辑配置文件

修改values.yaml文件的tune部分，将 `enable` 字段改为 `True` ，并配置大模型设置、
Embedding模型文件地址、以及需要调优的机器和对应机器上的 mysql 的账号名以及密码

```bash
vim /home/euler-copilot-framework/deploy/chart/agents/values.yaml
```

```yaml
tune:
    # 【必填】是否启用智能调优Agent
    enabled: true
    # 镜像设置
    image:
      # 镜像仓库。留空则使用全局设置。
      registry: ""
      # 【必填】镜像名称
      name: euler-copilot-tune
      # 【必填】镜像标签
      tag: "0.9.1"
      # 拉取策略。留空则使用全局设置。
      imagePullPolicy: ""
    # 【必填】容器根目录只读
    readOnly: false
    # 性能限制设置
    resources: {}
    # Service设置
    service:
      # 【必填】Service类型，ClusterIP或NodePort
      type: ClusterIP
      nodePort: 
    # 大模型设置
    llm:
      # 【必填】模型地址（需要包含v1后缀）
      url: 
      # 【必填】模型名称
      name: ""
      # 【必填】模型API Key
      key: ""
      # 【必填】模型最大Token数
      max_tokens: 8096
    # 【必填】Embedding模型文件地址
    embedding: ""
    # 待优化机器信息
    machine:
      # 【必填】IP地址
      ip: ""
      # 【必填】Root用户密码
      # 注意：必需启用Root用户以密码形式SSH登录
      password: ""
    # 待优化应用设置
    mysql:
      # 【必填】数据库用户名
      user: "root"
      # 【必填】数据库密码
      password: ""
```

## 安装智能调优插件

```bash
helm install -n euler-copilot agents .
```

如果之前有执行过安装，则按下面指令更新插件服务

```bash
helm upgrade-n euler-copilot agents .
```

如果 framework未重启，则需要重启framework配置

```bash
kubectl delete pod framework-deploy-service-bb5b58678-jxzqr -n eulercopilot
```

## 测试

+ 查看 tune 的 pod 状态

  ```bash
  NAME                                             READY   STATUS    RESTARTS   AGE
  authhub-backend-deploy-authhub-64896f5cdc-m497f   2/2     Running   0          16d
  authhub-web-deploy-authhub-7c48695966-h8d2p       1/1     Running   0          17d
  pgsql-deploy-databases-86b4dc4899-ppltc           1/1     Running   0          17d
  redis-deploy-databases-f8866b56-kj9jz             1/1     Running   0          17d
  mysql-deploy-databases-57f5f94ccf-sbhzp           2/2     Running   0          17d
  framework-deploy-service-bb5b58678-jxzqr          2/2     Running   0          16d
  rag-deploy-service-5b7887644c-sm58z               2/2     Running   0          110m
  web-deploy-service-74fbf7999f-r46rg               1/1     Running   0          2d
  tune-deploy-agents-5d46bfdbd4-xph7b               1/1     Running   0          2d
  ```

+ pod启动失败排查办法
    + 检查 euler-copilot-tune 目录下的 openapi.yaml 中 `servers.url` 字段，确保调优服务的启动地址被正确设置
    + 检查 `$plugin_dir` 插件文件夹的路径是否配置正确，该变量位于 `deploy/chart/euler_copilot/values.yaml` 中的 `framework`模块，如果插件目录不存在，需新建该目录，并需要将该目录下的 euler-copilot-tune 文件夹放到 `$plugin_dir` 中。
    + 检查sglang的地址和key填写是否正确，该变量位于 `vim /home/euler-copilot-framework/deploy/chart/euler_copilot/values.yaml`

    ```yaml
      # 用于Function Call的模型
      scheduler:
        # 推理框架类型
        backend: sglang
        # 模型地址
        url: ""
        # 模型 API Key
        key: ""
      # 数据库设置
    ```
