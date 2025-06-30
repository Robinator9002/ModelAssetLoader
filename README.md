The Problem

Tired of manually downloading .safetensors into stable-diffusion-webui/models/Lora/? Can't remember which models/checkpoints folder belongs to ComfyUI versus Forge? Spending more time organizing files than generating images?

We've been there. So we fixed it.
The Solution

M.A.L. (Model Asset Loader) is a powerful desktop application built to streamline the entire lifecycle of your AI assets. It serves as a central command center, connecting to popular sources like Hugging Face and downloading models directly into the correct, pre-configured folders for your favorite UI.

This project is under active and continuous development. We're building this in the open and shipping features weekly.
✨ Key Features

Feature
	

Status
	

Description

Universal Search
	

✅ Released
	

Find models from Hugging Face (and more soon!) with a single, clean interface.

Intelligent Downloads
	

✅ Released
	

M.A.L. knows the default folder structures for ComfyUI, A1111, ForgeUI, and you can define your own.

Fully Configurable
	

✅ Released
	

Point to any base folder and define custom relative paths for every model type. Your workflow, your rules.

Real-Time Tracking
	

✅ Released
	

A sleek, non-intrusive toast notification system keeps you updated on download progress without interrupting your workflow.

Secure & Atomic
	

✅ Released
	

Downloads are fail-safe to prevent corrupted files, and path resolution is securely locked to your chosen base directory.

Local File Manager
	

🚧 In Progress
	

A new view to browse, manage, and delete the models you've already downloaded.
🔭 The Vision: Our Roadmap

M.A.L. aims to be the essential hub for your entire local AI ecosystem. This is where we're headed:

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

🛠️ Tech Stack & Architecture

M.A.L. is built with a modern, fast, and reliable stack, running as a local client-server application to ensure maximum performance and responsiveness.

    Backend: A powerful and asynchronous API built with Python and FastAPI.

    Frontend: A beautiful, dynamic, and type-safe user interface built with React & TypeScript.

🤝 Contributing

This is a community-driven project, and we welcome contributions of all kinds! Whether you're a developer, a designer, or just an enthusiastic user with great ideas, we'd love for you to get involved.

    Find an Issue: Check out the Issues Tab to see our current needs, bugs, and feature requests.

    Fork & PR: Fork the repository, make your changes, and submit a pull request!

    Start a Discussion: Have an idea or a question? Open a new topic in the Discussions Tab.

📄 License

This project is licensed under the MIT License. See the LICENSE file for details.
