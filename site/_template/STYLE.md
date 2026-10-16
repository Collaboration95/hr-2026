# Voice and copy rules (revision pass)

The pack is read by the team **and by SystemEarth**. Write it as a neutral, third-person project document: a technical report with good diagrams, not a recap addressed to the team. Facts, numbers, diagrams, sections and caveats stay. Only tone and sentence structure change, plus the cuts below.

## Rules

1. **Third person, neutral.** No "you", "we'll", "our team", "tomorrow we". Prefer the subject doing the work: "Plotline stores…", "The decision layer…", "The benchmark measures…". "We" is acceptable sparingly for decisions the project made ("we dropped canopy %") where the passive would be awkward, but never to address the reader.
2. **Do not narrate SystemEarth to itself.** Not "SystemEarth asked how to…" or "SystemEarth wants…". State the problem directly ("EUDR screening intersects…"), or cite the brief neutrally ("The challenge brief asks for…", "The brief's evaluation measures are…").
3. **No time references.** Remove "tomorrow", "tonight", "today", "the night before", "the morning of the finals", "next day", countdowns, "Phase X happened at 2 am" color. Keep dated facts only where the date is the fact (e.g. EUDR application dates; "Phase 1 … Phase 4" as labels; data release versions; the build period 10–17 Oct 2026 on the event page). Phase labels stay, but drop "(evening)", "(late night)", "(early morning)" style timing.
4. **No page narration.** Cut "This page tells…", "Step through the week below", "Start here", "Read this first", "In this section we'll…", "Scroll down to…". Headings and diagrams already say it.
5. **Lead with the point.** One claim per sentence. Cut windups ("The thing to understand is…", "Here's the key idea:"), rhetorical questions, and filler ("actually", "really", "simply", "basically").
6. **Fewer quips.** Big headings (h1, h2) are plain and descriptive, not slogans. "Keep the decision, not the data" and similar taglines may appear once inside body text (attributed as the brief's framing), never as an h1/h2. Avoid punchy fragments like "One band. Twenty counters." as headings; use "One band with 20 codes per cell".
7. **Labels:** "If you read nothing else" → "In brief". "Say it" notes → "Summary line". "Careful" notes stay but are phrased as scope statements ("These are mapped observations, not compliance findings."), not instructions to the team.
8. **Presentation and checklist pages** (`pitch`, `submit`): keep the content (structure, demo run-through, slide outline, Q&A, terminology, requirement matrix, run instructions, checklist) but write it as a neutral presentation guide and readiness record. "Likely judge questions" → "Questions and answers". "Words to use / avoid" → "Terminology" with the reason for each preferred term. Remove second-person coaching ("memorise", "don't say the supplier is lying") and replace with the neutral fact ("The results do not establish supplier intent; the evidence files were not supplied."). Remove the "night before / morning of" grouping; keep a single readiness checklist.

## Examples

| Before | After |
| --- | --- |
| SystemEarth asked how to store years of satellite forest maps compactly, query them fast, and still give every farm plot the same deforestation answer. Plotline's decision layer is 99% smaller, re-checks registered plots 44× faster, and gives the same answer for all 744,732 map cells. | EUDR screening intersects farm plots with years of forest maps, and repeats the check whenever a map updates. Plotline stores only the facts that check reads: a decision layer 99% smaller than the original layers, with identical answers for all 744,732 map cells and 44× faster re-checks of registered plots. |
| This page tells the whole thing at a normal level, then points to the page that goes deeper on each part. | *(cut)* |
| If you read nothing else | In brief |
| We chose SystemEarth on 10 October and were accepted on 11 October. Step through the week below. | Track: SystemEarth, 10–17 October 2026. |
| The edge: registered plots re-check 44× faster… Tomorrow we pitch it. | Registered plots re-check 44× faster; new boundaries about 5× faster. |
| Five ideas did most of the work. | Five changes account for most of the speed-up. |
| Phase 3 (15 Oct, late night): two small wins | Phase 3: a leaner reducer and a faster first batch call |

## Do not change

Numbers, units, sources, diagram behaviour, section ids (other pages link to them), class names, scripts, the private-data rules in `BRIEF.md`, or the "Synthetic" labels. Edit visible text only (including `aria-label`s, captions in JS strings, button labels and `<title>`/meta description). After editing, reload the page and confirm no console errors and that instruments still run.
