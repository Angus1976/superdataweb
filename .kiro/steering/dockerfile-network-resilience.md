---
inclusion: fileMatch
fileMatchPattern: "**/Dockerfile*"
---

# Dockerfile 网络容错规则

用户网络环境不稳定，编写 Dockerfile 时必须遵守：

- `apt-get install` 命令使用 retry 循环（至少重试 3 次，间隔 sleep）
- `pip install` 命令加 `--retries 3 --timeout 60`
- 其他包管理器（npm、yarn 等）同样加 retry 参数
- 大文件下载使用 `curl --retry 3 --retry-delay 5` 或等效方式
