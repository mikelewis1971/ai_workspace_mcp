#!/usr/bin/env python3
"""
AI Workspace MCP Server - Hybrid Edition with SCREENSHOT OCR TOOL
===============================================================
- File Operations: Windows Native
- Code Execution: Hybrid (Windows/WSL)
- AI Capabilities: LangChain Integration
- NEW: Screen Shot OCR for text extraction from images
- Design: Explicit Tool Naming for Small Models
"""

import asyncio
import subprocess
import os
import sys
import json
import re
import urllib.request
import time
import tempfile
print("--- AI WORKSPACE MCP SERVER STARTING ---", file=sys.stderr)
from pathlib import Path
from typing import Any, Optional
import platform

# === ENVIRONMENT DETECTION ===
def is_wsl():
    try:
        uname = platform.uname()
        return "microsoft" in uname.release.lower() or "wsl" in uname.release.lower() or platform.system() == "Linux"
    except:
        return False

IS_WSL = is_wsl()
IS_WINDOWS = platform.system() == "Windows"

# MCP imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# === CONFIGURATION ===
if IS_WSL:
    WORKSPACE = Path("/mnt/f/AI Sandbox")
    WSL_ENVS_PATH = "/mnt/f/python_repos/envs"
else:
    WORKSPACE = Path("F:/AI Sandbox")
    WSL_ENVS_PATH = "F:/python_repos/envs"

WORKSPACE.mkdir(parents=True, exist_ok=True)

app = Server("ai-workspace-ultimate")

# === HELPER FUNCTIONS ===

# Unicode symbols that crash Windows cp1252 → ASCII replacements
_UNICODE_FIXES = {
    '\u2713': '[OK]', '\u2714': '[OK]', '\u2715': '[FAIL]', '\u2716': '[FAIL]',
    '\u2717': '[X]', '\u2718': '[X]', '\u2022': '*', '\u2023': '>',
    '\u25cf': '*', '\u25cb': 'o', '\u25a0': '#', '\u25a1': '[]',
    '\u2605': '*', '\u2606': '*', '\u25b6': '>', '\u25c0': '<',
    '\u2192': '->', '\u2190': '<-', '\u2191': '^', '\u2193': 'v',
    '\u2026': '...', '\u2014': '--', '\u2013': '-',
    '\u201c': '"', '\u201d': '"', '\u2018': "'", '\u2019': "'",
}

def sanitize_code_for_windows(code: str) -> str:
    """Pre-process AI-generated code to prevent common Windows execution failures."""
    # 1. Replace unicode symbols that crash cp1252
    for char, replacement in _UNICODE_FIXES.items():
        code = code.replace(char, replacement)
    
    # 2. Inject UTF-8 stdout reconfiguration at the very top
    utf8_header = (
        "import sys, io\n"
        "if hasattr(sys.stdout, 'reconfigure'):\n"
        "    sys.stdout.reconfigure(encoding='utf-8', errors='replace')\n"
        "    sys.stderr.reconfigure(encoding='utf-8', errors='replace')\n"
    )
    code = utf8_header + code
    return code

def sanitize_code_for_wsl(code: str) -> str:
    """Pre-process AI-generated code for WSL execution."""
    # Just ensure no raw Windows paths leak into the code
    return code


# === PATH CONVERSION UTILITIES ===

class PathConverter:
    """Converts between WSL and Windows paths correctly."""
    @staticmethod
    def to_wsl(path: str) -> str:
        p = str(path).replace("\\", "/")
        # Clean up common path corruption
        while "//" in p: p = p.replace("//", "/")
        if p.lower().startswith("f:"):
            return "/mnt/f" + p[2:]
        elif p.lower().startswith("c:"):
            return "/mnt/c" + p[2:]
        return p

    @staticmethod
    def to_win(path: str) -> str:
        p = str(path).replace("/", "\\")
        # Handle WSL mount points
        if p.lower().startswith("\\mnt\\f"):
            return "F:" + p[6:]
        elif p.lower().startswith("\\mnt\\c"):
            return "C:" + p[6:]
        return p

    @staticmethod
    def normalize(p: str) -> str:
        """Removes duplicate drive/path patterns."""
        p = str(p).replace("\\", "/")
        if "/AI Sandbox/AI Sandbox/" in p:
            p = p.replace("/AI Sandbox/AI Sandbox/", "/AI Sandbox/")
        return p

    @staticmethod
    def is_absolute(p: str) -> bool:
        p = str(p)
        return p.startswith("/") or (len(p) > 1 and p[1] == ":")

def resolve_path(p: str) -> Path:
    p = PathConverter.normalize(p)
    if PathConverter.is_absolute(p):
        # Convert Windows absolute to WSL if we are on WSL
        if IS_WSL and (len(p) > 1 and p[1] == ":"):
            return Path(PathConverter.to_wsl(p))
        return Path(p)
    return WORKSPACE / p

def get_cwd_for_env(env: str) -> str:
    """Returns WORKSPACE in the correct format for the target environment."""
    if env == "wsl":
        return PathConverter.to_wsl(str(WORKSPACE))
    return PathConverter.to_win(str(WORKSPACE))

def exec_cmd(command: str, timeout: int = 120, cwd: Optional[str] = None) -> tuple[int, str]:
    try:
        # Use cmd.exe on WSL, cmd on Windows
        exe = "cmd.exe" if IS_WSL else "cmd"
        target_cwd = cwd if cwd else PathConverter.to_win(str(WORKSPACE))
        
        # In WSL, cmd.exe doesn't like Linux paths as CWD.
        # It's better to cd inside the command string.
        # We must escape the target_cwd for CMD
        safe_cwd = target_cwd.replace("/", "\\")
        full_command = f'cd /d "{safe_cwd}" && {command}'
        
        result = subprocess.run(
            [exe, "/c", full_command],
            capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        return -1, str(e)

def exec_wsl(command: str, timeout: int = 120, cwd: Optional[str] = None) -> tuple[int, str]:
    try:
        # Always use WSL-style path for Bash CWD
        target_cwd = cwd if cwd else PathConverter.to_wsl(str(WORKSPACE))
        
        if IS_WSL:
            wsl_cmd = ["bash", "-lc", f"cd '{target_cwd}' && {command}"]
        else:
            wsl_cmd = ["wsl", "-d", "Ubuntu-24.04", "--", "bash", "-lc", f"cd '{target_cwd}' && {command}"]
            
        result = subprocess.run(
            wsl_cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        return -1, str(e)

def exec_powershell(command: str, timeout: int = 120, cwd: Optional[str] = None) -> tuple[int, str]:
    """Execute PowerShell by writing to a temp .ps1 file. Eliminates all inline escaping issues."""
    try:
        exe = "powershell.exe" if IS_WSL else "powershell"
        target_cwd = cwd if cwd else PathConverter.to_win(str(WORKSPACE))
        
        # Write to temp .ps1 file to avoid ALL escaping issues
        ps1_path = WORKSPACE / "_mcp_temp_cmd.ps1"
        full_script = f"Set-Location '{target_cwd}'\n{command}"
        with open(ps1_path, "w", encoding="utf-8") as f:
            f.write(full_script)
        
        ps1_win_path = PathConverter.to_win(str(ps1_path))
        
        result = subprocess.run(
            [exe, "-ExecutionPolicy", "Bypass", "-File", ps1_win_path],
            capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        return -1, str(e)


def get_windows_python() -> str:
    if not IS_WSL:
        return sys.executable
    
    # Common paths for Windows Python when called from WSL
    paths = [
        "python.exe",
        "/mnt/c/Users/Impac/AppData/Local/Programs/Python/Python312/python.exe",
        "/mnt/c/Windows/python.exe"
    ]
    for p in paths:
        if IS_WSL:
            check_path = p if p.startswith("/") else f"/mnt/c/Windows/System32/{p}"
            if os.path.exists(check_path) or subprocess.run(["which", p], capture_output=True).returncode == 0:
                return p
    return "python.exe" # Fallback

def get_wsl_python() -> str:
    """Returns the path to the Python interpreter in WSL."""
    if IS_WSL:
        return sys.executable
    return "python3" # Fallback

# === TOOL DEFINITIONS ===

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="ping",
            description="A simple health check to verify the server is responding.",
            inputSchema={"type": "object", "properties": {}}
        ),

        Tool(
            name="get_detailed_tool_usage_guide_and_examples",
            description="RETURNS A FULL MANUAL. Call this to learn how to use any tool. Returns markdown examples for everything.",
            inputSchema={"type": "object", "properties": {}}
        ),

        Tool(
            name="list_files_in_directory",
            description="LISTS all files and folders in a specific directory. Use this to see what files exist.\nEXAMPLE: list_files_in_directory(directory='F:/AI Sandbox')",
            inputSchema={
                "type": "object",
                "properties": {"directory": {"type": "string", "description": "Path to list. Default: Workspace root."}}
            }
        ),
        
        Tool(
            name="write_content_to_file_at_path",
            description=(
                "CREATES or OVERWRITES a file at the specified path with the provided content.\n"
                "JS TIP: Use ES6+, camelCase, and JSDoc. Ensure error handling (try/catch) for async ops.\n"
                "EXAMPLE: write_content_to_file_at_path(path='main.js', content='const run = async () => { try { ... } catch (e) { console.error(e); } }; run();')"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path (e.g. 'script.py')"},
                    "content": {"type": "string", "description": "Full text content of the file"}
                },
                "required": ["path", "content"]
            }
        ),
        
        Tool(
            name="read_content_from_file_at_path",
            description="READS the full content of a file.\nEXAMPLE: read_content_from_file_at_path(path='data.csv')",
            inputSchema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        ),

        Tool(
            name="execute_python_code_in_wsl_conda_environment",
            description="RUNS Python code inside a WSL (Linux) Conda Environment.\nUSE THIS FOR: Data Science, ML, complex imports.\nEXAMPLE: execute_python_code_in_wsl_conda_environment(code='import pandas', conda_env='Basic')",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code block"},
                    "file_path": {"type": "string", "description": "Path to .py file"},
                    "conda_env": {"type": "string", "description": "Environment name (e.g., 'Basic', 'base')"}
                }
            }
        ),
        
        Tool(
            name="execute_python_code_in_windows_native_environment",
            description="RUNS Python code directly on Windows (System Python).\nUSE THIS FOR: Simple scripts, Windows file automation.\nEXAMPLE: execute_python_code_in_windows_native_environment(code='print(1)')",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "file_path": {"type": "string"}
                }
            }
        ),
        
        Tool(
            name="create_new_conda_environment_on_f_drive",
            description="CREATES a new Conda environment in F:/python_repos/envs/NAME.\nEXAMPLE: create_new_conda_environment_on_f_drive(name='my_env', python_version='3.10', packages='numpy')",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "python_version": {"type": "string"},
                    "packages": {"type": "string"}
                },
                "required": ["name"]
            }
        ),
        
        Tool(
            name="execute_system_shell_command",
            description=(
                "RUNS a shell command in CMD (Windows) or Bash (WSL).\n"
                "JS TIP: Prefer 'npm start' or 'node index.js'. Use WSL for better Node.js compatibility.\n"
                "EXAMPLE: execute_system_shell_command(command='npm run dev', environment='wsl')"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "environment": {"type": "string", "enum": ["windows", "wsl"], "default": "windows"}
                },
                "required": ["command"]
            }
        ),
        
        Tool(
            name="fetch_text_content_from_url_website",
            description="DOWNLOADS and CLEANS text from a website URL.\nEXAMPLE: fetch_text_content_from_url_website(url='https://example.com')",
            inputSchema={
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"]
            }
        ),

        Tool(
            name="read_screen_shot_and_extract_text",
            description=(
                "EXTRACTS TEXT from a screenshot or image file using OCR technology.\n"
                "SUPPORTED FORMATS: PNG, JPG, BMP, TIFF, GIF\n"
                "CAPABILITIES:\n"
                "- Reads any visible text in screenshots (documents, webpages, terminal, etc.)\n"
                "- Returns full extracted text content as string\n"
                "- Automatically handles multi-line text and layouts\n"
                "\nEXAMPLE USAGE:\nread_screen_shot_and_extract_text(filepath='F:/workspace/screen_shot.png')\n"
                "Read any screenshot at any accessible path (Windows or WSL shared paths)"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Full path to screenshot/image file. Supports:\n"
                                      "- Windows paths: F:/workspace/screen.png, C:/Users/you/Desktop/img.jpg\n"
                                      "- WSL paths: /mnt/f/workspace/screen.png, /mnt/c/Users/you/Desktop/img.jpg\n"
                    }
                },
                "required": ["filepath"]
            }
        ),
        Tool(
            name="take_screenshot",
            description="CAPTURES a screenshot of a specific monitor and saves it to the specified path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to save the screenshot (e.g. 'F:/screenshots/desktop.png')"},
                    "monitor_id": {"type": "integer", "description": "ID of the monitor to capture (0 for primary, 1 for secondary, etc.). Default: 0", "default": 0}
                },
                "required": ["path"]
            }
        ),

        Tool(
            name="mouse_control",
            description="CONTROLS the mouse cursor (move, click, double-click, right-click).",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["move", "click", "double_click", "right_click"]},
                    "x": {"type": "integer", "description": "X coordinate"},
                    "y": {"type": "integer", "description": "Y coordinate"}
                },
                "required": ["action", "x", "y"]
            }
        ),

        Tool(
            name="keyboard_control",
            description="CONTROLS the keyboard (type text, press hotkeys).",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["type", "hotkey"]},
                    "text": {"type": "string", "description": "Text to type"},
                    "keys": {"type": "string", "description": "Hotkey string (e.g. '^(v)' for Ctrl+V, '%{F4}' for Alt+F4)"}
                },
                "required": ["action"]
            }
        ),

        Tool(
            name="ask_another_ai",
            description="CONSULTS another AI model (LM Studio) for specific tasks. Deterministic by default (temp=0). Uses a prompt library for consistency.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The question or instruction."},
                    "model": {
                        "type": "string", 
                        "enum": [
                            "qwen3.5-4b-claude-4.6-highiq-thinking-i1",
                            "qwen/qwen3-8b",
                            "qwen3.5-2b-gpt-5.1-highiq-deep-thinking-i1",
                            "qwen3.5-0.8b"
                        ],
                        "default": "qwen3.5-0.8b"
                    },
                    "system_prompt": {"type": "string", "default": "You are a helpful assistant. Be precise and deterministic."},
                    "prompt_id": {"type": "string", "description": "Optional unique ID to save/load this prompt from the prompts library."},
                    "bypass_cache": {"type": "boolean", "default": False}
                },
                "required": ["prompt"]
            }
        ),

        Tool(
            name="find_text_and_click",
            description="LOCATES specific text on the screen and CLICKS it. Use this for automating logins or clicking buttons in web apps.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The exact or partial text to find (e.g. 'Sign in', 'Submit')"},
                    "monitor_id": {"type": "integer", "description": "ID of the monitor. Default: 0", "default": 0},
                    "action": {"type": "string", "enum": ["click", "double_click", "right_click", "move"], "default": "click"}
                },
                "required": ["text"]
            }
        ),

        Tool(
            name="vision_read_current_screen",
            description="CAPTURES a screenshot and EXTRACTS all text. This is the best way to read content behind login walls (like NotebookLM).",
            inputSchema={
                "type": "object",
                "properties": {
                    "monitor_id": {"type": "integer", "description": "ID of the monitor to read. Default: 0", "default": 0}
                }
            }
        ),

        Tool(
            name="fix_html_links_in_file",
            description="SAFELY updates internal links in an HTML file. Converts absolute root links (starting with /) to relative links (../). Avoids regex syntax errors.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the HTML file."},
                    "depth": {"type": "integer", "description": "Number of '../' levels to add. Default: 1", "default": 1}
                },
                "required": ["path"]
            }
        ),

        Tool(
            name="list_rag_shards",
            description="LISTS and SUMMARIZES LM Studio Big-RAG vector shards. Useful for verifying index integrity.",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Path to the 'Vector Data' folder."}
                },
                "required": ["directory"]
            }
        ),

        Tool(
            name="fix_html_links_recursive",
            description="RECURSIVELY updates internal links in all HTML files within a directory. Converts absolute root links (/) to relative links. Much safer than writing custom scripts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Root directory to scan (e.g. 'F:/CSA_Website')."},
                    "base_depth": {"type": "integer", "description": "Base depth offset. Default: 0", "default": 0}
                },
                "required": ["directory"]
            }
        ),

        Tool(
            name="regex_search_replace_in_file",
            description=(
                "SAFELY performs regex search-and-replace on a file. "
                "YOU pass the pattern and replacement as arguments — the server compiles the regex. "
                "This avoids ALL escaping issues. Use this instead of writing Python scripts with regex.\n"
                "EXAMPLE: regex_search_replace_in_file(path='index.html', pattern='href=\"/([^\"]+)\"', replacement='href=\"../\\1\"')"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "pattern": {"type": "string", "description": "Regex pattern (raw — no extra escaping needed)"},
                    "replacement": {"type": "string", "description": "Replacement string. Use \\1, \\2 for groups."},
                    "case_insensitive": {"type": "boolean", "description": "Case insensitive match. Default: false", "default": False},
                    "dry_run": {"type": "boolean", "description": "If true, shows what WOULD change without writing. Default: false", "default": False}
                },
                "required": ["path", "pattern", "replacement"]
            }
        ),

        Tool(
            name="search_files_for_text",
            description=(
                "SEARCHES all files in a directory for a text string or pattern. "
                "Like grep. Returns matching filenames and line numbers.\n"
                "EXAMPLE: search_files_for_text(directory='F:/CSA_Website', text='href=\"/', extensions='.html,.htm')"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory to search"},
                    "text": {"type": "string", "description": "Text or regex pattern to find"},
                    "extensions": {"type": "string", "description": "Comma-separated file extensions to search (e.g. '.html,.py,.js'). Default: all files", "default": ""},
                    "is_regex": {"type": "boolean", "description": "Treat text as regex. Default: false", "default": False},
                    "max_results": {"type": "integer", "description": "Max results to return. Default: 50", "default": 50}
                },
                "required": ["directory", "text"]
            }
        ),

        Tool(
            name="count_pattern_in_file",
            description=(
                "COUNTS how many times a text or regex pattern appears in a file. "
                "Use this to verify fixes worked.\n"
                "EXAMPLE: count_pattern_in_file(path='index.html', pattern='href=\"/')"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "pattern": {"type": "string", "description": "Text or regex pattern to count"},
                    "is_regex": {"type": "boolean", "description": "Treat pattern as regex. Default: false", "default": False}
                },
                "required": ["path", "pattern"]
            }
        )
    ]



# === TOOL EXECUTION ===

@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    result = ""
    try:
        if name == "ping":
            result = "pong"

        elif name == "get_detailed_tool_usage_guide_and_examples":
            result = """# ULTIMATE TOOL GUIDE & SAFETY MANUAL

## ⚠️ CRITICAL SAFETY RULES (READ FIRST)
1. **NO UNICODE SYMBOLS**: Do NOT use symbols like ✓, ✗, ★, or emoji in your `print()` statements. They crash Windows Python. The server will try to auto-fix them, but it's better to avoid them.
2. **NO EMBEDDED REGEX**: Avoid writing Python scripts just to do regex search/replace. Use the built-in `regex_search_replace_in_file` tool instead. This avoids all quote/slash escaping nightmares.
3. **PATH FORMATS**: Always use forward slashes `/` for paths, even on Windows. The server converts them automatically.

## 1. FILE OPERATIONS
- **list_files_in_directory(directory)**: View files.
- **write_content_to_file_at_path(path, content)**: Save files.
- **read_content_from_file_at_path(path)**: Read files.
- **search_files_for_text(directory, text, extensions)**: Recursive grep. Use this to find things!
- **count_pattern_in_file(path, pattern)**: Count occurrences (text or regex).

## 2. ADVANCED FILE FIXING
- **regex_search_replace_in_file(path, pattern, replacement)**: THE SAFEST way to update file content. No script writing needed.
- **fix_html_links_recursive(directory)**: Fixes all `/path` -> `../path` links in a folder. Use this for website projects!

## 3. PYTHON EXECUTION
- **execute_python_code_in_wsl_conda_environment(code, conda_env)**: Run code in Conda (Linux).
- **execute_python_code_in_windows_native_environment(code)**: Run code in Windows. **Automatically sanitizes your code for encoding safety.**

## 4. SYSTEM & AUTOMATION
- **execute_system_shell_command(command, environment)**: Run shell commands.
- **take_screenshot(path, monitor_id)**: Capture screen.
- **vision_read_current_screen(monitor_id)**: Capture and OCR the screen.
- **find_text_and_click(text)**: Automate clicking UI elements.

## 5. AI CONSULTATION
- **ask_another_ai(prompt, model)**: Consult another model with temp=0 for deterministic results.
"""

        elif name == "list_files_in_directory":
            d = arguments.get("directory", str(WORKSPACE))
            path = resolve_path(d)
            if not path.exists():
                result = f"ERROR: Directory not found: {path}"
            else:
                all_items = sorted(path.iterdir())
                items = [f"{'[DIR] ' if i.is_dir() else '[FILE]'} {i.name}" for i in all_items[:100]]
                if len(all_items) > 100:
                    items.append(f"...and {len(all_items) - 100} more items (list truncated to save context).")
                result = f"CONTENTS of {path}:\n" + ("\n".join(items) if items else "(empty)")
        
        elif name == "write_content_to_file_at_path":
            # Normalize path first
            raw_path = arguments["path"]
            normalized_path = PathConverter.normalize(raw_path)
            path = resolve_path(normalized_path)
            
            content = arguments["content"]
            path.parent.mkdir(parents=True, exist_ok=True)
            # Explicitly use utf-8 to avoid encoding mangling
            with open(path, "w", encoding="utf-8", newline='\n') as f:
                f.write(content)
            result = f"SUCCESS: Written to {path} (UTF-8)"
            
        elif name == "read_content_from_file_at_path":
            path = resolve_path(arguments["path"])
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read(50000)
                    if f.read(1):  # Check if there's more
                        content += "\n\n...[FILE TRUNCATED AT 50,000 CHARACTERS TO PREVENT CONTEXT OVERFLOW]..."
                    result = content
            except UnicodeDecodeError:
                result = "ERROR: Cannot read file as text. It might be a binary file."
            except Exception as e:
                result = f"ERROR reading file: {e}"
                
        elif name == "execute_python_code_in_wsl_conda_environment":
            env_name = arguments.get("conda_env", "base")
            
            if "code" in arguments:
                # Sanitize code for WSL
                code = sanitize_code_for_wsl(arguments["code"])
                temp_file = WORKSPACE / "_script_wsl_temp.py"
                with open(temp_file, "w", encoding="utf-8", newline='\n') as f:
                    f.write(code)
                wsl_path = PathConverter.to_wsl(str(temp_file))
                # Use conda run -n {env} which is more reliable for non-interactive shells
                cmd = f"conda run --no-capture-output -n {env_name} python '{wsl_path}'" 
                exit_code, output = exec_wsl(cmd)
                result = f"WSL CONDA ({env_name}) OUTPUT:\n{output}"
            elif "file_path" in arguments:
                path = resolve_path(arguments["file_path"])
                wsl_path = PathConverter.to_wsl(str(path))
                cmd = f"conda run --no-capture-output -n {env_name} python '{wsl_path}'"
                exit_code, output = exec_wsl(cmd)
                result = f"EXIT: {exit_code}\nOUTPUT:\n{output}"
                
        elif name == "execute_python_code_in_windows_native_environment":
             python_exe = get_windows_python()
             if "code" in arguments:
                # Sanitize code for Windows (fixes unicode and forces UTF-8)
                code = sanitize_code_for_windows(arguments["code"])
                temp_file = WORKSPACE / "_script_win_temp.py"
                with open(temp_file, "w", encoding="utf-8", newline='\r\n') as f:
                    f.write(code)
                
                win_temp_path = PathConverter.to_win(str(temp_file))
                exit_code, output = exec_powershell(f'& "{python_exe}" "{win_temp_path}"')
                result = f"WINDOWS PYTHON OUTPUT:\n{output}"
             elif "file_path" in arguments:
                path = resolve_path(arguments["file_path"])
                win_path = PathConverter.to_win(str(path))
                exit_code, output = exec_powershell(f'& "{python_exe}" "{win_path}"')
                result = f"EXIT: {exit_code}\nOUTPUT:\n{output}"
                
        elif name == "execute_system_shell_command":
            cmd = arguments["command"]
            if arguments.get("environment") == "wsl":
                exit_code, output = exec_wsl(cmd)
                result = f"WSL OUTPUT:\n{output}"
            else:
                exit_code, output = exec_cmd(cmd)
                result = f"WINDOVS OUTPUT:\n{output}"
                
        elif name == "create_new_conda_environment_on_f_drive":
            env_name = arguments["name"]
            py_ver = arguments.get("python_version", "3.10")
            pkgs = arguments.get("packages", "")
            target_path = f"{WSL_ENVS_PATH}/{env_name}"
            cmd = f"conda create -p '{target_path}' python={py_ver} {pkgs} -y"
            exit_code, output = exec_wsl(cmd)
            result = f"Create Env Result:\n{output}"

        elif name == "fetch_text_content_from_url_website":
            import urllib.request
            import re
            url = arguments["url"]
            try:
                if not url.startswith('http'): url = 'https://' + url
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    html = response.read().decode('utf-8', errors='ignore')
                    text = re.sub(r'<(script|style).*?</\1>', ' ', html, flags=re.DOTALL)
                    text = re.sub(r'<[^>]+>', ' ', text)
                    text = re.sub(r'\s+', ' ', text).strip()
                    result = f"Website Content:\n{text[:4000]}"
            except Exception as e:
                result = f"ERROR: {e}"
        
                
        elif name == "read_screen_shot_and_extract_text":
            filepath = arguments["filepath"]
            # Path normalization
            wsl_path = PathConverter.to_wsl(filepath)
            
            ocr_script = f'''
import sys
sys.path.insert(0, '/mnt/f/python_repos')
from ai_workspace_ocr import read_screen_shot
try:
    text = read_screen_shot("{wsl_path}")
    print(text if text else "No text extracted.")
except Exception as e:
    print(f"OCR Error: {{e}}")
'''
            temp_file = WORKSPACE / "_ocr_temp_script.py"
            with open(temp_file, "w", encoding="utf-8", newline='\n') as f:
                f.write(ocr_script)
            
            wsl_path_str = PathConverter.to_wsl(str(temp_file))
            cmd = f"conda run --no-capture-output -n Basic python '{wsl_path_str}'"
            exit_code, output = exec_wsl(cmd)
            result = f"OCR RESULT:\n{output}"

        elif name == "take_screenshot":
            path = arguments["path"]
            monitor_id = arguments.get("monitor_id", 0)
            # Use PathConverter for consistent mapping
            win_path = PathConverter.to_win(path)
            
            ps_cmd = (
                "Add-Type -AssemblyName System.Windows.Forms, System.Drawing; "
                "$screens = [System.Windows.Forms.Screen]::AllScreens; "
                f"if ({monitor_id} -lt $screens.Count) {{ "
                f"$s = $screens[{monitor_id}]; "
                "$b = New-Object System.Drawing.Bitmap($s.Bounds.Width, $s.Bounds.Height); "
                "$g = [System.Drawing.Graphics]::FromImage($b); "
                "$g.CopyFromScreen($s.Bounds.X, $s.Bounds.Y, 0, 0, $b.Size); "
                f"$b.Save('{win_path}'); "
                "$g.Dispose(); $b.Dispose(); "
                "} else {{ "
                f"throw 'Monitor ID {monitor_id} out of range (Total screens: ' + $screens.Count + ')'; "
                "}}"
            )
            exit_code, output = exec_powershell(ps_cmd)
            if exit_code == 0:
                result = f"SCREENSHOT SAVED TO: {win_path}"
            else:
                result = f"SCREENSHOT ERROR: {output}"

        elif name == "mouse_control":
            action = arguments["action"]
            x, y = arguments["x"], arguments["y"]
            ps_parts = [
                "Add-Type -AssemblyName System.Windows.Forms;",
                f"[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point({x}, {y});"
            ]
            if action in ["click", "double_click", "right_click"]:
                # Use Add-Type with a unique name to avoid errors on repeated calls
                unique_id = f"Win32Mouse_{os.getpid()}"
                ps_parts.append(
                    f'$m = Add-Type -MemberDefinition "[DllImport(""user32.dll"")] public static extern void mouse_event(int f, int x, int y, int d, int e);" -Name "{unique_id}" -Namespace Win32Utils -PassThru;'
                )
                if action == "click":
                    ps_parts.append(f'[Win32Utils.{unique_id}]::mouse_event(0x0002, 0, 0, 0, 0); [Win32Utils.{unique_id}]::mouse_event(0x0004, 0, 0, 0, 0);')
                elif action == "double_click":
                    ps_parts.append(f'[Win32Utils.{unique_id}]::mouse_event(0x0002, 0, 0, 0, 0); [Win32Utils.{unique_id}]::mouse_event(0x0004, 0, 0, 0, 0);')
                    ps_parts.append(f'[Win32Utils.{unique_id}]::mouse_event(0x0002, 0, 0, 0, 0); [Win32Utils.{unique_id}]::mouse_event(0x0004, 0, 0, 0, 0);')
                elif action == "right_click":
                    ps_parts.append(f'[Win32Utils.{unique_id}]::mouse_event(0x0008, 0, 0, 0, 0); [Win32Utils.{unique_id}]::mouse_event(0x0010, 0, 0, 0, 0);')
            
            exit_code, output = exec_powershell(" ".join(ps_parts))
            result = f"MOUSE {action} at ({x}, {y}) result: {output if output else 'Success'}"

        elif name == "keyboard_control":
            action = arguments["action"]
            if action == "type":
                text = arguments.get("text", "").replace("'", "''") # Escape single quotes for PS
                ps_cmd = f"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('{text}')"
                exit_code, output = exec_powershell(ps_cmd)
            elif action == "hotkey":
                keys = arguments.get("keys", "")
                ps_cmd = f"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('{keys}')"
                exit_code, output = exec_powershell(ps_cmd)
            result = f"KEYBOARD {action} result: {output if output else 'Success'}"

        elif name == "ask_another_ai":
            prompt = arguments["prompt"]
            model = arguments.get("model", "qwen3.5-0.8b")
            system_prompt = arguments.get("system_prompt", "You are a helpful assistant. Be precise and deterministic.")
            prompt_id = arguments.get("prompt_id")
            bypass_cache = arguments.get("bypass_cache", False)
            
            library_path = WORKSPACE / "prompts_library.json"
            library = {}
            if library_path.exists():
                try:
                    with open(library_path, "r", encoding="utf-8") as f:
                        library = json.load(f)
                except:
                    pass
            
            # Cache check
            if prompt_id and not bypass_cache and prompt_id in library:
                result = f"LOADED FROM LIBRARY (ID: {prompt_id}):\n{library[prompt_id]['response']}"
            else:
                # Call LM Studio API
                url = "http://192.168.56.1:31415/v1/chat/completions"
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.0,
                    "max_tokens": 2048
                }
                try:
                    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=60) as response:
                        res_data = json.loads(response.read().decode("utf-8"))
                        ai_response = res_data["choices"][0]["message"]["content"]
                        
                        # Save to library if ID provided
                        if prompt_id:
                            library[prompt_id] = {
                                "prompt": prompt,
                                "model": model,
                                "response": ai_response,
                                "timestamp": time.ctime()
                            }
                            with open(library_path, "w", encoding="utf-8") as f:
                                json.dump(library, f, indent=2)
                        
                        result = f"AI RESPONSE ({model}):\n{ai_response}"
                except Exception as e:
                    result = f"ERROR calling another AI: {e}"

        elif name == "vision_read_current_screen":
            monitor_id = arguments.get("monitor_id", 0)
            shot_path = WORKSPACE / f"vision_read_{monitor_id}.png"
            wsl_shot_path = PathConverter.to_wsl(str(shot_path))
            win_shot_path = PathConverter.to_win(str(shot_path))
            
            # Capture
            ps_cmd = f"Add-Type -AssemblyName System.Windows.Forms, System.Drawing; $mon = [System.Windows.Forms.Screen]::AllScreens[{monitor_id}]; $bmp = New-Object System.Drawing.Bitmap $mon.Bounds.Width, $mon.Bounds.Height; $graphics = [System.Drawing.Graphics]::FromImage($bmp); $graphics.CopyFromScreen($mon.Bounds.X, $mon.Bounds.Y, 0, 0, $bmp.Size); $bmp.Save('{win_shot_path}'); $bmp.Dispose(); $graphics.Dispose()"
            exec_powershell(ps_cmd)
            
            # OCR
            ocr_script = f'''
import sys
sys.path.insert(0, '/mnt/f/python_repos')
from ai_workspace_ocr import read_screen_shot
try:
    print(read_screen_shot("{wsl_shot_path}"))
except Exception as e:
    print(f"OCR Error: {{e}}")
'''
            exit_code, output = exec_wsl(f"{get_wsl_python()} -c \"{ocr_script}\"")
            result = f"SCREEN CONTENT ({monitor_id}):\n{output}"

        elif name == "find_text_and_click":
            target_text = arguments["text"].lower()
            monitor_id = arguments.get("monitor_id", 0)
            action = arguments.get("action", "click")
            
            shot_path = WORKSPACE / f"search_shot_{monitor_id}.png"
            wsl_shot_path = PathConverter.to_wsl(str(shot_path))
            win_shot_path = PathConverter.to_win(str(shot_path))
            
            # 1. Capture
            ps_cmd = f"Add-Type -AssemblyName System.Windows.Forms, System.Drawing; $mon = [System.Windows.Forms.Screen]::AllScreens[{monitor_id}]; $bmp = New-Object System.Drawing.Bitmap $mon.Bounds.Width, $mon.Bounds.Height; $graphics = [System.Drawing.Graphics]::FromImage($bmp); $graphics.CopyFromScreen($mon.Bounds.X, $mon.Bounds.Y, 0, 0, $bmp.Size); $bmp.Save('{win_shot_path}'); $bmp.Dispose(); $graphics.Dispose()"
            exec_powershell(ps_cmd)
            
            # 2. Find coordinates
            coord_script = f'''
import sys
import json
sys.path.insert(0, '/mnt/f/python_repos')
from ai_workspace_ocr import get_text_coordinates
try:
    coords = get_text_coordinates("{wsl_shot_path}")
    print(json.dumps(coords))
except Exception as e:
    print(json.dumps([]))
'''
            _, coord_output = exec_wsl(f"{get_wsl_python()} -c \"{coord_script}\"")
            
            try:
                # Cleaning output - sometimes WSL output includes noise
                clean_output = coord_output.strip().split('\n')[-1]
                coords = json.loads(clean_output)
                found = None
                for c in coords:
                    if target_text in c['text'].lower():
                        found = c
                        break
                
                if found:
                    ps_mon_cmd = f"$mon = [System.Windows.Forms.Screen]::AllScreens[{monitor_id}]; \"$($mon.Bounds.X),$($mon.Bounds.Y)\""
                    _, mon_info = exec_powershell(ps_mon_cmd)
                    mon_x, mon_y = map(int, mon_info.strip().split(','))
                    
                    abs_x = mon_x + found['left'] + (found['width'] // 2)
                    abs_y = mon_y + found['top'] + (found['height'] // 2)
                    
                    if action == "click":
                        ps_mouse = f"[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point({abs_x}, {abs_y}); Add-Type -MemberDefinition '[DllImport(\"user32.dll\")] public static extern void mouse_event(int dwFlags, int dx, int dy, int dwData, int dwExtraInfo);' -Name User32 -Namespace Win32; [Win32.User32]::mouse_event(0x0002, 0, 0, 0, 0); [Win32.User32]::mouse_event(0x0004, 0, 0, 0, 0)"
                    elif action == "double_click":
                        ps_mouse = f"[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point({abs_x}, {abs_y}); Add-Type -MemberDefinition '[DllImport(\"user32.dll\")] public static extern void mouse_event(int dwFlags, int dx, int dy, int dwData, int dwExtraInfo);' -Name User32 -Namespace Win32; [Win32.User32]::mouse_event(0x0002, 0, 0, 0, 0); [Win32.User32]::mouse_event(0x0004, 0, 0, 0, 0); Start-Sleep -Milliseconds 100; [Win32.User32]::mouse_event(0x0002, 0, 0, 0, 0); [Win32.User32]::mouse_event(0x0004, 0, 0, 0, 0)"
                    elif action == "right_click":
                        ps_mouse = f"[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point({abs_x}, {abs_y}); Add-Type -MemberDefinition '[DllImport(\"user32.dll\")] public static extern void mouse_event(int dwFlags, int dx, int dy, int dwData, int dwExtraInfo);' -Name User32 -Namespace Win32; [Win32.User32]::mouse_event(0x0008, 0, 0, 0, 0); [Win32.User32]::mouse_event(0x0010, 0, 0, 0, 0)"
                    else: # move
                        ps_mouse = f"[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point({abs_x}, {abs_y})"
                    
                    exec_powershell(ps_mouse)
                    result = f"FOUND '{target_text}' at ({abs_x}, {abs_y}) and performed {action}."
                else:
                    result = f"COULD NOT FIND text '{target_text}' on monitor {monitor_id}."
            except Exception as e:
                result = f"ERROR in visual search: {e}\nOutput was: {coord_output}"

        elif name == "fix_html_links_in_file":
            path = resolve_path(arguments["path"])
            depth = arguments.get("depth", 1)
            prefix = "../" * depth
            
            try:
                import re
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Safer pattern for href and src
                # Matches href="/path" and converts to href="../path"
                def replacer(match):
                    attr = match.group(1) # href= or src=
                    quote = match.group(2)
                    link = match.group(3)
                    if link.startswith("/"):
                        return f'{attr}{quote}{prefix}{link[1:]}'
                    return match.group(0)

                pattern = r'(href=|src=)(["\'])(/[^"\'>\s]+)'
                new_content = re.sub(pattern, replacer, content)
                
                if new_content != content:
                    with open(path, "w", encoding="utf-8", newline='\n') as f:
                        f.write(new_content)
                    result = f"SUCCESS: Fixed links in {path}"
                else:
                    result = f"INFO: No root-relative links found in {path}"
            except Exception as e:
                result = f"ERROR fixing links: {e}"

        elif name == "list_rag_shards":
            directory = resolve_path(arguments["directory"])
            if not directory.exists():
                result = f"ERROR: Directory {directory} not found."
            else:
                shards = list(directory.glob("shard_*"))
                shard_info = []
                for s in sorted(shards):
                    index_file = s / "index.json"
                    size = index_file.stat().st_size if index_file.exists() else 0
                    shard_info.append(f"- {s.name}: {size / 1024 / 1024:.2f} MB")
                
                result = f"RAG SHARDS in {directory}:\n" + "\n".join(shard_info if shard_info else ["No shards found."])

        elif name == "fix_html_links_recursive":
            root_dir = resolve_path(arguments["directory"])
            base_depth = arguments.get("base_depth", 0)
            
            if not root_dir.exists():
                result = f"ERROR: Directory {root_dir} not found."
            else:
                import re
                fixed_files = []
                error_files = []
                
                # Pre-compile pattern
                pattern = re.compile(r'(href=|src=)(["\'])(/[^"\'>\s]+)')
                
                for root, _, files in os.walk(root_dir):
                    for file in files:
                        if file.lower().endswith((".html", ".htm")):
                            file_path = Path(root) / file
                            try:
                                # Calculate depth relative to root_dir
                                rel_path = file_path.relative_to(root_dir)
                                depth = len(rel_path.parts) - 1 + base_depth
                                prefix = "../" * depth if depth > 0 else "./"
                                
                                with open(file_path, "r", encoding="utf-8") as f:
                                    content = f.read()
                                
                                def replacer(match):
                                    attr = match.group(1)
                                    quote = match.group(2)
                                    link = match.group(3)
                                    return f'{attr}{quote}{prefix}{link[1:]}'

                                new_content = pattern.sub(replacer, content)
                                
                                if new_content != content:
                                    with open(file_path, "w", encoding="utf-8", newline='\n') as f:
                                        f.write(new_content)
                                    fixed_files.append(str(rel_path))
                            except Exception as e:
                                error_files.append(f"{rel_path}: {e}")
                
                result = f"LINK FIX REPORT for {root_dir}:\n"
                result += f"Total Files Fixed: {len(fixed_files)}\n"
                if fixed_files:
                    result += "Samples:\n" + "\n".join(fixed_files[:10])
                if error_files:
                    result += "\nERRORS:\n" + "\n".join(error_files[:10])

        elif name == "regex_search_replace_in_file":
            path = resolve_path(arguments["path"])
            pattern_str = arguments["pattern"]
            replacement = arguments["replacement"]
            case_insensitive = arguments.get("case_insensitive", False)
            dry_run = arguments.get("dry_run", False)
            
            try:
                flags = re.IGNORECASE if case_insensitive else 0
                pattern = re.compile(pattern_str, flags)
                
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                matches = list(pattern.finditer(content))
                if not matches:
                    result = f"INFO: No matches found for pattern in {path}"
                else:
                    new_content = pattern.sub(replacement, content)
                    if dry_run:
                        result = f"DRY RUN: Found {len(matches)} matches in {path}. No changes made."
                    else:
                        with open(path, "w", encoding="utf-8", newline='\n') as f:
                            f.write(new_content)
                        result = f"SUCCESS: Performed {len(matches)} replacements in {path}"
            except Exception as e:
                result = f"ERROR in regex replace: {e}"

        elif name == "search_files_for_text":
            root_dir = resolve_path(arguments["directory"])
            search_text = arguments["text"]
            exts = [e.strip().lower() for e in arguments.get("extensions", "").split(",") if e.strip()]
            is_regex = arguments.get("is_regex", False)
            max_results = arguments.get("max_results", 50)
            
            try:
                results = []
                count = 0
                pattern = re.compile(search_text, re.IGNORECASE) if is_regex else None
                
                for root, _, files in os.walk(root_dir):
                    if count >= max_results: break
                    for file in files:
                        if exts and not any(file.lower().endswith(e) for e in exts):
                            continue
                        
                        file_path = Path(root) / file
                        try:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                for i, line in enumerate(f, 1):
                                    found = False
                                    if is_regex:
                                        if pattern.search(line): found = True
                                    else:
                                        if search_text in line: found = True
                                    
                                    if found:
                                        rel = file_path.relative_to(root_dir)
                                        results.append(f"{rel}:{i}: {line.strip()[:100]}")
                                        count += 1
                                        if count >= max_results: break
                        except:
                            continue
                
                result = f"SEARCH RESULTS in {root_dir} (Max {max_results}):\n" + "\n".join(results if results else ["No matches found."])
            except Exception as e:
                result = f"ERROR in search: {e}"

        elif name == "count_pattern_in_file":
            path = resolve_path(arguments["path"])
            pattern_str = arguments["pattern"]
            is_regex = arguments.get("is_regex", False)
            
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                
                if is_regex:
                    matches = re.findall(pattern_str, content)
                    count = len(matches)
                else:
                    count = content.count(pattern_str)
                
                result = f"COUNT: '{pattern_str}' appears {count} times in {path}"
            except Exception as e:
                result = f"ERROR in count: {e}"

        else:
            result = f"Unknown tool: {name}"

    except Exception as e:
        import traceback
        error_details = f"{type(e).__name__}: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        result = f"ERROR: {error_details}"
    
    return [TextContent(type="text", text=result)]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
