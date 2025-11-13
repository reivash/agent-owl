"""
Unity Verification Plugin for Agent Owl

Checks Unity Editor state and determines appropriate prompts.
"""

import psutil
import os
import re


def verify():
    """
    Verify Unity state

    Returns:
        tuple: (status, message, prompt_override)
            - status: str identifier for prompt selection
            - message: str description of current state
            - prompt_override: str or None to override configured prompts
    """
    # Check if Unity is running
    unity_running = False
    unity_processes = []

    for proc in psutil.process_iter(['name']):
        try:
            if 'unity' in proc.info['name'].lower():
                unity_running = True
                unity_processes.append(proc.info['name'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if not unity_running:
        return 'unity_not_running', 'Unity is not running', None

    # Check Unity Editor log for errors
    unity_log_path = os.path.expanduser(r"~\AppData\Local\Unity\Editor\Editor.log")

    errors_found = []
    if os.path.exists(unity_log_path):
        try:
            with open(unity_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                recent_lines = lines[-100:] if len(lines) > 100 else lines

                error_patterns = [
                    r"Canvas.*not.*visible",
                    r"Button.*not.*rendered",
                    r"UI.*out of.*bounds",
                    r"RectTransform.*invalid",
                    r"NullReferenceException",
                    r"Error.*MainMenu"
                ]

                for line in recent_lines:
                    for pattern in error_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            errors_found.append(line.strip())
                            break
        except Exception as e:
            return 'error', f'Could not read Unity log: {e}', None

    if errors_found:
        # Return first error as message
        error_msg = errors_found[0][:100]  # Truncate long errors
        return 'unity_errors', f'Unity errors detected: {error_msg}', None

    # Unity running, no obvious errors
    return 'unity_running', f'Unity running ({", ".join(unity_processes)}), no errors detected', None
