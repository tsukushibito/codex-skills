---
name: design-build-validate-ui
description: Design, critique, implement, refine, and visually validate user interfaces across games, web, desktop, and mobile. Use when Codex needs to create a new UI, evaluate or redesign an existing interface, compare reference products, produce a wireframe or mockup, implement UI changes, inspect actual rendered screens, or validate responsive behavior, input, states, and accessibility.
---

# Design, Build, and Validate UI

Create UI from the user's decision and operating context, not from a preferred
layout. Treat reference images as design evidence and actual rendered output as
the completion evidence.

## Operating contract

- Match the user's authorization. Keep evaluation, diagnosis, and planning
  read-only; edit files only when the user asks to build or change the UI.
- Read applicable repository instructions, product requirements, design systems,
  and phase or platform constraints before proposing implementation.
- Prefer framework-native layout, controls, semantics, and input facilities over
  project-specific infrastructure.
- Preserve authoritative state, business rules, navigation, persistence, and
  confirmation behavior. Do not recompute domain policy in presentation code.
- Do not claim that a UI fits, reads well, or works visually until inspecting an
  actual render at the relevant viewport. If rendering is unavailable, report
  that validation gap explicitly.
- Distinguish generated mockups, reference-product screenshots, and actual
  product captures in both reasoning and handoff.

## Route the request

Classify the requested outcome before acting:

1. **Evaluate**: inspect and report evidence-backed findings without changing the
   product.
2. **Design**: define information architecture, interaction, and a wireframe or
   mockup. Do not silently expand this into implementation.
3. **Build or refine**: implement the requested change and validate the rendered
   result and interactions.

Then classify the surface:

- **Existing UI**: inspect the current rendered screen first when the product can
  run. Also inspect its source, data/state contracts, navigation, supported
  inputs, design system, and relevant tests. If it cannot run, inspect supplied
  captures and source, diagnose why, and label the missing live-render evidence.
- **New UI in an existing product**: inspect adjacent screens, shared components,
  design tokens, navigation ownership, and real data shapes before designing.
- **Greenfield UI**: establish the user, primary task or decision, content and
  state inventory, target devices, viewports, and input methods. Do not require a
  nonexistent current render; begin the render-inspect loop after the first
  working implementation or prototype exists.

Ask only for material product choices that cannot be discovered. Continue with
explicit, low-risk assumptions when the missing detail does not change the
product direction.

## Load only relevant guidance

- Read [information-architecture.md](references/information-architecture.md) for
  every new screen or material redesign.
- Read [platform-patterns.md](references/platform-patterns.md) for the target
  game, web, desktop, or mobile surface. Use every applicable section for
  cross-platform work.
- Read
  [interaction-accessibility.md](references/interaction-accessibility.md) for
  interactive screens, input behavior, or accessibility evaluation.
- Read [visual-validation.md](references/visual-validation.md) before capturing,
  reviewing, or declaring a rendered UI complete.

## Workflow

### 1. Frame the user decision

State the user, context, primary decision or task, primary action, and success
signal in plain language. Inventory real content, loading, empty, error, blocked,
disabled, destructive, confirmation, and unusually long or dense states. Separate
content that must be continuously visible from contextual help and exhaustive
detail.

### 2. Inspect and research

Use local product evidence before external inspiration. When competitive
comparison, current conventions, recommendations, or precise standards matter,
research current primary sources and comparable products. Compare screens that
support the same user decision and input context; do not copy surface styling or
trade dress. Cite external evidence and distinguish direct observations from
inference.

### 3. Choose the screen architecture

Select one screen, split view, modal, popover, tabs, drill-down, or a staged flow
from the information hierarchy and frequency of switching. Avoid adding tabs,
scroll regions, dashboards, or dialogs merely to fit content. Define responsive
reflow and progressive disclosure before shrinking text or controls.

### 4. Prototype at the right fidelity

Use a compact wireframe when relationships are the main uncertainty. Use image
generation when the user requests a bitmap mockup or visual direction materially
helps; use code-native HTML, CSS, SVG, canvas, or engine UI when an interactive or
implementation-faithful prototype is more useful. Populate the prototype with
representative content and edge states. Treat it as a hypothesis, not proof that
the production UI works.

### 5. Implement in the product's language

Reuse established components and tokens. Keep scene or view roots focused on
wiring and lifecycle, and retain existing ownership of state and policy. Implement
responsive layout, input routing, focus, back/cancel, confirmation, loading, and
failure behavior as part of the screen rather than as follow-up polish. Preserve
unrelated user changes.

### 6. Render, inspect, and correct

Run the product and capture the actual UI at the smallest supported viewport and
at least one representative larger viewport. Exercise the relevant state and
input matrix. Inspect the images directly, correct concrete hierarchy, clipping,
overflow, density, contrast, alignment, focus, and interaction problems, then
recapture affected states.

### 7. Validate behavior

Run project-supported static, component, interaction, accessibility, responsive,
and smoke checks in proportion to risk. Cover authoritative data use, navigation,
input modalities, destructive operations, state restoration, and content
extremes. Record skipped checks and the exact reason.

### 8. Report the outcome

Lead with what is now better for the user. Show the actual implemented capture
when available, identify any mockup separately, summarize the important behavior
and design decisions, list validation results, and disclose remaining manual or
environment gaps.

## Completion gates

Do not call the work complete until:

- the hierarchy supports the stated primary decision or task;
- required information is visible at the right time without irrelevant noise;
- supported input and navigation paths are coherent;
- meaning does not depend on color alone;
- required states and realistic content extremes remain usable;
- actual product renders have been inspected at the target viewport matrix when
  implementation or visual product evaluation is in scope; otherwise the
  remaining implementation validation is identified as outside the requested
  scope;
- affected automated checks pass, or unresolved gaps are reported precisely.
