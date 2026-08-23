# UI Resource Research — Magic UI, Watermelon UI, and the Neighboring Landscape

*Snapshot date: 2026-08-23. Sources verified live (sites, GitHub, public JSON APIs).*
*Purpose: inform Phase 3.5 (`docs/design_system.md` + `web/style.css` pass) and Phase 3.6 invite-card art.*

## TL;DR

- **Magic UI** (magicui.design) and **Watermelon UI** (ui.watermelon.sh) are both
  **React + TypeScript + Tailwind + Motion (framer-motion) component registries** in the
  shadcn "copy-paste the source into your own repo" tradition.
- **Neither (nor any of their neighbors) can run in this repo as-is** — GateKeyp's browser
  app is zero-dependency vanilla JS (`web/app.js`), no `package.json`, no build step, tokens
  already hand-rolled in `web/style.css`. All of these libraries ship `.tsx` snippets that
  assume React, Tailwind, and a bundler.
- They are **reference material, not dependencies**: a taxonomy of effects/motion to either
  borrow from deliberately (as plain CSS / SVG / a few dozen lines of vanilla JS) or
  consciously decline. Several individual techniques (grid/noise/stripe/retro-grid
  backgrounds, marquee, shimmer, aurora-as-gradient, `prefers-reduced-motion` handling) are
  pure CSS/SVG/JS and fully transplantable.
- **Watch-out for Phase 3.5:** this exact genre of library ("animated hero, aurora gradient,
  border beam, bento grid, glowing spotlight card") is *the* generic AI-SaaS look. The
  roadmap's "no generic generated-look" rule means these read more as a **decline list** than
  a shopping list. Are.na-minimal wants quiet editorial warmth, not animated shine.

## Magic UI — `magicui.design` / `github.com/magicuidesign/magicui`

- Built by **Dillion Verma**. **MIT license**, 22k+ stars, 1.1k forks, ~1.4k commits.
- Self-description: *"UI Library for Design Engineers. Animated components and effects you
  can copy and paste into your apps. Free. Open Source."*
- **Stack:** React + TypeScript + Tailwind CSS + **Motion**; drops in as a companion to
  shadcn/ui. Distributed as a shadcn registry (raw `.tsx` files under `registry/magicui/`,
  `registry.json` manifest), installed via the shadcn CLI or by copying the file
  (`npx shadcn add ...`, dependencies: `motion`, `class-variance-authority`, `lucide-react`,
  `tw-animate-css`).
- Also monetizes **Magic UI Pro** (50+ landing-page blocks/templates) and is cross-promoting
  a sibling **"Glyph Matrix UI"** library.
- **Component taxonomy (~89), grouped:**
  - *Special effects:* Animated Beam, Border Beam, Shine Border, Magic Card, Glare Hover,
    Meteors, Confetti, Particles, Animated Theme Toggler.
  - *Text/animations:* Blur Fade; Text Animate, Typing Animation, Line Shadow Text, Aurora
    Text, Video Text, Number Ticker, Animated Shiny Text, Animated Gradient Text, Text
    Reveal, Dia Text Reveal, Hyper Text, Word Rotate, Scroll Based Velocity, Sparkles, Text
    Morphing, Spinning Text, Text Highlighter, Text 3D Flip.
  - *Buttons:* Rainbow, Shimmer, Ripple.
  - *Backgrounds:* Flickering Grid, Animated Grid Pattern, Retro Grid, Ripple, Dot Pattern,
    Grid Pattern, Hexagon Pattern, Striped Pattern, Interactive Grid Pattern, Light Rays,
    Noise Texture. *(These are largely pure CSS keyframes/SVG — the most transplantable group.)*
  - *Widgets:* Marquee, Bento Grid, Animated List, Dock, Globe, Tweet Card, Orbiting
    Circles, Avatar Circles, Icon Cloud, Terminal, Hero Video Dialog, Progressive Blur,
    Dotted Map.
  - *Community/original:* Shiny Button, File Tree, Code Comparison, Scroll Progress, Neon
    Gradient Card, Comic Text, Kinetic Text, Warp Background, Pixel Image, Pulsating Button,
    Interactive Hover Button, Animated Circular Progress Bar, Backlight, Cool Mode.

## Watermelon UI — `ui.watermelon.sh` / `github.com/WatermelonCorp/watermelon-platform`

- "Premium components, dashboards & blocks — high-quality **React component registry**."
  **MIT**, ~300 stars, 24 forks, ~760 commits — a **brand-new project**, fast-moving but
  unproven (tiny community so far).
- **Stack:** React 18 + Vite + TypeScript + **shadcn/ui** (has `components.json`), Tailwind;
  dashboards use `recharts` + `@tabler/icons-react`.
- It is a **registry marketplace pattern**: MDX files auto-discover components + dashboards,
  live preview, one-click copy of install commands, ⌘K search, dark mode. Categories so far:
  buttons, cards, inputs, forms, navigation; plus dashboard templates (metric cards, charts,
  tables).
- Useful mainly as a **signal of the current "design engineer" ecosystem trend** (shadcn
  registry → full marketplace + dashboards), not as code we can use.
- **Naming hazard:** npm's `watermelon-ui` is an *unrelated, abandoned 2018 ISC package*
  (12 downloads/month). The real project is the GitHub org `WatermelonCorp`. Don't install
  anything by that npm name.

## The similar ecosystem (all React unless noted)

| Library | Home / Repo | Stack | License | Distribution |
|---|---|---|---|---|
| **Magic UI** | magicui.design / magicuidesign/magicui | React+TS+Tailwind+Motion | MIT | shadcn registry copy-paste |
| **Watermelon UI** | ui.watermelon.sh / WatermelonCorp/watermelon-platform | React+Vite+TS+Tailwind+shadcn | MIT | registry marketplace |
| **Aceternity UI** | ui.aceternity.com | React+TS+Tailwind+Motion | Free core; paid Pro | copy-paste + paid blocks |
| **React Bits** | reactbits.dev / DavidHDev/react-bits | React (Motion optional) | MIT | copy-paste components |
| **Motion Primitives** | motion-primitives.com / ibelick/motion-primitives | React+Motion+Radix | OSS core; paid Pro | copy-paste / package |
| **Animata** | animata.design | React | MIT | copy file into repo (a11y-forward) |
| **shadcn/ui** | ui.shadcn.com | React/TW; any shadcn prebuilt | MIT | CLI/registry (root of the genre) |
| **Tweakcn** | tweakcn.com / jnsahaj/tweakcn | React+Tailwind+shadcn | free tool | visual no-code shadcn *theme editor* |
| **HyperUI** | hyperui.dev | **plain HTML + Tailwind** | MIT | copy-paste markup (marketing/app/neobrutalism) |

- **Aceternity UI (Manu Arora):** the archetype — 200+ components/blocks/templates, "shadcn
  for magic effects"; heavy on parallax, bento, aurora, glowing borders, device mockups.
  Free core + paid lifetime "All-Access".
- **React Bits (David H. Dev):** more playful physical/micro-interaction pieces
  (AnimatedContent, Particles, Rat, Aurora, blob cursors, spotlight/tilted cards).
- **Motion Primitives (ibelick):** opinionated animated **primitives** on Motion + Radix —
  closer to a component system than one-off effects; clean "motion language" to crib.
- **Animata:** 155+ components, MIT "own the code" ethos; unusually explicit about
  **keyboard focus, screen-reader labels, reduced-motion fallbacks baked in** — the one to
  imitate for a11y discipline.
- **HyperUI** is the outlier: **plain HTML + Tailwind classes** (no JS framework), so its
  *markup structure* is the most directly readable — includes a `neobrutalism` category, a
  useful counterpoint when tuning how "minimal" Are.na-minimal should be.
- **Truly framework-agnostic tier** (worth knowing, all MIT): **Shoelace** (web components),
  plus CSS/SVG generators (Haikei, CSS shadow/gradient/glass tools) for standalone assets
  like invite-card ornaments.

## What is actually transplantable here (vanilla, zero-dep)

From the registries above, these techniques are pure CSS/SVG/JS and can be ported by hand into
`web/style.css` / `web/app.js` / the Phase-3.6 canvas renderer:

1. **Patterned backgrounds:** grid/dot/striped/hexagon/retro-grid via repeating gradients or
   inline SVG data-URIs; **noise** via tiny base64 PNG or SVG turbulence. Cheap, on-brand
   texture for paper surfaces and invite cards.
2. **Marquee** — the classic pure-CSS translateX loop (respects `prefers-reduced-motion`).
3. **Shimmer / shine border** — thin moving highlight on hairline borders; the only "effect"
   that arguably survives the Are.na-minimal filter, and only sparingly (e.g. live-radio
   "ON AIR" pulse in Phase 6, invite-card accent).
4. **Number ticker / text reveal / blur-fade** — a few lines of IntersectionObserver + CSS
   transitions; calm versions fit the "quiet motion" brief.
5. **Motion language for the design system:** steal *durations/easings* vocabulary from
   Motion Primitives/Magic UI (e.g. eased 150–300ms in/out, springy only for celebratory
   actions), wrap it in `@media (prefers-reduced-motion: reduce)`.
6. **A11y checklist as components, not afterthought** — from Animata's stated guarantees.

## Guidance vs. Phase 3.5 "no generic generated-look"

- **Borrow:** restrained versions of #1–#6 above, the a11y/motion discipline, and the
  *pattern vocabulary* for classifying our own components.
- **Decline:** aurora gradients, animated beams, glowing borders, bento grids, orbiting
  circles, morphing text, gradient text, particle fields, device mockups, emoji-filled
  dashboards, parallax hero, spotlight cards. These are the current "AI-generated" wallpaper
  and directly contradict Are.na-minimal.
- **Rule of thumb to record in `docs/design_system.md`:** if a component would look at home
  in the gallery of any of the above sites, it is off-brief. Motions must be short, mostly
  subtle, always reducible.

## Sources

- magicui.design and /docs/components; github.com/magicuidesign/magicui; raw
  `registry.json` (component list + shadcn registry format).
- ui.watermelon.sh; github.com/WatermelonCorp/watermelon-platform (README + license).
- ui.aceternity.com; github.com/DavidHDev/react-bits; github.com/ibelick/motion-primitives;
  animata.design; github.com/jnsahaj/tweakcn (GitHub search API); hyperui.dev.
- Repo ground-truth: `web/style.css` token block (fonts, paper/ink/line/accent/status
  colors, shadows, radii, spacing scale, focus ring, dark theme) confirmed present today.
