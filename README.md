# NTQQ Chat Exporter

本地整理并导出 NTQQ 聊天记录的开源工具。

## 功能

- 从本地或手机导入的 `nt_msg.db` 开始处理
- 提取当前 QQ NT 环境所需的数据库密钥
- 解密并整理为可查询的 SQLite 数据库
- 按好友会话导出 TXT 和 HTML 文件
- 提供 Windows GUI 导出器与底层 Python 脚本

## 目录结构

```text
deps/
├─ nt_msg_db_util/     # 数据库解密、消息解析和导出
└─ qq-win-db-key/      # Windows NTQQ 密钥提取脚本
docs/                  # 使用说明
```

## 基本要求

- Windows 10/11
- 已安装并登录 QQ NT
- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- 与当前 QQ 版本匹配的 `wrapper.node`

首次运行 `uv run` 时需要联网安装 Python 依赖。

## 使用说明

完整流程见 [`docs/完整导出器使用说明.md`](docs/完整导出器使用说明.md)。

底层流程大致为：

```text
复制 nt_msg.db
    → 提取数据库 key
    → 去除 QQ 文件头
    → SQLCipher 解密
    → 解析消息
    → 导出 TXT / HTML
```

## 隐私与安全

- 本项目只处理用户主动选择的本地数据库文件。
- 数据库 key 只在运行期间使用，不写入仓库或导出文件。
- 请勿将 `nt_msg.db`、解密数据库、导出聊天记录、`uv-cache` 或个人 UID 提交到 GitHub。
- 本项目与腾讯 QQ 无官方关联。

## 免责声明

请仅处理你有权访问和保存的聊天数据，并遵守 QQ 服务条款及所在地法律法规。

