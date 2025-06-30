M.A.L. - The Model Asset Loader

Tired of manually downloading .safetensors into stable-diffusion-webui/models/Lora/ or trying to remember which models/checkpoints folder belongs to ComfyUI vs. Forge? So were we.

M.A.L. (Model Asset Loader) is a desktop application built to streamline the entire lifecycle of your AI assets. It connects to popular sources like Hugging Face, lets you search for models, and downloads them directly into the correct, pre-configured folders for your favorite UI.

This project is under active development right now! We're building this in the open and shipping features weekly.
🚀 Key Features (So Far)

    Universal Search: Find models and resources from Hugging Face (with more sources coming soon!) from a single, clean interface.

    Intelligent Downloads: Download files directly to the right location. M.A.L. knows the default folder structures for ComfyUI, A1111, ForgeUI, and more.

    Fully Configurable: Don't like the defaults? Point M.A.L. to any base folder and define your own custom paths for every model type.

    Detailed Views: See a model's full README and browse all its files before you commit to downloading.

    Real-Time Download Manager: A sleek, non-intrusive toast notification system keeps you updated on download progress without interrupting your workflow.

    Secure & Robust: Built with a security-first mindset. Downloads are atomic (no corrupted files) and path resolution is locked to your base directory.

🔭 The Vision: Our Roadmap

M.A.L. is more than just a downloader. It's aiming to be the central hub for your entire local AI ecosystem. Here's where we're headed:

    Phase 1: Polish the Core (Now Underway)

        [x] Re-implement advanced search sorting and filtering.

        [ ] Complete a full UI/CSS cleanup for a polished, professional feel.

        [ ] Implement a Local Library Manager to view, manage, and delete files you've already downloaded.

    Phase 2: Environment Management

        [ ] Add functionality to download and manage the AI UIs themselves (ComfyUI, A1111, etc.).

        [ ] Integrate more model sources, with CivitAI as the next major target.

    Phase 3: The Platform

        [ ] Expand support to a wider range of applications, including LLM chat interfaces.

        [ ] Create comprehensive documentation on a dedicated website.

🛠️ Tech Stack

M.A.L. is built with a modern, fast, and reliable stack:

    Backend: Python with FastAPI for a high-performance, asynchronous API.

    Frontend: React & TypeScript for a robust, type-safe, and interactive user experience.

    Packaging: (Soon) Tauri to create a cross-platform desktop application.

🤝 Contributing

This is a community-driven project, and we welcome contributions of all kinds! Whether you're a developer, a designer, or just an enthusiastic user with great ideas, we'd love to have you.

    Check out the Issues Tab to see our current needs and bug reports.

    Fork the repository and submit a pull request!

    Have an idea? Start a new discussion in the Discussions Tab.

📄 License

This project is licensed under the MIT License. See the LICENSE file for details.
