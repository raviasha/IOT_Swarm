"""Unit tests for node.py"""

import pytest
import asyncio
import sys
from pathlib import Path

# Add sim directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from node import Node, Message, Position, Urgency


class TestMessage:
    """Tests for Message dataclass."""
    
    def test_message_creation_with_factory(self):
        """Test creating a message using the factory method."""
        msg = Message.create(
            from_node="node1",
            payload={"data": "test"}
        )
        assert msg.from_node == "node1"
        assert msg.payload == {"data": "test"}
        assert msg.ttl == 10
        assert msg.urgency == Urgency.NORMAL
        assert msg.id is not None
        assert msg.timestamp is not None
    
    def test_message_to_dict(self):
        """Test message serialization."""
        msg = Message.create(
            from_node="node1",
            to_node="node2",
            payload={"key": "value"}
        )
        d = msg.to_dict()
        assert d["from"] == "node1"
        assert d["to"] == "node2"
        assert d["payload"] == {"key": "value"}
        assert "id" in d
        assert "timestamp" in d
    
    def test_message_from_dict(self):
        """Test message deserialization."""
        data = {
            "id": "test-id",
            "from": "node1",
            "to": "node2",
            "ttl": 5,
            "seq": 1,
            "urgency": 3,
            "payload": {"data": "test"},
            "timestamp": "2026-01-01T00:00:00"
        }
        msg = Message.from_dict(data)
        assert msg.id == "test-id"
        assert msg.from_node == "node1"
        assert msg.to_node == "node2"
        assert msg.ttl == 5
        assert msg.urgency == 3
    
    def test_message_decrement_ttl(self):
        """Test TTL decrement."""
        msg = Message.create(from_node="node1", payload={}, ttl=5)
        new_msg = msg.decrement_ttl()
        assert new_msg.ttl == 4
        assert msg.ttl == 5  # Original unchanged


class TestNode:
    """Tests for Node class."""
    
    @pytest.fixture
    def node(self):
        """Create a test node."""
        return Node("test-node", position=Position(0.0, 0.0))
    
    def test_node_creation(self, node):
        """Test node initialization."""
        assert node.node_id == "test-node"
        assert node.position.x == 0.0
        assert node.position.y == 0.0
        assert len(node.neighbors) == 0
    
    def test_add_neighbor(self, node):
        """Test adding a neighbor."""
        node.add_neighbor("neighbor1")
        assert "neighbor1" in node.neighbors
    
    def test_remove_neighbor(self, node):
        """Test removing a neighbor."""
        node.add_neighbor("neighbor1")
        node.remove_neighbor("neighbor1")
        assert "neighbor1" not in node.neighbors
    
    def test_create_message(self, node):
        """Test message creation."""
        msg = node.create_message({"data": "test"}, to_node="target")
        assert msg.from_node == "test-node"
        assert msg.to_node == "target"
        assert msg.payload == {"data": "test"}
    
    @pytest.mark.asyncio
    async def test_receive_message(self, node):
        """Test receiving a message."""
        msg = Message.create(from_node="other", payload={"data": "test"})
        result = await node.receive(msg)
        assert result == True
        assert msg.id in node._seen_messages
    
    @pytest.mark.asyncio
    async def test_duplicate_message_rejected(self, node):
        """Test that duplicate messages are not processed twice."""
        msg = Message.create(from_node="other", payload={"data": "test"})
        await node.receive(msg)
        initial_received = node.stats.messages_received
        result = await node.receive(msg)  # Same message again
        assert result == False
        assert node.stats.messages_received == initial_received
    
    @pytest.mark.asyncio
    async def test_send_queues_message(self, node):
        """Test sending a message adds to outbox."""
        msg = node.create_message({"data": "broadcast"})
        result = await node.send(msg)
        assert result == True
        assert node.stats.messages_sent == 1


class TestPosition:
    """Tests for Position class."""
    
    def test_position_creation(self):
        """Test position initialization."""
        pos = Position(10.0, 20.0)
        assert pos.x == 10.0
        assert pos.y == 20.0
    
    def test_distance_calculation(self):
        """Test distance calculation between positions."""
        pos1 = Position(0.0, 0.0)
        pos2 = Position(3.0, 4.0)
        assert pos1.distance_to(pos2) == 5.0
    
    def test_distance_to_self(self):
        """Test distance to same position is zero."""
        pos = Position(5.0, 5.0)
        assert pos.distance_to(pos) == 0.0

