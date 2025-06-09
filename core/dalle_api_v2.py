"""
Enhanced DALL-E API Manager with batch processing and advanced features
"""
import asyncio
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncIterator
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import hashlib

import aiohttp
import aiofiles
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
import httpx

@dataclass
class BatchRequest:
    """Represents a single request in a batch"""
    custom_id: str
    method: str
    url: str
    body: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "custom_id": self.custom_id,
            "method": self.method,
            "url": self.url,
            "body": self.body
        }

@dataclass
class BatchJob:
    """Represents a batch job"""
    id: str
    status: str
    created_at: int
    completed_at: Optional[int] = None
    expired_at: Optional[int] = None
    output_file_id: Optional[str] = None
    error_file_id: Optional[str] = None
    request_counts: Optional[Dict[str, int]] = None

class BatchProcessor:
    """Handle batch API operations for cost-effective processing"""
    
    def __init__(self, api_key: str, cache_dir: Optional[Path] = None):
        self.client = AsyncOpenAI(api_key=api_key)
        self.cache_dir = cache_dir or Path.home() / ".dalle_cli" / "batch_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    async def create_batch_file(self, requests: List[BatchRequest]) -> str:
        """Create a JSONL file for batch processing"""
        batch_id = hashlib.md5(
            json.dumps([r.to_dict() for r in requests]).encode()
        ).hexdigest()[:12]
        
        file_path = self.cache_dir / f"batch_{batch_id}.jsonl"
        
        async with aiofiles.open(file_path, 'w') as f:
            for request in requests:
                await f.write(json.dumps(request.to_dict()) + '\n')
        
        # Upload file to OpenAI
        with open(file_path, 'rb') as f:
            response = await self.client.files.create(
                file=f,
                purpose="batch"
            )
        
        return response.id
    
    async def submit_batch(self, file_id: str, 
                          description: Optional[str] = None) -> BatchJob:
        """Submit a batch job"""
        response = await self.client.batches.create(
            input_file_id=file_id,
            endpoint="/v1/images/generations",
            completion_window="24h",
            metadata={
                "description": description or "DALL-E batch generation",
                "created_by": "dalle_cli_v2"
            }
        )
        
        return BatchJob(
            id=response.id,
            status=response.status,
            created_at=response.created_at
        )
    
    async def get_batch_status(self, batch_id: str) -> BatchJob:
        """Get current status of a batch job"""
        response = await self.client.batches.retrieve(batch_id)
        
        return BatchJob(
            id=response.id,
            status=response.status,
            created_at=response.created_at,
            completed_at=response.completed_at,
            expired_at=response.expires_at,
            output_file_id=response.output_file_id,
            error_file_id=response.error_file_id,
            request_counts=response.request_counts
        )
    
    async def wait_for_completion(self, batch_id: str, 
                                 poll_interval: int = 60,
                                 callback=None) -> BatchJob:
        """Wait for batch job to complete"""
        while True:
            job = await self.get_batch_status(batch_id)
            
            if callback:
                callback(job)
            
            if job.status in ['completed', 'failed', 'expired']:
                return job
            
            await asyncio.sleep(poll_interval)
    
    async def get_batch_results(self, output_file_id: str) -> List[Dict[str, Any]]:
        """Retrieve results from completed batch"""
        # Download the output file
        content = await self.client.files.content(output_file_id)
        
        results = []
        for line in content.text.strip().split('\n'):
            if line:
                results.append(json.loads(line))
        
        return results
    
    async def create_image_batch(self, prompts: List[str], 
                               model: str = "dall-e-3",
                               size: str = "1024x1024",
                               quality: str = "standard") -> str:
        """Create a batch job for multiple image generation requests"""
        requests = []
        
        for i, prompt in enumerate(prompts):
            request = BatchRequest(
                custom_id=f"img_{i}_{hashlib.md5(prompt.encode()).hexdigest()[:8]}",
                method="POST",
                url="/v1/images/generations",
                body={
                    "model": model,
                    "prompt": prompt,
                    "size": size,
                    "quality": quality,
                    "n": 1
                }
            )
            requests.append(request)
        
        file_id = await self.create_batch_file(requests)
        batch_job = await self.submit_batch(file_id, 
                                          f"Batch of {len(prompts)} images")
        
        return batch_job.id

class EnhancedImageGenerator:
    """Advanced image generation with caching and optimization"""
    
    def __init__(self, api_key: str, cache_enabled: bool = True):
        self.client = AsyncOpenAI(api_key=api_key)
        self.cache_enabled = cache_enabled
        self.cache_dir = Path.home() / ".dalle_cli" / "image_cache"
        if cache_enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def _get_cache_key(self, prompt: str, model: str, size: str, 
                      quality: str, style: Optional[str] = None) -> str:
        """Generate cache key for a request"""
        params = f"{prompt}|{model}|{size}|{quality}|{style or ''}"
        return hashlib.sha256(params.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Check if result exists in cache"""
        if not self.cache_enabled:
            return None
            
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            # Check if cache is less than 7 days old
            age = time.time() - cache_file.stat().st_mtime
            if age < 7 * 24 * 3600:  # 7 days
                with open(cache_file, 'r') as f:
                    return json.load(f)
        return None
    
    def _save_to_cache(self, cache_key: str, result: Dict[str, Any]):
        """Save result to cache"""
        if not self.cache_enabled:
            return
            
        cache_file = self.cache_dir / f"{cache_key}.json"
        with open(cache_file, 'w') as f:
            json.dump(result, f)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate_with_retry(self, prompt: str, model: str, 
                                 size: str, quality: str, 
                                 style: Optional[str] = None) -> Dict[str, Any]:
        """Generate image with automatic retry on failure"""
        # Check cache first
        cache_key = self._get_cache_key(prompt, model, size, quality, style)
        cached = self._get_cached_result(cache_key)
        if cached:
            cached['from_cache'] = True
            return cached
        
        # Generate new image
        params = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "n": 1
        }
        
        if model == "dall-e-3" and style:
            params["style"] = style
        
        response = await self.client.images.generate(**params)
        
        result = {
            "success": True,
            "url": response.data[0].url,
            "revised_prompt": getattr(response.data[0], 'revised_prompt', prompt),
            "model": model,
            "size": size,
            "quality": quality,
            "generated_at": datetime.now().isoformat(),
            "from_cache": False
        }
        
        # Save to cache
        self._save_to_cache(cache_key, result)
        
        return result
    
    async def generate_stream(self, prompts: List[str], model: str,
                            size: str, quality: str,
                            max_concurrent: int = 5) -> AsyncIterator[Dict[str, Any]]:
        """Generate images with controlled concurrency"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def generate_with_semaphore(prompt: str, index: int):
            async with semaphore:
                try:
                    result = await self.generate_with_retry(
                        prompt, model, size, quality
                    )
                    result['index'] = index
                    result['prompt'] = prompt
                    return result
                except Exception as e:
                    return {
                        "success": False,
                        "error": str(e),
                        "prompt": prompt,
                        "index": index
                    }
        
        # Create all tasks
        tasks = [
            generate_with_semaphore(prompt, i) 
            for i, prompt in enumerate(prompts)
        ]
        
        # Yield results as they complete
        for task in asyncio.as_completed(tasks):
            yield await task

class PromptOptimizer:
    """Optimize prompts for better results"""
    
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
    
    async def enhance_prompt(self, prompt: str, style: str = "photorealistic") -> str:
        """Enhance a prompt for better image generation"""
        system_prompt = f"""You are an expert at writing prompts for DALL-E image generation.
        Enhance the given prompt to be more detailed and specific for {style} image generation.
        Keep the enhanced prompt under 400 characters.
        Focus on visual details, lighting, composition, and style."""
        
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Enhance this prompt: {prompt}"}
            ],
            max_tokens=150,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
    
    async def generate_variations(self, base_prompt: str, count: int = 3) -> List[str]:
        """Generate variations of a prompt"""
        system_prompt = """Generate creative variations of the given image prompt.
        Each variation should maintain the core concept but explore different:
        - Artistic styles
        - Compositions
        - Lighting conditions
        - Color palettes
        Keep each under 400 characters."""
        
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Generate {count} variations of: {base_prompt}"}
            ],
            max_tokens=500,
            temperature=0.8
        )
        
        # Parse variations from response
        content = response.choices[0].message.content
        variations = []
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith(('#', '-', '*', '1', '2', '3')):
                variations.append(line)
            elif line.startswith(('1.', '2.', '3.', '-', '*')):
                # Remove numbering or bullets
                cleaned = line.lstrip('0123456789.-* ')
                if cleaned:
                    variations.append(cleaned)
        
        return variations[:count]

class ImageMetadata:
    """Manage image metadata and history"""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".dalle_cli" / "metadata.json"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load_data()
    
    def _load_data(self) -> Dict[str, Any]:
        """Load metadata from disk"""
        if self.db_path.exists():
            with open(self.db_path, 'r') as f:
                return json.load(f)
        return {"images": [], "stats": {"total_generated": 0, "total_cost": 0}}
    
    def save(self):
        """Save metadata to disk"""
        with open(self.db_path, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def add_image(self, prompt: str, url: str, model: str, 
                 size: str, quality: str, cost: float,
                 local_path: Optional[str] = None):
        """Add image metadata"""
        entry = {
            "id": hashlib.md5(f"{url}{time.time()}".encode()).hexdigest()[:12],
            "prompt": prompt,
            "url": url,
            "model": model,
            "size": size,
            "quality": quality,
            "cost": cost,
            "local_path": local_path,
            "created_at": datetime.now().isoformat()
        }
        
        self.data["images"].append(entry)
        self.data["stats"]["total_generated"] += 1
        self.data["stats"]["total_cost"] += cost
        
        self.save()
    
    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search images by prompt"""
        results = []
        query_lower = query.lower()
        
        for image in self.data["images"]:
            if query_lower in image["prompt"].lower():
                results.append(image)
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get generation statistics"""
        stats = self.data["stats"].copy()
        
        # Add more detailed stats
        if self.data["images"]:
            # Group by model
            model_counts = {}
            for img in self.data["images"]:
                model = img["model"]
                model_counts[model] = model_counts.get(model, 0) + 1
            
            stats["by_model"] = model_counts
            
            # Recent activity
            recent = [img for img in self.data["images"] 
                     if (datetime.now() - datetime.fromisoformat(img["created_at"])).days < 7]
            stats["generated_this_week"] = len(recent)
        
        return stats