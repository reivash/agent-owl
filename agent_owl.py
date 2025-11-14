#!/usr/bin/env python3
"""
Agent Owl - Smart AI Agent Monitor
Keep your AI agents working autonomously without interruption spam

Uses screenshot comparison to detect when AI agents are truly idle vs actively thinking.
Supports custom verification plugins for different use cases.
"""

import time
import pyautogui
import pygetwindow as gw
from datetime import datetime
from PIL import Image, ImageChops
import os
import json
import importlib.util
from pathlib import Path


class AgentOwl:
    """
    Smart monitor for AI agents using screenshot-based idle detection

    Watches a window, compares screenshots over time, and sends continuation
    prompts only when the agent is truly idle (not just thinking).
    """

    def __init__(self, config_path=None, **kwargs):
        """
        Initialize Agent Owl

        Args:
            config_path: Path to JSON config file (optional)
            **kwargs: Direct configuration options (override config file)
        """
        # Load config from file if provided
        if config_path:
            with open(config_path, 'r') as f:
                config = json.load(f)
        else:
            config = {}

        # Merge with kwargs (kwargs override file config)
        config.update(kwargs)

        # Core settings
        self.window_pattern = config.get('window_pattern', 'Agent')
        self.check_interval = config.get('check_interval', 90)
        self.screenshots_to_compare = config.get('screenshots_to_compare', 4)
        self.cooldown = config.get('cooldown_minutes', 15) * 60
        self.screenshot_threshold = config.get('screenshot_threshold', 0.01)

        # Prompts
        self.prompts = config.get('prompts', {
            'default': 'Continue working on the task.',
            'idle': 'You appear to be idle. Please continue with the task.'
        })

        # Verification plugin
        self.verification_module = None
        if 'verification_plugin' in config:
            self._load_verification_plugin(config['verification_plugin'])

        # State
        self.last_prompt_time = 0
        self.screenshot_history = []
        self.screenshot_dir = config.get('screenshot_dir', 'screenshots')
        self.interaction_count = 0

        # Create screenshot directory
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)

    def _load_verification_plugin(self, plugin_path):
        """Load a custom verification plugin"""
        try:
            spec = importlib.util.spec_from_file_location("verification_plugin", plugin_path)
            self.verification_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.verification_module)
            self.log(f"✓ Loaded verification plugin: {plugin_path}")
        except Exception as e:
            self.log(f"✗ Failed to load verification plugin: {e}")
            self.verification_module = None

    def log(self, message):
        """Log with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            print(f"[{timestamp}] {message}")
        except UnicodeEncodeError:
            safe_message = message.encode('ascii', errors='replace').decode('ascii')
            print(f"[{timestamp}] {safe_message}")

    def find_window(self):
        """Find the target window by checking process name"""
        try:
            import psutil
            windows = gw.getAllWindows()

            # Get all PowerShell process IDs
            powershell_pids = []
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if 'powershell' in proc.info['name'].lower():
                        powershell_pids.append(proc.info['pid'])
                except:
                    pass

            # Try Windows-specific window-to-process mapping
            try:
                import win32process
                import win32gui

                for window in windows:
                    if not window.title.strip():
                        continue

                    try:
                        # Get process ID for this window
                        _, window_pid = win32process.GetWindowThreadProcessId(window._hWnd)

                        # Check if this window belongs to a PowerShell process
                        if window_pid in powershell_pids:
                            return window
                    except:
                        pass
            except ImportError:
                # pywin32 not available, use fallback
                pass

            # Fallback: check by window title pattern
            if self.window_pattern:
                for window in windows:
                    if self.window_pattern.lower() in window.title.lower():
                        return window

            return None
        except Exception as e:
            self.log(f"Error finding window: {e}")
            return None

    def capture_window_screenshot(self, window):
        """Capture screenshot of window"""
        try:
            x, y, width, height = window.left, window.top, window.width, window.height
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
            return screenshot
        except Exception as e:
            self.log(f"Error capturing screenshot: {e}")
            return None

    def images_are_identical(self, img1, img2):
        """
        Compare two images and return True if essentially identical

        Args:
            img1, img2: PIL Images to compare
        """
        try:
            if img1.size != img2.size:
                return False

            diff = ImageChops.difference(img1, img2)
            diff_gray = diff.convert('L')
            histogram = diff_gray.histogram()

            total_pixels = img1.size[0] * img1.size[1]
            diff_pixels = sum(histogram[1:])
            diff_percentage = diff_pixels / total_pixels

            return diff_percentage < self.screenshot_threshold
        except Exception as e:
            self.log(f"Error comparing images: {e}")
            return False

    def is_agent_truly_idle(self, window, current_screenshot=None):
        """
        Determine if agent is truly idle by comparing screenshots
        Returns True only if last N screenshots are identical (no new output)
        """
        if current_screenshot is None:
            current_screenshot = self.capture_window_screenshot(window)

        if not current_screenshot:
            return False

        # Save screenshot
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = os.path.join(self.screenshot_dir, f"agent_{timestamp}.png")
        current_screenshot.save(screenshot_path)

        # Add to history (keep only last N)
        self.screenshot_history.append(current_screenshot)
        if len(self.screenshot_history) > self.screenshots_to_compare:
            self.screenshot_history.pop(0)

        # Need at least N screenshots to compare
        if len(self.screenshot_history) < self.screenshots_to_compare:
            self.log(f"Collecting screenshots ({len(self.screenshot_history)}/{self.screenshots_to_compare})...")
            return False

        # Check if all recent screenshots are identical
        all_identical = True
        for i in range(len(self.screenshot_history) - 1):
            if not self.images_are_identical(self.screenshot_history[i], self.screenshot_history[i + 1]):
                all_identical = False
                break

        if all_identical:
            self.log(f"✓ Agent appears TRULY idle (last {self.screenshots_to_compare} screenshots identical)")
            return True
        else:
            self.log(f"✓ Agent is ACTIVE (screenshots show changes - likely thinking/working)")
            return False

    def detect_permission_prompt(self, screenshot):
        """
        Detect if the screenshot shows a permission prompt
        Uses both OCR (if available) and pixel-based detection
        """
        try:
            # Try OCR-based detection first
            try:
                import pytesseract
                text = pytesseract.image_to_string(screenshot).lower()

                permission_keywords = [
                    'do you want to proceed',
                    'permission',
                    'allow',
                    'enable full access',
                    'approve',
                    'grant access',
                    'authorize',
                    'yes',
                    'no'
                ]

                for keyword in permission_keywords:
                    if keyword in text:
                        self.log(f"🔒 Permission prompt detected (OCR): '{keyword}'")
                        return True
            except ImportError:
                # OCR not available - permission detection disabled
                # Install pytesseract for automatic permission approval
                pass

            return False
        except Exception as e:
            self.log(f"Error detecting permission prompt: {e}")
            return False

    def approve_permission(self, window):
        """
        Automatically approve permission by selecting 'Enable full access' option
        Uses arrow keys to navigate and Enter to confirm
        """
        try:
            self.log("🔓 Auto-approving permission...")

            # Activate window
            if window.isMinimized:
                window.restore()
                time.sleep(0.5)

            window.activate()
            time.sleep(0.5)

            # Press down arrow 2-3 times to select "Enable full access" option
            # (usually the last/bottom option in Claude's permission prompts)
            for i in range(3):
                pyautogui.press('down')
                time.sleep(0.1)

            # Press Enter to confirm
            time.sleep(0.3)
            pyautogui.press('enter')
            time.sleep(0.5)

            self.log("✓ Permission approved successfully")
            self.screenshot_history = []  # Clear history after approval
            return True
        except Exception as e:
            self.log(f"Error approving permission: {e}")
            return False

    def detect_question_prompt(self, screenshot):
        """
        Detect if the screenshot shows a multiple-choice question from Claude
        Looks for numbered options, bullet points, or question patterns
        """
        try:
            # Try OCR-based detection
            try:
                import pytesseract
                text = pytesseract.image_to_string(screenshot).lower()

                # Look for question indicators
                question_patterns = [
                    'which',
                    'what',
                    'how',
                    'would you like',
                    'choose',
                    'select',
                    '?',
                ]

                # Look for option patterns (numbered or bulleted lists)
                option_patterns = [
                    '1.',
                    '2.',
                    '•',
                    '-',
                    'option',
                ]

                has_question = any(pattern in text for pattern in question_patterns)
                has_options = any(pattern in text for pattern in option_patterns)

                if has_question and has_options:
                    self.log(f"❓ Question prompt detected - Claude is asking for input")
                    return True
            except ImportError:
                # OCR not available - question detection disabled
                pass

            return False
        except Exception as e:
            self.log(f"Error detecting question prompt: {e}")
            return False

    def answer_question(self, window):
        """
        Automatically answer a question by selecting the first/top option
        Uses Enter key to select the default/first option
        """
        try:
            self.log("💡 Auto-answering question with top option...")

            # Activate window
            if window.isMinimized:
                window.restore()
                time.sleep(0.5)

            window.activate()
            time.sleep(0.5)

            # Simply press Enter to select the first/default option
            # Claude typically highlights the first option by default
            pyautogui.press('enter')
            time.sleep(0.5)

            self.log("✓ Question answered successfully (selected top option)")
            self.screenshot_history = []  # Clear history after answering
            return True
        except Exception as e:
            self.log(f"Error answering question: {e}")
            return False

    def run_verification(self):
        """
        Run custom verification if plugin is loaded
        Returns: (status: str, message: str, prompt_override: str or None)
        """
        if not self.verification_module:
            return 'unknown', 'No verification configured', None

        try:
            if hasattr(self.verification_module, 'verify'):
                return self.verification_module.verify()
            else:
                return 'unknown', 'Verification plugin missing verify() function', None
        except Exception as e:
            self.log(f"Verification error: {e}")
            return 'error', str(e), None

    def get_prompt_message(self):
        """Get the appropriate prompt message based on verification"""
        status, msg, prompt_override = self.run_verification()

        if prompt_override:
            return prompt_override

        if status in self.prompts:
            return self.prompts[status]

        return self.prompts.get('default', 'Continue working on the task.')

    def send_prompt(self, window, message):
        """Send a continuation prompt to the agent"""
        try:
            self.log(f"Sending prompt: {message}")

            # Disable PyAutoGUI failsafe temporarily
            original_failsafe = pyautogui.FAILSAFE
            pyautogui.FAILSAFE = False

            try:
                # Restore if minimized
                if window.isMinimized:
                    window.restore()
                    time.sleep(0.5)

                # Activate window
                window.activate()
                time.sleep(1.0)

                # Click in window
                click_x = window.left + (window.width // 2)
                click_y = window.top + window.height - 100
                pyautogui.click(click_x, click_y)
                time.sleep(0.5)

                # Type message
                pyautogui.write(message, interval=0.05)
                time.sleep(0.3)
                pyautogui.press('enter')

                self.last_prompt_time = time.time()
                self.screenshot_history = []  # Clear history after prompt
                self.interaction_count += 1

                self.log("✓ Prompt sent successfully")
                return True
            finally:
                # Restore failsafe setting
                pyautogui.FAILSAFE = original_failsafe

        except Exception as e:
            self.log(f"Error sending prompt: {e}")
            return False

    def run_check_cycle(self):
        """Run one monitoring cycle"""
        self.log("=" * 60)
        self.log("Running check cycle...")

        # Find window
        window = self.find_window()
        if not window:
            self.log(f"✗ Window not found (pattern: '{self.window_pattern}')")
            return False

        self.log(f"✓ Found window: {window.title}")

        # Capture screenshot once for all checks
        current_screenshot = self.capture_window_screenshot(window)
        if not current_screenshot:
            return False

        # Check if truly idle using screenshots
        truly_idle = self.is_agent_truly_idle(window, current_screenshot)

        if not truly_idle:
            return True

        # Agent is idle - check if it's waiting for permission
        if self.detect_permission_prompt(current_screenshot):
            self.log("✓ Detected permission prompt while agent is idle")
            self.approve_permission(window)
            return True

        # Agent is idle - check if it's waiting for an answer to a question
        if self.detect_question_prompt(current_screenshot):
            self.log("✓ Detected question prompt while agent is idle")
            self.answer_question(window)
            return True

        # Agent is idle - check cooldown
        time_since_last_prompt = time.time() - self.last_prompt_time
        if time_since_last_prompt < self.cooldown:
            cooldown_remaining = int(self.cooldown - time_since_last_prompt)
            minutes_remaining = cooldown_remaining // 60
            seconds_remaining = cooldown_remaining % 60
            self.log(f"⏳ Cooldown active: {minutes_remaining}m {seconds_remaining}s remaining")
            return True

        # Ready to send prompt
        message = self.get_prompt_message()
        self.send_prompt(window, message)
        return True

    def run(self):
        """Main monitoring loop"""
        self.log("=" * 60)
        self.log("  🦉 AGENT OWL - Smart AI Agent Monitor")
        self.log("=" * 60)
        self.log(f"Window pattern: '{self.window_pattern}'")
        self.log(f"Check interval: {self.check_interval}s")
        self.log(f"Screenshots to compare: {self.screenshots_to_compare}")
        self.log(f"Cooldown: {self.cooldown // 60} minutes")
        self.log(f"Screenshot directory: {self.screenshot_dir}/")
        self.log("")
        self.log("How it works:")
        self.log(f"  1. Takes screenshot every {self.check_interval}s")
        self.log(f"  2. Compares last {self.screenshots_to_compare} screenshots")
        self.log(f"  3. Only prompts if screenshots identical (no new output)")
        self.log(f"  4. Waits {self.cooldown // 60} minutes between prompts")
        if self.verification_module:
            self.log(f"  5. Runs custom verification before prompting")
        self.log("")
        self.log("Press Ctrl+C to stop")
        self.log("=" * 60)
        self.log("")

        try:
            while True:
                self.run_check_cycle()
                self.log(f"Waiting {self.check_interval}s until next check...")
                self.log("")
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            self.log("\n" + "=" * 60)
            self.log(f"  Monitor stopped - {self.interaction_count} prompts sent")
            self.log("=" * 60)
        except Exception as e:
            self.log(f"Unexpected error: {e}")
            raise


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Agent Owl - Smart AI Agent Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with default settings
  python agent_owl.py --window "PowerShell"

  # With custom config file
  python agent_owl.py --config configs/codex_unity.json

  # Override specific settings
  python agent_owl.py --window "Claude" --interval 60 --cooldown 20
        """
    )

    parser.add_argument(
        '--config',
        help='Path to JSON config file'
    )
    parser.add_argument(
        '--window',
        help='Window title pattern to match'
    )
    parser.add_argument(
        '--interval',
        type=int,
        help='Check interval in seconds (default: 90)'
    )
    parser.add_argument(
        '--screenshots',
        type=int,
        help='Number of identical screenshots before considering idle (default: 4)'
    )
    parser.add_argument(
        '--cooldown',
        type=int,
        help='Minutes between prompts (default: 15)'
    )

    args = parser.parse_args()

    # Check dependencies
    try:
        import pyautogui
        import pygetwindow
        from PIL import Image
    except ImportError:
        print("Missing dependencies. Please install:")
        print("  pip install pyautogui pygetwindow Pillow")
        return

    # Build kwargs from args
    kwargs = {}
    if args.window:
        kwargs['window_pattern'] = args.window
    if args.interval:
        kwargs['check_interval'] = args.interval
    if args.screenshots:
        kwargs['screenshots_to_compare'] = args.screenshots
    if args.cooldown:
        kwargs['cooldown_minutes'] = args.cooldown

    # Create and run monitor
    owl = AgentOwl(config_path=args.config, **kwargs)
    owl.run()


if __name__ == "__main__":
    main()
