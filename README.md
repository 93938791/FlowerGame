# 🌸 FlowerGame Backend

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?style=for-the-badge&logo=fastapi&logoColor=white)

FlowerGame 的后端核心服务，负责游戏逻辑、资源管理及网络同步。

## 🚀 功能概览

- 🎮 **Minecraft 管理**：支持游戏登录（Microsoft Auth）、版本下载、模组安装及启动。
- 🔄 **数据同步**：集成 Syncthing 进行游戏存档和配置的自动同步。
- 🌐 **虚拟组网**：内置 Easytier 支持，轻松实现局域网联机。
- ⚡ **高性能 API**：基于 FastAPI 构建的异步接口。

## 🛠️ 快速开始

### 环境要求

- Python 3.12+
- Windows 系统

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行服务

```bash
python main.py
```

## 📂 核心模块

- `service/minecraft`: Minecraft 相关业务（登录、下载、启动）
- `service/syncthing`: 同步服务管理
- `service/easytier`: 组网服务管理
- `ui/`: 桌面端界面逻辑
- `utils/`: 通用工具类

## 📝 配置

应用配置位于 `config.py` 及相关配置文件中。

---
*Created for FlowerGame Project*
