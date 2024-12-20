import numpy as np
from scipy.optimize import minimize
import matplotlib.pyplot as plt
import networkx as nx
import argparse
import matplotlib.animation as animation


def main():
    parser = argparse.ArgumentParser(description='Trajectory Optimization with Extra Constraints')
    parser.add_argument('--start', nargs=2, type=float, default=[0.0, 0.0], help='Start position (x y)')
    parser.add_argument('--goal', nargs=2, type=float, default=[5.0, 5.0], help='Goal position (x y)')
    parser.add_argument('--T', type=int, default=50, help='Number of time steps')
    parser.add_argument('--x0', nargs=2, type=float, default=[-1.0, 2.0], help='Intermediate state 1 (x y)')
    parser.add_argument('--x1', nargs=2, type=float, default=[3.0, 7.0], help='Intermediate state 2 (x y)')
    args = parser.parse_args()


    dt = 0.1  # Time step
    T = args.T
    start = np.array(args.start)
    goal = np.array(args.goal)
    x0_in = np.array(args.x0)
    x1_in = np.array(args.x1)

    class FactorGraph:
        def __init__(self, T, start, goal, dt):
            self.T = T
            self.start = start
            self.goal = goal
            self.dt = dt
            self.num_states = T + 1
            self.num_controls = T
            self.factors = []

        def add_factor(self, factor):
            self.factors.append(factor)

        def compute_total_cost(self, variables):
            q = variables[:self.num_states * 2].reshape(self.num_states, 2)
            u = variables[self.num_states * 2:].reshape(self.num_controls, 2)
            total_cost = 0
            for factor in self.factors:
                total_cost += factor(q, u)
            return total_cost

    def dynamics_factor(dt, t):
        """Dynamics factor: Enforces q_{t+1} = q_t + u_t * dt."""
        def factor(q, u):
            q_t = q[t]
            q_t1 = q[t + 1]
            u_t = u[t]
            dynamics_residual = q_t1 - (q_t + u_t * dt)
            return np.linalg.norm(dynamics_residual)**2
        return factor

    def start_factor(start):
        """Start factor: Enforces q_0 = start."""
        def factor(q, u):
            return np.linalg.norm(q[0] - start)**2 * 1e6  # v Large weight
        return factor

    def goal_factor(goal):
        """Goal factor: Enforces q_T = goal."""
        def factor(q, u):
            return np.linalg.norm(q[-1] - goal)**2 * 1e6  # v Large weight
        return factor

    def intermediate_factor(intermediate_state, t):
        """Intermediate state constraint: Enforces q_t = intermediate_state."""
        def factor(q, u):
            return np.linalg.norm(q[t] - intermediate_state)**2 * 1e6  
        return factor

    def control_cost_factor(t):
        """Control cost: Penalizes large control inputs."""
        def factor(q, u):
            u_t = u[t]
            return np.linalg.norm(u_t)**2
        return factor

    def acceleration_cost_factor(dt, t):
        """Acceleration cost: Penalizes changes in control (accelerations)."""
        def factor(q, u):
            u_t = u[t]
            u_t1 = u[t + 1]
            acceleration = (u_t1 - u_t) / dt
            return np.linalg.norm(acceleration)**2
        return factor

    # Initialize 
    factor_graph = FactorGraph(T, start, goal, dt)

    
    factor_graph.add_factor(start_factor(start))  
    factor_graph.add_factor(goal_factor(goal))   
    factor_graph.add_factor(intermediate_factor(x0_in, T // 3))    
    factor_graph.add_factor(intermediate_factor(x1_in, 2 * T // 3))  

    for t in range(T):
        factor_graph.add_factor(control_cost_factor(t))  
        factor_graph.add_factor(dynamics_factor(dt, t))  

    for t in range(T - 1):
        factor_graph.add_factor(acceleration_cost_factor(dt, t))  

    # Initial guess: Straight line with intermediate points
    waypoints = [start, x0_in, x1_in, goal]
    waypoint_times = [0, T // 3, 2 * T // 3, T]
    initial_positions = np.zeros((factor_graph.num_states, 2))

    for i in range(len(waypoints) - 1):
        start_idx = waypoint_times[i]
        end_idx = waypoint_times[i + 1]
        initial_positions[start_idx:end_idx + 1] = np.linspace(waypoints[i], waypoints[i + 1], end_idx - start_idx + 1)

    # Initial guess for controls
    initial_controls = np.diff(initial_positions, axis=0) / dt

    # Flatten
    initial_variables = np.hstack((initial_positions.flatten(), initial_controls.flatten()))

    # Optimize 
    result = minimize(
        factor_graph.compute_total_cost,
        initial_variables,
        method="SLSQP",
        options={"disp": True, "maxiter": 2000, "ftol": 1e-6}
    )

    
    optimized_positions = result.x[:factor_graph.num_states * 2].reshape(factor_graph.num_states, 2)
    optimized_controls = result.x[factor_graph.num_states * 2:].reshape(factor_graph.num_controls, 2)

    
    plt.figure()
    plt.plot(initial_positions[:, 0], initial_positions[:, 1], label="Initial Trajectory")
    plt.plot(optimized_positions[:, 0], optimized_positions[:, 1], label="Optimized Trajectory", color="orange")
    plt.scatter([start[0], x0_in[0], x1_in[0], goal[0]],
                [start[1], x0_in[1], x1_in[1], goal[1]],
                c="red", label="Key Points", zorder=5)
    plt.title("Trajectory Optimization with Extra Constraints")
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.legend()
    plt.grid()
    plt.show()


# --- we can uncomment all these for way more visualizations ---
    # Plot velocity profile
    velocities = optimized_controls
    velocity_magnitudes = np.linalg.norm(velocities, axis=1)
    time_steps = np.arange(factor_graph.num_controls) * dt

    plt.figure()
    plt.plot(time_steps, velocity_magnitudes, label='Velocity Magnitude')
    plt.title('Velocity Profile Over Time')
    plt.xlabel('Time (s)')
    plt.ylabel('Velocity Magnitude')
    plt.legend()
    plt.grid()
    plt.show()

    # Plot acceleration profile
    accelerations = np.diff(optimized_controls, axis=0) / dt
    acceleration_magnitudes = np.linalg.norm(accelerations, axis=1)
    time_steps_acc = np.arange(factor_graph.num_controls - 1) * dt

    plt.figure()
    plt.plot(time_steps_acc, acceleration_magnitudes, label='Acceleration Magnitude')
    plt.title('Acceleration Profile Over Time')
    plt.xlabel('Time (s)')
    plt.ylabel('Acceleration Magnitude')
    plt.legend()
    plt.grid()
    plt.show()

    # Visualize the Factor Graph
    def visualize_factor_graph(T):
        G = nx.Graph()
        # Add nodes for states and controls
        for t in range(T + 1):
            G.add_node(f"q_{t}")
        for t in range(T):
            G.add_node(f"u_{t}")
        # dynamics factors
        for t in range(T):
            G.add_edge(f"q_{t}", f"q_{t+1}", label="dynamics")
            G.add_edge(f"q_{t}", f"u_{t}", label="dynamics")
        # control cost factors
        for t in range(T):
            G.add_edge(f"u_{t}", f"u_{t}", label="control cost")
        # acceleration cost factors
        for t in range(T - 1):
            G.add_edge(f"u_{t}", f"u_{t+1}", label="acceleration cost")
        
        G.add_edge("start", "q_0", label="start")
        G.add_edge(f"q_{T}", "goal", label="goal")
        G.add_edge(f"q_{T//3}", "x0_in", label="intermediate_1")
        G.add_edge(f"q_{2*T//3}", "x1_in", label="intermediate_2")

        pos = nx.spring_layout(G, seed=42)
        nx.draw(G, pos, with_labels=True, node_size=500, font_size=8)
        nx.draw_networkx_edge_labels(G, pos, edge_labels=nx.get_edge_attributes(G, "label"))
        plt.title("Factor Graph Representation")
        plt.show()
    
    fig, ax = plt.subplots()
    ax.set_xlim(np.min(optimized_positions[:, 0]) - 1, np.max(optimized_positions[:, 0]) + 1)
    ax.set_ylim(np.min(optimized_positions[:, 1]) - 1, np.max(optimized_positions[:, 1]) + 1)
    line, = ax.plot([], [], 'ro-')

    def init():
        line.set_data([], [])
        return line,

    def animate(i):
        line.set_data(optimized_positions[:i, 0], optimized_positions[:i, 1])
        return line,

    ani = animation.FuncAnimation(fig, animate, frames=factor_graph.num_states, init_func=init, blit=True)
    plt.show()



    visualize_factor_graph(T=min(5, T))  

if __name__ == "__main__":
    main()
