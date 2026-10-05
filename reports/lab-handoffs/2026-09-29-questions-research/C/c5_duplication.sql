WITH own AS (
  SELECT contest_id, display_name, SUM(pct_drafted) own FROM nfl_raw.contest_ownership
  WHERE season=2026 AND contest_id IN ('193028206','195648007','195905122') GROUP BY 1,2),
e AS (
  SELECT week, contest_id, duplicate_key, COUNT(*) copies, MIN(rank) best_rank, ANY_VALUE(points) points,
         -- @our_handle: the operator's DK username, a query parameter from the private config; never committed
         LOGICAL_OR(entry_name LIKE CONCAT(@our_handle, '%')) ours, ANY_VALUE(n) n
  FROM (SELECT *, COUNT(*) OVER (PARTITION BY contest_id) n FROM nfl_raw.contest_entries WHERE contest_id IN ('193028206','195648007','195905122'))
  GROUP BY 1,2,3),
x AS (
  SELECT e.week, e.duplicate_key, e.copies, e.best_rank, e.points, e.ours, e.n,
         SUM(o.own) own_sum, COUNTIF(o.own<5) n_under5, COUNTIF(o.own>=20) n_20plus, COUNTIF(o.own IS NULL) n_unmatched
  FROM e, UNNEST(SPLIT(e.duplicate_key,'|')) p LEFT JOIN own o ON o.contest_id=e.contest_id AND o.display_name=p
  GROUP BY 1,2,3,4,5,6,7),
ent AS (SELECT x.*, NTILE(10) OVER (PARTITION BY week ORDER BY own_sum) dec FROM x, UNNEST(GENERATE_ARRAY(1, copies)) c)
SELECT 'A_overall' q, week, CAST(NULL AS STRING) grp, COUNT(*) entries, COUNT(DISTINCT duplicate_key) distinct_lineups,
       ROUND(COUNTIF(copies=1)/COUNT(*),4) share_unique_entries, ROUND(AVG(copies),3) mean_copies, MAX(copies) max_copies,
       ROUND(AVG(points),2) mean_points, ROUND(AVG(own_sum),1) mean_own_sum, SUM(n_unmatched) unmatched, ROUND(AVG(n_under5),2) mean_under5
FROM ent GROUP BY 1,2,3
UNION ALL
SELECT 'B_by_own_decile', week, CAST(dec AS STRING), COUNT(*), COUNT(DISTINCT duplicate_key), ROUND(COUNTIF(copies=1)/COUNT(*),4), ROUND(AVG(copies),3), MAX(copies), ROUND(AVG(points),2), ROUND(AVG(own_sum),1), MIN(CAST(own_sum AS INT64)), ROUND(AVG(n_under5),2)
FROM ent GROUP BY 1,2,3
UNION ALL
SELECT 'C_by_n_under5', week, CAST(LEAST(n_under5,6) AS STRING), COUNT(*), COUNT(DISTINCT duplicate_key), ROUND(COUNTIF(copies=1)/COUNT(*),4), ROUND(AVG(copies),3), MAX(copies), ROUND(AVG(points),2), ROUND(AVG(own_sum),1), NULL, ROUND(AVG(n_20plus),2)
FROM ent GROUP BY 1,2,3
UNION ALL
SELECT 'D_by_line', week, line, COUNT(*), COUNT(DISTINCT duplicate_key), ROUND(COUNTIF(copies=1)/COUNT(*),4), ROUND(AVG(copies),3), MAX(copies), ROUND(AVG(1/copies),3), ROUND(AVG(own_sum),1), NULL, ROUND(AVG(n_under5),2)
FROM (SELECT ent.*, CASE WHEN best_rank<=10 THEN '1_top10' WHEN best_rank<=100 THEN '2_top100' WHEN best_rank<=1000 THEN '3_top1000' WHEN best_rank<=CAST(0.01*n AS INT64) THEN '4_top1pct' WHEN best_rank<=CAST(0.2*n AS INT64) THEN '5_cash20pct' ELSE '6_below' END line FROM ent) GROUP BY 1,2,3
UNION ALL
SELECT 'E_ours', week, 'ours', COUNT(*), COUNT(DISTINCT duplicate_key), ROUND(COUNTIF(copies=1)/COUNT(*),4), ROUND(AVG(copies),3), MAX(copies), ROUND(AVG(points),2), ROUND(AVG(own_sum),1), MIN(best_rank), ROUND(AVG(n_under5),2)
FROM ent WHERE ours GROUP BY 1,2,3
UNION ALL
SELECT 'F_chalkcore', week, CASE WHEN n_under5<=2 AND n_20plus>=1 THEN 'chalk_core' ELSE 'other' END, COUNT(*), COUNT(DISTINCT duplicate_key), ROUND(COUNTIF(copies=1)/COUNT(*),4), ROUND(AVG(copies),3), MAX(copies), ROUND(AVG(points),2), ROUND(AVG(own_sum),1), COUNTIF(best_rank<=CAST(0.2*n AS INT64)), ROUND(AVG(n_under5),2)
FROM ent GROUP BY 1,2,3
ORDER BY 1,2,3
