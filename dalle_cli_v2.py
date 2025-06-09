#!/usr/bin/env python3
"""
DALL-E CLI v2 - Modern, feature-rich command line interface for DALL-E image generation
"""
import os
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import base64
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib

# Third party imports
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.columns import Columns
from rich import box
import questionary
from PIL import Image
import openai
from openai import OpenAI, AsyncOpenAI
import httpx
import aiofiles
import aiohttp

# Local imports
sys.path.insert(0, str(Path(__file__).parent))
from core.security import SecurityManager
from core.config_manager import ConfigManager
from data.database import DatabaseManager

# Initialize Typer app with rich markup
app = typer.Typer(
    rich_markup_mode="rich",
    help="🎨 [bold cyan]DALL-E CLI v2[/bold cyan] - Generate stunning AI images from your terminal"
)

# Console for rich output
console = Console()

# Global settings
MODELS = {
    "dall-e-2": {
        "sizes": ["256x256", "512x512", "1024x1024"],
        "default_size": "1024x1024",
        "max_prompt": 1000,
        "features": ["variations", "edits"]
    },
    "dall-e-3": {
        "sizes": ["1024x1024", "1024x1792", "1792x1024"],
        "default_size": "1024x1024",
        "max_prompt": 4000,
        "features": ["hd", "style"]
    }
}

class DalleCliV2:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.security_manager = SecurityManager()
        self.db_manager = DatabaseManager(Path.home() / ".dalle2_cli" / "database.db")
        self.client = None
        self.async_client = None
        self.save_dir = Path.home() / ".dalle2_cli" / "images"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
    def initialize_client(self, api_key: str):
        """Initialize OpenAI clients"""
        self.client = OpenAI(api_key=api_key)
        self.async_client = AsyncOpenAI(api_key=api_key)
        
    def get_image_hash(self, image_path: Path) -> str:
        """Get SHA256 hash of image for deduplication"""
        with open(image_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

cli_instance = DalleCliV2()

# Callback for global options
@app.callback()
def main(
    ctx: typer.Context,
    api_key: Optional[str] = typer.Option(None, "--api-key", "-k", help="OpenAI API key"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    version: bool = typer.Option(None, "--version", callback=lambda x: _version_callback(x), is_eager=True)
):
    """
    🎨 [bold cyan]DALL-E CLI v2[/bold cyan] - Generate stunning AI images from your terminal
    
    [yellow]Features:[/yellow]
    • Generate images with DALL-E 2 or DALL-E 3
    • Create variations of existing images
    • Edit images with AI-powered inpainting
    • Batch processing with progress tracking
    • Gallery view with metadata
    • Export/import image collections
    • Real-time streaming generation
    """
    if ctx.invoked_subcommand is None:
        # Show interactive menu if no command specified
        interactive_menu()
        return
        
    # Set up API key
    if api_key:
        cli_instance.initialize_client(api_key)
    else:
        stored_key = cli_instance.security_manager.load_api_key()
        if stored_key:
            cli_instance.initialize_client(stored_key)
        else:
            console.print("[red]No API key found![/red]")
            console.print("Please run: [cyan]dalle setup[/cyan] or provide --api-key")
            raise typer.Exit(1)

def _version_callback(value: bool):
    if value:
        console.print("[bold cyan]DALL-E CLI v2.0.0[/bold cyan]")
        console.print("Built with ❤️ using Typer and Rich")
        raise typer.Exit()

@app.command()
def generate(
    prompt: str = typer.Argument(..., help="The prompt to generate images from"),
    model: str = typer.Option("dall-e-3", "--model", "-m", help="Model to use"),
    size: Optional[str] = typer.Option(None, "--size", "-s", help="Image size"),
    quality: str = typer.Option("standard", "--quality", "-q", help="Image quality (dall-e-3 only)"),
    style: str = typer.Option("vivid", "--style", help="Image style (dall-e-3 only)"),
    n: int = typer.Option(1, "--number", "-n", help="Number of images to generate"),
    batch: bool = typer.Option(False, "--batch", "-b", help="Enable batch mode for multiple variations"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory")
):
    """
    🎨 Generate images from text prompts
    
    [bold]Examples:[/bold]
    $ dalle generate "a serene landscape at sunset"
    $ dalle generate "futuristic city" --model dall-e-3 --quality hd
    $ dalle generate "abstract art" --size 1792x1024 --n 4
    """
    # Validate model
    if model not in MODELS:
        console.print(f"[red]Invalid model: {model}[/red]")
        console.print(f"Available models: {', '.join(MODELS.keys())}")
        raise typer.Exit(1)
        
    # Set default size if not specified
    if not size:
        size = MODELS[model]["default_size"]
    elif size not in MODELS[model]["sizes"]:
        console.print(f"[red]Invalid size for {model}: {size}[/red]")
        console.print(f"Available sizes: {', '.join(MODELS[model]['sizes'])}")
        raise typer.Exit(1)
    
    # Create output directory
    output_dir = output or cli_instance.save_dir / datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Show generation panel
    panel = Panel(
        f"[bold]Prompt:[/bold] {prompt}\n"
        f"[bold]Model:[/bold] {model}\n"
        f"[bold]Size:[/bold] {size}\n"
        f"[bold]Quality:[/bold] {quality}\n"
        f"[bold]Images:[/bold] {n}",
        title="🎨 Generation Settings",
        border_style="cyan"
    )
    console.print(panel)
    
    # Generate images with progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        if batch and n > 1:
            # Batch mode - generate in parallel
            asyncio.run(_batch_generate(prompt, model, size, quality, style, n, output_dir, progress))
        else:
            # Sequential generation
            task = progress.add_task(f"[cyan]Generating {n} images...", total=n)
            
            for i in range(n):
                try:
                    response = _generate_single_image(prompt, model, size, quality, style)
                    
                    # Save image
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"dalle_{model}_{timestamp}_{i+1}.png"
                    filepath = output_dir / filename
                    
                    _save_image_from_url(response.data[0].url, filepath)
                    
                    # Store in database
                    cli_instance.db_manager.add_generation(
                        prompt=prompt,
                        model=model,
                        size=size,
                        quality=quality,
                        style=style if model == "dall-e-3" else None,
                        image_path=str(filepath),
                        revised_prompt=getattr(response.data[0], 'revised_prompt', None)
                    )
                    
                    progress.update(task, advance=1)
                    console.print(f"✅ Saved: [green]{filepath}[/green]")
                    
                except Exception as e:
                    console.print(f"[red]Error generating image {i+1}: {e}[/red]")
    
    # Show summary
    console.print(f"\n✨ Generated {n} images in [cyan]{output_dir}[/cyan]")

async def _batch_generate(prompt, model, size, quality, style, n, output_dir, progress):
    """Generate multiple images in parallel"""
    task = progress.add_task(f"[cyan]Generating {n} images in parallel...", total=n)
    
    async def generate_one(index):
        try:
            if model == "dall-e-3":
                response = await cli_instance.async_client.images.generate(
                    model=model,
                    prompt=prompt,
                    size=size,
                    quality=quality,
                    style=style,
                    n=1
                )
            else:
                response = await cli_instance.async_client.images.generate(
                    model=model,
                    prompt=prompt,
                    size=size,
                    n=1
                )
            
            # Save image
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"dalle_{model}_{timestamp}_{index+1}.png"
            filepath = output_dir / filename
            
            await _async_save_image(response.data[0].url, filepath)
            
            # Store in database
            cli_instance.db_manager.add_generation(
                prompt=prompt,
                model=model,
                size=size,
                quality=quality,
                style=style if model == "dall-e-3" else None,
                image_path=str(filepath),
                revised_prompt=getattr(response.data[0], 'revised_prompt', None)
            )
            
            progress.update(task, advance=1)
            return filepath
            
        except Exception as e:
            console.print(f"[red]Error in batch {index+1}: {e}[/red]")
            return None
    
    # Create tasks
    tasks = [generate_one(i) for i in range(n)]
    results = await asyncio.gather(*tasks)
    
    # Report results
    successful = [r for r in results if r is not None]
    console.print(f"\n✅ Successfully generated {len(successful)}/{n} images")

def _generate_single_image(prompt, model, size, quality, style):
    """Generate a single image"""
    if model == "dall-e-3":
        return cli_instance.client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            quality=quality,
            style=style,
            n=1
        )
    else:
        return cli_instance.client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            n=1
        )

def _save_image_from_url(url: str, filepath: Path):
    """Download and save image from URL"""
    response = httpx.get(url)
    response.raise_for_status()
    
    with open(filepath, 'wb') as f:
        f.write(response.content)

async def _async_save_image(url: str, filepath: Path):
    """Async download and save image"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            content = await response.read()
            async with aiofiles.open(filepath, 'wb') as f:
                await f.write(content)

@app.command()
def variations(
    image_path: Path = typer.Argument(..., help="Path to the source image"),
    n: int = typer.Option(2, "--number", "-n", help="Number of variations"),
    size: Optional[str] = typer.Option(None, "--size", "-s", help="Output size"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory")
):
    """
    🔄 Create variations of an existing image
    
    [bold]Example:[/bold]
    $ dalle variations image.png --n 4
    """
    if not image_path.exists():
        console.print(f"[red]Image not found: {image_path}[/red]")
        raise typer.Exit(1)
    
    # Open and prepare image
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()
    
    # Create output directory
    output_dir = output or cli_instance.save_dir / f"variations_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    console.print(f"🔄 Creating {n} variations of [cyan]{image_path.name}[/cyan]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Generating variations...", total=n)
        
        try:
            response = cli_instance.client.images.create_variation(
                image=image_data,
                n=n,
                size=size or "1024x1024"
            )
            
            for i, image_data in enumerate(response.data):
                filename = f"variation_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i+1}.png"
                filepath = output_dir / filename
                
                _save_image_from_url(image_data.url, filepath)
                progress.update(task, advance=1)
                console.print(f"✅ Saved: [green]{filepath}[/green]")
                
        except Exception as e:
            console.print(f"[red]Error creating variations: {e}[/red]")
            raise typer.Exit(1)
    
    console.print(f"\n✨ Created {n} variations in [cyan]{output_dir}[/cyan]")

@app.command()
def edit(
    image_path: Path = typer.Argument(..., help="Path to the image to edit"),
    mask_path: Path = typer.Argument(..., help="Path to the mask image"),
    prompt: str = typer.Argument(..., help="Description of the edit"),
    n: int = typer.Option(1, "--number", "-n", help="Number of edits"),
    size: Optional[str] = typer.Option(None, "--size", "-s", help="Output size")
):
    """
    ✏️ Edit images with AI-powered inpainting
    
    [bold]Example:[/bold]
    $ dalle edit image.png mask.png "add a rainbow in the sky"
    """
    if not image_path.exists() or not mask_path.exists():
        console.print("[red]Image or mask file not found![/red]")
        raise typer.Exit(1)
    
    # Implementation would follow similar pattern to variations
    console.print("✏️ Edit functionality coming soon!")

@app.command()
def gallery(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of images to show"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Filter by model"),
    date: Optional[str] = typer.Option(None, "--date", "-d", help="Filter by date (YYYY-MM-DD)")
):
    """
    🖼️ View your generated images in a gallery
    
    [bold]Example:[/bold]
    $ dalle gallery --limit 20
    $ dalle gallery --model dall-e-3 --date 2024-01-09
    """
    # Get recent generations from database
    generations = cli_instance.db_manager.get_recent_generations(limit)
    
    if not generations:
        console.print("[yellow]No images found in gallery[/yellow]")
        return
    
    # Create gallery table
    table = Table(title="🖼️ Image Gallery", box=box.ROUNDED)
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Prompt", style="white", width=40)
    table.add_column("Model", style="green", width=10)
    table.add_column("Size", style="blue", width=12)
    table.add_column("Date", style="yellow", width=20)
    table.add_column("Path", style="magenta", width=30)
    
    for gen in generations:
        # Truncate prompt if too long
        prompt = gen.prompt[:37] + "..." if len(gen.prompt) > 40 else gen.prompt
        
        table.add_row(
            str(gen.id),
            prompt,
            gen.model,
            gen.size,
            gen.created_at.strftime("%Y-%m-%d %H:%M"),
            Path(gen.image_path).name
        )
    
    console.print(table)
    
    # Offer to view specific image
    if Confirm.ask("\n[cyan]View a specific image?[/cyan]"):
        image_id = Prompt.ask("Enter image ID")
        try:
            image_id = int(image_id)
            gen = next((g for g in generations if g.id == image_id), None)
            if gen and Path(gen.image_path).exists():
                Image.open(gen.image_path).show()
                
                # Show full details
                details = Panel(
                    f"[bold]Prompt:[/bold] {gen.prompt}\n"
                    f"[bold]Model:[/bold] {gen.model}\n"
                    f"[bold]Size:[/bold] {gen.size}\n"
                    f"[bold]Quality:[/bold] {gen.quality}\n"
                    f"[bold]Created:[/bold] {gen.created_at}\n"
                    f"[bold]Path:[/bold] {gen.image_path}",
                    title="📋 Image Details",
                    border_style="cyan"
                )
                console.print(details)
            else:
                console.print("[red]Image not found![/red]")
        except ValueError:
            console.print("[red]Invalid ID![/red]")

@app.command()
def setup():
    """
    ⚙️ Configure DALL-E CLI settings
    """
    console.print(Panel("⚙️ [bold cyan]DALL-E CLI Setup[/bold cyan]", expand=False))
    
    # API Key setup
    if Confirm.ask("\n[cyan]Configure OpenAI API key?[/cyan]"):
        api_key = Prompt.ask("Enter your OpenAI API key", password=True)
        cli_instance.security_manager.save_api_key(api_key)
        console.print("✅ API key saved securely")
    
    # Default settings
    if Confirm.ask("\n[cyan]Configure default settings?[/cyan]"):
        settings = {}
        
        # Default model
        model_choices = list(MODELS.keys())
        settings['default_model'] = questionary.select(
            "Default model:",
            choices=model_choices,
            default="dall-e-3"
        ).ask()
        
        # Default size
        size_choices = MODELS[settings['default_model']]['sizes']
        settings['default_size'] = questionary.select(
            "Default size:",
            choices=size_choices,
            default=MODELS[settings['default_model']]['default_size']
        ).ask()
        
        # Default quality for DALL-E 3
        if settings['default_model'] == 'dall-e-3':
            settings['default_quality'] = questionary.select(
                "Default quality:",
                choices=['standard', 'hd'],
                default='standard'
            ).ask()
            
            settings['default_style'] = questionary.select(
                "Default style:",
                choices=['vivid', 'natural'],
                default='vivid'
            ).ask()
        
        # Save settings
        cli_instance.config_manager.update_config(settings)
        console.print("✅ Settings saved")
    
    console.print("\n✨ Setup complete! Run [cyan]dalle --help[/cyan] to get started.")

@app.command()
def export(
    output: Path = typer.Argument(..., help="Output file path (JSON or ZIP)"),
    format: str = typer.Option("json", "--format", "-f", help="Export format (json/zip)"),
    include_images: bool = typer.Option(False, "--include-images", "-i", help="Include image files (zip only)")
):
    """
    📤 Export your image collection
    
    [bold]Example:[/bold]
    $ dalle export collection.json
    $ dalle export backup.zip --include-images
    """
    console.print(f"📤 Exporting collection to [cyan]{output}[/cyan]")
    
    # Get all generations
    generations = cli_instance.db_manager.get_all_generations()
    
    if format == "json":
        # Export metadata only
        data = []
        for gen in generations:
            data.append({
                'id': gen.id,
                'prompt': gen.prompt,
                'model': gen.model,
                'size': gen.size,
                'quality': gen.quality,
                'style': gen.style,
                'image_path': gen.image_path,
                'created_at': gen.created_at.isoformat(),
                'revised_prompt': gen.revised_prompt
            })
        
        with open(output, 'w') as f:
            json.dump(data, f, indent=2)
        
        console.print(f"✅ Exported {len(data)} images metadata")
    
    elif format == "zip":
        import zipfile
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Creating archive...", total=len(generations))
            
            with zipfile.ZipFile(output, 'w') as zf:
                # Add metadata
                metadata = []
                for gen in generations:
                    metadata.append({
                        'id': gen.id,
                        'prompt': gen.prompt,
                        'model': gen.model,
                        'size': gen.size,
                        'quality': gen.quality,
                        'style': gen.style,
                        'image_path': gen.image_path,
                        'created_at': gen.created_at.isoformat(),
                        'revised_prompt': gen.revised_prompt
                    })
                    
                    # Add image if requested and exists
                    if include_images and Path(gen.image_path).exists():
                        zf.write(gen.image_path, f"images/{Path(gen.image_path).name}")
                    
                    progress.update(task, advance=1)
                
                # Write metadata
                zf.writestr('metadata.json', json.dumps(metadata, indent=2))
        
        console.print(f"✅ Exported {len(generations)} images to archive")

def interactive_menu():
    """Show interactive menu when no command is specified"""
    console.print(Panel("🎨 [bold cyan]DALL-E CLI v2[/bold cyan]", expand=False))
    
    choices = [
        "🎨 Generate new images",
        "🔄 Create variations",
        "✏️  Edit images",
        "🖼️  View gallery",
        "📤 Export collection",
        "⚙️  Setup/Settings",
        "❌ Exit"
    ]
    
    choice = questionary.select(
        "What would you like to do?",
        choices=choices
    ).ask()
    
    if "Generate" in choice:
        # Interactive generation
        prompt = Prompt.ask("Enter your prompt")
        model = questionary.select("Select model:", choices=list(MODELS.keys())).ask()
        
        # Use typer context to run command
        ctx = typer.Context(command=generate)
        ctx.invoke(generate, prompt=prompt, model=model)
        
    elif "variations" in choice:
        console.print("[cyan]Run: dalle variations <image_path>[/cyan]")
    elif "Edit" in choice:
        console.print("[cyan]Run: dalle edit <image_path> <mask_path> <prompt>[/cyan]")
    elif "gallery" in choice:
        ctx = typer.Context(command=gallery)
        ctx.invoke(gallery)
    elif "Export" in choice:
        console.print("[cyan]Run: dalle export <output_path>[/cyan]")
    elif "Setup" in choice:
        ctx = typer.Context(command=setup)
        ctx.invoke(setup)

if __name__ == "__main__":
    app()