---
name: pseudocode
description: Use when the user mentions pseudocode to align with their definition of pseudocode.
---

# Pseudocode Definition

Declarative, behavioral description of code *intent*. Terse natural language expressions focused on inputs, outputs, state machines and flow control.
The rationale is to leave room for problem solving, adaptation and judgment calls when the time comes to implement that pseudocode, while keeping the original intent. 

**Trivial example:**

<implementation>
def add(a, b):
  return a + b
</implementation>
<pseudocode>
Function that returns the sum of two numbers
</pseudocode>

**More Complex Examples:**

<implementation>
ZERO = Decimal(0)

def _apply_sell(state, event, realized_pnl):
    held = state.held_qty(event.asset_id)
    if event.qty > held:
        raise ResolverError(
            f"insufficient {event.asset_id}: need {event.qty}, have {held}")

    proceeds = event.qty * event.price_per_unit - event.fee - event.tax
    state.cash += proceeds

    remaining = event.qty
    cost_basis = ZERO
    new_lots = []
    for lot in state.lots.get(event.asset_id, []):
        if remaining <= ZERO:
            new_lots.append(lot)
            continue
        if lot.remaining_qty <= remaining:
            cost_basis += lot.remaining_qty * lot.cost_per_unit
            remaining -= lot.remaining_qty
        else:
            cost_basis += remaining * lot.cost_per_unit
            new_lots.append(Lot(
                lot.buy_event_id, lot.asset_id, lot.acquired_date,
                lot.remaining_qty - remaining, lot.cost_per_unit))
            remaining = ZERO

    state.lots[event.asset_id] = new_lots
    state.position_qty[event.asset_id] = held - event.qty
    realized_pnl.append(
        RealizedPnlEntry(event.date, proceeds - cost_basis, event.asset_id))
</implementation>
<pseudocode>
Apply a sell event to portfolio state using FIFO lot matching: guard against
overselling, update cash by the net proceeds, then walk the lot inventory
oldest-first — consuming full lots where possible, partially splitting the last
lot touched — and finally record the realized gain or loss.
</pseudocode>

<implementation>
function getSelectedArticles(selectedIds, payloads) {
  if (!payloads) return []

  const selectedArticles = []
  for (const payload of payloads) {
    for (const article of payload.articles) {
      if (selectedIds.has(`article-${article.url}`)) {
        selectedArticles.push(article)
      }
    }
  }
  return selectedArticles
}

function groupSelectedByDate(selectedArticles) {
  const grouped = new Map()
  for (const article of selectedArticles) {
    if (!grouped.has(article.issueDate)) {
      grouped.set(article.issueDate, [])
    }
    grouped.get(article.issueDate).push(article)
  }
  return grouped
}
</implementation>
<pseudocode>
Walk a nested feed structure to collect every article whose ID appears in a
selection set, then bucket the collected articles by issue date into a map,
lazily creating each date bucket on first encounter.
</pseudocode>
