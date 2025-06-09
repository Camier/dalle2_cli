"""
Plugin system for DALL-E CLI v2
Allows extending functionality with custom commands
"""
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
import inspect
import click
from abc import ABC, abstractmethod

class PluginBase(ABC):
    """Base class for DALL-E CLI plugins"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Plugin description"""
        pass
    
    @abstractmethod
    def get_commands(self) -> List[click.Command]:
        """Return list of Click commands provided by this plugin"""
        pass
    
    def on_load(self):
        """Called when plugin is loaded"""
        pass
    
    def on_unload(self):
        """Called when plugin is unloaded"""
        pass

class PluginManager:
    """Manage plugins for DALL-E CLI"""
    
    def __init__(self, plugin_dir: Optional[Path] = None):
        self.plugin_dir = plugin_dir or Path.home() / ".dalle_cli" / "plugins"
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        self.plugins: Dict[str, PluginBase] = {}
        self.commands: Dict[str, click.Command] = {}
        
    def discover_plugins(self) -> List[str]:
        """Discover available plugins"""
        plugins = []
        
        # Look for Python files in plugin directory
        for path in self.plugin_dir.glob("*.py"):
            if path.stem != "__init__":
                plugins.append(path.stem)
        
        # Look for plugin packages
        for path in self.plugin_dir.iterdir():
            if path.is_dir() and (path / "__init__.py").exists():
                plugins.append(path.name)
        
        return plugins
    
    def load_plugin(self, plugin_name: str) -> bool:
        """Load a plugin by name"""
        if plugin_name in self.plugins:
            return True  # Already loaded
        
        try:
            # Try to load as module
            plugin_path = self.plugin_dir / f"{plugin_name}.py"
            if plugin_path.exists():
                spec = importlib.util.spec_from_file_location(
                    f"dalle_plugin_{plugin_name}", plugin_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            else:
                # Try to load as package
                module = importlib.import_module(
                    f"dalle_plugin_{plugin_name}",
                    package=str(self.plugin_dir)
                )
            
            # Find plugin class
            plugin_class = None
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, PluginBase) and 
                    obj != PluginBase):
                    plugin_class = obj
                    break
            
            if not plugin_class:
                return False
            
            # Instantiate plugin
            plugin = plugin_class()
            plugin.on_load()
            
            # Register plugin and its commands
            self.plugins[plugin_name] = plugin
            
            for command in plugin.get_commands():
                self.commands[command.name] = command
            
            return True
            
        except Exception as e:
            print(f"Error loading plugin {plugin_name}: {e}")
            return False
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin"""
        if plugin_name not in self.plugins:
            return False
        
        plugin = self.plugins[plugin_name]
        
        # Remove commands
        for command in plugin.get_commands():
            self.commands.pop(command.name, None)
        
        # Unload plugin
        plugin.on_unload()
        del self.plugins[plugin_name]
        
        return True
    
    def get_plugin_commands(self) -> Dict[str, click.Command]:
        """Get all commands from loaded plugins"""
        return self.commands.copy()
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """List all available plugins with their status"""
        available = self.discover_plugins()
        
        plugins = []
        for name in available:
            plugin_info = {
                "name": name,
                "loaded": name in self.plugins,
                "description": "",
                "commands": []
            }
            
            if name in self.plugins:
                plugin = self.plugins[name]
                plugin_info["description"] = plugin.description
                plugin_info["commands"] = [cmd.name for cmd in plugin.get_commands()]
            
            plugins.append(plugin_info)
        
        return plugins

# Example plugin implementation
class ExamplePlugin(PluginBase):
    """Example plugin showing how to extend DALL-E CLI"""
    
    @property
    def name(self) -> str:
        return "example"
    
    @property
    def description(self) -> str:
        return "Example plugin with sample commands"
    
    def get_commands(self) -> List[click.Command]:
        @click.command()
        @click.pass_context
        def hello(ctx):
            """Say hello from plugin"""
            click.echo("Hello from example plugin!")
        
        @click.command()
        @click.argument('text')
        @click.pass_context
        def echo(ctx, text):
            """Echo text with plugin prefix"""
            click.echo(f"[Plugin] {text}")
        
        return [hello, echo]

# Plugin for style presets
class StylePresetsPlugin(PluginBase):
    """Plugin providing artistic style presets"""
    
    @property
    def name(self) -> str:
        return "style_presets"
    
    @property
    def description(self) -> str:
        return "Artistic style presets for image generation"
    
    def get_commands(self) -> List[click.Command]:
        @click.command()
        @click.argument('preset')
        @click.argument('subject')
        @click.pass_context
        def style(ctx, preset, subject):
            """Apply artistic style preset to subject
            
            Available presets:
            - anime: Japanese anime style
            - oil: Oil painting style
            - watercolor: Watercolor painting
            - pencil: Pencil sketch
            - cyberpunk: Cyberpunk aesthetic
            - renaissance: Renaissance art style
            """
            presets = {
                "anime": "in anime style, vibrant colors, cel shaded, Studio Ghibli inspired",
                "oil": "oil painting, thick brushstrokes, impressionist style, rich textures",
                "watercolor": "watercolor painting, soft edges, flowing colors, artistic",
                "pencil": "detailed pencil sketch, graphite drawing, artistic shading",
                "cyberpunk": "cyberpunk style, neon lights, futuristic, blade runner aesthetic",
                "renaissance": "renaissance painting style, classical composition, old master technique"
            }
            
            if preset not in presets:
                click.echo(f"Unknown preset: {preset}")
                click.echo(f"Available: {', '.join(presets.keys())}")
                return
            
            # Build enhanced prompt
            enhanced_prompt = f"{subject}, {presets[preset]}"
            
            # Use the generate command with enhanced prompt
            from .dalle_cli_v2 import generate
            ctx.invoke(generate, prompt=enhanced_prompt)
        
        return [style]

# Plugin for prompt templates
class PromptTemplatesPlugin(PluginBase):
    """Plugin providing prompt templates"""
    
    @property
    def name(self) -> str:
        return "templates"
    
    @property
    def description(self) -> str:
        return "Prompt templates for common scenarios"
    
    def get_commands(self) -> List[click.Command]:
        @click.command()
        @click.pass_context
        def list_templates(ctx):
            """List available prompt templates"""
            templates = {
                "portrait": "Portrait of {subject}, professional photography, soft lighting",
                "landscape": "{location} landscape, golden hour, dramatic sky, high detail",
                "product": "{product} product shot, white background, studio lighting, commercial photography",
                "logo": "Modern logo design for {company}, minimalist, vector style, professional",
                "character": "{description} character design, full body, concept art, detailed",
                "architecture": "{building} architectural visualization, photorealistic, modern design"
            }
            
            click.echo("Available templates:")
            for name, template in templates.items():
                click.echo(f"  {name}: {template}")
        
        @click.command()
        @click.argument('template')
        @click.option('--vars', '-v', multiple=True, help='Template variables (key=value)')
        @click.pass_context
        def apply_template(ctx, template, vars):
            """Apply a prompt template with variables"""
            templates = {
                "portrait": "Portrait of {subject}, professional photography, soft lighting",
                "landscape": "{location} landscape, golden hour, dramatic sky, high detail",
                "product": "{product} product shot, white background, studio lighting, commercial photography",
                "logo": "Modern logo design for {company}, minimalist, vector style, professional",
                "character": "{description} character design, full body, concept art, detailed",
                "architecture": "{building} architectural visualization, photorealistic, modern design"
            }
            
            if template not in templates:
                click.echo(f"Unknown template: {template}")
                return
            
            # Parse variables
            template_vars = {}
            for var in vars:
                if '=' in var:
                    key, value = var.split('=', 1)
                    template_vars[key] = value
            
            # Apply template
            try:
                prompt = templates[template].format(**template_vars)
                click.echo(f"Generated prompt: {prompt}")
                
                # Use the generate command
                from .dalle_cli_v2 import generate
                ctx.invoke(generate, prompt=prompt)
            except KeyError as e:
                click.echo(f"Missing template variable: {e}")
        
        return [list_templates, apply_template]

def create_plugin_template(name: str, output_dir: Path) -> bool:
    """Create a plugin template file"""
    template = f'''"""
{name.title()} plugin for DALL-E CLI
"""
import click
from dalle_cli.core.plugins import PluginBase

class {name.title()}Plugin(PluginBase):
    """Plugin description here"""
    
    @property
    def name(self) -> str:
        return "{name}"
    
    @property
    def description(self) -> str:
        return "Description of what this plugin does"
    
    def get_commands(self) -> list:
        @click.command()
        @click.pass_context
        def my_command(ctx):
            """Command description"""
            click.echo("Hello from {name} plugin!")
        
        return [my_command]
    
    def on_load(self):
        """Called when plugin is loaded"""
        print(f"Loading {name} plugin...")
    
    def on_unload(self):
        """Called when plugin is unloaded"""
        print(f"Unloading {name} plugin...")
'''
    
    plugin_file = output_dir / f"{name}.py"
    
    try:
        with open(plugin_file, 'w') as f:
            f.write(template)
        return True
    except Exception:
        return False