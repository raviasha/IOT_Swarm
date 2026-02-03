#!/usr/bin/env python3
"""
mobility_test.py - Node Mobility Experiment

This experiment:
1. Creates nodes that move randomly in space using random waypoint model
2. Measures how mobility affects message delivery time and reliability
3. Compares with static network performance

Tests the swarm's ability to handle dynamic topology changes.
"""

import asyncio
import sys
import os
import logging
import time
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

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


class MobilityExperiment:
    """
    Node mobility experiment.
    
    Tests message delivery under different mobility conditions.
    """
    
    def __init__(
        self,
        num_nodes: int = 50,
        world_size: float = 1000.0,
        runtime_per_phase: float = 60.0,
        packet_loss: float = 0.1,
        messages_per_second: float = 2.0,
        communication_range: float = 150.0
    ):
        self.num_nodes = num_nodes
        self.world_size = world_size
        self.runtime_per_phase = runtime_per_phase
        self.packet_loss = packet_loss
        self.messages_per_second = messages_per_second
        self.communication_range = communication_range
        
        # Results storage
        self.results = {
            'static': {},
            'slow_mobility': {},
            'fast_mobility': {},
            'summary': {}
        }
        
        self.swarm = None
        self.network = None
        self._running = False
        self._message_count = 0
        self._delivery_times: List[float] = []
    
    def _create_network(self, mobility_enabled: bool, speed_min: float, speed_max: float) -> SimulatedNetwork:
        """Create network with specified mobility settings."""
        config = NetworkConfig(
            packet_loss=self.packet_loss,
            min_delay_ms=10.0,
            max_delay_ms=50.0,
            communication_range=self.communication_range,
            world_width=self.world_size,
            world_height=self.world_size,
            mobility_enabled=mobility_enabled,
            mobility_speed_min=speed_min,
            mobility_speed_max=speed_max,
            mobility_pause_min=1.0,
            mobility_pause_max=5.0
        )
        return SimulatedNetwork(config)
    
    def _create_swarm(self, network: SimulatedNetwork) -> Swarm:
        """Create swarm with the network."""
        config = SwarmConfig(
            num_nodes=self.num_nodes,
            world_width=self.world_size,
            world_height=self.world_size,
            communication_range=self.communication_range,
            gossip_interval=0.1,
            message_ttl=15
        )
        swarm = Swarm(network, config)
        swarm.create_nodes()
        return swarm
    
    async def _generate_messages(self):
        """Generate messages at regular intervals."""
        interval = 1.0 / self.messages_per_second
        
        while self._running:
            self._message_count += 1
            
            nodes = self.swarm.get_all_nodes()
            if len(nodes) >= 2:
                from_node = random.choice(nodes)
                to_node = random.choice([n for n in nodes if n.node_id != from_node.node_id])
                
                send_time = time.time()
                msg = await self.swarm.send_message(
                    from_node.node_id,
                    {
                        "msg_num": self._message_count,
                        "send_time": send_time
                    },
                    to_node=to_node.node_id
                )
            
            await asyncio.sleep(interval)
    
    async def _track_topology_changes(self):
        """Track how often the network topology changes."""
        changes = 0
        last_connectivity = {}
        
        while self._running:
            current_connectivity = self.swarm.get_connectivity_matrix()
            
            if last_connectivity:
                for node_id, neighbors in current_connectivity.items():
                    old_neighbors = set(last_connectivity.get(node_id, []))
                    new_neighbors = set(neighbors)
                    if old_neighbors != new_neighbors:
                        changes += 1
            
            last_connectivity = current_connectivity
            await asyncio.sleep(1.0)
        
        return changes
    
    def _collect_metrics(self, phase: str):
        """Collect metrics for current phase."""
        metrics = self.swarm.get_metrics()
        network_stats = metrics.get('network_stats', {})
        
        self.results[phase] = {
            'messages_sent': metrics.get('total_messages_sent', 0),
            'messages_delivered': metrics.get('total_messages_delivered', 0),
            'delivery_ratio': metrics.get('delivery_ratio', 0),
            'dropped_packets': network_stats.get('dropped_packets', 0),
            'average_delay_ms': network_stats.get('average_delay_ms', 0),
            'gossip_rounds': metrics.get('total_gossip_rounds', 0),
            'transmission_success_rate': network_stats.get('transmission_success_rate', 0)
        }
        
        logger.info(f"Phase '{phase}': delivery ratio = {self.results[phase]['delivery_ratio']:.1%}")
    
    async def _run_phase(self, phase_name: str, mobility_enabled: bool, speed_min: float, speed_max: float):
        """Run a single phase of the experiment."""
        logger.info(f"\n{'='*60}")
        logger.info(f"PHASE: {phase_name.upper()}")
        logger.info(f"Mobility: {'enabled' if mobility_enabled else 'disabled'}")
        if mobility_enabled:
            logger.info(f"Speed range: {speed_min} - {speed_max} units/sec")
        logger.info(f"{'='*60}")
        
        # Create fresh network and swarm for this phase
        self.network = self._create_network(mobility_enabled, speed_min, speed_max)
        self.swarm = self._create_swarm(self.network)
        
        self._running = True
        self._message_count = 0
        
        # Start the swarm
        await self.swarm.start()
        
        # Start message generation
        message_task = asyncio.create_task(self._generate_messages())
        
        # Track topology if mobile
        topology_task = None
        if mobility_enabled:
            topology_task = asyncio.create_task(self._track_topology_changes())
        
        # Run for the specified duration
        await asyncio.sleep(self.runtime_per_phase)
        
        # Stop
        self._running = False
        message_task.cancel()
        if topology_task:
            topology_task.cancel()
        
        try:
            await message_task
        except asyncio.CancelledError:
            pass
        
        await self.swarm.stop()
        
        # Collect metrics
        self._collect_metrics(phase_name)
        
        return self.results[phase_name]
    
    async def run(self):
        """Run the complete mobility experiment."""
        logger.info("="*60)
        logger.info("MOBILITY EXPERIMENT")
        logger.info("="*60)
        logger.info(f"Nodes: {self.num_nodes}")
        logger.info(f"World size: {self.world_size}x{self.world_size}")
        logger.info(f"Runtime per phase: {self.runtime_per_phase}s")
        logger.info(f"Communication range: {self.communication_range}")
        logger.info("="*60)
        
        start_time = time.time()
        
        # Phase 1: Static (no mobility)
        await self._run_phase('static', mobility_enabled=False, speed_min=0, speed_max=0)
        
        # Phase 2: Slow mobility
        await self._run_phase('slow_mobility', mobility_enabled=True, speed_min=1.0, speed_max=5.0)
        
        # Phase 3: Fast mobility
        await self._run_phase('fast_mobility', mobility_enabled=True, speed_min=10.0, speed_max=30.0)
        
        end_time = time.time()
        
        # Calculate summary
        self.results['summary'] = {
            'total_runtime_seconds': end_time - start_time,
            'num_nodes': self.num_nodes,
            'world_size': self.world_size,
            'communication_range': self.communication_range,
            'static_delivery_ratio': self.results['static'].get('delivery_ratio', 0),
            'slow_mobility_delivery_ratio': self.results['slow_mobility'].get('delivery_ratio', 0),
            'fast_mobility_delivery_ratio': self.results['fast_mobility'].get('delivery_ratio', 0)
        }
        
        self._print_results()
        return self.results
    
    def _print_results(self):
        """Print experiment results."""
        print("\n" + "="*60)
        print("MOBILITY EXPERIMENT RESULTS")
        print("="*60)
        
        for phase in ['static', 'slow_mobility', 'fast_mobility']:
            data = self.results[phase]
            print(f"\n{phase.replace('_', ' ').upper()}:")
            print(f"  Messages Sent:          {data.get('messages_sent', 0)}")
            print(f"  Messages Delivered:     {data.get('messages_delivered', 0)}")
            print(f"  Delivery Ratio:         {data.get('delivery_ratio', 0):.2%}")
            print(f"  Average Delay:          {data.get('average_delay_ms', 0):.2f} ms")
            print(f"  Transmission Success:   {data.get('transmission_success_rate', 0):.2%}")
        
        print("\n" + "-"*60)
        print("COMPARISON:")
        summary = self.results['summary']
        print(f"  Static Delivery Ratio:      {summary['static_delivery_ratio']:.2%}")
        print(f"  Slow Mobility Delivery:     {summary['slow_mobility_delivery_ratio']:.2%}")
        print(f"  Fast Mobility Delivery:     {summary['fast_mobility_delivery_ratio']:.2%}")
        
        # Calculate impact
        if summary['static_delivery_ratio'] > 0:
            slow_impact = ((summary['slow_mobility_delivery_ratio'] - summary['static_delivery_ratio']) 
                          / summary['static_delivery_ratio'] * 100)
            fast_impact = ((summary['fast_mobility_delivery_ratio'] - summary['static_delivery_ratio']) 
                          / summary['static_delivery_ratio'] * 100)
            print(f"\n  Slow Mobility Impact:       {slow_impact:+.1f}%")
            print(f"  Fast Mobility Impact:       {fast_impact:+.1f}%")
        
        print("="*60 + "\n")
    
    def save_results(self, output_dir: str = "../results"):
        """Save results to CSV."""
        import csv
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_path / f"mobility_test_{timestamp}.csv"
        
        # Flatten results
        flat_results = {
            'experiment': 'mobility_test',
            'timestamp': timestamp,
            **{f'static_{k}': v for k, v in self.results['static'].items()},
            **{f'slow_{k}': v for k, v in self.results['slow_mobility'].items()},
            **{f'fast_{k}': v for k, v in self.results['fast_mobility'].items()},
            **{f'summary_{k}': v for k, v in self.results['summary'].items()}
        }
        
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=flat_results.keys())
            writer.writeheader()
            writer.writerow(flat_results)
        
        logger.info(f"Results saved to {filename}")


async def run_mobility_test(
    num_nodes: int = 50,
    runtime_per_phase: float = 30.0,
    save_results: bool = True
):
    """
    Run the mobility test experiment.
    
    Args:
        num_nodes: Number of nodes in the swarm
        runtime_per_phase: Duration for each mobility phase (seconds)
        save_results: Whether to save results to file
    """
    experiment = MobilityExperiment(
        num_nodes=num_nodes,
        runtime_per_phase=runtime_per_phase
    )
    
    results = await experiment.run()
    
    if save_results:
        experiment.save_results()
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run mobility experiment')
    parser.add_argument('--nodes', type=int, default=50, help='Number of nodes')
    parser.add_argument('--runtime', type=float, default=30.0, 
                       help='Runtime per phase in seconds')
    parser.add_argument('--quick', action='store_true',
                       help='Quick test with shorter durations')
    args = parser.parse_args()
    
    if args.quick:
        asyncio.run(run_mobility_test(
            num_nodes=20,
            runtime_per_phase=10.0
        ))
    else:
        asyncio.run(run_mobility_test(
            num_nodes=args.nodes,
            runtime_per_phase=args.runtime
        ))
