import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import asyncio
import threading
import time
from pathlib import Path
from typing import Optional, List
from PIL import Image, ImageTk, ImageDraw
import json
import numpy as np

from ...core.dalle_api import DALLEAPIManager, EditRequest, ImageDownloader
from ...data.database import DatabaseManager, GenerationRecord
from ...core.config_manager import ConfigManager
from ...utils.logger import logger


class MaskCanvas(ctk.CTkFrame):
    def __init__(self, parent, width=400, height=400):
        super().__init__(parent, width=width, height=height)
        
        self.canvas_width = width - 20
        self.canvas_height = height - 20
        
        # Create canvas for mask drawing
        self.canvas = tk.Canvas(self, width=self.canvas_width, height=self.canvas_height,
                               bg="white", cursor="crosshair")
        self.canvas.pack(padx=10, pady=10)
        
        # Drawing state
        self.drawing = False
        self.brush_size = 20
        self.mask_image = None
        self.original_image = None
        self.display_image = None
        self.image_scale = 1.0
        
        # Bind mouse events
        self.canvas.bind("<Button-1>", self.start_draw)
        self.canvas.bind("<B1-Motion>", self.draw)
        self.canvas.bind("<ButtonRelease-1>", self.stop_draw)
        
        # Drawing mode: 'mask' or 'erase'
        self.draw_mode = 'mask'
    
    def load_image(self, image_path: Path):
        try:
            self.original_image = Image.open(image_path)
            
            # Calculate scaling to fit canvas
            img_width, img_height = self.original_image.size
            scale_x = self.canvas_width / img_width
            scale_y = self.canvas_height / img_height
            self.image_scale = min(scale_x, scale_y, 1.0)  # Don't upscale
            
            # Resize image for display
            new_width = int(img_width * self.image_scale)
            new_height = int(img_height * self.image_scale)
            
            self.display_image = self.original_image.resize(
                (new_width, new_height), Image.Resampling.LANCZOS
            )
            
            # Create initial mask (transparent)
            self.mask_image = Image.new('RGBA', (new_width, new_height), (0, 0, 0, 0))
            
            # Display the image
            self.update_canvas()
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading image for editing: {e}")
            return False
    
    def update_canvas(self):
        if self.display_image and self.mask_image:
            # Composite the image with the mask overlay
            overlay = self.display_image.copy().convert('RGBA')
            
            # Create red overlay for masked areas
            mask_overlay = Image.new('RGBA', overlay.size, (255, 0, 0, 0))
            mask_draw = ImageDraw.Draw(mask_overlay)
            
            # Draw mask as semi-transparent red
            for x in range(self.mask_image.width):
                for y in range(self.mask_image.height):
                    if self.mask_image.getpixel((x, y))[3] > 0:  # If alpha > 0
                        mask_draw.point((x, y), fill=(255, 0, 0, 100))
            
            # Composite the overlay
            result = Image.alpha_composite(overlay, mask_overlay)
            
            # Convert to PhotoImage and display
            self.photo_image = ImageTk.PhotoImage(result)
            
            # Clear canvas and draw image
            self.canvas.delete("all")
            
            # Center the image on canvas
            x_offset = (self.canvas_width - result.width) // 2
            y_offset = (self.canvas_height - result.height) // 2
            
            self.canvas.create_image(x_offset, y_offset, anchor="nw", image=self.photo_image)
    
    def start_draw(self, event):
        self.drawing = True
        self.draw(event)
    
    def draw(self, event):
        if not self.drawing or not self.mask_image:
            return
        
        # Convert canvas coordinates to image coordinates
        x_offset = (self.canvas_width - self.display_image.width) // 2
        y_offset = (self.canvas_height - self.display_image.height) // 2
        
        x = event.x - x_offset
        y = event.y - y_offset
        
        # Check if within image bounds
        if 0 <= x < self.display_image.width and 0 <= y < self.display_image.height:
            # Draw on mask
            mask_draw = ImageDraw.Draw(self.mask_image)
            
            if self.draw_mode == 'mask':
                # Draw white circle (masked area)
                mask_draw.ellipse([
                    x - self.brush_size//2, y - self.brush_size//2,
                    x + self.brush_size//2, y + self.brush_size//2
                ], fill=(255, 255, 255, 255))
            else:  # erase mode
                # Draw transparent circle
                mask_draw.ellipse([
                    x - self.brush_size//2, y - self.brush_size//2,
                    x + self.brush_size//2, y + self.brush_size//2
                ], fill=(0, 0, 0, 0))
            
            self.update_canvas()
    
    def stop_draw(self, event):
        self.drawing = False
    
    def set_brush_size(self, size):
        self.brush_size = size
    
    def set_draw_mode(self, mode):
        self.draw_mode = mode
    
    def clear_mask(self):
        if self.mask_image:
            self.mask_image = Image.new('RGBA', self.mask_image.size, (0, 0, 0, 0))
            self.update_canvas()
    
    def get_mask_for_api(self) -> Optional[Path]:
        """Save mask in format required by DALL-E API and return path"""
        if not self.mask_image or not self.original_image:
            return None
        
        try:
            # Scale mask back to original image size
            original_size = self.original_image.size
            mask_resized = self.mask_image.resize(original_size, Image.Resampling.NEAREST)
            
            # Convert to grayscale (white = masked, black = unmasked)
            mask_gray = Image.new('L', original_size, 0)
            
            for x in range(original_size[0]):
                for y in range(original_size[1]):
                    if mask_resized.getpixel((x, y))[3] > 128:  # If mostly opaque
                        mask_gray.putpixel((x, y), 255)
            
            # Save mask to temporary file
            temp_path = Path.cwd() / "temp_mask.png"
            mask_gray.save(temp_path, "PNG")
            
            return temp_path
            
        except Exception as e:
            logger.error(f"Error creating mask for API: {e}")
            return None


class EditTab(ctk.CTkFrame):
    def __init__(self, parent, api_manager: DALLEAPIManager, db_manager: DatabaseManager, 
                 config_manager: ConfigManager):
        super().__init__(parent)
        
        self.api_manager = api_manager
        self.db_manager = db_manager
        self.config_manager = config_manager
        
        self.current_image_path = None
        
        self.create_widgets()
    
    def create_widgets(self):
        # Main layout: left controls, center canvas, right preview
        left_panel = ctk.CTkFrame(self)
        left_panel.pack(side="left", fill="y", padx=(10, 5), pady=10)
        
        center_panel = ctk.CTkFrame(self)
        center_panel.pack(side="left", fill="both", expand=True, padx=5, pady=10)
        
        right_panel = ctk.CTkFrame(self)
        right_panel.pack(side="right", fill="y", padx=(5, 10), pady=10)
        
        # Left panel - controls
        self.create_left_panel(left_panel)
        
        # Center panel - mask canvas
        self.create_center_panel(center_panel)
        
        # Right panel - results
        self.create_right_panel(right_panel)
    
    def create_left_panel(self, parent):
        controls_frame = ctk.CTkFrame(parent)
        controls_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Load image section
        load_label = ctk.CTkLabel(controls_frame, text="Source Image:", 
                                 font=ctk.CTkFont(weight="bold"))
        load_label.pack(anchor="w", pady=(0, 5))
        
        load_btn = ctk.CTkButton(controls_frame, text="Load Image", 
                                command=self.load_image, width=200)
        load_btn.pack(pady=(0, 10))
        
        self.image_info_label = ctk.CTkLabel(controls_frame, text="No image loaded", 
                                           wraplength=180)
        self.image_info_label.pack(pady=(0, 15))
        
        # Mask tools section
        mask_label = ctk.CTkLabel(controls_frame, text="Mask Tools:", 
                                 font=ctk.CTkFont(weight="bold"))
        mask_label.pack(anchor="w", pady=(0, 5))
        
        # Drawing mode
        mode_frame = ctk.CTkFrame(controls_frame)
        mode_frame.pack(fill="x", pady=(0, 10))
        
        self.draw_mode_var = ctk.StringVar(value="mask")
        
        mask_radio = ctk.CTkRadioButton(mode_frame, text="Draw Mask", 
                                       variable=self.draw_mode_var, value="mask",
                                       command=self.update_draw_mode)
        mask_radio.pack(anchor="w", padx=10, pady=2)
        
        erase_radio = ctk.CTkRadioButton(mode_frame, text="Erase Mask", 
                                        variable=self.draw_mode_var, value="erase",
                                        command=self.update_draw_mode)
        erase_radio.pack(anchor="w", padx=10, pady=2)
        
        # Brush size
        brush_label = ctk.CTkLabel(controls_frame, text="Brush Size:")
        brush_label.pack(anchor="w", pady=(5, 0))
        
        self.brush_slider = ctk.CTkSlider(controls_frame, from_=5, to=50, 
                                         command=self.update_brush_size, width=200)
        self.brush_slider.set(20)
        self.brush_slider.pack(pady=5)
        
        self.brush_size_label = ctk.CTkLabel(controls_frame, text="Size: 20px")
        self.brush_size_label.pack()
        
        # Mask actions
        clear_btn = ctk.CTkButton(controls_frame, text="Clear Mask", 
                                 command=self.clear_mask, width=200)
        clear_btn.pack(pady=(10, 5))
        
        # Prompt section
        prompt_label = ctk.CTkLabel(controls_frame, text="Edit Prompt:", 
                                   font=ctk.CTkFont(weight="bold"))
        prompt_label.pack(anchor="w", pady=(15, 5))
        
        self.prompt_text = ctk.CTkTextbox(controls_frame, width=200, height=80)
        self.prompt_text.pack(pady=(0, 10))
        
        # Settings
        settings_frame = ctk.CTkFrame(controls_frame)
        settings_frame.pack(fill="x", pady=(0, 10))
        
        # Size
        size_label = ctk.CTkLabel(settings_frame, text="Size:")
        size_label.pack(anchor="w", padx=10, pady=(10, 0))
        
        self.size_var = ctk.StringVar(value="1024x1024")
        size_combo = ctk.CTkComboBox(settings_frame, variable=self.size_var,
                                    values=["1024x1024", "512x512", "256x256"],
                                    width=180)
        size_combo.pack(padx=10, pady=5)
        
        # Number of images
        n_label = ctk.CTkLabel(settings_frame, text="Images:")
        n_label.pack(anchor="w", padx=10, pady=(5, 0))
        
        self.n_var = ctk.StringVar(value="1")
        n_combo = ctk.CTkComboBox(settings_frame, variable=self.n_var,
                                 values=["1", "2", "3", "4"], width=180)
        n_combo.pack(padx=10, pady=(5, 10))
        
        # Generate button
        self.generate_btn = ctk.CTkButton(controls_frame, text="Generate Edit", 
                                         command=self.generate_edit, height=40,
                                         font=ctk.CTkFont(size=14, weight="bold"),
                                         state="disabled")
        self.generate_btn.pack(pady=10)
        
        # Progress
        self.progress = ctk.CTkProgressBar(controls_frame, width=200)
        self.progress.pack(pady=(0, 5))
        self.progress.set(0)
        
        # Status
        self.status_label = ctk.CTkLabel(controls_frame, text="Load an image to begin",
                                        wraplength=180)
        self.status_label.pack()
    
    def create_center_panel(self, parent):
        canvas_label = ctk.CTkLabel(parent, text="Image Editor", 
                                   font=ctk.CTkFont(size=16, weight="bold"))
        canvas_label.pack(pady=(10, 0))
        
        instructions_label = ctk.CTkLabel(parent, 
                                         text="Draw on the image to mark areas for editing",
                                         font=ctk.CTkFont(size=12))
        instructions_label.pack(pady=(0, 10))
        
        # Mask canvas
        self.mask_canvas = MaskCanvas(parent, width=500, height=500)
        self.mask_canvas.pack(padx=10, pady=10)
    
    def create_right_panel(self, parent):
        results_label = ctk.CTkLabel(parent, text="Generated Edits", 
                                    font=ctk.CTkFont(size=16, weight="bold"))
        results_label.pack(pady=(10, 0))
        
        # Scrollable frame for results
        self.results_scroll = ctk.CTkScrollableFrame(parent, width=300, height=400)
        self.results_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.result_images = []
    
    def load_image(self):
        file_path = filedialog.askopenfilename(
            title="Select Image to Edit",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg"),
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg *.jpeg"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            self.current_image_path = Path(file_path)
            
            if self.mask_canvas.load_image(self.current_image_path):
                # Update UI
                pil_image = Image.open(file_path)
                width, height = pil_image.size
                file_size = self.current_image_path.stat().st_size / 1024
                
                info_text = f"Loaded: {self.current_image_path.name}\n{width}×{height}\n{file_size:.1f} KB"
                self.image_info_label.configure(text=info_text)
                
                self.generate_btn.configure(state="normal")
                self.status_label.configure(text="Draw mask areas and add prompt")
            else:
                messagebox.showerror("Error", "Failed to load image")
    
    def update_draw_mode(self):
        mode = self.draw_mode_var.get()
        self.mask_canvas.set_draw_mode(mode)
    
    def update_brush_size(self, value):
        size = int(value)
        self.mask_canvas.set_brush_size(size)
        self.brush_size_label.configure(text=f"Size: {size}px")
    
    def clear_mask(self):
        self.mask_canvas.clear_mask()
    
    def generate_edit(self):
        if not self.current_image_path:
            messagebox.showerror("Error", "Please load an image first")
            return
        
        prompt = self.prompt_text.get("1.0", "end-1c").strip()
        if not prompt:
            messagebox.showerror("Error", "Please enter an edit prompt")
            return
        
        # Get mask from canvas
        mask_path = self.mask_canvas.get_mask_for_api()
        
        # Prepare image for API (must be PNG and square)
        try:
            pil_image = Image.open(self.current_image_path)
            width, height = pil_image.size
            
            if width != height:
                # Make square by cropping to center
                size = min(width, height)
                left = (width - size) // 2
                top = (height - size) // 2
                pil_image = pil_image.crop((left, top, left + size, top + size))
            
            # Convert to PNG if needed
            temp_image_path = self.config_manager.get_cache_directory() / f"edit_image_{int(time.time())}.png"
            pil_image.save(temp_image_path, "PNG")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to prepare image: {e}")
            return
        
        # Create edit request
        request = EditRequest(
            image_path=str(temp_image_path),
            mask_path=str(mask_path) if mask_path else None,
            prompt=prompt,
            size=self.size_var.get(),
            n=int(self.n_var.get())
        )
        
        # Disable generate button and show progress
        self.generate_btn.configure(state="disabled", text="Generating...")
        self.progress.set(0)
        self.status_label.configure(text="Creating edited images...")
        
        # Clear previous results
        for widget in self.results_scroll.winfo_children():
            widget.destroy()
        self.result_images.clear()
        
        # Start generation in thread
        threading.Thread(target=self._generate_thread, args=(request,), daemon=True).start()
    
    def _generate_thread(self, request: EditRequest):
        try:
            # Run async generation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._generate_async(request))
            loop.close()
        except Exception as e:
            logger.error(f"Edit generation thread error: {e}")
            self.after(0, lambda: self._update_ui_after_error(str(e)))
    
    async def _generate_async(self, request: EditRequest):
        try:
            # Update UI
            self.after(0, lambda: self.status_label.configure(text="Processing edit..."))
            self.after(0, lambda: self.progress.set(0.3))
            
            # Generate edited images
            result = await self.api_manager.edit_image_async(request)
            
            if result.success:
                self.after(0, lambda: self.status_label.configure(text="Downloading results..."))
                self.after(0, lambda: self.progress.set(0.6))
                
                # Download images
                output_dir = self.config_manager.get_output_directory() / "edits"
                output_dir.mkdir(exist_ok=True)
                timestamp = int(time.time())
                
                async with ImageDownloader(output_dir) as downloader:
                    image_paths = await downloader.download_multiple(
                        result.image_urls, 
                        f"edit_{timestamp}"
                    )
                
                if image_paths:
                    # Save to database
                    for i, image_path in enumerate(image_paths):
                        record = GenerationRecord(
                            prompt=f"Edit: {request.prompt}",
                            image_path=str(image_path),
                            cost=result.cost / len(image_paths),
                            size=request.size,
                            generation_type="edit",
                            metadata=json.dumps({
                                "source_image": request.image_path,
                                "has_mask": request.mask_path is not None,
                                "edit_index": i + 1
                            })
                        )
                        self.db_manager.add_generation(record)
                    
                    # Update UI with success
                    self.after(0, lambda: self._update_ui_after_success(image_paths, result.cost))
                else:
                    self.after(0, lambda: self._update_ui_after_error("Failed to download edited images"))
            else:
                self.after(0, lambda: self._update_ui_after_error(result.error))
        
        except Exception as e:
            logger.error(f"Async edit generation error: {e}")
            self.after(0, lambda: self._update_ui_after_error(str(e)))
        finally:
            # Clean up temporary files
            try:
                if Path(request.image_path).exists():
                    Path(request.image_path).unlink()
                if request.mask_path and Path(request.mask_path).exists():
                    Path(request.mask_path).unlink()
            except:
                pass
    
    def _update_ui_after_success(self, image_paths: List[Path], cost: float):
        self.progress.set(1.0)
        self.status_label.configure(text=f"Generated {len(image_paths)} edits (${cost:.4f})")
        
        # Display results
        for i, image_path in enumerate(image_paths):
            self._add_result_image(image_path, i)
        
        # Re-enable generate button
        self.generate_btn.configure(state="normal", text="Generate Edit")
        self.progress.set(0)
        
        logger.log_api_request("edit", self.prompt_text.get("1.0", "end-1c"), cost)
    
    def _update_ui_after_error(self, error_message: str):
        self.progress.set(0)
        self.status_label.configure(text=f"Error: {error_message}")
        self.generate_btn.configure(state="normal", text="Generate Edit")
        messagebox.showerror("Edit Error", error_message)
    
    def _add_result_image(self, image_path: Path, index: int):
        # Create frame for this result
        result_frame = ctk.CTkFrame(self.results_scroll)
        result_frame.pack(fill="x", padx=5, pady=5)
        
        try:
            # Load and display image
            pil_image = Image.open(image_path)
            pil_image.thumbnail((250, 250), Image.Resampling.LANCZOS)
            
            ctk_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, 
                                    size=pil_image.size)
            
            image_label = ctk.CTkLabel(result_frame, image=ctk_image, text="")
            image_label.pack(padx=10, pady=10)
            
            # Buttons
            buttons_frame = ctk.CTkFrame(result_frame, fg_color="transparent")
            buttons_frame.pack(fill="x", padx=10, pady=(0, 10))
            
            save_btn = ctk.CTkButton(buttons_frame, text="Save", width=80,
                                    command=lambda: self._save_result(image_path))
            save_btn.pack(side="left", padx=5)
            
            view_btn = ctk.CTkButton(buttons_frame, text="View", width=80,
                                    command=lambda: self._view_result(image_path))
            view_btn.pack(side="left", padx=5)
            
            use_btn = ctk.CTkButton(buttons_frame, text="Edit More", width=80,
                                   command=lambda: self._use_for_more_edits(image_path))
            use_btn.pack(side="left", padx=5)
            
            self.result_images.append((result_frame, image_path))
            
        except Exception as e:
            logger.error(f"Error creating result preview: {e}")
    
    def _save_result(self, image_path: Path):
        save_path = filedialog.asksaveasfilename(
            title="Save Edited Image",
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")],
            initialname=image_path.name
        )
        
        if save_path:
            try:
                import shutil
                shutil.copy2(image_path, save_path)
                messagebox.showinfo("Success", f"Image saved to {save_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save image: {e}")
    
    def _view_result(self, image_path: Path):
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
    
    def _use_for_more_edits(self, image_path: Path):
        """Load this result as the source for more editing"""
        self.current_image_path = image_path
        
        if self.mask_canvas.load_image(image_path):
            pil_image = Image.open(image_path)
            width, height = pil_image.size
            file_size = image_path.stat().st_size / 1024
            
            info_text = f"Loaded: {image_path.name}\n{width}×{height}\n{file_size:.1f} KB"
            self.image_info_label.configure(text=info_text)
            
            messagebox.showinfo("Source Updated", "This edited image is now loaded for further editing")