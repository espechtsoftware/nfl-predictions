# Sourced by scripts/sunday_build_host.sh (and its tests): the --main mix fallback (reviewer 2026-10-05).
#
# A MIX main that cannot reach K rows exits "MIX MAIN REFUSED" before writing anything. The chain then re-runs the union
# with the HOUSE main -- --main pmo_x50, the ownership term's flags KEPT, the --mix-* flags dropped -- under a capitals
# banner: "MIX REFUSED -> HOUSE MAIN (C)". That is the closest tested arm (study 18's C is that form without the term).
# A partial cell failure never comes here: it stays inside MIX (a pass to A1, counted in the receipt). If the house main
# then refuses too, the host's existing PMO_X50 fallback builds the union's mean main, as before.
#
# Needs from the caller: UNION_ARGS (array), UNION_RC, OUT, RUN_TAG, and a run_union function.

# mix_to_house_args ARGS... -> OUT_ARGS: --main mix becomes --main pmo_x50; --mix-plan / --mix-layout / --mix-portfolio / --mix-spares and their values dropped
# 2026-10-07 (the laptop, wiring the priority order): every MIX-only flag goes too -- --mix-fill / --mix-cell-quotas /
# --mix-cover-games / --mix-rs-rows, the live term block's --term-block-* (the cheap +2 trial), --winner-select (each with its
# value) and the bare --priority-order. Each needs --main mix, so the house main REFUSED with any of them aboard and the
# chain ended in UNION FAILED instead of C: the fallback now builds C without them (the house main never carried them).
# 2026-10-09 (his package; the laptop): the ownership cap's flags are MIX-only too, and the flat 35% never runs alone (his
# rule, Addendum 186), so a house fallback of a package run ALSO goes back to the package's fallback player cap (0.5:
# today's book), set in place of the package's --main-cap-share 0.35 (one value, for study 38's parity).
mix_to_house_args() {
  OUT_ARGS=(); local skip=0 x i own_cap=0 fb=0.5 take_fb=0
  for x in "$@"; do
    if (( take_fb )); then take_fb=0; fb="$x"; continue; fi
    if (( skip )); then skip=0; continue; fi
    case "$x" in
      --mix-plan|--mix-layout|--mix-portfolio|--mix-spares|--mix-fill|--mix-cell-quotas|--mix-cover-games|--mix-rs-rows) skip=1 ;;
      --term-block-rows|--term-block-source|--term-block-tilt|--term-block-cap-points|--term-block-min-coverage|--winner-select) skip=1 ;;
      --main-own-cap-delta|--main-own-cap-source|--main-own-cap-min-coverage) skip=1; own_cap=1 ;;
      --mix-max-te|--mix-max-low-own|--mix-low-own-pct) skip=1 ;;     # his test-2 row rules (10-09): MIX-only
      --mix-min-star|--mix-star-salary|--proj-shrink-k|--proj-shrink-window) skip=1 ;;   # his 10-09 S1 / S2: tested on the mix only
      --main-own-cap-fallback-share) take_fb=1; own_cap=1 ;;
      --priority-order) ;;
      *) OUT_ARGS+=("$x") ;;
    esac
  done
  if (( own_cap )); then                                    # the player cap back to the package's fallback, in place
    local placed=0
    for i in "${!OUT_ARGS[@]}"; do [[ "${OUT_ARGS[$i]}" == "--main-cap-share" ]] && { OUT_ARGS[$((i+1))]="$fb"; placed=1; }; done
    (( placed )) || OUT_ARGS+=(--main-cap-share "$fb")
  fi
  for i in "${!OUT_ARGS[@]}"; do
    if [[ "${OUT_ARGS[$i]}" == "--main" && "${OUT_ARGS[$((i+1))]:-}" == "mix" ]]; then OUT_ARGS[$((i+1))]=pmo_x50; fi
  done
}

# mix_fallback: when the last union call refused its MIX main, re-run it as the house main (sets UNION_RC, UNION_ARGS,
# UNION_MAIN_EFFECTIVE; keeps the refusal log as $OUT/union-$RUN_TAG-mix-refused.txt). A no-op otherwise.
mix_fallback() {
  UNION_MAIN_EFFECTIVE=${UNION_MAIN_EFFECTIVE:-${UNION_MAIN:-mean}}
  (( UNION_RC != 0 )) || return 0
  [[ "$UNION_MAIN_EFFECTIVE" == "mix" ]] || return 0
  grep -q 'MIX MAIN REFUSED' "$OUT/union-$RUN_TAG.txt" || return 0
  local why; why=$(grep 'MIX MAIN REFUSED' "$OUT/union-$RUN_TAG.txt" | tail -1)
  printf '\n%s\n%s\n%s\n\n' "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" \
    "!!! MIX REFUSED -> HOUSE MAIN (C) for $RUN_TAG: $why" \
    "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
  cp "$OUT/union-$RUN_TAG.txt" "$OUT/union-$RUN_TAG-mix-refused.txt"
  mix_to_house_args "${UNION_ARGS[@]}"; UNION_ARGS=("${OUT_ARGS[@]}"); UNION_MAIN_EFFECTIVE=pmo_x50
  UNION_RC=0; run_union "${UNION_ARGS[@]}" || UNION_RC=$?
}
