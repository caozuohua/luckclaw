# Luckclaw 
[![Stargazers](https://img.shields.io/github/stars/caozuohua/luckclaw?style=flat-square)](https://github.com/caozuohua/luckclaw/stargazers)
[![Issues](https://img.shields.io/github/issues/caozuohua/luckclaw?style=flat-square)](https://github.com/caozuohua/luckclaw/issues)
[![MIT License](https://img.shields.io/github/license/caozuohua/luckclaw?style=flat-square)](https://github.com/caozuohua/luckclaw/blob/main/LICENSE)

**Luckclaw** is a minimalist, open-source AI agent designed specifically for the individual developer. It runs on a Google Cloud VPS and acts as your personal assistant for managing your digital footprint across your blog, GitHub repositories, and the VPS itself.

Built with Python and leveraging the power of Google's Agent Platform and Lark for communication, Luckclaw aims to be the perfect, low-maintenance sidekick for your creative and development workflows.

### Core Philosophy

*   **Simplicity:** No complex dashboards. Just chat with it.
*   **Ownership:** You host it, you control it. It runs on your own VPS.
*   **Extensibility:** Easily create new tools and capabilities using simple Python or shell scripts.
*   **Focus:** Built for developers, by a developer (and his AI assistant). It automates the tedious parts of a developer's life.

### Key Features

*   **Blog Management**: Write, publish, and manage your Hugo-based blog directly from the chat.
*   **GitHub Operations**: Initialize repositories, manage files, and perform common GitHub tasks.
*   **VPS Control**: Execute shell commands, manage system services, and install software on your VPS.
*   **Self-Evolution**: Luckclaw can remember key information, update its own system prompt, and even create new tools for itself.

### Architecture

```
lark-agent/
├── main.py              # Main entry point, just starts the agent
├── config.py            # Centralized configuration management
├── lark/
│   ├── client.py        # Send/receive messages, file uploads
│   └── handler.py       # Event handling, command routing
├── agent/
│   ├── base.py          # LLM abstraction layer (supports model switching)
│   ├── gemini.py        # Gemini implementation
│   └── claude.py        # Claude implementation (NEW)
├── tools/
│   ├── registry.py      # Tool registry (core of the plugin system)
│   ├── builtin/         # Built-in tools
│   │   ├── shell.py
│   │   ├── blog.py
│   │   ├── github.py
│   │   ├── memory.py
│   │   └── system.py
│   └── custom/          # Tools created by the agent itself (dynamically loaded)
│       └── *.py
├── memory/
│   └── store.py         # Unified storage layer
└── .env
```

### Hot Tags & Keywords

`#AI` `#Agent` `#LLM` `#OpenSource` `#DeveloperTool` `#Python` `#GoogleCloud` `#VPS` `#GitHub` `#Blog` `#Automation` `#SelfHosted` `#Lark` `#Gemini` `#Claude` `#Minimalist`

---
*This README was generated and pushed by Luckclaw itself.*
