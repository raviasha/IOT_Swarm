"""
node.py - Virtual IoT Device Node

Represents a single virtual IoT device in the swarm.
Each node has a local message queue, neighbor list, and gossip behavior.
"""

import asyncio
import uuid
import json
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any, Set, Callable
from dataclasses import dataclass, field
from collections import deque
from enum import IntEnum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Urgency(IntEnum):
    """Message urgency levels (0-5)"""
    LOWEST = 0
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5


@dataclass
class Message:
    """
    Standard message envelope for all swarm communication.
    """
    id: str
    from_node: str
    to_node: Optional[str]  # None = broadcast
    ttl: int
    seq: int
    urgency: int
    payload: Dict[str, Any]
    timestamp: str
    
    @classmethod
    def create(
        cls,
        from_node: str,
        payload: Dict[str, Any],
        to_node: Optional[str] = None,
        ttl: int = 10,
        seq: int = 0,
        urgency: int = Urgency.NORMAL
    ) -> 'Message':
        """Factory method to create a new message."""
        return cls(
            id=str(uuid.uuid4()),
            from_node=from_node,
            to_node=to_node,
            ttl=ttl,
            seq=seq,
            urgency=urgency,
            payload=payload,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format."""
        return {
            "id": self.id,
            "from": self.from_node,
            "to": self.to_node,
            "ttl": self.ttl,
            "seq": self.seq,
            "urgency": self.urgency,
            "payload": self.payload,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary."""
        return cls(
            id=data["id"],
            from_node=data["from"],
            to_node=data.get("to"),
            ttl=data["ttl"],
            seq=data["seq"],
            urgency=data["urgency"],
            payload=data["payload"],
            timestamp=data["timestamp"]
        )
    
    def decrement_ttl(self) -> 'Message':
        """Return a copy with decremented TTL."""
        return Message(
            id=self.id,
            from_node=self.from_node,
            to_node=self.to_node,
            ttl=self.ttl - 1,
            seq=self.seq,
            urgency=self.urgency,
            payload=self.payload,
            timestamp=self.timestamp
        )


@dataclass
class Position:
    """2D position for mobility simulation."""
    x: float = 0.0
    y: float = 0.0
    
    def distance_to(self, other: 'Position') -> float:
        """Calculate Euclidean distance to another position."""
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5


@dataclass
class NodeStats:
    """Statistics for a node's operation."""
    messages_sent: int = 0
    messages_received: int = 0
    messages_forwarded: int = 0
    messages_dropped: int = 0
    messages_delivered: int = 0


class Node:
    """
    Virtual IoT Device Node.
    
    Simulates a single IoT device with:
    - Local message queue (inbox/outbox)
    - Neighbor list (nodes within communication range)
    - Gossip-based message propagation
    - Position for mobility simulation
    """
    
    def __init__(
        self,
        node_id: str,
        position: Optional[Position] = None,
        communication_range: float = 100.0,
        queue_size: int = 1000
    ):
        self.node_id = node_id
        self.position = position or Position()
        self.communication_range = communication_range
        
        # Message queues
        self._inbox: deque = deque(maxlen=queue_size)
        self._outbox: deque = deque(maxlen=queue_size)
        
        # Track seen messages to avoid duplicates
        self._seen_messages: Set[str] = set()
        self._max_seen = 10000  # Limit memory usage
        
        # Sequence counter for outgoing messages
        self._sequence = 0
        
        # Neighbor tracking
        self._neighbors: Set[str] = set()
        
        # Statistics
        self.stats = NodeStats()
        
        # Callbacks
        self._on_message_received: Optional[Callable] = None
        self._on_message_delivered: Optional[Callable] = None
        
        # Running state
        self._running = False
        self._network = None  # Will be set by swarm
        
        logger.debug(f"Node {node_id} created at position ({position})")
    
    @property
    def neighbors(self) -> Set[str]:
        """Get current neighbor set."""
        return self._neighbors.copy()
    
    def set_neighbors(self, neighbors: Set[str]):
        """Update neighbor list."""
        self._neighbors = neighbors - {self.node_id}  # Exclude self
    
    def add_neighbor(self, neighbor_id: str):
        """Add a neighbor."""
        if neighbor_id != self.node_id:
            self._neighbors.add(neighbor_id)
    
    def remove_neighbor(self, neighbor_id: str):
        """Remove a neighbor."""
        self._neighbors.discard(neighbor_id)
    
    def is_neighbor(self, other_node: 'Node') -> bool:
        """Check if another node is within communication range."""
        return self.position.distance_to(other_node.position) <= self.communication_range
    
    def create_message(
        self,
        payload: Dict[str, Any],
        to_node: Optional[str] = None,
        ttl: int = 10,
        urgency: int = Urgency.NORMAL
    ) -> Message:
        """Create a new message from this node."""
        self._sequence += 1
        return Message.create(
            from_node=self.node_id,
            payload=payload,
            to_node=to_node,
            ttl=ttl,
            seq=self._sequence,
            urgency=urgency
        )
    
    async def send(self, message: Message) -> bool:
        """
        Send a message to the network.
        The message will be queued for transmission via gossip.
        """
        if message.id in self._seen_messages:
            return False
        
        self._mark_seen(message.id)
        self._outbox.append(message)
        self.stats.messages_sent += 1
        
        logger.debug(f"Node {self.node_id} queued message {message.id[:8]}...")
        return True
    
    async def receive(self, message: Message) -> bool:
        """
        Receive a message from the network.
        Returns True if message was accepted, False if duplicate/dropped.
        """
        # Check if already seen
        if message.id in self._seen_messages:
            return False
        
        self._mark_seen(message.id)
        self._inbox.append(message)
        self.stats.messages_received += 1
        
        # Check if message is for this node
        if message.to_node == self.node_id or message.to_node is None:
            self.stats.messages_delivered += 1
            if self._on_message_delivered:
                await self._on_message_delivered(message)
        
        if self._on_message_received:
            await self._on_message_received(message)
        
        logger.debug(f"Node {self.node_id} received message {message.id[:8]}...")
        return True
    
    def _mark_seen(self, message_id: str):
        """Mark a message as seen, with cleanup for memory management."""
        self._seen_messages.add(message_id)
        # Cleanup old messages if too many
        if len(self._seen_messages) > self._max_seen:
            # Remove oldest half
            to_remove = list(self._seen_messages)[:self._max_seen // 2]
            for msg_id in to_remove:
                self._seen_messages.discard(msg_id)
    
    async def gossip_round(self) -> List[Message]:
        """
        Perform one round of gossip protocol.
        Returns messages to be forwarded to neighbors.
        """
        messages_to_forward = []
        
        # Process inbox - forward messages that aren't expired
        while self._inbox:
            message = self._inbox.popleft()
            
            # Check TTL
            if message.ttl <= 0:
                self.stats.messages_dropped += 1
                continue
            
            # Forward to neighbors (decrement TTL)
            forwarded = message.decrement_ttl()
            messages_to_forward.append(forwarded)
            self.stats.messages_forwarded += 1
        
        # Also forward outbox messages
        while self._outbox:
            message = self._outbox.popleft()
            if message.ttl > 0:
                messages_to_forward.append(message)
        
        return messages_to_forward
    
    def get_pending_messages(self) -> List[Message]:
        """Get all pending messages (inbox + outbox)."""
        return list(self._inbox) + list(self._outbox)
    
    def on_message_received(self, callback: Callable):
        """Set callback for when any message is received."""
        self._on_message_received = callback
    
    def on_message_delivered(self, callback: Callable):
        """Set callback for when a message addressed to this node arrives."""
        self._on_message_delivered = callback
    
    def move_to(self, new_position: Position):
        """Move node to a new position."""
        self.position = new_position
    
    def get_stats(self) -> Dict[str, Any]:
        """Get node statistics."""
        return {
            "node_id": self.node_id,
            "position": {"x": self.position.x, "y": self.position.y},
            "neighbors": len(self._neighbors),
            "inbox_size": len(self._inbox),
            "outbox_size": len(self._outbox),
            "stats": {
                "sent": self.stats.messages_sent,
                "received": self.stats.messages_received,
                "forwarded": self.stats.messages_forwarded,
                "dropped": self.stats.messages_dropped,
                "delivered": self.stats.messages_delivered
            }
        }
    
    def __repr__(self) -> str:
        return f"Node({self.node_id}, pos=({self.position.x:.1f}, {self.position.y:.1f}))"


# Convenience function for testing
async def create_test_node(node_id: str = "test_node") -> Node:
    """Create a node for testing purposes."""
    return Node(node_id=node_id, position=Position(0, 0))


if __name__ == "__main__":
    # Simple test
    async def test():
        node1 = Node("node_001", Position(0, 0))
        node2 = Node("node_002", Position(50, 50))
        
        # Create and send a message
        msg = node1.create_message({"temperature": 23.5}, to_node="node_002")
        await node1.send(msg)
        
        # Simulate receiving
        await node2.receive(msg)
        
        print(f"Node 1 stats: {node1.get_stats()}")
        print(f"Node 2 stats: {node2.get_stats()}")
    
    asyncio.run(test())
