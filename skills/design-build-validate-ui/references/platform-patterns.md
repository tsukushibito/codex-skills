# Platform Patterns

Apply only the sections relevant to the requested product. Product conventions
and current platform guidance override these defaults.

## Games

- Determine whether the surface is moment-to-moment HUD, pause UI, loadout,
  inventory, hub, map, settings, or a modal decision. Their time pressure and
  information budgets differ.
- Design for the supported combination of controller, keyboard, mouse, and touch.
  Make focus movement spatially predictable and keep back/cancel hierarchical.
- Test readability at play distance, target resolution, safe areas, UI scale, and
  the most visually busy background state.
- Keep critical combat information glanceable; move planning and exhaustive
  numbers to low-pressure surfaces.
- Use engine-native layout and input systems. Preserve authoritative gameplay and
  persistence contracts outside presentation code.

## Web applications

- Prefer semantic document and control structure before custom interaction.
- Define narrow, medium, and wide behavior from content priority rather than
  desktop-first shrinking.
- Preserve keyboard order, browser zoom, text reflow, validation, history, deep
  links, and refresh behavior where applicable.
- Cover loading, partial data, network failure, stale data, permissions, empty
  results, and long user-generated content.

## Desktop applications

- Support resize, minimum window size, high-density displays, system text scaling,
  keyboard shortcuts, and predictable menu or command placement.
- Decide which panes may collapse, detach, resize, or scroll. Avoid nested scroll
  regions without a clear ownership boundary.
- Preserve selection and work state across dialogs, window changes, and
  recoverable failures.

## Mobile applications

- Respect safe areas, system bars, virtual keyboards, orientation policy, and
  dynamic text.
- Keep frequent actions reachable without putting destructive actions where they
  are easy to trigger accidentally.
- Design for touch first while preserving external keyboard and assistive input
  when supported.
- Test narrow widths, long localization, interrupted loading, offline behavior,
  permissions, and back navigation.

## Cross-platform products

Share task structure, terminology, and state semantics. Adapt navigation,
interaction, density, and control presentation to each platform instead of
forcing pixel-identical screens. Define which behaviors are invariant and which
are platform-specific before implementation.
