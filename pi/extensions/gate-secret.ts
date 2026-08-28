/**
 * 100xprism gate + secret enforcement for Pi.
 *
 * Shells out to the existing Python hooks so logic cannot drift from Claude Code /
 * Codex. Maps Pi tool_call events into the Claude Code PreToolUse JSON shape those
 * hooks already understand.
 *
 * Exit 2 from a hook = block.
 */
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent/hooks";

const HERE = dirname(fileURLToPath(import.meta.url));
// pi/extensions → repo root (package install) or fall back via env
const REPO = process.env.HUNDRED_X_HOME
  || process.env.DEV_100X_HOME
  || join(HERE, "..", "..");

function hookScript(name: string): string | null {
  const p = join(REPO, "hooks", name);
  return existsSync(p) ? p : null;
}

function runHook(scriptName: string, event: Record<string, unknown>): { block: boolean; reason: string } {
  const script = hookScript(scriptName);
  if (!script) {
    return { block: true, reason: `100xprism hook unavailable: ${scriptName}` };
  }
  const result = spawnSync("python3", [script], {
    input: JSON.stringify(event),
    encoding: "utf8",
    cwd: (event.cwd as string) || process.cwd(),
    env: process.env,
  });
  if (result.status === 2) {
    return {
      block: true,
      reason: (result.stderr || result.stdout || "blocked by 100xprism hook").trim(),
    };
  }
  if (result.status !== 0) {
    return {
      block: true,
      reason: (result.error?.message || result.stderr || result.stdout
        || `100xprism hook failed: ${scriptName}`).trim(),
    };
  }
  return { block: false, reason: "" };
}

function isBash(event: { toolName: string }): boolean {
  return event.toolName === "bash";
}

function isWriteLike(event: { toolName: string }): boolean {
  return event.toolName === "write" || event.toolName === "edit";
}

export default async function (pi: ExtensionAPI) {
  pi.on("tool_call", async (event, ctx) => {
    if (isBash(event)) {
      const command = (event.input as { command?: string })?.command ?? "";
      const payload = {
        hook_event_name: "PreToolUse",
        tool_name: "Bash",
        cwd: ctx.cwd,
        tool_input: { command },
      };
      const { block, reason } = runHook("pretooluse-gate.py", payload);
      if (block) {
        return { block: true, reason: reason || "100xprism gate: run /skill:gate first" };
      }
    }

    if (isWriteLike(event)) {
      const input = event.input as {
        path?: string;
        content?: string;
        newText?: string;
        oldText?: string;
      };
      // Pi edit uses different field names than Claude Code; map best-effort.
      const content = input.content ?? input.newText ?? "";
      const payload = {
        hook_event_name: "PreToolUse",
        tool_name: event.toolName === "write" ? "Write" : "Edit",
        cwd: ctx.cwd,
        tool_input: {
          file_path: input.path,
          content,
          new_string: content,
        },
      };
      const { block, reason } = runHook("pretooluse-secret-scan.py", payload);
      if (block) {
        return { block: true, reason: reason || "100xprism secret-scan blocked this write" };
      }
    }
  });
}
