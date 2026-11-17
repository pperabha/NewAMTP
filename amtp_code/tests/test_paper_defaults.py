"""With no AMTP_* variable set, the code runs the paper's configuration: fill placement, γ with the partition
version, AND pruning with greedy expansion, result-only partition proofs, and the Search Tree auxiliary data."""
import os

import pytest

from amtp.index import and_plan_greedy_on, and_prune_on, gamma_has_v, part_leaf_on, part_results_on

FLAGS = ("AMTP_AND_PRUNE", "AMTP_AND_GREEDY", "AMTP_PART_RESULTS", "AMTP_PART_LEAF", "AMTP_GAMMA_V")


@pytest.mark.skipif(any(f in os.environ for f in FLAGS), reason="an AMTP_* flag is set in the environment")
def test_defaults_are_the_paper_configuration():
    assert and_prune_on() and and_plan_greedy_on() and part_results_on() and part_leaf_on() and gamma_has_v()
