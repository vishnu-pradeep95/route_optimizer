# Agents & Prompts Usage Guide

How to use the AI agent system in this project.

## TL;DR

| What you want | What to do |
|---|---|
| Start/resume a session | Use **Resume Work** prompt |
| Plan + build a feature | Talk to **Kerala Delivery Route Architect** agent |
| Quick bug fix or small task | Use **Quick** prompt |
| Debug something broken | Use **Debug** prompt |
| Check project status | Use **Progress** prompt |
| Verify a phase is done | Use **Verify Work** prompt |
| Save session for next time | Click **💾 Save Session** handoff in Architect |

---

## How Agents Work in VS Code Copilot

### Agents vs Prompts

| Concept | What it is | How to invoke |
|---|---|---|
| **Agent** | A persona with specific expertise and access to other agents | Type `@agent-name` in Copilot Chat |
| **Prompt** | A reusable workflow/recipe that runs step-by-step | Type `/prompt-name` in Copilot Chat |
| **Handoff** | A button the Architect agent shows to delegate to a sub-agent | Click the button in chat |

### Key difference

- **Agents** are conversational — you talk back and forth
- **Prompts** are more procedural — they follow a defined workflow
- **Handoffs** are how the Architect delegates work to specialized agents

---

## The Architect Agent (Main Entry Point)

### Invoking it

```
@kerala-delivery-route-architect start Phase 0
@kerala-delivery-route-architect set up OSRM container
@kerala-delivery-route-architect add time windows to VROOM
```

### Does it use other agents automatically?

**Yes, but through handoffs you control.** Here's how it works:

1. You describe what you want to the Architect
2. The Architect thinks through the approach
3. It presents **handoff buttons** for delegating to specialized agents
4. **You click the button** to trigger the delegation

The Architect can also spawn sub-agents directly via `runSubagent` when it determines that's the right approach — but for major delegations, it uses the handoff buttons so you stay in control.

### Available Handoffs

| Button | Delegates to | When to use |
|---|---|---|
| 📋 Create Phase Plan | Plan | Break a phase into detailed tasks |
| 🚀 Start Implementation | Implementer | Build the next task from the plan |
| 🔍 Deep Research | Deep Researcher | Research a technology/approach in depth |
| 🧪 Review & Validate | Code Reviewer | Review code changes against project standards |
| 💬 Explain to Partner | Partner Explainer | Translate technical decisions for non-technical stakeholders |
| 💾 Save Session | Session Journal | Save context to `.planning/STATE.md` |
| 🐛 Debug Issue | Debugger | Scientific debugging with persistent state |
| 🗺️ Map Codebase | Codebase Mapper | Generate codebase analysis documents |
| ✅ Verify Phase | Verifier | Verify a phase achieved its goals |
| 📝 Check Plan | Plan Checker | Validate a plan before execution |

### Typical Workflow

```
1. @kerala-delivery-route-architect "Let's start Phase 1"
2. Architect reads design doc, discusses approach
3. You click 📋 Create Phase Plan → Plan agent creates task list
4. You click 📝 Check Plan → Plan Checker validates it
5. You click 🚀 Start Implementation → Implementer builds task 1
6. (repeat for each task)
7. You click 🧪 Review & Validate → Code Reviewer checks everything
8. You click ✅ Verify Phase → Verifier confirms phase goals met
9. You click 💾 Save Session → Journal agent saves context
```

---

## Prompts (Direct Workflows)

### `/resume-work` — Start of Every Session

**Use this first when you open VS Code.** It:
1. Reads `.planning/STATE.md` for context
2. Checks for interrupted work (debug sessions, uncommitted changes)
3. Runs a health check (pytest, Docker)
4. Presents a briefing with recommended next action
5. Proactively loads relevant files

```
/resume-work
```

### `/debug` — Systematic Debugging

When something is broken:

```
/debug The OSRM container returns 400 on distance matrix requests
```

It will:
1. Ask for symptoms, expected behavior, recent changes
2. Spawn the Debugger agent
3. Create a persistent debug file at `.planning/debug/`
4. Use scientific method (hypotheses → experiments → conclusions)

### `/quick` — Small Tasks

For obvious fixes that don't need the full plan-check-verify cycle:

```
/quick Add a docstring to the OSRMAdapter.get_route method
/quick Fix the typo in config.py
/quick Add a test for the geocoding cache hit path
```

### `/verify-work` — Validate What's Built

After building features:

```
/verify-work Verify Phase 1 deliverables
```

It runs automated checks (tests, stub detection, wiring), then walks you through manual verification items one at a time.

### `/progress` — Where Are We?

```
/progress
```

Shows: current phase, test status, open items, blockers, recent decisions, and recommends next action.

---

## Other Agents (Standalone Use)

You can also talk to specialized agents directly without going through the Architect:

### `@session-journal`

```
@session-journal save       # Append entry to journal
@session-journal load       # Read and summarize journal
@session-journal resume     # Full context restore + health check
```

### `@debugger`

```
@debugger pytest is failing on test_vroom_adapter with a timeout error
```

### `@codebase-mapper`

```
@codebase-mapper Map the tech stack and integrations
@codebase-mapper Analyze architecture and structure
@codebase-mapper Review code quality and conventions
@codebase-mapper Flag concerns and risks
```

Writes analysis to `.planning/codebase/`.

### `@verifier`

```
@verifier Check if Phase 0 deliverables are complete
```

### `@plan-checker`

```
@plan-checker Review the Phase 1 plan for gaps
```

### `@code-reviewer`

```
@code-reviewer Review the changes I just made to core/routing/
```

### `@implementer`

```
@implementer Build the OSRM distance matrix endpoint
```

### `@deep-researcher`

```
@deep-researcher Compare VROOM vs OR-Tools for our use case
```

### `@partner-explainer`

```
@partner-explainer Explain why we need PostGIS instead of regular PostgreSQL
```

---

## MCP Servers (Auto-Available)

Two MCP servers are configured in `.vscode/mcp.json` and start automatically:

| Server | What it does | Example use |
|---|---|---|
| **Context7** | Fetches library documentation | Agents use it to look up VROOM, FastAPI, pytest docs |
| **Brave Search** | Web search | Agents use it to search for error solutions, tutorials |

You don't need to install or start these — `npx` handles it automatically.

---

## Directory Structure

```
.github/
  agents/           # Agent definitions (personas + handoffs)
  instructions/     # Shared rules (TDD, git, checkpoints, etc.)
  prompts/          # Reusable workflows (/debug, /quick, etc.)
  skills/           # Multi-step skill workflows

.planning/          # Working directory for structured artifacts
  debug/            # Active debug sessions
  debug/resolved/   # Completed debug sessions
  phases/           # Phase verifications and UAT results
  codebase/         # Codebase analysis documents
  templates/        # Templates for DEBUG.md, UAT.md, etc.

docs/                        # All documentation files
  DEPLOY.md, SETUP.md, GUIDE.md, CSV_FORMAT.md, etc.
```

---

## Quick Reference Card

| Situation | Action |
|---|---|
| Starting a new day | `/resume-work` |
| Planning a phase | `@kerala-delivery-route-architect` → 📋 |
| Building features | `@kerala-delivery-route-architect` → 🚀 |
| Something broke | `/debug` |
| Small fix needed | `/quick` |
| Need to research | `@kerala-delivery-route-architect` → 🔍 |
| Done building, need to verify | `/verify-work` |
| Where was I? | `/progress` |
| End of session | `@kerala-delivery-route-architect` → 💾 |
| Explain to partner | `@kerala-delivery-route-architect` → 💬 |
