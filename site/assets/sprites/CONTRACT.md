# Sprite contract (shared by all sprite artists)

Goal: tiny, cute, hand-made-feeling pixel critters for the Plotline explainer site, so it feels less
templated and more like a person made it. Topical to forests, map cells, shrinking data, speed.

## File format
- One file per creature: `site/assets/sprites/<name>.svg`. Pure SVG, **no JS, no external refs, no images**.
- `viewBox="0 0 32 32"` (pixel grid; draw with 1x1 `<rect>`s or small path runs, `shape-rendering="crispEdges"`).
  A 2-sprite-wide creature may use `0 0 48 32`; state it in the file comment.
- Palette: only these (site tokens), plus pure white/near-black outline `#0F1222` and one cheek-blush `#FF9FB0`:
  forest `#15803D` / light `#4ABA78` / wash `#DCF5E4`, canopy dark `#2F6B47`, loss orange `#E8590C`,
  highlight yellow `#FFE45C`, pen blue `#2F45FF`, water `#2B6CB0`, declared purple `#7A5AF8`, paper `#F6F7F9`.
- Every creature has a 1px dark outline, a readable silhouette at 64px display size, and big eyes (cute > realistic).

## Poses (actions)
Each pose is a `<g class="pose" data-pose="NAME">` containing the full drawing for that pose.
Required for every creature: `idle`, `happy`, `sad`. Then 2 or more creature-specific poses (e.g. `wave`, `dance`,
`sprint`, `squish`, `sleep`). Aim for 5 poses total. Poses that animate (blink, bob, wiggle) use CSS
`@keyframes` inside a `<style>` in the SVG, scoped under `.pose[data-pose=NAME] ...`, steps() easing preferred for a
chunky pixel feel, and wrapped in `@media (prefers-reduced-motion: no-preference)`.
All poses other than the default should be hidden by the shared sheet via `.pose{display:none}` and
`svg[data-pose=idle] .pose[data-pose=idle]{display:inline}` rules (the engine sets `data-pose` on the root `<svg>`).
Put those exact show/hide rules at the top of your own `<style>` so the file also works standalone in a browser.

## Personality
Each creature gets a `<title>` (accessible name) and a `<desc>` containing: name, one-line personality, and the
speech-bubble line for each pose (`idle: "..."`). Lines are short, dry, friendly, max 7 words, no emojis, no
claims that change project facts. Numbers, if used, must be: 744,732 cells identical; 99% smaller (623 KB to 6.1 KB);
44x faster re-checks of registered plots; 17/17 plots.

## Rules
- Write ONLY inside your assigned filenames/directory. Do not edit any HTML/CSS/JS elsewhere in `site/`.
- Never include real plot outlines or supplier data.
- When finished, run `python3 -m http.server <ephemeral port>` from `site/` yourself ONLY if you need to check;
  you cannot browse, so validate by `xmllint --noout` and by eye-reasoning pixel coordinates. Add `site/assets/sprites/<name>.preview.html`
  is NOT needed; the engine/lab page will show your poses.
- Final reply: list the files, each pose, and each speech line, in under 200 words.
