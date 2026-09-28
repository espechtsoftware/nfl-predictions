"""Mean vs variance at satellite ticket lines (Gaussian; field p50 127, sd 27; a row with mean mu)."""
import numpy as np
from scipy.stats import norm
for name, z in [("p89", 1.22), ("p95", 1.645), ("p99", 2.33), ("p99.8", 2.88)]:
    for mu, sd in [(135, 25), (140, 25), (135, 30)]:
        L = 127 + z * 27
        p = 1 - norm.cdf((L - mu) / sd); p1 = 1 - norm.cdf((L - mu - 1) / sd); ps = 1 - norm.cdf((L - mu) / (sd * 1.1))
        print(f"{name} line {L:5.1f} | mu {mu} sd {sd}: P {100*p:5.2f}%  +1pt -> x{p1/p:.3f}  sd+10% -> x{ps/p:.2f}")
for s in (7.5, 8.5):
    print(f"player sd {s}: independent {np.sqrt(9*s*s):.1f}; QB+2 stack {np.sqrt(9*s*s+2*s*s*(0.38+0.36)):.1f}; "
          f"+bring-back {np.sqrt(9*s*s+2*s*s*(0.38+0.36+0.09+0.09)):.1f}")
