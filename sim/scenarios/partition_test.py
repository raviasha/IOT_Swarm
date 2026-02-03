#!/usr/bin/env python3
"""
partition_test.py - Network Partition Experiment

This experiment:
1. Creates 50 nodes in a connected network
2. Splits them into two isolated partitions for 5 minutes
3. Reconnects (heals) the partitions
4. Measures how many messages eventually get delivered

This tests the swarm's ability to buffer and eventually deliver
messages across network partitions.
"""

import asyncio
import sys
import os
import logging
import time
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from node import Node, Message, Position, Urgency
from network import SimulatedNetwork, NetworkConfig
from swarm import Swarm, SwarmConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PartitionExperiment:
    """
    Network partition experiment.
    
    Tests message delivery across network partitions and healing.
    """
    
    def __init__(
        self,
        num_nodes: int = 50,
        partition_duration: float = 300.0,  # 5 minutes
        pre_partition_time: float = 60.0,   # 1 minute
        post_healing_time: float = 120.0,   # 2 minutes
        world_size: float = 1000.0,
        packet_loss: float = 0.1,
        messages_per_second: float = 2.0
    ):
        self.num_nodes = num_nodes
        self.partition_duration = partition_duration
        self.pre_partition_time = pre_partition_time
        self.post_healing_time = post_healing_time
        self.world_size = world_size
        self.packet_loss = packet_loss
        self.messages_per_second = messages_per_second
        
        # Results storage
        self.results = {
            'pre_partition': {},
            'during_partition': {},
            'post_healing': {},
            'summary': {}
        }
        
        self.swarm = None
        self.network = None
        self._running = False
        self._message_count = 0
        self._cross_partition_messages = []
    
    def _create_network_and_swarm(self):
        """Create the network and swarm."""
        network_config = NetworkConfig(
            packet_loss=self.packet_loss,
            min_delay_ms=10.0,
            max_delay_ms=100.0,
            communication_range=200.0,
            world_width=self.world_size,
            world_height=self.world_size
        )
        
        self.network = SimulatedNetwork(network_config)
        
        swarm_config = SwarmConfig(
            num_nodes=self.num_nodes,
            world_width=self.world_size,
            world_height=self.world_size,
            communication_range=200.0,
            gossip_interval=0.1,
            message_ttl=20  # Higher TTL for partition recovery
        )
        
        self.swarm = Swarm(self.network, swarm_config)
        
        # Create nodes in two clusters (to make partition more realistic)
        half = self.num_nodes // 2
        self.swarm.create_nodes_in_clusters(
            num_clusters=2,
            nodes_per_cluster=half,
            cluster_radius=150.0
        )
        
        logger.info(f"Created {self.num_nodes} nodes in 2 clusters")
    
    def _create_partition(self):
        """Split the network into two partitions."""
        nodes = self.swarm.get_all_nodes()
        half = len(nodes) // 2
        
        # First half in partition 0
        partition_0 = {nodes[i].node_id for i in range(half)}
        # Second half in partition 1
        partition_1 = {nodes[i].node_id for i in range(half, len(nodes))}
        
        self.network.set_partitions_by_groups([partition_0, partition_1])
        
        logger.info(f"Network partitioned: {len(partition_0)} nodes vs {len(partition_1)} nodes")
        return partition_0, partition_1
    
    def _heal_partition(self):
        """Heal the network partition."""
        self.network.clear_partitions()
        logger.info("Network partition healed - all nodes can now communicate")
    
    async def _generate_messages(self, partition_0, partition_1):
        """Generate messages, including cross-partition messages."""
        interval = 1.0 / self.messages_per_second
        nodes = self.swarm.get_all_nodes()
        
        import random
        
        while self._running:
            self._message_count += 1
            
            # 50% of messages are cross-partition (harder to deliver)
            if random.random() < 0.5:
                # Cross-partition message
                from_partition = random.choice([partition_0, partition_1])
                to_partition = partition_1 if from_partition == partition_0 else partition_0
                
                from_node_id = random.choice(list(from_partition))
                to_node_id = random.choice(list(to_partition))
                
                msg = await self.swarm.send_message(
                    from_node_id,
                    {"msg_num": self._message_count, "cross_partition": True},
                    to_node=to_node_id,
                    urgency=Urgency.HIGH
                )
                if msg:
                    self._cross_partition_messages.append(msg.id)
            else:
                # Same-partition message
                partition = random.choice([partition_0, partition_1])
                from_node_id = random.choice(list(partition))
                to_node_id = random.choice(list(partition - {from_node_id}))
                
                await self.swarm.send_message(
                    from_node_id,
                    {"msg_num": self._message_count, "cross_partition": False},
                    to_node=to_node_id
                )
            
            await asyncio.sleep(interval)
    
    def _collect_metrics(self, phase: str):
        """Collect current metrics for a phase."""
        metrics = self.swarm.get_metrics()
        network_stats = metrics.get('network_stats', {})
        
        self.results[phase] = {
            'messages_sent': metrics.get('total_messages_sent', 0),
            'messages_delivered': metrics.get('total_messages_delivered', 0),
            'delivery_ratio': metrics.get('delivery_ratio', 0),
            'dropped_packets': network_stats.get('dropped_packets', 0),
            'gossip_rounds': metrics.get('total_gossip_rounds', 0),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Phase '{phase}': {self.results[phase]['messages_delivered']}/"
                   f"{self.results[phase]['messages_sent']} delivered "
                   f"({self.results[phase]['delivery_ratio']:.1%})")
    
    async def run(self):
        """Run the partition experiment."""
        logger.info("="*60)
        logger.info("PARTITION EXPERIMENT")
        logger.info("="*60)
        logger.info(f"Nodes: {self.num_nodes}")
        logger.info(f"Pre-partition time: {self.pre_partition_time}s")
        logger.info(f"Partition duration: {self.partition_duration}s")
        logger.info(f"Post-healing time: {self.post_healing_time}s")
        logger.info("="*60)
        
        start_time = time.time()
        
        # Setup
        self._create_network_and_swarm()
        nodes = self.swarm.get_all_nodes()
        half = len(nodes) // 2
        partition_0 = {nodes[i].node_id for i in range(half)}
        partition_1 = {nodes[i].node_id for i in range(half, len(nodes))}
        
        # Start swarm
        self._running = True
        await self.swarm.start()
        
        # Start message generation
        message_task = asyncio.create_task(
            self._generate_messages(partition_0, partition_1)
        )
        
        # Phase 1: Pre-partition (normal operation)
        logger.info("\n--- Phase 1: Pre-partition (normal operation) ---")
        await asyncio.sleep(self.pre_partition_time)
        self._collect_metrics('pre_partition')
        
        # Phase 2: Create partition
        logger.info("\n--- Phase 2: Network partitioned ---")
        self._create_partition()
        await asyncio.sleep(self.partition_duration)
        self._collect_metrics('during_partition')
        
        # Phase 3: Heal partition
        logger.info("\n--- Phase 3: Partition healed ---")
        self._heal_partition()
        await asyncio.sleep(self.post_healing_time)
        self._collect_metrics('post_healing')
        
        # Stop
        self._running = False
        message_task.cancel()
        try:
            await message_task
        except asyncio.CancelledError:
            pass
        
        await self.swarm.stop()
        
        end_time = time.time()
        
        # Calculate summary
        total_runtime = end_time - start_time
        final_metrics = self.swarm.get_metrics()
        
        self.results['summary'] = {
            'total_runtime_seconds': total_runtime,
            'total_messages_sent': final_metrics.get('total_messages_sent', 0),
            'total_messages_delivered': final_metrics.get('total_messages_delivered', 0),
            'final_delivery_ratio': final_metrics.get('delivery_ratio', 0),
            'cross_partition_messages': len(self._cross_partition_messages),
            'num_nodes': self.num_nodes,
            'partition_duration': self.partition_duration
        }
        
        self._print_results()
        return self.results
    
    def _print_results(self):
        """Print experiment results."""
        print("\n" + "="*60)
        print("PARTITION EXPERIMENT RESULTS")
        print("="*60)
        
        for phase in ['pre_partition', 'during_partition', 'post_healing']:
            data = self.results[phase]
            print(f"\n{phase.replace('_', ' ').upper()}:")
            print(f"  Messages Sent:     {data.get('messages_sent', 0)}")
            print(f"  Messages Delivered: {data.get('messages_delivered', 0)}")
            print(f"  Delivery Ratio:    {data.get('delivery_ratio', 0):.2%}")
        
        print("\n" + "-"*60)
        print("SUMMARY:")
        summary = self.results['summary']
        print(f"  Total Runtime:           {summary['total_runtime_seconds']:.1f}s")
        print(f"  Total Messages Sent:     {summary['total_messages_sent']}")
        print(f"  Total Delivered:         {summary['total_messages_delivered']}")
        print(f"  Final Delivery Ratio:    {summary['final_delivery_ratio']:.2%}")
        print(f"  Cross-partition Messages: {summary['cross_partition_messages']}")
        print("="*60 + "\n")
    
    def save_results(self, output_dir: str = "../results"):
        """Save results to CSV."""
        import csv
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_path / f"partition_test_{timestamp}.csv"
        
        # Flatten results for CSV
        flat_results = {
            'experiment': 'partition_test',
            'timestamp': timestamp,
            **{f'pre_{k}': v for k, v in self.results['pre_partition'].items()},
            **{f'during_{k}': v for k, v in self.results['during_partition'].items()},
            **{f'post_{k}': v for k, v in self.results['post_healing'].items()},
            **{f'summary_{k}': v for k, v in self.results['summary'].items()}
        }
        
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=flat_results.keys())
            writer.writeheader()
            writer.writerow(flat_results)
        
        logger.info(f"Results saved to {filename}")


async def run_partition_test(
    num_nodes: int = 50,
    partition_duration: float = 60.0,  # Shorter for demo
    pre_partition_time: float = 30.0,
    post_healing_time: float = 30.0,
    save_results: bool = True
):
    """
    Run the partition test experiment.
    
    Args:
        num_nodes: Number of nodes in the swarm
        partition_duration: How long to maintain the partition (seconds)
        pre_partition_time: Time before creating partition (seconds)
        post_healing_time: Time after healing partition (seconds)
        save_results: Whether to save results to file
    """
    experiment = PartitionExperiment(
        num_nodes=num_nodes,
        partition_duration=partition_duration,
        pre_partition_time=pre_partition_time,
        post_healing_time=post_healing_time
    )
    
    results = await experiment.run()
    
    if save_results:
        experiment.save_results()
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run network partition experiment')
    parser.add_argument('--nodes', type=int, default=50, help='Number of nodes')
    parser.add_argument('--partition-time', type=float, default=60.0, 
                       help='Partition duration in seconds')
    parser.add_argument('--quick', action='store_true', 
                       help='Quick test with shorter durations')
    args = parser.parse_args()
    
    if args.quick:
        # Quick test mode
        asyncio.run(run_partition_test(
            num_nodes=20,
            partition_duration=10.0,
            pre_partition_time=5.0,
            post_healing_time=10.0
        ))
    else:
        asyncio.run(run_partition_test(
            num_nodes=args.nodes,
            partition_duration=args.partition_time
        ))
