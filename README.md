# OpenCrab Frontend

This branch contains the OpenCrab desktop client built with Vue 3, TypeScript, Vuetify, Vite, and Tauri 2.

The frontend is only one part of OpenCrab. For a complete local run, start the backend from the [`backend-new`](https://github.com/sustech-cs304/team-project-26spring-26s-1/tree/backend-new) branch first.

## Prerequisites

- Node.js 22 or newer
- npm
- Rust stable, installed through `rustup`
- OS build tools required by Tauri:
  - Windows: Microsoft C++ Build Tools
  - macOS: Xcode Command Line Tools
  - Linux: WebKitGTK and common build packages
- A running OpenCrab backend on `http://127.0.0.1:8000`

## Install

```bash
npm ci
```

## Backend Dependency

Run the backend from a checkout of the `backend-new` branch before starting the client:

```bash
uv run python -m agent.main --host 127.0.0.1 --port 8000
```

The frontend expects these backend defaults:

- API base URL: `http://127.0.0.1:8000/api`
- WebSocket base URL: `ws://127.0.0.1:8000`

The Skills Hub admin service from `skillshub-admin` is optional. Start it only when testing skill upload, review, approval, or download flows.

## Run Web Client

```bash
npm run dev
```

Open:

```text
http://localhost:3000
```

By default, the frontend calls the local backend at `http://127.0.0.1:8000/api`.

## Run Tauri Desktop Client

Start the backend first, then run:

```bash
npx tauri dev
```

For development, running the backend manually is the most reliable path. Packaged builds can start a bundled Python backend runtime when the release workflow stages `python-runtime` and backend resources.

## Environment Variables

Use these variables to point the client to another backend:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000/api
VITE_WS_BASE_URL=ws://127.0.0.1:8000
```

Windows PowerShell:

```powershell
$env:VITE_API_BASE_URL="http://127.0.0.1:8000/api"
$env:VITE_WS_BASE_URL="ws://127.0.0.1:8000"
npm run dev
```

## Build

Build web assets:

```bash
npm run build
```

Build a local Tauri package:

```bash
npx tauri build
```

Build artifacts are written under `src-tauri/target/`.

## Useful Scripts

- `npm run dev`: start the Vite dev server on port `3000`.
- `npm run build`: type-check and build frontend assets.
- `npm run preview`: preview the production web build.
- `npx tauri dev`: run the desktop app in development.
- `npx tauri build`: build a desktop package.

## Main Client Areas

- Chat: streaming agent conversations, attachments, tool-call display, and human-in-the-loop cards.
- Calendar: custom events, imported routines, source controls, and reminders.
- Tasks: scheduled automations, manual triggers, run history, and logs.
- Skills: browse, download, upload, and uninstall reusable agent skills.
- Settings and onboarding: model endpoints, campus credentials, notifications, and runtime preferences.
