<div align="center">
  <img src="img/opencrab.png" alt="OpenCrab logo" width="96" />
  <h1>OpenCrab</h1>
  <p><strong>A local-first AI agent desktop app for campus workflows.</strong></p>

  <p>
    <img alt="Vue" src="https://img.shields.io/badge/Vue-3-42b883?logo=vuedotjs&logoColor=white" />
    <img alt="Tauri" src="https://img.shields.io/badge/Tauri-2-24c8db?logo=tauri&logoColor=white" />
    <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.135-009688?logo=fastapi&logoColor=white" />
    <img alt="Python" src="https://img.shields.io/badge/Python-3.13-3776ab?logo=python&logoColor=white" />
    <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-5.9-3178c6?logo=typescript&logoColor=white" />
    <img alt="Rust" src="https://img.shields.io/badge/Rust-stable-b7410e?logo=rust&logoColor=white" />
  </p>
</div>

## Overview

OpenCrab combines a Vue/Tauri desktop client with a FastAPI Python agent runtime. The system supports streaming AI conversations, local state, file-aware retrieval, calendar workflows, scheduled tasks, notifications, and downloadable skills.

This `main` branch is the project landing page. Implementation code is maintained in separate source branches, each with its own setup instructions.

## Modules and Branches

- [`main`](https://github.com/sustech-cs304/team-project-26spring-26s-1/tree/main): project hub for the README, proposal/design documents, and CI/CD workflows.
- [`frontend`](https://github.com/sustech-cs304/team-project-26spring-26s-1/tree/frontend): Vue 3, Vuetify, TypeScript, and Tauri desktop client.
- [`backend-new`](https://github.com/sustech-cs304/team-project-26spring-26s-1/tree/backend-new): FastAPI agent runtime, API server, tools, persistence, and RAG workflows.
- [`skillshub-admin`](https://github.com/sustech-cs304/team-project-26spring-26s-1/tree/skillshub-admin): Skills Hub service for skill submission, review, approval, download, and admin pages.

## Setup Guides

Use the README in each source branch for module-specific installation and run commands:

- Backend API: [`backend-new/README.md`](https://github.com/sustech-cs304/team-project-26spring-26s-1/blob/backend-new/README.md)
- Frontend and Tauri client: [`frontend/README.md`](https://github.com/sustech-cs304/team-project-26spring-26s-1/blob/frontend/README.md)
- Skills Hub admin service: [`skillshub-admin/README.md`](https://github.com/sustech-cs304/team-project-26spring-26s-1/blob/skillshub-admin/README.md)

Typical local run order:

1. Start the backend API from the `backend-new` branch.
2. Start the frontend client from the `frontend` branch.
3. Start the Skills Hub admin service from `skillshub-admin` only when testing skill upload/review flows.
4. Open the desktop or web client and complete onboarding/settings.

## Key Features

- AI chat with streaming responses, conversation history, message restart, file attachments, tool-call cards, and human-in-the-loop confirmations.
- Agent runtime with FastAPI, LangGraph, SQLite persistence, checkpoint recovery, tools, skills, and configurable model providers.
- Files and RAG workflows for uploads, file parsing, knowledge-base sync, and retrieval during conversations.
- Calendar support for custom events, course/routine events, CAS/TIS/Blackboard credentials, reminders, and source controls.
- Task automation with cron schedules, manual triggers, script/prompt modes, environment variables, run history, and live logs.
- Skills Hub workflows for browsing, upload, review, approval, download, uninstall, and local skill management.
- Desktop integration through Tauri, including tray menu, global shortcut, deep links, local notifications, and packaged backend sidecar support.

## Using the Client

After the backend and frontend are running:

1. Complete onboarding and settings with model endpoints and campus credentials.
2. Open the chat page and send a request to the agent.
3. Attach a document in chat when the request needs file context.
4. Use Calendar to review imported course events and create custom events.
5. Use Tasks to create scheduled automations, trigger runs manually, and inspect logs.
6. Use Skills to browse, download, upload, or uninstall reusable agent skills.

## Screenshots

Final UI screenshots will be added here after the current client UI is finalized.

## CI/CD

- [`Tauri Desktop Release`](https://github.com/sustech-cs304/team-project-26spring-26s-1/blob/main/.github/workflows/tauri-release.yml) packages Windows, Linux, and macOS desktop artifacts from configurable frontend/backend refs.
- [`Code Metrics`](https://github.com/sustech-cs304/team-project-26spring-26s-1/blob/main/.github/workflows/code-metrics.yml) reports LOC, source-file count, cyclomatic complexity, and dependency counts for `frontend` and `backend-new`.

## Resources

- Project proposal: [proposal-team1.md](proposal-team1.md)
- Backend OpenAPI module specs: [`backend-new/spec/modules`](https://github.com/sustech-cs304/team-project-26spring-26s-1/tree/backend-new/spec/modules)
- Frontend source: [`frontend/src`](https://github.com/sustech-cs304/team-project-26spring-26s-1/tree/frontend/src)
- Backend source: [`backend-new/src/agent`](https://github.com/sustech-cs304/team-project-26spring-26s-1/tree/backend-new/src/agent)
- Skills Hub admin source: [`skillshub-admin`](https://github.com/sustech-cs304/team-project-26spring-26s-1/tree/skillshub-admin)

## License

This is a course project repository. Add a formal license file before public redistribution.
