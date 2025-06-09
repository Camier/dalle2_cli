# DALL-E CLI v2 🎨

A modern, feature-rich command-line interface for OpenAI's DALL-E image generation API, built with best practices from 2024.

## ✨ Features

### Core Capabilities
- **DALL-E 2 & 3 Support** - Generate images with both models
- **Async Operations** - Fast, concurrent image generation
- **Batch Processing** - Process multiple prompts efficiently (50% cost savings)
- **Vision API Integration** - Analyze images with GPT-4 Vision
- **Rich Terminal UI** - Beautiful output with progress bars and tables
- **Image Preview** - View images directly in terminal (iTerm2, Kitty, ASCII)
- **Plugin System** - Extend functionality with custom plugins

### Advanced Features
- **Cost Tracking** - Monitor and estimate generation costs
- **Smart Caching** - Cache results to avoid duplicate API calls
- **Prompt Enhancement** - AI-powered prompt optimization
- **Image Variations** - Create variations of existing images
- **Image Editing** - Edit images with prompts and masks
- **Interactive Mode** - REPL-style interface for quick experiments
- **Configuration Profiles** - Save and switch between settings
- **Metadata Tracking** - Search and manage generated images

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/dalle2_cli.git
cd dalle2_cli

# Install dependencies
pip install -r requirements_v2.txt

# Set up your OpenAI API key
export OPENAI_API_KEY='your-api-key'
# Or configure it with the CLI
python dalle_cli_v2.py config set api_key your-api-key
```

## 📖 Usage

### Basic Generation
```bash
# Generate a single image
python dalle_cli_v2.py generate "a serene mountain landscape at sunset"

# Generate with specific model and size
python dalle_cli_v2.py generate "cyberpunk city" --model dall-e-3 --size 1024x1792

# Generate multiple variations
python dalle_cli_v2.py generate "abstract art" --count 4
```

### Batch Processing
```bash
# Process prompts from file
python dalle_cli_v2.py batch prompts.txt --output-dir ./batch_output

# With custom settings
python dalle_cli_v2.py batch prompts.txt --model dall-e-2 --concurrent 8
```

### Image Operations
```bash
# Create variations
python dalle_cli_v2.py variations image.png --count 3

# Analyze image with Vision API
python dalle_cli_v2.py analyze photo.jpg --prompt "What architectural style is this?"

# Interactive mode
python dalle_cli_v2.py interactive
```

### Configuration
```bash
# Show current config
python dalle_cli_v2.py config show

# Set default model
python dalle_cli_v2.py config set default_model dall-e-3

# Set save directory
python dalle_cli_v2.py config set save_directory ~/my_dalle_images
```

## 🔌 Plugin System

Create custom plugins to extend functionality:

```python
# ~/.dalle_cli/plugins/my_plugin.py
from dalle_cli.core.plugins import PluginBase
import click

class MyPlugin(PluginBase):
    @property
    def name(self):
        return "my_plugin"
    
    @property
    def description(self):
        return "Custom functionality"
    
    def get_commands(self):
        @click.command()
        def my_command():
            """Do something cool"""
            click.echo("Hello from plugin!")
        
        return [my_command]
```

## 🎯 Command Reference

### Main Commands
- `generate` - Generate images from text prompts
- `batch` - Process multiple prompts from file
- `variations` - Create variations of existing images
- `analyze` - Analyze images using GPT-4 Vision
- `interactive` - Enter interactive mode
- `config` - Manage configuration

### Options
- `--model` / `-m` - Model to use (dall-e-2, dall-e-3)
- `--size` / `-s` - Image size
- `--quality` / `-q` - Image quality (standard, hd)
- `--style` - Style (vivid, natural) for DALL-E 3
- `--count` / `-n` - Number of images
- `--save-dir` / `-d` - Directory to save images
- `--show-cost` - Show cost estimation

## 💰 Cost Tracking

The CLI automatically tracks generation costs:

### Pricing (as of 2024)
- **DALL-E 2**
  - 1024×1024: $0.020 per image
  - 512×512: $0.018 per image
  - 256×256: $0.016 per image

- **DALL-E 3**
  - 1024×1024: $0.040 per image
  - 1024×1792, 1792×1024: $0.080 per image

### Batch API Savings
Using batch processing provides 50% cost reduction on API calls!

## 🖼️ Terminal Image Display

The CLI supports multiple methods for displaying images:

1. **iTerm2** - Native inline images
2. **Kitty** - Using icat kitten
3. **Block Art** - Colored Unicode blocks
4. **ASCII Art** - Classic ASCII representation

## 🛠️ Advanced Configuration

### Environment Variables
```bash
export OPENAI_API_KEY='sk-...'
export DALLE_CLI_CONFIG_DIR='~/.dalle_cli'
export DALLE_CLI_PLUGIN_DIR='~/.dalle_cli/plugins'
```

### Config File
```json
{
  "api_key": "sk-...",
  "default_model": "dall-e-3",
  "default_size": "1024x1024",
  "default_quality": "standard",
  "save_directory": "~/dalle_images",
  "history_enabled": true,
  "cost_tracking": true,
  "batch_size": 4,
  "max_retries": 3,
  "timeout": 120
}
```

## 🔄 Migration from v1

If you're upgrading from the original dalle_cli:

1. Configuration is now in `~/.dalle_cli/config.json`
2. API key can be set via config command
3. New async architecture provides better performance
4. Batch processing now uses OpenAI's batch API
5. Plugin system replaces hardcoded extensions

## 🤝 Contributing

Contributions are welcome! Key areas:

1. **Plugins** - Create and share useful plugins
2. **Terminal Support** - Add support for more terminal emulators
3. **Prompt Templates** - Contribute artistic templates
4. **Documentation** - Improve guides and examples

## 📝 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

Built with:
- [Click](https://click.palletsprojects.com/) - CLI framework
- [Rich](https://rich.readthedocs.io/) - Terminal formatting
- [OpenAI Python SDK](https://github.com/openai/openai-python) - API client
- [Pillow](https://pillow.readthedocs.io/) - Image processing

## 🚧 Roadmap

- [ ] Web UI companion
- [ ] Stable Diffusion integration
- [ ] Prompt library management
- [ ] Team collaboration features
- [ ] Export to various formats
- [ ] Advanced image post-processing