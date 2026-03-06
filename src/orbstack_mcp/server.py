#!/usr/bin/env python3
"""
OrbStack MCP Server

通过 MCP 协议控制 OrbStack，支持管理 Docker 容器、Linux 虚拟机和 Kubernetes 集群。
仅适用于 macOS 上安装了 OrbStack 的环境。
"""

import asyncio
import json
import shutil
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

# ============================================================
# 初始化 MCP 服务器
# ============================================================
mcp = FastMCP("orbstack_mcp")


# ============================================================
# 通用枚举和工具函数
# ============================================================
class ResponseFormat(str, Enum):
    """输出格式"""
    MARKDOWN = "markdown"
    JSON = "json"


async def _run_command(cmd: List[str], timeout: int = 30) -> tuple[int, str, str]:
    """执行系统命令并返回 (returncode, stdout, stderr)"""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
        return (
            process.returncode or 0,
            stdout.decode("utf-8", errors="replace").strip(),
            stderr.decode("utf-8", errors="replace").strip(),
        )
    except asyncio.TimeoutError:
        return 1, "", f"命令超时（{timeout}秒）: {' '.join(cmd)}"
    except FileNotFoundError:
        return 1, "", f"命令未找到: {cmd[0]}。请确保 OrbStack 已安装并且 orb 命令在 PATH 中。"
    except Exception as e:
        return 1, "", f"执行命令失败: {e}"


async def _run_orb(args: List[str], timeout: int = 30) -> tuple[int, str, str]:
    """执行 orb 命令"""
    return await _run_command(["orb"] + args, timeout=timeout)


async def _run_docker(args: List[str], timeout: int = 60) -> tuple[int, str, str]:
    """执行 docker 命令"""
    return await _run_command(["docker"] + args, timeout=timeout)


def _format_error(stderr: str, suggestion: str = "") -> str:
    """格式化错误信息"""
    msg = f"错误: {stderr}"
    if suggestion:
        msg += f"\n建议: {suggestion}"
    return msg


def _check_orb_available() -> bool:
    """检查 orb 命令是否可用"""
    return shutil.which("orb") is not None


# ============================================================
# 输入模型定义
# ============================================================

# --- 系统管理 ---
class EmptyInput(BaseModel):
    """无参数输入"""
    model_config = ConfigDict(extra="forbid")


# --- Linux 机器管理 ---
class MachineCreateInput(BaseModel):
    """创建 Linux 机器的输入参数"""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    distro: str = Field(
        ...,
        description="Linux 发行版名称，如 ubuntu, debian, fedora, arch, alpine 等",
        min_length=1,
        max_length=50,
    )
    name: Optional[str] = Field(
        default=None,
        description="机器名称，不指定则自动生成",
        max_length=100,
    )
    arch: Optional[str] = Field(
        default=None,
        description="CPU 架构：amd64 或 arm64，默认为宿主机架构",
    )


class MachineNameInput(BaseModel):
    """需要机器名称的输入参数"""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(
        ...,
        description="Linux 机器的名称",
        min_length=1,
        max_length=100,
    )


class MachineRunInput(BaseModel):
    """在 Linux 机器中执行命令的输入参数"""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    command: str = Field(
        ...,
        description="要执行的命令，如 'uname -a', 'ls -la /home' 等",
        min_length=1,
    )
    machine: Optional[str] = Field(
        default=None,
        description="目标机器名称，不指定则使用默认机器",
    )
    user: Optional[str] = Field(
        default=None,
        description="执行命令的用户，如 root",
    )


class MachineFileTransferInput(BaseModel):
    """文件传输的输入参数"""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source: str = Field(
        ...,
        description="源文件路径",
        min_length=1,
    )
    destination: Optional[str] = Field(
        default=None,
        description="目标路径，不指定则使用当前目录",
    )
    machine: Optional[str] = Field(
        default=None,
        description="目标机器名称，不指定则使用默认机器",
    )


# --- Docker 容器管理 ---
class DockerPsInput(BaseModel):
    """列出 Docker 容器的输入参数"""
    model_config = ConfigDict(extra="forbid")

    all: bool = Field(
        default=False,
        description="是否显示所有容器（包括已停止的），默认只显示运行中的",
    )


class DockerRunInput(BaseModel):
    """运行 Docker 容器的输入参数"""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    image: str = Field(
        ...,
        description="Docker 镜像名称，如 nginx:latest, ubuntu:22.04",
        min_length=1,
    )
    name: Optional[str] = Field(
        default=None,
        description="容器名称",
    )
    ports: Optional[List[str]] = Field(
        default=None,
        description="端口映射列表，如 ['8080:80', '443:443']",
    )
    volumes: Optional[List[str]] = Field(
        default=None,
        description="卷挂载列表，如 ['/host/path:/container/path']",
    )
    env: Optional[List[str]] = Field(
        default=None,
        description="环境变量列表，如 ['KEY=VALUE']",
    )
    detach: bool = Field(
        default=True,
        description="是否后台运行，默认为 True",
    )
    command: Optional[str] = Field(
        default=None,
        description="容器启动后执行的命令",
    )
    platform: Optional[str] = Field(
        default=None,
        description="指定平台架构，如 linux/amd64, linux/arm64",
    )


class DockerContainerInput(BaseModel):
    """需要容器标识的输入参数"""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    container: str = Field(
        ...,
        description="容器 ID 或名称",
        min_length=1,
    )


class DockerLogsInput(BaseModel):
    """获取容器日志的输入参数"""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    container: str = Field(
        ...,
        description="容器 ID 或名称",
        min_length=1,
    )
    tail: Optional[int] = Field(
        default=100,
        description="显示最后 N 行日志",
        ge=1,
        le=5000,
    )
    follow: bool = Field(
        default=False,
        description="是否持续输出日志（注意：MCP 环境下建议设为 False）",
    )


class DockerExecInput(BaseModel):
    """在容器中执行命令的输入参数"""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    container: str = Field(
        ...,
        description="容器 ID 或名称",
        min_length=1,
    )
    command: str = Field(
        ...,
        description="要执行的命令，如 'ls -la', 'cat /etc/os-release'",
        min_length=1,
    )


class DockerImageInput(BaseModel):
    """Docker 镜像相关输入"""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    image: str = Field(
        ...,
        description="镜像名称，如 nginx:latest, ubuntu:22.04",
        min_length=1,
    )


# ============================================================
# 工具实现 - 系统管理
# ============================================================

@mcp.tool(
    name="orbstack_status",
    annotations={
        "title": "OrbStack 状态查询",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def orbstack_status() -> str:
    """获取 OrbStack 的运行状态信息。

    返回 OrbStack 是否正在运行、版本等基本状态。

    Returns:
        str: OrbStack 状态信息
    """
    code, stdout, stderr = await _run_orb(["status"])
    if code != 0:
        return _format_error(stderr, "请确认 OrbStack 已安装: brew install orbstack")
    return f"OrbStack 状态:\n{stdout}"


@mcp.tool(
    name="orbstack_version",
    annotations={
        "title": "OrbStack 版本信息",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def orbstack_version() -> str:
    """获取 OrbStack 版本号。

    Returns:
        str: OrbStack 版本信息
    """
    code, stdout, stderr = await _run_orb(["version"])
    if code != 0:
        return _format_error(stderr)
    return f"OrbStack 版本: {stdout}"


@mcp.tool(
    name="orbstack_start",
    annotations={
        "title": "启动 OrbStack",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def orbstack_start() -> str:
    """启动 OrbStack 服务。

    如果 OrbStack 已在运行，此操作无副作用。

    Returns:
        str: 启动结果
    """
    code, stdout, stderr = await _run_orb(["start"])
    if code != 0:
        return _format_error(stderr)
    return "OrbStack 已启动" + (f"\n{stdout}" if stdout else "")


@mcp.tool(
    name="orbstack_stop",
    annotations={
        "title": "停止 OrbStack",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def orbstack_stop() -> str:
    """停止 OrbStack 服务。

    这将停止所有运行中的容器和 Linux 机器。

    Returns:
        str: 停止结果
    """
    code, stdout, stderr = await _run_orb(["stop"])
    if code != 0:
        return _format_error(stderr)
    return "OrbStack 已停止" + (f"\n{stdout}" if stdout else "")


# ============================================================
# 工具实现 - Linux 机器管理
# ============================================================

@mcp.tool(
    name="orbstack_machine_list",
    annotations={
        "title": "列出 Linux 机器",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def orbstack_machine_list() -> str:
    """列出所有 OrbStack Linux 机器及其状态。

    显示机器名称、发行版、架构和运行状态。

    Returns:
        str: 机器列表信息
    """
    code, stdout, stderr = await _run_orb(["list"])
    if code != 0:
        return _format_error(stderr)
    if not stdout:
        return "当前没有 Linux 机器。使用 orbstack_machine_create 创建一个。"
    return f"Linux 机器列表:\n{stdout}"


@mcp.tool(
    name="orbstack_machine_create",
    annotations={
        "title": "创建 Linux 机器",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def orbstack_machine_create(params: MachineCreateInput) -> str:
    """创建一个新的 Linux 虚拟机。

    支持 ubuntu, debian, fedora, arch, alpine 等多种发行版。
    在 Apple Silicon 上可通过 arch 参数指定 amd64 来运行 Intel 架构。

    Args:
        params: 创建参数，包括发行版名称、可选的机器名和架构

    Returns:
        str: 创建结果
    """
    args = ["create"]
    if params.arch:
        args.extend(["--arch", params.arch])
    args.append(params.distro)
    if params.name:
        args.append(params.name)

    code, stdout, stderr = await _run_orb(args, timeout=120)
    if code != 0:
        return _format_error(
            stderr,
            "可用发行版: ubuntu, debian, fedora, arch, alpine, centos, rocky, opensuse 等",
        )
    name = params.name or params.distro
    return f"Linux 机器 '{name}' 创建成功！\n{stdout}" if stdout else f"Linux 机器 '{name}' 创建成功！"


@mcp.tool(
    name="orbstack_machine_start",
    annotations={
        "title": "启动 Linux 机器",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def orbstack_machine_start(params: MachineNameInput) -> str:
    """启动指定的 Linux 机器。

    Args:
        params: 包含机器名称

    Returns:
        str: 启动结果
    """
    code, stdout, stderr = await _run_orb(["start", params.name])
    if code != 0:
        return _format_error(stderr, "使用 orbstack_machine_list 查看可用机器")
    return f"机器 '{params.name}' 已启动"


@mcp.tool(
    name="orbstack_machine_stop",
    annotations={
        "title": "停止 Linux 机器",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def orbstack_machine_stop(params: MachineNameInput) -> str:
    """停止指定的 Linux 机器。

    Args:
        params: 包含机器名称

    Returns:
        str: 停止结果
    """
    code, stdout, stderr = await _run_orb(["stop", params.name])
    if code != 0:
        return _format_error(stderr)
    return f"机器 '{params.name}' 已停止"


@mcp.tool(
    name="orbstack_machine_delete",
    annotations={
        "title": "删除 Linux 机器",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def orbstack_machine_delete(params: MachineNameInput) -> str:
    """删除指定的 Linux 机器。

    警告: 此操作不可撤销，机器中的所有数据将被永久删除。

    Args:
        params: 包含机器名称

    Returns:
        str: 删除结果
    """
    code, stdout, stderr = await _run_orb(["delete", "-f", params.name])
    if code != 0:
        return _format_error(stderr)
    return f"机器 '{params.name}' 已删除"


@mcp.tool(
    name="orbstack_machine_info",
    annotations={
        "title": "查看 Linux 机器详情",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def orbstack_machine_info(params: MachineNameInput) -> str:
    """获取指定 Linux 机器的详细信息。

    包括发行版、架构、状态、IP 地址等。

    Args:
        params: 包含机器名称

    Returns:
        str: 机器详细信息
    """
    code, stdout, stderr = await _run_orb(["info", params.name])
    if code != 0:
        return _format_error(stderr)
    return f"机器 '{params.name}' 详情:\n{stdout}"


@mcp.tool(
    name="orbstack_machine_run",
    annotations={
        "title": "在 Linux 机器中执行命令",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def orbstack_machine_run(params: MachineRunInput) -> str:
    """在 Linux 机器中执行命令并返回输出。

    可以指定目标机器和执行用户。不指定机器时使用默认机器。

    Args:
        params: 包含要执行的命令、可选的机器名和用户

    Returns:
        str: 命令执行输出
    """
    args = []
    if params.machine:
        args.extend(["-m", params.machine])
    if params.user:
        args.extend(["-u", params.user])

    # orb 命令直接接受要运行的命令
    args.extend(["run", "--"] + params.command.split())

    code, stdout, stderr = await _run_command(["orbctl"] + args, timeout=60)
    if code != 0:
        return _format_error(stderr or stdout)
    return stdout if stdout else "(命令执行完毕，无输出)"


@mcp.tool(
    name="orbstack_machine_push",
    annotations={
        "title": "推送文件到 Linux 机器",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def orbstack_machine_push(params: MachineFileTransferInput) -> str:
    """将文件从 macOS 推送到 Linux 机器。

    Args:
        params: 包含源文件路径、可选的目标路径和机器名

    Returns:
        str: 传输结果
    """
    args = ["push"]
    if params.machine:
        args.extend(["-m", params.machine])
    args.append(params.source)
    if params.destination:
        args.append(params.destination)

    code, stdout, stderr = await _run_orb(args)
    if code != 0:
        return _format_error(stderr)
    return f"文件已推送: {params.source}" + (f" -> {params.destination}" if params.destination else "")


@mcp.tool(
    name="orbstack_machine_pull",
    annotations={
        "title": "从 Linux 机器拉取文件",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def orbstack_machine_pull(params: MachineFileTransferInput) -> str:
    """从 Linux 机器拉取文件到 macOS。

    Args:
        params: 包含源文件路径、可选的目标路径和机器名

    Returns:
        str: 传输结果
    """
    args = ["pull"]
    if params.machine:
        args.extend(["-m", params.machine])
    args.append(params.source)
    if params.destination:
        args.append(params.destination)

    code, stdout, stderr = await _run_orb(args)
    if code != 0:
        return _format_error(stderr)
    return f"文件已拉取: {params.source}" + (f" -> {params.destination}" if params.destination else "")


# ============================================================
# 工具实现 - Docker 容器管理
# ============================================================

@mcp.tool(
    name="orbstack_docker_ps",
    annotations={
        "title": "列出 Docker 容器",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def orbstack_docker_ps(params: DockerPsInput) -> str:
    """列出 Docker 容器。

    默认只显示运行中的容器，设置 all=True 显示全部。

    Args:
        params: 包含是否显示所有容器的选项

    Returns:
        str: 容器列表（格式化表格）
    """
    args = ["ps", "--format", "table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"]
    if params.all:
        args.append("-a")

    code, stdout, stderr = await _run_docker(args)
    if code != 0:
        return _format_error(stderr, "请确认 OrbStack 正在运行: orbstack_start")
    if not stdout or stdout.count("\n") == 0:
        return "当前没有运行中的容器。" + (" 使用 --all 查看所有容器。" if not params.all else "")
    return f"Docker 容器:\n{stdout}"


@mcp.tool(
    name="orbstack_docker_run",
    annotations={
        "title": "运行 Docker 容器",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def orbstack_docker_run(params: DockerRunInput) -> str:
    """创建并运行一个新的 Docker 容器。

    支持端口映射、卷挂载、环境变量等配置。

    Args:
        params: 容器运行参数

    Returns:
        str: 容器 ID 或运行输出
    """
    args = ["run"]
    if params.detach:
        args.append("-d")
    if params.name:
        args.extend(["--name", params.name])
    if params.platform:
        args.extend(["--platform", params.platform])
    if params.ports:
        for port in params.ports:
            args.extend(["-p", port])
    if params.volumes:
        for vol in params.volumes:
            args.extend(["-v", vol])
    if params.env:
        for e in params.env:
            args.extend(["-e", e])
    args.append(params.image)
    if params.command:
        args.extend(params.command.split())

    code, stdout, stderr = await _run_docker(args, timeout=120)
    if code != 0:
        return _format_error(stderr)
    container_id = stdout[:12] if len(stdout) >= 12 else stdout
    display_name = params.name or container_id
    return f"容器 '{display_name}' 已启动\n容器ID: {container_id}"


@mcp.tool(
    name="orbstack_docker_stop",
    annotations={
        "title": "停止 Docker 容器",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def orbstack_docker_stop(params: DockerContainerInput) -> str:
    """停止运行中的 Docker 容器。

    Args:
        params: 包含容器 ID 或名称

    Returns:
        str: 停止结果
    """
    code, stdout, stderr = await _run_docker(["stop", params.container])
    if code != 0:
        return _format_error(stderr, "使用 orbstack_docker_ps 查看运行中的容器")
    return f"容器 '{params.container}' 已停止"


@mcp.tool(
    name="orbstack_docker_rm",
    annotations={
        "title": "删除 Docker 容器",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def orbstack_docker_rm(params: DockerContainerInput) -> str:
    """删除 Docker 容器。

    容器必须已停止才能删除。如需强制删除运行中的容器请先停止。

    Args:
        params: 包含容器 ID 或名称

    Returns:
        str: 删除结果
    """
    code, stdout, stderr = await _run_docker(["rm", params.container])
    if code != 0:
        if "running" in stderr.lower() or "is running" in stderr.lower():
            return _format_error(stderr, "容器仍在运行，请先使用 orbstack_docker_stop 停止容器")
        return _format_error(stderr)
    return f"容器 '{params.container}' 已删除"


@mcp.tool(
    name="orbstack_docker_logs",
    annotations={
        "title": "查看容器日志",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def orbstack_docker_logs(params: DockerLogsInput) -> str:
    """获取 Docker 容器的日志输出。

    Args:
        params: 包含容器标识和日志行数

    Returns:
        str: 容器日志
    """
    args = ["logs", "--tail", str(params.tail), params.container]
    code, stdout, stderr = await _run_docker(args)
    if code != 0:
        return _format_error(stderr)
    output = stdout or stderr  # 有些程序输出到 stderr
    return f"容器 '{params.container}' 日志（最后 {params.tail} 行）:\n{output}" if output else "（无日志输出）"


@mcp.tool(
    name="orbstack_docker_exec",
    annotations={
        "title": "在容器中执行命令",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def orbstack_docker_exec(params: DockerExecInput) -> str:
    """在运行中的 Docker 容器中执行命令。

    Args:
        params: 包含容器标识和要执行的命令

    Returns:
        str: 命令输出
    """
    args = ["exec", params.container] + params.command.split()
    code, stdout, stderr = await _run_docker(args)
    if code != 0:
        return _format_error(stderr or stdout)
    return stdout if stdout else "（命令执行完毕，无输出）"


@mcp.tool(
    name="orbstack_docker_images",
    annotations={
        "title": "列出 Docker 镜像",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def orbstack_docker_images() -> str:
    """列出本地所有 Docker 镜像。

    Returns:
        str: 镜像列表（格式化表格）
    """
    args = ["images", "--format", "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}\t{{.CreatedSince}}"]
    code, stdout, stderr = await _run_docker(args)
    if code != 0:
        return _format_error(stderr)
    if not stdout:
        return "本地没有 Docker 镜像。"
    return f"Docker 镜像:\n{stdout}"


@mcp.tool(
    name="orbstack_docker_pull",
    annotations={
        "title": "拉取 Docker 镜像",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def orbstack_docker_pull(params: DockerImageInput) -> str:
    """从镜像仓库拉取 Docker 镜像。

    Args:
        params: 包含镜像名称

    Returns:
        str: 拉取结果
    """
    code, stdout, stderr = await _run_docker(["pull", params.image], timeout=300)
    if code != 0:
        return _format_error(stderr, "请检查镜像名称是否正确")
    return f"镜像 '{params.image}' 拉取成功\n{stdout}"


@mcp.tool(
    name="orbstack_docker_restart",
    annotations={
        "title": "重启 Docker 容器",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def orbstack_docker_restart(params: DockerContainerInput) -> str:
    """重启 Docker 容器。

    Args:
        params: 包含容器 ID 或名称

    Returns:
        str: 重启结果
    """
    code, stdout, stderr = await _run_docker(["restart", params.container])
    if code != 0:
        return _format_error(stderr)
    return f"容器 '{params.container}' 已重启"


@mcp.tool(
    name="orbstack_docker_inspect",
    annotations={
        "title": "查看容器详情",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def orbstack_docker_inspect(params: DockerContainerInput) -> str:
    """查看 Docker 容器的详细配置和状态信息。

    返回 JSON 格式的完整容器信息，包括网络、挂载、环境变量等。

    Args:
        params: 包含容器 ID 或名称

    Returns:
        str: 容器详细信息（JSON）
    """
    code, stdout, stderr = await _run_docker(["inspect", params.container])
    if code != 0:
        return _format_error(stderr)
    # 尝试美化 JSON 输出
    try:
        data = json.loads(stdout)
        if isinstance(data, list) and len(data) == 1:
            data = data[0]
        # 提取关键信息
        summary = {
            "Name": data.get("Name", ""),
            "State": data.get("State", {}).get("Status", ""),
            "Image": data.get("Config", {}).get("Image", ""),
            "Created": data.get("Created", ""),
            "Ports": data.get("NetworkSettings", {}).get("Ports", {}),
            "Mounts": [
                {"Source": m.get("Source"), "Destination": m.get("Destination")}
                for m in data.get("Mounts", [])
            ],
            "Env": data.get("Config", {}).get("Env", []),
            "Networks": list(data.get("NetworkSettings", {}).get("Networks", {}).keys()),
        }
        return f"容器 '{params.container}' 详情:\n{json.dumps(summary, indent=2, ensure_ascii=False)}"
    except (json.JSONDecodeError, KeyError, TypeError):
        return f"容器 '{params.container}' 详情:\n{stdout[:3000]}"


# ============================================================
# 工具实现 - Kubernetes 管理
# ============================================================

@mcp.tool(
    name="orbstack_k8s_start",
    annotations={
        "title": "启动 Kubernetes",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def orbstack_k8s_start() -> str:
    """启动 OrbStack 内置的 Kubernetes 集群。

    OrbStack 提供轻量级的单节点 K8s 集群。

    Returns:
        str: 启动结果
    """
    code, stdout, stderr = await _run_orb(["k8s", "start"], timeout=120)
    if code != 0:
        return _format_error(stderr)
    return "Kubernetes 集群已启动" + (f"\n{stdout}" if stdout else "")


@mcp.tool(
    name="orbstack_k8s_stop",
    annotations={
        "title": "停止 Kubernetes",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def orbstack_k8s_stop() -> str:
    """停止 OrbStack 的 Kubernetes 集群。

    Returns:
        str: 停止结果
    """
    code, stdout, stderr = await _run_orb(["k8s", "stop"])
    if code != 0:
        return _format_error(stderr)
    return "Kubernetes 集群已停止" + (f"\n{stdout}" if stdout else "")


@mcp.tool(
    name="orbstack_k8s_status",
    annotations={
        "title": "Kubernetes 状态",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def orbstack_k8s_status() -> str:
    """查看 OrbStack Kubernetes 集群的状态。

    Returns:
        str: K8s 集群状态
    """
    code, stdout, stderr = await _run_orb(["k8s", "status"])
    if code != 0:
        return _format_error(stderr)
    return f"Kubernetes 状态:\n{stdout}" if stdout else "Kubernetes 状态: 未运行"


# ============================================================
# Docker Compose 支持
# ============================================================

class DockerComposeInput(BaseModel):
    """Docker Compose 操作的输入参数"""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    project_dir: str = Field(
        ...,
        description="docker-compose.yml 所在目录的路径",
        min_length=1,
    )
    service: Optional[str] = Field(
        default=None,
        description="指定服务名称，不指定则操作所有服务",
    )


@mcp.tool(
    name="orbstack_compose_up",
    annotations={
        "title": "启动 Compose 项目",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def orbstack_compose_up(params: DockerComposeInput) -> str:
    """使用 Docker Compose 启动服务。

    在指定目录中执行 docker compose up -d。

    Args:
        params: 包含项目目录和可选的服务名

    Returns:
        str: 启动结果
    """
    args = ["compose", "-f", f"{params.project_dir}/docker-compose.yml", "up", "-d"]
    if params.service:
        args.append(params.service)

    code, stdout, stderr = await _run_docker(args, timeout=180)
    if code != 0:
        return _format_error(stderr)
    return f"Compose 项目已启动\n{stdout or stderr}"


@mcp.tool(
    name="orbstack_compose_down",
    annotations={
        "title": "停止 Compose 项目",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def orbstack_compose_down(params: DockerComposeInput) -> str:
    """使用 Docker Compose 停止并移除服务。

    Args:
        params: 包含项目目录

    Returns:
        str: 停止结果
    """
    args = ["compose", "-f", f"{params.project_dir}/docker-compose.yml", "down"]

    code, stdout, stderr = await _run_docker(args, timeout=120)
    if code != 0:
        return _format_error(stderr)
    return f"Compose 项目已停止\n{stdout or stderr}"


@mcp.tool(
    name="orbstack_compose_ps",
    annotations={
        "title": "查看 Compose 服务状态",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def orbstack_compose_ps(params: DockerComposeInput) -> str:
    """查看 Docker Compose 项目中各服务的运行状态。

    Args:
        params: 包含项目目录

    Returns:
        str: 服务状态列表
    """
    args = ["compose", "-f", f"{params.project_dir}/docker-compose.yml", "ps"]

    code, stdout, stderr = await _run_docker(args)
    if code != 0:
        return _format_error(stderr)
    return f"Compose 服务状态:\n{stdout}" if stdout else "没有运行中的 Compose 服务"


# ============================================================
# 入口点
# ============================================================

def main():
    """MCP 服务器入口"""
    mcp.run()


if __name__ == "__main__":
    main()
