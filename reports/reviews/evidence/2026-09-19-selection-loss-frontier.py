"""Research-only one-exchange selection frontier; selection worlds only.

The caller authenticates the full corpus, equal component mass, eligibility,
legal unique rosters, and the final delivered control. No audit input enters
this proposal function. Replacements preserve the displaced delivery position.
"""
import numpy as np

LOSS_BUDGETS = (0.0, 0.25, 0.5, 1.0, 2.0)
SHORTLIST = 128
THRESHOLD = 220.0


def proposals(totals, book, admissible):
    totals = np.asarray(totals)
    book = list(map(int, book))
    admissible = np.asarray(admissible)
    assert totals.ndim == 2 and totals.shape[1] > 0 and np.isfinite(totals).all()
    assert book and len(book) == len(set(book))
    assert min(book) >= 0 and max(book) < len(totals)
    assert admissible.dtype == bool and admissible.shape == (len(totals),)
    assert admissible[book].all(), 'control must satisfy the same admission contract'
    selected = totals[book]
    best = selected.max(axis=0)
    mean0 = float(best.mean(dtype=np.float64))
    p0 = float(np.mean(best >= THRESHOLD))
    available = admissible.copy()
    available[book] = False
    choices = np.flatnonzero(available)
    # Prespecified bounded search: target currently uncovered selection worlds.
    uncovered = best < THRESHOLD
    reach = np.count_nonzero(totals[choices][:, uncovered] >= THRESHOLD, axis=1)
    means = totals[choices].mean(axis=1, dtype=np.float64)
    incoming = choices[np.lexsort((choices, -means, -reach))[:SHORTLIST]]
    second = (np.partition(selected, len(book) - 2, axis=0)[-2]
              if len(book) > 1 else np.full_like(best, -np.inf))
    argbest = selected.argmax(axis=0)
    rows = []
    for position, outgoing in enumerate(book):
        remaining = np.where(argbest == position, second, best)
        for start in range(0, len(incoming), 16):
            ids = incoming[start:start + 16]
            alternative = np.maximum(totals[ids], remaining)
            dm = alternative.mean(axis=1, dtype=np.float64) - mean0
            dp = (alternative >= THRESHOLD).mean(axis=1) - p0
            rows.extend(dict(incoming=int(i), outgoing=outgoing, position=position,
                             delta_emax=float(m), delta_p220=float(p))
                        for i, m, p in zip(ids, dm, dp))
    books, decisions = {'control': book}, []
    for cap in LOSS_BUDGETS:
        eligible = [r for r in rows if r['delta_emax'] >= -cap and r['delta_p220'] > 0]
        if not eligible:
            decisions.append(dict(loss_budget=cap, book='control', reason='no positive P220 proposal within budget'))
            continue
        chosen = min(eligible, key=lambda r: (-r['delta_p220'], -r['delta_emax'], r['incoming'], r['position']))
        alternative = book.copy()
        alternative[chosen['position']] = chosen['incoming']
        assert len(alternative) == len(set(alternative)) == len(book)
        name = f"replace_{chosen['position'] + 1}_with_{chosen['incoming']}"
        books[name] = alternative
        decisions.append(dict(loss_budget=cap, book=name, **chosen))
    return dict(control_selection=dict(emax=mean0, p220=p0), books=books, decisions=decisions,
                shortlist=list(map(int, incoming)), evaluated_exchanges=rows,
                search_scope='128 incoming candidates, all outgoing positions, one exchange only',
                audit_used_for_proposals=False)
