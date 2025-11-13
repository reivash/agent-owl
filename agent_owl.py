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
        """Find the target window"""
        try:
            windows = gw.getAllWindows()
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

    def is_agent_truly_idle(self, window):
        """
        Determine if agent is truly idle by comparing screenshots
        Returns True only if last N screenshots are identical (no new output)
        """
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

        # Check if truly idle using screenshots
        truly_idle = self.is_agent_truly_idle(window)

        if not truly_idle:
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
