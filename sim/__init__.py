"""
P2P Swarm Model Simulator

A software-only simulation of peer-to-peer swarm communication
for disconnected IoT devices.
"""

from .node import Node, Message, Position, Urgency, NodeStats
from .network import SimulatedNetwork, NetworkConfig, NetworkCondition
from .swarm import Swarm, SwarmConfig, SwarmMetrics

__version__ = "1.0.0"
__all__ = [
    "Node",
    "Message",
    "Position",
    "Urgency",
    "NodeStats",
    "SimulatedNetwork",
    "NetworkConfig",
    "NetworkCondition",
    "Swarm",
    "SwarmConfig",
    "SwarmMetrics",
]
