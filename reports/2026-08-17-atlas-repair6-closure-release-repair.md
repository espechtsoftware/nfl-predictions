# ATLAS repair6 closure and parity-release repair

Date frozen: 2026-08-17, while 43 of the 54 repair5 primaries were still
nonterminal and before repair5 attempt resolution/census, repair6
classification, either repair6 canary, any repair6 grid execution, a hybrid
population, or historical-v4 scoring existed.

The already-frozen queue amendment requires the continuous-interaction parity
diagnostic to return to the one-heavy queue immediately when repair6 closes
without a scoreable population. The replacement watcher implemented this for
failure-classification closure, but its terminal canary-execution and
grid-execution failure branches exited without releasing parity. Its
historical-v4 watcher could consequently wait forever for a hybrid population
that was no longer possible.

This repair changes queue control only:

1. A terminal failed repair6 dual-canary execution or repair6 grid execution
   records a create-once `queue-closure.txt` with a frozen categorical reason
   and no candidate, effect, score, outcome or production consequence.
2. Failure-classification closure records the same receipt before releasing
   parity.
3. An explicitly present hybrid-completion receipt whose disposition is not
   `valid-complete-repair6-hybrid-population` records hybrid-invalid closure.
   A missing completion caused by a local finisher/transport error still stops
   for repair and does not infer scientific closure.
4. Every recorded closure runs the existing continuous-parity launcher,
   status wait and strict finisher exactly once through a shared function.
5. The historical-v4 watcher exits score-free when it sees a valid repair6
   closure receipt instead of waiting for an impossible hybrid.

Launcher/preflight failures, local validator failures, nonterminal executions
and missing receipts remain repairable transport states and do not create a
scientific closure. This repair changes no repair5/repair6 model, optimizer,
tolerance, candidate identity, seed, resource, failure classifier, historical
gate, parity law or production policy. It cancels and reruns nothing.

