"""
swarm.py - Swarm Coordinator

Coordinates many nodes and runs gossip synchronization rounds.
"""

import asyncio
import random
import logging
import time
from typing import Dict, List, Set, Optional, Any, Callable
from dataclasses import dataclass, field

try:
    from .node import Node, Message, Position, Urgency
    from .network import SimulatedNetwork, NetworkConfig
except ImportError:
    from node import Node, Message, Position, Urgency
    from network import SimulatedNetwork, NetworkConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SwarmConfig:
    """Configuration for the swarm."""
    num_nodes: int = 50
    world_width: float = 1000.0
    world_height: float = 1000.0
    communication_range: float = 150.0
    gossip_interval: float = 0.1  # seconds between gossip rounds
    message_ttl: int = 10


@dataclass
class SwarmMetrics:
    """Metrics for swarm performance."""
    total_messages_sent: int = 0
    total_messages_delivered: int = 0
    total_gossip_rounds: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    
    @property
    def delivery_ratio(self) -> float:
        if self.total_messages_sent == 0:
            return 0.0
        return self.total_messages_delivered / self.total_messages_sent
    
    @property
    def runtime(self) -> float:
        return self.end_time - self.start_time if self.end_time > 0 else 0.0


class Swarm:
    """
    Swarm Coordinator.
    
    Manages a collection of virtual IoT nodes and coordinates
    gossip-based message propagation through the simulated network.
    """
    
    def __init__(
        self, 
        network: SimulatedNetwork,
        config: Optional[SwarmConfig] = None
    ):
        self.network = network
        self.config = config or SwarmConfig()
        self._nodes: Dict[str, Node] = {}
        self._running = False
        self._gossip_task: Optional[asyncio.Task] = None
        self._mobility_task: Optional[asyncio.Task] = None
        
        # Metrics
        self.metrics = SwarmMetrics()
        
        # Message tracking
        self._pending_messages: Dict[str, Message] = {}  # msg_id -> message
        self._delivered_to: Dict[str, Set[str]] = {}  # msg_id -> set of node_ids
        
        # Callbacks
        self._on_message_delivered: Optional[Callable] = None
        
        logger.info(f"Swarm created with config: {config}")
    
    def create_nodes(self, num_nodes: Optional[int] = None) -> List[Node]:
        """Create and register nodes in a random grid pattern."""
        n = num_nodes or self.config.num_nodes
        nodes = []
        
        for i in range(n):
            node_id = f"node_{i:03d}"
            position = Position(
                x=random.uniform(0, self.config.world_width),
                y=random.uniform(0, self.config.world_height)
            )
            node = Node(
                node_id=node_id,
                position=position,
                communication_range=self.config.communication_range
            )
            
            # Set up delivery tracking
            node.on_message_delivered(self._handle_delivery)
            
            self._nodes[node_id] = node
            self.network.register_node(node)
            nodes.append(node)
        
        # Update neighbor lists
        self.network.update_neighbors()
        
        logger.info(f"Created {n} nodes")
        return nodes
    
    def create_nodes_in_grid(self, rows: int, cols: int, spacing: float = 100.0) -> List[Node]:
        """Create nodes in a regular grid pattern."""
        nodes = []
        node_idx = 0
        
        for r in range(rows):
            for c in range(cols):
                node_id = f"node_{node_idx:03d}"
                position = Position(x=c * spacing, y=r * spacing)
                node = Node(
                    node_id=node_id,
                    position=position,
                    communication_range=self.config.communication_range
                )
                node.on_message_delivered(self._handle_delivery)
                
                self._nodes[node_id] = node
                self.network.register_node(node)
                nodes.append(node)
                node_idx += 1
        
        self.network.update_neighbors()
        logger.info(f"Created {len(nodes)} nodes in {rows}x{cols} grid")
        return nodes
    
    def create_nodes_in_clusters(
        self, 
        num_clusters: int, 
        nodes_per_cluster: int,
        cluster_radius: float = 50.0
    ) -> List[Node]:
        """Create nodes in clustered groups."""
        nodes = []
        node_idx = 0
        
        for cluster in range(num_clusters):
            # Random cluster center
            center_x = random.uniform(cluster_radius, self.config.world_width - cluster_radius)
            center_y = random.uniform(cluster_radius, self.config.world_height - cluster_radius)
            
            for _ in range(nodes_per_cluster):
                node_id = f"node_{node_idx:03d}"
                # Random position within cluster
                angle = random.uniform(0, 2 * 3.14159)
                radius = random.uniform(0, cluster_radius)
                position = Position(
                    x=center_x + radius * __import__('math').cos(angle),
                    y=center_y + radius * __import__('math').sin(angle)
                )
                node = Node(
                    node_id=node_id,
                    position=position,
                    communication_range=self.config.communication_range
                )
                node.on_message_delivered(self._handle_delivery)
                
                self._nodes[node_id] = node
                self.network.register_node(node)
                nodes.append(node)
                node_idx += 1
        
        self.network.update_neighbors()
        logger.info(f"Created {len(nodes)} nodes in {num_clusters} clusters")
        return nodes
    
    async def _handle_delivery(self, message: Message):
        """Handle message delivery event."""
        msg_id = message.id
        
        if msg_id not in self._delivered_to:
            self._delivered_to[msg_id] = set()
        
        # Track which nodes received the message
        if message.to_node:
            self._delivered_to[msg_id].add(message.to_node)
            self.metrics.total_messages_delivered += 1
            self.network.record_delivery(msg_id, time.time())
        
        if self._on_message_delivered:
            await self._on_message_delivered(message)
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID."""
        return self._nodes.get(node_id)
    
    def get_all_nodes(self) -> List[Node]:
        """Get all nodes in the swarm."""
        return list(self._nodes.values())
    
    def get_random_node(self) -> Optional[Node]:
        """Get a random node from the swarm."""
        if not self._nodes:
            return None
        return random.choice(list(self._nodes.values()))
    
    async def send_message(
        self,
        from_node: str,
        payload: Dict[str, Any],
        to_node: Optional[str] = None,
        ttl: Optional[int] = None,
        urgency: int = Urgency.NORMAL
    ) -> Optional[Message]:
        """
        Send a message from a specific node.
        
        Args:
            from_node: Source node ID
            payload: Message payload
            to_node: Optional target node ID (None for broadcast)
            ttl: Time-to-live (hops)
            urgency: Message urgency level
            
        Returns:
            The created message, or None if node not found
        """
        node = self._nodes.get(from_node)
        if not node:
            logger.warning(f"Node {from_node} not found")
            return None
        
        message = node.create_message(
            payload=payload,
            to_node=to_node,
            ttl=ttl or self.config.message_ttl,
            urgency=urgency
        )
        
        await node.send(message)
        self._pending_messages[message.id] = message
        self.metrics.total_messages_sent += 1
        self.network.track_message_origin(message, time.time())
        
        logger.debug(f"Message {message.id[:8]} sent from {from_node}")
        return message
    
    async def broadcast_from_random(
        self,
        payload: Dict[str, Any],
        urgency: int = Urgency.NORMAL
    ) -> Optional[Message]:
        """Broadcast a message from a random node."""
        node = self.get_random_node()
        if not node:
            return None
        return await self.send_message(node.node_id, payload, urgency=urgency)
    
    async def gossip_round(self):
        """
        Execute one round of gossip protocol across all nodes.
        
        Each node:
        1. Processes its inbox
        2. Forwards messages to neighbors
        """
        self.metrics.total_gossip_rounds += 1
        
        # Collect messages to forward from all nodes
        forward_tasks = []
        
        for node in self._nodes.values():
            messages = await node.gossip_round()
            
            for message in messages:
                # Forward to all neighbors
                for neighbor_id in node.neighbors:
                    forward_tasks.append(
                        self.network.transmit(message, node.node_id, neighbor_id)
                    )
        
        # Execute all transmissions
        if forward_tasks:
            await asyncio.gather(*forward_tasks, return_exceptions=True)
    
    async def run_gossip_loop(self, interval: Optional[float] = None):
        """Run continuous gossip rounds."""
        interval = interval or self.config.gossip_interval
        
        while self._running:
            await self.gossip_round()
            await asyncio.sleep(interval)
    
    async def run_mobility_loop(self, interval: float = 0.1):
        """Run continuous mobility updates."""
        while self._running:
            self.network.update_mobility(interval)
            await asyncio.sleep(interval)
    
    async def start(self):
        """Start the swarm (gossip and mobility loops)."""
        if self._running:
            return
        
        self._running = True
        self.metrics.start_time = time.time()
        
        # Start gossip loop
        self._gossip_task = asyncio.create_task(self.run_gossip_loop())
        
        # Start mobility loop if enabled
        if self.network.config.mobility_enabled:
            self._mobility_task = asyncio.create_task(self.run_mobility_loop())
        
        logger.info("Swarm started")
    
    async def stop(self):
        """Stop the swarm."""
        self._running = False
        self.metrics.end_time = time.time()
        
        if self._gossip_task:
            self._gossip_task.cancel()
            try:
                await self._gossip_task
            except asyncio.CancelledError:
                pass
        
        if self._mobility_task:
            self._mobility_task.cancel()
            try:
                await self._mobility_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Swarm stopped")
    
    async def run_for(self, duration: float):
        """Run the swarm for a specific duration."""
        await self.start()
        await asyncio.sleep(duration)
        await self.stop()
    
    def on_message_delivered(self, callback: Callable):
        """Set callback for message delivery events."""
        self._on_message_delivered = callback
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get swarm metrics."""
        return {
            "total_messages_sent": self.metrics.total_messages_sent,
            "total_messages_delivered": self.metrics.total_messages_delivered,
            "delivery_ratio": self.metrics.delivery_ratio,
            "total_gossip_rounds": self.metrics.total_gossip_rounds,
            "runtime_seconds": self.metrics.runtime,
            "num_nodes": len(self._nodes),
            "network_stats": self.network.get_statistics()
        }
    
    def get_node_statistics(self) -> List[Dict[str, Any]]:
        """Get statistics for all nodes."""
        return [node.get_stats() for node in self._nodes.values()]
    
    def get_connectivity_matrix(self) -> Dict[str, List[str]]:
        """Get the current connectivity between nodes."""
        return {
            node_id: list(node.neighbors) 
            for node_id, node in self._nodes.items()
        }
    
    def calculate_network_diameter(self) -> int:
        """Calculate the network diameter (longest shortest path)."""
        # Simple BFS-based diameter calculation
        max_distance = 0
        
        for start_node in self._nodes:
            distances = {start_node: 0}
            queue = [start_node]
            
            while queue:
                current = queue.pop(0)
                current_node = self._nodes[current]
                
                for neighbor in current_node.neighbors:
                    if neighbor not in distances:
                        distances[neighbor] = distances[current] + 1
                        queue.append(neighbor)
                        max_distance = max(max_distance, distances[neighbor])
        
        return max_distance


# Utility functions
async def create_simple_swarm(
    num_nodes: int = 50,
    packet_loss: float = 0.0,
    world_size: float = 1000.0
) -> Swarm:
    """Create a simple swarm with random node placement."""
    from network import NetworkConfig
    
    config = SwarmConfig(
        num_nodes=num_nodes,
        world_width=world_size,
        world_height=world_size
    )
    
    network_config = NetworkConfig(
        packet_loss=packet_loss,
        world_width=world_size,
        world_height=world_size
    )
    
    network = SimulatedNetwork(network_config)
    swarm = Swarm(network, config)
    swarm.create_nodes()
    
    return swarm


if __name__ == "__main__":
    async def test():
        # Create a simple swarm
        swarm = await create_simple_swarm(num_nodes=20, packet_loss=0.1)
        
        # Send some messages
        for i in range(5):
            await swarm.broadcast_from_random({"test": i})
        
        # Run for a few seconds
        await swarm.run_for(2.0)
        
        # Print metrics
        print(f"Swarm metrics: {swarm.get_metrics()}")
    
    asyncio.run(test())
