#!/usr/bin/env python3
"""
pair-loop.py — CLI orchestration for the /pair-loop handoff skill.

The interactive agent running the skill IS the coder; this CLI never simulates
coding. It owns: run bookkeeping (manifest + HANDOFF.md), the per-round budget
check, invoking the reviewer subprocess, and PR-body assembly. See
docs/superpowers/specs/2026-07-09-pair-loop-handoff-skill-design.md for the
full state machine.

Subcommands: start, budget-check, coder-done, review, finish.
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_manifest  # noqa: E402
import handoff  # noqa: E402
import reviewer  # noqa: E402
import _config  # noqa: E402
import _budget  # noqa: E402
import adapters.claude_code as claude_code  # noqa: E402
import adapters.codex as codex  # noqa: E402


def _git_dirty(cwd):
    r = subprocess.run(["git", "status", "--porcelain"], cwd=cwd,
                       capture_output=True, text=True)
    return bool(r.stdout.strip())


def _current_branch(cwd):
    r = subprocess.run(["git", "branch", "--show-current"], cwd=cwd,
                       capture_output=True, text=True)
    return r.stdout.strip() or "HEAD"


def cmd_start(args):
    cwd = os.path.abspath(args.cwd or ".")
    # The dirty-tree check must run before any manifest/HANDOFF.md side effects
    # are created — a rejected start must leave zero partial state behind.
    if _git_dirty(cwd):
        print("error: working tree is dirty — commit or stash before starting a pair-loop run",
              file=sys.stderr)
        sys.exit(1)
    cfg = _config.load_config()["pair_loop"]
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    branch = _current_branch(cwd)
    manifest = run_manifest.new_manifest(run_id, args.task, cwd, branch,
                                          cfg["coder"], cfg["reviewer"])
    run_manifest.save_manifest(manifest)
    handoff_path = os.path.join(cwd, handoff.HANDOFF_FILENAME)
    handoff.init_file(handoff_path, run_id, args.task, branch, cfg["coder"], cfg["reviewer"])
    print(json.dumps({"run_id": run_id, "manifest_path": run_manifest.manifest_path(run_id),
                      "handoff_path": handoff_path, "max_rounds": cfg["max_rounds"],
                      "coder": cfg["coder"], "reviewer": cfg["reviewer"]}))


def cmd_budget_check(args):
    manifest = run_manifest.load_manifest(args.run)
    per_run = _config.load_config()["budget"].get("per_run_usd")
    summaries = claude_code.scan(verbose=False) + codex.scan(verbose=False)
    cost = run_manifest.run_cost(manifest, summaries)
    _, level = _budget.status_for(cost["total"], per_run)
    print(json.dumps({"level": level, "spent": cost["total"], "limit": per_run}))
    sys.exit(2 if level == "alert" else 0)


CLAUDE_PROJECTS = os.path.join(os.path.expanduser("~"), ".claude", "projects")


def _guess_current_claude_session(cwd):
    """Best-effort: the most-recently-modified transcript file for this cwd's
    mangled project dir, at the moment this is called."""
    import _value
    mangled = _value.mangle_path(os.path.abspath(cwd))
    proj_dir = os.path.join(CLAUDE_PROJECTS, mangled)
    files = glob.glob(os.path.join(proj_dir, "*.jsonl"))
    if not files:
        return None
    newest = max(files, key=os.path.getmtime)
    return os.path.splitext(os.path.basename(newest))[0]


def _guess_current_codex_session(before_mtimes):
    """Best-effort: a Codex rollout file that appeared/changed after
    `before_mtimes` was snapshotted (see cmd_review)."""
    paths = glob.glob(os.path.join(codex.SOURCE_DIR, "**", "*.jsonl"), recursive=True)
    newest, newest_mtime = None, 0
    for p in paths:
        try:
            mt = os.path.getmtime(p)
        except OSError:
            continue
        if mt > before_mtimes.get(p, 0) and mt > newest_mtime:
            newest, newest_mtime = p, mt
    if not newest:
        return None
    with open(newest, errors="ignore") as f:
        for line in f:
            try:
                o = json.loads(line)
            except Exception:
                continue
            if o.get("type") == "session_meta":
                payload = o.get("payload") or {}
                return payload.get("session_id") or payload.get("id")
    return None


def cmd_coder_done(args):
    manifest = run_manifest.load_manifest(args.run)
    cwd = manifest["cwd"]
    if manifest["coder"] == "claude":
        session_id = _guess_current_claude_session(cwd)
    elif manifest["coder"] == "codex":
        # The coder's actual work happens between the previous CLI call and
        # this one, driven by the calling agent — not by this process — so
        # there's no "before" snapshot to take here the way cmd_review takes
        # `codex_before` right before invoking the reviewer subprocess.
        # Best-effort fallback: reuse _guess_current_codex_session with an
        # empty before-snapshot, which picks the single newest Codex session
        # file for this machine. Correct for the common single-active-session
        # case; could misattribute if multiple Codex sessions are running
        # concurrently in the same directory.
        session_id = _guess_current_codex_session({})
    else:
        session_id = None
    round_ = run_manifest.add_round(manifest, "coder", manifest["coder"], session_id=session_id)
    run_manifest.close_round(manifest, round_, findings_addressed=args.findings_addressed)
    handoff_path = os.path.join(cwd, handoff.HANDOFF_FILENAME)
    handoff.append_coder_round(handoff_path, round_["n"], manifest["coder"], args.summary)
    print(json.dumps({"round": round_["n"]}))


MAX_UNTRACKED_FILE_BYTES = 200_000  # guard against dumping something absurd (data file, lockfile) into the prompt


def _build_untracked_sections(cwd):
    """`git diff <branch>` never includes untracked (new, not-yet-`git add`-ed)
    files — but the pair-loop workflow explicitly tells the coder not to
    commit until the run finishes, so brand-new files stay untracked for the
    whole loop. Without this, the reviewer could approve a round having never
    seen a new file's contents at all. Show each untracked file's full
    current content (there's no "before" to diff against). Skip binaries and
    huge files gracefully rather than erroring the whole review out."""
    result = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
                            cwd=cwd, capture_output=True, text=True)
    sections = []
    for rel_path in result.stdout.splitlines():
        if not rel_path:
            continue
        abs_path = os.path.join(cwd, rel_path)
        try:
            if os.path.getsize(abs_path) > MAX_UNTRACKED_FILE_BYTES:
                sections.append(f"=== NEW (untracked) FILE: {rel_path} ===\n"
                                 f"[skipped — {os.path.getsize(abs_path)} bytes, over the "
                                 f"{MAX_UNTRACKED_FILE_BYTES}-byte review limit]\n")
                continue
            with open(abs_path, encoding="utf-8") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        sections.append(f"=== NEW (untracked) FILE: {rel_path} ===\n{content}\n")
    return sections


def _build_review_prompt(cwd, branch, handoff_path):
    result = subprocess.run(["git", "diff", branch], cwd=cwd, capture_output=True,
                            text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git diff against '{branch}' failed: {result.stderr.strip()}")
    diff = result.stdout
    untracked_sections = _build_untracked_sections(cwd)
    untracked_text = "\n".join(untracked_sections)
    if os.path.exists(handoff_path):
        with open(handoff_path, encoding="utf-8") as f:
            handoff_text = f.read()
    else:
        handoff_text = ""
    return (
        "You are reviewing a code change as an independent reviewer in a "
        "coder<->reviewer handoff loop. Read the diff, any new untracked "
        "files, and the prior handoff rounds below, then respond with a "
        "numbered findings list in the form "
        "'N. [category] file:line — description' (omit file:line if not "
        "applicable), followed by a final line that is EXACTLY "
        "'VERDICT: APPROVED' or 'VERDICT: CHANGES_REQUESTED'.\n\n"
        f"=== DIFF vs {branch} ===\n{diff}\n\n"
        + (f"{untracked_text}\n\n" if untracked_text else "")
        + f"=== HANDOFF SO FAR ===\n{handoff_text}\n"
    )


def cmd_review(args):
    manifest = run_manifest.load_manifest(args.run)
    cwd = manifest["cwd"]
    prompt = _build_review_prompt(cwd, manifest["branch"],
                                  os.path.join(cwd, handoff.HANDOFF_FILENAME))

    run_command = None
    if args.reviewer_cmd:
        fixed_cmd = json.loads(args.reviewer_cmd)

        def run_command(cmd, prompt, cwd, timeout):
            r = subprocess.run(fixed_cmd, input=prompt, cwd=cwd, capture_output=True,
                              text=True, timeout=timeout)
            return r.stdout

    codex_before = {p: os.path.getmtime(p) for p in
                    glob.glob(os.path.join(codex.SOURCE_DIR, "**", "*.jsonl"), recursive=True)} \
        if os.path.isdir(codex.SOURCE_DIR) else {}

    fallback_models = _config.load_config()["pair_loop"].get("fallback_models", {})

    # --reviewer-cmd fully overrides dispatch: the supplied argv is run verbatim
    # and no vendor binary is invoked, so requiring one on PATH would break the
    # override on exactly the machines it exists for.
    require_cli = not args.reviewer_cmd

    result = reviewer.invoke(manifest["reviewer"], prompt, cwd, run_command=run_command,
                             fallback_models=fallback_models, require_cli=require_cli)
    verdict = handoff.parse_verdict(result.output)
    if verdict is None:
        # one re-ask with a stricter prompt, then fall back to CHANGES_REQUESTED
        retry_prompt = prompt + "\n\nYour previous response had no parseable VERDICT line. Respond again, ending with exactly 'VERDICT: APPROVED' or 'VERDICT: CHANGES_REQUESTED'."
        result = reviewer.invoke(manifest["reviewer"], retry_prompt, cwd, run_command=run_command,
                                 fallback_models=fallback_models, require_cli=require_cli)
        verdict = handoff.parse_verdict(result.output)
    findings = handoff.parse_findings(result.output)
    if verdict is None:
        verdict = "CHANGES_REQUESTED"
        findings = findings or [{"n": 1, "category": "process",
                                  "location": "", "text": "reviewer produced no parseable verdict"}]

    actual_tool = manifest["reviewer"]
    if result.fallback_used:
        actual_tool = "claude" if manifest["reviewer"] == "codex" else "codex"
        manifest["reviewer_fallback"] = True
        # Record the model too: "claude reviewed claude" is only acceptable
        # because a different model ran, so the model is the evidence.
        manifest["reviewer_fallback_model"] = result.model

    session_id = (_guess_current_codex_session(codex_before) if actual_tool == "codex"
                  else _guess_current_claude_session(cwd))
    round_ = run_manifest.add_round(manifest, "reviewer", actual_tool, session_id=session_id)
    run_manifest.close_round(manifest, round_, findings=len(findings), verdict=verdict)
    handoff.append_reviewer_round(os.path.join(cwd, handoff.HANDOFF_FILENAME),
                                  round_["n"], actual_tool, findings, verdict)
    print(json.dumps({"verdict": verdict, "findings": findings,
                      "fallback_used": result.fallback_used,
                      "reviewer_model": result.model}))


def render_review_summary(manifest):
    """Markdown summary of the loop, for posting as a PR comment.

    A reviewer on GitHub otherwise sees only the final diff, with no evidence
    that an adversarial pass happened at all. This records who reviewed (and on
    which model, when one was pinned — the normal path uses each CLI's own
    default, which is not recorded), how many rounds it took, and how many
    findings were raised
    and resolved.
    """
    reviewer_rounds = [r for r in manifest["rounds"] if r["role"] == "reviewer"]
    coder_rounds = [r for r in manifest["rounds"] if r["role"] == "coder"]
    findings_raised = sum(r.get("findings") or 0 for r in reviewer_rounds)
    findings_addressed = sum(r.get("findings_addressed") or 0 for r in coder_rounds)

    reviewer_label = manifest["reviewer"]
    fallback_model = None
    if manifest.get("reviewer_fallback"):
        # Name the model explicitly — it is the only thing separating this from
        # a self-review, so burying it would misrepresent the result.
        actual = "claude" if manifest["reviewer"] == "codex" else "codex"
        fallback_model = manifest.get("reviewer_fallback_model")
        reviewer_label = f"{actual} (`{fallback_model}`)" if fallback_model else f"{actual} (model not pinned)"

    lines = [
        "## Pair-loop review",
        "",
        "| | |",
        "|---|---|",
        f"| Coder | {manifest['coder']} |",
        f"| Reviewer | {reviewer_label} |",
        f"| Rounds | {manifest['outcome']['rounds']} |",
        f"| Findings raised | {findings_raised} |",
        f"| Findings addressed | {findings_addressed} |",
        f"| Verdict | **{manifest['outcome']['verdict']}** |",
        "",
    ]

    if manifest.get("reviewer_fallback"):
        # State only what is known. We record the reviewer's model when we pin
        # one, but nothing here compares it to the coder's — so claiming the
        # models *differed* and claiming they *matched* are equally unfounded.
        # An earlier version asserted each in turn; both were wrong. Report the
        # facts (same vendor; model pinned or not) and let the reader judge.
        if fallback_model:
            warning = (
                f"> ⚠️ **Cross-vendor review unavailable.** The `{manifest['reviewer']}` "
                f"CLI was not on PATH, so the review ran on the coder's own vendor, "
                f"pinned to `{fallback_model}`. If that is not the model you code "
                f"with, this is a weaker-but-real second opinion; if it is, the "
                f"approval carries no independent signal."
            )
        else:
            warning = (
                f"> 🛑 **Independence unverified.** The `{manifest['reviewer']}` CLI was "
                f"not on PATH and no fallback model was configured, so the review ran "
                f"on the coder's own vendor at that CLI's default model — which may or "
                f"may not be the model the coder used. Nothing here checked. Set "
                f"`pair_loop.fallback_models` in `~/.100xprism/config.json` to pin one."
            )
        lines += [warning, ""]

    for r in reviewer_rounds:
        lines.append(
            f"- Round {r['n']} — {r.get('findings', 0)} finding(s), "
            f"{r.get('verdict', 'no verdict')}"
        )

    return "\n".join(lines) + "\n"


def post_pr_comment(pr, body, cwd, run=None):
    """Post `body` to PR `pr` via gh. Returns True on success.

    A failed post must not fail the run: the review itself already happened and
    is recorded in the manifest, so a network blip or a missing gh should warn,
    not discard the result.
    """
    run = run or (lambda cmd, **kw: subprocess.run(cmd, **kw))
    try:
        result = run(["gh", "pr", "comment", str(pr), "--body", body],
                     cwd=cwd, capture_output=True, text=True)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"warning: could not post review summary to PR #{pr}: {exc}", file=sys.stderr)
        return False
    if result.returncode != 0:
        print(f"warning: could not post review summary to PR #{pr}: "
              f"{(result.stderr or '').strip()}", file=sys.stderr)
        return False
    return True


def cmd_finish(args):
    manifest = run_manifest.load_manifest(args.run)
    # `finish` is called twice in the real workflow: once right after
    # approval (no --pr yet — the PR doesn't exist), and again with --pr once
    # it's actually opened (see modules/pair-loop/SKILL.md Step 5). Only
    # overwrite manifest["pr"] when a value was actually passed — otherwise a
    # bare re-run (or the first, PR-less call) would clobber an already
    # recorded PR number back to None.
    if args.pr is not None:
        manifest["pr"] = args.pr
    run_manifest.close_run(manifest, args.verdict, merged=None)

    handoff_path = os.path.join(manifest["cwd"], handoff.HANDOFF_FILENAME)
    transcript = open(handoff_path, encoding="utf-8").read() if os.path.exists(handoff_path) else ""
    body = (
        f"## {manifest['task']}\n\n"
        f"Pair-loop run `{manifest['run_id']}` — coder: {manifest['coder']}, "
        f"reviewer: {manifest['reviewer']}"
        + (" (fallback used)" if manifest.get("reviewer_fallback") else "") + "\n\n"
        f"<details><summary>Full handoff transcript ({manifest['outcome']['rounds']} rounds)</summary>\n\n"
        f"```\n{transcript}\n```\n\n</details>\n"
    )
    body_path = os.path.join(os.path.dirname(run_manifest.manifest_path(manifest["run_id"])),
                             f"{manifest['run_id']}-pr-body.md")
    with open(body_path, "w", encoding="utf-8") as f:
        f.write(body)

    # Only once the PR exists (the second `finish` call — see the comment above)
    # is there somewhere to post the summary.
    summary_posted = False
    if manifest.get("pr") is not None and not args.no_comment:
        summary_posted = post_pr_comment(manifest["pr"], render_review_summary(manifest),
                                         manifest["cwd"])

    print(json.dumps({"pr_body_path": body_path, "summary_posted": summary_posted}))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start")
    p_start.add_argument("--task", required=True)
    p_start.add_argument("--cwd", default=None)
    p_start.set_defaults(func=cmd_start)

    p_budget = sub.add_parser("budget-check")
    p_budget.add_argument("--run", required=True)
    p_budget.set_defaults(func=cmd_budget_check)

    p_coder_done = sub.add_parser("coder-done")
    p_coder_done.add_argument("--run", required=True)
    p_coder_done.add_argument("--summary", required=True)
    p_coder_done.add_argument("--findings-addressed", type=int, default=0)
    p_coder_done.set_defaults(func=cmd_coder_done)

    p_review = sub.add_parser("review")
    p_review.add_argument("--run", required=True)
    p_review.add_argument("--reviewer-cmd", default=None,
                          help="JSON array override for testing (bypasses codex/claude auto-detect)")
    p_review.set_defaults(func=cmd_review)

    p_finish = sub.add_parser("finish")
    p_finish.add_argument("--run", required=True)
    p_finish.add_argument("--verdict", required=True, choices=["APPROVED", "CHANGES_REQUESTED"])
    p_finish.add_argument("--pr", type=int, default=None)
    p_finish.add_argument("--no-comment", action="store_true",
                          help="skip posting the review summary to the PR")
    p_finish.set_defaults(func=cmd_finish)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
