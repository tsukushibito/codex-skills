# Information Architecture

Use this guide to decide what the screen should contain and how users should
move through it.

## Start from the job

Write a one-sentence contract:

> In this context, this user must decide or accomplish X, using Y evidence, and
> know that it succeeded through Z.

If the sentence contains several unrelated decisions, split the workflow or
establish a clear primary task and subordinate tasks.

## Rank information

Classify every content item:

1. **Decision-critical**: needed to choose or act correctly now.
2. **Status and consequence**: confirms current state, cost, risk, or result.
3. **Supporting**: useful for confidence but not required continuously.
4. **Exhaustive**: audit, explanation, history, or low-frequency detail.

Keep the first two near the primary action. Reveal supporting information in
context. Put exhaustive information behind a deliberate detail path unless the
screen's purpose is analysis.

Do not fill a composition with unchanged values, empty metrics, duplicated
summaries, decorative labels, or descriptions already evident from the control.

## Choose the surface

- Use one screen when the task is singular and the decision evidence is bounded.
- Use a split view when selection and detail must remain visible together.
- Use a modal for a focused, temporary decision that preserves useful background
  context and has an unambiguous exit.
- Use a popover or drawer for supplemental context that does not become a second
  workflow.
- Use drill-down for dense or exhaustive detail that is not needed during the
  parent decision.
- Use tabs only for peer modes users repeatedly switch between. Do not use tabs
  to hide unrelated tasks or rescue an overloaded page.
- Use a staged flow only when later choices depend on earlier ones or when the
  consequence warrants explicit review.

Keep primary actions stable and close to their consequences. Put secondary exits
where platform convention and navigation hierarchy make them predictable.

## Design comparison

Make the compared states explicit: current, candidate, and resulting state are
not interchangeable. Lead with changed, decision-relevant values; preserve units
and direction semantics. Show benefit, loss, tradeoff, and incompatibility with
text or symbols as well as color. Suppress unchanged padding while keeping a
clear empty state when nothing changes.

Use authoritative product projections rather than rebuilding calculations in
the view.

## Inventory states

Define at minimum the applicable states:

- initial and populated;
- loading and refreshing;
- empty and first-use;
- error and recoverable error;
- unavailable, permission-limited, or locked;
- disabled with a reason;
- destructive confirmation and completion;
- long text, large values, localization expansion, and maximum item counts.

Use representative fixtures early. Placeholder-perfect layouts often fail when
real content appears.

## Plan responsive behavior

Preserve priority before geometry. Reflow regions, collapse supporting material,
and move exhaustive detail behind an explicit path before reducing legibility or
target size. Define what remains visible at the smallest supported viewport and
what changes position, representation, or disclosure level.
