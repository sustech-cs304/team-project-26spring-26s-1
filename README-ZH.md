<div align="center">
  <img src="img/opencrab.png" alt="OpenCrab logo" width="96" />
  <h1>OpenCrab</h1>
  <p><strong>面向校园场景的桌面 AI 助手。</strong></p>
  <p>中文 <a href="./README.md">English</a></p>

  <p>
    <img alt="Vue" src="https://img.shields.io/badge/Vue-3-42b883?logo=vuedotjs&logoColor=white" />
    <img alt="Tauri" src="https://img.shields.io/badge/Tauri-2-24c8db?logo=tauri&logoColor=white" />
    <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.135-009688?logo=fastapi&logoColor=white" />
    <img alt="Python" src="https://img.shields.io/badge/Python-3.13-3776ab?logo=python&logoColor=white" />
    <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-5.9-3178c6?logo=typescript&logoColor=white" />
    <img alt="Rust" src="https://img.shields.io/badge/Rust-stable-b7410e?logo=rust&logoColor=white" />
  </p>
</div>

## 概览

现代学生的日常工作通常分散在聊天软件、文件夹、日历和任务工具之间。课程资料放在一处，截止日期放在另一处，而真正用来学习的助手又常常看不到本地文件或日程。

OpenCrab 将这些能力整合到一个桌面工作区中。它为学生提供一个本地优先的 AI 助手，可以聊天、读取文件、管理日历、自动执行重复任务，并复用技能，而不必在多个工具之间来回切换。

## 主要功能

- **流式 AI 聊天**：支持实时回复、工具调用展示和对话历史。
- **文件问答**：附加本地文档后，可结合文件上下文进行提问。
- **日历管理**：统一查看课程事件、提醒和自定义日程。
- **定时任务**：创建基于 prompt 或脚本的自动化任务，并按计划执行。
- **技能管理**：浏览、下载、上传并管理可复用的 agent 技能。
- **桌面集成**：通过 Tauri 以桌面应用形式运行，并支持原生系统集成。

## 获取应用

### 推荐：Releases

当仓库发布了构建产物后，优先从 [Releases 页面](https://github.com/sustech-cs304/team-project-26spring-26s-1/releases) 下载对应平台的安装包。

### 快速开始

1. 下载 release 版本，或者按照源码分支的 README 进行本地运行。
2. 打开应用并完成首次设置。
3. 配置模型提供方或本地模型端点。
4. 开始聊天、上传文件，或者打开日历和任务页面体验其他功能。

### 源码运行

项目按功能拆分到了不同分支，具体安装和运行说明请查看各分支 README：

- 前端客户端：[`frontend/README.md`](https://github.com/sustech-cs304/team-project-26spring-26s-1/blob/frontend/README.md)
- 后端运行时：[`backend-new/README.md`](https://github.com/sustech-cs304/team-project-26spring-26s-1/blob/backend-new/README.md)
- Skills Hub 管理服务：[`skillshub-admin/README.md`](https://github.com/sustech-cs304/team-project-26spring-26s-1/blob/skillshub-admin/README.md)

## 项目结构

- [`main`](https://github.com/sustech-cs304/team-project-26spring-26s-1/tree/main)：项目主页、提案/设计文档和发布工作流
- [`frontend`](https://github.com/sustech-cs304/team-project-26spring-26s-1/tree/frontend)：Vue 3 + Tauri 桌面客户端
- [`backend-new`](https://github.com/sustech-cs304/team-project-26spring-26s-1/tree/backend-new)：FastAPI agent 运行时、工具、持久化和 RAG
- [`skillshub-admin`](https://github.com/sustech-cs304/team-project-26spring-26s-1/tree/skillshub-admin)：技能提交、审核与管理服务

## RAG 模型兼容性

OpenCrab 的云端知识库使用 `BAAI/bge-m3` 作为 embedding 模型，使用 `BAAI/bge-reranker-v2-m3` 作为 rerank 模型。配置云端知识库相关的 embedding 和 rerank 模型时，请使用这两个模型，以保证检索结果和已发布索引兼容。

---

Copyright © OpenCrab Team
