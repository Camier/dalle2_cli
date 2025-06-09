#!/usr/bin/env python3
"""
DALL-E Workers - Distributed processing for ultra-fast generation
"""
import asyncio
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Callable, Optional
import time
import queue
import threading
from dataclasses import dataclass
from enum import Enum
import psutil
import os

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.live import Live
from rich.table import Table
from rich.panel import Panel

console = Console()

class WorkerStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    COMPLETED = "completed"

@dataclass
class WorkerTask:
    """Task for worker processing"""
    id: str
    task_type: str
    payload: Dict[str, Any]
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 3

@dataclass
class WorkerResult:
    """Result from worker processing"""
    task_id: str
    status: WorkerStatus
    result: Any
    error: Optional[Exception] = None
    duration: float = 0.0

class WorkerPool:
    """Advanced worker pool with monitoring and load balancing"""
    
    def __init__(self, 
                 num_workers: Optional[int] = None,
                 worker_type: str = "thread",
                 enable_monitoring: bool = True):
        """
        Initialize worker pool
        
        Args:
            num_workers: Number of workers (None = auto-detect)
            worker_type: "thread" or "process"
            enable_monitoring: Enable real-time monitoring
        """
        self.num_workers = num_workers or self._auto_detect_workers()
        self.worker_type = worker_type
        self.enable_monitoring = enable_monitoring
        
        # Task queues
        self.task_queue = queue.PriorityQueue()
        self.result_queue = queue.Queue()
        
        # Worker management
        self.workers = []
        self.worker_stats = {}
        self.active_tasks = {}
        self.completed_tasks = 0
        
        # Monitoring
        self.monitor_thread = None
        self.shutdown_flag = threading.Event()
        
        # Executor
        if worker_type == "process":
            self.executor = ProcessPoolExecutor(max_workers=self.num_workers)
        else:
            self.executor = ThreadPoolExecutor(max_workers=self.num_workers)
    
    def _auto_detect_workers(self) -> int:
        """Auto-detect optimal number of workers"""
        cpu_count = psutil.cpu_count(logical=False) or 2
        
        # For I/O bound tasks (API calls), we can use more workers
        if self.worker_type == "thread":
            return min(cpu_count * 2, 8)
        else:
            # For CPU bound tasks
            return cpu_count
    
    def start(self):
        """Start the worker pool"""
        console.print(f"[green]Starting {self.num_workers} {self.worker_type} workers...[/green]")
        
        # Initialize worker stats
        for i in range(self.num_workers):
            self.worker_stats[f"worker_{i}"] = {
                "status": WorkerStatus.IDLE,
                "tasks_completed": 0,
                "current_task": None,
                "start_time": None
            }
        
        # Start monitoring if enabled
        if self.enable_monitoring:
            self.monitor_thread = threading.Thread(target=self._monitor_workers)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
    
    def stop(self):
        """Stop the worker pool gracefully"""
        console.print("[yellow]Shutting down worker pool...[/yellow]")
        self.shutdown_flag.set()
        self.executor.shutdown(wait=True)
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
    
    def submit_task(self, task: WorkerTask) -> str:
        """Submit a task to the pool"""
        self.task_queue.put((task.priority, task))
        return task.id
    
    def submit_batch(self, tasks: List[WorkerTask]) -> List[str]:
        """Submit multiple tasks"""
        task_ids = []
        for task in tasks:
            task_ids.append(self.submit_task(task))
        return task_ids
    
    async def process_tasks_async(self, 
                                  processor_func: Callable,
                                  timeout: Optional[float] = None) -> List[WorkerResult]:
        """Process all queued tasks asynchronously"""
        results = []
        futures = []
        
        # Submit all tasks
        while not self.task_queue.empty():
            _, task = self.task_queue.get()
            future = self.executor.submit(self._process_single_task, task, processor_func)
            futures.append((future, task))
            self.active_tasks[task.id] = task
        
        # Wait for completion with timeout
        start_time = time.time()
        
        for future, task in futures:
            try:
                if timeout:
                    remaining = timeout - (time.time() - start_time)
                    if remaining <= 0:
                        raise TimeoutError("Batch processing timeout")
                    result = future.result(timeout=remaining)
                else:
                    result = future.result()
                
                results.append(result)
                self.completed_tasks += 1
                
            except Exception as e:
                result = WorkerResult(
                    task_id=task.id,
                    status=WorkerStatus.ERROR,
                    result=None,
                    error=e
                )
                results.append(result)
            
            finally:
                if task.id in self.active_tasks:
                    del self.active_tasks[task.id]
        
        return results
    
    def _process_single_task(self, task: WorkerTask, processor_func: Callable) -> WorkerResult:
        """Process a single task"""
        start_time = time.time()
        worker_id = f"worker_{threading.get_ident() % self.num_workers}"
        
        # Update worker status
        self.worker_stats[worker_id]["status"] = WorkerStatus.BUSY
        self.worker_stats[worker_id]["current_task"] = task.id
        self.worker_stats[worker_id]["start_time"] = start_time
        
        try:
            # Process the task
            result = processor_func(task.payload)
            
            # Success
            worker_result = WorkerResult(
                task_id=task.id,
                status=WorkerStatus.COMPLETED,
                result=result,
                duration=time.time() - start_time
            )
            
            self.worker_stats[worker_id]["tasks_completed"] += 1
            
        except Exception as e:
            # Handle error with retry logic
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                self.submit_task(task)  # Re-queue for retry
                
            worker_result = WorkerResult(
                task_id=task.id,
                status=WorkerStatus.ERROR,
                result=None,
                error=e,
                duration=time.time() - start_time
            )
        
        finally:
            # Reset worker status
            self.worker_stats[worker_id]["status"] = WorkerStatus.IDLE
            self.worker_stats[worker_id]["current_task"] = None
        
        return worker_result
    
    def _monitor_workers(self):
        """Monitor worker status in real-time"""
        with Live(console=console, refresh_per_second=2) as live:
            while not self.shutdown_flag.is_set():
                # Create monitoring table
                table = Table(title="Worker Pool Status", box="rounded")
                table.add_column("Worker", style="cyan")
                table.add_column("Status", style="white")
                table.add_column("Current Task", style="yellow")
                table.add_column("Tasks Done", style="green")
                table.add_column("CPU %", style="magenta")
                table.add_column("Memory MB", style="blue")
                
                # Get system stats
                cpu_percent = psutil.cpu_percent(interval=0.1, percpu=True)
                memory_info = psutil.virtual_memory()
                
                for i, (worker_id, stats) in enumerate(self.worker_stats.items()):
                    status_color = {
                        WorkerStatus.IDLE: "green",
                        WorkerStatus.BUSY: "yellow",
                        WorkerStatus.ERROR: "red"
                    }.get(stats["status"], "white")
                    
                    status = f"[{status_color}]{stats['status'].value}[/{status_color}]"
                    current_task = stats["current_task"] or "-"
                    
                    # Estimate CPU usage
                    cpu = f"{cpu_percent[i % len(cpu_percent)]:.1f}%" if i < len(cpu_percent) else "N/A"
                    
                    # Memory per worker (rough estimate)
                    mem_per_worker = memory_info.used / 1024 / 1024 / self.num_workers
                    
                    table.add_row(
                        worker_id,
                        status,
                        current_task,
                        str(stats["tasks_completed"]),
                        cpu,
                        f"{mem_per_worker:.0f}"
                    )
                
                # Add summary
                summary = Panel(
                    f"Total Tasks: {self.completed_tasks} | "
                    f"Active: {len(self.active_tasks)} | "
                    f"Queued: {self.task_queue.qsize()}",
                    title="Summary",
                    border_style="green"
                )
                
                # Update display
                live.update(table)
                console.print(summary)
                
                time.sleep(1)

class ImageGenerationWorker:
    """Specialized worker for DALL-E image generation"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = None
    
    def initialize(self):
        """Initialize OpenAI client"""
        from openai import OpenAI
        self.client = OpenAI(api_key=self.api_key)
    
    def process_generation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process image generation task"""
        if not self.client:
            self.initialize()
        
        # Extract parameters
        prompt = payload["prompt"]
        model = payload.get("model", "dall-e-3")
        size = payload.get("size", "1024x1024")
        quality = payload.get("quality", "standard")
        
        # Generate image
        response = self.client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            quality=quality,
            n=1
        )
        
        # Return result
        return {
            "url": response.data[0].url,
            "revised_prompt": getattr(response.data[0], 'revised_prompt', None),
            "prompt": prompt,
            "model": model
        }

class BatchProcessor:
    """High-performance batch processing with workers"""
    
    def __init__(self, api_key: str, num_workers: Optional[int] = None):
        self.api_key = api_key
        self.worker_pool = WorkerPool(
            num_workers=num_workers,
            worker_type="thread",  # Use threads for I/O bound API calls
            enable_monitoring=True
        )
        self.generation_worker = ImageGenerationWorker(api_key)
    
    async def generate_batch(self, 
                           prompts: List[str],
                           model: str = "dall-e-3",
                           size: str = "1024x1024",
                           quality: str = "standard",
                           show_progress: bool = True) -> List[Dict[str, Any]]:
        """Generate multiple images in parallel using workers"""
        
        # Start worker pool
        self.worker_pool.start()
        
        try:
            # Create tasks
            tasks = []
            for i, prompt in enumerate(prompts):
                task = WorkerTask(
                    id=f"gen_{i}",
                    task_type="generate",
                    payload={
                        "prompt": prompt,
                        "model": model,
                        "size": size,
                        "quality": quality
                    },
                    priority=i  # Process in order
                )
                tasks.append(task)
            
            # Submit batch
            self.worker_pool.submit_batch(tasks)
            
            # Process with progress
            if show_progress:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    console=console
                ) as progress:
                    task = progress.add_task(
                        f"Generating {len(prompts)} images...", 
                        total=len(prompts)
                    )
                    
                    # Process tasks
                    results = await self.worker_pool.process_tasks_async(
                        self.generation_worker.process_generation
                    )
                    
                    progress.update(task, completed=len(results))
            else:
                results = await self.worker_pool.process_tasks_async(
                    self.generation_worker.process_generation
                )
            
            # Extract successful results
            successful = []
            failed = []
            
            for result in results:
                if result.status == WorkerStatus.COMPLETED:
                    successful.append(result.result)
                else:
                    failed.append({
                        "task_id": result.task_id,
                        "error": str(result.error)
                    })
            
            # Report results
            console.print(f"\n✅ Successfully generated: {len(successful)}")
            if failed:
                console.print(f"❌ Failed: {len(failed)}")
                for fail in failed:
                    console.print(f"  - {fail['task_id']}: {fail['error']}")
            
            return successful
            
        finally:
            # Clean shutdown
            self.worker_pool.stop()

# Example usage
async def demo_workers():
    """Demo the worker system"""
    console.print("[bold cyan]DALL-E Worker System Demo[/bold cyan]\n")
    
    # Sample prompts
    prompts = [
        "A futuristic city at sunset",
        "A serene mountain landscape",
        "An abstract art composition",
        "A cozy coffee shop interior",
        "A magical forest scene"
    ]
    
    # Initialize batch processor
    api_key = "your-api-key-here"  # Replace with actual key
    processor = BatchProcessor(api_key, num_workers=3)
    
    # Generate batch
    console.print(f"[green]Generating {len(prompts)} images with 3 workers...[/green]\n")
    
    start_time = time.time()
    results = await processor.generate_batch(prompts, quality="standard")
    duration = time.time() - start_time
    
    console.print(f"\n⏱️ Total time: {duration:.2f} seconds")
    console.print(f"📊 Average per image: {duration/len(prompts):.2f} seconds")

if __name__ == "__main__":
    # Run demo
    asyncio.run(demo_workers())