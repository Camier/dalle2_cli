#!/usr/bin/env python3
"""
DALL-E 2 CLI Enhanced - Generate unlimited images at max resolution
Bypasses the 4-image API limit by making multiple requests
"""
import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime
import base64
import shutil
import time
import math

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import openai
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import print as rprint
from rich.prompt import Prompt, Confirm
import questionary
from PIL import Image
import requests

console = Console()

class EnhancedDalleCLI:
    def __init__(self):
        self.api_key = None
        self.client = None
        self.save_dir = Path.home() / ".dalle2_cli" / "images"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        # Max resolutions for each model
        self.MAX_RESOLUTIONS = {
            "dall-e-2": "1024x1024",
            "dall-e-3": "1024x1024"  # Can also be 1024x1792 or 1792x1024
        }
        
        # API limits
        self.MAX_PER_REQUEST = {
            "dall-e-2": 4,
            "dall-e-3": 1
        }
        
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
            return api_key
        else:
            console.print("[red]✗ No API key provided[/red]")
            sys.exit(1)
    
    def generate_image_batch(self):
        """Generate multiple images with automatic max resolution"""
        console.print("\n[bold cyan]Generate Images - Enhanced Mode[/bold cyan]")
        console.print("[dim]Automatic max resolution + unlimited images[/dim]\n")
        
        prompt = questionary.text(
            "Enter your prompt:",
            instruction="(Be descriptive for best results)"
        ).ask()
        
        if not prompt:
            return
        
        # Model selection
        model = questionary.select(
            "Select model:",
            choices=[
                "dall-e-2 (Faster, supports up to 4 per request)",
                "dall-e-3 (Better quality, 1 per request)"
            ]
        ).ask()
        
        model = "dall-e-2" if "dall-e-2" in model else "dall-e-3"
        
        # Number of images
        default_num = "10" if model == "dall-e-2" else "5"
        num_images = int(questionary.text(
            f"Number of images to generate:",
            default=default_num,
            validate=lambda x: x.isdigit() and 1 <= int(x) <= 100
        ).ask())
        
        # Size selection - default to max, but allow options
        if model == "dall-e-2":
            sizes = ["1024x1024 (Max)", "512x512", "256x256"]
        else:
            sizes = ["1024x1024 (Square)", "1024x1792 (Portrait)", "1792x1024 (Landscape)"]
        
        size_choice = questionary.select(
            "Select size:",
            choices=sizes
        ).ask()
        
        size = size_choice.split()[0]  # Extract just the size
        
        # Quality and style for DALL-E 3
        quality = "standard"
        style = "natural"
        
        if model == "dall-e-3":
            quality = questionary.select(
                "Select quality:",
                choices=["hd (Best quality, slower)", "standard (Faster)"]
            ).ask().split()[0]
            
            style = questionary.select(
                "Select style:",
                choices=["natural", "vivid"]
            ).ask()
        
        # Calculate batches needed
        max_per_request = self.MAX_PER_REQUEST[model]
        num_batches = math.ceil(num_images / max_per_request)
        
        console.print(f"\n[yellow]Generating {num_images} images in {num_batches} batch(es)...[/yellow]")
        
        # Create save directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_subdir = self.save_dir / f"{model}_batch_{timestamp}"
        save_subdir.mkdir(parents=True, exist_ok=True)
        
        # Save generation info
        with open(save_subdir / "generation_info.txt", 'w') as f:
            f.write(f"Prompt: {prompt}\n")
            f.write(f"Model: {model}\n")
            f.write(f"Total Images: {num_images}\n")
            f.write(f"Size: {size}\n")
            if model == "dall-e-3":
                f.write(f"Quality: {quality}\n")
                f.write(f"Style: {style}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Generate images in batches
        all_images = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            
            main_task = progress.add_task(
                f"Generating {num_images} images...", 
                total=num_images
            )
            
            image_count = 0
            
            for batch_num in range(num_batches):
                # Calculate images for this batch
                remaining = num_images - image_count
                batch_size = min(remaining, max_per_request)
                
                progress.update(
                    main_task, 
                    description=f"Batch {batch_num + 1}/{num_batches} ({batch_size} images)..."
                )
                
                try:
                    # Generate batch
                    params = {
                        "model": model,
                        "prompt": prompt,
                        "size": size,
                        "n": batch_size
                    }
                    
                    if model == "dall-e-3":
                        params["quality"] = quality
                        params["style"] = style
                        # DALL-E 3 only supports n=1, so we need multiple calls
                        for i in range(batch_size):
                            response = self.client.images.generate(**{**params, "n": 1})
                            
                            for image_data in response.data:
                                image_count += 1
                                
                                # Download and save
                                image_url = image_data.url
                                resp = requests.get(image_url)
                                
                                if resp.status_code == 200:
                                    filename = save_subdir / f"image_{image_count:03d}.png"
                                    with open(filename, 'wb') as f:
                                        f.write(resp.content)
                                    
                                    all_images.append(filename)
                                    
                                    # Save revised prompt if available
                                    if hasattr(image_data, 'revised_prompt'):
                                        with open(save_subdir / f"revised_prompt_{image_count:03d}.txt", 'w') as f:
                                            f.write(image_data.revised_prompt)
                                
                                progress.update(main_task, advance=1)
                    else:
                        # DALL-E 2 can handle multiple images per request
                        response = self.client.images.generate(**params)
                        
                        for i, image_data in enumerate(response.data):
                            image_count += 1
                            
                            # Download and save
                            image_url = image_data.url
                            resp = requests.get(image_url)
                            
                            if resp.status_code == 200:
                                filename = save_subdir / f"image_{image_count:03d}.png"
                                with open(filename, 'wb') as f:
                                    f.write(resp.content)
                                
                                all_images.append(filename)
                            
                            progress.update(main_task, advance=1)
                    
                    # Small delay between batches to avoid rate limits
                    if batch_num < num_batches - 1:
                        time.sleep(1)
                    
                except Exception as e:
                    console.print(f"[red]Error in batch {batch_num + 1}: {str(e)}[/red]")
                    # Continue with next batch
        
        # Summary
        console.print(f"\n[bold green]Generation Complete![/bold green]")
        console.print(f"✓ Generated {len(all_images)} images")
        console.print(f"✓ Saved to: {save_subdir}")
        console.print(f"✓ Size: {size}")
        
        # Create a contact sheet (optional)
        if len(all_images) > 1 and questionary.confirm("Create a contact sheet of all images?").ask():
            self.create_contact_sheet(all_images, save_subdir / "contact_sheet.jpg")
        
        if questionary.confirm("Open folder?").ask():
            os.system(f"xdg-open '{save_subdir}' 2>/dev/null || open '{save_subdir}' 2>/dev/null || explorer.exe '{save_subdir}' 2>/dev/null")
    
    def create_contact_sheet(self, image_files, output_path):
        """Create a contact sheet of all generated images"""
        if not image_files:
            return
        
        # Calculate grid size
        num_images = len(image_files)
        cols = math.ceil(math.sqrt(num_images))
        rows = math.ceil(num_images / cols)
        
        # Load first image to get size
        first_img = Image.open(image_files[0])
        img_width, img_height = first_img.size
        
        # Create contact sheet
        thumb_size = (256, 256)  # Thumbnail size
        sheet_width = cols * thumb_size[0]
        sheet_height = rows * thumb_size[1]
        
        contact_sheet = Image.new('RGB', (sheet_width, sheet_height), 'white')
        
        for idx, img_file in enumerate(image_files):
            img = Image.open(img_file)
            img.thumbnail(thumb_size, Image.Resampling.LANCZOS)
            
            # Calculate position
            col = idx % cols
            row = idx // cols
            x = col * thumb_size[0]
            y = row * thumb_size[1]
            
            # Paste thumbnail
            contact_sheet.paste(img, (x, y))
        
        # Save contact sheet
        contact_sheet.save(output_path, quality=90)
        console.print(f"[green]✓ Contact sheet saved: {output_path}[/green]")
    
    def quick_generate(self):
        """Quick generation with defaults"""
        console.print("\n[bold cyan]Quick Generate (Max Quality)[/bold cyan]")
        
        prompt = questionary.text("Enter prompt:").ask()
        if not prompt:
            return
        
        # Default to DALL-E 2, max res, 10 images
        console.print("[yellow]Generating 10 images at 1024x1024...[/yellow]")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_subdir = self.save_dir / f"quick_{timestamp}"
        save_subdir.mkdir(parents=True, exist_ok=True)
        
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Generating...", total=10)
            
            for batch in range(3):  # 3 batches: 4+4+2
                n = 4 if batch < 2 else 2
                
                try:
                    response = self.client.images.generate(
                        model="dall-e-2",
                        prompt=prompt,
                        size="1024x1024",
                        n=n
                    )
                    
                    for i, image_data in enumerate(response.data):
                        resp = requests.get(image_data.url)
                        if resp.status_code == 200:
                            idx = batch * 4 + i + 1
                            filename = save_subdir / f"image_{idx:03d}.png"
                            with open(filename, 'wb') as f:
                                f.write(resp.content)
                            progress.advance(task, 1)
                    
                    time.sleep(0.5)  # Small delay
                    
                except Exception as e:
                    console.print(f"[red]Error: {str(e)}[/red]")
        
        console.print(f"[green]✓ Generated 10 images in: {save_subdir}[/green]")
    
    def main_menu(self):
        """Main menu loop"""
        self.initialize()
        
        console.print(Panel.fit(
            "[bold cyan]DALL-E CLI Enhanced[/bold cyan]\n"
            "[yellow]Unlimited Images • Max Resolution • Batch Processing[/yellow]",
            border_style="cyan"
        ))
        
        while True:
            choices = [
                "🚀 Generate images (enhanced mode)",
                "⚡ Quick generate (10 images, max res)",
                "🎨 Create variations (DALL-E 2 only)",
                "📁 View history",
                "❌ Exit"
            ]
            
            action = questionary.select(
                "\nWhat would you like to do?",
                choices=choices
            ).ask()
            
            if "Generate images" in action:
                self.generate_image_batch()
            elif "Quick generate" in action:
                self.quick_generate()
            elif "Create variations" in action:
                self.create_variations()
            elif "View history" in action:
                self.view_history()
            elif "Exit" in action:
                console.print("\n[yellow]Goodbye![/yellow]")
                break
    
    def create_variations(self):
        """Create variations with batch support"""
        console.print("\n[bold cyan]Create Variations (DALL-E 2)[/bold cyan]")
        
        image_path = questionary.path(
            "Select image file:",
            validate=lambda x: Path(x).exists() and Path(x).suffix.lower() in ['.png', '.jpg', '.jpeg']
        ).ask()
        
        if not image_path:
            return
        
        num_variations = int(questionary.text(
            "Number of variations to create:",
            default="10",
            validate=lambda x: x.isdigit() and 1 <= int(x) <= 50
        ).ask())
        
        # Always use max resolution for variations
        size = "1024x1024"
        
        # Calculate batches
        num_batches = math.ceil(num_variations / 4)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_subdir = self.save_dir / f"variations_{timestamp}"
        save_subdir.mkdir(parents=True, exist_ok=True)
        
        # Copy original
        shutil.copy2(image_path, save_subdir / f"original_{Path(image_path).name}")
        
        console.print(f"\n[yellow]Creating {num_variations} variations in {num_batches} batch(es)...[/yellow]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            
            task = progress.add_task("Creating variations...", total=num_variations)
            variation_count = 0
            
            for batch_num in range(num_batches):
                remaining = num_variations - variation_count
                batch_size = min(remaining, 4)
                
                try:
                    with open(image_path, 'rb') as f:
                        response = self.client.images.create_variation(
                            image=f,
                            n=batch_size,
                            size=size
                        )
                    
                    for i, image_data in enumerate(response.data):
                        variation_count += 1
                        
                        resp = requests.get(image_data.url)
                        if resp.status_code == 200:
                            filename = save_subdir / f"variation_{variation_count:03d}.png"
                            with open(filename, 'wb') as f:
                                f.write(resp.content)
                        
                        progress.advance(task, 1)
                    
                    if batch_num < num_batches - 1:
                        time.sleep(1)
                        
                except Exception as e:
                    console.print(f"[red]Error in batch {batch_num + 1}: {str(e)}[/red]")
        
        console.print(f"\n[bold green]Created {variation_count} variations![/bold green]")
        console.print(f"Saved in: {save_subdir}")
    
    def view_history(self):
        """View generation history with enhanced info"""
        console.print("\n[bold cyan]Generation History[/bold cyan]")
        
        folders = sorted([d for d in self.save_dir.iterdir() if d.is_dir()], reverse=True)
        
        if not folders:
            console.print("[yellow]No generation history found[/yellow]")
            return
        
        table = Table(title="Recent Generations")
        table.add_column("#", style="cyan", width=3)
        table.add_column("Date/Time", style="white")
        table.add_column("Type", style="green")
        table.add_column("Images", style="magenta")
        table.add_column("Size", style="yellow")
        
        for i, folder in enumerate(folders[:20]):
            parts = folder.name.split('_')
            gen_type = parts[0]
            
            # Count images
            images = list(folder.glob("*.png")) + list(folder.glob("*.jpg"))
            
            # Get size from first image
            size = "Unknown"
            if images:
                try:
                    img = Image.open(images[0])
                    size = f"{img.width}x{img.height}"
                except:
                    pass
            
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
                str(len(images)),
                size
            )
        
        console.print(table)
        
        if folders and questionary.confirm("View details of a generation?").ask():
            idx = questionary.text(
                f"Enter number (1-{min(20, len(folders))}):",
                validate=lambda x: x.isdigit() and 1 <= int(x) <= min(20, len(folders))
            ).ask()
            
            if idx:
                folder = folders[int(idx) - 1]
                
                # Show generation info if exists
                info_file = folder / "generation_info.txt"
                if info_file.exists():
                    console.print(f"\n[bold]Generation Info:[/bold]")
                    console.print(info_file.read_text())
                
                console.print(f"\n[bold]Folder:[/bold] {folder}")
                console.print(f"[bold]Total images:[/bold] {len(list(folder.glob('*.png')))}")
                
                if questionary.confirm("Open folder?").ask():
                    os.system(f"xdg-open '{folder}' 2>/dev/null || open '{folder}' 2>/dev/null || explorer.exe '{folder}' 2>/dev/null")

def main():
    """Main entry point"""
    app = EnhancedDalleCLI()
    
    try:
        app.main_menu()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {str(e)}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
