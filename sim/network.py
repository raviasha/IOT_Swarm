"""
network.py - Simulated Wireless Network Layer

Simulates the wireless world with:
- Packet loss
- Delays
- Partitions
- Mobility (random waypoint model)
"""

import asyncio
import random
import logging
from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import math

try:
    from .node import Node, Message, Position
except ImportError:
    from node import Node, Message, Position

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NetworkCondition(Enum):
    """Network condition presets."""
    IDEAL = "ideal"
    GOOD = "good"
    MODERATE = "moderate"
    POOR = "poor"
    SEVERE = "severe"


@dataclass
class NetworkConfig:
    """Configuration for network simulation."""
    # Packet loss probability (0.0 - 1.0)
    packet_loss: float = 0.0
    
    # Delay range in milliseconds
    min_delay_ms: float = 0.0
    max_delay_ms: float = 100.0
    
    # Communication range for nodes
    communication_range: float = 100.0
    
    # World size for mobility
    world_width: float = 1000.0
    world_height: float = 1000.0
    
    # Mobility settings
    mobility_enabled: bool = False
    mobility_speed_min: float = 1.0  # units per second
    mobility_speed_max: float = 10.0
    mobility_pause_min: float = 0.0  # seconds
    mobility_pause_max: float = 5.0
    
    @classmethod
    def from_condition(cls, condition: NetworkCondition) -> 'NetworkConfig':
        """Create config from preset condition."""
        presets = {
            NetworkCondition.IDEAL: cls(packet_loss=0.0, min_delay_ms=0, max_delay_ms=10),
            NetworkCondition.GOOD: cls(packet_loss=0.05, min_delay_ms=10, max_delay_ms=50),
            NetworkCondition.MODERATE: cls(packet_loss=0.15, min_delay_ms=50, max_delay_ms=200),
            NetworkCondition.POOR: cls(packet_loss=0.30, min_delay_ms=100, max_delay_ms=500),
            NetworkCondition.SEVERE: cls(packet_loss=0.50, min_delay_ms=200, max_delay_ms=1000),
        }
        return presets.get(condition, cls())


@dataclass
class TransmissionResult:
    """Result of a message transmission attempt."""
    success: bool
    delay_ms: float
    dropped: bool
    reason: Optional[str] = None


@dataclass
class MobilityState:
    """State for random waypoint mobility model."""
    target: Position
    speed: float
    pause_remaining: float = 0.0
    moving: bool = False


class Partition:
    """Represents a network partition (isolated group of nodes)."""
    
    def __init__(self, partition_id: int, node_ids: Set[str]):
        self.partition_id = partition_id
        self.node_ids = node_ids
    
    def contains(self, node_id: str) -> bool:
        return node_id in self.node_ids
    
    def can_communicate(self, node_a: str, node_b: str) -> bool:
        """Check if two nodes are in the same partition."""
        return (node_a in self.node_ids) == (node_b in self.node_ids)


class SimulatedNetwork:
    """
    Simulated Wireless Network.
    
    Handles:
    - Message transmission between nodes
    - Packet loss simulation
    - Delay simulation
    - Network partitions
    - Node mobility
    """
    
    def __init__(self, config: Optional[NetworkConfig] = None):
        self.config = config or NetworkConfig()
        self._nodes: Dict[str, Node] = {}
        self._partitions: List[Partition] = []
        self._mobility_states: Dict[str, MobilityState] = {}
        
        # Statistics
        self._total_transmissions = 0
        self._successful_transmissions = 0
        self._dropped_packets = 0
        self._total_delay_ms = 0.0
        
        # Delivery tracking
        self._message_origins: Dict[str, Tuple[str, float]] = {}  # msg_id -> (origin_node, send_time)
        self._delivery_times: Dict[str, float] = {}  # msg_id -> delivery_time
        
        logger.info(f"Network created with config: loss={self.config.packet_loss}, "
                   f"delay={self.config.min_delay_ms}-{self.config.max_delay_ms}ms")
    
    def register_node(self, node: Node):
        """Register a node with the network."""
        self._nodes[node.node_id] = node
        node._network = self
        
        if self.config.mobility_enabled:
            self._init_mobility(node.node_id)
        
        logger.debug(f"Node {node.node_id} registered with network")
    
    def unregister_node(self, node_id: str):
        """Remove a node from the network."""
        if node_id in self._nodes:
            del self._nodes[node_id]
            if node_id in self._mobility_states:
                del self._mobility_states[node_id]
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID."""
        return self._nodes.get(node_id)
    
    def get_all_nodes(self) -> List[Node]:
        """Get all registered nodes."""
        return list(self._nodes.values())
    
    def _init_mobility(self, node_id: str):
        """Initialize mobility state for a node."""
        node = self._nodes[node_id]
        target = self._random_position()
        speed = random.uniform(self.config.mobility_speed_min, self.config.mobility_speed_max)
        self._mobility_states[node_id] = MobilityState(target=target, speed=speed, moving=True)
    
    def _random_position(self) -> Position:
        """Generate a random position within world bounds."""
        return Position(
            x=random.uniform(0, self.config.world_width),
            y=random.uniform(0, self.config.world_height)
        )
    
    def update_neighbors(self):
        """Update neighbor lists for all nodes based on positions."""
        nodes = list(self._nodes.values())
        
        for node in nodes:
            neighbors = set()
            for other in nodes:
                if other.node_id == node.node_id:
                    continue
                
                # Check distance
                if node.position.distance_to(other.position) <= self.config.communication_range:
                    # Check partitions
                    if self._can_communicate(node.node_id, other.node_id):
                        neighbors.add(other.node_id)
            
            node.set_neighbors(neighbors)
    
    def _can_communicate(self, node_a: str, node_b: str) -> bool:
        """Check if two nodes can communicate (partition check)."""
        if not self._partitions:
            return True
        
        for partition in self._partitions:
            if partition.contains(node_a) and partition.contains(node_b):
                return True
            if partition.contains(node_a) != partition.contains(node_b):
                return False
        
        return True
    
    def create_partition(self, node_ids: Set[str]) -> Partition:
        """Create a network partition with the specified nodes."""
        partition_id = len(self._partitions)
        partition = Partition(partition_id, node_ids)
        self._partitions.append(partition)
        
        logger.info(f"Created partition {partition_id} with {len(node_ids)} nodes")
        self.update_neighbors()
        return partition
    
    def remove_partition(self, partition: Partition):
        """Remove a partition (heal the network)."""
        if partition in self._partitions:
            self._partitions.remove(partition)
            logger.info(f"Removed partition {partition.partition_id}")
            self.update_neighbors()
    
    def clear_partitions(self):
        """Remove all partitions."""
        self._partitions.clear()
        logger.info("All partitions cleared")
        self.update_neighbors()
    
    def set_partitions_by_groups(self, groups: List[Set[str]]):
        """Set network partitions by specifying isolated groups."""
        self._partitions.clear()
        for i, group in enumerate(groups):
            self._partitions.append(Partition(i, group))
        
        logger.info(f"Set {len(groups)} partition groups")
        self.update_neighbors()
    
    async def transmit(self, message: Message, from_node: str, to_node: str) -> TransmissionResult:
        """
        Simulate transmission of a message between two nodes.
        Applies packet loss and delay.
        """
        self._total_transmissions += 1
        
        # Check if nodes exist
        sender = self._nodes.get(from_node)
        receiver = self._nodes.get(to_node)
        
        if not sender or not receiver:
            return TransmissionResult(success=False, delay_ms=0, dropped=True, 
                                    reason="Node not found")
        
        # Check partition
        if not self._can_communicate(from_node, to_node):
            self._dropped_packets += 1
            return TransmissionResult(success=False, delay_ms=0, dropped=True,
                                    reason="Partition barrier")
        
        # Check distance
        distance = sender.position.distance_to(receiver.position)
        if distance > self.config.communication_range:
            self._dropped_packets += 1
            return TransmissionResult(success=False, delay_ms=0, dropped=True,
                                    reason="Out of range")
        
        # Simulate packet loss
        if random.random() < self.config.packet_loss:
            self._dropped_packets += 1
            return TransmissionResult(success=False, delay_ms=0, dropped=True,
                                    reason="Packet loss")
        
        # Simulate delay
        delay_ms = random.uniform(self.config.min_delay_ms, self.config.max_delay_ms)
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)
        
        self._total_delay_ms += delay_ms
        self._successful_transmissions += 1
        
        # Deliver message
        await receiver.receive(message)
        
        return TransmissionResult(success=True, delay_ms=delay_ms, dropped=False)
    
    async def broadcast_from(self, message: Message, from_node: str) -> Dict[str, TransmissionResult]:
        """Broadcast a message from one node to all its neighbors."""
        sender = self._nodes.get(from_node)
        if not sender:
            return {}
        
        results = {}
        for neighbor_id in sender.neighbors:
            result = await self.transmit(message, from_node, neighbor_id)
            results[neighbor_id] = result
        
        return results
    
    def update_mobility(self, delta_time: float):
        """
        Update node positions based on random waypoint mobility model.
        
        Args:
            delta_time: Time elapsed in seconds
        """
        if not self.config.mobility_enabled:
            return
        
        for node_id, state in self._mobility_states.items():
            node = self._nodes.get(node_id)
            if not node:
                continue
            
            if state.pause_remaining > 0:
                # Node is paused
                state.pause_remaining -= delta_time
                continue
            
            if not state.moving:
                # Pick new target
                state.target = self._random_position()
                state.speed = random.uniform(
                    self.config.mobility_speed_min, 
                    self.config.mobility_speed_max
                )
                state.moving = True
            
            # Move towards target
            dx = state.target.x - node.position.x
            dy = state.target.y - node.position.y
            distance = math.sqrt(dx*dx + dy*dy)
            
            if distance < state.speed * delta_time:
                # Arrived at target
                node.move_to(state.target)
                state.moving = False
                state.pause_remaining = random.uniform(
                    self.config.mobility_pause_min,
                    self.config.mobility_pause_max
                )
            else:
                # Move towards target
                ratio = (state.speed * delta_time) / distance
                new_x = node.position.x + dx * ratio
                new_y = node.position.y + dy * ratio
                node.move_to(Position(new_x, new_y))
        
        # Update neighbor lists after movement
        self.update_neighbors()
    
    def track_message_origin(self, message: Message, send_time: float):
        """Track when a message was originally sent."""
        self._message_origins[message.id] = (message.from_node, send_time)
    
    def record_delivery(self, message_id: str, delivery_time: float):
        """Record when a message was delivered."""
        self._delivery_times[message_id] = delivery_time
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get network statistics."""
        delivery_delays = []
        for msg_id, delivery_time in self._delivery_times.items():
            if msg_id in self._message_origins:
                _, send_time = self._message_origins[msg_id]
                delivery_delays.append(delivery_time - send_time)
        
        avg_delivery_delay = sum(delivery_delays) / len(delivery_delays) if delivery_delays else 0
        
        return {
            "total_transmissions": self._total_transmissions,
            "successful_transmissions": self._successful_transmissions,
            "dropped_packets": self._dropped_packets,
            "transmission_success_rate": (self._successful_transmissions / self._total_transmissions 
                                         if self._total_transmissions > 0 else 0),
            "average_delay_ms": (self._total_delay_ms / self._successful_transmissions 
                                if self._successful_transmissions > 0 else 0),
            "messages_tracked": len(self._message_origins),
            "messages_delivered": len(self._delivery_times),
            "delivery_ratio": (len(self._delivery_times) / len(self._message_origins)
                             if self._message_origins else 0),
            "average_delivery_delay": avg_delivery_delay,
            "partitions": len(self._partitions),
            "nodes": len(self._nodes)
        }
    
    def reset_statistics(self):
        """Reset all statistics."""
        self._total_transmissions = 0
        self._successful_transmissions = 0
        self._dropped_packets = 0
        self._total_delay_ms = 0.0
        self._message_origins.clear()
        self._delivery_times.clear()


# Utility functions for creating networks
def create_ideal_network() -> SimulatedNetwork:
    """Create a network with ideal conditions."""
    return SimulatedNetwork(NetworkConfig.from_condition(NetworkCondition.IDEAL))


def create_lossy_network(loss_rate: float = 0.3) -> SimulatedNetwork:
    """Create a network with specified packet loss."""
    config = NetworkConfig(packet_loss=loss_rate)
    return SimulatedNetwork(config)


def create_mobile_network(
    speed_range: Tuple[float, float] = (1.0, 10.0),
    world_size: Tuple[float, float] = (1000.0, 1000.0)
) -> SimulatedNetwork:
    """Create a network with mobile nodes."""
    config = NetworkConfig(
        mobility_enabled=True,
        mobility_speed_min=speed_range[0],
        mobility_speed_max=speed_range[1],
        world_width=world_size[0],
        world_height=world_size[1]
    )
    return SimulatedNetwork(config)


if __name__ == "__main__":
    # Simple test
    async def test():
        network = create_lossy_network(0.2)
        
        node1 = Node("node_001", Position(0, 0))
        node2 = Node("node_002", Position(50, 50))
        
        network.register_node(node1)
        network.register_node(node2)
        network.update_neighbors()
        
        print(f"Node 1 neighbors: {node1.neighbors}")
        print(f"Node 2 neighbors: {node2.neighbors}")
        
        # Send a message
        msg = node1.create_message({"test": "data"}, to_node="node_002")
        result = await network.transmit(msg, "node_001", "node_002")
        print(f"Transmission result: {result}")
        
        print(f"Network stats: {network.get_statistics()}")
    
    asyncio.run(test())
