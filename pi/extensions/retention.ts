/**
 * Defense-in-depth retention for Pi.
 *
 * Emit-time filtering already parks resolver modules in pi/100xprism-catalog/.
 * This extension re-asserts the filtered skill roots on discover so a stray
 * full modules/ path is never the only source of skills from this package.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent/hooks";

const HERE = dirname(fileURLToPath(import.meta.url));
const PI_ROOT = join(HERE, "..");

export default async function (pi: ExtensionAPI) {
  pi.on("resources_discover", async (event) => {
    const skillsDir = join(PI_ROOT, "skills");
    const promptsDir = join(PI_ROOT, "prompts");
    const projectSkills = join(event.cwd, ".pi", "skills");
    const projectPrompts = join(event.cwd, ".pi", "prompts");

    const skillPaths: string[] = [];
    const promptPaths: string[] = [];

    // Prefer project-local filtered tree when present (100xprism init / emit-pi).
    if (existsSync(projectSkills)) skillPaths.push(projectSkills);
    else if (existsSync(skillsDir)) skillPaths.push(skillsDir);

    if (existsSync(projectPrompts)) promptPaths.push(projectPrompts);
    else if (existsSync(promptsDir)) promptPaths.push(promptsDir);

    // Soft assert: package manifest should stay well under 68 indexed skills.
    const manifestPath = existsSync(join(event.cwd, ".pi", ".100xprism-pi-manifest.json"))
      ? join(event.cwd, ".pi", ".100xprism-pi-manifest.json")
      : join(PI_ROOT, ".100xprism-pi-manifest.json");
    if (existsSync(manifestPath)) {
      try {
        const m = JSON.parse(readFileSync(manifestPath, "utf8"));
        if (Array.isArray(m.skills) && m.skills.length >= 68) {
          console.warn(
            "100xprism retention: manifest lists >= 68 skills — emit-pi may have run with profiles=all",
          );
        }
      } catch {
        /* ignore */
      }
    }

    return {
      skillPaths: skillPaths.length ? skillPaths : undefined,
      promptPaths: promptPaths.length ? promptPaths : undefined,
    };
  });
}
