"""
plots.py - Visualization Utilities

Provides plotting functions for analyzing simulation results.
"""

import csv
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not available. Plotting functions disabled.")

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


def check_matplotlib():
    """Check if matplotlib is available."""
    if not MATPLOTLIB_AVAILABLE:
        raise ImportError("matplotlib is required for plotting. Install with: pip install matplotlib")


def plot_network_topology(
    nodes: List[Dict[str, Any]],
    connections: Dict[str, List[str]],
    title: str = "Network Topology",
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 10)
):
    """
    Plot the network topology showing nodes and their connections.
    
    Args:
        nodes: List of node dictionaries with 'node_id' and 'position' keys
        connections: Dictionary mapping node_id to list of neighbor node_ids
        title: Plot title
        save_path: Optional path to save the figure
        figsize: Figure size
    """
    check_matplotlib()
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # Create position lookup
    positions = {
        node['node_id']: (node['position']['x'], node['position']['y'])
        for node in nodes
    }
    
    # Draw connections
    for node_id, neighbors in connections.items():
        if node_id not in positions:
            continue
        x1, y1 = positions[node_id]
        for neighbor_id in neighbors:
            if neighbor_id in positions:
                x2, y2 = positions[neighbor_id]
                ax.plot([x1, x2], [y1, y2], 'b-', alpha=0.2, linewidth=0.5)
    
    # Draw nodes
    xs = [pos[0] for pos in positions.values()]
    ys = [pos[1] for pos in positions.values()]
    ax.scatter(xs, ys, c='red', s=50, zorder=5, edgecolors='black')
    
    # Label nodes
    for node_id, (x, y) in positions.items():
        ax.annotate(node_id[-3:], (x, y), fontsize=6, ha='center', va='bottom')
    
    ax.set_xlabel('X Position')
    ax.set_ylabel('Y Position')
    ax.set_title(title)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved topology plot to {save_path}")
    
    plt.tight_layout()
    return fig, ax


def plot_delivery_over_time(
    timestamps: List[float],
    delivery_counts: List[int],
    title: str = "Message Delivery Over Time",
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 6)
):
    """
    Plot message delivery count over time.
    
    Args:
        timestamps: List of timestamps (seconds from start)
        delivery_counts: Cumulative delivery counts at each timestamp
        title: Plot title
        save_path: Optional path to save the figure
        figsize: Figure size
    """
    check_matplotlib()
    
    fig, ax = plt.subplots(figsize=figsize)
    
    ax.plot(timestamps, delivery_counts, 'b-', linewidth=2)
    ax.fill_between(timestamps, 0, delivery_counts, alpha=0.3)
    
    ax.set_xlabel('Time (seconds)')
    ax.set_ylabel('Messages Delivered')
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved delivery plot to {save_path}")
    
    plt.tight_layout()
    return fig, ax


def plot_node_statistics(
    node_stats: List[Dict[str, Any]],
    metric: str = 'received',
    title: Optional[str] = None,
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 6)
):
    """
    Plot a histogram of node statistics.
    
    Args:
        node_stats: List of node statistics dictionaries
        metric: Which metric to plot ('sent', 'received', 'forwarded', 'dropped', 'delivered')
        title: Plot title
        save_path: Optional path to save the figure
        figsize: Figure size
    """
    check_matplotlib()
    
    values = [stat.get(metric, stat.get('stats', {}).get(metric, 0)) for stat in node_stats]
    node_ids = [stat['node_id'][-3:] for stat in node_stats]
    
    fig, ax = plt.subplots(figsize=figsize)
    
    bars = ax.bar(range(len(values)), values, color='steelblue', edgecolor='black')
    
    ax.set_xlabel('Node')
    ax.set_ylabel(f'Messages {metric.capitalize()}')
    ax.set_title(title or f'Messages {metric.capitalize()} per Node')
    
    # Set x-axis labels (show every nth label for readability)
    n = max(1, len(node_ids) // 20)
    ax.set_xticks(range(0, len(node_ids), n))
    ax.set_xticklabels([node_ids[i] for i in range(0, len(node_ids), n)], rotation=45)
    
    ax.grid(True, alpha=0.3, axis='y')
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved node stats plot to {save_path}")
    
    plt.tight_layout()
    return fig, ax


def plot_comparison(
    results: List[Dict[str, Any]],
    x_key: str,
    y_key: str,
    title: str = "Comparison",
    xlabel: Optional[str] = None,
    ylabel: Optional[str] = None,
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 6)
):
    """
    Plot a comparison of multiple experiment results.
    
    Args:
        results: List of experiment result dictionaries
        x_key: Key for x-axis values
        y_key: Key for y-axis values
        title: Plot title
        xlabel: X-axis label
        ylabel: Y-axis label
        save_path: Optional path to save the figure
        figsize: Figure size
    """
    check_matplotlib()
    
    x_values = [r.get(x_key, 0) for r in results]
    y_values = [r.get(y_key, 0) for r in results]
    
    fig, ax = plt.subplots(figsize=figsize)
    
    ax.plot(x_values, y_values, 'bo-', linewidth=2, markersize=8)
    
    ax.set_xlabel(xlabel or x_key.replace('_', ' ').title())
    ax.set_ylabel(ylabel or y_key.replace('_', ' ').title())
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved comparison plot to {save_path}")
    
    plt.tight_layout()
    return fig, ax


def plot_heatmap(
    data: List[List[float]],
    row_labels: List[str],
    col_labels: List[str],
    title: str = "Heatmap",
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 8)
):
    """
    Plot a heatmap visualization.
    
    Args:
        data: 2D array of values
        row_labels: Labels for rows
        col_labels: Labels for columns
        title: Plot title
        save_path: Optional path to save the figure
        figsize: Figure size
    """
    check_matplotlib()
    
    fig, ax = plt.subplots(figsize=figsize)
    
    im = ax.imshow(data, cmap='YlOrRd', aspect='auto')
    
    ax.set_xticks(range(len(col_labels)))
    ax.set_yticks(range(len(row_labels)))
    ax.set_xticklabels(col_labels, rotation=45, ha='right')
    ax.set_yticklabels(row_labels)
    
    plt.colorbar(im, ax=ax)
    ax.set_title(title)
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved heatmap to {save_path}")
    
    plt.tight_layout()
    return fig, ax


def plot_partition_experiment(
    before_partition: Dict[str, Any],
    during_partition: Dict[str, Any],
    after_healing: Dict[str, Any],
    title: str = "Partition Experiment Results",
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 6)
):
    """
    Plot results from a partition experiment showing delivery ratio at different phases.
    
    Args:
        before_partition: Results before partition
        during_partition: Results during partition
        after_healing: Results after partition heals
        title: Plot title
        save_path: Optional path to save the figure
        figsize: Figure size
    """
    check_matplotlib()
    
    phases = ['Before Partition', 'During Partition', 'After Healing']
    delivery_ratios = [
        before_partition.get('delivery_ratio', 0),
        during_partition.get('delivery_ratio', 0),
        after_healing.get('delivery_ratio', 0)
    ]
    
    fig, ax = plt.subplots(figsize=figsize)
    
    colors = ['green', 'red', 'blue']
    bars = ax.bar(phases, delivery_ratios, color=colors, edgecolor='black')
    
    ax.set_ylabel('Delivery Ratio')
    ax.set_title(title)
    ax.set_ylim(0, 1.1)
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for bar, val in zip(bars, delivery_ratios):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
               f'{val:.1%}', ha='center', va='bottom', fontsize=12)
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved partition plot to {save_path}")
    
    plt.tight_layout()
    return fig, ax


def load_results_csv(filepath: str) -> Dict[str, Any]:
    """Load experiment results from a CSV file."""
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert numeric values
            result = {}
            for key, value in row.items():
                try:
                    if '.' in value:
                        result[key] = float(value)
                    else:
                        result[key] = int(value)
                except (ValueError, TypeError):
                    result[key] = value
            return result
    return {}


def load_node_stats_csv(filepath: str) -> List[Dict[str, Any]]:
    """Load node statistics from a CSV file."""
    stats = []
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stat = {}
            for key, value in row.items():
                try:
                    if '.' in value:
                        stat[key] = float(value)
                    else:
                        stat[key] = int(value)
                except (ValueError, TypeError):
                    stat[key] = value
            stats.append(stat)
    return stats


def generate_report(
    results_dir: str,
    output_file: str = "report.html"
):
    """
    Generate an HTML report from experiment results.
    
    Args:
        results_dir: Directory containing CSV result files
        output_file: Output HTML file path
    """
    results_path = Path(results_dir)
    csv_files = list(results_path.glob("*.csv"))
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>P2P Swarm Simulation Report</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            h1 { color: #333; }
            table { border-collapse: collapse; width: 100%; margin: 20px 0; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #4CAF50; color: white; }
            tr:nth-child(even) { background-color: #f2f2f2; }
            .metric { font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>P2P Swarm Simulation Report</h1>
        <p>Generated: """ + datetime.now().isoformat() + """</p>
    """
    
    for csv_file in csv_files:
        if '.nodes.' in csv_file.name:
            continue
        
        result = load_results_csv(str(csv_file))
        if not result:
            continue
        
        html += f"""
        <h2>{result.get('experiment_name', csv_file.stem)}</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
        """
        
        for key, value in result.items():
            if isinstance(value, float):
                if 'ratio' in key or 'rate' in key:
                    value = f"{value:.2%}"
                else:
                    value = f"{value:.2f}"
            html += f"<tr><td class='metric'>{key.replace('_', ' ').title()}</td><td>{value}</td></tr>"
        
        html += "</table>"
    
    html += """
    </body>
    </html>
    """
    
    output_path = results_path / output_file
    with open(output_path, 'w') as f:
        f.write(html)
    
    print(f"Report generated: {output_path}")


if __name__ == "__main__":
    # Demo plotting
    if MATPLOTLIB_AVAILABLE:
        # Create sample data
        sample_nodes = [
            {'node_id': f'node_{i:03d}', 'position': {'x': i * 100 % 500, 'y': i * 100 // 500 * 100}}
            for i in range(25)
        ]
        
        sample_connections = {
            node['node_id']: [sample_nodes[(i+1) % 25]['node_id'], sample_nodes[(i-1) % 25]['node_id']]
            for i, node in enumerate(sample_nodes)
        }
        
        fig, ax = plot_network_topology(sample_nodes, sample_connections, title="Sample Network")
        plt.show()
    else:
        print("Matplotlib not available for demo")
