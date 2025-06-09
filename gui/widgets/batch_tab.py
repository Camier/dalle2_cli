import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import asyncio
import threading
import time
import csv
from pathlib import Path
from typing import List, Dict, Any
from PIL import Image
import json
from dataclasses import dataclass

from ...core.dalle_api import DALLEAPIManager, GenerationRequest, ImageDownloader
from ...data.database import DatabaseManager, GenerationRecord
from ...core.config_manager import ConfigManager
from ...utils.logger import logger


@dataclass
class BatchJob:
    id: str
    prompt: str
    size: str = "1024x1024"
    quality: str = "standard"
    style: str = "natural"
    n: int = 1
    status: str = "pending"  # pending, processing, completed, failed
    result_paths: List[str] = None
    error: str = ""
    cost: float = 0.0
    
    def __post_init__(self):
        if self.result_paths is None:
            self.result_paths = []


class BatchProgressFrame(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        # Overall progress
        self.overall_label = ctk.CTkLabel(self, text="Batch Progress: 0/0", 
                                         font=ctk.CTkFont(weight="bold"))
        self.overall_label.pack(pady=(10, 5))
        
        self.overall_progress = ctk.CTkProgressBar(self, width=400)
        self.overall_progress.pack(pady=(0, 10))
        self.overall_progress.set(0)
        
        # Current job
        self.current_label = ctk.CTkLabel(self, text="Status: Ready")
        self.current_label.pack(pady=(0, 5))
        
        # Stats
        stats_frame = ctk.CTkFrame(self)
        stats_frame.pack(fill="x", padx=10, pady=5)
        
        self.completed_label = ctk.CTkLabel(stats_frame, text="Completed: 0")
        self.completed_label.pack(side="left", padx=10)
        
        self.failed_label = ctk.CTkLabel(stats_frame, text="Failed: 0")
        self.failed_label.pack(side="left", padx=10)
        
        self.cost_label = ctk.CTkLabel(stats_frame, text="Total Cost: $0.00")
        self.cost_label.pack(side="right", padx=10)
    
    def update_progress(self, completed: int, total: int, current_job: str = "", 
                       failed: int = 0, total_cost: float = 0.0):
        # Update overall progress
        if total > 0:
            progress = completed / total
            self.overall_progress.set(progress)
            self.overall_label.configure(text=f"Batch Progress: {completed}/{total}")
        
        # Update current job
        self.current_label.configure(text=f"Status: {current_job}")
        
        # Update stats
        self.completed_label.configure(text=f"Completed: {completed}")
        self.failed_label.configure(text=f"Failed: {failed}")
        self.cost_label.configure(text=f"Total Cost: ${total_cost:.4f}")


class BatchJobsList(ctk.CTkScrollableFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.jobs = []
        self.job_frames = {}
        
        # Header
        header_frame = ctk.CTkFrame(self)
        header_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(header_frame, text="Prompt", width=200, 
                    font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header_frame, text="Settings", width=100, 
                    font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header_frame, text="Status", width=100, 
                    font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(header_frame, text="Actions", width=100, 
                    font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
    
    def add_job(self, job: BatchJob):
        self.jobs.append(job)
        
        # Create job frame
        job_frame = ctk.CTkFrame(self)
        job_frame.pack(fill="x", padx=5, pady=2)
        
        # Prompt (truncated)
        prompt_text = job.prompt[:50] + "..." if len(job.prompt) > 50 else job.prompt
        prompt_label = ctk.CTkLabel(job_frame, text=prompt_text, width=200, 
                                   anchor="w", wraplength=190)
        prompt_label.pack(side="left", padx=5, pady=5)
        
        # Settings
        settings_text = f"{job.size}\n{job.quality}, {job.style}\nn={job.n}"
        settings_label = ctk.CTkLabel(job_frame, text=settings_text, width=100, 
                                     anchor="w")
        settings_label.pack(side="left", padx=5, pady=5)
        
        # Status
        status_label = ctk.CTkLabel(job_frame, text=job.status, width=100, 
                                   anchor="w")
        status_label.pack(side="left", padx=5, pady=5)
        
        # Actions
        actions_frame = ctk.CTkFrame(job_frame, fg_color="transparent")
        actions_frame.pack(side="left", padx=5, pady=5)
        
        # Remove button (only if pending)
        if job.status == "pending":
            remove_btn = ctk.CTkButton(actions_frame, text="Remove", width=80,
                                      command=lambda: self.remove_job(job.id))
            remove_btn.pack(pady=2)
        
        # View results button (only if completed)
        if job.status == "completed" and job.result_paths:
            view_btn = ctk.CTkButton(actions_frame, text="View", width=80,
                                    command=lambda: self.view_results(job))
            view_btn.pack(pady=2)
        
        self.job_frames[job.id] = {
            'frame': job_frame,
            'status_label': status_label,
            'actions_frame': actions_frame
        }
    
    def update_job_status(self, job_id: str, status: str):
        for job in self.jobs:
            if job.id == job_id:
                job.status = status
                break
        
        if job_id in self.job_frames:
            self.job_frames[job_id]['status_label'].configure(text=status)
            
            # Update actions based on status
            actions_frame = self.job_frames[job_id]['actions_frame']
            
            # Clear existing buttons
            for widget in actions_frame.winfo_children():
                widget.destroy()
            
            job = next((j for j in self.jobs if j.id == job_id), None)
            if job:
                if status == "pending":
                    remove_btn = ctk.CTkButton(actions_frame, text="Remove", width=80,
                                              command=lambda: self.remove_job(job_id))
                    remove_btn.pack(pady=2)
                elif status == "completed" and job.result_paths:
                    view_btn = ctk.CTkButton(actions_frame, text="View", width=80,
                                            command=lambda: self.view_results(job))
                    view_btn.pack(pady=2)
    
    def remove_job(self, job_id: str):
        # Remove from jobs list
        self.jobs = [job for job in self.jobs if job.id != job_id]
        
        # Remove frame
        if job_id in self.job_frames:
            self.job_frames[job_id]['frame'].destroy()
            del self.job_frames[job_id]
    
    def view_results(self, job: BatchJob):
        # Open folder containing results
        if job.result_paths:
            import subprocess
            import sys
            
            folder_path = Path(job.result_paths[0]).parent
            try:
                if sys.platform == "win32":
                    subprocess.run(["explorer", str(folder_path)])
                elif sys.platform == "darwin":
                    subprocess.run(["open", str(folder_path)])
                else:
                    subprocess.run(["xdg-open", str(folder_path)])
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open folder: {e}")
    
    def clear_all_jobs(self):
        for job_frame_data in self.job_frames.values():
            job_frame_data['frame'].destroy()
        
        self.jobs.clear()
        self.job_frames.clear()
    
    def get_pending_jobs(self) -> List[BatchJob]:
        return [job for job in self.jobs if job.status == "pending"]


class BatchTab(ctk.CTkFrame):
    def __init__(self, parent, api_manager: DALLEAPIManager, db_manager: DatabaseManager, 
                 config_manager: ConfigManager):
        super().__init__(parent)
        
        self.api_manager = api_manager
        self.db_manager = db_manager
        self.config_manager = config_manager
        
        self.batch_running = False
        self.current_batch_task = None
        
        self.create_widgets()
    
    def create_widgets(self):
        # Top section - Add jobs
        top_frame = ctk.CTkFrame(self)
        top_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        # Left - Manual entry
        left_panel = ctk.CTkFrame(top_frame)
        left_panel.pack(side="left", fill="y", padx=(10, 5), pady=10)
        
        # Right - File import
        right_panel = ctk.CTkFrame(top_frame)
        right_panel.pack(side="right", fill="y", padx=(5, 10), pady=10)
        
        self.create_manual_entry(left_panel)
        self.create_file_import(right_panel)
        
        # Middle section - Progress
        self.progress_frame = BatchProgressFrame(self, height=150)
        self.progress_frame.pack(fill="x", padx=10, pady=5)
        
        # Bottom section - Jobs list
        jobs_frame = ctk.CTkFrame(self)
        jobs_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        
        jobs_label = ctk.CTkLabel(jobs_frame, text="Batch Jobs", 
                                 font=ctk.CTkFont(size=16, weight="bold"))
        jobs_label.pack(pady=(10, 5))
        
        # Control buttons
        controls_frame = ctk.CTkFrame(jobs_frame)
        controls_frame.pack(fill="x", padx=10, pady=5)
        
        self.start_btn = ctk.CTkButton(controls_frame, text="Start Batch", 
                                      command=self.start_batch, height=35,
                                      font=ctk.CTkFont(weight="bold"))
        self.start_btn.pack(side="left", padx=5)
        
        self.stop_btn = ctk.CTkButton(controls_frame, text="Stop Batch", 
                                     command=self.stop_batch, height=35,
                                     state="disabled")
        self.stop_btn.pack(side="left", padx=5)
        
        clear_btn = ctk.CTkButton(controls_frame, text="Clear All", 
                                 command=self.clear_all_jobs, height=35)
        clear_btn.pack(side="left", padx=5)
        
        export_btn = ctk.CTkButton(controls_frame, text="Export Results", 
                                  command=self.export_results, height=35)
        export_btn.pack(side="right", padx=5)
        
        # Jobs list
        self.jobs_list = BatchJobsList(jobs_frame, width=800, height=300)
        self.jobs_list.pack(fill="both", expand=True, padx=10, pady=10)
    
    def create_manual_entry(self, parent):
        title = ctk.CTkLabel(parent, text="Add Single Job", 
                           font=ctk.CTkFont(size=14, weight="bold"))
        title.pack(pady=(10, 5))
        
        # Prompt entry
        prompt_label = ctk.CTkLabel(parent, text="Prompt:")
        prompt_label.pack(anchor="w", padx=10, pady=(5, 0))
        
        self.prompt_entry = ctk.CTkTextbox(parent, width=300, height=60)
        self.prompt_entry.pack(padx=10, pady=5)
        
        # Settings
        settings_frame = ctk.CTkFrame(parent)
        settings_frame.pack(fill="x", padx=10, pady=5)
        
        # Size
        ctk.CTkLabel(settings_frame, text="Size:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.size_var = ctk.StringVar(value="1024x1024")
        size_combo = ctk.CTkComboBox(settings_frame, variable=self.size_var,
                                    values=["1024x1024", "1024x1792", "1792x1024"],
                                    width=120)
        size_combo.grid(row=0, column=1, padx=5, pady=2)
        
        # Quality
        ctk.CTkLabel(settings_frame, text="Quality:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.quality_var = ctk.StringVar(value="standard")
        quality_combo = ctk.CTkComboBox(settings_frame, variable=self.quality_var,
                                       values=["standard", "hd"], width=120)
        quality_combo.grid(row=1, column=1, padx=5, pady=2)
        
        # Style
        ctk.CTkLabel(settings_frame, text="Style:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.style_var = ctk.StringVar(value="natural")
        style_combo = ctk.CTkComboBox(settings_frame, variable=self.style_var,
                                     values=["natural", "vivid"], width=120)
        style_combo.grid(row=2, column=1, padx=5, pady=2)
        
        # Number
        ctk.CTkLabel(settings_frame, text="Images:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        self.n_var = ctk.StringVar(value="1")
        n_combo = ctk.CTkComboBox(settings_frame, variable=self.n_var,
                                 values=["1", "2", "3", "4"], width=120)
        n_combo.grid(row=3, column=1, padx=5, pady=2)
        
        # Add button
        add_btn = ctk.CTkButton(parent, text="Add to Batch", 
                               command=self.add_manual_job, width=280)
        add_btn.pack(padx=10, pady=10)
    
    def create_file_import(self, parent):
        title = ctk.CTkLabel(parent, text="Import from File", 
                           font=ctk.CTkFont(size=14, weight="bold"))
        title.pack(pady=(10, 5))
        
        # Instructions
        instructions = ctk.CTkLabel(parent, 
                                   text="Import prompts from CSV file.\nFormat: prompt,size,quality,style,n",
                                   justify="left")
        instructions.pack(padx=10, pady=5)
        
        # File selection
        self.file_path_var = ctk.StringVar()
        file_frame = ctk.CTkFrame(parent)
        file_frame.pack(fill="x", padx=10, pady=5)
        
        file_entry = ctk.CTkEntry(file_frame, textvariable=self.file_path_var, 
                                 width=200, placeholder_text="Select CSV file...")
        file_entry.pack(side="left", padx=5, pady=5)
        
        browse_btn = ctk.CTkButton(file_frame, text="Browse", 
                                  command=self.browse_csv_file, width=80)
        browse_btn.pack(side="right", padx=5, pady=5)
        
        # Import button
        import_btn = ctk.CTkButton(parent, text="Import Jobs", 
                                  command=self.import_from_csv, width=280)
        import_btn.pack(padx=10, pady=10)
        
        # Sample CSV button
        sample_btn = ctk.CTkButton(parent, text="Create Sample CSV", 
                                  command=self.create_sample_csv, width=280)
        sample_btn.pack(padx=10, pady=(0, 10))
    
    def add_manual_job(self):
        prompt = self.prompt_entry.get("1.0", "end-1c").strip()
        if not prompt:
            messagebox.showerror("Error", "Please enter a prompt")
            return
        
        job = BatchJob(
            id=str(int(time.time() * 1000)),  # Unique ID
            prompt=prompt,
            size=self.size_var.get(),
            quality=self.quality_var.get(),
            style=self.style_var.get(),
            n=int(self.n_var.get())
        )
        
        self.jobs_list.add_job(job)
        self.prompt_entry.delete("1.0", "end")
        
        messagebox.showinfo("Success", "Job added to batch")
    
    def browse_csv_file(self):
        file_path = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if file_path:
            self.file_path_var.set(file_path)
    
    def import_from_csv(self):
        csv_path = self.file_path_var.get()
        if not csv_path or not Path(csv_path).exists():
            messagebox.showerror("Error", "Please select a valid CSV file")
            return
        
        try:
            jobs_added = 0
            with open(csv_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                for row in reader:
                    prompt = row.get('prompt', '').strip()
                    if not prompt:
                        continue
                    
                    job = BatchJob(
                        id=str(int(time.time() * 1000) + jobs_added),
                        prompt=prompt,
                        size=row.get('size', '1024x1024'),
                        quality=row.get('quality', 'standard'),
                        style=row.get('style', 'natural'),
                        n=int(row.get('n', 1))
                    )
                    
                    self.jobs_list.add_job(job)
                    jobs_added += 1
            
            messagebox.showinfo("Success", f"Imported {jobs_added} jobs from CSV")
            self.file_path_var.set("")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import CSV: {e}")
    
    def create_sample_csv(self):
        save_path = filedialog.asksaveasfilename(
            title="Save Sample CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialname="batch_prompts_sample.csv"
        )
        
        if save_path:
            try:
                sample_data = [
                    ["prompt", "size", "quality", "style", "n"],
                    ["A beautiful sunset over mountains", "1024x1024", "standard", "natural", "1"],
                    ["A cute cat wearing a hat", "1024x1024", "hd", "vivid", "2"],
                    ["Abstract geometric art", "1792x1024", "standard", "natural", "1"],
                    ["A futuristic city skyline", "1024x1792", "hd", "vivid", "1"]
                ]
                
                with open(save_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerows(sample_data)
                
                messagebox.showinfo("Success", f"Sample CSV created at {save_path}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create sample CSV: {e}")
    
    def start_batch(self):
        pending_jobs = self.jobs_list.get_pending_jobs()
        if not pending_jobs:
            messagebox.showerror("Error", "No pending jobs to process")
            return
        
        # Confirm start
        total_cost_estimate = sum(self._estimate_job_cost(job) for job in pending_jobs)
        message = f"Start batch processing {len(pending_jobs)} jobs?\nEstimated cost: ${total_cost_estimate:.4f}"
        
        if not messagebox.askyesno("Confirm Batch", message):
            return
        
        # Start batch processing
        self.batch_running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        
        # Start processing in thread
        self.current_batch_task = threading.Thread(
            target=self._process_batch_thread, 
            args=(pending_jobs.copy(),), 
            daemon=True
        )
        self.current_batch_task.start()
    
    def stop_batch(self):
        self.batch_running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        
        self.progress_frame.update_progress(0, 0, "Batch stopped")
    
    def clear_all_jobs(self):
        if messagebox.askyesno("Clear All", "Remove all jobs from the batch?"):
            self.jobs_list.clear_all_jobs()
    
    def _estimate_job_cost(self, job: BatchJob) -> float:
        base_costs = {
            "1024x1024": {"standard": 0.04, "hd": 0.08},
            "1024x1792": {"standard": 0.08, "hd": 0.12},
            "1792x1024": {"standard": 0.08, "hd": 0.12}
        }
        cost_per_image = base_costs.get(job.size, {}).get(job.quality, 0.04)
        return cost_per_image * job.n
    
    def _process_batch_thread(self, jobs: List[BatchJob]):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._process_batch_async(jobs))
            loop.close()
        except Exception as e:
            logger.error(f"Batch processing thread error: {e}")
        finally:
            self.after(0, lambda: self._batch_finished())
    
    async def _process_batch_async(self, jobs: List[BatchJob]):
        completed = 0
        failed = 0
        total_cost = 0.0
        
        for i, job in enumerate(jobs):
            if not self.batch_running:
                break
            
            try:
                # Update UI
                self.after(0, lambda j=job: self.jobs_list.update_job_status(j.id, "processing"))
                self.after(0, lambda: self.progress_frame.update_progress(
                    completed, len(jobs), f"Processing: {job.prompt[:30]}...", 
                    failed, total_cost
                ))
                
                # Create generation request
                request = GenerationRequest(
                    prompt=job.prompt,
                    size=job.size,
                    quality=job.quality,
                    style=job.style,
                    n=job.n
                )
                
                # Generate images
                result = await self.api_manager.generate_image_async(request)
                
                if result.success:
                    # Download images
                    output_dir = self.config_manager.get_output_directory() / "batch" / f"job_{job.id}"
                    output_dir.mkdir(parents=True, exist_ok=True)
                    
                    async with ImageDownloader(output_dir) as downloader:
                        image_paths = await downloader.download_multiple(
                            result.image_urls, 
                            f"image"
                        )
                    
                    if image_paths:
                        # Update job
                        job.result_paths = [str(p) for p in image_paths]
                        job.cost = result.cost
                        job.status = "completed"
                        
                        # Save to database
                        for image_path in image_paths:
                            record = GenerationRecord(
                                prompt=job.prompt,
                                image_path=str(image_path),
                                cost=result.cost / len(image_paths),
                                size=job.size,
                                generation_type="batch",
                                metadata=json.dumps({
                                    "batch_job_id": job.id,
                                    "quality": job.quality,
                                    "style": job.style
                                })
                            )
                            self.db_manager.add_generation(record)
                        
                        completed += 1
                        total_cost += result.cost
                        
                        self.after(0, lambda: self.jobs_list.update_job_status(job.id, "completed"))
                    else:
                        job.status = "failed"
                        job.error = "Failed to download images"
                        failed += 1
                        self.after(0, lambda: self.jobs_list.update_job_status(job.id, "failed"))
                else:
                    job.status = "failed"
                    job.error = result.error
                    failed += 1
                    self.after(0, lambda: self.jobs_list.update_job_status(job.id, "failed"))
                
                # Update progress
                self.after(0, lambda: self.progress_frame.update_progress(
                    completed, len(jobs), f"Completed job {completed + failed}/{len(jobs)}", 
                    failed, total_cost
                ))
                
                # Delay between jobs
                if self.batch_running and i < len(jobs) - 1:
                    await asyncio.sleep(self.config_manager.config.batch_delay_seconds)
                
            except Exception as e:
                logger.error(f"Error processing batch job {job.id}: {e}")
                job.status = "failed"
                job.error = str(e)
                failed += 1
                self.after(0, lambda: self.jobs_list.update_job_status(job.id, "failed"))
        
        # Final update
        status = "Batch completed" if self.batch_running else "Batch stopped"
        self.after(0, lambda: self.progress_frame.update_progress(
            completed, len(jobs), status, failed, total_cost
        ))
    
    def _batch_finished(self):
        self.batch_running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
    
    def export_results(self):
        completed_jobs = [job for job in self.jobs_list.jobs if job.status == "completed"]
        
        if not completed_jobs:
            messagebox.showinfo("No Results", "No completed jobs to export")
            return
        
        save_path = filedialog.asksaveasfilename(
            title="Export Results",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialname="batch_results.csv"
        )
        
        if save_path:
            try:
                with open(save_path, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['job_id', 'prompt', 'size', 'quality', 'style', 'n', 
                                 'cost', 'image_count', 'image_paths']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for job in completed_jobs:
                        writer.writerow({
                            'job_id': job.id,
                            'prompt': job.prompt,
                            'size': job.size,
                            'quality': job.quality,
                            'style': job.style,
                            'n': job.n,
                            'cost': job.cost,
                            'image_count': len(job.result_paths),
                            'image_paths': ';'.join(job.result_paths)
                        })
                
                messagebox.showinfo("Success", f"Results exported to {save_path}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export results: {e}")