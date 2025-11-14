"""
Performance monitoring utilities for tracking optimization improvements.
"""
import time
import logging
import asyncio
from functools import wraps
from typing import Dict, Any, Optional
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Monitor and track performance metrics."""
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self.start_times = {}
    
    def start_timer(self, operation_name: str):
        """Start timing an operation."""
        self.start_times[operation_name] = time.time()
    
    def end_timer(self, operation_name: str, additional_info: str = ""):
        """End timing an operation and record the metric."""
        if operation_name in self.start_times:
            elapsed_time = time.time() - self.start_times[operation_name]
            self.metrics[operation_name].append({
                'duration': elapsed_time,
                'timestamp': time.time(),
                'additional_info': additional_info
            })
            del self.start_times[operation_name]
            
            logger.info(f"[PERF] {operation_name}: {elapsed_time:.3f}s {additional_info}")
            return elapsed_time
        return 0.0
    
    def get_stats(self, operation_name: str) -> Dict[str, Any]:
        """Get statistics for an operation."""
        if operation_name not in self.metrics:
            return {}
        
        durations = [m['duration'] for m in self.metrics[operation_name]]
        if not durations:
            return {}
        
        return {
            'count': len(durations),
            'avg': statistics.mean(durations),
            'min': min(durations),
            'max': max(durations),
            'median': statistics.median(durations),
            'total_time': sum(durations)
        }
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all operations."""
        return {op: self.get_stats(op) for op in self.metrics.keys()}
    
    def clear_metrics(self):
        """Clear all metrics."""
        self.metrics.clear()
        self.start_times.clear()

# Global performance monitor instance
performance_monitor = PerformanceMonitor()

def track_performance(operation_name: str):
    """Decorator to track performance of functions."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            performance_monitor.start_timer(operation_name)
            try:
                result = await func(*args, **kwargs)
                performance_monitor.end_timer(operation_name, "success")
                return result
            except Exception as e:
                performance_monitor.end_timer(operation_name, f"error: {str(e)}")
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            performance_monitor.start_timer(operation_name)
            try:
                result = func(*args, **kwargs)
                performance_monitor.end_timer(operation_name, "success")
                return result
            except Exception as e:
                performance_monitor.end_timer(operation_name, f"error: {str(e)}")
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def log_performance_summary():
    """Log a summary of all performance metrics."""
    stats = performance_monitor.get_all_stats()
    if not stats:
        logger.info("No performance metrics recorded")
        return
    
    logger.info("=== PERFORMANCE SUMMARY ===")
    for operation, stat in stats.items():
        logger.info(f"{operation}: {stat['count']} calls, "
                   f"avg: {stat['avg']:.3f}s, "
                   f"min: {stat['min']:.3f}s, "
                   f"max: {stat['max']:.3f}s, "
                   f"total: {stat['total_time']:.3f}s")
    logger.info("==========================") 