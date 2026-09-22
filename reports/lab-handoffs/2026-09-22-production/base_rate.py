"""Base-rate correction to the supply-vs-retrieval read.

"We generated 30 lineups >=170 and entered none" is only damning if a book of K
rows drawn at random WOULD have entered some. With 30 qualifying rows in 12,555,
it would not. This computes, per threshold, the hypergeometric expectation for a
random K-row book and the selector's realised conversion against it.
"""
from scipy.stats import hypergeom
WEEKS = {
 1: dict(N=3200,  K=90, rows={150:1215, 170:506, 194:104, 200:62, 220:6}, entered={150:39,170:22,194:8,200:7,220:0}),
 2: dict(N=12555, K=97, rows={150:222,  170:30,  194:1,   200:0,  220:0}, entered={150:3, 170:0, 194:0, 200:0, 220:0}),
}
for wk, d in WEEKS.items():
    N, K = d["N"], d["K"]
    print(f"\n=== WEEK {wk}  pool {N}, book {K} ===")
    print(f"{'thresh':>7}{'in pool':>9}{'pool rate':>11}{'E[random book]':>16}"
          f"{'P(random=0)':>13}{'entered':>9}{'lift vs random':>16}")
    for t, m in d["rows"].items():
        if m == 0:
            print(f"{t:>7}{m:>9}{'0.00%':>11}{'--':>16}{'100.0%':>13}"
                  f"{d['entered'][t]:>9}{'n/a':>16}"); continue
        exp = K * m / N
        p0 = hypergeom.sf(-1, N, m, K) - hypergeom.sf(0, N, m, K)  # P(X=0)
        p0 = hypergeom.pmf(0, N, m, K)
        ent = d["entered"][t]
        lift = f"{ent/exp:.2f}x" if exp > 0 else "n/a"
        print(f"{t:>7}{m:>9}{m/N*100:>10.2f}%{exp:>16.2f}{p0*100:>12.1f}%"
              f"{ent:>9}{lift:>16}")
print("""
Reading: 'E[random book]' is how many qualifying rows a RANDOM K-row draw from the
same pool would contain. 'P(random=0)' is how often a random book enters none.""")
