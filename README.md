# Agent Skills

A collection of reusable skills for **Antigravity (`agy`)** and compatible AI coding agents.

## Available Skills

| Skill | Description |
| :--- | :--- |
| [`codmod-translator`](./codmod-translator/SKILL.md) | Reviews or generates any Google Cloud Migration Center App Modernization Assessment (`codmod`) report, interactively selects the target modernization strategy and Google Cloud backing services, constructs a 4-phase `/goal` execution plan, and refactors + deploys the workload end-to-end. |

## Repository Structure

```text
skills/
├── README.md
└── codmod-translator/
    ├── SKILL.md
    ├── references/
    │   └── gcp-deployment-patterns.md
    └── scripts/
        └── extract_codmod_report.py
```

## Installation

### Install Globally (All Workspaces)

```bash
mkdir -p ~/.gemini/config/skills
cp -R codmod-translator ~/.gemini/config/skills/
```

### Install in a Specific Project Workspace

```bash
mkdir -p /path/to/your-project/.agents/skills
cp -R codmod-translator /path/to/your-project/.agents/skills/
```
