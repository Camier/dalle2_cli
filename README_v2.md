# 🎨 DALL-E CLI v2

A modern, feature-rich command-line interface for DALL-E image generation with stunning visual effects and powerful capabilities.

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![License](https://img.shields.io/badge/license-MIT-purple)

## ✨ Features

### 🚀 Core Features
- **Multi-model Support**: DALL-E 2 and DALL-E 3 with optimized settings
- **Batch Generation**: Generate multiple images in parallel with progress tracking
- **Interactive Mode**: User-friendly menu when no command specified
- **Rich Terminal UI**: Beautiful colors, tables, and progress indicators
- **Async Operations**: Lightning-fast parallel image generation

### 🎯 Advanced Features
- **Prompt Enhancement**: AI-powered prompt suggestions and improvements
- **Template System**: Pre-built templates for common scenarios
- **Real-time Preview**: Live generation progress with animations
- **Gallery View**: Browse your generated images with metadata
- **Export/Import**: Backup and share your image collections
- **Image Variations**: Create variations of existing images
- **Smart Caching**: Deduplication and efficient storage

### 🎭 Visual Effects
- **Animated Progress**: Multiple animation styles during generation
- **Matrix Rain Effect**: Cool visual effects while processing
- **Dashboard View**: Real-time statistics for batch operations
- **Creative Spinners**: Various loading animations

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/Camier/dalle2_cli.git
cd dalle2_cli

# Install dependencies
pip install -r requirements.txt

# Run setup
python dalle_cli_v2.py setup
```

## 🚀 Quick Start

### Basic Usage

```bash
# Generate a single image
dalle generate "a serene landscape at sunset"

# Generate with specific model and quality
dalle generate "futuristic city" --model dall-e-3 --quality hd

# Generate multiple images
dalle generate "abstract art" --n 4 --batch

# Interactive mode (just run without arguments)
dalle
```

### Command Reference

#### `generate` - Create images from text
```bash
dalle generate [PROMPT] [OPTIONS]

Options:
  -m, --model         Model to use (dall-e-2, dall-e-3)
  -s, --size          Image size (1024x1024, 1792x1024, etc.)
  -q, --quality       Quality level (standard, hd)
  --style            Style (vivid, natural) [DALL-E 3 only]
  -n, --number       Number of images to generate
  -b, --batch        Enable parallel batch generation
  -o, --output       Output directory
```

#### `variations` - Create variations of existing images
```bash
dalle variations [IMAGE_PATH] [OPTIONS]

Options:
  -n, --number       Number of variations
  -s, --size         Output size
  -o, --output       Output directory
```

#### `gallery` - Browse your generated images
```bash
dalle gallery [OPTIONS]

Options:
  -l, --limit        Number of images to show
  -m, --model        Filter by model
  -d, --date         Filter by date (YYYY-MM-DD)
```

#### `setup` - Configure settings
```bash
dalle setup
```

#### `export` - Export your collection
```bash
dalle export [OUTPUT_PATH] [OPTIONS]

Options:
  -f, --format       Export format (json, zip)
  -i, --include-images  Include image files (zip only)
```

## 🎨 Prompt Enhancement

The CLI includes advanced prompt enhancement features:

```python
# Run the prompt enhancer
python dalle_cli_extras.py

# Example enhancements:
Original: "a cat sitting on a chair"
Enhanced: "a cat sitting on a chair, oil painting, golden hour lighting, serene atmosphere, highly detailed, 8k resolution, masterpiece"
```

### Available Styles
- Oil painting, watercolor, digital art, pencil sketch
- Photorealistic, abstract, impressionist, surreal
- Minimalist, baroque, art nouveau, cyberpunk
- Studio Ghibli style, Pixar style, and more!

### Lighting Effects
- Golden hour, dramatic, soft ambient
- Neon, cinematic, natural, rim lighting
- Volumetric lighting, chiaroscuro

### Moods
- Ethereal, moody, vibrant, serene
- Dramatic, whimsical, mysterious
- Nostalgic, futuristic

## 🎭 Animations & Effects

Run the animation demo:
```bash
python dalle_cli_animations.py
```

Features include:
- Animated generation display with ASCII art
- Paint splash loading animations
- Matrix rain effect
- Multi-bar progress indicators
- Creative spinners
- Real-time status dashboard

## 📝 Templates

Pre-built templates for common use cases:

- **Portrait**: Professional headshots, artistic portraits
- **Landscape**: Panoramic views, nature photography
- **Product**: Commercial photography, lifestyle shots
- **Fantasy**: Epic scenes, magical realms
- **Sci-Fi**: Futuristic concepts, cyberpunk aesthetics
- **Architecture**: Modern buildings, interior design

## 🔧 Configuration

The CLI stores configuration in `~/.dalle2_cli/`:
- `config.json`: User preferences and defaults
- `database.db`: Image metadata and history
- `images/`: Generated images organized by date

## 🎯 Tips & Tricks

1. **Batch Generation**: Use `--batch` flag for parallel generation (much faster!)
2. **HD Quality**: Add `--quality hd` for DALL-E 3 for best results
3. **Size Options**: 
   - DALL-E 2: 256x256, 512x512, 1024x1024
   - DALL-E 3: 1024x1024, 1024x1792, 1792x1024
4. **Interactive Mode**: Just run `dalle` without arguments for a guided experience

## 🛠️ Development

### Project Structure
```
dalle2_cli/
├── dalle_cli_v2.py        # Main CLI application
├── dalle_cli_extras.py    # Enhancement features
├── dalle_cli_animations.py # Visual effects
├── core/                  # Core modules
│   ├── dalle_api.py      # API interface
│   ├── config_manager.py  # Configuration
│   └── security.py       # Security utilities
├── data/                 # Data layer
│   └── database.py       # SQLite database
└── utils/                # Utilities
```

### Adding New Features

1. **New Commands**: Add to `dalle_cli_v2.py` using `@app.command()`
2. **Animations**: Add to `dalle_cli_animations.py`
3. **Enhancements**: Add to `dalle_cli_extras.py`

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- Built with [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/)
- Powered by OpenAI's DALL-E API
- Inspired by modern CLI design principles

---

Made with ❤️ and 🎨 by the DALL-E CLI team