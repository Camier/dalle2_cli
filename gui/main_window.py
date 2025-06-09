import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import asyncio
import threading
import time
from pathlib import Path
from typing import Optional, List
from PIL import Image, ImageTk
import json

from ..core.security import SecurityManager
from ..core.config_manager import ConfigManager
from ..core.dalle_api import DALLEAPIManager, GenerationRequest, VariationRequest, EditRequest, ImageDownloader
from ..data.database import DatabaseManager, GenerationRecord, TemplateRecord
from ..utils.logger import logger
from .widgets.variations_tab import VariationsTab
from .widgets.edit_tab import EditTab
from .widgets.batch_tab import BatchTab
from .widgets.gallery_tab import GalleryTab
from .widgets.settings_tab import SettingsTab

# Set appearance mode and color theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class APIKeyDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Enter OpenAI API Key")
        self.geometry("400x200")
        self.transient(parent)
        self.grab_set()
        
        self.api_key = None
        
        # Center the dialog
        self.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
        
        self.create_widgets()
    
    def create_widgets(self):
        # Main frame
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_label = ctk.CTkLabel(main_frame, text="OpenAI API Key Required", 
                                  font=ctk.CTkFont(size=16, weight="bold"))
        title_label.pack(pady=(0, 10))
        
        # Instructions
        instructions = ctk.CTkLabel(main_frame, 
                                   text="Please enter your OpenAI API key to use DALL-E 2:",
                                   wraplength=350)
        instructions.pack(pady=(0, 10))
        
        # API Key entry
        self.api_key_entry = ctk.CTkEntry(main_frame, width=350, show="*", 
                                         placeholder_text="sk-...")
        self.api_key_entry.pack(pady=(0, 20))
        
        # Buttons frame
        buttons_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        buttons_frame.pack(fill="x")
        
        cancel_btn = ctk.CTkButton(buttons_frame, text="Cancel", 
                                  command=self.cancel, width=100)
        cancel_btn.pack(side="left", padx=(0, 10))
        
        ok_btn = ctk.CTkButton(buttons_frame, text="OK", 
                              command=self.ok, width=100)
        ok_btn.pack(side="right")
        
        # Bind Enter key
        self.api_key_entry.bind("<Return>", lambda e: self.ok())
        self.api_key_entry.focus()
    
    def ok(self):
        self.api_key = self.api_key_entry.get().strip()
        if self.api_key:
            self.destroy()
        else:
            messagebox.showerror("Error", "Please enter a valid API key")
    
    def cancel(self):
        self.api_key = None
        self.destroy()


class ImagePreview(ctk.CTkFrame):
    def __init__(self, parent, width=300, height=300):
        super().__init__(parent, width=width, height=height)
        
        self.image_label = ctk.CTkLabel(self, text="No image", width=width-20, height=height-20)
        self.image_label.pack(padx=10, pady=10)
        
        self.current_image = None
        self.current_path = None
    
    def display_image(self, image_path: Path):
        try:
            # Load and resize image
            pil_image = Image.open(image_path)
            # Calculate size maintaining aspect ratio
            img_width, img_height = pil_image.size
            max_width, max_height = 280, 280
            
            ratio = min(max_width/img_width, max_height/img_height)
            new_width = int(img_width * ratio)
            new_height = int(img_height * ratio)
            
            pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Convert to CTkImage
            ctk_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, 
                                    size=(new_width, new_height))
            
            self.image_label.configure(image=ctk_image, text="")
            self.current_image = ctk_image
            self.current_path = image_path
            
        except Exception as e:
            logger.error(f"Error displaying image: {e}")
            self.image_label.configure(image=None, text="Error loading image")
    
    def clear(self):
        self.image_label.configure(image=None, text="No image")
        self.current_image = None
        self.current_path = None


class GenerateTab(ctk.CTkFrame):
    def __init__(self, parent, api_manager: DALLEAPIManager, db_manager: DatabaseManager, 
                 config_manager: ConfigManager):
        super().__init__(parent)
        
        self.api_manager = api_manager
        self.db_manager = db_manager
        self.config_manager = config_manager
        
        self.create_widgets()
    
    def create_widgets(self):
        # Left panel for controls
        left_panel = ctk.CTkFrame(self)
        left_panel.pack(side="left", fill="y", padx=(10, 5), pady=10)
        
        # Right panel for preview
        right_panel = ctk.CTkFrame(self)
        right_panel.pack(side="right", fill="both", expand=True, padx=(5, 10), pady=10)
        
        # Controls in left panel
        controls_frame = ctk.CTkFrame(left_panel)
        controls_frame.pack(fill="x", padx=10, pady=10)
        
        # Prompt section
        prompt_label = ctk.CTkLabel(controls_frame, text="Prompt:", font=ctk.CTkFont(weight="bold"))
        prompt_label.pack(anchor="w", pady=(0, 5))
        
        self.prompt_text = ctk.CTkTextbox(controls_frame, width=350, height=100)
        self.prompt_text.pack(pady=(0, 10))
        
        # Recent prompts dropdown
        recent_label = ctk.CTkLabel(controls_frame, text="Recent Prompts:")
        recent_label.pack(anchor="w")
        
        self.recent_prompts = ctk.CTkComboBox(controls_frame, width=350, 
                                             command=self.load_recent_prompt)
        self.recent_prompts.pack(pady=(0, 10))
        self.update_recent_prompts()
        
        # Settings frame
        settings_frame = ctk.CTkFrame(controls_frame)
        settings_frame.pack(fill="x", pady=(0, 10))
        
        # Size selection
        size_label = ctk.CTkLabel(settings_frame, text="Size:")
        size_label.grid(row=0, column=0, sticky="w", padx=(10, 5), pady=5)
        
        self.size_var = ctk.StringVar(value=self.config_manager.config.default_size)
        size_combo = ctk.CTkComboBox(settings_frame, variable=self.size_var,
                                    values=["1024x1024", "1024x1792", "1792x1024"],
                                    width=150)
        size_combo.grid(row=0, column=1, padx=5, pady=5)
        
        # Quality selection
        quality_label = ctk.CTkLabel(settings_frame, text="Quality:")
        quality_label.grid(row=1, column=0, sticky="w", padx=(10, 5), pady=5)
        
        self.quality_var = ctk.StringVar(value=self.config_manager.config.default_quality)
        quality_combo = ctk.CTkComboBox(settings_frame, variable=self.quality_var,
                                       values=["standard", "hd"], width=150)
        quality_combo.grid(row=1, column=1, padx=5, pady=5)
        
        # Style selection
        style_label = ctk.CTkLabel(settings_frame, text="Style:")
        style_label.grid(row=2, column=0, sticky="w", padx=(10, 5), pady=5)
        
        self.style_var = ctk.StringVar(value=self.config_manager.config.default_style)
        style_combo = ctk.CTkComboBox(settings_frame, variable=self.style_var,
                                     values=["natural", "vivid"], width=150)
        style_combo.grid(row=2, column=1, padx=5, pady=5)
        
        # Number of images
        n_label = ctk.CTkLabel(settings_frame, text="Images:")
        n_label.grid(row=3, column=0, sticky="w", padx=(10, 5), pady=5)
        
        self.n_var = ctk.StringVar(value=str(self.config_manager.config.default_n))
        n_combo = ctk.CTkComboBox(settings_frame, variable=self.n_var,
                                 values=["1", "2", "3", "4"], width=150)
        n_combo.grid(row=3, column=1, padx=5, pady=5)
        
        # Style presets
        presets_label = ctk.CTkLabel(controls_frame, text="Style Presets:")
        presets_label.pack(anchor="w", pady=(10, 5))
        
        presets = list(self.config_manager.get_style_presets().keys())
        self.style_preset = ctk.CTkComboBox(controls_frame, width=350, values=presets,
                                           command=self.apply_style_preset)
        self.style_preset.pack(pady=(0, 10))
        
        # Generate button
        self.generate_btn = ctk.CTkButton(controls_frame, text="Generate Images", 
                                         command=self.generate_images, height=40,
                                         font=ctk.CTkFont(size=14, weight="bold"))
        self.generate_btn.pack(pady=10)
        
        # Progress bar
        self.progress = ctk.CTkProgressBar(controls_frame, width=350)
        self.progress.pack(pady=(0, 10))
        self.progress.set(0)
        
        # Status label
        self.status_label = ctk.CTkLabel(controls_frame, text="Ready")
        self.status_label.pack()
        
        # Preview area in right panel
        preview_label = ctk.CTkLabel(right_panel, text="Generated Images", 
                                   font=ctk.CTkFont(size=16, weight="bold"))
        preview_label.pack(pady=(10, 0))
        
        # Scrollable frame for images
        self.preview_scroll = ctk.CTkScrollableFrame(right_panel, width=400, height=500)
        self.preview_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.preview_images = []
    
    def update_recent_prompts(self):
        recent = self.db_manager.get_recent_prompts(10)
        if recent:
            self.recent_prompts.configure(values=recent)
    
    def load_recent_prompt(self, selection):
        if selection:
            self.prompt_text.delete("1.0", "end")
            self.prompt_text.insert("1.0", selection)
    
    def apply_style_preset(self, preset_name):
        if preset_name:
            presets = self.config_manager.get_style_presets()
            preset_text = presets.get(preset_name, "")
            if preset_text:
                current_prompt = self.prompt_text.get("1.0", "end-1c")
                if current_prompt and not current_prompt.endswith(", "):
                    current_prompt += ", "
                self.prompt_text.delete("1.0", "end")
                self.prompt_text.insert("1.0", current_prompt + preset_text)
    
    def generate_images(self):
        prompt = self.prompt_text.get("1.0", "end-1c").strip()
        if not prompt:
            messagebox.showerror("Error", "Please enter a prompt")
            return
        
        # Create generation request
        request = GenerationRequest(
            prompt=prompt,
            size=self.size_var.get(),
            quality=self.quality_var.get(),
            style=self.style_var.get(),
            n=int(self.n_var.get())
        )
        
        # Disable generate button and show progress
        self.generate_btn.configure(state="disabled", text="Generating...")
        self.progress.set(0)
        self.status_label.configure(text="Sending request to DALL-E...")
        
        # Clear previous images
        for widget in self.preview_scroll.winfo_children():
            widget.destroy()
        self.preview_images.clear()
        
        # Start generation in thread
        threading.Thread(target=self._generate_thread, args=(request,), daemon=True).start()
    
    def _generate_thread(self, request: GenerationRequest):
        try:
            # Run async generation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._generate_async(request))
            loop.close()
        except Exception as e:
            logger.error(f"Generation thread error: {e}")
            self._update_ui_after_error(str(e))
    
    async def _generate_async(self, request: GenerationRequest):
        try:
            # Update UI
            self.after(0, lambda: self.status_label.configure(text="Generating images..."))
            self.after(0, lambda: self.progress.set(0.3))
            
            # Generate images
            result = await self.api_manager.generate_image_async(request)
            
            if result.success:
                self.after(0, lambda: self.status_label.configure(text="Downloading images..."))
                self.after(0, lambda: self.progress.set(0.6))
                
                # Download images
                output_dir = self.config_manager.get_output_directory()
                timestamp = int(time.time())
                
                async with ImageDownloader(output_dir) as downloader:
                    image_paths = await downloader.download_multiple(
                        result.image_urls, 
                        f"generation_{timestamp}"
                    )
                
                if image_paths:
                    # Save to database
                    for i, image_path in enumerate(image_paths):
                        record = GenerationRecord(
                            prompt=request.prompt,
                            image_path=str(image_path),
                            cost=result.cost / len(image_paths),
                            size=request.size,
                            generation_type="generation",
                            metadata=json.dumps({
                                "quality": request.quality,
                                "style": request.style,
                                "revised_prompt": result.request_id
                            })
                        )
                        self.db_manager.add_generation(record)
                    
                    # Update UI with success
                    self.after(0, lambda: self._update_ui_after_success(image_paths, result.cost))
                else:
                    self.after(0, lambda: self._update_ui_after_error("Failed to download images"))
            else:
                self.after(0, lambda: self._update_ui_after_error(result.error))
        
        except Exception as e:
            logger.error(f"Async generation error: {e}")
            self.after(0, lambda: self._update_ui_after_error(str(e)))
    
    def _update_ui_after_success(self, image_paths: List[Path], cost: float):
        self.progress.set(1.0)
        self.status_label.configure(text=f"Generated {len(image_paths)} images (${cost:.4f})")
        
        # Display images
        for i, image_path in enumerate(image_paths):
            self._add_preview_image(image_path, i)
        
        # Re-enable generate button
        self.generate_btn.configure(state="normal", text="Generate Images")
        self.progress.set(0)
        
        # Update recent prompts
        self.update_recent_prompts()
        
        logger.log_api_request("generation", self.prompt_text.get("1.0", "end-1c"), cost)
    
    def _update_ui_after_error(self, error_message: str):
        self.progress.set(0)
        self.status_label.configure(text=f"Error: {error_message}")
        self.generate_btn.configure(state="normal", text="Generate Images")
        messagebox.showerror("Generation Error", error_message)
    
    def _add_preview_image(self, image_path: Path, index: int):
        # Create frame for this image
        image_frame = ctk.CTkFrame(self.preview_scroll)
        image_frame.pack(fill="x", padx=5, pady=5)
        
        # Load and display image
        try:
            pil_image = Image.open(image_path)
            # Resize for preview
            pil_image.thumbnail((200, 200), Image.Resampling.LANCZOS)
            
            ctk_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, 
                                    size=pil_image.size)
            
            image_label = ctk.CTkLabel(image_frame, image=ctk_image, text="")
            image_label.pack(side="left", padx=10, pady=10)
            
            # Buttons frame
            buttons_frame = ctk.CTkFrame(image_frame, fg_color="transparent")
            buttons_frame.pack(side="right", fill="y", padx=10, pady=10)
            
            # Save button
            save_btn = ctk.CTkButton(buttons_frame, text="Save As...", width=100,
                                    command=lambda: self._save_image(image_path))
            save_btn.pack(pady=2)
            
            # View full size button
            view_btn = ctk.CTkButton(buttons_frame, text="View Full", width=100,
                                    command=lambda: self._view_full_image(image_path))
            view_btn.pack(pady=2)
            
            self.preview_images.append((image_frame, image_path))
            
        except Exception as e:
            logger.error(f"Error creating preview for {image_path}: {e}")
    
    def _save_image(self, image_path: Path):
        filetypes = [
            ("PNG files", "*.png"),
            ("JPEG files", "*.jpg"),
            ("All files", "*.*")
        ]
        
        save_path = filedialog.asksaveasfilename(
            title="Save Image",
            defaultextension=".png",
            filetypes=filetypes,
            initialname=image_path.name
        )
        
        if save_path:
            try:
                import shutil
                shutil.copy2(image_path, save_path)
                messagebox.showinfo("Success", f"Image saved to {save_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save image: {e}")
    
    def _view_full_image(self, image_path: Path):
        # Open full size image in new window
        import subprocess
        import sys
        
        try:
            if sys.platform == "win32":
                subprocess.run(["start", str(image_path)], shell=True)
            elif sys.platform == "darwin":
                subprocess.run(["open", str(image_path)])
            else:
                subprocess.run(["xdg-open", str(image_path)])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open image: {e}")


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("DALL-E 2 Studio")
        self.geometry("1200x800")
        
        # Initialize managers
        self.security_manager = SecurityManager()
        self.config_manager = ConfigManager()
        self.db_manager = DatabaseManager(self.config_manager.get_database_path())
        
        # API manager will be initialized after getting API key
        self.api_manager = None
        
        # Check for API key
        if not self._ensure_api_key():
            self.destroy()
            return
        
        self.create_widgets()
        
        # Start API manager
        self._start_api_manager()
    
    def _ensure_api_key(self) -> bool:
        api_key = self.security_manager.load_api_key()
        
        if not api_key:
            dialog = APIKeyDialog(self)
            self.wait_window(dialog)
            
            if dialog.api_key:
                if self.security_manager.save_api_key(dialog.api_key):
                    api_key = dialog.api_key
                else:
                    messagebox.showerror("Error", "Failed to save API key")
                    return False
            else:
                return False
        
        # Test API key
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)
            # Make a simple test call
            models = client.models.list()
            return True
        except Exception as e:
            messagebox.showerror("Invalid API Key", 
                               f"The API key is invalid or there was an error: {e}")
            self.security_manager.clear_api_key()
            return self._ensure_api_key()  # Recursive call to try again
    
    def _start_api_manager(self):
        api_key = self.security_manager.load_api_key()
        if api_key:
            self.api_manager = DALLEAPIManager(api_key, self.config_manager.config.max_workers)
            
            # Start the API manager in a separate thread
            def start_manager():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.api_manager.start())
            
            threading.Thread(target=start_manager, daemon=True).start()
    
    def create_widgets(self):
        # Create tabview
        self.tabview = ctk.CTkTabview(self, width=1180, height=750)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Add tabs
        self.generate_tab = self.tabview.add("Generate")
        self.variations_tab = self.tabview.add("Variations")
        self.edit_tab = self.tabview.add("Edit")
        self.batch_tab = self.tabview.add("Batch")
        self.gallery_tab = self.tabview.add("Gallery")
        self.settings_tab = self.tabview.add("Settings")
        
        # Initialize tabs
        if self.api_manager:
            self.generate_widget = GenerateTab(self.generate_tab, self.api_manager, 
                                             self.db_manager, self.config_manager)
            self.generate_widget.pack(fill="both", expand=True)
            
            self.variations_widget = VariationsTab(self.variations_tab, self.api_manager,
                                                 self.db_manager, self.config_manager)
            self.variations_widget.pack(fill="both", expand=True)
            
            self.edit_widget = EditTab(self.edit_tab, self.api_manager,
                                     self.db_manager, self.config_manager)
            self.edit_widget.pack(fill="both", expand=True)
            
            self.batch_widget = BatchTab(self.batch_tab, self.api_manager,
                                       self.db_manager, self.config_manager)
            self.batch_widget.pack(fill="both", expand=True)
            
            self.gallery_widget = GalleryTab(self.gallery_tab, self.db_manager, 
                                           self.config_manager)
            self.gallery_widget.pack(fill="both", expand=True)
            
            self.settings_widget = SettingsTab(self.settings_tab, self.config_manager,
                                             self.security_manager, self.db_manager)
            self.settings_widget.pack(fill="both", expand=True)
        
        # Create status bar
        self.status_bar = ctk.CTkFrame(self, height=30)
        self.status_bar.pack(fill="x", side="bottom")
        
        self.status_label = ctk.CTkLabel(self.status_bar, text="Ready")
        self.status_label.pack(side="left", padx=10, pady=5)
        
        # Cost display
        total_cost = self.db_manager.get_total_cost()
        self.cost_label = ctk.CTkLabel(self.status_bar, text=f"Total Cost: ${total_cost:.2f}")
        self.cost_label.pack(side="right", padx=10, pady=5)
    
    def on_closing(self):
        # Stop API manager
        if self.api_manager:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.api_manager.stop())
                loop.close()
            except:
                pass
        
        self.destroy()


def main():
    import time
    
    app = MainWindow()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()