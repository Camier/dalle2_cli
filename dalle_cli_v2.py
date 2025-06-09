#!/usr/bin/env python3
"""
DALL-E CLI v2 - Modern, async-powered CLI for OpenAI image generation
Built with best practices from 2024 research
"""
import os
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib

import click
import aiohttp
import aiofiles
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Prompt, Confirm
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.live import Live
from rich.layout import Layout
from rich import print as rprint
from PIL import Image
import openai
from openai import AsyncOpenAI

console = Console()

class DALLEConfig:
    """Configuration management for DALL-E CLI"""
    def __init__(self):
        self.config_dir = Path.home() / ".dalle_cli"
        self.config_file = self.config_dir / "config.json"
        self.config = self.load_config()
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return {
            "api_key": None,
            "default_model": "dall-e-3",
            "default_size": "1024x1024",
            "default_quality": "standard",
            "save_directory": str(Path.home() / "dalle_images"),
            "history_enabled": True,
            "cost_tracking": True,
            "batch_size": 4,
            "max_retries": 3,
            "timeout": 120
        }
    
    def save_config(self):
        """Save configuration to file"""
        self.config_dir.mkdir(exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get(self, key: str, default=None):
        """Get configuration value"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set configuration value"""
        self.config[key] = value
        self.save_config()

class ImageGenerator:
    """Async image generation with advanced features"""
    
    PRICING = {
        "dall-e-2": {
            "1024x1024": 0.020,
            "512x512": 0.018,
            "256x256": 0.016
        },
        "dall-e-3": {
            "1024x1024": 0.040,
            "1024x1792": 0.080,
            "1792x1024": 0.080
        }
    }
    
    def __init__(self, api_key: str, config: DALLEConfig):
        self.client = AsyncOpenAI(api_key=api_key)
        self.config = config
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def estimate_cost(self, model: str, size: str, count: int) -> float:
        """Estimate generation cost"""
        price_per_image = self.PRICING.get(model, {}).get(size, 0.040)
        return price_per_image * count
    
    async def generate_single(self, prompt: str, model: str, size: str, 
                            quality: str, style: str = "vivid") -> Dict[str, Any]:
        """Generate a single image"""
        try:
            params = {
                "model": model,
                "prompt": prompt,
                "size": size,
                "quality": quality,
                "n": 1
            }
            
            if model == "dall-e-3":
                params["style"] = style
                
            response = await self.client.images.generate(**params)
            
            return {
                "success": True,
                "url": response.data[0].url,
                "revised_prompt": getattr(response.data[0], 'revised_prompt', prompt),
                "model": model,
                "size": size,
                "quality": quality
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "prompt": prompt
            }
    
    async def generate_batch(self, prompts: List[str], model: str, size: str,
                           quality: str, style: str = "vivid", 
                           progress_callback=None) -> List[Dict[str, Any]]:
        """Generate multiple images concurrently"""
        tasks = []
        for i, prompt in enumerate(prompts):
            task = self.generate_single(prompt, model, size, quality, style)
            tasks.append(task)
            
        results = []
        for i, task in enumerate(asyncio.as_completed(tasks)):
            result = await task
            results.append(result)
            if progress_callback:
                progress_callback(i + 1, len(prompts))
                
        return results
    
    async def download_image(self, url: str, save_path: Path) -> bool:
        """Download image from URL"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    async with aiofiles.open(save_path, 'wb') as f:
                        await f.write(content)
                    return True
        except Exception as e:
            console.print(f"[red]Error downloading image: {e}[/red]")
        return False
    
    async def create_variations(self, image_path: Path, n: int = 1, 
                              size: str = "1024x1024") -> List[Dict[str, Any]]:
        """Create variations of an existing image"""
        try:
            with open(image_path, 'rb') as f:
                response = await self.client.images.create_variation(
                    image=f,
                    n=n,
                    size=size
                )
            
            return [{
                "success": True,
                "url": data.url,
                "original": str(image_path)
            } for data in response.data]
        except Exception as e:
            return [{
                "success": False,
                "error": str(e),
                "original": str(image_path)
            }]
    
    async def edit_image(self, image_path: Path, prompt: str, 
                        mask_path: Optional[Path] = None,
                        size: str = "1024x1024") -> Dict[str, Any]:
        """Edit an existing image with a prompt"""
        try:
            with open(image_path, 'rb') as img_file:
                if mask_path:
                    with open(mask_path, 'rb') as mask_file:
                        response = await self.client.images.edit(
                            image=img_file,
                            mask=mask_file,
                            prompt=prompt,
                            size=size
                        )
                else:
                    response = await self.client.images.edit(
                        image=img_file,
                        prompt=prompt,
                        size=size
                    )
            
            return {
                "success": True,
                "url": response.data[0].url,
                "prompt": prompt,
                "original": str(image_path)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "prompt": prompt
            }

class VisionAnalyzer:
    """Analyze images using GPT-4 Vision"""
    
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
    
    async def analyze_image(self, image_path: Path, prompt: str = "What's in this image?") -> str:
        """Analyze an image using vision API"""
        try:
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            }
                        }
                    ]
                }]
            )
            
            return response.choices[0].message.content
        except Exception as e:
            return f"Error analyzing image: {e}"

# Click command groups
@click.group(context_settings={'help_option_names': ['-h', '--help']})
@click.version_option(version='2.0.0', prog_name='DALL-E CLI')
@click.pass_context
def cli(ctx):
    """DALL-E CLI v2 - Modern AI image generation tool
    
    \b
    Features:
    - Generate images with DALL-E 2 and DALL-E 3
    - Batch processing for multiple prompts
    - Image variations and editing
    - Vision API integration
    - Cost tracking and estimation
    - Rich terminal output
    """
    ctx.ensure_object(dict)
    ctx.obj['config'] = DALLEConfig()
    
    # Check API key
    api_key = ctx.obj['config'].get('api_key') or os.getenv('OPENAI_API_KEY')
    if not api_key and ctx.invoked_subcommand != 'config':
        console.print("[red]No API key found![/red]")
        console.print("Set it with: dalle config set api_key YOUR_KEY")
        ctx.exit(1)
    
    ctx.obj['api_key'] = api_key

@cli.group()
@click.pass_context
def config(ctx):
    """Manage configuration settings"""
    pass

@config.command('show')
@click.pass_context
def config_show(ctx):
    """Show current configuration"""
    config = ctx.obj['config']
    
    table = Table(title="DALL-E CLI Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    for key, value in config.config.items():
        if key == "api_key" and value:
            value = value[:8] + "..." + value[-4:]
        table.add_row(key, str(value))
    
    console.print(table)

@config.command('set')
@click.argument('key')
@click.argument('value')
@click.pass_context
def config_set(ctx, key, value):
    """Set a configuration value"""
    config = ctx.obj['config']
    
    # Handle boolean values
    if value.lower() in ['true', 'false']:
        value = value.lower() == 'true'
    # Handle numeric values
    elif value.isdigit():
        value = int(value)
    
    config.set(key, value)
    console.print(f"[green]✓[/green] Set {key} = {value}")

@cli.command()
@click.argument('prompt')
@click.option('--model', '-m', default=None, help='Model to use (dall-e-2 or dall-e-3)')
@click.option('--size', '-s', default=None, help='Image size')
@click.option('--quality', '-q', default=None, help='Image quality (standard or hd)')
@click.option('--style', default='vivid', help='Style (vivid or natural) - DALL-E 3 only')
@click.option('--count', '-n', default=1, help='Number of images to generate')
@click.option('--save-dir', '-d', type=click.Path(), help='Directory to save images')
@click.option('--no-download', is_flag=True, help='Don\'t download images locally')
@click.option('--show-cost', is_flag=True, help='Show cost estimation before generating')
@click.pass_context
def generate(ctx, prompt, model, size, quality, style, count, save_dir, no_download, show_cost):
    """Generate images from a text prompt"""
    config = ctx.obj['config']
    
    # Use defaults from config if not specified
    model = model or config.get('default_model')
    size = size or config.get('default_size')
    quality = quality or config.get('default_quality')
    save_dir = Path(save_dir) if save_dir else Path(config.get('save_directory'))
    
    # Validate parameters
    if model not in ['dall-e-2', 'dall-e-3']:
        console.print(f"[red]Invalid model: {model}[/red]")
        return
    
    # Run async function
    asyncio.run(_generate_async(
        ctx.obj['api_key'], config, prompt, model, size, quality, 
        style, count, save_dir, no_download, show_cost
    ))

async def _generate_async(api_key, config, prompt, model, size, quality, 
                         style, count, save_dir, no_download, show_cost):
    """Async implementation of generate command"""
    async with ImageGenerator(api_key, config) as generator:
        # Show cost estimation
        if show_cost or config.get('cost_tracking'):
            cost = generator.estimate_cost(model, size, count)
            console.print(f"[yellow]Estimated cost: ${cost:.3f}[/yellow]")
            if show_cost and not Confirm.ask("Continue?"):
                return
        
        # Prepare prompts
        prompts = [prompt] * count
        
        # Generate images with progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            task = progress.add_task(f"Generating {count} image(s)...", total=count)
            
            def update_progress(completed, total):
                progress.update(task, completed=completed)
            
            results = await generator.generate_batch(
                prompts, model, size, quality, style, update_progress
            )
        
        # Process results
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        if successful:
            console.print(f"\n[green]✓ Generated {len(successful)} image(s)[/green]")
            
            # Save images
            if not no_download:
                save_dir.mkdir(parents=True, exist_ok=True)
                
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console
                ) as progress:
                    task = progress.add_task("Downloading images...", total=len(successful))
                    
                    for i, result in enumerate(successful):
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"dalle_{timestamp}_{i+1}.png"
                        save_path = save_dir / filename
                        
                        if await generator.download_image(result['url'], save_path):
                            console.print(f"  → Saved: {save_path}")
                            
                            # Show revised prompt if different
                            if result.get('revised_prompt') != prompt:
                                console.print(f"    [dim]Revised: {result['revised_prompt']}[/dim]")
                        
                        progress.update(task, advance=1)
        
        if failed:
            console.print(f"\n[red]✗ Failed to generate {len(failed)} image(s)[/red]")
            for result in failed:
                console.print(f"  Error: {result['error']}")

@cli.command()
@click.argument('prompts_file', type=click.Path(exists=True))
@click.option('--model', '-m', default=None, help='Model to use')
@click.option('--size', '-s', default=None, help='Image size')
@click.option('--quality', '-q', default=None, help='Image quality')
@click.option('--concurrent', '-c', default=4, help='Number of concurrent requests')
@click.option('--output-dir', '-o', type=click.Path(), help='Output directory')
@click.pass_context
def batch(ctx, prompts_file, model, size, quality, concurrent, output_dir):
    """Generate images from multiple prompts in a file"""
    config = ctx.obj['config']
    
    # Read prompts
    with open(prompts_file, 'r') as f:
        prompts = [line.strip() for line in f if line.strip()]
    
    if not prompts:
        console.print("[red]No prompts found in file[/red]")
        return
    
    console.print(f"[cyan]Found {len(prompts)} prompts[/cyan]")
    
    # Use defaults
    model = model or config.get('default_model')
    size = size or config.get('default_size')
    quality = quality or config.get('default_quality')
    output_dir = Path(output_dir) if output_dir else Path(config.get('save_directory'))
    
    asyncio.run(_batch_async(
        ctx.obj['api_key'], config, prompts, model, size, quality, 
        concurrent, output_dir
    ))

async def _batch_async(api_key, config, prompts, model, size, quality, 
                      concurrent, output_dir):
    """Async implementation of batch command"""
    async with ImageGenerator(api_key, config) as generator:
        # Estimate total cost
        total_cost = generator.estimate_cost(model, size, len(prompts))
        console.print(f"[yellow]Estimated total cost: ${total_cost:.3f}[/yellow]")
        
        if not Confirm.ask("Continue with batch generation?"):
            return
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Process in batches
        all_results = []
        batch_size = concurrent
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console
        ) as progress:
            task = progress.add_task(f"Processing {len(prompts)} prompts...", total=len(prompts))
            
            for i in range(0, len(prompts), batch_size):
                batch_prompts = prompts[i:i+batch_size]
                
                def update_batch_progress(completed, total):
                    progress.update(task, completed=i+completed)
                
                results = await generator.generate_batch(
                    batch_prompts, model, size, quality, 
                    progress_callback=update_batch_progress
                )
                
                # Save successful results
                for j, result in enumerate(results):
                    if result['success']:
                        prompt_hash = hashlib.md5(batch_prompts[j].encode()).hexdigest()[:8]
                        filename = f"batch_{prompt_hash}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                        save_path = output_dir / filename
                        
                        if await generator.download_image(result['url'], save_path):
                            result['saved_path'] = str(save_path)
                
                all_results.extend(results)
        
        # Summary
        successful = len([r for r in all_results if r['success']])
        console.print(f"\n[green]✓ Successfully generated {successful}/{len(prompts)} images[/green]")
        
        # Save results report
        report_path = output_dir / f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(all_results, f, indent=2)
        console.print(f"[dim]Report saved to: {report_path}[/dim]")

@cli.command()
@click.argument('image_path', type=click.Path(exists=True))
@click.option('--count', '-n', default=1, help='Number of variations')
@click.option('--size', '-s', default='1024x1024', help='Output size')
@click.pass_context
def variations(ctx, image_path, count, size):
    """Create variations of an existing image"""
    asyncio.run(_variations_async(
        ctx.obj['api_key'], ctx.obj['config'], Path(image_path), count, size
    ))

async def _variations_async(api_key, config, image_path, count, size):
    """Async implementation of variations command"""
    async with ImageGenerator(api_key, config) as generator:
        console.print(f"[cyan]Creating {count} variation(s) of {image_path.name}...[/cyan]")
        
        results = await generator.create_variations(image_path, count, size)
        
        save_dir = Path(config.get('save_directory')) / 'variations'
        save_dir.mkdir(parents=True, exist_ok=True)
        
        for i, result in enumerate(results):
            if result['success']:
                filename = f"variation_{image_path.stem}_{i+1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                save_path = save_dir / filename
                
                if await generator.download_image(result['url'], save_path):
                    console.print(f"[green]✓[/green] Saved variation: {save_path}")
            else:
                console.print(f"[red]✗ Error: {result['error']}[/red]")

@cli.command()
@click.argument('image_path', type=click.Path(exists=True))
@click.option('--prompt', '-p', help='What the image should depict')
@click.pass_context
def analyze(ctx, image_path, prompt):
    """Analyze an image using GPT-4 Vision"""
    prompt = prompt or "Describe this image in detail."
    
    asyncio.run(_analyze_async(ctx.obj['api_key'], Path(image_path), prompt))

async def _analyze_async(api_key, image_path, prompt):
    """Async implementation of analyze command"""
    analyzer = VisionAnalyzer(api_key)
    
    with console.status("Analyzing image..."):
        result = await analyzer.analyze_image(image_path, prompt)
    
    console.print(Panel(Markdown(result), title=f"Analysis of {image_path.name}"))

@cli.command()
@click.pass_context
def interactive(ctx):
    """Interactive mode with rich prompts"""
    console.print("[bold cyan]DALL-E Interactive Mode[/bold cyan]")
    console.print("Type 'help' for commands, 'exit' to quit\n")
    
    config = ctx.obj['config']
    api_key = ctx.obj['api_key']
    
    asyncio.run(_interactive_async(api_key, config))

async def _interactive_async(api_key, config):
    """Async implementation of interactive mode"""
    async with ImageGenerator(api_key, config) as generator:
        while True:
            try:
                command = Prompt.ask("\n[bold blue]dalle[/bold blue]")
                
                if command.lower() in ['exit', 'quit', 'q']:
                    break
                elif command.lower() == 'help':
                    console.print("""
[bold]Available commands:[/bold]
  generate <prompt>  - Generate an image
  batch <file>      - Process prompts from file
  cost <count>      - Estimate generation cost
  settings          - Show current settings
                    """)
                elif command.startswith('generate '):
                    prompt = command[9:]
                    model = config.get('default_model')
                    size = config.get('default_size')
                    quality = config.get('default_quality')
                    
                    with console.status("Generating image..."):
                        result = await generator.generate_single(
                            prompt, model, size, quality
                        )
                    
                    if result['success']:
                        console.print(f"[green]✓ Generated![/green] URL: {result['url']}")
                        if result.get('revised_prompt') != prompt:
                            console.print(f"[dim]Revised prompt: {result['revised_prompt']}[/dim]")
                    else:
                        console.print(f"[red]Error: {result['error']}[/red]")
                
                elif command.startswith('cost '):
                    count = int(command[5:])
                    model = config.get('default_model')
                    size = config.get('default_size')
                    cost = generator.estimate_cost(model, size, count)
                    console.print(f"[yellow]Cost for {count} images: ${cost:.3f}[/yellow]")
                
                elif command == 'settings':
                    table = Table(title="Current Settings")
                    table.add_column("Setting", style="cyan")
                    table.add_column("Value", style="green")
                    
                    table.add_row("Model", config.get('default_model'))
                    table.add_row("Size", config.get('default_size'))
                    table.add_row("Quality", config.get('default_quality'))
                    
                    console.print(table)
                
            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'exit' to quit[/yellow]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

if __name__ == '__main__':
    cli()