"""Unit tests for network.py"""

import pytest
import asyncio
import sys
from pathlib import Path

# Add sim directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from network import SimulatedNetwork, NetworkConfig, NetworkCondition


class TestNetworkConfig:
    """Tests for NetworkConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = NetworkConfig()
        assert config.packet_loss == 0.0
        assert config.min_delay_ms == 0.0
        assert config.max_delay_ms == 100.0
        assert config.communication_range == 100.0
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = NetworkConfig(
            packet_loss=0.3,
            min_delay_ms=50.0,
            max_delay_ms=500.0
        )
        assert config.packet_loss == 0.3
        assert config.min_delay_ms == 50.0
        assert config.max_delay_ms == 500.0
    
    def test_preset_conditions(self):
        """Test preset network conditions."""
        ideal = NetworkConfig.from_condition(NetworkCondition.IDEAL)
        assert ideal.packet_loss == 0.0
        
        poor = NetworkConfig.from_condition(NetworkCondition.POOR)
        assert poor.packet_loss == 0.30


class TestSimulatedNetwork:
    """Tests for SimulatedNetwork."""
    
    @pytest.fixture
    def network(self):
        """Create a test network."""
        config = NetworkConfig(packet_loss=0.0)
        return SimulatedNetwork(config)
    
    @pytest.fixture
    def lossy_network(self):
        """Create a network with 100% packet loss."""
        config = NetworkConfig(packet_loss=1.0)
        return SimulatedNetwork(config)
    
    def test_register_node(self, network):
        """Test node registration."""
        from node import Node, Position
        node = Node("test-node", position=Position(0, 0))
        network.register_node(node)
        assert "test-node" in network._nodes
    
    def test_unregister_node(self, network):
        """Test node unregistration."""
        from node import Node, Position
        node = Node("test-node", position=Position(0, 0))
        network.register_node(node)
        network.unregister_node("test-node")
        assert "test-node" not in network._nodes
    
    def test_partition_nodes(self, network):
        """Test network partitioning."""
        from node import Node, Position
        for i in range(4):
            node = Node(f"node{i}", position=Position(i * 10, 0))
            network.register_node(node)
        
        network.set_partitions_by_groups([{"node0", "node1"}, {"node2", "node3"}])
        assert len(network._partitions) == 2
    
    def test_clear_partitions(self, network):
        """Test clearing network partitions."""
        network.set_partitions_by_groups([{"node0"}, {"node1"}])
        network.clear_partitions()
        assert len(network._partitions) == 0


class TestNetworkMetrics:
    """Tests for network metrics calculation."""
    
    @pytest.fixture
    def network(self):
        config = NetworkConfig()
        return SimulatedNetwork(config)
    
    def test_initial_stats(self, network):
        """Test initial transmission statistics."""
        assert network._total_transmissions == 0
        assert network._successful_transmissions == 0
        assert network._dropped_packets == 0
