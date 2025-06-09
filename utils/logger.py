import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


class AppLogger:
    def __init__(self, log_dir: Optional[Path] = None, log_level: str = "INFO"):
        self.log_dir = log_dir or Path.home() / ".dalle2_app" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_file = self.log_dir / f"dalle2_app_{datetime.now().strftime('%Y%m%d')}.log"
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger("DALLE2App")
    
    def info(self, message: str):
        self.logger.info(message)
    
    def error(self, message: str):
        self.logger.error(message)
    
    def warning(self, message: str):
        self.logger.warning(message)
    
    def debug(self, message: str):
        self.logger.debug(message)
    
    def log_api_request(self, request_type: str, prompt: str, cost: float):
        self.info(f"API Request - Type: {request_type}, Cost: ${cost:.4f}, Prompt: {prompt[:100]}...")
    
    def log_error(self, error: Exception, context: str = ""):
        self.error(f"Error in {context}: {str(error)}")
    
    def log_user_action(self, action: str, details: str = ""):
        self.info(f"User Action - {action}: {details}")
    
    def cleanup_old_logs(self, days: int = 30):
        cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        for log_file in self.log_dir.glob("*.log"):
            if log_file.stat().st_mtime < cutoff_date:
                try:
                    log_file.unlink()
                    self.info(f"Deleted old log file: {log_file}")
                except Exception as e:
                    self.error(f"Failed to delete old log file {log_file}: {e}")


# Global logger instance
logger = AppLogger()