#!/usr/bin/env python3
"""
DALL-E 2 CLI - Interactive Command Line Interface
"""
import os
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import base64

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import questionary
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich import print as rprint
import click
from PIL import Image

from core.security import SecurityManager
from core.config_manager import ConfigManager
from core.dalle_api import DALLEAPIManager, GenerationRequest, VariationRequest, EditRequest
from data.database import DatabaseManager, GenerationRecord, TemplateRecord
from utils.logger import logger

console = Console()

class DalleCLI:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.security_manager = SecurityManager()
        self.db_manager = DatabaseManager(Path.home() / ".dalle2_cli" / "database.db")
        self.api_manager = None
        self.api_key = None
        
    async def initialize(self):
        """Initialize the CLI application"""
        # Check for API key
        self.api_key = self.security_manager.load_api_key()
        if not self.api_key:
            self.api_key = await self.setup_api_key()
        
        # Initialize API manager
        self.api_manager = DALLEAPIManager(self.api_key)
        
    async def setup_api_key(self):
        """Setup OpenAI API key"""
        console.print("\n[bold yellow]OpenAI API Key Required[/bold yellow]")
        console.print("Get your API key from: https://platform.openai.com/api-keys\n")
        
        api_key = Prompt.ask("Enter your OpenAI API key", password=True)
        
        if api_key:
            self.security_manager.save_api_key(api_key)
            console.print("[green]✓ API key saved securely[/green]")
            return api_key
        else:
            console.print("[red]✗ No API key provided[/red]")
            sys.exit(1)
    
    async def generate_image(self):
        """Generate image from text prompt"""
        console.print("\n[bold cyan]Generate Image from Text[/bold cyan]")
        
        prompt = questionary.text(
            "Enter your prompt:",
            instruction="(Be descriptive for best results)"
        ).ask()
        
        if not prompt:
            return
        
        # Image settings
        size = questionary.select(
            "Select image size:",
            choices=["1024x1024", "1024x1792", "1792x1024"]
        ).ask()
        
        quality = questionary.select(
            "Select quality:",
            choices=["standard", "hd"]
        ).ask()
        
        style = questionary.select(
            "Select style:",
            choices=["natural", "vivid"]
        ).ask()
        
        n = int(questionary.text(
            "Number of images to generate:",
            default="1",
            validate=lambda x: x.isdigit() and 1 <= int(x) <= 4
        ).ask())
        
        # Generate
        request = GenerationRequest(
            prompt=prompt,
            size=size,
            quality=quality,
            style=style,
            n=n
        )
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Generating images...", total=None)
            
            try:
                results = await self.api_manager.generate_images(request)
                progress.update(task, completed=True)
                
                # Save images
                save_dir = Path("generated_images") / datetime.now().strftime("%Y%m%d_%H%M%S")
                save_dir.mkdir(parents=True, exist_ok=True)
                
                for i, image_data in enumerate(results):
                    if image_data.get('url'):
                        # Download and save
                        import aiohttp
                        async with aiohttp.ClientSession() as session:
                            async with session.get(image_data['url']) as resp:
                                content = await resp.read()
                                
                                filename = save_dir / f"image_{i+1}.png"
                                with open(filename, 'wb') as f:
                                    f.write(content)
                                
                                console.print(f"[green]✓ Saved: {filename}[/green]")
                                
                                # Show preview if possible
                                if questionary.confirm("Open image?").ask():
                                    os.system(f"xdg-open {filename} 2>/dev/null || open {filename} 2>/dev/null")
                
                # Save to database
                record = GenerationRecord(
                    prompt=prompt,
                    size=size,
                    quality=quality,
                    style=style,
                    n=n,
                    timestamp=datetime.now().isoformat(),
                    images_path=str(save_dir)
                )
                self.db_manager.add_generation(record)
                
                console.print(f"\n[bold green]Successfully generated {n} image(s)![/bold green]")
                
            except Exception as e:
                progress.update(task, completed=True)
                console.print(f"[red]Error: {str(e)}[/red]")
    
    async def create_variations(self):
        """Create variations of an existing image"""
        console.print("\n[bold cyan]Create Image Variations[/bold cyan]")
        
        image_path = questionary.path(
            "Select image file:",
            validate=lambda x: Path(x).exists() and Path(x).suffix.lower() in ['.png', '.jpg', '.jpeg']
        ).ask()
        
        if not image_path:
            return
        
        size = questionary.select(
            "Select output size:",
            choices=["1024x1024", "1024x1792", "1792x1024"]
        ).ask()
        
        n = int(questionary.text(
            "Number of variations:",
            default="1",
            validate=lambda x: x.isdigit() and 1 <= int(x) <= 4
        ).ask())
        
        request = VariationRequest(
            image_path=image_path,
            size=size,
            n=n
        )
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Creating variations...", total=None)
            
            try:
                results = await self.api_manager.create_variations(request)
                progress.update(task, completed=True)
                
                # Save variations
                save_dir = Path("variations") / datetime.now().strftime("%Y%m%d_%H%M%S")
                save_dir.mkdir(parents=True, exist_ok=True)
                
                for i, image_data in enumerate(results):
                    if image_data.get('url'):
                        import aiohttp
                        async with aiohttp.ClientSession() as session:
                            async with session.get(image_data['url']) as resp:
                                content = await resp.read()
                                
                                filename = save_dir / f"variation_{i+1}.png"
                                with open(filename, 'wb') as f:
                                    f.write(content)
                                
                                console.print(f"[green]✓ Saved: {filename}[/green]")
                
                console.print(f"\n[bold green]Successfully created {n} variation(s)![/bold green]")
                
            except Exception as e:
                progress.update(task, completed=True)
                console.print(f"[red]Error: {str(e)}[/red]")
    
    async def view_history(self):
        """View generation history"""
        console.print("\n[bold cyan]Generation History[/bold cyan]")
        
        history = self.db_manager.get_all_generations()
        
        if not history:
            console.print("[yellow]No generation history found[/yellow]")
            return
        
        table = Table(title="Recent Generations")
        table.add_column("Date", style="cyan")
        table.add_column("Prompt", style="white", max_width=50)
        table.add_column("Size", style="green")
        table.add_column("Quality", style="yellow")
        table.add_column("Images", style="magenta")
        
        for record in history[-10:]:  # Show last 10
            date = datetime.fromisoformat(record.timestamp).strftime("%Y-%m-%d %H:%M")
            prompt = record.prompt[:47] + "..." if len(record.prompt) > 50 else record.prompt
            table.add_row(
                date,
                prompt,
                record.size,
                record.quality,
                str(record.n)
            )
        
        console.print(table)
        
        if questionary.confirm("View full details of a generation?").ask():
            idx = questionary.text(
                "Enter row number (1-10):",
                validate=lambda x: x.isdigit() and 1 <= int(x) <= min(10, len(history))
            ).ask()
            
            if idx:
                record = history[-(int(idx))]
                console.print(f"\n[bold]Full Prompt:[/bold] {record.prompt}")
                console.print(f"[bold]Images saved in:[/bold] {record.images_path}")
    
    async def manage_templates(self):
        """Manage prompt templates"""
        console.print("\n[bold cyan]Prompt Templates[/bold cyan]")
        
        choices = [
            "View templates",
            "Create new template",
            "Delete template",
            "Back"
        ]
        
        action = questionary.select("Choose action:", choices=choices).ask()
        
        if action == "View templates":
            templates = self.db_manager.get_all_templates()
            if not templates:
                console.print("[yellow]No templates found[/yellow]")
            else:
                table = Table(title="Saved Templates")
                table.add_column("Name", style="cyan")
                table.add_column("Prompt", style="white", max_width=60)
                
                for template in templates:
                    prompt = template.prompt[:57] + "..." if len(template.prompt) > 60 else template.prompt
                    table.add_row(template.name, prompt)
                
                console.print(table)
        
        elif action == "Create new template":
            name = questionary.text("Template name:").ask()
            prompt = questionary.text("Template prompt:").ask()
            
            if name and prompt:
                template = TemplateRecord(name=name, prompt=prompt)
                self.db_manager.add_template(template)
                console.print(f"[green]✓ Template '{name}' saved[/green]")
        
        elif action == "Delete template":
            templates = self.db_manager.get_all_templates()
            if templates:
                choices = [f"{t.name}: {t.prompt[:50]}..." for t in templates]
                to_delete = questionary.select("Select template to delete:", choices=choices).ask()
                
                if to_delete and questionary.confirm("Are you sure?").ask():
                    idx = choices.index(to_delete)
                    self.db_manager.delete_template(templates[idx].id)
                    console.print("[green]✓ Template deleted[/green]")
    
    async def settings(self):
        """Manage settings"""
        console.print("\n[bold cyan]Settings[/bold cyan]")
        
        choices = [
            "Change API key",
            "View current settings",
            "Back"
        ]
        
        action = questionary.select("Choose action:", choices=choices).ask()
        
        if action == "Change API key":
            await self.setup_api_key()
        
        elif action == "View current settings":
            settings = {
                "API Key": "***" + self.api_key[-4:] if self.api_key else "Not set",
                "Database": str(self.db_manager.db_path),
                "Config": str(self.config_manager.config_path)
            }
            
            table = Table(title="Current Settings")
            table.add_column("Setting", style="cyan")
            table.add_column("Value", style="white")
            
            for key, value in settings.items():
                table.add_row(key, value)
            
            console.print(table)
    
    async def main_menu(self):
        """Main menu loop"""
        await self.initialize()
        
        console.print(Panel.fit(
            "[bold cyan]DALL-E 2 CLI[/bold cyan]\n"
            "Interactive Command Line Interface",
            border_style="cyan"
        ))
        
        while True:
            choices = [
                "Generate image from text",
                "Create variations",
                "View history",
                "Manage templates",
                "Settings",
                "Exit"
            ]
            
            action = questionary.select(
                "\nWhat would you like to do?",
                choices=choices
            ).ask()
            
            if action == "Generate image from text":
                await self.generate_image()
            elif action == "Create variations":
                await self.create_variations()
            elif action == "View history":
                await self.view_history()
            elif action == "Manage templates":
                await self.manage_templates()
            elif action == "Settings":
                await self.settings()
            elif action == "Exit":
                console.print("\n[yellow]Goodbye![/yellow]")
                break

@click.command()
@click.option('--generate', '-g', help='Quick generate with prompt')
@click.option('--variations', '-v', help='Create variations of image file')
@click.option('--history', '-h', is_flag=True, help='Show generation history')
async def cli(generate, variations, history):
    """DALL-E 2 CLI - Interactive Command Line Interface"""
    app = DalleCLI()
    
    if generate:
        # Quick generation mode
        await app.initialize()
        request = GenerationRequest(prompt=generate)
        console.print(f"Generating image for: [cyan]{generate}[/cyan]")
        # ... implement quick generation

def run_cli():
    """Wrapper to run async CLI with click"""
    @click.command()
    @click.option('--generate', '-g', help='Quick generate with prompt')
    @click.option('--variations', '-v', help='Create variations of image file')
    @click.option('--history', '-h', is_flag=True, help='Show generation history')
    def cli(generate, variations, history):
        """DALL-E 2 CLI - Interactive Command Line Interface"""
        app = DalleCLI()
        
        async def async_main():
            if generate:
                # Quick generation mode
                await app.initialize()
                request = GenerationRequest(prompt=generate)
                console.print(f"Generating image for: [cyan]{generate}[/cyan]")
                # ... implement quick generation
            elif variations:
                # Quick variations mode
                await app.initialize()
                # ... implement quick variations
            elif history:
                # Show history
                await app.initialize()
                await app.view_history()
            else:
                # Interactive mode
                await app.main_menu()
        
        asyncio.run(async_main())
    
    return cli

if __name__ == "__main__":
    try:
        cli_func = run_cli()
        cli_func()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {str(e)}[/red]")
        import traceback
        traceback.print_exc()
