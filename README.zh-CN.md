[![English](https://img.shields.io/badge/English-555555?style=flat)](README.md) [![简体中文](https://img.shields.io/badge/简体中文-555555?style=flat)](README.zh-CN.md)

# privaudit

为使用 PipeWire 的 Linux 桌面记录本地麦克风和摄像头访问历史。privaudit 观察采集节点，记录开始和停止事件，方便事后查询；不会静音或修改音视频流配置。

![终端输出示例](docs/images/example-output.png)

## 环境与安装

需要 Linux、Python 3.9+、正在运行的 PipeWire 会话，以及 `PATH` 中可用的 `pw-dump`。不支持仅使用 PulseAudio 的系统或非 Linux 平台。Python 运行时仅依赖标准库，无需 root。

```bash
git clone https://github.com/zhuhroscar-tech/privaudit.git
cd privaudit
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

也可从 [Releases](https://github.com/zhuhroscar-tech/privaudit/releases) 下载 `privaudit.pyz`，运行 `python3 privaudit.pyz --help`。这种方式不需要 pip 安装，但仍需 PipeWire 和 Python。

## 快速上手

```bash
privaudit watch
# 在另一个终端中激活相同环境后运行：
privaudit status
privaudit history --since-hours 24
privaudit history --kind mic --app zoom
privaudit history --json
```

`watch` 在前台运行，每两秒轮询一次，按 Ctrl+C 停止。可用 `watch --interval 5` 调整间隔。`status` 直接查看当前节点，无需先启动 watcher；`history` 只能查询已经记录的事件。可选的登录自启动配置见[参考文档](docs/REFERENCE.md)。

## 隐私与限制

工具只读取 PipeWire 元数据，不读取音视频内容，不发起网络请求，不需要 root，也不会打开采集设备。JSONL 日志记录应用名称、可执行文件名、PID、节点 ID 和时间戳，默认路径为 `~/.local/share/privaudit/history.jsonl`。可为 `watch` 和 `history` 指定 `--log PATH`，或设置 `PRIVAUDIT_LOG`。

这是轮询式观察工具，不是安全隔离机制，也不保证审计记录完整。两次轮询之间的短暂事件、可见 PipeWire 节点之外的采集，以及 watcher 停止期间的活动，都可能遗漏。`pw-dump` 读取失败会被当作空快照处理，因此空的状态输出不能证明没有采集行为。应用活动信息敏感时，请妥善保护本地日志。

## 开发与卸载

运行 `python -m pytest -v`。[CI](.github/workflows/ci.yml)包含 Linux 集成测试和 zipapp 构建步骤。使用 `python -m pip uninstall privaudit` 卸载；历史日志不会自动删除。如配置了用户服务，应先停止服务。

[MIT 许可证](LICENSE)。
