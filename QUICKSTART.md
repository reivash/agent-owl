# 🦉 Agent Owl - Quick Start Guide

Get started monitoring your AI agents in under 2 minutes!

## Installation

```bash
cd C:\Users\javie\Documents\GitHub\agent-owl
pip install -r requirements.txt
```

## Basic Usage

### 1. Monitor Any Window

```bash
python agent_owl.py --window "PowerShell"
```

This will:
- Find windows matching "PowerShell"
- Take screenshots every 90 seconds
- Compare the last 4 screenshots
- Prompt when truly idle (screenshots identical)
- Wait 15 minutes between prompts

### 2. Monitor Codex on Unity

```bash
python agent_owl.py --config configs/codex_unity.json
```

This uses the pre-configured Unity setup:
- Monitors PowerShell window
- Checks Unity process and logs
- Sends Unity-specific prompts
- 20-minute cooldown

### 3. Custom Settings

```bash
python agent_owl.py \
  --window "Claude" \
  --interval 60 \
  --screenshots 3 \
  --cooldown 10
```

Options:
- `--interval 60`: Check every 60 seconds
- `--screenshots 3`: Compare last 3 screenshots
- `--cooldown 10`: 10 minutes between prompts

## What You'll See

```
============================================================
  🦉 AGENT OWL - Smart AI Agent Monitor
============================================================
Window pattern: 'PowerShell'
Check interval: 90s
Screenshots to compare: 4
Cooldown: 15 minutes
Screenshot directory: screenshots/

How it works:
  1. Takes screenshot every 90s
  2. Compares last 4 screenshots
  3. Only prompts if screenshots identical (no new output)
  4. Waits 15 minutes between prompts

Press Ctrl+C to stop
============================================================

============================================================
Running check cycle...
✓ Found window: Windows PowerShell
Collecting screenshots (1/4)...
Waiting 90s until next check...
```

## Understanding the Output

- **"Collecting screenshots"**: Building screenshot history
- **"Agent is ACTIVE"**: Screenshots show changes (agent working)
- **"Agent appears TRULY idle"**: Screenshots identical (frozen)
- **"Cooldown active"**: Too soon to send another prompt
- **"Sending prompt"**: Actually sending continuation message

## Next Steps

1. **Try it out**: Run with your AI agent window
2. **Tweak settings**: Adjust interval/screenshots/cooldown as needed
3. **Create config**: Save your settings to a JSON file
4. **Build verification**: Create custom plugins for your use case

## Need Help?

- Read the full README.md
- Check example configs in `configs/`
- See example plugins in `examples/`

**Happy Monitoring! 🦉**
