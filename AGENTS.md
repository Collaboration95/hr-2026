# Project instructions

## Project context

This is the working repository for Hack & Hire Sustainability Edition 2026, a one-week proof-of-work project with real companies. The build period is 10–17 October 2026, followed by pitches to company teams on 17 October. Teams may have one, two, or three participants. Build a useful, demonstrable project with clear reasoning and evidence.

At setup, no track, team allocation, stack, or implementation is selected. `README.md` holds the current decision state. Use a recorded selection or the user's current instruction rather than inferring a track from an example or source document. Ask for the track only when an unresolved choice blocks the requested work.

The six available challenges are:

- **BlueNexus operations:** Analyze water-plant data for abnormal or inefficient operation. Help reduce energy, chemical, and water use while maintaining treatment performance.
- **BlueNexus ESG:** Measure and communicate autonomous water-system impact in a credible, useful client reporting format.
- **Bizsu leads:** Develop a scalable lead-generation and sales approach. The target audience needs confirmation.
- **Bizsu content:** Produce content that explains the air-conditioning product, introduces the team, and encourages customers to act. A strategy alone is insufficient under the spoken brief.
- **beez-fm:** Explain why an efficiency technology fits a building's energy profile, making the recommendation credible to owners and financial decision-makers.
- **SystemEarth:** Store and query geospatial layers across time and space efficiently while preserving information needed for plot-level compliance decisions.

## Read the right context

For substantive project work, read the current status in `README.md` and then the relevant sections below. Read the actual file contents; a filename or Markdown link is only a pointer. A small unrelated edit does not require loading every reference.

| Task | Read | What it contributes |
| --- | --- | --- |
| Compare or select tracks; define the selected problem | `docs/problem_statement_reference.txt` | Printed briefs, role fit, expected outcomes, and optional approaches. |
| Plan or build a company solution; prepare questions or a pitch | `docs/transcript_rules_and_constraints.txt` | Spoken clarifications, practical scope, targets, data offers, and unresolved company questions. |
| Design or evaluate SystemEarth work; verify slide expectations | `docs/sustainability_kickoff_reference.txt` | Layer selection, encoding/sample prototype, and storage, query, and decision/pixel fidelity measures. |
| Register, rank tracks, plan deadlines, or resolve conflicting instructions | `docs/event_rules_and_open_questions.txt` | Forms, dates, allocation changes, finals/workshop details, and cross-source differences. |

For implementation, read both the selected printed brief and its spoken guidance. Use `docs/sources/` PDFs only when exact wording or a source discrepancy requires them.

## Interpret the requirements faithfully

- The printed Bizsu lead brief targets homeowners; the spoken brief targets Singapore SMEs. Keep this unresolved until confirmed. The 100-email/20%-response targets belong to spoken lead generation; 30,000 views belongs to spoken content. These are not universal judging criteria.
- SystemEarth's printed guidance requests a working prototype; speech is less firm. Preserve that distinction. Existing algorithms and freely chosen datasets/use cases are allowed. Compare against original layers and explain pipeline choices and AI outputs.
- BlueNexus does not expect a full industrial AI platform within the week. Exact ESG impact figures are not essential when the measurement method and client reporting format are usable.
- Company data offers do not establish working access. Identify missing data early. Clearly label sample or synthetic data and assumptions.
- Keep required work, suggestions, performance targets, and unknowns distinct. Preserve source differences rather than silently choosing a convenient interpretation.
- Event dates describe the October 2026 schedule. Use recorded company or organizer updates when interpreting active deadlines. Workshop attendance is optional and testimonial priority is not a guarantee.

## Working conventions

- Focus on a small, complete project slice that can be demonstrated within the week. Record the selected track, agreed scope, data access, and important decisions in `README.md` as they become known.
- Maintain the current references in place. Use clear headings and ordinary bullets. Preserve meaningful qualifications when editing.
- Choose implementation tools for the confirmed problem. No runtime, package manager, build, or test commands exist yet; document the actual commands once introduced. Verify changes using the checks appropriate to the resulting implementation.
- When delegating user-authorized grunt work, prefer GPT-6 Luna when available. The main agent reviews and integrates the result.
- For all GitHub access, use the authenticated `gh` CLI exclusively; do not use GitHub connectors, APIs, or browser access. Local Git operations use `git`.
- Use the `guru/` prefix for new branches. Format commits as `<type>(<scope>): <imperative summary>`, such as `docs(context): update project guidance`.
