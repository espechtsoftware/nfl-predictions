"""Contest economics for the week: rake, base ticket rate, break-even rate, the edge needed, and the realized line.

    cd $W3DIR && python w3_economics.py       # after w3_field_lines.py (contest_meta.csv, contest_lines.csv)
"""
import pandas as pd
m = pd.read_csv("contest_meta.csv"); L = pd.read_csv("contest_lines.csv")
m["type"] = m.name.str[:44] + " | " + m.entries_dk.astype(str)
g = m.groupby("type").agg(fee=("fee", "first"), entries=("entries_dk", "first"), paid=("paid", "first"), ticket=("ticket_value", "first"), n=("contest_id", "size")).reset_index()
L["type"] = L.contest.str[:44] + " | " + L.entries.astype(str)
g = g.merge(L.groupby("type").agg(line=("line", "mean"), p50=("p50", "mean"), line_pct=("line_pct", "mean")).reset_index(), on="type", how="left")
g["collected"] = g.fee * g.entries; g["paid_out"] = g.paid * g.ticket
g["rake %"] = 100 * (1 - g.paid_out / g.collected)            # meaningful for ticket contests only (the GPPs list the first prize)
g["base P(ticket) %"] = 100 * g.paid / g.entries
g["break-even P %"] = 100 * g.fee / g.ticket
g["edge needed (x field)"] = g["break-even P %"] / g["base P(ticket) %"]
pd.set_option("display.width", 260)
cols = ["type", "fee", "entries", "paid", "ticket", "n", "rake %", "base P(ticket) %", "break-even P %", "edge needed (x field)", "line", "p50", "line_pct"]
print(g[cols].sort_values("fee", ascending=False).round(2).to_string(index=False))
