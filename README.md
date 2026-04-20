# ai_workspace_mcp
```markdown
# AI Workspace MCP Server - Ultimate Hybrid Edition
**Self-Upgrading + Self-Healing AI Workspace for LM Studio & JAN.ai**

**Version:** Self-Upgrading (v2026.04)  
**Author:** Built for local AI agents that can improve themselves

---

## What Is This?

This is a **full-featured MCP (Model Context Protocol) server** that turns your local LLM (running in LM Studio or JAN.ai) into a powerful AI agent that can:

- Control your Windows desktop (mouse, keyboard, screenshots)
- Run Python code in Windows **or** WSL Conda environments
- Perform OCR on any screenshot
- Build an **evolving RAG** memory that survives restarts
- **Upgrade its own code** safely (with automatic backups)
- **Restore itself completely** if anything gets fucked up
- Read/write files, browse websites, and more

It is designed specifically for **smaller local models** (Qwen3 0.8B–8B, etc.) that are not as smart as commercial AIs. Every tool description contains explicit instructions so the model cannot easily make mistakes.

---

## Core Features

- **Hybrid Execution**: Windows native + WSL Ubuntu 24.04
- **Evolving RAG** – conversation memory that compresses and persists forever
- **Self-Upgrade Tool** – the AI can rewrite its own `.py` file
- **Self-Restore Tool** – one-click recovery from any backup ZIP
- **Git-aware Backups** – automatically commits originals to git if repo exists
- **Vision & Automation** – take screenshots, read text, click buttons, type, etc.
- **OCR Tool** – extract text from any image/screenshot

---

## Installation (LM Studio or JAN.ai)

### Step 1: Prerequisites
1. Windows 10/11
2. **Python 3.10+** installed on Windows (add to PATH)
3. **WSL + Ubuntu 24.04** (recommended but not required)
4. **Conda** installed in WSL (Miniforge or Anaconda)
5. LM Studio **or** JAN.ai running with a local model (recommended: `qwen3.5-0.8b` or `qwen3.5-4b`)

### Step 2: Download & Place Files
1. Create folder: `F:\AI Sandbox`
2. Save the latest `ai_workspace_mcp.py` into that folder (the file you just upgraded or the one provided).
3. (Optional but recommended) Initialize git in the folder:
   ```bash
   cd "F:\AI Sandbox"
   git init
   ```

### Step 3: Install Dependencies (one-time)
Open **PowerShell as Administrator** and run:
```powershell
pip install mcp numpy
```

In WSL (if using Conda environments):
```bash
conda create -p /mnt/f/python_repos/envs/Basic python=3.12 -y
conda activate /mnt/f/python_repos/envs/Basic
pip install pillow pytesseract opencv-python numpy
```

### Step 4: Run the MCP Server
**Option A – LM Studio (recommended)**
1. Start LM Studio
2. Go to **Local Inference Server** → start server on `http://192.168.56.1:31415`
3. In a separate terminal run:
   ```powershell
   cd "F:\AI Sandbox"
   python ai_workspace_mcp.py
   ```

**Option B – JAN.ai**
1. Start JAN.ai
2. Enable **MCP / Tool Use** in the model settings
3. Load the MCP server the same way (JAN.ai supports stdio MCP servers)

The terminal should show:
```
--- AI WORKSPACE MCP SERVER STARTING ---
```

Leave this terminal **open** – it is the MCP server.

---

## How Self-Upgrade & Self-Restore Work

### Upgrade Process (AI improves itself)
1. The AI reads the current code using `read_content_from_file_at_path`
2. It thinks of improvements
3. It calls **`upgrade_mcp_server_code`** with the **full new code**
4. The server:
   - Saves the **exact original** as `_ORIGINAL_YYYYMMDD_HHMMSS.py`
   - Commits it to git (if repo exists)
   - Creates `MCP_SELF_UPGRADE_BACKUP_YYYYMMDD_HHMMSS.zip`
   - Overwrites the `.py` file
5. You manually **restart** the Python script

### Restore Process (if upgrade breaks everything)
1. The AI (or you) calls **`restore_mcp_from_backup`** with the ZIP path
2. The server unzips the backup and replaces the current code with the working original
3. Restart the server

**You will always have a downloadable ZIP** of every previous version.

---

## All Tools (with exact usage for local AIs)

### 1. `ping`
**Purpose**: Health check  
**Special Note for Local AI**: Always use this first to confirm the server is alive.  
**Example call**:
```json
{"name": "ping"}
```

### 2. `get_detailed_tool_usage_guide_and_examples`
**Purpose**: Get this entire manual + latest examples  
**Special Note**: Call this whenever you feel unsure. It returns the most up-to-date instructions.

### 3. `upgrade_mcp_server_code`
**Purpose**: Let the AI upgrade its own code  
**Special Note for Local AI**: Always read the current file first, then send the **complete** new script.  
**Example**:
```json
{"name": "upgrade_mcp_server_code", "arguments": {"new_code": "#!/usr/bin/env python3\n...full code..."}}
```

### 4. `restore_mcp_from_backup`
**Purpose**: Fix a broken upgrade  
**Special Note**: Use the exact ZIP path returned by the upgrade tool.  
**Example**:
```json
{"name": "restore_mcp_from_backup", "arguments": {"zip_path": "F:/AI Sandbox/MCP_SELF_UPGRADE_BACKUP_20260420_124700.zip"}}
```

### 5. `compress_conversation_turn_to_rag`
**Purpose**: Add memory to the evolving RAG  
**Special Note**: Use this after every important conversation turn.

### 6. `query_evolving_rag`
**Purpose**: Retrieve past context

### 7. `get_rag_summary`
**Purpose**: See current compressed memory

(Full list of all 20+ tools with the same verbose "SPECIAL NOTE FOR LOCAL AI" is inside the server – just call `get_detailed_tool_usage_guide_and_examples` to see everything.)

---

## Recommended Workflow for the AI

1. Call `ping` → confirm server is alive
2. Call `get_detailed_tool_usage_guide_and_examples` → read instructions
3. Use `read_content_from_file_at_path` to see current MCP code
4. Decide on improvements
5. Call `upgrade_mcp_server_code` with new full code
6. Tell user: "Upgrade complete – please restart the MCP server"
7. (If something breaks) Call `restore_mcp_from_backup` with the ZIP

---

## Troubleshooting

**Server not responding?**  
→ Restart the Python script in the terminal.

**Upgrade failed?**  
→ The ZIP was still created. Use `restore_mcp_from_backup`.

**Path issues?**  
→ Always use full Windows paths (`F:/AI Sandbox/...`) or WSL paths (`/mnt/f/AI Sandbox/...`).

**Git not working?**  
→ It falls back to local + ZIP – still safe.

**Model keeps truncating code?**  
→ Tell it: "Output the **entire** file without any summarization."

---

## You now have a self-improving AI workspace.

The AI can literally evolve its own tools, fix its own bugs, and maintain perfect memory across sessions.

**Start the server, load it in LM Studio or JAN.ai, and tell the model:**

> "You are now running inside the Ultimate AI Workspace MCP Server. You can upgrade and restore yourself. Begin by calling `get_detailed_tool_usage_guide_and_examples`."

Enjoy your self-healing local AI agent!
```
