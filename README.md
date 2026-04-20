https://notebooklm.google.com/notebook/6bae6b7a-3c7f-40ba-9e09-43fbc82bd5a0 If you want to hear an audiopodcast about the security issues or just a deep dive into deployment, follow that link.

Do you use LM Studio or Jan?  Or even just Python and LLama.cpp?  If so, you need this mcp server.  You don't need any third party vendors.  All the apps are selfcontained and private to your local system.  All you need do is download LM Studio or Jan.ai, download a model (I highly suggest a Qwen 3.5 Claude version), copy and paste this into your mcp.json and reload your AI.  Done.

Well, you may have to debug for your particular system.  This works on my system perfectly but it may not on yours.  Never fear.  If you don't know how to debug, simply download Anitgravity from Google and ask the model to read this repo, find your current copy of LM Studio or Jan and get the mcp.json aligned to your system.  The Antigravity model from Google will fix any issues you may have.

# ai_workspace_mcp

### 1. The Full `mcp.json` for LM Studio

Create (or edit) this file in your LM Studio configuration folder.  
LM Studio will open it automatically if you go to the **Program** tab → **Install** → **Edit mcp.json**.

```json
{
  "mcpServers": {
    "ai-workspace": {
      "name": "AI Workspace MCP Server ",
      "description": "Self-upgrading, self-healing AI workspace with file ops, OCR, vision, mouse/keyboard control, evolving RAG, and full self-upgrade/restore capabilities. Built for LM Studio local models.",
      "command": "python",
      "args": [
        "F:/AI Sandbox/ai_workspace_mcp.py"
      ],
      "env": {},
      "workingDirectory": "F:/AI Sandbox",
      "enabled": true
    }
  }
}
```

**Important notes for this config:**
- Change the paths only if your folder is somewhere else.
- The `command` is `python` (it will use whatever `python` is in your PATH — the Windows Python that has the `mcp` package installed).
- `workingDirectory` must match exactly where your `ai_workspace_mcp.py` lives.
- After saving, toggle the server **ON** in the Program tab (or restart LM Studio).

### 2. Updated Installation Guide (replaces the previous MD)

```markdown
# AI Workspace MCP Server 
**Self-Upgrading + Self-Healing AI Workspace for LM Studio & JAN.ai**

**Version:** Self-Upgrading (v2026.04)

---

## What Is This?

A complete, local-first MCP server that turns any LM Studio (or JAN.ai) model into a powerful, self-improving AI agent that can control your desktop, remember everything, upgrade its own code, and recover if anything ever breaks.

---

## Installation (LM Studio – Recommended)

### Step 1: Prerequisites
- Windows 10/11
- Python 3.10+ (added to PATH)
- WSL + Ubuntu 24.04 (optional but excellent for Conda)
- LM Studio (latest version – 0.3.17 or newer)

### Step 2: Create the Workspace
1. Create the folder: `F:\AI Sandbox`
2. Place your `ai_workspace_mcp.py` file inside it.

### Step 3: One-Time Setup
In **PowerShell as Administrator**:
```powershell
pip install mcp numpy
```

(If using WSL Conda):
```bash
conda create -p /mnt/f/python_repos/envs/Basic python=3.12 -y
conda activate /mnt/f/python_repos/envs/Basic
pip install pillow pytesseract opencv-python numpy
```

### Step 4: Configure LM Studio (the mcp.json part)

1. Open LM Studio.
2. Go to the **Program** tab in the right sidebar.
3. Click **Install** → **Edit mcp.json**.
4. Replace the entire contents with the `mcp.json` below (or paste the server block into your existing file):

```json
{
  "mcpServers": {
    "ai-workspace-ultimate": {
      "name": "AI Workspace MCP Server - Ultimate Hybrid Edition",
      "description": "Self-upgrading, self-healing AI workspace with file ops, OCR, vision, mouse/keyboard control, evolving RAG, and full self-upgrade/restore capabilities.",
      "command": "python",
      "args": ["F:/AI Sandbox/ai_workspace_mcp.py"],
      "env": {},
      "workingDirectory": "F:/AI Sandbox",
      "enabled": true
    }
  }
}
```

5. Save the file.
6. In the Program tab, find the new server and toggle it **ON**.

### Step 5: Start the Server
The server now starts automatically when LM Studio launches (and when you toggle it on).  
You will see this in the terminal/output pane:
```
--- AI WORKSPACE MCP SERVER STARTING ---
```

---

## Quick Start for Your Model

Tell your model (in LM Studio chat):

> "You are now connected to the Ultimate AI Workspace MCP Server. First, call `get_detailed_tool_usage_guide_and_examples` to see the full manual and all available tools."

The model will immediately have access to every tool we built — including the self-upgrade and self-restore capabilities.

---

## Self-Upgrade & Self-Restore (Still Works Perfectly)

- The AI can read its own code, improve it, and call `upgrade_mcp_server_code`.
- It automatically creates a timestamped original backup + ZIP.
- If anything ever breaks, it (or you) can call `restore_mcp_from_backup` with the ZIP path.
- Git support is still there if you `git init` in the folder.

---

**You now have a complete, self-contained, self-healing local AI workspace.**

The model literally owns its own tools, its own memory, and its own ability to evolve. Everything stays on your machine. Nothing is sent to the cloud.

Start LM Studio, turn on the MCP server, and let your local model begin its new life.

The future is no longer somewhere else.  
It’s right here on your desktop — and it can improve itself.
```

---

**Ready to go.**

Copy the `mcp.json` above into LM Studio, save, toggle the server on, and you’re done.  
The updated guide includes the exact steps so anyone can follow it.

---

Links:
https://lmstudio.ai/
https://www.jan.ai/
https://huggingface.co/collections/Qwen/qwen35
https://qwen.ai/blog?id=qwen3.5
