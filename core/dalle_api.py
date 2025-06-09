import asyncio
import aiohttp
import openai
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from concurrent.futures import ThreadPoolExecutor
import threading
import time
from dataclasses import dataclass
from PIL import Image
import io
import base64


@dataclass
class GenerationRequest:
    prompt: str
    size: str = "1024x1024"
    quality: str = "standard"
    style: str = "natural"
    n: int = 1
    user_id: Optional[str] = None


@dataclass
class VariationRequest:
    image_path: str
    size: str = "1024x1024"
    n: int = 1
    user_id: Optional[str] = None


@dataclass
class EditRequest:
    image_path: str
    mask_path: Optional[str]
    prompt: str
    size: str = "1024x1024"
    n: int = 1
    user_id: Optional[str] = None


@dataclass
class GenerationResult:
    success: bool
    image_urls: List[str] = None
    error: str = None
    cost: float = 0.0
    request_id: str = None


class DALLEWorker:
    def __init__(self, api_key: str, worker_id: int):
        self.api_key = api_key
        self.worker_id = worker_id
        self.client = openai.OpenAI(api_key=api_key)
        self.is_busy = False
        self.current_task = None
    
    async def generate_image(self, request: GenerationRequest) -> GenerationResult:
        self.is_busy = True
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, self._sync_generate, request
            )
            return response
        finally:
            self.is_busy = False
    
    def _sync_generate(self, request: GenerationRequest) -> GenerationResult:
        try:
            response = self.client.images.generate(
                model="dall-e-3" if request.quality == "hd" else "dall-e-2",
                prompt=request.prompt,
                size=request.size,
                quality=request.quality,
                style=request.style,
                n=request.n,
                user=request.user_id
            )
            
            urls = [img.url for img in response.data]
            cost = self._calculate_cost(request.size, request.quality, request.n)
            
            return GenerationResult(
                success=True,
                image_urls=urls,
                cost=cost,
                request_id=response.data[0].revised_prompt if hasattr(response.data[0], 'revised_prompt') else None
            )
        except Exception as e:
            return GenerationResult(
                success=False,
                error=str(e)
            )
    
    async def create_variation(self, request: VariationRequest) -> GenerationResult:
        self.is_busy = True
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, self._sync_variation, request
            )
            return response
        finally:
            self.is_busy = False
    
    def _sync_variation(self, request: VariationRequest) -> GenerationResult:
        try:
            with open(request.image_path, 'rb') as image_file:
                response = self.client.images.create_variation(
                    image=image_file,
                    n=request.n,
                    size=request.size,
                    user=request.user_id
                )
            
            urls = [img.url for img in response.data]
            cost = self._calculate_variation_cost(request.size, request.n)
            
            return GenerationResult(
                success=True,
                image_urls=urls,
                cost=cost
            )
        except Exception as e:
            return GenerationResult(
                success=False,
                error=str(e)
            )
    
    async def edit_image(self, request: EditRequest) -> GenerationResult:
        self.is_busy = True
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, self._sync_edit, request
            )
            return response
        finally:
            self.is_busy = False
    
    def _sync_edit(self, request: EditRequest) -> GenerationResult:
        try:
            with open(request.image_path, 'rb') as image_file:
                kwargs = {
                    'image': image_file,
                    'prompt': request.prompt,
                    'n': request.n,
                    'size': request.size,
                    'user': request.user_id
                }
                
                if request.mask_path:
                    with open(request.mask_path, 'rb') as mask_file:
                        kwargs['mask'] = mask_file
                        response = self.client.images.edit(**kwargs)
                else:
                    response = self.client.images.edit(**kwargs)
            
            urls = [img.url for img in response.data]
            cost = self._calculate_edit_cost(request.size, request.n)
            
            return GenerationResult(
                success=True,
                image_urls=urls,
                cost=cost
            )
        except Exception as e:
            return GenerationResult(
                success=False,
                error=str(e)
            )
    
    def _calculate_cost(self, size: str, quality: str, n: int) -> float:
        base_costs = {
            "1024x1024": {"standard": 0.04, "hd": 0.08},
            "1024x1792": {"standard": 0.08, "hd": 0.12},
            "1792x1024": {"standard": 0.08, "hd": 0.12}
        }
        return base_costs.get(size, {}).get(quality, 0.04) * n
    
    def _calculate_variation_cost(self, size: str, n: int) -> float:
        costs = {"1024x1024": 0.02, "512x512": 0.018, "256x256": 0.016}
        return costs.get(size, 0.02) * n
    
    def _calculate_edit_cost(self, size: str, n: int) -> float:
        costs = {"1024x1024": 0.02, "512x512": 0.018, "256x256": 0.016}
        return costs.get(size, 0.02) * n


class DALLEAPIManager:
    def __init__(self, api_key: str, max_workers: int = 3):
        self.api_key = api_key
        self.max_workers = max_workers
        self.workers = [DALLEWorker(api_key, i) for i in range(max_workers)]
        self.task_queue = asyncio.Queue()
        self.result_callbacks = {}
        self._running = False
        self._worker_tasks = []
    
    async def start(self):
        self._running = True
        self._worker_tasks = [
            asyncio.create_task(self._worker_loop(worker))
            for worker in self.workers
        ]
    
    async def stop(self):
        self._running = False
        for task in self._worker_tasks:
            task.cancel()
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
    
    async def _worker_loop(self, worker: DALLEWorker):
        while self._running:
            try:
                task_data = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                task_type, request, callback = task_data
                
                if task_type == "generate":
                    result = await worker.generate_image(request)
                elif task_type == "variation":
                    result = await worker.create_variation(request)
                elif task_type == "edit":
                    result = await worker.edit_image(request)
                else:
                    continue
                
                if callback:
                    callback(result)
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Worker {worker.worker_id} error: {e}")
    
    async def generate_image_async(self, request: GenerationRequest, callback: Optional[Callable] = None):
        await self.task_queue.put(("generate", request, callback))
    
    async def create_variation_async(self, request: VariationRequest, callback: Optional[Callable] = None):
        await self.task_queue.put(("variation", request, callback))
    
    async def edit_image_async(self, request: EditRequest, callback: Optional[Callable] = None):
        await self.task_queue.put(("edit", request, callback))
    
    def get_queue_size(self) -> int:
        return self.task_queue.qsize()
    
    def get_busy_workers(self) -> int:
        return sum(1 for worker in self.workers if worker.is_busy)
    
    def get_available_workers(self) -> int:
        return len(self.workers) - self.get_busy_workers()


class ImageDownloader:
    def __init__(self, download_dir: Path):
        self.download_dir = download_dir
        self.download_dir.mkdir(exist_ok=True)
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def download_image(self, url: str, filename: str) -> Optional[Path]:
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    filepath = self.download_dir / filename
                    
                    with open(filepath, 'wb') as f:
                        f.write(content)
                    
                    return filepath
                else:
                    print(f"Failed to download image: HTTP {response.status}")
                    return None
        except Exception as e:
            print(f"Error downloading image: {e}")
            return None
    
    async def download_multiple(self, urls: List[str], base_filename: str) -> List[Path]:
        tasks = []
        for i, url in enumerate(urls):
            filename = f"{base_filename}_{i+1}.png"
            tasks.append(self.download_image(url, filename))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, Path)]