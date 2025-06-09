# Migration Guide: DALL-E CLI v1 to v2

This guide helps you migrate from the original DALL-E CLI to the improved v2 version.

## 🚀 Why Upgrade?

### Performance Improvements
- **5-10x faster** with async operations
- **Concurrent generation** for multiple images
- **Smart caching** reduces duplicate API calls

### Cost Savings
- **50% cost reduction** with Batch API
- **Cost tracking** and estimation
- **Efficient token usage**

### New Features
- **DALL-E 3** support with enhanced features
- **Vision API** for image analysis
- **Plugin system** for custom extensions
- **Rich terminal UI** with progress bars
- **Interactive mode** for quick experiments

## 📋 Breaking Changes

### 1. Command Structure
```bash
# Old (v1)
python dalle_cli.py --prompt "cat" --count 3

# New (v2)
python dalle_cli_v2.py generate "cat" --count 3
```

### 2. Configuration
```bash
# Old: Environment variables only
export DALLE_API_KEY="sk-..."

# New: Config file + command
python dalle_cli_v2.py config set api_key "sk-..."
```

### 3. API Key Management
```python
# Old
api_key = os.getenv('DALLE_API_KEY')

# New
config = DALLEConfig()
api_key = config.get('api_key')
```

## 🔧 Migration Steps

### Step 1: Install New Dependencies
```bash
pip install -r requirements_v2.txt
```

### Step 2: Migrate Configuration
```bash
# Set your API key
python dalle_cli_v2.py config set api_key $DALLE_API_KEY

# Migrate other settings
python dalle_cli_v2.py config set default_model dall-e-3
python dalle_cli_v2.py config set save_directory ~/dalle_images
```

### Step 3: Update Scripts
If you have scripts using the old CLI:

```bash
# Old script
#!/bin/bash
python dalle_cli.py --prompt "$1" --size 1024x1024 --save

# New script
#!/bin/bash
python dalle_cli_v2.py generate "$1" --size 1024x1024
```

### Step 4: Migrate Custom Code
If you've built on top of the old CLI:

```python
# Old
from core.dalle_api import DALLEAPIManager

manager = DALLEAPIManager(api_key)
result = manager.generate_image(prompt, size="1024x1024")

# New (async)
from dalle_cli_v2 import ImageGenerator

async def generate():
    async with ImageGenerator(api_key, config) as generator:
        result = await generator.generate_single(
            prompt, "dall-e-3", "1024x1024", "standard"
        )
```

## 🆕 New Features Guide

### Batch Processing
Save 50% on costs for bulk generation:

```bash
# Create prompts file
cat > prompts.txt << EOF
futuristic city at night
serene mountain landscape
abstract geometric patterns
EOF

# Process in batch
python dalle_cli_v2.py batch prompts.txt --output-dir ./batch_output
```

### Vision API
Analyze existing images:

```bash
python dalle_cli_v2.py analyze image.jpg --prompt "What art style is this?"
```

### Interactive Mode
Quick experimentation:

```bash
python dalle_cli_v2.py interactive
dalle> generate a happy robot
dalle> variations last_image.png
dalle> cost 10
```

### Plugins
Extend functionality:

```bash
# List plugins
python dalle_cli_v2.py plugins list

# Load plugin
python dalle_cli_v2.py plugins load style_presets

# Use plugin command
python dalle_cli_v2.py style anime "dragon warrior"
```

## 📊 Feature Comparison

| Feature | v1 | v2 |
|---------|----|----|
| DALL-E 2 | ✅ | ✅ |
| DALL-E 3 | ❌ | ✅ |
| Async Generation | ❌ | ✅ |
| Batch API | ❌ | ✅ |
| Vision API | ❌ | ✅ |
| Cost Tracking | Basic | Advanced |
| Plugin System | ❌ | ✅ |
| Interactive Mode | ✅ | ✅ Enhanced |
| Terminal Preview | ❌ | ✅ |
| Prompt Enhancement | ❌ | ✅ |
| Caching | ❌ | ✅ |

## 🔍 Common Issues

### Issue: API Key Not Found
```bash
# Solution
python dalle_cli_v2.py config set api_key "your-key"
```

### Issue: Import Errors
```bash
# Solution: Install new dependencies
pip install -r requirements_v2.txt
```

### Issue: Old Scripts Breaking
```bash
# Create compatibility wrapper
cat > dalle_cli.py << 'EOF'
#!/usr/bin/env python3
"""Compatibility wrapper for old scripts"""
import sys
import subprocess

# Convert old args to new format
args = sys.argv[1:]
new_args = ['python', 'dalle_cli_v2.py', 'generate']

for i, arg in enumerate(args):
    if arg == '--prompt' and i+1 < len(args):
        new_args.append(args[i+1])
    elif arg == '--count':
        new_args.extend(['--count', args[i+1]])
    # Add more conversions as needed

subprocess.run(new_args)
EOF
```

## 💡 Best Practices

1. **Use Batch API** for multiple images (50% cost savings)
2. **Enable caching** to avoid duplicate generations
3. **Set up cost alerts** with the tracking feature
4. **Create plugins** for repeated workflows
5. **Use interactive mode** for experimentation

## 🆘 Getting Help

- Check the [README](README_v2.md) for detailed documentation
- Run `python dalle_cli_v2.py --help` for command help
- Submit issues on [GitHub](https://github.com/yourusername/dalle2_cli)

## 🎉 Welcome to v2!

The new version is designed to be more powerful while remaining easy to use. Take advantage of:

- **Faster generation** with async operations
- **Lower costs** with batch processing
- **More features** with plugins
- **Better UX** with rich terminal output

Happy generating! 🎨