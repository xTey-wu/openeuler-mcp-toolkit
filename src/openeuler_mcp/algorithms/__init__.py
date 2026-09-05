from .disk import simulate_disk_allocation
from .page_replacement import simulate_page_replacement
from .scheduling import simulate_cpu_scheduling

__all__ = [
    "simulate_cpu_scheduling",
    "simulate_disk_allocation",
    "simulate_page_replacement",
]
