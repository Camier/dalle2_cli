#!/usr/bin/env python3
"""
Collect all DALL-E generated images into one folder
"""
import os
import shutil
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich import print as rprint

console = Console()

def collect_all_images():
    """Collect all generated images into a single folder"""
    # Source directory
    source_dir = Path.home() / ".dalle2_cli" / "images"
    
    if not source_dir.exists():
        console.print("[red]No images directory found at ~/.dalle2_cli/images[/red]")
        return
    
    # Create collection directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    collection_dir = Path.home() / ".dalle2_cli" / f"ALL_IMAGES_{timestamp}"
    collection_dir.mkdir(parents=True, exist_ok=True)
    
    # Also create a permanent "ALL_IMAGES" folder that gets updated
    permanent_dir = Path.home() / ".dalle2_cli" / "ALL_IMAGES"
    permanent_dir.mkdir(parents=True, exist_ok=True)
    
    console.print(f"\n[bold cyan]Collecting all DALL-E images...[/bold cyan]")
    console.print(f"Source: {source_dir}")
    console.print(f"Destination: {collection_dir}")
    console.print(f"Permanent collection: {permanent_dir}\n")
    
    # Find all image files
    image_extensions = ['.png', '.jpg', '.jpeg', '.webp']
    all_images = []
    
    for folder in source_dir.iterdir():
        if folder.is_dir():
            for ext in image_extensions:
                all_images.extend(folder.glob(f"*{ext}"))
    
    if not all_images:
        console.print("[yellow]No images found![/yellow]")
        return
    
    console.print(f"[green]Found {len(all_images)} images[/green]\n")
    
    # Copy images with progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console
    ) as progress:
        
        task = progress.add_task("Copying images...", total=len(all_images))
        
        copied_count = 0
        skipped_count = 0
        
        for img_path in all_images:
            try:
                # Generate new filename with folder prefix
                folder_name = img_path.parent.name
                original_name = img_path.name
                
                # Create descriptive filename
                if folder_name.startswith(('dalle-2', 'dalle-3', 'variations', 'quick')):
                    new_name = f"{folder_name}_{original_name}"
                else:
                    new_name = original_name
                
                # Copy to timestamped collection
                dest_path = collection_dir / new_name
                
                # Handle duplicates by adding number
                if dest_path.exists():
                    base = dest_path.stem
                    ext = dest_path.suffix
                    counter = 1
                    while dest_path.exists():
                        dest_path = collection_dir / f"{base}_{counter}{ext}"
                        counter += 1
                
                shutil.copy2(img_path, dest_path)
                
                # Also copy to permanent folder
                perm_dest = permanent_dir / new_name
                if perm_dest.exists():
                    base = perm_dest.stem
                    ext = perm_dest.suffix
                    counter = 1
                    while perm_dest.exists():
                        perm_dest = permanent_dir / f"{base}_{counter}{ext}"
                        counter += 1
                
                shutil.copy2(img_path, perm_dest)
                
                copied_count += 1
                
            except Exception as e:
                console.print(f"[red]Error copying {img_path.name}: {e}[/red]")
                skipped_count += 1
            
            progress.advance(task, 1)
    
    # Summary
    console.print(f"\n[bold green]Collection complete![/bold green]")
    console.print(f"✓ Copied: {copied_count} images")
    if skipped_count > 0:
        console.print(f"✗ Skipped: {skipped_count} images")
    
    # Show folder sizes
    collection_size = sum(f.stat().st_size for f in collection_dir.glob("*")) / (1024 * 1024)
    permanent_size = sum(f.stat().st_size for f in permanent_dir.glob("*")) / (1024 * 1024)
    
    table = Table(title="Collection Summary")
    table.add_column("Folder", style="cyan")
    table.add_column("Images", style="green")
    table.add_column("Size", style="yellow")
    
    table.add_row(
        "Timestamped Collection",
        str(len(list(collection_dir.glob("*")))),
        f"{collection_size:.1f} MB"
    )
    table.add_row(
        "Permanent Collection",
        str(len(list(permanent_dir.glob("*")))),
        f"{permanent_size:.1f} MB"
    )
    
    console.print(table)
    
    console.print(f"\n[bold]Locations:[/bold]")
    console.print(f"New collection: {collection_dir}")
    console.print(f"All images: {permanent_dir}")
    
    # Open folder option
    console.print("\n[cyan]Open folder with:[/cyan]")
    console.print("1. Timestamped collection (newest only)")
    console.print("2. ALL_IMAGES folder (everything)")
    console.print("3. Don't open")
    
    choice = input("\nChoice (1/2/3): ").strip()
    
    if choice == "1":
        os.system(f"xdg-open '{collection_dir}' 2>/dev/null || open '{collection_dir}' 2>/dev/null || explorer.exe '{collection_dir}' 2>/dev/null")
    elif choice == "2":
        os.system(f"xdg-open '{permanent_dir}' 2>/dev/null || open '{permanent_dir}' 2>/dev/null || explorer.exe '{permanent_dir}' 2>/dev/null")

def quick_open_all():
    """Quick function to just open the ALL_IMAGES folder"""
    permanent_dir = Path.home() / ".dalle2_cli" / "ALL_IMAGES"
    if permanent_dir.exists():
        console.print(f"[green]Opening: {permanent_dir}[/green]")
        os.system(f"xdg-open '{permanent_dir}' 2>/dev/null || open '{permanent_dir}' 2>/dev/null || explorer.exe '{permanent_dir}' 2>/dev/null")
    else:
        console.print("[red]No ALL_IMAGES folder found. Run collection first![/red]")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--open":
        quick_open_all()
    else:
        collect_all_images()
