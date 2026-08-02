# Interaction and Accessibility

Treat accessibility as part of the interaction contract, not a final visual
audit. When exact conformance criteria matter, consult current authoritative
platform and accessibility standards rather than relying on frozen values here.

## Input and focus

- Support every input method promised by the product.
- Keep keyboard and controller focus visible, ordered, and contained within the
  active modal or workspace.
- Make directional navigation match spatial relationships.
- Define initial focus, restored focus, back/cancel, submit, escape, and
  destructive confirmation behavior.
- Do not leave hidden, disabled, or background controls focusable.
- Keep pointer and touch targets separated enough for reliable activation.
- Avoid hover-only information and gesture-only required actions.

## Perception

- Communicate success, warning, selection, increase, decrease, and failure with
  text, iconography, shape, or position in addition to color.
- Maintain readable contrast across default, hover, pressed, disabled, selected,
  and focus states.
- Preserve legibility under text scaling, browser zoom, UI scale, high-density
  displays, visually busy game backgrounds, and reduced viewport space.
- Provide meaningful labels and accessible names for controls and icons. Keep
  reading and focus order aligned with the visual hierarchy.
- Avoid motion that is required to understand state. Respect reduced-motion
  preferences where the platform exposes them.

## State and feedback

- Place validation and unavailable reasons next to the affected control and
  explain recovery when possible.
- Distinguish disabled, loading, locked, unavailable, selected, and completed
  states.
- Announce asynchronous success, failure, and material state changes through the
  platform's accessible semantics.
- Preserve user input after recoverable errors.
- Confirm destructive, costly, or difficult-to-reverse actions in proportion to
  risk; do not add confirmation to harmless, easily reversible actions.

## Content

- Use concise labels that describe actions rather than implementation.
- Keep terminology stable across navigation, headings, controls, feedback, and
  documentation.
- Test localization expansion, multiline labels, empty values, large numbers,
  and user-generated content.
- Do not use placeholder text as the only label or instruction.
