# VeriFix interface redesign

## Diagnosis
The previous UI presented operator controls, implementation details, partner marketing,
financial projections, benchmark statistics and source-code editors at the same level.
The initial deployed JavaScript failed to parse (an apostrophe in a Python-generated
JavaScript string), leaving empty statistics and a nonfunctional case selector.

## Approaches considered
1. **Restyle the old dashboard:** low migration risk but preserves its information overload.
2. **Marketing landing page plus separate app:** clear introduction but adds a detour before inspecting evidence.
3. **Task-oriented workspace with progressive disclosure — selected:** one interface,
five destinations, one primary action, real evidence within one click.

## Information architecture
- **Overview:** plain-language explanation, bounded measured comparison, one verified record, workflow.
- **Run history:** searchable and filterable records, ten rows at a time, keyboard-accessible inspector.
- **Run a benchmark:** fixed cases, deliberate confirmation, advanced fault tests collapsed.
- **Evidence library:** separate Neatlogs, Entire, projected finances and upstream contribution.
- **System & quality:** live diagnostics, operator documentation, release report and known limitations.

## Visual system
| Decision | Implementation |
|---|---|
| Palette | Off-white canvas, white surfaces, forest-green primary actions |
| Typography | System sans-serif; monospace only for code and identifiers |
| Hierarchy | One page heading, compact section headings, one primary CTA per workflow |
| Layout | Persistent desktop navigation, responsive mobile navigation and stacked cards |
| Density | Three contextual measurements, not a wall of unrelated counters |
| Evidence | Timestamps, run identifiers and sample limitations adjacent to claims |
| Accessibility | Semantic landmarks, labels, focus outlines, skip link, reduced motion, modal focus management |

## Engineering decisions
- HTML, CSS and JS are separate source files. A single deterministic builder embeds
  them for both Lambda and Pages; no third-party frontend CDN, font or package runtime.
- A new read-only workspace endpoint avoids startup CLI calls and duplicate raw JSON.
- Native dialogs, event delegation and a small explicit state object replace inline event handlers.
- Render untrusted data as escaped text. Never use API-supplied HTML as markup.
- No global `fetch` monkey-patch; every request goes through an explicit client boundary.
- HTTP and schema errors are visible; preserve and label stale data, not fake replacement data.
- Timeouts stop client waiting, not the backend process. Mutating requests are never auto-retried.
- Public code execution is restricted to four known benchmark repositories. Custom Python
  and arbitrary paths require an operator token; a worktree is not a hostile-code sandbox.

## Accessibility and usability limits
Automated axe checks and agent-reviewed screenshots are evidence of checks, not
proof of universal accessibility. No human usability panel or real-user A/B study
was conducted. Interface copy is English; locale-aware numbers and dates were checked,
but full translation/RTL support is not claimed.
