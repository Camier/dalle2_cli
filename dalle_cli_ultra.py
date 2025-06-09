#!/usr/bin/env python3
"""
DALL-E CLI Ultra - User-friendly version with best practices
"""
import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import json
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from functools import lru_cache
import signal
import atexit

# Third party imports
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Prompt, Confirm, IntPrompt
from rich import box
from rich.text import Text
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.columns import Columns
from rich.traceback import install as install_rich_traceback
import questionary
from questionary import Style
from openai import OpenAI, AsyncOpenAI
import httpx

# Install rich traceback for better error messages
install_rich_traceback(show_locals=True)

# Initialize app with better help
app = typer.Typer(
    rich_markup_mode="rich",
    help="🎨 DALL-E CLI Ultra - The most user-friendly AI image generator",
    add_completion=True,
    pretty_exceptions_show_locals=False,
    context_settings={"help_option_names": ["-h", "--help"]}
)

console = Console()

# User-friendly styling
CUSTOM_STYLE = Style([
    ('qmark', 'fg:#673ab7 bold'),
    ('question', 'bold'),
    ('answer', 'fg:#ff9d00 bold'),
    ('pointer', 'fg:#673ab7 bold'),
    ('highlighted', 'fg:#673ab7 bold'),
    ('selected', 'fg:#cc5454'),
    ('separator', 'fg:#cc5454'),
    ('instruction', 'fg:#abb2bf'),
    ('text', 'fg:#ffffff'),
])

# Best practice: Clear configuration
class Config:
    """Centralized configuration with smart defaults"""
    DEFAULT_MODEL = "dall-e-3"
    DEFAULT_SIZE = "1024x1024"
    DEFAULT_QUALITY = "standard"
    DEFAULT_STYLE = "vivid"
    MAX_WORKERS = 4
    RETRY_ATTEMPTS = 3
    TIMEOUT_SECONDS = 30
    
    # User preferences cache
    _preferences = None
    
    @classmethod
    def load_preferences(cls):
        """Load user preferences with fallback"""
        if cls._preferences is None:
            pref_file = Path.home() / ".dalle2_cli" / "preferences.json"
            try:
                if pref_file.exists():
                    with open(pref_file) as f:
                        cls._preferences = json.load(f)
                else:
                    cls._preferences = {}
            except:
                cls._preferences = {}
        return cls._preferences
    
    @classmethod
    def save_preference(cls, key: str, value: Any):
        """Save user preference"""
        prefs = cls.load_preferences()
        prefs[key] = value
        
        pref_file = Path.home() / ".dalle2_cli" / "preferences.json"
        pref_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(pref_file, 'w') as f:
            json.dump(prefs, f, indent=2)

class WorkerPool:
    """Intelligent worker pool for parallel processing"""
    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or Config.MAX_WORKERS
        self.executor = None
        self.active_tasks = []
        
    def __enter__(self):
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.executor.shutdown(wait=True)
        
    async def submit_batch(self, func, items, progress=None):
        """Submit batch of items for parallel processing"""
        loop = asyncio.get_event_loop()
        futures = []
        
        for item in items:
            future = loop.run_in_executor(self.executor, func, item)
            futures.append(future)
            
        results = []
        for future in asyncio.as_completed(futures):
            try:
                result = await future
                results.append(result)
                if progress:
                    progress.advance(1)
            except Exception as e:
                console.print(f"[red]Worker error: {e}[/red]")
                
        return results

class SmartErrorHandler:
    """Intelligent error handling with recovery suggestions"""
    
    ERROR_SOLUTIONS = {
        "api_key": {
            "message": "🔑 API key issue detected",
            "solution": "Run 'dalle setup' to configure your API key",
            "command": "dalle setup"
        },
        "rate_limit": {
            "message": "⏱️ Rate limit reached",
            "solution": "Wait a moment or try with fewer images",
            "retry": True
        },
        "network": {
            "message": "🌐 Network connection issue",
            "solution": "Check your internet connection and try again",
            "retry": True
        },
        "invalid_size": {
            "message": "📐 Invalid image size",
            "solution": "Use --help to see valid sizes for your model",
            "command": "dalle generate --help"
        },
        "quota": {
            "message": "💳 Quota exceeded",
            "solution": "Check your OpenAI account balance",
            "url": "https://platform.openai.com/account/usage"
        }
    }
    
    @classmethod
    def handle_error(cls, error: Exception) -> Dict:
        """Analyze error and provide helpful suggestions"""
        error_str = str(error).lower()
        
        # Match error patterns
        if "api" in error_str and "key" in error_str:
            return cls.ERROR_SOLUTIONS["api_key"]
        elif "rate" in error_str and "limit" in error_str:
            return cls.ERROR_SOLUTIONS["rate_limit"]
        elif "network" in error_str or "connection" in error_str:
            return cls.ERROR_SOLUTIONS["network"]
        elif "size" in error_str:
            return cls.ERROR_SOLUTIONS["invalid_size"]
        elif "quota" in error_str or "balance" in error_str:
            return cls.ERROR_SOLUTIONS["quota"]
        else:
            return {
                "message": "❌ An unexpected error occurred",
                "solution": "Try again or check the error details above",
                "retry": True
            }
    
    @classmethod
    def show_error_help(cls, error: Exception):
        """Display user-friendly error help"""
        help_info = cls.handle_error(error)
        
        panel = Panel(
            f"[bold red]{help_info['message']}[/bold red]\n\n"
            f"💡 [yellow]Solution:[/yellow] {help_info['solution']}",
            title="⚠️ Error Help",
            border_style="red",
            box=box.ROUNDED
        )
        console.print(panel)
        
        # Offer command suggestion
        if "command" in help_info:
            if Confirm.ask(f"\n[cyan]Would you like to run '{help_info['command']}'?[/cyan]"):
                os.system(help_info['command'])
                
        # Offer retry
        elif help_info.get("retry") and Confirm.ask("\n[cyan]Would you like to retry?[/cyan]"):
            return True
            
        # Open URL if provided
        elif "url" in help_info:
            if Confirm.ask(f"\n[cyan]Open {help_info['url']} in browser?[/cyan]"):
                import webbrowser
                webbrowser.open(help_info['url'])
                
        return False

class UserFriendlyPrompts:
    """Enhanced prompts with better UX"""
    
    @staticmethod
    def get_prompt_with_suggestions():
        """Get prompt with intelligent suggestions"""
        # Show recent prompts
        recent = Config.load_preferences().get("recent_prompts", [])
        
        if recent:
            console.print("\n[dim]Recent prompts:[/dim]")
            for i, prompt in enumerate(recent[-5:], 1):
                console.print(f"  [dim]{i}. {prompt[:50]}...[/dim]")
        
        # Get user input
        prompt = questionary.text(
            "What would you like to create?",
            style=CUSTOM_STYLE,
            instruction="(Describe your image idea)"
        ).ask()
        
        if not prompt:
            return None
            
        # Save to recent
        recent.append(prompt)
        Config.save_preference("recent_prompts", recent[-10:])
        
        # Offer enhancement
        if len(prompt.split()) < 5:
            if Confirm.ask("\n[cyan]Would you like me to enhance this prompt?[/cyan]"):
                return enhance_prompt_intelligently(prompt)
                
        return prompt
    
    @staticmethod
    def select_model_smart():
        """Smart model selection with explanations"""
        choices = [
            questionary.Choice(
                "🎨 DALL-E 3 (Recommended)",
                value="dall-e-3",
                shortcut_key="3"
            ),
            questionary.Choice(
                "🖼️ DALL-E 2 (Legacy)",
                value="dall-e-2",
                shortcut_key="2"
            )
        ]
        
        model = questionary.select(
            "Which model would you like to use?",
            choices=choices,
            style=CUSTOM_STYLE,
            instruction="(DALL-E 3 has better quality and understanding)"
        ).ask()
        
        return model

def enhance_prompt_intelligently(prompt: str) -> str:
    """AI-powered prompt enhancement"""
    enhancements = [
        "highly detailed",
        "professional quality",
        "stunning composition",
        "beautiful lighting"
    ]
    
    # Smart enhancement based on content
    if "portrait" in prompt.lower():
        enhancements.extend(["perfect face", "expressive eyes"])
    elif "landscape" in prompt.lower():
        enhancements.extend(["epic vista", "atmospheric"])
    elif "product" in prompt.lower():
        enhancements.extend(["studio lighting", "clean background"])
        
    enhanced = f"{prompt}, {', '.join(enhancements)}"
    
    console.print(f"\n✨ Enhanced: [green]{enhanced}[/green]")
    return enhanced

class OnboardingFlow:
    """First-time user onboarding"""
    
    @staticmethod
    def check_first_run():
        """Check if this is the first run"""
        marker = Path.home() / ".dalle2_cli" / ".initialized"
        if not marker.exists():
            return True
        return False
    
    @staticmethod
    def run_onboarding():
        """Run the onboarding flow"""
        console.clear()
        
        # Welcome message
        welcome = Panel(
            Text.from_markup(
                "[bold cyan]Welcome to DALL-E CLI Ultra![/bold cyan]\n\n"
                "I'll help you get started with AI image generation.\n"
                "This setup will only take a minute."
            ),
            title="👋 Welcome",
            border_style="cyan",
            box=box.DOUBLE
        )
        console.print(welcome)
        
        # Step 1: API Key
        console.print("\n[bold]Step 1: API Key Setup[/bold]")
        if not Config.load_preferences().get("api_key"):
            api_key = Prompt.ask(
                "Enter your OpenAI API key",
                password=True,
                default="sk-..."
            )
            
            if api_key and api_key.startswith("sk-"):
                Config.save_preference("api_key", api_key)
                console.print("✅ API key saved securely")
            else:
                console.print("[yellow]⚠️ Skipped API key setup[/yellow]")
        
        # Step 2: Preferences
        console.print("\n[bold]Step 2: Default Preferences[/bold]")
        
        # Quality preference
        quality = questionary.select(
            "Default image quality?",
            choices=["standard", "hd"],
            default="standard",
            style=CUSTOM_STYLE
        ).ask()
        Config.save_preference("default_quality", quality)
        
        # Save preference
        save_all = Confirm.ask("Save all generated images automatically?", default=True)
        Config.save_preference("auto_save", save_all)
        
        # Step 3: Quick tutorial
        console.print("\n[bold]Step 3: Quick Tutorial[/bold]")
        tutorial = Panel(
            Text.from_markup(
                "🎨 [bold]Generate:[/bold] dalle generate \"your idea\"\n"
                "🔄 [bold]Variations:[/bold] dalle variations image.png\n"
                "🖼️ [bold]Gallery:[/bold] dalle gallery\n"
                "❓ [bold]Help:[/bold] dalle --help\n\n"
                "[dim]Tip: Just run 'dalle' for interactive mode![/dim]"
            ),
            title="📚 Quick Commands",
            border_style="green"
        )
        console.print(tutorial)
        
        # Mark as initialized
        marker = Path.home() / ".dalle2_cli" / ".initialized"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
        
        console.print("\n✨ [bold green]Setup complete![/bold green]")
        if Confirm.ask("\nWould you like to generate your first image?"):
            return True
        return False

# Improved callback with better error handling
@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(None, "--version", "-v", help="Show version"),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose output")
):
    """
    🎨 DALL-E CLI Ultra - The most user-friendly AI image generator
    
    [bold cyan]Quick Start:[/bold cyan]
    • Run without arguments for interactive mode
    • Use 'dalle generate "your idea"' for quick generation
    • Try 'dalle --help' for all commands
    """
    # Check first run
    if OnboardingFlow.check_first_run():
        if OnboardingFlow.run_onboarding():
            # Redirect to generate after onboarding
            ctx.invoke(generate_interactive)
            return
    
    if version:
        console.print("[bold cyan]DALL-E CLI Ultra v3.0.0[/bold cyan]")
        console.print("The most user-friendly AI image generator")
        return
        
    if ctx.invoked_subcommand is None:
        # No command specified - run interactive mode
        interactive_menu_ultra()

@app.command()
def generate(
    prompt: Optional[str] = typer.Argument(None, help="Image description"),
    model: str = typer.Option(Config.DEFAULT_MODEL, "--model", "-m"),
    size: str = typer.Option(Config.DEFAULT_SIZE, "--size", "-s"),
    quality: str = typer.Option(Config.DEFAULT_QUALITY, "--quality", "-q"),
    n: int = typer.Option(1, "--number", "-n", min=1, max=10),
    enhance: bool = typer.Option(False, "--enhance", "-e", help="Auto-enhance prompt")
):
    """🎨 Generate amazing images from text"""
    if not prompt:
        # Interactive mode
        generate_interactive()
        return
        
    try:
        # Initialize client
        api_key = Config.load_preferences().get("api_key")
        if not api_key:
            SmartErrorHandler.show_error_help(Exception("API key not found"))
            return
            
        client = OpenAI(api_key=api_key)
        
        # Enhance prompt if requested
        if enhance:
            prompt = enhance_prompt_intelligently(prompt)
        
        # Show generation info
        info = Panel(
            f"[bold]Prompt:[/bold] {prompt}\n"
            f"[bold]Model:[/bold] {model} | [bold]Size:[/bold] {size}\n"
            f"[bold]Quality:[/bold] {quality} | [bold]Count:[/bold] {n}",
            title="🎨 Generating Images",
            border_style="cyan"
        )
        console.print(info)
        
        # Generate with progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Creating your images...", total=n)
            
            # Use worker pool for multiple images
            if n > 1:
                with WorkerPool() as pool:
                    results = asyncio.run(
                        pool.submit_batch(
                            lambda i: generate_single(client, prompt, model, size, quality),
                            range(n),
                            progress
                        )
                    )
            else:
                results = [generate_single(client, prompt, model, size, quality)]
                progress.advance(task)
        
        # Show results
        console.print(f"\n✅ [bold green]Successfully generated {len(results)} images![/bold green]")
        
        # Offer to view
        if Confirm.ask("\n[cyan]Would you like to view the images?[/cyan]"):
            for i, path in enumerate(results, 1):
                console.print(f"Opening image {i}: {path}")
                os.system(f"open {path}" if sys.platform == "darwin" else f"xdg-open {path}")
                
    except Exception as e:
        if SmartErrorHandler.show_error_help(e):
            # Retry
            generate(prompt, model, size, quality, n, enhance)

def generate_single(client, prompt, model, size, quality):
    """Generate a single image with retry logic"""
    for attempt in range(Config.RETRY_ATTEMPTS):
        try:
            # Build parameters based on model
            params = {
                "model": model,
                "prompt": prompt,
                "size": size,
                "n": 1
            }
            
            # Only add quality for DALL-E 3
            if model == "dall-e-3":
                params["quality"] = quality
            
            response = client.images.generate(**params)
            
            # Save image
            save_dir = Path.home() / ".dalle2_cli" / "images"
            save_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dalle_{timestamp}_{attempt}.png"
            filepath = save_dir / filename
            
            # Download and save
            import requests
            img_data = requests.get(response.data[0].url).content
            with open(filepath, 'wb') as f:
                f.write(img_data)
                
            return filepath
            
        except Exception as e:
            if attempt < Config.RETRY_ATTEMPTS - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise

def generate_interactive():
    """Interactive generation flow"""
    console.clear()
    console.print(Panel("🎨 [bold cyan]Interactive Image Generation[/bold cyan]", expand=False))
    
    # Get prompt with suggestions
    prompt = UserFriendlyPrompts.get_prompt_with_suggestions()
    if not prompt:
        return
        
    # Smart model selection
    model = UserFriendlyPrompts.select_model_smart()
    
    # Quick options
    quick_options = questionary.checkbox(
        "Select options:",
        choices=[
            "🚀 Fast generation (standard quality)",
            "✨ HD quality (slower)",
            "🎯 Auto-enhance prompt",
            "📦 Generate multiple variations"
        ],
        style=CUSTOM_STYLE
    ).ask()
    
    # Parse options
    quality = "hd" if "HD quality" in str(quick_options) else "standard"
    enhance = "Auto-enhance" in str(quick_options)
    n = 3 if "multiple variations" in str(quick_options) else 1
    
    # Generate
    generate(prompt, model, Config.DEFAULT_SIZE, quality, n, enhance)

def interactive_menu_ultra():
    """Ultra user-friendly interactive menu"""
    console.clear()
    
    # Animated welcome
    welcome = Panel(
        Text.from_markup(
            "[bold cyan]DALL-E CLI Ultra[/bold cyan]\n"
            "The most user-friendly AI image generator\n\n"
            "[dim]Choose an option below or press Ctrl+C to exit[/dim]"
        ),
        box=box.DOUBLE,
        border_style="cyan"
    )
    console.print(welcome)
    
    choices = [
        questionary.Choice("🎨 Generate new images", "generate"),
        questionary.Choice("🔄 Create variations", "variations"),
        questionary.Choice("🖼️ Browse gallery", "gallery"),
        questionary.Choice("📊 View statistics", "stats"),
        questionary.Choice("⚙️ Settings", "settings"),
        questionary.Choice("❓ Help & Tutorial", "help"),
        questionary.Choice("❌ Exit", "exit")
    ]
    
    while True:
        action = questionary.select(
            "What would you like to do?",
            choices=choices,
            style=CUSTOM_STYLE,
            use_shortcuts=True
        ).ask()
        
        if action == "generate":
            generate_interactive()
        elif action == "gallery":
            show_gallery()
        elif action == "stats":
            show_statistics()
        elif action == "settings":
            show_settings()
        elif action == "help":
            show_help_tutorial()
        elif action == "exit":
            console.print("\n👋 [cyan]Thanks for using DALL-E CLI Ultra![/cyan]")
            break
        else:
            console.print("[yellow]Feature coming soon![/yellow]")
            
        if action != "exit":
            console.print("\n[dim]Press Enter to continue...[/dim]")
            input()
            console.clear()
            console.print(welcome)

def show_gallery():
    """Show image gallery with preview"""
    images_dir = Path.home() / ".dalle2_cli" / "images"
    if not images_dir.exists():
        console.print("[yellow]No images found yet![/yellow]")
        return
        
    images = sorted(images_dir.glob("*.png"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not images:
        console.print("[yellow]No images found yet![/yellow]")
        return
    
    table = Table(title="🖼️ Your Gallery", box=box.ROUNDED)
    table.add_column("Index", style="cyan", width=6)
    table.add_column("Filename", style="white")
    table.add_column("Size", style="green")
    table.add_column("Created", style="yellow")
    
    for i, img in enumerate(images[:20], 1):
        size = f"{img.stat().st_size / 1024:.1f} KB"
        created = datetime.fromtimestamp(img.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        table.add_row(str(i), img.name, size, created)
    
    console.print(table)

def show_statistics():
    """Show usage statistics"""
    prefs = Config.load_preferences()
    
    stats = Panel(
        f"[bold]Total Images Generated:[/bold] {prefs.get('total_generated', 0)}\n"
        f"[bold]Favorite Model:[/bold] {prefs.get('favorite_model', 'N/A')}\n"
        f"[bold]Average Quality:[/bold] {prefs.get('avg_quality', 'standard')}\n"
        f"[bold]Most Used Size:[/bold] {prefs.get('most_used_size', '1024x1024')}",
        title="📊 Your Statistics",
        border_style="green"
    )
    console.print(stats)

def show_settings():
    """Interactive settings menu"""
    console.print(Panel("⚙️ [bold]Settings[/bold]", expand=False))
    
    settings = questionary.checkbox(
        "Configure settings:",
        choices=[
            "🔑 Update API key",
            "🎨 Change default model",
            "📐 Change default size",
            "💾 Toggle auto-save",
            "🗑️ Clear image cache"
        ],
        style=CUSTOM_STYLE
    ).ask()
    
    # Handle each setting
    if "Update API key" in settings:
        api_key = Prompt.ask("Enter new API key", password=True)
        Config.save_preference("api_key", api_key)
        console.print("✅ API key updated")

def show_help_tutorial():
    """Interactive help and tutorial"""
    help_text = """
# DALL-E CLI Ultra Help

## Quick Commands
- `dalle` - Launch interactive mode
- `dalle generate "prompt"` - Quick generation
- `dalle gallery` - View your images
- `dalle --help` - Show help

## Tips
- Use descriptive prompts for better results
- Add style keywords: "oil painting", "photorealistic", etc.
- Try HD quality for important images
- Use batch generation for variations

## Keyboard Shortcuts
- Ctrl+C - Exit anytime
- Tab - Auto-complete commands
- ↑/↓ - Navigate menus
"""
    
    console.print(Markdown(help_text))

if __name__ == "__main__":
    # Set up signal handlers for clean exit
    def signal_handler(sig, frame):
        console.print("\n\n👋 [cyan]Goodbye![/cyan]")
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    
    # Run the app
    app()