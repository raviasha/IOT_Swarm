#!/usr/bin/env python3
"""
simulator.py - Main Experiment Runner

Allows running experiments with configurable parameters:
- Number of nodes
- Packet loss rate
- Runtime duration
- Partitions
- Mobility

Outputs results to CSV.
"""

import asyncio
import argparse
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, asdict

# Add parent directory to path for standalone execution
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))

try:
    from .node import Node, Message, Position, Urgency
    from .network import SimulatedNetwork, NetworkConfig, NetworkCondition
    from .swarm import Swarm, SwarmConfig
except ImportError:
    from node import Node, Message, Position, Urgency
    from network import SimulatedNetwork, NetworkConfig, NetworkCondition
    from swarm import Swarm, SwarmConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ExperimentConfig:
    """Configuration for an experiment."""
    name: str = "default_experiment"
    num_nodes: int = 50
    packet_loss: float = 0.0
    runtime_seconds: float = 60.0
    world_size: float = 1000.0
    communication_range: float = 150.0
    gossip_interval: float = 0.1
    message_ttl: int = 10
    
    # Message generation
    messages_per_second: float = 1.0
    message_target_mode: str = "random"  # "random", "broadcast", "specific"
    
    # Network conditions
    min_delay_ms: float = 0.0
    max_delay_ms: float = 100.0
    
    # Partitions
    enable_partitions: bool = False
    partition_count: int = 2
    partition_duration: float = 0.0  # 0 = permanent
    
    # Mobility
    enable_mobility: bool = False
    mobility_speed_min: float = 1.0
    mobility_speed_max: float = 10.0
    
    # Output
    output_dir: str = "../results"
    save_node_stats: bool = True


@dataclass
class ExperimentResults:
    """Results from an experiment run."""
    experiment_name: str
    timestamp: str
    runtime_seconds: float
    
    # Configuration
    num_nodes: int
    packet_loss: float
    
    # Delivery metrics
    messages_sent: int
    messages_delivered: int
    delivery_ratio: float
    messages_dropped: int
    
    # Timing metrics
    average_delay_ms: float
    gossip_rounds: int
    
    # Network metrics
    total_transmissions: int
    transmission_success_rate: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Simulator:
    """
    Main experiment simulator.
    
    Coordinates experiment execution and result collection.
    """
    
    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.swarm: Optional[Swarm] = None
        self.results: Optional[ExperimentResults] = None
        self._message_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Ensure output directory exists
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)
    
    def _create_network(self) -> SimulatedNetwork:
        """Create the simulated network with configured parameters."""
        network_config = NetworkConfig(
            packet_loss=self.config.packet_loss,
            min_delay_ms=self.config.min_delay_ms,
            max_delay_ms=self.config.max_delay_ms,
            communication_range=self.config.communication_range,
            world_width=self.config.world_size,
            world_height=self.config.world_size,
            mobility_enabled=self.config.enable_mobility,
            mobility_speed_min=self.config.mobility_speed_min,
            mobility_speed_max=self.config.mobility_speed_max,
        )
        return SimulatedNetwork(network_config)
    
    def _create_swarm(self, network: SimulatedNetwork) -> Swarm:
        """Create the swarm with configured parameters."""
        swarm_config = SwarmConfig(
            num_nodes=self.config.num_nodes,
            world_width=self.config.world_size,
            world_height=self.config.world_size,
            communication_range=self.config.communication_range,
            gossip_interval=self.config.gossip_interval,
            message_ttl=self.config.message_ttl,
        )
        return Swarm(network, swarm_config)
    
    def _setup_partitions(self):
        """Set up network partitions if configured."""
        if not self.config.enable_partitions:
            return
        
        nodes = list(self.swarm.get_all_nodes())
        nodes_per_partition = len(nodes) // self.config.partition_count
        
        groups = []
        for i in range(self.config.partition_count):
            start = i * nodes_per_partition
            end = start + nodes_per_partition if i < self.config.partition_count - 1 else len(nodes)
            group = {nodes[j].node_id for j in range(start, end)}
            groups.append(group)
        
        self.swarm.network.set_partitions_by_groups(groups)
        logger.info(f"Created {len(groups)} partitions")
    
    async def _generate_messages(self):
        """Generate messages at the configured rate."""
        interval = 1.0 / self.config.messages_per_second if self.config.messages_per_second > 0 else 1.0
        message_count = 0
        
        while self._running:
            message_count += 1
            payload = {
                "msg_num": message_count,
                "timestamp": datetime.utcnow().isoformat(),
                "data": f"test_message_{message_count}"
            }
            
            if self.config.message_target_mode == "broadcast":
                await self.swarm.broadcast_from_random(payload)
            elif self.config.message_target_mode == "random":
                # Send from random node to another random node
                nodes = self.swarm.get_all_nodes()
                if len(nodes) >= 2:
                    import random
                    from_node = random.choice(nodes)
                    to_node = random.choice([n for n in nodes if n.node_id != from_node.node_id])
                    await self.swarm.send_message(
                        from_node.node_id,
                        payload,
                        to_node=to_node.node_id
                    )
            else:
                await self.swarm.broadcast_from_random(payload)
            
            await asyncio.sleep(interval)
    
    async def run(self) -> ExperimentResults:
        """Run the experiment and return results."""
        logger.info(f"Starting experiment: {self.config.name}")
        logger.info(f"Config: {self.config.num_nodes} nodes, {self.config.packet_loss:.1%} loss, "
                   f"{self.config.runtime_seconds}s runtime")
        
        start_time = time.time()
        
        # Create network and swarm
        network = self._create_network()
        self.swarm = self._create_swarm(network)
        
        # Create nodes
        self.swarm.create_nodes()
        logger.info(f"Created {self.config.num_nodes} nodes")
        
        # Set up partitions if configured
        self._setup_partitions()
        
        # Start the swarm
        self._running = True
        await self.swarm.start()
        
        # Start message generation
        self._message_task = asyncio.create_task(self._generate_messages())
        
        # Handle partition healing if configured
        if self.config.enable_partitions and self.config.partition_duration > 0:
            asyncio.create_task(self._heal_partitions_after(self.config.partition_duration))
        
        # Run for the configured duration
        await asyncio.sleep(self.config.runtime_seconds)
        
        # Stop everything
        self._running = False
        if self._message_task:
            self._message_task.cancel()
            try:
                await self._message_task
            except asyncio.CancelledError:
                pass
        
        await self.swarm.stop()
        
        end_time = time.time()
        
        # Collect results
        metrics = self.swarm.get_metrics()
        network_stats = metrics.get("network_stats", {})
        
        self.results = ExperimentResults(
            experiment_name=self.config.name,
            timestamp=datetime.utcnow().isoformat(),
            runtime_seconds=end_time - start_time,
            num_nodes=self.config.num_nodes,
            packet_loss=self.config.packet_loss,
            messages_sent=metrics.get("total_messages_sent", 0),
            messages_delivered=metrics.get("total_messages_delivered", 0),
            delivery_ratio=metrics.get("delivery_ratio", 0),
            messages_dropped=network_stats.get("dropped_packets", 0),
            average_delay_ms=network_stats.get("average_delay_ms", 0),
            gossip_rounds=metrics.get("total_gossip_rounds", 0),
            total_transmissions=network_stats.get("total_transmissions", 0),
            transmission_success_rate=network_stats.get("transmission_success_rate", 0),
        )
        
        logger.info(f"Experiment complete: {self.results.messages_sent} sent, "
                   f"{self.results.messages_delivered} delivered "
                   f"({self.results.delivery_ratio:.1%})")
        
        return self.results
    
    async def _heal_partitions_after(self, duration: float):
        """Heal network partitions after a duration."""
        await asyncio.sleep(duration)
        if self._running:
            self.swarm.network.clear_partitions()
            logger.info("Network partitions healed")
    
    def save_results(self, filename: Optional[str] = None):
        """Save experiment results to CSV."""
        if not self.results:
            logger.warning("No results to save")
            return
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.config.name}_{timestamp}.csv"
        
        filepath = Path(self.config.output_dir) / filename
        
        # Write results
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.results.to_dict().keys())
            writer.writeheader()
            writer.writerow(self.results.to_dict())
        
        logger.info(f"Results saved to {filepath}")
        
        # Save node statistics if configured
        if self.config.save_node_stats and self.swarm:
            node_stats_file = filepath.with_suffix('.nodes.csv')
            node_stats = self.swarm.get_node_statistics()
            
            if node_stats:
                # Flatten nested stats
                flat_stats = []
                for stat in node_stats:
                    flat = {
                        'node_id': stat['node_id'],
                        'pos_x': stat['position']['x'],
                        'pos_y': stat['position']['y'],
                        'neighbors': stat['neighbors'],
                        **stat['stats']
                    }
                    flat_stats.append(flat)
                
                with open(node_stats_file, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=flat_stats[0].keys())
                    writer.writeheader()
                    writer.writerows(flat_stats)
                
                logger.info(f"Node statistics saved to {node_stats_file}")
    
    def print_summary(self):
        """Print a summary of the results."""
        if not self.results:
            print("No results available")
            return
        
        print("\n" + "="*60)
        print(f"EXPERIMENT SUMMARY: {self.results.experiment_name}")
        print("="*60)
        print(f"Runtime:              {self.results.runtime_seconds:.2f} seconds")
        print(f"Nodes:                {self.results.num_nodes}")
        print(f"Packet Loss:          {self.results.packet_loss:.1%}")
        print("-"*60)
        print(f"Messages Sent:        {self.results.messages_sent}")
        print(f"Messages Delivered:   {self.results.messages_delivered}")
        print(f"Delivery Ratio:       {self.results.delivery_ratio:.2%}")
        print(f"Messages Dropped:     {self.results.messages_dropped}")
        print("-"*60)
        print(f"Average Delay:        {self.results.average_delay_ms:.2f} ms")
        print(f"Gossip Rounds:        {self.results.gossip_rounds}")
        print(f"Total Transmissions:  {self.results.total_transmissions}")
        print(f"Transmission Success: {self.results.transmission_success_rate:.2%}")
        print("="*60 + "\n")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='P2P Swarm Network Simulator',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument('--name', type=str, default='simulation',
                       help='Experiment name')
    parser.add_argument('--nodes', type=int, default=50,
                       help='Number of nodes in the swarm')
    parser.add_argument('--packet-loss', type=float, default=0.0,
                       help='Packet loss probability (0.0-1.0)')
    parser.add_argument('--runtime', type=float, default=60.0,
                       help='Simulation runtime in seconds')
    parser.add_argument('--world-size', type=float, default=1000.0,
                       help='World size (square)')
    parser.add_argument('--range', type=float, default=150.0,
                       help='Communication range')
    parser.add_argument('--gossip-interval', type=float, default=0.1,
                       help='Interval between gossip rounds')
    parser.add_argument('--ttl', type=int, default=10,
                       help='Message time-to-live (hops)')
    parser.add_argument('--msg-rate', type=float, default=1.0,
                       help='Messages generated per second')
    parser.add_argument('--min-delay', type=float, default=0.0,
                       help='Minimum transmission delay (ms)')
    parser.add_argument('--max-delay', type=float, default=100.0,
                       help='Maximum transmission delay (ms)')
    parser.add_argument('--partitions', type=int, default=0,
                       help='Number of network partitions (0=disabled)')
    parser.add_argument('--partition-duration', type=float, default=0.0,
                       help='Partition duration in seconds (0=permanent)')
    parser.add_argument('--mobility', action='store_true',
                       help='Enable node mobility')
    parser.add_argument('--output-dir', type=str, default='../results',
                       help='Output directory for results')
    parser.add_argument('--no-save', action='store_true',
                       help='Do not save results to file')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    return parser.parse_args()


async def main():
    """Main entry point."""
    args = parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create experiment configuration
    config = ExperimentConfig(
        name=args.name,
        num_nodes=args.nodes,
        packet_loss=args.packet_loss,
        runtime_seconds=args.runtime,
        world_size=args.world_size,
        communication_range=args.range,
        gossip_interval=args.gossip_interval,
        message_ttl=args.ttl,
        messages_per_second=args.msg_rate,
        min_delay_ms=args.min_delay,
        max_delay_ms=args.max_delay,
        enable_partitions=args.partitions > 0,
        partition_count=args.partitions if args.partitions > 0 else 2,
        partition_duration=args.partition_duration,
        enable_mobility=args.mobility,
        output_dir=args.output_dir,
    )
    
    # Run the simulation
    simulator = Simulator(config)
    
    try:
        results = await simulator.run()
        simulator.print_summary()
        
        if not args.no_save:
            simulator.save_results()
        
        return 0
    
    except KeyboardInterrupt:
        logger.info("Simulation interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Simulation failed: {e}")
        raise


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
