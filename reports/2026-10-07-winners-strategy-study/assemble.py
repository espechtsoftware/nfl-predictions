"""Assemble the study document: skeleton (sections 0) + narrative body (sections 1-4, with [CROSS-TABLE] filled from the
summarizer) + Appendix A (the summarizer's per-week tables). Usage: assemble.py RUN_DIR SKELETON BODY OUT"""
import subprocess, sys
from pathlib import Path
run, skel, body, out = sys.argv[1:5]
summ = subprocess.run([sys.executable, str(Path(__file__).parent / "summarize.py"), run], capture_output=True, text=True).stdout
weeks_part, _, cross_part = summ.partition("### Cross-week")
cross_table = "\n".join(l for l in cross_part.splitlines() if l.startswith("|"))
head = Path(skel).read_text().split("## 1. Week by week")[0].rstrip() + "\n\n"
text = Path(body).read_text().replace("[CROSS-TABLE]", cross_table)
appendix = "\n\n## Appendix A. The attribute tables, ladders and best lineups, as the run recorded them\n" + weeks_part.replace("### Week", "#### Week") + "\n\n### Cross-week (all runs)\n\n" + cross_table + "\n"
Path(out).write_text(head + text.rstrip() + appendix)
print(f"wrote {out}: {len((head + text + appendix).splitlines())} lines; placeholders left: {[p for p in ('[W4-LADDER]', '[W4-READING]', '[W4-STRATEGY]', '[W4-OWN]', '[W4-CROSS]') if p in text]}")
