from typing import Dict, Any, List, Optional
import asyncio
from datetime import datetime

class WorkflowInfo:
    """Manages workflow execution information and status."""
    
    def __init__(self):
        """Initialize workflow information with default values."""
        self.info = {
            "success": False,
            "phases_executed": [],
            "phases_succeeded": [],
            "phases_failed": [],
            "error": None,
            "reasoning_obtained": False,
            "reasoning_method": None,
            "reasoning_content": None,
            "content_obtained": False,
            "content": None,
            "content_method": None,
            "final_answer_obtained": False,
            "final_answer_method": None,
            "start_time": asyncio.get_event_loop().time(),
            "end_time": None,
            "duration": None,
            "retries": {
                "phase1": 0,
                "phase2": 0
            },
            "errors": {}
        }
    
    def get(self) -> Dict[str, Any]:
        """Get the complete workflow information dictionary."""
        return self.info
    
    def get_phase_info(self, phase: str) -> Dict[str, Any]:
        """Get information for a specific phase."""
        return {
            "executed": phase in self.info["phases_executed"],
            "succeeded": phase in self.info["phases_succeeded"],
            "failed": phase in self.info["phases_failed"],
            "error": self.info["errors"].get(phase)
        }
    
    def mark_phase_executed(self, phase: str) -> None:
        """Mark a phase as executed."""
        if phase not in self.info["phases_executed"]:
            self.info["phases_executed"].append(phase)
    
    def mark_phase_succeeded(self, phase: str) -> None:
        """Mark a phase as succeeded."""
        self.mark_phase_executed(phase)
        if phase not in self.info["phases_succeeded"]:
            self.info["phases_succeeded"].append(phase)
        if phase in self.info["phases_failed"]:
            self.info["phases_failed"].remove(phase)
    
    def mark_phase_failed(self, phase: str, error_msg: Optional[str] = None) -> None:
        """Mark a phase as failed with optional error message."""
        self.mark_phase_executed(phase)
        if phase not in self.info["phases_failed"]:
            self.info["phases_failed"].append(phase)
        if phase in self.info["phases_succeeded"]:
            self.info["phases_succeeded"].remove(phase)
        if error_msg:
            self.info["errors"][phase] = error_msg
    
    def update_reasoning(self, content: str, method: str) -> None:
        """Update reasoning content and method."""
        self.info["reasoning_content"] = content
        self.info["reasoning_obtained"] = bool(content.strip())
        self.info["reasoning_method"] = method
    
    def update_content(self, content: str, method: str) -> None:
        """Update content and method."""
        self.info["content"] = content
        self.info["content_obtained"] = bool(content.strip())
        self.info["content_method"] = method
    
    def update_final_answer(self, content: str, method: str) -> None:
        """Update final answer content and method."""
        self.info["final_answer_obtained"] = bool(content.strip())
        self.info["final_answer_method"] = method
    
    def increment_retry(self, phase: str) -> None:
        """Increment retry count for a phase."""
        if phase in self.info["retries"]:
            self.info["retries"][phase] += 1
    
    def get_retry_count(self, phase: str) -> int:
        """Get retry count for a phase."""
        return self.info["retries"].get(phase, 0)
    
    def finalize(self, success: bool, error_msg: Optional[str] = None) -> None:
        """Finalize workflow execution."""
        self.info["end_time"] = asyncio.get_event_loop().time()
        self.info["duration"] = self.info["end_time"] - self.info["start_time"]
        self.info["success"] = success
        if error_msg:
            self.info["error"] = error_msg
    
    def get_reasoning_content(self) -> Optional[str]:
        """Get reasoning content."""
        return self.info.get("reasoning_content")
    
    def set_content(self, content: str) -> None:
        """Set content."""
        self.info["content"] = content
        self.info["content_obtained"] = bool(content.strip())
    
    def set_reasoning_method(self, method: str) -> None:
        """Set reasoning method."""
        self.info["reasoning_method"] = method
    
    def get_content(self) -> Optional[str]:
        """Get content."""
        return self.info.get("content")
    
    def is_phase_succeeded(self, phase: str) -> bool:
        """Check if a phase has succeeded."""
        return phase in self.info["phases_succeeded"]
    
    def is_phase_failed(self, phase: str) -> bool:
        """Check if a phase has failed."""
        return phase in self.info["phases_failed"]
    
    def get_phase_error(self, phase: str) -> Optional[str]:
        """Get error message for a phase."""
        return self.info["errors"].get(phase)
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get a summary of workflow execution."""
        return {
            "success": self.info["success"],
            "duration": self.info["duration"],
            "phases_executed": self.info["phases_executed"],
            "phases_succeeded": self.info["phases_succeeded"],
            "phases_failed": self.info["phases_failed"],
            "reasoning_obtained": self.info["reasoning_obtained"],
            "content_obtained": self.info["content_obtained"],
            "final_answer_obtained": self.info["final_answer_obtained"],
            "errors": self.info["errors"]
        } 