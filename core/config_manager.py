import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class AppConfig:
    # API Settings
    max_workers: int = 3
    request_timeout: int = 60
    retry_attempts: int = 3
    
    # UI Settings
    theme: str = "dark"
    window_width: int = 1200
    window_height: int = 800
    auto_save_prompts: bool = True
    show_cost_warnings: bool = True
    
    # Generation Defaults
    default_size: str = "1024x1024"
    default_quality: str = "standard"
    default_style: str = "natural"
    default_n: int = 1
    
    # Directories
    output_directory: str = ""
    cache_directory: str = ""
    backup_directory: str = ""
    
    # Advanced Settings
    enable_prompt_enhancement: bool = True
    auto_download_images: bool = True
    max_cache_size_mb: int = 500
    cleanup_old_files_days: int = 30
    
    # Batch Processing
    batch_delay_seconds: float = 1.0
    max_batch_size: int = 10
    
    # Export Settings
    default_export_format: str = "PNG"
    export_original_size: bool = True
    add_metadata_to_exports: bool = True


class ConfigManager:
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path.home() / ".dalle2_app"
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        self.config = self._load_config()
        self._ensure_directories()
    
    def _load_config(self) -> AppConfig:
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    return AppConfig(**data)
            except Exception as e:
                print(f"Error loading config: {e}")
                return AppConfig()
        else:
            return AppConfig()
    
    def save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(asdict(self.config), f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def _ensure_directories(self):
        dirs = [
            self.get_output_directory(),
            self.get_cache_directory(),
            self.get_backup_directory()
        ]
        
        for directory in dirs:
            directory.mkdir(exist_ok=True)
    
    def get_output_directory(self) -> Path:
        if self.config.output_directory:
            return Path(self.config.output_directory)
        return self.config_dir / "images"
    
    def get_cache_directory(self) -> Path:
        if self.config.cache_directory:
            return Path(self.config.cache_directory)
        return self.config_dir / "cache"
    
    def get_backup_directory(self) -> Path:
        if self.config.backup_directory:
            return Path(self.config.backup_directory)
        return self.config_dir / "backups"
    
    def get_database_path(self) -> Path:
        return self.config_dir / "dalle2_app.db"
    
    def update_setting(self, key: str, value: Any):
        if hasattr(self.config, key):
            setattr(self.config, key, value)
            self.save_config()
        else:
            raise ValueError(f"Unknown setting: {key}")
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        return getattr(self.config, key, default)
    
    def reset_to_defaults(self):
        self.config = AppConfig()
        self.save_config()
        self._ensure_directories()
    
    def export_config(self, export_path: Path):
        with open(export_path, 'w') as f:
            json.dump(asdict(self.config), f, indent=2)
    
    def import_config(self, import_path: Path):
        with open(import_path, 'r') as f:
            data = json.load(f)
            self.config = AppConfig(**data)
            self.save_config()
            self._ensure_directories()
    
    def get_style_presets(self) -> Dict[str, str]:
        return {
            "Photorealistic": "photorealistic, high detail, professional photography",
            "Artistic": "artistic, creative, expressive",
            "Digital Art": "digital art, concept art, detailed",
            "Oil Painting": "oil painting, traditional art, painterly",
            "Watercolor": "watercolor, soft, flowing, artistic",
            "Sketch": "pencil sketch, drawing, artistic study",
            "Vintage": "vintage style, retro, classic",
            "Minimalist": "minimalist, clean, simple, modern",
            "Fantasy": "fantasy art, magical, mystical, ethereal",
            "Sci-Fi": "science fiction, futuristic, technological"
        }
    
    def get_prompt_templates(self) -> Dict[str, str]:
        return {
            "Portrait": "A portrait of {subject}, {style}, professional lighting",
            "Landscape": "A beautiful landscape of {location}, {time_of_day}, {weather}",
            "Product": "A {product} on {background}, commercial photography style",
            "Architecture": "Modern {building_type}, architectural photography, {style}",
            "Food": "Delicious {food_item}, food photography, appetizing, {style}",
            "Animal": "A {animal} in {environment}, wildlife photography, natural",
            "Abstract": "Abstract {concept}, {colors}, artistic interpretation",
            "Logo": "A logo for {company}, {style}, professional design"
        }
    
    def cleanup_old_files(self):
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=self.config.cleanup_old_files_days)
        
        directories = [
            self.get_cache_directory(),
            self.get_output_directory() / "temp"
        ]
        
        for directory in directories:
            if directory.exists():
                for file_path in directory.iterdir():
                    if file_path.is_file():
                        file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if file_time < cutoff_date:
                            try:
                                file_path.unlink()
                            except Exception as e:
                                print(f"Error deleting old file {file_path}: {e}")
    
    def get_cache_size_mb(self) -> float:
        cache_dir = self.get_cache_directory()
        total_size = 0
        
        if cache_dir.exists():
            for file_path in cache_dir.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        
        return total_size / (1024 * 1024)  # Convert to MB
    
    def cleanup_cache_if_needed(self):
        current_size = self.get_cache_size_mb()
        if current_size > self.config.max_cache_size_mb:
            cache_dir = self.get_cache_directory()
            
            # Get all files sorted by modification time (oldest first)
            files = []
            for file_path in cache_dir.rglob('*'):
                if file_path.is_file():
                    files.append((file_path.stat().st_mtime, file_path))
            
            files.sort()
            
            # Delete oldest files until we're under the limit
            for _, file_path in files:
                try:
                    file_path.unlink()
                    current_size = self.get_cache_size_mb()
                    if current_size <= self.config.max_cache_size_mb * 0.8:  # Leave some buffer
                        break
                except Exception as e:
                    print(f"Error deleting cache file {file_path}: {e}")