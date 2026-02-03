# P2P-Swarm-Model

## Software-Only Peer-to-Peer Swarm Communication Network Simulator

[![CI](https://github.com/yourusername/P2P-Swarm-Model/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/P2P-Swarm-Model/actions/workflows/ci.yml)

### 🎯 What This Is

This is a **fully simulated, software-only** distributed swarm model that behaves like real IoT networks:

- **Nodes are virtual** — Python processes or asyncio tasks
- **Networks are simulated** — No Bluetooth, LoRa, or Wi-Fi required
- **Runs anywhere** — Normal laptop, cloud server, or container
- **Purpose** — Research, teaching, and experimentation

### ⚠️ Important

This is **NOT** for real hardware devices. Everything runs in software simulation.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Go 1.21+ (optional, for gateway)
- Docker & Docker Compose (optional)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/P2P-Swarm-Model.git
cd P2P-Swarm-Model

# Install Python dependencies
pip install -r requirements.txt

# Run the simulator
cd sim
python simulator.py
```

### Run with Docker

```bash
docker-compose up --build
```

---

## 📁 Project Structure

```
P2P-Swarm-Model/
│
├── README.md                 # This file
├── docker-compose.yml        # Container orchestration
├── requirements.txt          # Python dependencies
├── .github/workflows/ci.yml  # CI/CD pipeline
│
├── gateway/                  # Go-based cloud bridge (optional)
│   ├── main.go
│   ├── router.go
│   ├── storage.go
│   └── Dockerfile
│
├── sim/                      # Python simulator (main)
│   ├── node.py              # Virtual IoT device
│   ├── network.py           # Simulated wireless network
│   ├── swarm.py             # Swarm coordinator
│   ├── simulator.py         # Main experiment runner
│   ├── plots.py             # Visualization
│   └── scenarios/           # Pre-built experiments
│       ├── partition_test.py
│       └── mobility_test.py
│
└── docs/                     # Documentation
    ├── architecture.md
    └── experiments.md
```

---

## 🔬 Running Experiments

### Basic Simulation

```bash
cd sim
python simulator.py --nodes 50 --packet-loss 0.3 --runtime 300
```

### Partition Test

```bash
python -m scenarios.partition_test
```

### Mobility Test

```bash
python -m scenarios.mobility_test
```

### Output

Results are saved to `results/` as CSV files:
- `delivery_ratio` — Percentage of messages delivered
- `average_delay` — Mean time to delivery
- `messages_dropped` — Count of lost messages

---

## 🌐 Gateway (Optional)

The Go gateway acts as a "super-node" cloud bridge:

```bash
cd gateway
go run .

# Or with Docker
docker build -t p2p-gateway .
docker run -p 8080:8080 p2p-gateway
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/inject` | Inject a message into the swarm |
| GET | `/status` | Get gateway status |
| GET | `/messages` | Retrieve stored messages |

---

## 📊 Message Format

All messages use this envelope:

```json
{
  "id": "uuid-v4",
  "from": "node_001",
  "to": "node_002",
  "ttl": 10,
  "seq": 42,
  "urgency": 3,
  "payload": {"temperature": 23.5},
  "timestamp": "2026-02-03T10:30:00Z"
}
```

---

## 📚 Documentation

- [Architecture Overview](docs/architecture.md)
- [Running Experiments](docs/experiments.md)

---

## 🧪 Testing

```bash
# Run Python tests
cd sim
python -m pytest tests/

# Run Go tests
cd gateway
go test ./...
```

---

## 📄 License

MIT License — See LICENSE file for details.

---

## 🤝 Contributing

Contributions welcome! Please read the contributing guidelines first.
