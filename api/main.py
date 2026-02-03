#!/usr/bin/env python3
"""
main.py - FastAPI Server for P2P Swarm Model

Provides REST API endpoints for:
- Running simulations
- Viewing network status
- Getting simulation results
"""

import os
import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from sim.node import Node, Message, Position, Urgency
from sim.network import SimulatedNetwork, NetworkConfig, NetworkCondition
from sim.swarm import Swarm, SwarmConfig

# ============== Models ==============

class SimulationConfig(BaseModel):
    """Configuration for a simulation run."""
    num_nodes: int = Field(default=20, ge=2, le=200, description="Number of nodes")
    packet_loss: float = Field(default=0.1, ge=0.0, le=1.0, description="Packet loss rate")
    runtime_seconds: float = Field(default=10.0, ge=1.0, le=300.0, description="Simulation runtime")
    world_size: float = Field(default=500.0, ge=100.0, le=2000.0, description="World size")
    communication_range: float = Field(default=100.0, ge=10.0, le=500.0, description="Node communication range")
    enable_mobility: bool = Field(default=False, description="Enable node mobility")


class MessagePayload(BaseModel):
    """Payload for injecting a message."""
    from_node: Optional[str] = None
    to_node: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    urgency: int = Field(default=2, ge=0, le=5)


class SimulationStatus(BaseModel):
    """Status of a simulation."""
    id: str
    status: str  # "running", "completed", "failed"
    progress: float
    started_at: str
    completed_at: Optional[str] = None
    config: SimulationConfig
    results: Optional[Dict[str, Any]] = None


# ============== App State ==============

class AppState:
    def __init__(self):
        self.simulations: Dict[str, SimulationStatus] = {}
        self.current_swarm: Optional[Swarm] = None
        self.current_network: Optional[SimulatedNetwork] = None
        self.demo_nodes: Dict[str, Node] = {}
        
    def init_demo_network(self, num_nodes: int = 10):
        """Initialize a demo network for quick testing."""
        config = NetworkConfig(
            packet_loss=0.1,
            min_delay_ms=10.0,
            max_delay_ms=50.0,
            communication_range=150.0,
            world_width=500.0,
            world_height=500.0
        )
        self.current_network = SimulatedNetwork(config)
        
        # Create nodes in a grid
        import random
        self.demo_nodes = {}
        for i in range(num_nodes):
            node = Node(
                f"node_{i:03d}",
                position=Position(
                    x=random.uniform(0, 500),
                    y=random.uniform(0, 500)
                ),
                communication_range=150.0
            )
            self.demo_nodes[node.node_id] = node
            self.current_network.register_node(node)
        
        self.current_network.update_neighbors()


app_state = AppState()


# ============== Lifespan ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app_state.init_demo_network(10)
    print("🚀 P2P Swarm Model API started")
    print(f"📡 Demo network initialized with {len(app_state.demo_nodes)} nodes")
    yield
    # Shutdown
    print("👋 P2P Swarm Model API shutting down")


# ============== FastAPI App ==============

app = FastAPI(
    title="P2P Swarm Model API",
    description="""
    REST API for the P2P Swarm Communication Network Simulator.
    
    This is a **software-only simulation** of peer-to-peer IoT networks.
    No physical hardware required!
    
    ## Features
    - Create and manage virtual IoT nodes
    - Simulate network conditions (packet loss, delays, partitions)
    - Run experiments and collect metrics
    - Inject messages and observe propagation
    """,
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ============== Endpoints ==============

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web UI."""
    html_file = Path(__file__).parent.parent / "static" / "index.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(), status_code=200)
    else:
        return HTMLResponse(content="""
        <html>
            <head><title>P2P Swarm Model</title></head>
            <body>
                <h1>P2P Swarm Model API</h1>
                <p>API is running. Visit <a href="/docs">/docs</a> for API documentation.</p>
            </body>
        </html>
        """, status_code=200)


@app.get("/api")
async def api_info():
    """API information endpoint."""
    return {
        "name": "P2P Swarm Model API",
        "version": "1.0.0",
        "status": "running",
        "description": "Software-only P2P IoT network simulator",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "nodes": "/api/nodes",
            "network": "/api/network/status",
            "simulate": "/api/simulate"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "demo_nodes": len(app_state.demo_nodes)
    }


# ============== Node Endpoints ==============

@app.get("/api/nodes")
async def list_nodes():
    """List all nodes in the demo network."""
    nodes = []
    for node_id, node in app_state.demo_nodes.items():
        nodes.append({
            "node_id": node.node_id,
            "position": {"x": node.position.x, "y": node.position.y},
            "neighbors": list(node.neighbors),
            "stats": {
                "messages_sent": node.stats.messages_sent,
                "messages_received": node.stats.messages_received,
                "messages_delivered": node.stats.messages_delivered
            }
        })
    return {"count": len(nodes), "nodes": nodes}


@app.get("/api/nodes/{node_id}")
async def get_node(node_id: str):
    """Get details of a specific node."""
    if node_id not in app_state.demo_nodes:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    
    node = app_state.demo_nodes[node_id]
    return {
        "node_id": node.node_id,
        "position": {"x": node.position.x, "y": node.position.y},
        "communication_range": node.communication_range,
        "neighbors": list(node.neighbors),
        "stats": {
            "messages_sent": node.stats.messages_sent,
            "messages_received": node.stats.messages_received,
            "messages_forwarded": node.stats.messages_forwarded,
            "messages_dropped": node.stats.messages_dropped,
            "messages_delivered": node.stats.messages_delivered
        }
    }


@app.post("/api/nodes/reset")
async def reset_nodes(num_nodes: int = 10):
    """Reset the demo network with new nodes."""
    if num_nodes < 2 or num_nodes > 100:
        raise HTTPException(status_code=400, detail="num_nodes must be between 2 and 100")
    
    app_state.init_demo_network(num_nodes)
    return {
        "status": "reset",
        "num_nodes": len(app_state.demo_nodes),
        "message": f"Demo network reset with {num_nodes} nodes"
    }


# ============== Network Endpoints ==============

@app.get("/api/network/status")
async def network_status():
    """Get current network status."""
    if not app_state.current_network:
        raise HTTPException(status_code=500, detail="Network not initialized")
    
    net = app_state.current_network
    
    # Calculate connectivity
    total_connections = sum(len(node.neighbors) for node in app_state.demo_nodes.values())
    
    return {
        "status": "active",
        "config": {
            "packet_loss": net.config.packet_loss,
            "min_delay_ms": net.config.min_delay_ms,
            "max_delay_ms": net.config.max_delay_ms,
            "communication_range": net.config.communication_range,
            "world_size": {
                "width": net.config.world_width,
                "height": net.config.world_height
            }
        },
        "nodes": len(app_state.demo_nodes),
        "total_connections": total_connections,
        "partitions": len(net._partitions),
        "statistics": {
            "total_transmissions": net._total_transmissions,
            "successful_transmissions": net._successful_transmissions,
            "dropped_packets": net._dropped_packets
        }
    }


@app.post("/api/network/partition")
async def create_partition(group1: List[str], group2: List[str]):
    """Create a network partition between two groups of nodes."""
    if not app_state.current_network:
        raise HTTPException(status_code=500, detail="Network not initialized")
    
    # Validate node IDs
    all_nodes = set(app_state.demo_nodes.keys())
    for node_id in group1 + group2:
        if node_id not in all_nodes:
            raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    
    app_state.current_network.set_partitions_by_groups([set(group1), set(group2)])
    
    return {
        "status": "partitioned",
        "group1": group1,
        "group2": group2,
        "message": "Network partitioned into two isolated groups"
    }


@app.post("/api/network/heal")
async def heal_partition():
    """Heal all network partitions."""
    if not app_state.current_network:
        raise HTTPException(status_code=500, detail="Network not initialized")
    
    app_state.current_network.clear_partitions()
    
    return {
        "status": "healed",
        "message": "All network partitions removed"
    }


# ============== Message Endpoints ==============

@app.post("/api/messages/inject")
async def inject_message(payload: MessagePayload):
    """Inject a message into the network."""
    if not app_state.demo_nodes:
        raise HTTPException(status_code=500, detail="No nodes available")
    
    # Select source node
    if payload.from_node:
        if payload.from_node not in app_state.demo_nodes:
            raise HTTPException(status_code=404, detail=f"Node {payload.from_node} not found")
        source_node = app_state.demo_nodes[payload.from_node]
    else:
        import random
        source_node = random.choice(list(app_state.demo_nodes.values()))
    
    # Create and send message
    message = source_node.create_message(
        payload=payload.payload,
        to_node=payload.to_node,
        urgency=payload.urgency
    )
    
    await source_node.send(message)
    
    return {
        "status": "injected",
        "message_id": message.id,
        "from_node": source_node.node_id,
        "to_node": payload.to_node,
        "timestamp": message.timestamp
    }


# ============== Simulation Endpoints ==============

@app.post("/api/simulate")
async def run_simulation(config: SimulationConfig, background_tasks: BackgroundTasks):
    """Start a new simulation (runs in background)."""
    sim_id = str(uuid.uuid4())[:8]
    
    status = SimulationStatus(
        id=sim_id,
        status="running",
        progress=0.0,
        started_at=datetime.utcnow().isoformat() + "Z",
        config=config
    )
    
    app_state.simulations[sim_id] = status
    
    # Run simulation in background
    background_tasks.add_task(run_simulation_task, sim_id, config)
    
    return {
        "simulation_id": sim_id,
        "status": "started",
        "message": "Simulation started in background",
        "check_status": f"/api/simulate/{sim_id}"
    }


async def run_simulation_task(sim_id: str, config: SimulationConfig):
    """Background task to run simulation."""
    import random
    
    status = app_state.simulations[sim_id]
    
    try:
        # Create network
        net_config = NetworkConfig(
            packet_loss=config.packet_loss,
            min_delay_ms=10.0,
            max_delay_ms=50.0,
            communication_range=config.communication_range,
            world_width=config.world_size,
            world_height=config.world_size,
            mobility_enabled=config.enable_mobility
        )
        network = SimulatedNetwork(net_config)
        
        # Create nodes
        nodes = []
        for i in range(config.num_nodes):
            node = Node(
                f"sim_{sim_id}_node_{i:03d}",
                position=Position(
                    x=random.uniform(0, config.world_size),
                    y=random.uniform(0, config.world_size)
                ),
                communication_range=config.communication_range
            )
            nodes.append(node)
            network.register_node(node)
        
        network.update_neighbors()
        
        # Simulate message passing
        messages_sent = 0
        messages_delivered = 0
        
        steps = int(config.runtime_seconds * 10)  # 10 steps per second
        for step in range(steps):
            # Update progress
            status.progress = (step + 1) / steps
            
            # Random node sends a message
            if random.random() < 0.3:  # 30% chance per step
                sender = random.choice(nodes)
                receiver = random.choice(nodes)
                if sender != receiver:
                    msg = sender.create_message(
                        payload={"step": step, "data": "test"},
                        to_node=receiver.node_id
                    )
                    await sender.send(msg)
                    messages_sent += 1
                    
                    # Simulate delivery through neighbors
                    if receiver.node_id in sender.neighbors:
                        result = await network.transmit(msg, sender.node_id, receiver.node_id)
                        if result.success:
                            messages_delivered += 1
            
            # Small delay to simulate time passing
            await asyncio.sleep(0.01)
        
        # Calculate results
        delivery_ratio = messages_delivered / messages_sent if messages_sent > 0 else 0
        
        status.status = "completed"
        status.completed_at = datetime.utcnow().isoformat() + "Z"
        status.results = {
            "messages_sent": messages_sent,
            "messages_delivered": messages_delivered,
            "delivery_ratio": round(delivery_ratio, 4),
            "total_transmissions": network._total_transmissions,
            "packets_dropped": network._dropped_packets,
            "nodes": config.num_nodes,
            "runtime_seconds": config.runtime_seconds
        }
        
    except Exception as e:
        status.status = "failed"
        status.results = {"error": str(e)}


@app.get("/api/simulate/{sim_id}")
async def get_simulation_status(sim_id: str):
    """Get status of a simulation."""
    if sim_id not in app_state.simulations:
        raise HTTPException(status_code=404, detail=f"Simulation {sim_id} not found")
    
    status = app_state.simulations[sim_id]
    return {
        "id": status.id,
        "status": status.status,
        "progress": round(status.progress * 100, 1),
        "started_at": status.started_at,
        "completed_at": status.completed_at,
        "config": status.config.dict(),
        "results": status.results
    }


@app.get("/api/simulations")
async def list_simulations():
    """List all simulations."""
    return {
        "count": len(app_state.simulations),
        "simulations": [
            {
                "id": s.id,
                "status": s.status,
                "progress": round(s.progress * 100, 1),
                "started_at": s.started_at
            }
            for s in app_state.simulations.values()
        ]
    }


# ============== Main ==============

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
