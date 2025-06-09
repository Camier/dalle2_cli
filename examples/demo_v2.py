#!/usr/bin/env python3
"""
Demo script showing DALL-E CLI v2 improvements
"""
import asyncio
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dalle_cli_v2 import ImageGenerator, VisionAnalyzer, DALLEConfig
from core.dalle_api_v2 import BatchProcessor, PromptOptimizer, ImageMetadata
from utils.terminal_image import TerminalImageViewer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

console = Console()

async def demo_improvements():
    """Demonstrate key improvements in v2"""
    config = DALLEConfig()
    api_key = config.get('api_key') or input("Enter OpenAI API key: ")
    
    console.print("[bold cyan]DALL-E CLI v2 Improvements Demo[/bold cyan]\n")
    
    # 1. Async Generation with Progress
    console.print("[yellow]1. Async Generation with Multiple Prompts[/yellow]")
    prompts = [
        "futuristic cityscape with flying cars",
        "serene Japanese garden in autumn",
        "abstract geometric art in vibrant colors"
    ]
    
    async with ImageGenerator(api_key, config) as generator:
        console.print("Generating 3 images concurrently...")
        
        results = []
        async for result in generator.generate_stream(
            prompts, "dall-e-2", "512x512", "standard", max_concurrent=3
        ):
            if result['success']:
                console.print(f"✓ Generated: {result['prompt'][:50]}...")
            else:
                console.print(f"✗ Failed: {result['error']}")
            results.append(result)
    
    # 2. Cost Estimation
    console.print("\n[yellow]2. Cost Tracking and Estimation[/yellow]")
    total_cost = 0.018 * 3  # 512x512 DALL-E 2 images
    
    table = Table(title="Generation Cost Breakdown")
    table.add_column("Model", style="cyan")
    table.add_column("Size", style="magenta")
    table.add_column("Count", style="green")
    table.add_column("Cost per Image", style="yellow")
    table.add_column("Total Cost", style="red")
    
    table.add_row("dall-e-2", "512×512", "3", "$0.018", f"${total_cost:.3f}")
    console.print(table)
    
    # 3. Prompt Enhancement
    console.print("\n[yellow]3. AI-Powered Prompt Enhancement[/yellow]")
    optimizer = PromptOptimizer(api_key)
    
    original = "sunset over mountains"
    console.print(f"Original: {original}")
    
    enhanced = await optimizer.enhance_prompt(original, "photorealistic")
    console.print(f"Enhanced: {enhanced}")
    
    # 4. Batch Processing Demo
    console.print("\n[yellow]4. Batch API for Cost Savings (50% off)[/yellow]")
    batch_processor = BatchProcessor(api_key)
    
    batch_prompts = [
        "minimalist logo design for tech startup",
        "watercolor painting of a lighthouse",
        "retro 80s synthwave landscape"
    ]
    
    console.print("Creating batch job...")
    batch_id = await batch_processor.create_image_batch(
        batch_prompts, model="dall-e-2", size="256x256"
    )
    console.print(f"Batch job created: {batch_id}")
    console.print("[dim]Note: Batch jobs complete within 24 hours[/dim]")
    
    # 5. Vision API Integration
    console.print("\n[yellow]5. Vision API Integration[/yellow]")
    console.print("Analyzing an image with GPT-4 Vision...")
    
    # Create a simple test image for demo
    test_image = Path.home() / ".dalle_cli" / "test_image.png"
    if test_image.exists():
        analyzer = VisionAnalyzer(api_key)
        analysis = await analyzer.analyze_image(
            test_image, 
            "Describe the artistic style and composition"
        )
        console.print(Panel(analysis, title="Image Analysis"))
    else:
        console.print("[dim]No test image found for analysis[/dim]")
    
    # 6. Terminal Image Display
    console.print("\n[yellow]6. Terminal Image Display[/yellow]")
    if results and results[0].get('success'):
        console.print("Displaying image in terminal (ASCII art):")
        # This would show ASCII art of the image
        # TerminalImageViewer.display_image(image_path, method='ascii', width=60)
        console.print("[dim]ASCII art preview would appear here[/dim]")
    
    # 7. Metadata and Search
    console.print("\n[yellow]7. Image Metadata and Search[/yellow]")
    metadata = ImageMetadata()
    
    # Add some sample metadata
    for result in results:
        if result.get('success'):
            metadata.add_image(
                prompt=result['prompt'],
                url=result['url'],
                model="dall-e-2",
                size="512x512",
                quality="standard",
                cost=0.018
            )
    
    stats = metadata.get_stats()
    console.print(f"Total images generated: {stats['total_generated']}")
    console.print(f"Total cost: ${stats['total_cost']:.3f}")
    
    # Search example
    search_results = metadata.search("city")
    if search_results:
        console.print(f"Found {len(search_results)} images matching 'city'")

async def demo_plugin_system():
    """Demonstrate plugin system"""
    console.print("\n[yellow]8. Plugin System[/yellow]")
    
    from core.plugins import PluginManager, create_plugin_template
    
    pm = PluginManager()
    
    # List available plugins
    console.print("Available plugins:")
    plugins = pm.list_plugins()
    
    table = Table()
    table.add_column("Plugin", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Description", style="dim")
    
    for plugin in plugins:
        status = "✓ Loaded" if plugin['loaded'] else "Not loaded"
        table.add_row(plugin['name'], status, plugin['description'])
    
    console.print(table)
    
    # Create plugin template
    console.print("\nCreating plugin template...")
    plugin_dir = Path.home() / ".dalle_cli" / "plugins"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    
    if create_plugin_template("custom_styles", plugin_dir):
        console.print("✓ Created plugin template: custom_styles.py")
        console.print(f"  Location: {plugin_dir / 'custom_styles.py'}")

async def main():
    """Run all demos"""
    try:
        await demo_improvements()
        await demo_plugin_system()
        
        console.print("\n[bold green]✨ DALL-E CLI v2 Demo Complete![/bold green]")
        console.print("\nKey improvements demonstrated:")
        console.print("• Async/concurrent generation")
        console.print("• Cost tracking and batch API (50% savings)")
        console.print("• AI-powered prompt enhancement")
        console.print("• Vision API integration")
        console.print("• Terminal image display")
        console.print("• Plugin system for extensibility")
        console.print("• Rich terminal UI with tables and progress")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

if __name__ == "__main__":
    asyncio.run(main())