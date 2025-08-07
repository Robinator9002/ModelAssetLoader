# 🤖 M.A.L. (Model Asset Loader)

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=for-the-badge)

**Tired of manually downloading `.safetensors`? So was I.**

M.A.L. is a desktop application built to streamline the entire lifecycle of your AI assets. It connects to popular sources like **[Hugging Face]**, lets you search for models, and downloads them directly into the correct, pre-configured folders for your favorite UI.

With a robust backend and a polished, reactive frontend, M.A.L. has moved beyond its initial development phase and is now focused on refinement and feature expansion.

---

### 🚀 Key Features

-   **[Universal Search]**: Find models and resources from Hugging Face (with more sources coming soon!) from a single, clean interface.
-   **[Intelligent Downloads]**: Download files directly to the right location. M.A.L. knows the default folder structures for ComfyUI, A1111, Forge, and more.
-   **[Fully Configurable]**: Don't like the defaults? Point M.A.L. to any base folder and define your own custom paths for every model type.
-   **[Detailed Views]**: See a model's full README and browse all its files before you commit to downloading.
-   **[Real-Time Download Manager]**: A sleek sidebar keeps you updated on download, installation, and process progress without interrupting your workflow.
-   **[Environment Management]**: Install, manage, run, and even "adopt" existing installations of AI UIs like ComfyUI and A1111 directly within the app.
-   **[Secure & Robust]**: Built with a security-first mindset. Downloads are atomic (no corrupted files) and path resolution is locked to your base directory.

---

### 🔭 The Vision: Project Roadmap

M.A.L. is more than just a downloader. The goal is for it to be the central hub for your entire local AI ecosystem. Here's where we're at:

#### ✅ **Phase 1: Polish the Core** `(Finished)`

-   [x] Re-implement advanced search sorting and filtering.
-   [x] Complete a full UI/CSS cleanup for a polished, professional feel.
-   [x] Add a Download Sidebar for better visibility and workflow.

#### ✅ **Phase 2: Environment Management** `(Finished)`

-   [x] Implement a Local Library Manager to view, manage, and delete files.
-   [x] Add functionality to download and manage the AI UIs themselves.
-   [x] Rework Configuration and Installation Mechanics for the Automation System.
-   [x] Add Adoption Mechanic for existing installations.
-   [x] Implement robust cancellation for UI downloads and fix process start functionality.

#### ⏳ **Phase 3: Architectural Rework** `(Close to Finish)`

-   [x] Decomposed UI Management into specialized services (Process, Installation).
-   [x] Decomposed File Management into specialized services (Filesystem, Downloader).
-   [x] Refactored all API endpoints into domain-specific routers.
-   [x] Established a dedicated, reusable API service layer on the frontend.
-   [x] Implemented robust, decoupled state management with Zustand.
-   [ ] Formalize Dependency Injection with FastAPI `Depends`.
-   [ ] Abstract complex frontend logic into custom hooks.

#### 🎯 **Phase 4: Core Improvements** `(Starting Soon)`

-   [ ] Overwork UI Management to allow changing paths and stacking multiple versions of one UI.
-   [ ] Fix the start button for every individual AI and give better feedback during startup.
-   [ ] Overwork Error Messages to be more descriptive and user-friendly.

#### 🏁 **Phase 5: The M.A.L. Platform** `(Final Steps)`

-   [ ] Integrate more model sources, with **[CivitAI]** as the next major target.
-   [ ] Expand support to a wider range of applications, including LLM chat interfaces.
-   [ ] Create comprehensive documentation on a dedicated website.

---

### 🛠️ Tech Stack

M.A.L. is built with a modern, fast, and reliable stack, running as a local web application.

-   **Backend**: **[Python]** with **[FastAPI]** for a high-performance, asynchronous API.
-   **Frontend**: **[React]** & **[TypeScript]** for a robust, type-safe, and interactive user experience.

### 🤝 Contributing

This is a community-driven project, and contributions of all kinds are welcome! Whether you're a developer, a designer, or just an enthusiastic user with great ideas, I'd love to have your input.

-   Check out the **[Issues Tab]** to see current needs and bug reports.
-   **[Fork the repository]** and submit a pull request!
-   Have an idea? Start a new discussion in the **[Discussions Tab]**.

### 📄 License

This project is licensed under the **[Apache License 2.0]**. See the `LICENSE` file for details.
