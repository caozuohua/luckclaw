# luckclaw

Your personal AI assistant, deployed on a Google Cloud VPS (e2-micro). It can directly operate the server, manage blogs, emails, and GitHub repositories.

## Features

- **Direct Server Operation**: Execute shell commands on the VPS.
- **Content Management**: Create, update, and publish blog posts using Hugo.
- **GitHub Integration**: Manage repositories, files, and workflows.
- **Self-Evolution**: The agent can update its own system prompts and create new tools.
- **Extensible Tools**: A plug-in architecture allows for adding new capabilities on the fly.
- **Long-term Memory**: Remembers key information across sessions.

## Architecture

This project follows a modular architecture to separate concerns and allow for easy extension.

```
lark-agent/
├── main.py              # Entrypoint, responsible for startup
├── config.py            # Centralized configuration management
├── lark/
│   ├── client.py        # Send/receive messages, file uploads
│   └── handler.py       # Event handling and command routing
├── agent/
│   ├── base.py          # LLM call abstraction layer (supports model switching)
│   ├── gemini.py        # Gemini implementation
│   └── claude.py        # Claude implementation (new)
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
└── .env                 # Environment variables (gitignored)
```

### Core Components

- **`lark/`**: Handles all interactions with the Lark messenger platform.
- **`agent/`**: Contains the core logic for interacting with Large Language Models (LLMs). It features an abstraction layer that makes it simple to switch between different models like Gemini and Claude.
- **`tools/`**: The heart of the agent's capabilities. It uses a registry pattern to discover and manage tools. New functionalities can be added by simply dropping a Python script into the `builtin` or `custom` directories.
- **`memory/`**: Provides a persistent storage layer, allowing the agent to have long-term memory.
- **`config.py`**: A single source of truth for all configurations, making the system easy to manage and deploy.
