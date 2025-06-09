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
# tkinterdnd2 import with fallback

from ...core.dalle_api import DALLEAPIManager, VariationRequest, ImageDownloader
from ...data.database import DatabaseManager, GenerationRecord
from ...core.config_manager import ConfigManager
from ...utils.logger import logger


class DragDropFrame(ctk.CTkFrame):
    def __init__(self, parent, on_drop_callback=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_drop_callback = on_drop_callback
        
        # Visual feedback
        self.configure(border_width=2, border_color="gray")
        
        # Instructions label
        self.instructions = ctk.CTkLabel(
            self, 
            text="Click to browse for an image",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        self.instructions.pack(expand=True)
        
        # Click to browse
        self.bind("<Button-1>", self._on_click)
        self.instructions.bind("<Button-1>", self._on_click)
        
        self.current_image_path = None
    
    def _on_click(self, event):
        file_path = filedialog.askopenfilename(
            title="Select Image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg *.jpeg"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            self._load_image(file_path)
    
    def _is_image_file(self, file_path):
        valid_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        return Path(file_path).suffix.lower() in valid_extensions
    
    def _load_image(self, file_path):
        try:
            self.current_image_path = Path(file_path)
            
            # Load and display preview
            pil_image = Image.open(file_path)
            
            # Resize for preview while maintaining aspect ratio
            max_size = 200
            pil_image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Update the display
            ctk_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, 
                                    size=pil_image.size)
            
            self.instructions.configure(image=ctk_image, text="")
            self.configure(border_color="green")
            
            # Call callback if provided
            if self.on_drop_callback:
                self.on_drop_callback(self.current_image_path)
                
        except Exception as e:
            logger.error(f"Error loading image: {e}")
            messagebox.showerror("Error", f"Failed to load image: {e}")
            self.configure(border_color="red")
    
    def clear(self):
        self.instructions.configure(image=None, text="Click to browse for an image")
        self.configure(border_color="gray")
        self.current_image_path = None


class VariationsTab(ctk.CTkFrame):
    def __init__(self, parent, api_manager: DALLEAPIManager, db_manager: DatabaseManager, 
                 config_manager: ConfigManager):
        super().__init__(parent)
        
        self.api_manager = api_manager
        self.db_manager = db_manager
        self.config_manager = config_manager
        
        self.create_widgets()
    
    def create_widgets(self):
        # Main layout: left controls, right preview
        left_panel = ctk.CTkFrame(self)
        left_panel.pack(side="left", fill="y", padx=(10, 5), pady=10)
        
        right_panel = ctk.CTkFrame(self)
        right_panel.pack(side="right", fill="both", expand=True, padx=(5, 10), pady=10)
        
        # Left panel controls
        controls_frame = ctk.CTkFrame(left_panel)
        controls_frame.pack(fill="x", padx=10, pady=10)
        
        # Image upload section
        upload_label = ctk.CTkLabel(controls_frame, text="Source Image:", 
                                   font=ctk.CTkFont(weight="bold"))
        upload_label.pack(anchor="w", pady=(0, 5))
        
        self.drag_drop_frame = DragDropFrame(controls_frame, 
                                           on_drop_callback=self._on_image_loaded,
                                           width=350, height=200)
        self.drag_drop_frame.pack(pady=(0, 10))
        
        # Settings frame
        settings_frame = ctk.CTkFrame(controls_frame)
        settings_frame.pack(fill="x", pady=(0, 10))
        
        # Size selection
        size_label = ctk.CTkLabel(settings_frame, text="Size:")
        size_label.grid(row=0, column=0, sticky="w", padx=(10, 5), pady=5)
        
        self.size_var = ctk.StringVar(value="1024x1024")
        size_combo = ctk.CTkComboBox(settings_frame, variable=self.size_var,
                                    values=["1024x1024", "512x512", "256x256"],
                                    width=200)
        size_combo.grid(row=0, column=1, padx=5, pady=5)
        
        # Number of variations
        n_label = ctk.CTkLabel(settings_frame, text="Variations:")
        n_label.grid(row=1, column=0, sticky="w", padx=(10, 5), pady=5)
        
        self.n_var = ctk.StringVar(value="2")
        n_combo = ctk.CTkComboBox(settings_frame, variable=self.n_var,
                                 values=["1", "2", "3", "4", "5"], width=200)
        n_combo.grid(row=1, column=1, padx=5, pady=5)
        
        # Image info frame
        self.info_frame = ctk.CTkFrame(controls_frame)
        self.info_frame.pack(fill="x", pady=(0, 10))
        
        self.info_label = ctk.CTkLabel(self.info_frame, text="No image selected", 
                                      wraplength=330)
        self.info_label.pack(padx=10, pady=10)
        
        # Generate variations button
        self.generate_btn = ctk.CTkButton(controls_frame, text="Generate Variations", 
                                         command=self.generate_variations, height=40,
                                         font=ctk.CTkFont(size=14, weight="bold"),
                                         state="disabled")
        self.generate_btn.pack(pady=10)
        
        # Progress bar
        self.progress = ctk.CTkProgressBar(controls_frame, width=350)
        self.progress.pack(pady=(0, 10))
        self.progress.set(0)
        
        # Status label
        self.status_label = ctk.CTkLabel(controls_frame, text="Select an image to begin")
        self.status_label.pack()
        
        # Cost estimate
        self.cost_label = ctk.CTkLabel(controls_frame, text="", 
                                      font=ctk.CTkFont(size=12))
        self.cost_label.pack(pady=(5, 0))
        
        # Right panel - preview area
        preview_label = ctk.CTkLabel(right_panel, text="Generated Variations", 
                                   font=ctk.CTkFont(size=16, weight="bold"))
        preview_label.pack(pady=(10, 0))
        
        # Scrollable frame for variations
        self.preview_scroll = ctk.CTkScrollableFrame(right_panel, width=400, height=500)
        self.preview_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.preview_images = []
        
        # Update cost estimate when settings change
        self.size_var.trace('w', self._update_cost_estimate)
        self.n_var.trace('w', self._update_cost_estimate)
    
    def _on_image_loaded(self, image_path: Path):
        try:
            # Load image and get info
            pil_image = Image.open(image_path)
            width, height = pil_image.size
            file_size = image_path.stat().st_size / 1024  # KB
            
            # Update info display
            info_text = f"Image: {image_path.name}\nSize: {width}×{height}\nFile: {file_size:.1f} KB"
            self.info_label.configure(text=info_text)
            
            # Enable generate button
            self.generate_btn.configure(state="normal")
            self.status_label.configure(text="Ready to generate variations")
            
            # Update cost estimate
            self._update_cost_estimate()
            
        except Exception as e:
            logger.error(f"Error processing uploaded image: {e}")
            messagebox.showerror("Error", f"Failed to process image: {e}")
    
    def _update_cost_estimate(self, *args):
        if not self.drag_drop_frame.current_image_path:
            self.cost_label.configure(text="")
            return
        
        try:
            size = self.size_var.get()
            n = int(self.n_var.get())
            
            # Calculate cost based on DALL-E 2 pricing
            costs = {"1024x1024": 0.02, "512x512": 0.018, "256x256": 0.016}
            cost_per_image = costs.get(size, 0.02)
            total_cost = cost_per_image * n
            
            self.cost_label.configure(text=f"Estimated cost: ${total_cost:.4f}")
            
        except ValueError:
            self.cost_label.configure(text="")
    
    def generate_variations(self):
        if not self.drag_drop_frame.current_image_path:
            messagebox.showerror("Error", "Please select an image first")
            return
        
        # Validate image format and size
        try:
            pil_image = Image.open(self.drag_drop_frame.current_image_path)
            width, height = pil_image.size
            
            # DALL-E 2 requires square images and PNG format
            if width != height:
                messagebox.showerror("Error", 
                                   "Image must be square (same width and height). "
                                   "Please crop your image to square dimensions.")
                return
            
            if pil_image.format != 'PNG':
                # Convert to PNG
                temp_path = self.config_manager.get_cache_directory() / f"temp_{int(time.time())}.png"
                pil_image.save(temp_path, "PNG")
                image_path = temp_path
            else:
                image_path = self.drag_drop_frame.current_image_path
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to process image: {e}")
            return
        
        # Create variation request
        request = VariationRequest(
            image_path=str(image_path),
            size=self.size_var.get(),
            n=int(self.n_var.get())
        )
        
        # Disable generate button and show progress
        self.generate_btn.configure(state="disabled", text="Generating...")
        self.progress.set(0)
        self.status_label.configure(text="Creating variations...")
        
        # Clear previous variations
        for widget in self.preview_scroll.winfo_children():
            widget.destroy()
        self.preview_images.clear()
        
        # Start generation in thread
        threading.Thread(target=self._generate_thread, args=(request,), daemon=True).start()
    
    def _generate_thread(self, request: VariationRequest):
        try:
            # Run async generation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._generate_async(request))
            loop.close()
        except Exception as e:
            logger.error(f"Variation generation thread error: {e}")
            self.after(0, lambda: self._update_ui_after_error(str(e)))
    
    async def _generate_async(self, request: VariationRequest):
        try:
            # Update UI
            self.after(0, lambda: self.status_label.configure(text="Generating variations..."))
            self.after(0, lambda: self.progress.set(0.3))
            
            # Generate variations
            result = await self.api_manager.create_variation_async(request)
            
            if result.success:
                self.after(0, lambda: self.status_label.configure(text="Downloading variations..."))
                self.after(0, lambda: self.progress.set(0.6))
                
                # Download images
                output_dir = self.config_manager.get_output_directory() / "variations"
                output_dir.mkdir(exist_ok=True)
                timestamp = int(time.time())
                
                async with ImageDownloader(output_dir) as downloader:
                    image_paths = await downloader.download_multiple(
                        result.image_urls, 
                        f"variation_{timestamp}"
                    )
                
                if image_paths:
                    # Save to database
                    original_image_name = Path(request.image_path).name
                    for i, image_path in enumerate(image_paths):
                        record = GenerationRecord(
                            prompt=f"Variation of {original_image_name}",
                            image_path=str(image_path),
                            cost=result.cost / len(image_paths),
                            size=request.size,
                            generation_type="variation",
                            metadata=json.dumps({
                                "source_image": request.image_path,
                                "variation_index": i + 1
                            })
                        )
                        self.db_manager.add_generation(record)
                    
                    # Update UI with success
                    self.after(0, lambda: self._update_ui_after_success(image_paths, result.cost))
                else:
                    self.after(0, lambda: self._update_ui_after_error("Failed to download variations"))
            else:
                self.after(0, lambda: self._update_ui_after_error(result.error))
        
        except Exception as e:
            logger.error(f"Async variation generation error: {e}")
            self.after(0, lambda: self._update_ui_after_error(str(e)))
    
    def _update_ui_after_success(self, image_paths: List[Path], cost: float):
        self.progress.set(1.0)
        self.status_label.configure(text=f"Generated {len(image_paths)} variations (${cost:.4f})")
        
        # Display variations
        for i, image_path in enumerate(image_paths):
            self._add_preview_image(image_path, i)
        
        # Re-enable generate button
        self.generate_btn.configure(state="normal", text="Generate Variations")
        self.progress.set(0)
        
        logger.log_api_request("variation", f"Variation #{len(image_paths)}", cost)
    
    def _update_ui_after_error(self, error_message: str):
        self.progress.set(0)
        self.status_label.configure(text=f"Error: {error_message}")
        self.generate_btn.configure(state="normal", text="Generate Variations")
        messagebox.showerror("Variation Error", error_message)
    
    def _add_preview_image(self, image_path: Path, index: int):
        # Create frame for this variation
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
            
            # Info and buttons frame
            info_frame = ctk.CTkFrame(image_frame, fg_color="transparent")
            info_frame.pack(side="right", fill="y", padx=10, pady=10)
            
            # Variation info
            info_label = ctk.CTkLabel(info_frame, text=f"Variation {index + 1}", 
                                     font=ctk.CTkFont(weight="bold"))
            info_label.pack(pady=(0, 10))
            
            # Buttons
            save_btn = ctk.CTkButton(info_frame, text="Save As...", width=100,
                                    command=lambda: self._save_image(image_path))
            save_btn.pack(pady=2)
            
            view_btn = ctk.CTkButton(info_frame, text="View Full", width=100,
                                    command=lambda: self._view_full_image(image_path))
            view_btn.pack(pady=2)
            
            # Use as source button
            use_btn = ctk.CTkButton(info_frame, text="Use as Source", width=100,
                                   command=lambda: self._use_as_source(image_path))
            use_btn.pack(pady=2)
            
            self.preview_images.append((image_frame, image_path))
            
        except Exception as e:
            logger.error(f"Error creating preview for variation {image_path}: {e}")
    
    def _save_image(self, image_path: Path):
        filetypes = [
            ("PNG files", "*.png"),
            ("JPEG files", "*.jpg"),
            ("All files", "*.*")
        ]
        
        save_path = filedialog.asksaveasfilename(
            title="Save Variation",
            defaultextension=".png",
            filetypes=filetypes,
            initialname=image_path.name
        )
        
        if save_path:
            try:
                import shutil
                shutil.copy2(image_path, save_path)
                messagebox.showinfo("Success", f"Variation saved to {save_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save variation: {e}")
    
    def _view_full_image(self, image_path: Path):
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
    
    def _use_as_source(self, image_path: Path):
        """Use this variation as the source for generating more variations"""
        self.drag_drop_frame.clear()
        self.drag_drop_frame._load_image(str(image_path))
        messagebox.showinfo("Source Updated", "This variation is now set as the source image")