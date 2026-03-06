# OrbStack MCP Server

通过 MCP（Model Context Protocol）协议控制 OrbStack，让 AI 助手直接管理你的 Docker 容器、Linux 虚拟机和 Kubernetes 集群。

## 前置要求

- macOS（OrbStack 仅支持 macOS）
- [OrbStack](https://orbstack.dev/) 已安装
- Python >= 3.10
- `orb` 和 `docker` 命令在 PATH 中可用

## 安装

```bash
# 克隆或下载项目
cd orbstack-mcp

# 安装依赖
pip install -e .
```

## 使用方式

### 在 Claude Desktop 中配置

编辑 `~/Library/Application Support/Claude/claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "orbstack": {
      "command": "python",
      "args": ["-m", "orbstack_mcp.server"],
      "cwd": "/path/to/orbstack-mcp/src"
    }
  }
}
```

或者使用安装后的命令：

```json
{
  "mcpServers": {
    "orbstack": {
      "command": "orbstack-mcp"
    }
  }
}
```

### 在 Claude Code 中配置

```bash
claude mcp add orbstack -- python -m orbstack_mcp.server
```

## 可用工具

### 系统管理
| 工具 | 说明 |
|------|------|
| `orbstack_status` | 查看 OrbStack 运行状态 |
| `orbstack_version` | 获取版本信息 |
| `orbstack_start` | 启动 OrbStack |
| `orbstack_stop` | 停止 OrbStack |

### Linux 机器管理
| 工具 | 说明 |
|------|------|
| `orbstack_machine_list` | 列出所有 Linux 机器 |
| `orbstack_machine_create` | 创建新的 Linux 机器 |
| `orbstack_machine_start` | 启动 Linux 机器 |
| `orbstack_machine_stop` | 停止 Linux 机器 |
| `orbstack_machine_delete` | 删除 Linux 机器 |
| `orbstack_machine_info` | 查看机器详细信息 |
| `orbstack_machine_run` | 在机器中执行命令 |
| `orbstack_machine_push` | 推送文件到机器 |
| `orbstack_machine_pull` | 从机器拉取文件 |

### Docker 容器管理
| 工具 | 说明 |
|------|------|
| `orbstack_docker_ps` | 列出容器 |
| `orbstack_docker_run` | 运行新容器 |
| `orbstack_docker_stop` | 停止容器 |
| `orbstack_docker_rm` | 删除容器 |
| `orbstack_docker_restart` | 重启容器 |
| `orbstack_docker_logs` | 查看容器日志 |
| `orbstack_docker_exec` | 在容器中执行命令 |
| `orbstack_docker_images` | 列出本地镜像 |
| `orbstack_docker_pull` | 拉取镜像 |
| `orbstack_docker_inspect` | 查看容器详情 |

### Docker Compose
| 工具 | 说明 |
|------|------|
| `orbstack_compose_up` | 启动 Compose 项目 |
| `orbstack_compose_down` | 停止 Compose 项目 |
| `orbstack_compose_ps` | 查看 Compose 服务状态 |

### Kubernetes
| 工具 | 说明 |
|------|------|
| `orbstack_k8s_start` | 启动 K8s 集群 |
| `orbstack_k8s_stop` | 停止 K8s 集群 |
| `orbstack_k8s_status` | 查看 K8s 状态 |

## 架构说明

本 MCP 服务器通过封装 `orb` / `orbctl` / `docker` CLI 命令实现对 OrbStack 的控制。
使用 stdio 传输方式，适合本地集成场景。

## 许可证

MIT
