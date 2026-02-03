# Research Experiments Guide

This guide explains how to design and run experiments with the P2P-Swarm-Model simulator.

## Quick Start

### Running the Basic Simulation

```bash
# Basic run with defaults (20 nodes, 10 rounds)
python -m sim.simulator

# Custom configuration
python -m sim.simulator --nodes 50 --packet-loss 0.2 --runtime 60

# Full options
python -m sim.simulator \
  --nodes 100 \
  --packet-loss 0.15 \
  --delay-min 0.01 \
  --delay-max 0.1 \
  --runtime 120 \
  --gossip-interval 0.5 \
  --output results.csv
```

## Pre-Built Experiments

### 1. Partition Tolerance Test

Tests message delivery before, during, and after network partitions.

```bash
python -m sim.scenarios.partition_test
```

**What it measures:**
- Delivery rate in normal conditions
- Impact of network splits
- Healing behavior after partition removal

**Expected output:**
```
=== Partition Tolerance Experiment ===
Nodes: 30
Message rate: 5/sec
Packet loss: 10%

Phase 1: Pre-partition (10s)
  Messages sent: 50
  Delivered: 47 (94.0%)

Phase 2: Partitioned (15s)
  Messages sent: 75
  Delivered: 41 (54.7%)
  Cross-partition: 0

Phase 3: Healed (10s)
  Messages sent: 50
  Delivered: 48 (96.0%)
```

### 2. Mobility Impact Test

Compares message delivery across different node movement speeds.

```bash
python -m sim.scenarios.mobility_test
```

**Scenarios tested:**
- Static: No movement
- Slow: 1-5 units/second
- Fast: 10-20 units/second

**What it measures:**
- How mobility affects connectivity
- Message delivery variance
- Neighbor stability

## Designing Custom Experiments

### Experiment Template

```python
"""custom_experiment.py"""
import asyncio
from sim.swarm import Swarm
from sim.network import SimulatedNetwork, NetworkConfig

async def run_experiment():
    # 1. Configure network conditions
    config = NetworkConfig(
        packet_loss=0.1,
        delay_min=0.01,
        delay_max=0.05,
        world_size=(500, 500),
        comm_range=100.0
    )
    network = SimulatedNetwork(config)
    
    # 2. Create swarm with nodes
    swarm = Swarm(network)
    swarm.create_nodes_random(count=50)
    
    # 3. Inject test messages
    for i, node in enumerate(swarm.nodes[:10]):
        target = swarm.nodes[(i + 25) % len(swarm.nodes)]
        node.send(
            to=target.node_id,
            payload={"experiment": "custom", "seq": i}
        )
    
    # 4. Run simulation
    await swarm.run_gossip_loop(
        rounds=100,
        interval=0.1
    )
    
    # 5. Collect results
    metrics = swarm.get_metrics()
    print(f"Delivery rate: {metrics['delivery_rate']:.2%}")
    return metrics

if __name__ == "__main__":
    asyncio.run(run_experiment())
```

### Research Variables

#### Independent Variables (What you change)

| Variable | Range | Purpose |
|----------|-------|---------|
| `nodes` | 10-1000 | Test scalability |
| `packet_loss` | 0.0-0.5 | Simulate unreliable links |
| `delay_min/max` | 0-1s | Model latency |
| `comm_range` | 50-200 | Affect connectivity |
| `ttl` | 5-50 | Message lifetime |
| `gossip_interval` | 0.1-2s | Protocol frequency |

#### Dependent Variables (What you measure)

| Metric | Formula | Meaning |
|--------|---------|---------|
| Delivery Rate | delivered / sent | Success percentage |
| Average Hops | sum(hops) / delivered | Path efficiency |
| Convergence Time | time(all delivered) | Speed |
| Message Overhead | total_tx / delivered | Efficiency |

## Experiment Scenarios

### Scenario 1: Scalability Study

**Research Question:** How does delivery rate change as network size increases?

```python
import asyncio
from sim.swarm import Swarm
from sim.network import SimulatedNetwork, NetworkConfig

async def scalability_experiment():
    results = []
    
    for node_count in [10, 25, 50, 100, 200, 500]:
        config = NetworkConfig(
            packet_loss=0.1,
            world_size=(1000, 1000),
            comm_range=150.0
        )
        network = SimulatedNetwork(config)
        swarm = Swarm(network)
        swarm.create_nodes_random(count=node_count)
        
        # Send messages
        msg_count = node_count // 2
        for i in range(msg_count):
            sender = swarm.nodes[i]
            receiver = swarm.nodes[-(i+1)]
            sender.send(to=receiver.node_id, payload={"test": i})
        
        await swarm.run_gossip_loop(rounds=50, interval=0.1)
        metrics = swarm.get_metrics()
        
        results.append({
            "nodes": node_count,
            "delivery_rate": metrics["delivery_rate"],
            "avg_hops": metrics["avg_hops"]
        })
        print(f"Nodes: {node_count}, Rate: {metrics['delivery_rate']:.2%}")
    
    return results

asyncio.run(scalability_experiment())
```

### Scenario 2: Packet Loss Sensitivity

**Research Question:** At what packet loss rate does delivery become unreliable?

```python
async def loss_sensitivity_experiment():
    results = []
    
    for loss in [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5]:
        config = NetworkConfig(
            packet_loss=loss,
            world_size=(500, 500),
            comm_range=100.0
        )
        network = SimulatedNetwork(config)
        swarm = Swarm(network)
        swarm.create_nodes_random(count=50)
        
        # Inject messages
        for i in range(25):
            swarm.nodes[i].send(
                to=swarm.nodes[49-i].node_id,
                payload={"loss_test": loss}
            )
        
        await swarm.run_gossip_loop(rounds=100, interval=0.1)
        metrics = swarm.get_metrics()
        
        results.append({
            "packet_loss": loss,
            "delivery_rate": metrics["delivery_rate"]
        })
        print(f"Loss: {loss:.0%}, Delivery: {metrics['delivery_rate']:.2%}")
    
    return results
```

### Scenario 3: TTL Optimization

**Research Question:** What is the optimal TTL for different network sizes?

```python
async def ttl_optimization_experiment():
    results = []
    
    for ttl in [5, 10, 15, 20, 30, 50]:
        config = NetworkConfig(
            packet_loss=0.1,
            world_size=(500, 500),
            comm_range=100.0
        )
        network = SimulatedNetwork(config)
        swarm = Swarm(network)
        swarm.create_nodes_random(count=100)
        
        # Inject messages with specific TTL
        for i in range(50):
            swarm.nodes[i].send(
                to=swarm.nodes[99-i].node_id,
                payload={"ttl_test": ttl},
                ttl=ttl
            )
        
        await swarm.run_gossip_loop(rounds=100, interval=0.1)
        metrics = swarm.get_metrics()
        
        overhead = metrics["total_transmissions"] / max(1, metrics["delivered"])
        
        results.append({
            "ttl": ttl,
            "delivery_rate": metrics["delivery_rate"],
            "overhead": overhead
        })
        print(f"TTL: {ttl}, Delivery: {metrics['delivery_rate']:.2%}, Overhead: {overhead:.1f}x")
    
    return results
```

## Statistical Analysis

### Running Multiple Trials

```python
import statistics

async def run_with_replication(experiment_func, trials=10):
    """Run experiment multiple times for statistical validity."""
    all_results = []
    
    for trial in range(trials):
        result = await experiment_func()
        all_results.append(result["delivery_rate"])
    
    return {
        "mean": statistics.mean(all_results),
        "stdev": statistics.stdev(all_results) if len(all_results) > 1 else 0,
        "min": min(all_results),
        "max": max(all_results),
        "trials": trials
    }
```

### Confidence Intervals

```python
import math

def confidence_interval(data, confidence=0.95):
    """Calculate confidence interval for results."""
    n = len(data)
    mean = statistics.mean(data)
    stdev = statistics.stdev(data)
    
    # t-value approximation for 95% CI
    t_value = 1.96 if n > 30 else 2.045
    
    margin = t_value * (stdev / math.sqrt(n))
    return (mean - margin, mean + margin)
```

## Output and Visualization

### Export to CSV

```python
import csv

def export_results(results, filename="experiment_results.csv"):
    """Export experiment results to CSV."""
    if not results:
        return
    
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    
    print(f"Results saved to {filename}")
```

### Generate Plots

```python
from sim.plots import (
    plot_delivery_vs_loss,
    plot_message_hops,
    plot_convergence
)

# After running experiment
plot_delivery_vs_loss(results, output="delivery_loss.png")
plot_convergence(timeline_data, output="convergence.png")
```

## Best Practices

### 1. Reproducibility
```python
import random
random.seed(42)  # Set seed for reproducible results
```

### 2. Warm-up Period
```python
# Run some rounds before collecting metrics
await swarm.run_gossip_loop(rounds=10, interval=0.1)  # Warm-up
swarm.reset_metrics()  # Clear warm-up data
await swarm.run_gossip_loop(rounds=100, interval=0.1)  # Actual experiment
```

### 3. Parameter Documentation
```python
experiment_config = {
    "name": "Scalability Study v1",
    "date": "2026-02-03",
    "parameters": {
        "nodes": 50,
        "packet_loss": 0.1,
        "ttl": 15,
        "rounds": 100
    },
    "hypothesis": "Delivery rate decreases logarithmically with node count"
}
```

## Docker-Based Experiments

For reproducible, isolated experiments:

```bash
# Build simulator image
docker build -f Dockerfile.sim -t p2p-sim .

# Run experiment
docker run --rm -v $(pwd)/results:/app/results p2p-sim \
  python -m sim.simulator --nodes 100 --output /app/results/exp1.csv

# Run with specific scenario
docker run --rm p2p-sim python -m sim.scenarios.partition_test
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Low delivery rate | High packet loss | Reduce `packet_loss` |
| Messages stuck | Low TTL | Increase `ttl` |
| Slow convergence | Sparse network | Increase `comm_range` or reduce `world_size` |
| High memory | Too many messages | Limit queue size, reduce node count |
| No neighbors | Nodes too far apart | Check `comm_range` vs `world_size` |
