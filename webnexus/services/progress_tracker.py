"""
Progress Tracker

Simple progress tracking system for WebNexus crawling operations.
Uses logging instead of SocketIO for simplified architecture.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class ProgressStatus(Enum):
    """Progress status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProgressTracker:
    """
    Simple progress tracker that logs progress and maintains state.
    
    This replaces the original project's SocketIO-based progress tracking
    with a simpler logging-based approach suitable for WebNexus.
    """
    
    def __init__(self):
        """Initialize progress tracker."""
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self.callbacks: Dict[str, Callable] = {}
    
    def start_task(
        self, 
        task_id: str, 
        task_type: str,
        description: str,
        total_items: int = 0,
        callback: Optional[Callable] = None
    ) -> None:
        """
        Start tracking a new task.
        
        Args:
            task_id: Unique task identifier
            task_type: Type of task (crawl, process, etc.)
            description: Human-readable description
            total_items: Total number of items to process
            callback: Optional callback function for progress updates
        """
        self.active_tasks[task_id] = {
            "task_id": task_id,
            "task_type": task_type,
            "description": description,
            "status": ProgressStatus.RUNNING.value,
            "current_item": 0,
            "total_items": total_items,
            "progress_percent": 0,
            "started_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "error_message": None,
            "metadata": {}
        }
        
        if callback:
            self.callbacks[task_id] = callback
        
        logger.info(f"Started task {task_id} ({task_type}): {description}")
        self._notify_progress(task_id)
    
    def update_progress(
        self, 
        task_id: str, 
        current_item: Optional[int] = None,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Update progress for a task.
        
        Args:
            task_id: Task identifier
            current_item: Current item number being processed
            message: Progress message
            metadata: Additional metadata
        """
        if task_id not in self.active_tasks:
            logger.warning(f"Task {task_id} not found for progress update")
            return
        
        task = self.active_tasks[task_id]
        
        if current_item is not None:
            task["current_item"] = current_item
            
            # Calculate percentage
            if task["total_items"] > 0:
                task["progress_percent"] = min(100, (current_item / task["total_items"]) * 100)
            else:
                # For tasks without known total, use current_item as percentage
                task["progress_percent"] = min(100, current_item)
        
        if message:
            task["current_message"] = message
        
        if metadata:
            task["metadata"].update(metadata)
        
        task["updated_at"] = datetime.utcnow().isoformat()
        
        logger.info(
            f"Progress {task_id}: {task['progress_percent']:.1f}% "
            f"({task['current_item']}/{task['total_items']}) - {message or task['description']}"
        )
        
        self._notify_progress(task_id)
    
    def complete_task(
        self, 
        task_id: str, 
        message: str = "Task completed",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Mark a task as completed.
        
        Args:
            task_id: Task identifier
            message: Completion message
            metadata: Final metadata
        """
        if task_id not in self.active_tasks:
            logger.warning(f"Task {task_id} not found for completion")
            return
        
        task = self.active_tasks[task_id]
        task["status"] = ProgressStatus.COMPLETED.value
        task["progress_percent"] = 100
        task["current_message"] = message
        task["completed_at"] = datetime.utcnow().isoformat()
        
        if metadata:
            task["metadata"].update(metadata)
        
        logger.info(f"Completed task {task_id}: {message}")
        self._notify_progress(task_id)
        
        # Clean up callback
        if task_id in self.callbacks:
            del self.callbacks[task_id]
    
    def fail_task(
        self, 
        task_id: str, 
        error_message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Mark a task as failed.
        
        Args:
            task_id: Task identifier
            error_message: Error description
            metadata: Additional metadata
        """
        if task_id not in self.active_tasks:
            logger.warning(f"Task {task_id} not found for failure")
            return
        
        task = self.active_tasks[task_id]
        task["status"] = ProgressStatus.FAILED.value
        task["error_message"] = error_message
        task["failed_at"] = datetime.utcnow().isoformat()
        
        if metadata:
            task["metadata"].update(metadata)
        
        logger.error(f"Failed task {task_id}: {error_message}")
        self._notify_progress(task_id)
        
        # Clean up callback
        if task_id in self.callbacks:
            del self.callbacks[task_id]
    
    def cancel_task(self, task_id: str, message: str = "Task cancelled") -> None:
        """
        Cancel a running task.
        
        Args:
            task_id: Task identifier
            message: Cancellation message
        """
        if task_id not in self.active_tasks:
            logger.warning(f"Task {task_id} not found for cancellation")
            return
        
        task = self.active_tasks[task_id]
        task["status"] = ProgressStatus.CANCELLED.value
        task["current_message"] = message
        task["cancelled_at"] = datetime.utcnow().isoformat()
        
        logger.info(f"Cancelled task {task_id}: {message}")
        self._notify_progress(task_id)
        
        # Clean up callback
        if task_id in self.callbacks:
            del self.callbacks[task_id]
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status of a task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task status dictionary or None if not found
        """
        return self.active_tasks.get(task_id)
    
    def get_active_tasks(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all active tasks.
        
        Returns:
            Dictionary of active tasks
        """
        # Filter to only running tasks
        active = {
            task_id: task 
            for task_id, task in self.active_tasks.items()
            if task["status"] == ProgressStatus.RUNNING.value
        }
        return active
    
    def cleanup_completed_tasks(self, max_age_hours: int = 24) -> None:
        """
        Clean up old completed/failed/cancelled tasks.
        
        Args:
            max_age_hours: Maximum age in hours for completed tasks
        """
        from datetime import datetime, timedelta
        
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        to_remove = []
        for task_id, task in self.active_tasks.items():
            if task["status"] in [ProgressStatus.COMPLETED.value, ProgressStatus.FAILED.value, ProgressStatus.CANCELLED.value]:
                try:
                    completed_at = datetime.fromisoformat(task.get("completed_at", task.get("failed_at", task.get("cancelled_at", ""))))
                    if completed_at < cutoff_time:
                        to_remove.append(task_id)
                except:
                    # If we can't parse the date, remove it
                    to_remove.append(task_id)
        
        for task_id in to_remove:
            del self.active_tasks[task_id]
            if task_id in self.callbacks:
                del self.callbacks[task_id]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old tasks")
    
    def _notify_progress(self, task_id: str) -> None:
        """
        Notify progress callback if available.
        
        Args:
            task_id: Task identifier
        """
        if task_id in self.callbacks:
            try:
                callback = self.callbacks[task_id]
                task = self.active_tasks[task_id]
                
                # Call the callback with task information
                if callback:
                    # For async callbacks, we can't await here, so we just call it
                    # The callback should handle async operations internally
                    callback(
                        task.get("current_message", task["description"]),
                        task["progress_percent"],
                        task.get("metadata", {})
                    )
                    
            except Exception as e:
                logger.warning(f"Error calling progress callback for {task_id}: {e}")


# Global progress tracker instance
progress_tracker = ProgressTracker()