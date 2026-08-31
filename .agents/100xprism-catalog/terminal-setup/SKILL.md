---
name: terminal-setup
description: Guide for optimal terminal and environment setup for Claude Code — Ghostty, statusline, tmux worktrees, voice dictation, and tab organization. Use when setting up a new machine or optimizing your Claude Code workflow.
category: engineering
tier: on-demand
allowed-tools: Read
---

Configure your terminal environment for maximum Claude Code productivity.

## Recommended Setup

### Terminal: Ghostty
- Synchronized rendering, 24-bit color, proper unicode support
- Color-code and name terminal tabs for context (e.g., "frontend", "api", "tests")
- One tab per task or git worktree

### Status Bar: /statusline
Run `/statusline` to configure your status bar to always show:
- Current context token usage
- Current git branch
- Active task / worktree name

This prevents context overload surprises mid-session.

### Tmux for Parallel Worktrees
- One tmux window per Claude task/worktree
- Name windows after the task: `tmux rename-window "auth-refactor"`
- Lets you switch between parallel Claude sessions without losing context

### Voice Dictation
- You speak 3x faster than you type
- Voice-dictated prompts are more detailed and natural → better Claude output
- macOS: press `fn fn` (double-tap fn key) to activate dictation anywhere
- Use voice for long context dumps, specs, and bug descriptions

## Quick Setup Checklist

- [ ] Install Ghostty (or iTerm2 with 24-bit color)
- [ ] Run `/statusline` to enable token + branch display
- [ ] Set up tmux with one window per active task
- [ ] Enable macOS voice dictation (`System Settings → Keyboard → Dictation`)
- [ ] Color-code tabs by domain (frontend=blue, api=green, infra=red)

## Tips

- Before starting a large task: open a new tmux window, name it, start fresh
- Use `ctrl+b` in tmux to run Claude agents in background
- The status line's context counter tells you when to `/compact` or start fresh
