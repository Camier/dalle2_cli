import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import time
from pathlib import Path
from typing import Dict, Any

from ...core.config_manager import ConfigManager
from ...core.security import SecurityManager
from ...data.database import DatabaseManager
from ...utils.logger import logger


class SettingsTab(ctk.CTkFrame):
    def __init__(self, parent, config_manager: ConfigManager, security_manager: SecurityManager, 
                 db_manager: DatabaseManager):
        super().__init__(parent)
        
        self.config_manager = config_manager
        self.security_manager = security_manager
        self.db_manager = db_manager
        
        self.create_widgets()
        self.load_current_settings()
    
    def create_widgets(self):
        # Create scrollable frame for all settings
        scroll_frame = ctk.CTkScrollableFrame(self, width=800, height=600)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # API Settings Section
        self.create_api_section(scroll_frame)
        
        # UI Settings Section
        self.create_ui_section(scroll_frame)
        
        # Generation Defaults Section
        self.create_generation_section(scroll_frame)
        
        # Directory Settings Section
        self.create_directory_section(scroll_frame)
        
        # Advanced Settings Section
        self.create_advanced_section(scroll_frame)
        
        # Actions Section
        self.create_actions_section(scroll_frame)
    
    def create_section_header(self, parent, title: str):
        header_frame = ctk.CTkFrame(parent)
        header_frame.pack(fill="x", pady=(20, 10))
        
        title_label = ctk.CTkLabel(header_frame, text=title, 
                                  font=ctk.CTkFont(size=18, weight="bold"))
        title_label.pack(pady=10)
        
        return header_frame
    
    def create_api_section(self, parent):
        self.create_section_header(parent, "API Settings")
        
        api_frame = ctk.CTkFrame(parent)
        api_frame.pack(fill="x", padx=10, pady=5)
        
        # API Key management
        api_key_frame = ctk.CTkFrame(api_frame)
        api_key_frame.pack(fill="x", padx=10, pady=10)
        
        key_label = ctk.CTkLabel(api_key_frame, text="OpenAI API Key:")
        key_label.pack(anchor="w", padx=10, pady=(10, 5))
        
        key_status = "✓ API Key is set" if self.security_manager.has_api_key() else "✗ No API Key"
        self.key_status_label = ctk.CTkLabel(api_key_frame, text=key_status)
        self.key_status_label.pack(anchor="w", padx=10, pady=(0, 5))
        
        key_buttons_frame = ctk.CTkFrame(api_key_frame, fg_color="transparent")
        key_buttons_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        change_key_btn = ctk.CTkButton(key_buttons_frame, text="Change API Key", 
                                      command=self.change_api_key)
        change_key_btn.pack(side="left", padx=5)
        
        clear_key_btn = ctk.CTkButton(key_buttons_frame, text="Clear API Key", 
                                     command=self.clear_api_key)
        clear_key_btn.pack(side="left", padx=5)
        
        test_key_btn = ctk.CTkButton(key_buttons_frame, text="Test API Key", 
                                    command=self.test_api_key)
        test_key_btn.pack(side="left", padx=5)
        
        # API Settings
        api_settings_frame = ctk.CTkFrame(api_frame)
        api_settings_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        # Max Workers
        workers_label = ctk.CTkLabel(api_settings_frame, text="Max Workers:")
        workers_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)
        
        self.workers_var = ctk.StringVar()
        workers_spin = ctk.CTkComboBox(api_settings_frame, variable=self.workers_var,
                                      values=["1", "2", "3", "4", "5"], width=100)
        workers_spin.grid(row=0, column=1, padx=10, pady=5)
        
        # Request Timeout
        timeout_label = ctk.CTkLabel(api_settings_frame, text="Request Timeout (seconds):")
        timeout_label.grid(row=1, column=0, sticky="w", padx=10, pady=5)
        
        self.timeout_var = ctk.StringVar()
        timeout_entry = ctk.CTkEntry(api_settings_frame, textvariable=self.timeout_var, width=100)
        timeout_entry.grid(row=1, column=1, padx=10, pady=5)
    
    def create_ui_section(self, parent):
        self.create_section_header(parent, "UI Settings")
        
        ui_frame = ctk.CTkFrame(parent)
        ui_frame.pack(fill="x", padx=10, pady=5)
        
        # Theme
        theme_label = ctk.CTkLabel(ui_frame, text="Theme:")
        theme_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)
        
        self.theme_var = ctk.StringVar()
        theme_combo = ctk.CTkComboBox(ui_frame, variable=self.theme_var,
                                     values=["dark", "light", "system"], 
                                     command=self.theme_changed, width=120)
        theme_combo.grid(row=0, column=1, padx=10, pady=5)
        
        # Window Size
        size_label = ctk.CTkLabel(ui_frame, text="Default Window Size:")
        size_label.grid(row=1, column=0, sticky="w", padx=10, pady=5)
        
        size_frame = ctk.CTkFrame(ui_frame, fg_color="transparent")
        size_frame.grid(row=1, column=1, padx=10, pady=5)
        
        self.width_var = ctk.StringVar()
        width_entry = ctk.CTkEntry(size_frame, textvariable=self.width_var, width=80)
        width_entry.pack(side="left", padx=2)
        
        ctk.CTkLabel(size_frame, text="×").pack(side="left", padx=2)
        
        self.height_var = ctk.StringVar()
        height_entry = ctk.CTkEntry(size_frame, textvariable=self.height_var, width=80)
        height_entry.pack(side="left", padx=2)
        
        # Auto-save prompts
        self.auto_save_var = ctk.BooleanVar()
        auto_save_check = ctk.CTkCheckBox(ui_frame, text="Auto-save prompts", 
                                         variable=self.auto_save_var)
        auto_save_check.grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=5)
        
        # Show cost warnings
        self.cost_warnings_var = ctk.BooleanVar()
        cost_warnings_check = ctk.CTkCheckBox(ui_frame, text="Show cost warnings", 
                                             variable=self.cost_warnings_var)
        cost_warnings_check.grid(row=3, column=0, columnspan=2, sticky="w", padx=10, pady=5)
    
    def create_generation_section(self, parent):
        self.create_section_header(parent, "Generation Defaults")
        
        gen_frame = ctk.CTkFrame(parent)
        gen_frame.pack(fill="x", padx=10, pady=5)
        
        # Default Size
        size_label = ctk.CTkLabel(gen_frame, text="Default Size:")
        size_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)
        
        self.default_size_var = ctk.StringVar()
        size_combo = ctk.CTkComboBox(gen_frame, variable=self.default_size_var,
                                    values=["1024x1024", "1024x1792", "1792x1024"], width=120)
        size_combo.grid(row=0, column=1, padx=10, pady=5)
        
        # Default Quality
        quality_label = ctk.CTkLabel(gen_frame, text="Default Quality:")
        quality_label.grid(row=1, column=0, sticky="w", padx=10, pady=5)
        
        self.default_quality_var = ctk.StringVar()
        quality_combo = ctk.CTkComboBox(gen_frame, variable=self.default_quality_var,
                                       values=["standard", "hd"], width=120)
        quality_combo.grid(row=1, column=1, padx=10, pady=5)
        
        # Default Style
        style_label = ctk.CTkLabel(gen_frame, text="Default Style:")
        style_label.grid(row=2, column=0, sticky="w", padx=10, pady=5)
        
        self.default_style_var = ctk.StringVar()
        style_combo = ctk.CTkComboBox(gen_frame, variable=self.default_style_var,
                                     values=["natural", "vivid"], width=120)
        style_combo.grid(row=2, column=1, padx=10, pady=5)
        
        # Default Number
        n_label = ctk.CTkLabel(gen_frame, text="Default Images Count:")
        n_label.grid(row=3, column=0, sticky="w", padx=10, pady=5)
        
        self.default_n_var = ctk.StringVar()
        n_combo = ctk.CTkComboBox(gen_frame, variable=self.default_n_var,
                                 values=["1", "2", "3", "4"], width=120)
        n_combo.grid(row=3, column=1, padx=10, pady=5)
    
    def create_directory_section(self, parent):
        self.create_section_header(parent, "Directory Settings")
        
        dir_frame = ctk.CTkFrame(parent)
        dir_frame.pack(fill="x", padx=10, pady=5)
        
        # Output Directory
        output_label = ctk.CTkLabel(dir_frame, text="Output Directory:")
        output_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)
        
        self.output_dir_var = ctk.StringVar()
        output_entry = ctk.CTkEntry(dir_frame, textvariable=self.output_dir_var, width=300)
        output_entry.grid(row=0, column=1, padx=10, pady=5)
        
        output_browse_btn = ctk.CTkButton(dir_frame, text="Browse", width=80,
                                         command=lambda: self.browse_directory(self.output_dir_var))
        output_browse_btn.grid(row=0, column=2, padx=5, pady=5)
        
        # Cache Directory
        cache_label = ctk.CTkLabel(dir_frame, text="Cache Directory:")
        cache_label.grid(row=1, column=0, sticky="w", padx=10, pady=5)
        
        self.cache_dir_var = ctk.StringVar()
        cache_entry = ctk.CTkEntry(dir_frame, textvariable=self.cache_dir_var, width=300)
        cache_entry.grid(row=1, column=1, padx=10, pady=5)
        
        cache_browse_btn = ctk.CTkButton(dir_frame, text="Browse", width=80,
                                        command=lambda: self.browse_directory(self.cache_dir_var))
        cache_browse_btn.grid(row=1, column=2, padx=5, pady=5)
    
    def create_advanced_section(self, parent):
        self.create_section_header(parent, "Advanced Settings")
        
        adv_frame = ctk.CTkFrame(parent)
        adv_frame.pack(fill="x", padx=10, pady=5)
        
        # Prompt Enhancement
        self.prompt_enhancement_var = ctk.BooleanVar()
        prompt_enhancement_check = ctk.CTkCheckBox(adv_frame, text="Enable prompt enhancement", 
                                                  variable=self.prompt_enhancement_var)
        prompt_enhancement_check.grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=5)
        
        # Auto Download
        self.auto_download_var = ctk.BooleanVar()
        auto_download_check = ctk.CTkCheckBox(adv_frame, text="Auto-download images", 
                                             variable=self.auto_download_var)
        auto_download_check.grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=5)
        
        # Cache Size Limit
        cache_size_label = ctk.CTkLabel(adv_frame, text="Max Cache Size (MB):")
        cache_size_label.grid(row=2, column=0, sticky="w", padx=10, pady=5)
        
        self.cache_size_var = ctk.StringVar()
        cache_size_entry = ctk.CTkEntry(adv_frame, textvariable=self.cache_size_var, width=100)
        cache_size_entry.grid(row=2, column=1, padx=10, pady=5)
        
        # Cleanup Days
        cleanup_label = ctk.CTkLabel(adv_frame, text="Cleanup old files after (days):")
        cleanup_label.grid(row=3, column=0, sticky="w", padx=10, pady=5)
        
        self.cleanup_days_var = ctk.StringVar()
        cleanup_entry = ctk.CTkEntry(adv_frame, textvariable=self.cleanup_days_var, width=100)
        cleanup_entry.grid(row=3, column=1, padx=10, pady=5)
        
        # Batch Delay
        batch_delay_label = ctk.CTkLabel(adv_frame, text="Batch delay (seconds):")
        batch_delay_label.grid(row=4, column=0, sticky="w", padx=10, pady=5)
        
        self.batch_delay_var = ctk.StringVar()
        batch_delay_entry = ctk.CTkEntry(adv_frame, textvariable=self.batch_delay_var, width=100)
        batch_delay_entry.grid(row=4, column=1, padx=10, pady=5)
    
    def create_actions_section(self, parent):
        self.create_section_header(parent, "Actions")
        
        actions_frame = ctk.CTkFrame(parent)
        actions_frame.pack(fill="x", padx=10, pady=5)
        
        # Save/Reset buttons
        buttons_frame = ctk.CTkFrame(actions_frame)
        buttons_frame.pack(fill="x", padx=10, pady=10)
        
        save_btn = ctk.CTkButton(buttons_frame, text="Save Settings", 
                                command=self.save_settings, width=120,
                                font=ctk.CTkFont(weight="bold"))
        save_btn.pack(side="left", padx=5)
        
        reset_btn = ctk.CTkButton(buttons_frame, text="Reset to Defaults", 
                                 command=self.reset_to_defaults, width=140)
        reset_btn.pack(side="left", padx=5)
        
        # Database actions
        db_frame = ctk.CTkFrame(actions_frame)
        db_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        db_label = ctk.CTkLabel(db_frame, text="Database:", 
                               font=ctk.CTkFont(weight="bold"))
        db_label.pack(anchor="w", padx=10, pady=(10, 5))
        
        db_buttons_frame = ctk.CTkFrame(db_frame, fg_color="transparent")
        db_buttons_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        backup_btn = ctk.CTkButton(db_buttons_frame, text="Backup Database", 
                                  command=self.backup_database, width=140)
        backup_btn.pack(side="left", padx=5)
        
        cleanup_btn = ctk.CTkButton(db_buttons_frame, text="Cleanup Cache", 
                                   command=self.cleanup_cache, width=120)
        cleanup_btn.pack(side="left", padx=5)
        
        # Export/Import
        export_frame = ctk.CTkFrame(actions_frame)
        export_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        export_label = ctk.CTkLabel(export_frame, text="Configuration:", 
                                   font=ctk.CTkFont(weight="bold"))
        export_label.pack(anchor="w", padx=10, pady=(10, 5))
        
        export_buttons_frame = ctk.CTkFrame(export_frame, fg_color="transparent")
        export_buttons_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        export_config_btn = ctk.CTkButton(export_buttons_frame, text="Export Config", 
                                         command=self.export_config, width=120)
        export_config_btn.pack(side="left", padx=5)
        
        import_config_btn = ctk.CTkButton(export_buttons_frame, text="Import Config", 
                                         command=self.import_config, width=120)
        import_config_btn.pack(side="left", padx=5)
    
    def load_current_settings(self):
        config = self.config_manager.config
        
        # API Settings
        self.workers_var.set(str(config.max_workers))
        self.timeout_var.set(str(config.request_timeout))
        
        # UI Settings
        self.theme_var.set(config.theme)
        self.width_var.set(str(config.window_width))
        self.height_var.set(str(config.window_height))
        self.auto_save_var.set(config.auto_save_prompts)
        self.cost_warnings_var.set(config.show_cost_warnings)
        
        # Generation Defaults
        self.default_size_var.set(config.default_size)
        self.default_quality_var.set(config.default_quality)
        self.default_style_var.set(config.default_style)
        self.default_n_var.set(str(config.default_n))
        
        # Directories
        self.output_dir_var.set(config.output_directory)
        self.cache_dir_var.set(config.cache_directory)
        
        # Advanced
        self.prompt_enhancement_var.set(config.enable_prompt_enhancement)
        self.auto_download_var.set(config.auto_download_images)
        self.cache_size_var.set(str(config.max_cache_size_mb))
        self.cleanup_days_var.set(str(config.cleanup_old_files_days))
        self.batch_delay_var.set(str(config.batch_delay_seconds))
    
    def save_settings(self):
        try:
            config = self.config_manager.config
            
            # API Settings
            config.max_workers = int(self.workers_var.get())
            config.request_timeout = int(self.timeout_var.get())
            
            # UI Settings
            config.theme = self.theme_var.get()
            config.window_width = int(self.width_var.get())
            config.window_height = int(self.height_var.get())
            config.auto_save_prompts = self.auto_save_var.get()
            config.show_cost_warnings = self.cost_warnings_var.get()
            
            # Generation Defaults
            config.default_size = self.default_size_var.get()
            config.default_quality = self.default_quality_var.get()
            config.default_style = self.default_style_var.get()
            config.default_n = int(self.default_n_var.get())
            
            # Directories
            config.output_directory = self.output_dir_var.get()
            config.cache_directory = self.cache_dir_var.get()
            
            # Advanced
            config.enable_prompt_enhancement = self.prompt_enhancement_var.get()
            config.auto_download_images = self.auto_download_var.get()
            config.max_cache_size_mb = int(self.cache_size_var.get())
            config.cleanup_old_files_days = int(self.cleanup_days_var.get())
            config.batch_delay_seconds = float(self.batch_delay_var.get())
            
            self.config_manager.save_config()
            messagebox.showinfo("Success", "Settings saved successfully!")
            
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid value: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
    
    def reset_to_defaults(self):
        if messagebox.askyesno("Reset Settings", "Reset all settings to defaults?"):
            self.config_manager.reset_to_defaults()
            self.load_current_settings()
            messagebox.showinfo("Success", "Settings reset to defaults")
    
    def theme_changed(self, theme):
        ctk.set_appearance_mode(theme)
    
    def browse_directory(self, var: ctk.StringVar):
        directory = filedialog.askdirectory(title="Select Directory")
        if directory:
            var.set(directory)
    
    def change_api_key(self):
        # Simple input dialog for API key
        from tkinter import simpledialog
        
        api_key = simpledialog.askstring("API Key", "Enter your OpenAI API Key:", show='*')
        
        if api_key and api_key.strip():
            if self.security_manager.save_api_key(api_key.strip()):
                self.key_status_label.configure(text="✓ API Key is set")
                messagebox.showinfo("Success", "API Key updated successfully")
            else:
                messagebox.showerror("Error", "Failed to save API key")
    
    def clear_api_key(self):
        if messagebox.askyesno("Clear API Key", "Are you sure you want to clear the API key?"):
            if self.security_manager.clear_api_key():
                self.key_status_label.configure(text="✗ No API Key")
                messagebox.showinfo("Success", "API Key cleared")
            else:
                messagebox.showerror("Error", "Failed to clear API key")
    
    def test_api_key(self):
        api_key = self.security_manager.load_api_key()
        if not api_key:
            messagebox.showerror("Error", "No API key set")
            return
        
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)
            models = client.models.list()
            messagebox.showinfo("Success", "API key is valid!")
        except Exception as e:
            messagebox.showerror("Error", f"API key test failed: {e}")
    
    def backup_database(self):
        save_path = filedialog.asksaveasfilename(
            title="Save Database Backup",
            defaultextension=".db",
            filetypes=[("Database files", "*.db"), ("All files", "*.*")],
            initialname=f"dalle2_backup_{int(time.time())}.db"
        )
        
        if save_path:
            try:
                self.db_manager.backup_database(Path(save_path))
                messagebox.showinfo("Success", f"Database backed up to {save_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to backup database: {e}")
    
    def cleanup_cache(self):
        if messagebox.askyesno("Cleanup Cache", "Clean up old cache files?"):
            try:
                self.config_manager.cleanup_cache_if_needed()
                self.config_manager.cleanup_old_files()
                messagebox.showinfo("Success", "Cache cleaned up successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to cleanup cache: {e}")
    
    def export_config(self):
        save_path = filedialog.asksaveasfilename(
            title="Export Configuration",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialname="dalle2_config.json"
        )
        
        if save_path:
            try:
                self.config_manager.export_config(Path(save_path))
                messagebox.showinfo("Success", f"Configuration exported to {save_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export configuration: {e}")
    
    def import_config(self):
        file_path = filedialog.askopenfilename(
            title="Import Configuration",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            if messagebox.askyesno("Import Config", "This will overwrite current settings. Continue?"):
                try:
                    self.config_manager.import_config(Path(file_path))
                    self.load_current_settings()
                    messagebox.showinfo("Success", "Configuration imported successfully")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to import configuration: {e}")