# AMTP configuration used for every AMTP result in the paper. Source it before running AMTP code:
#
#   source scripts/paper_env.sh
#
# Without these variables the code runs the plain construction (no AND pruning, proofs for every covered
# partition, no auxiliary Search Tree data). Responses verify the same way in both modes.
export AMTP_PLACEMENT=fill        # fill-first placement (Phase 2, Step 1)
export AMTP_GAMMA_V=1             # gamma includes the partition version v (Eq. 18)
export AMTP_AND_PRUNE=1           # ASPA: focus evidence for conjunctions (Phase 4, Step 2)
export AMTP_AND_GREEDY=1          # greedy expansion of H_full while it lowers the proof size
export AMTP_PART_RESULTS=1        # partition proofs only for partitions of returned files (Eq. 62-63)
export AMTP_PART_LEAF=1           # Aux_i(h_w) in the Search Tree leaf (Eq. 17)
echo "AMTP paper configuration: fill placement, gamma with v, AND pruning (greedy), result-only partition proofs, part leaf"
