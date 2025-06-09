#!/usr/bin/env python3
"""
DALL-E 2 CLI - Fixed Interactive Interface
"""
import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime
import base64
import shutil

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import openai
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint
from rich.prompt import Prompt, Confirm
import questionary
from PIL import Image
import requests  # Using requests instead of aiohttp to avoid async issues

console = Console()

class SimpleDalleCLI:
    def __init__(self):
        self.api_key = None
        self.client = None
        self.save_dir = Path.home() / ".dalle2_cli" / "images"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
    def initialize(self):
        """Initialize the CLI application"""
        # Check for API key in environment or ask user
        self.api_key = os.environ.get("OPENAI_API_KEY")
        
        # Try to load from .env file
        env_file = Path.home() / ".dalle2_cli" / ".env"
        if not self.api_key and env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith("OPENAI_API_KEY="):
                        self.api_key = line.strip().split("=", 1)[1]
                        break
        
        if not self.api_key:
            self.api_key = self.setup_api_key()
        
        # Initialize OpenAI client
        self.client = openai.OpenAI(api_key=self.api_key)
        
    def setup_api_key(self):
        """Setup OpenAI API key"""
        console.print("\n[bold yellow]OpenAI API Key Required[/bold yellow]")
        console.print("Get your API key from: https://platform.openai.com/api-keys\n")
        
        api_key = Prompt.ask("Enter your OpenAI API key", password=True)
        
        if api_key:
            # Save to environment file
            env_file = Path.home() / ".dalle2_cli" / ".env"
            env_file.parent.mkdir(exist_ok=True)
            
            with open(env_file, 'w') as f:
                f.write(f"OPENAI_API_KEY={api_key}\n")
            
            console.print("[green]✓ API key saved to ~/.dalle2_cli/.env[/green]")
            console.print("  Add to your shell: export OPENAI_API_KEY='your-key'")
            return api_key
        else:
            console.print("[red]✗ No API key provided[/red]")
            sys.exit(1)
    
    def generate_image(self):
        """Generate image from text prompt"""
        console.print("\n[bold cyan]Generate Image from Text[/bold cyan]")
        
        prompt = questionary.text(
            "Enter your prompt:",
            instruction="(Be descriptive for best results)"
        ).ask()
        
        if not prompt:
            return
        
        # Image settings
        model = questionary.select(
            "Select model:",
            choices=["dall-e-2", "dall-e-3"]
        ).ask()
        
        if model == "dall-e-2":
            sizes = ["256x256", "512x512", "1024x1024"]
        else:  # dall-e-3
            sizes = ["1024x1024", "1024x1792", "1792x1024"]
        
        size = questionary.select("Select image size:", choices=sizes).ask()
        
        quality = "standard"
        style = "natural"
        
        if model == "dall-e-3":
            quality = questionary.select(
                "Select quality:",
                choices=["standard", "hd"]
            ).ask()
            
            style = questionary.select(
                "Select style:",
                choices=["natural", "vivid"]
            ).ask()
        
        n = 1
        if model == "dall-e-2":
            n = int(questionary.text(
                "Number of images to generate:",
                default="1",
                validate=lambda x: x.isdigit() and 1 <= int(x) <= 4
            ).ask())
        
        # Generate
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Generating images...", total=None)
            
            try:
                params = {
                    "model": model,
                    "prompt": prompt,
                    "size": size,
                    "n": n
                }
                
                if model == "dall-e-3":
                    params["quality"] = quality
                    params["style"] = style
                
                response = self.client.images.generate(**params)
                progress.update(task, completed=True)
                
                # Save images
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_subdir = self.save_dir / f"{model}_{timestamp}"
                save_subdir.mkdir(parents=True, exist_ok=True)
                
                # Save prompt
                with open(save_subdir / "prompt.txt", 'w') as f:
                    f.write(f"Prompt: {prompt}\n")
                    f.write(f"Model: {model}\n")
                    f.write(f"Size: {size}\n")
                    if model == "dall-e-3":
                        f.write(f"Quality: {quality}\n")
                        f.write(f"Style: {style}\n")
                
                for i, image_data in enumerate(response.data):
                    # Download and save
                    image_url = image_data.url
                    
                    # Download with requests
                    resp = requests.get(image_url)
                    if resp.status_code == 200:
                        filename = save_subdir / f"image_{i+1}.png"
                        with open(filename, 'wb') as f:
                            f.write(resp.content)
                        
                        console.print(f"[green]✓ Saved: {filename}[/green]")
                        
                        # Show revised prompt for DALL-E 3
                        if model == "dall-e-3" and hasattr(image_data, 'revised_prompt'):
                            console.print(f"[yellow]Revised prompt: {image_data.revised_prompt}[/yellow]")
                
                console.print(f"\n[bold green]Successfully generated {n} image(s)![/bold green]")
                console.print(f"Saved in: {save_subdir}")
                
                if questionary.confirm("Open folder?").ask():
                    os.system(f"xdg-open '{save_subdir}' 2>/dev/null || open '{save_subdir}' 2>/dev/null || explorer.exe '{save_subdir}' 2>/dev/null")
                
            except Exception as e:
                progress.update(task, completed=True)
                console.print(f"[red]Error: {str(e)}[/red]")
    
    def create_variations(self):
        """Create variations of an existing image"""
        console.print("\n[bold cyan]Create Image Variations (DALL-E 2 only)[/bold cyan]")
        
        image_path = questionary.path(
            "Select image file:",
            validate=lambda x: Path(x).exists() and Path(x).suffix.lower() in ['.png', '.jpg', '.jpeg']
        ).ask()
        
        if not image_path:
            return
        
        # Only DALL-E 2 supports variations
        size = questionary.select(
            "Select output size:",
            choices=["256x256", "512x512", "1024x1024"]
        ).ask()
        
        n = int(questionary.text(
            "Number of variations:",
            default="1",
            validate=lambda x: x.isdigit() and 1 <= int(x) <= 4
        ).ask())
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Creating variations...", total=None)
            
            try:
                # Open and prepare image
                with open(image_path, 'rb') as f:
                    response = self.client.images.create_variation(
                        image=f,
                        n=n,
                        size=size
                    )
                
                progress.update(task, completed=True)
                
                # Save variations
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_subdir = self.save_dir / f"variations_{timestamp}"
                save_subdir.mkdir(parents=True, exist_ok=True)
                
                # Copy original
                shutil.copy2(image_path, save_subdir / f"original_{Path(image_path).name}")
                
                for i, image_data in enumerate(response.data):
                    # Download and save
                    image_url = image_data.url
                    
                    resp = requests.get(image_url)
                    if resp.status_code == 200:
                        filename = save_subdir / f"variation_{i+1}.png"
                        with open(filename, 'wb') as f:
                            f.write(resp.content)
                        
                        console.print(f"[green]✓ Saved: {filename}[/green]")
                
                console.print(f"\n[bold green]Successfully created {n} variation(s)![/bold green]")
                console.print(f"Saved in: {save_subdir}")
                
            except Exception as e:
                progress.update(task, completed=True)
                console.print(f"[red]Error: {str(e)}[/red]")
    
    def view_history(self):
        """View generation history"""
        console.print("\n[bold cyan]Generation History[/bold cyan]")
        
        # List all generation folders
        folders = sorted([d for d in self.save_dir.iterdir() if d.is_dir()], reverse=True)
        
        if not folders:
            console.print("[yellow]No generation history found[/yellow]")
            return
        
        table = Table(title="Recent Generations")
        table.add_column("#", style="cyan", width=3)
        table.add_column("Date/Time", style="white")
        table.add_column("Type", style="green")
        table.add_column("Images", style="magenta")
        
        for i, folder in enumerate(folders[:20]):  # Show last 20
            # Parse folder name
            parts = folder.name.split('_')
            gen_type = parts[0]
            
            # Count images
            images = list(folder.glob("*.png")) + list(folder.glob("*.jpg"))
            
            # Get timestamp
            try:
                timestamp = folder.stat().st_mtime
                date_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
            except:
                date_str = folder.name
            
            table.add_row(
                str(i + 1),
                date_str,
                gen_type,
                str(len(images))
            )
        
        console.print(table)
        
        if folders and questionary.confirm("View details of a generation?").ask():
            idx = questionary.text(
                f"Enter number (1-{min(20, len(folders))}):",
                validate=lambda x: x.isdigit() and 1 <= int(x) <= min(20, len(folders))
            ).ask()
            
            if idx:
                folder = folders[int(idx) - 1]
                
                # Show prompt if exists
                prompt_file = folder / "prompt.txt"
                if prompt_file.exists():
                    console.print(f"\n[bold]Generation Details:[/bold]")
                    console.print(prompt_file.read_text())
                
                console.print(f"\n[bold]Folder:[/bold] {folder}")
                
                if questionary.confirm("Open folder?").ask():
                    os.system(f"xdg-open '{folder}' 2>/dev/null || open '{folder}' 2>/dev/null || explorer.exe '{folder}' 2>/dev/null")
    
    def main_menu(self):
        """Main menu loop"""
        self.initialize()
        
        console.print(Panel.fit(
            "[bold cyan]DALL-E CLI[/bold cyan]\n"
            "Simple Interactive Command Line Interface",
            border_style="cyan"
        ))
        
        while True:
            choices = [
                "Generate image from text",
                "Create variations (DALL-E 2 only)",
                "View history",
                "Exit"
            ]
            
            action = questionary.select(
                "\nWhat would you like to do?",
                choices=choices
            ).ask()
            
            if action == "Generate image from text":
                self.generate_image()
            elif action == "Create variations (DALL-E 2 only)":
                self.create_variations()
            elif action == "View history":
                self.view_history()
            elif action == "Exit":
                console.print("\n[yellow]Goodbye![/yellow]")
                break

def main():
    """Main entry point"""
    app = SimpleDalleCLI()
    
    try:
        app.main_menu()  # Not async anymore
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {str(e)}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
