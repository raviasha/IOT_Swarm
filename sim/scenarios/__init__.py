"""
Scenarios package for P2P Swarm simulations.

Provides ready-to-run experiments for testing different network conditions.
"""

from .partition_test import run_partition_test
from .mobility_test import run_mobility_test

__all__ = ['run_partition_test', 'run_mobility_test']
