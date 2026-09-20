# Amendment: SIS shrunk concentration feature

The outcome-free support census showed that weekly SIS defender cells are sparse but highly concentrated. Before any outcome read, add one fixed feature family to the existing held-out gate:

- `sis_target_hhi`: sum of squared defender target shares over the prior eight completed games for the opponent/alignment;
- `sis_top_target_share`: largest defender target share over the same prior window.

The source table's existing vulnerability field remains the shrunk SIS efficiency input. The new concentration fields are computed only from source weeks strictly earlier than the target week, using the same eight-game window and no outcome columns. No threshold, feature removal, or model tuning follows the result. Evaluate the concentration arm against the frozen control and the already frozen SIS coverage × alignment arm on the same 2024/2025 held-out folds.
