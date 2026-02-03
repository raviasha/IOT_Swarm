# P2P Swarm Model Architecture

## Overview

The P2P-Swarm-Model is a **software-only simulation** of a peer-to-peer communication network for disconnected IoT devices. It models realistic swarm behavior without requiring any physical hardware.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        P2P SWARM MODEL                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐        │
│   │ Node 1  │◄──►│ Node 2  │◄──►│ Node 3  │◄──►│ Node N  │        │
│   └────┬────┘    └────┬────┘    └────┬────┘    └────┬────┘        │
│        │              │              │              │              │
│        └──────────────┴──────────────┴──────────────┘              │
│                              │                                      │
│                    ┌─────────▼─────────┐                           │
│                    │ Simulated Network │                           │
│                    │  (network.py)     │                           │
│                    │  - Packet loss    │                           │
│                    │  - Delays         │                           │
│                    │  - Partitions     │                           │
│                    │  - Mobility       │                           │
│                    └─────────┬─────────┘                           │
│                              │                                      │
│                    ┌─────────▼─────────┐                           │
│                    │     Gateway       │                           │
│                    │   (Go Service)    │                           │
│                    │  - REST API       │                           │
│                    │  - Message Store  │                           │
│                    └───────────────────┘                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Virtual Nodes (`node.py`)

Each node represents a simulated IoT device:

```
┌────────────────────────────────────────┐
│              Virtual Node              │
├────────────────────────────────────────┤
│  • Node ID (unique identifier)         │
│  • Position (x, y coordinates)         │
│  • Communication Range                 │
│  • Message Inbox/Outbox                │
│  • Neighbor List                       │
│  • Statistics                          │
├────────────────────────────────────────┤
│  Methods:                              │
│  • send() - Queue outgoing message     │
│  • receive() - Accept incoming message │
│  • gossip_round() - Forward messages   │
└────────────────────────────────────────┘
```

### 2. Simulated Network (`network.py`)

The network layer simulates wireless communication:

```
┌────────────────────────────────────────┐
│          Simulated Network             │
├────────────────────────────────────────┤
│  Network Conditions:                   │
│  • Packet Loss (0-100%)                │
│  • Transmission Delay (ms)             │
│  • Communication Range                 │
│                                        │
│  Topology Features:                    │
│  • Network Partitions                  │
│  • Dynamic Neighbor Discovery          │
│                                        │
│  Mobility Model:                       │
│  • Random Waypoint Movement            │
│  • Variable Speed                      │
│  • Pause Times                         │
└────────────────────────────────────────┘
```

### 3. Swarm Coordinator (`swarm.py`)

Manages the collection of nodes:

```
┌────────────────────────────────────────┐
│           Swarm Coordinator            │
├────────────────────────────────────────┤
│  • Node Creation & Management          │
│  • Gossip Protocol Execution           │
│  • Metrics Collection                  │
│  • Message Tracking                    │
│                                        │
│  Node Placement Patterns:              │
│  • Random Distribution                 │
│  • Grid Layout                         │
│  • Clustered Groups                    │
└────────────────────────────────────────┘
```

### 4. Gateway (`gateway/`)

Optional cloud bridge for external integration:

```
┌────────────────────────────────────────┐
│              Go Gateway                │
├────────────────────────────────────────┤
│  REST API Endpoints:                   │
│  • POST /inject  - Inject messages     │
│  • GET  /status  - Gateway status      │
│  • GET  /messages - Retrieve messages  │
│  • GET  /health  - Health check        │
│                                        │
│  Features:                             │
│  • Thread-safe storage                 │
│  • Pagination support                  │
│  • CORS enabled                        │
└────────────────────────────────────────┘
```

## Message Flow

### Standard Message Envelope

```json
{
  "id": "uuid-v4",
  "from": "node_001",
  "to": "node_002",
  "ttl": 10,
  "seq": 42,
  "urgency": 3,
  "payload": {
    "temperature": 23.5,
    "humidity": 65
  },
  "timestamp": "2026-02-03T10:30:00Z"
}
```

### Gossip Protocol Flow

```
1. Node A creates message
       │
       ▼
2. Message queued in outbox
       │
       ▼
3. Gossip round executes
       │
       ▼
4. Message sent to all neighbors
       │
       ▼
5. Network applies conditions
   (loss/delay)
       │
       ▼
6. Surviving messages reach neighbors
       │
       ▼
7. Neighbors process & forward
   (TTL decremented)
       │
       ▼
8. Process repeats until:
   - Message reaches destination
   - TTL expires
   - All paths exhausted
```

## Network Simulation Details

### Packet Loss Model

```python
# Bernoulli model
if random.random() < packet_loss_probability:
    drop_packet()
else:
    deliver_packet()
```

### Delay Model

```python
# Uniform distribution
delay = random.uniform(min_delay, max_delay)
await asyncio.sleep(delay)
```

### Partition Model

```
Before Partition:
┌───────────────────────────────┐
│  A ── B ── C ── D ── E       │
└───────────────────────────────┘

After Partition:
┌─────────────┐   ┌─────────────┐
│  A ── B ── C│   │D ── E       │
└─────────────┘   └─────────────┘
  Partition 1       Partition 2
```

### Mobility Model (Random Waypoint)

```
1. Choose random destination
2. Move towards destination at random speed
3. Arrive at destination
4. Pause for random duration
5. Repeat from step 1
```

## Data Flow Architecture

```
┌────────────┐     ┌────────────┐     ┌────────────┐
│  Scenario  │────►│  Simulator │────►│  Results   │
│   Config   │     │            │     │   (CSV)    │
└────────────┘     └────────────┘     └────────────┘
                          │
                          │
              ┌───────────┼───────────┐
              │           │           │
              ▼           ▼           ▼
         ┌────────┐  ┌────────┐  ┌────────┐
         │ Swarm  │  │Network │  │ Plots  │
         └────────┘  └────────┘  └────────┘
              │           │
              │           │
              ▼           ▼
         ┌────────────────────┐
         │   Virtual Nodes    │
         └────────────────────┘
```

## Scalability Considerations

| Scale | Nodes | Recommendations |
|-------|-------|-----------------|
| Small | 10-50 | Default settings |
| Medium | 50-200 | Increase gossip interval |
| Large | 200-1000 | Reduce message rate |
| Very Large | 1000+ | Use clustering, optimize TTL |

## Performance Tuning

### Memory Usage
- Each node: ~10KB base + message queue
- Network: ~100 bytes per connection
- Messages: ~500 bytes average

### CPU Usage
- Gossip rounds: O(N × M × K)
  - N = nodes
  - M = messages
  - K = neighbors

### Optimization Tips
1. Use lower TTL for large networks
2. Increase gossip interval for CPU savings
3. Limit message queue sizes
4. Use partitions strategically for testing
