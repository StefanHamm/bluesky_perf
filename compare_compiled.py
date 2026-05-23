import numpy as np
import argparse
import time
from pathlib import Path
import bluesky as bs


def setup_benchmark_scenario(n_aircraft: int, scenario_seed: int = 42):
    """
    Setup a complex, repeatable benchmark scenario with multiple aircraft.
    
    Args:
        n_aircraft: Number of aircraft to create
        scenario_seed: Random seed for reproducibility
    
    Returns:
        Dictionary with scenario information
    """
    np.random.seed(scenario_seed)
    
    # Define airspace bounds
    lat_min, lat_max = 50.0, 52.0
    lon_min, lon_max = 4.0, 6.0
    alt_min, alt_max = 1000, 35000  # feet
    
    aircraft_config = []
    
    for i in range(n_aircraft):
        # Vary aircraft positions across the airspace
        lat = np.random.uniform(lat_min, lat_max)
        lon = np.random.uniform(lon_min, lon_max)
        
        # Vary altitudes
        alt = np.random.uniform(alt_min, alt_max)
        
        # Vary speeds (typical cruise speed 450 knots +/- variation)
        heading = np.random.uniform(0, 360)
        speed = np.random.uniform(300, 500)  # knots
        
        # Vary vertical speeds for climb/descent
        vs = np.random.choice([-500, -300, -100, 0, 100, 300, 500])  # fpm
        
        # Target altitude (for climb/descent operations)
        target_alt = np.random.choice([5000, 10000, 15000, 25000, 35000])
        
        aircraft_config.append({
            'callsign': f'AC{i:04d}',
            'lat': lat,
            'lon': lon,
            'alt': alt,
            'heading': heading,
            'speed': speed,
            'vs': vs,
            'target_alt': target_alt,
            'index': i
        })
    
    return aircraft_config


def create_scenario_commands(aircraft_config: list) -> list:
    """
    Generate BlueSky commands to create and configure the scenario.
    
    Args:
        aircraft_config: List of aircraft configuration dictionaries
    
    Returns:
        List of command strings for BlueSky
    """
    commands = []
    
    # Clear any existing traffic
    commands.append('RESET')
    
    # Set simulation speed (realtime)
    commands.append('SIMSPEED 1')
    
    # Create all aircraft
    for ac in aircraft_config:
        # Create aircraft: CRE callsign lat lon alt speed heading
        cmd = (f"CRE {ac['callsign']} {ac['lat']:.4f} {ac['lon']:.4f} "
               f"{ac['alt']:.0f} {ac['heading']:.1f} {ac['speed']:.1f}")
        commands.append(cmd)
    
    # Add vertical speed and target altitude changes for variety
    for i, ac in enumerate(aircraft_config):
        if ac['vs'] != 0:
            # Use VS command to set vertical speed
            commands.append(f"VS {ac['callsign']} {ac['vs']:.0f}")
        
        # Set target altitude for some aircraft (every 3rd aircraft)
        if i % 3 == 0 and ac['target_alt'] != ac['alt']:
            commands.append(f"ALT {ac['callsign']} {ac['target_alt']:.0f}")
    
    return commands


def run_benchmark(n_aircraft: int = 100, n_steps: int = 1000,
                  scenario_seed: int = 42, verbose: bool = True,
                  configfile: str | None = None):
    """
    Run the benchmark simulation.
    
    Args:
        n_aircraft: Number of aircraft in scenario
        n_steps: Number of simulation steps to run
        scenario_seed: Random seed for reproducibility
        verbose: Print progress information
        configfile: Optional BlueSky config file to load instead of the default settings.cfg
    
    Returns:
        Dictionary with timing and performance metrics
    """
    if verbose:
        print(f"=== BlueSky Benchmark ===")
        print(f"Aircraft: {n_aircraft}")
        print(f"Steps: {n_steps}")
        print(f"Seed: {scenario_seed}")
        print()
    
    # Setup scenario
    if verbose:
        print("Setting up scenario...")
    aircraft_config = setup_benchmark_scenario(n_aircraft, scenario_seed)
    commands = create_scenario_commands(aircraft_config)

    if configfile:
        configfile = str(Path(configfile).expanduser().resolve())
    
    # Initialize BlueSky
    if verbose:
        print("Initializing BlueSky...")
    if configfile and verbose:
        print(f"Using config file: {configfile}")
    bs.init(mode='sim', configfile=configfile)
    
    # Execute setup commands
    if verbose:
        print("Creating aircraft...")
    for cmd in commands:
        bs.stack.stack(cmd)
    
    # Run simulation
    if verbose:
        print("Running simulation...")
    
    start_time = time.perf_counter()
    
    for step in range(n_steps):
        # Update simulation
        bs.sim.step()
        
        # Apply some dynamic changes every 100 steps for variety
        if step % 100 == 0 and step > 0:
            # Change some aircraft speeds/headings
            for i in range(0, min(10, n_aircraft)):
                ac_idx = (step // 100 + i) % n_aircraft
                ac = aircraft_config[ac_idx]
                new_speed = np.random.uniform(300, 500)
                new_heading = np.random.uniform(0, 360)
                bs.stack.stack(f"SPD {ac['callsign']} {new_speed:.1f}")
                bs.stack.stack(f"HDG {ac['callsign']} {new_heading:.1f}")
        
        if verbose and (step + 1) % max(100, n_steps // 10) == 0:
            print(f"  Step {step + 1}/{n_steps}")
    
    end_time = time.perf_counter()
    elapsed = end_time - start_time
    
    # Calculate metrics
    metrics = {
        'n_aircraft': n_aircraft,
        'n_steps': n_steps,
        'total_time': elapsed,
        'time_per_step': elapsed / n_steps,
        'time_per_aircraft_step': elapsed / (n_aircraft * n_steps),
        'steps_per_second': n_steps / elapsed,
        'scenario_seed': scenario_seed,
    }
    
    if verbose:
        print()
        print("=== Results ===")
        print(f"Total time: {metrics['total_time']:.4f}s")
        print(f"Time per step: {metrics['time_per_step']:.6f}s")
        print(f"Time per aircraft-step: {metrics['time_per_aircraft_step']:.9f}s")
        print(f"Simulation steps/sec: {metrics['steps_per_second']:.2f}")
    
    return metrics


def main():
    parser = argparse.ArgumentParser(
        description='BlueSky Benchmark: Complex repeatable scenario for profiling'
    )
    parser.add_argument('--aircraft', '-a', type=int, default=100,
                        help='Number of aircraft (default: 100)')
    parser.add_argument('--steps', '-s', type=int, default=1000,
                        help='Number of simulation steps (default: 1000)')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed for reproducibility (default: 42)')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress verbose output')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output file for metrics (CSV format)')
    parser.add_argument('--config', '-c', type=str, default=None,
                        help='BlueSky config file to load, e.g. a settings.cfg with uncompiled geo functions')
    
    args = parser.parse_args()
    
    # Run benchmark
    metrics = run_benchmark(
        n_aircraft=args.aircraft,
        n_steps=args.steps,
        scenario_seed=args.seed,
        verbose=not args.quiet,
        configfile=args.config
    )
    
    # Save metrics if requested
    if args.output:
        import csv
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if file exists to append or create
        file_exists = output_path.exists()
        
        with open(output_path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=metrics.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(metrics)
        
        if not args.quiet:
            print(f"Metrics saved to {output_path}")
    
    return metrics


if __name__ == '__main__':
    main() 