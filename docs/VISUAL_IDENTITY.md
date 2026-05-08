# Concord Lite Visual Identity

Concord Lite ships a deliberately non-default visual identity. This is a one-page
record of what we picked, what we rejected, and why — so future contributors don't
silently regress to generic SaaS aesthetics.

## TASTE CHECK output (Sprint 18 #89)

### Defaults rejected

| Default | Choice | Reason |
|---|---|---|
| Inter / Roboto / system-ui | `ui-monospace` stack (SF Mono → Menlo → Consolas) | Terminal aesthetic anchors a forensic/audit product. Monospace makes alignment of identifiers, timestamps, and spans visually exact. |
| Lucide / Heroicons / Tabler | Unicode glyphs (`▣ ● ◆ → ▲ ◉ ★ ✕ ✚ ✓`) | One glyph per span kind, no icon font dep, fully theme-able via CSS color. |
| Purple → blue gradient | Dark earth-tone palette anchored on gold (`#c8b560`) | Avoids the SaaS dark-mode default. Warm terminal feel. |
| Pill-shaped status badges | Square-edged outline pills | Matches the angular instrument-panel feel; reinforces the `<` `>` shell ASCII chrome. |
| SaaS hero/features/pricing/CTA template | Forensic instrument panel layout (top tabs + meta strip + main content area) | Concord is not a marketing site; it's a tool. |
| Animated gradient backgrounds | Solid surfaces with sharp 1.5px borders | Audit-grade products need stillness. |

### Distinguishing decisions

- **Monospace EVERYTHING** — chrome, body text, tabs, headers. Not just code.
- **Sharp corners** — `border-radius: 0` is the default. Buttons, cards, inputs are all square.
- **Gold accent** — `#c8b560` is the only "highlight" color; brick `#b85c4a` for errors,
  sage `#7a9e7e` for success, orange `#c4854a` for warnings.
- **Span kind colors** — earth tones (gold, brick, sage, orange, text-3) coded by
  semantic role, never decorative rainbow.
- **No animated gradients, no glowing borders, no mouse-tracking effects.**

### Copy rules

Banned phrases (audited, currently absent):
- "Welcome to Concord"
- "Get started for free"
- "Revolutionize your workflow"
- "Supercharge your productivity"
- "Seamlessly integrate"
- "Blazingly fast"
- "100% secure"
- "Something went wrong" → use `ErrorState` with status-specific copy

Preferred audit-grade language:
- *contract violation* — not "issue" or "problem"
- *repair patch* — not "fix" or "solution"
- *regression test* — not "test" alone
- *forensic span* — not "trace event"
- *failed agent* — not "broken agent"

## Self-distinguishing test

If you put Concord Lite next to 10 other AI-built SaaS dashboards, this is what
makes it not-generic:

1. **Monospace chrome** — almost all SaaS apps use Inter/Roboto. We don't.
2. **Earth-tone dark mode** — almost all SaaS dark themes lean blue/purple. We don't.
3. **Span kind glyphs** — ▣ ● ◆ → ▲ ◉ ★ ✕ ✚ ✓ are recognizably ours, not Lucide.
4. **Forensic span tree + waterfall + inspector** is a layout choice, not a default.
5. **Square corners, sharp borders** — most SaaS now defaults to rounded everything.

## When you change a color, font, or icon

1. Read this file first.
2. Update the rejected-defaults table if the choice changes.
3. Re-run the visual regression suite (`npm run test:visual:update` then commit).
4. Re-run axe-core: contrast budgets must still pass at WCAG 2.2 AA.
