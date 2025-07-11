# 工作流中的MCP使用手册

# 前置操作

若用户发现在插件中心无法创建MCP服务,此时需要去后端手动给该用户添加管理员权限.

```
# 获取mongo-password的密码
kubectl get secret -n euler-copilot euler-copilot-database -oyaml
#将获取到的密码使用base64进行解密
echo {mongo_password} | base64 -d
# 此时获取到了进入mongodb的密码
# 然后需要进入mongodb容器
kubectl -n euler-copilot get pods
kubectl -n euler-copilot exec -it mongo-deploy-xxxxxx-xxxxxxx -- bash
# 然后替换为前面获取的mongodb的密码替换
mongosh "mongodb://euler_copilot:{your_secret}@localhost:27017/?directConnection=true&replicaSet=rs0"
use euler_copilot;
# 这里的id为下图所展示的id
db["user"].update({_id: "{your_id}"}, { $set: {is_admin: true }});
```

![id图片](./pictures/id图片.png)



## 1 注册MCP

### 1.1 在插件中心点击创建MCP服务

![创建MCP](./pictures/创建MCP.png)

### 1.2 填写MCP服务的相关信息

![填写MCP信息](./pictures/填写MCP信息.png)

上传图片,填写MCP名称和简介.

### 1.3 选择MCP类型以及填入MCP.json

以time-mcp-server为例

https://mcp.so/server/time/modelcontextprotocol,这是这个time-mcp的使用网址.

需要将MCP-server给的server config改成上面图片所给的格式,所以不需要更改,但这里time MCPserver给的server config为

```
{
  "mcp": {
    "servers": {
      "time": {
        "command": "uvx",
        "args": [
          "mcp-server-time",
          "--local-timezone=America/New_York"
        ]
      }
    }
  }
}
```

所以需要改造一下变成

```
{
  "command": "uvx",
  "args": ["mcp-server-time",
  "--local-timezone=America/New_York"],
  "env": {},
  "autoApprove": [],
  "autoInstall": true,
  "disabled": false
}
```

## 2 使用MCP

![复制MCPID信息](./pictures/复制MCPID信息.png)

完成后会有一行显示ID,需要复制.

当使用的时候还需要激活该MCP,点击上述激活按钮即可

### 2.1 创建工作流

![image-20250522173235997](./pictures/创建工作流步骤1.png)

![创建工作流步骤2](./pictures/创建工作流步骤2.png)

![创建工作流步骤3](./pictures/创建工作流步骤3.png)

![创建工作流步骤4](./pictures/创建工作流步骤4.png)

![填写MCP ID](./pictures/填写MCPID.png)

![调试MCP](./pictures/调试MCP.png)

![发布应用](./pictures/发布应用.png)

到此应用MCP的一个工作流应用就创建完成了.