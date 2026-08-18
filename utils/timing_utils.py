import time
import os
from functools import wraps
import matplotlib.pyplot as plt

def measure_time(func=None, *, return_time=True):
    """
    Decorator to measure the runtime of a function.
    If `return_time` is False, only the result of the function is returned.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = fn(*args, **kwargs)
            elapsed_time = time.time() - start_time
            print(f"{fn.__name__} took {elapsed_time:.4f} seconds")
            if return_time:
                return elapsed_time, result
            return result
        return wrapper

    return decorator(func) if func else decorator

def visualize_timings(timings, title="Excution Time", save_path="/benchmarking/timings_chart.png"):
    """Visualize function timings using a bar chart and save it."""
    save_dir = os.path.dirname(save_path)
    if save_dir and not os.path.exists(save_dir):
        os.makedirs(save_dir)

    labels = [key for key in timings.keys() if key != 'total_time']
    values = [timings[key] for key in labels]

    # Add total time as a separate bar for comparison
    labels.append('total_time')
    values.append(timings['total_time'])

    # Create a horizontal bar chart
    plt.figure(figsize=(10, 6))
    plt.barh(labels, values, color='skyblue')
    plt.xlabel('Time (seconds)')
    plt.ylabel('Functions')
    plt.title(f'Benchmark Results: Execution Time for {title}')
    plt.grid(axis='x', linestyle='--', alpha=0.7)
    plt.tight_layout()

    # Save the chart to a file
    plt.savefig(save_path)
    print(f"Timing chart saved to {save_path}")

    plt.close()