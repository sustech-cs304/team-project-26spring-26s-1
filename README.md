
# Vuetify 4 + Tauri Desktop App

This repository contains a desktop application built with [Vuetify 4](https://vuetifyjs.com/) (Vue 3 UI framework) and [Tauri](https://tauri.app/) (cross-platform desktop application framework).

This setup allows you to build highly responsive, modern desktop applications using web technologies while leveraging a lightweight, native Rust backend.

## 📦 Prerequisites

Before you begin, ensure you have the following installed on your machine:

1. **Node.js** (v18 or higher recommended)
2. **Rust** (Install via [rustup](https://rustup.rs/))
3. **OS-Specific Build Tools**:
* **Windows**: Visual Studio C++ Build Tools.
* **macOS**: Xcode Command Line Tools (`xcode-select --install`).
* **Linux**: WebKit2GTK, build-essential, curl, wget, etc. (Check Tauri Linux setup guide).



## 📂 Project Structure

* `/src`: Contains the Vue 3 + Vuetify 4 frontend codebase.
* `/src-tauri`: Contains the Rust backend code, Tauri configurations, and platform-specific assets (icons, etc.).
* `vite.config.js` / `vite.config.ts`: Frontend bundler configuration.
* `src-tauri/tauri.conf.json`: Core configuration for the Tauri desktop window and build settings.

## 🚀 Getting Started

1. **Clone the repository** (if applicable) and navigate to the project root.
2. **Install frontend dependencies**:
```bash
npm install

```


*(Note: If you use `yarn` or `pnpm`, swap out the npm commands accordingly.)*

## 🛠️ Development Workflow

To start the development server. This command will automatically spin up the Vite development server (for Vuetify) and open the native Tauri desktop window.

```bash
npx tauri dev

```

*Note: The first time you run this, it will take some time as Rust downloads and compiles the backend crates.*

### Important Configuration Sync

If you change your frontend dev server port (default is usually `3000` or `5173`), ensure you update the `build.devPath` in your `src-tauri/tauri.conf.json` to match:

```json
"build": {
  "beforeDevCommand": "npm run dev",
  "beforeBuildCommand": "npm run build",
  "devPath": "http://localhost:3000", 
  "distDir": "../dist"
}

```

## 🏗️ Building for Production

To package your application into a native executable (e.g., `.exe` for Windows, `.dmg` / `.app` for macOS, `.AppImage` / `.deb` for Linux):

```bash
npx tauri build

```

This command will:

1. Run the frontend build command (`npm run build` by default) to compile the Vuetify project into the `dist` folder.
2. Compile the Rust backend in release mode.
3. Bundle everything into an installer and executable located in `src-tauri/target/release/bundle/`.

## 📜 Available NPM Scripts

For convenience, you can add these scripts to your `package.json`:

```json
"scripts": {
  "dev": "vite",
  "build": "vite build",
  "tauri": "tauri",
  "app:dev": "tauri dev",
  "app:build": "tauri build"
}

```

Then you can simply run `npm run app:dev` or `npm run app:build`.
