****🤖 M.A.L. (Model Asset Loader)****

**Tired of manually downloading .safetensors? So was I.**

M.A.L. is a desktop application I'm building to streamline the entire lifecycle of your AI assets. It connects to popular sources like Hugging Face, lets you search for models, and downloads them directly into the correct, pre-configured folders for your favorite UI.

This project is under active development. I'm building this in the open and shipping features as often as possible!
🚀 Key Features

    Universal Search: Find models and resources from Hugging Face (with more sources coming soon!) from a single, clean interface.

    Intelligent Downloads: Download files directly to the right location. M.A.L. knows the default folder structures for ComfyUI, A1111, Forge, and more.

    Fully Configurable: Don't like the defaults? Point M.A.L. to any base folder and define your own custom paths for every model type.

    Detailed Views: See a model's full README and browse all its files before you commit to downloading.

    Real-Time Download Manager: A sleek, non-intrusive toast notification system keeps you updated on download progress without interrupting your workflow.

    Secure & Robust: Built with a security-first mindset. Downloads are atomic (no corrupted files) and path resolution is locked to your base directory.

**🔭 The Vision: My Roadmap**

M.A.L. is more than just a downloader. My goal is for it to be the central hub for your entire local AI ecosystem. Here's where I'm headed:

[x] Phase 1: Polish the Core (Already Finished)

    [x] Re-implement advanced search sorting and filtering.

    [x] Complete a full UI/CSS cleanup for a polished, professional feel.

    [x] Add an Download Sidebar, replacing the old Toasts, for better visibility and workflow.

[x] Phase 2: Environment Management (Finished)

    [x] Implement a Local Library Manager to view, manage, and delete files you've already downloaded.

    [x] Add functionality to download and manage the AI UIs themselves (ComfyUI, A1111, etc.).

    [x] Rework the Configuration and Installation Mechanics to fit the new Automation System.

    [x] Add Adoption Mechanic for Installation.

    [x] Fix the Installation Modal for Ui Installations

[x] Phase 2.5: Bugfixing (Finished)

    [x] Get the Cancellation of UI Downloads to work
    
    [x] Fix the Adoption Mechanics Analysis so it works for real now!

    [x] Fix the Start Functionality for Installed Uis

[ ] Phase 3: Improvements (Starting now)

    [ ] Overwork the UI Management to allow the user to change paths and stack more version of one ui

    [ ] Fix the start button for every individual AI and give better feedback during starting (including A1111 installation)

    [ ] Overwork Error Messages to be more descriptive

[ ] Phase 4: The Platform (Coming Soon, Very very Soon)

    [ ] Integrate more model sources, with CivitAI as the next major target.

    [ ] Expand support to a wider range of applications, including LLM chat interfaces.

    [ ] Create comprehensive documentation on a dedicated website.

**🛠️ Tech Stack**

M.A.L. is built with a modern, fast, and reliable stack, running as a local web application.

    Backend: Python with FastAPI for a high-performance, asynchronous API.

    Frontend: React & TypeScript for a robust, type-safe, and interactive user experience.

**🤝 Contributing**

This is a community-driven project, and contributions of all kinds are welcome! Whether you're a developer, a designer, or just an enthusiastic user with great ideas, I'd love to have your input.

    Check out the Issues Tab to see current needs and bug reports.

    Fork the repository and submit a pull request!

    Have an idea? Start a new discussion in the Discussions Tab.

**📄 License**

This project is licensed under the Apache License. See the LICENSE file for details.
