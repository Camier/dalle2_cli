import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict


@dataclass
class GenerationRecord:
    id: Optional[int] = None
    prompt: str = ""
    image_path: str = ""
    cost: float = 0.0
    timestamp: str = ""
    size: str = "1024x1024"
    generation_type: str = "generation"
    metadata: str = "{}"


@dataclass
class TemplateRecord:
    id: Optional[int] = None
    name: str = ""
    prompt: str = ""
    category: str = "General"
    usage_count: int = 0


class DatabaseManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prompt TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    cost REAL DEFAULT 0.0,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    size TEXT DEFAULT '1024x1024',
                    generation_type TEXT DEFAULT 'generation',
                    metadata TEXT DEFAULT '{}'
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    prompt TEXT NOT NULL,
                    category TEXT DEFAULT 'General',
                    usage_count INTEGER DEFAULT 0
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_generations_timestamp 
                ON generations(timestamp)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_templates_category 
                ON templates(category)
            ''')
            
            conn.commit()
    
    def add_generation(self, record: GenerationRecord) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO generations 
                (prompt, image_path, cost, timestamp, size, generation_type, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                record.prompt,
                record.image_path,
                record.cost,
                record.timestamp or datetime.now().isoformat(),
                record.size,
                record.generation_type,
                record.metadata
            ))
            return cursor.lastrowid
    
    def get_generations(self, limit: int = 100, offset: int = 0) -> List[GenerationRecord]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM generations 
                ORDER BY timestamp DESC 
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            
            return [GenerationRecord(**dict(row)) for row in cursor.fetchall()]
    
    def search_generations(self, query: str, limit: int = 50) -> List[GenerationRecord]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM generations 
                WHERE prompt LIKE ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (f'%{query}%', limit))
            
            return [GenerationRecord(**dict(row)) for row in cursor.fetchall()]
    
    def delete_generation(self, generation_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('DELETE FROM generations WHERE id = ?', (generation_id,))
            return cursor.rowcount > 0
    
    def get_total_cost(self) -> float:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT SUM(cost) FROM generations')
            result = cursor.fetchone()[0]
            return result if result is not None else 0.0
    
    def get_generation_stats(self) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as total_generations,
                    SUM(cost) as total_cost,
                    AVG(cost) as avg_cost,
                    generation_type,
                    COUNT(*) as count_by_type
                FROM generations 
                GROUP BY generation_type
            ''')
            
            stats = {
                'total_generations': 0,
                'total_cost': 0.0,
                'avg_cost': 0.0,
                'by_type': {}
            }
            
            for row in cursor.fetchall():
                if stats['total_generations'] == 0:
                    stats['total_generations'] = row[0]
                    stats['total_cost'] = row[1] or 0.0
                    stats['avg_cost'] = row[2] or 0.0
                
                stats['by_type'][row[3]] = row[4]
            
            return stats
    
    def add_template(self, template: TemplateRecord) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT OR REPLACE INTO templates 
                (name, prompt, category, usage_count)
                VALUES (?, ?, ?, ?)
            ''', (template.name, template.prompt, template.category, template.usage_count))
            return cursor.lastrowid
    
    def get_templates(self, category: Optional[str] = None) -> List[TemplateRecord]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            if category:
                cursor = conn.execute('''
                    SELECT * FROM templates 
                    WHERE category = ? 
                    ORDER BY usage_count DESC, name
                ''', (category,))
            else:
                cursor = conn.execute('''
                    SELECT * FROM templates 
                    ORDER BY category, usage_count DESC, name
                ''')
            
            return [TemplateRecord(**dict(row)) for row in cursor.fetchall()]
    
    def increment_template_usage(self, template_id: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE templates 
                SET usage_count = usage_count + 1 
                WHERE id = ?
            ''', (template_id,))
    
    def delete_template(self, template_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('DELETE FROM templates WHERE id = ?', (template_id,))
            return cursor.rowcount > 0
    
    def get_template_categories(self) -> List[str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT DISTINCT category FROM templates ORDER BY category')
            return [row[0] for row in cursor.fetchall()]
    
    def set_setting(self, key: str, value: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO settings (key, value) 
                VALUES (?, ?)
            ''', (key, value))
    
    def get_setting(self, key: str, default: str = "") -> str:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT value FROM settings WHERE key = ?', (key,))
            result = cursor.fetchone()
            return result[0] if result else default
    
    def get_all_settings(self) -> Dict[str, str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT key, value FROM settings')
            return dict(cursor.fetchall())
    
    def backup_database(self, backup_path: Path):
        with sqlite3.connect(self.db_path) as source:
            with sqlite3.connect(backup_path) as backup:
                source.backup(backup)
    
    def get_recent_prompts(self, limit: int = 10) -> List[str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT DISTINCT prompt FROM generations 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
            return [row[0] for row in cursor.fetchall()]