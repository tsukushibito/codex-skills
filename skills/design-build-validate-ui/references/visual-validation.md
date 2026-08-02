# Visual Validation

Validate the product's actual rendering. A design file, generated mockup, scene
tree, component source, or passing unit test cannot establish that the final UI
is visually correct.

## Build the capture matrix

Choose the smallest supported viewport and at least one representative larger
viewport. Add platform-specific cases such as portrait and landscape, safe-area
devices, browser zoom, desktop minimum window size, game UI scale, or high-density
display when applicable.

Capture the applicable states:

- default populated screen;
- selection, hover, pressed, and visible focus;
- modal, drawer, menu, tooltip, and confirmation;
- loading, empty, error, disabled, locked, and success;
- maximum rows or cards, long text, large values, and localization expansion;
- software keyboard, controller focus, or other input-specific state.

Use deterministic fixtures when visual comparison or regression evidence depends
on stable content.

## Inspect the images directly

Check:

- clipping, overlap, unintended scroll, and content outside safe bounds;
- whether the primary decision, evidence, and action dominate in the right order;
- density, redundant information, dead space, and competing emphasis;
- alignment, rhythm, grouping, consistent units, and readable line lengths;
- text size, contrast, background interference, and non-color state cues;
- long labels, wrapped values, truncated identifiers, and icon-label ambiguity;
- visible focus, active modal containment, disabled clarity, and actionable error
  placement;
- consistency with adjacent product surfaces without copying a reference
  product's trade dress.

Inspect at native resolution when small text, icons, or pixel-level clipping is
in question.

## Compare with references correctly

Compare information hierarchy, task flow, density, component proportions, and
interaction strategy. Do not treat pixel similarity as the goal. Explain
intentional deviations caused by the product's content, platform, input model,
design system, or technical constraints.

Keep generated concepts and reference screenshots labeled separately from actual
implemented captures.

## Iterate and report

Correct concrete issues, rerun affected behavior checks, and recapture every
changed state. Automated screenshot diffs can detect change but cannot judge
hierarchy or usability by themselves.

If the UI cannot be rendered, report what was inspected instead, why live
validation was unavailable, and the exact remaining manual step. Never describe
an unrendered implementation as visually verified.
