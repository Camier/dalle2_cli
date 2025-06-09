# 🚀 How to Launch DALL-E CLI v2

## Quick Launch Commands

### 1. **Interactive Mode (Best UI)**
```bash
cd /home/mik/dalle2_app
./dalle_v2
```

### 2. **With Python directly**
```bash
cd /home/mik/dalle2_app
python dalle_cli_v2.py
```

### 3. **See Cool Animations**
```bash
cd /home/mik/dalle2_app
python dalle_cli_animations.py
```

### 4. **View Help**
```bash
cd /home/mik/dalle2_app
./dalle_v2 --help
```

## First Time Setup
```bash
cd /home/mik/dalle2_app
./dalle_v2 setup
```

## Example Commands

### Generate Images
```bash
./dalle_v2 generate "a beautiful sunset over mountains" --model dall-e-3 --quality hd
```

### View Gallery
```bash
./dalle_v2 gallery
```

### Create Variations
```bash
./dalle_v2 variations path/to/image.png --n 4
```

## Create an Alias (Optional)

Add this to your ~/.bashrc:
```bash
alias dalle2='cd /home/mik/dalle2_app && ./dalle_v2'
```

Then you can just type `dalle2` from anywhere!