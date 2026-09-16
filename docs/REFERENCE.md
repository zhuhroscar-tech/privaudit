# Optional login startup / 可选登录自启动

[English README](../README.md) · [简体中文](../README.zh-CN.md)

To keep recording after login, create `~/.config/systemd/user/privaudit.service`. Set `ExecStart` to the **absolute path** of your installed executable (for a virtual environment, use its `bin/privaudit`). The example path must be replaced before use.

如需登录后持续记录，可创建以下用户服务。请将 `ExecStart` 替换为实际安装位置的**绝对路径**；使用虚拟环境时，指向该环境中的 `bin/privaudit`。

```ini
[Unit]
Description=privaudit mic/camera access logger

[Service]
ExecStart=/absolute/path/to/.venv/bin/privaudit watch
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now privaudit.service
systemctl --user status privaudit.service
```

Before uninstalling, stop and disable the service. This does not delete history.
卸载前先停止并禁用服务；这不会删除历史记录。

```bash
systemctl --user disable --now privaudit.service
```
