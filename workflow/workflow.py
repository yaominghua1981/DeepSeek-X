import asyncio
from typing import Dict, List, Optional, Union, Callable, Any, AsyncGenerator, Tuple, TYPE_CHECKING, Type
import traceback
import json

# Conditional import to avoid circular dependencies
if TYPE_CHECKING:
    from clients.deepseek_client import DeepSeekClient
    from clients.openai_compatible_client import OpenAICompatibleClient
    from logging import Logger
    from config.config_manager import ConfigManager

from utils.logger import get_logger
from .workflow_info import WorkflowInfo

class DeepSeekXWorkflow:
    """
    DeepSeek-X Workflow Manager
    
    Responsible for coordinating the complete process between DeepSeek reasoning 
    and OpenAI-compatible model responses
    """
    
    def __init__(self, 
                deepseek_client: 'DeepSeekClient', 
                openai_compatible_client: 'OpenAICompatibleClient',
                config_manager: 'ConfigManager',
                logger: Optional['Logger'] = None):
        """
        Initialize workflow manager
        
        Args:
            deepseek_client: DeepSeek client instance
            openai_compatible_client: OpenAI compatible client instance
            config_manager: Configuration manager instance
            logger: Logger instance
        """
        self.deepseek_client = deepseek_client
        self.openai_compatible_client = openai_compatible_client
        self.config_manager = config_manager
        self.logger = get_logger(self.__class__.__name__)
        # Execution history
        self.execution_history = []
    
    def set_callback(self, callback_name: str, callback_func: Callable) -> None:
        """
        Set callback function
        
        Args:
            callback_name: Callback function name
            callback_func: Callback function
        """
        self.config_manager.set_callback(callback_name, callback_func)
    
    async def process(
        self,
        user_message: str,
        system_message: str = "",
        assistant_message: str = ""
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process the chat request through the configured workflow
        
        Args:
            user_message: User's question or request
            system_message: System message that guides the model
            assistant_message: Optional assistant message for context
            
        Yields:
            Dict[str, Any]: Events from the workflow process
        """
        workflow_info = WorkflowInfo()
        try:
            # Get workflow configuration from config_manager
            workflow_config = self.config_manager.get_workflow_config()
            
            # Get Phase1 and Phase2 configurations
            phase1_config = workflow_config.get("phase1_inference", {})
            phase2_config = workflow_config.get("phase2_final", {})
            
            # Get step configurations for each phase
            phase1_steps = phase1_config.get("step", [])
            phase2_steps = phase2_config.get("step", [])
            
            # Only require phase2_steps to be present
            if not phase2_steps:
                self.logger.error("Invalid workflow configuration: missing phase2 step configurations")
                raise ValueError("Invalid workflow configuration: missing phase2 step configurations")
            
            # Get first step settings for each phase
            phase2_settings = phase2_steps[0]
            
            # Process Phase1 (DeepSeek Inference) only if steps exist
            if phase1_steps:
                phase1_settings = phase1_steps[0]
                # Process Phase1 (DeepSeek Inference)
                if phase1_settings.get("stream", False):
                    self.logger.info("Phase1: Using streaming mode")
                    async for event in self._process_phase1_stream(user_message, system_message, assistant_message, workflow_info):
                        yield event
                else:
                    self.logger.info("Phase1: Using non-streaming mode")
                    async for event in self._process_phase1_nonstream(user_message, system_message, assistant_message, workflow_info):
                        yield event
            else:
                self.logger.info("Phase1 steps not configured, skipping to Phase2")
            
            # Always proceed to Phase2
            self.logger.info("Proceeding to Phase2")
            if phase2_settings.get("stream", False):
                self.logger.info("Phase2: Using streaming mode")
                async for event in self._process_phase2_stream(user_message, system_message, assistant_message, workflow_info):
                    yield event
            else:
                self.logger.info("Phase2: Using non-streaming mode")
                result = await self._process_phase2_nonstream(user_message, system_message, assistant_message, workflow_info)
                # Record phase2 execution for non-streaming mode
                workflow_info.mark_phase_executed("phase2_nonstream")
                if "type" not in result or result["type"] != "error":
                    workflow_info.mark_phase_succeeded("phase2_nonstream")
                    yield result
                else:
                    workflow_info.mark_phase_failed("phase2_nonstream", result.get("content", "Unknown error"))
                    yield result
                    
            # Finalize workflow
            await self._finalize_workflow(workflow_info, workflow_info.get()["success"], "")
            
        except Exception as e:
            self.logger.error(f"Workflow processing failed: {str(e)}")
            self.logger.error(traceback.format_exc())
            workflow_info.mark_phase_failed("workflow", str(e))
            yield {
                "type": "error",
                "content": f"Workflow processing failed: {str(e)}"
            }
    
    async def _finalize_workflow(self, workflow_info: WorkflowInfo, success: bool, message: str) -> None:
        """
        Complete workflow, record results
        
        Args:
            workflow_info: Workflow information
            success: Whether successful
            message: Completion message
        """
        workflow_info.finalize(success, message)
        
        # Execute workflow completion callback
        await self._execute_callback(
            "on_workflow_complete",
            success,
            message or ("Workflow successful" if success else "Workflow failed"),
            workflow_info.get()
        )
        
        # Log workflow execution results
        self._log_workflow_results(workflow_info)
    
    def _record_workflow_history(self, prompt: str, workflow_info: WorkflowInfo, result: str) -> None:
        """
        Record workflow history
        
        Args:
            prompt: Prompt text
            workflow_info: Workflow information
            result: Result description
        """
        self.execution_history.append({
            "prompt": prompt,
            "workflow_info": workflow_info.get(),
            "result": result,
            "timestamp": asyncio.get_event_loop().time()
        })
    
    def _log_workflow_results(self, workflow_info: WorkflowInfo) -> None:
        """
        Record workflow execution results to log
        
        Args:
            workflow_info: Workflow information
        """
        summary = workflow_info.get_execution_summary()
        self.logger.info("\nWorkflow execution information:")
        self.logger.info(f"Success: {summary['success']}")
        self.logger.info(f"Executed phases: {summary['phases_executed']}")
        self.logger.info(f"Successful phases: {summary['phases_succeeded']}")
        self.logger.info(f"Failed phases: {summary['phases_failed']}")
        self.logger.info(f"Reasoning obtained: {'Yes' if summary['reasoning_obtained'] else 'No'}")
        if summary['reasoning_obtained']:
            self.logger.info(f"Reasoning method: {workflow_info.get()['reasoning_method']}")
        self.logger.info(f"Final answer obtained: {'Yes' if summary['final_answer_obtained'] else 'No'}")
        if summary['final_answer_obtained']:
            self.logger.info(f"Final answer method: {workflow_info.get()['final_answer_method']}")
    
        if not summary['success']:
            self.logger.info(f"\nWorkflow failed: {workflow_info.get()['error']}")
            if summary['errors']:
                for phase, error in summary['errors'].items():
                    self.logger.info(f"Phase {phase} error: {error}")
    
    async def _process_phase1_stream(
        self,
        user_message: str,
        system_message: str,
        assistant_message: str,
        workflow_info: WorkflowInfo
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process first phase streaming request
        
        Args:
            user_message: User's question or request
            system_message: System message that guides the model to provide reasoning
            assistant_message: Optional assistant message for context
            workflow_info: Workflow information dictionary
            
        Yields:
            Dict[str, Any]: Streaming response event
        """
        retry_count = 0
        reasoning_content = ""
        content = ""
        reasoning_started = False
        phase1_completed = False
        
        while retry_count <= 0:
            try:
                # Reasoning content collection phase
                self.logger.info("Starting streaming reasoning")
                
                # Create streaming request
                async for chunk in self.deepseek_client.stream_chat(
                    user_message=user_message,
                    system_message=system_message
                ):
                    try:
                        # Check if chunk is string type
                        if isinstance(chunk, str):
                            # Check if content is empty or too short
                            if not chunk.strip():
                                self.logger.warning("Received empty string chunk, skipping")
                                continue
                                
                            if len(chunk.strip()) < 5:
                                self.logger.warning(f"Received very short string chunk: '{chunk}', length: {len(chunk.strip())}")
                            
                            # Update content and immediately yield
                            content += chunk
                            yield {
                                "type": "content",
                                "content": chunk
                            }
                            continue
                        
                        # Process dictionary type chunk
                        result_type = chunk.get("type", "")
                        chunk_content = chunk.get("content", "")
                        
                        if result_type == "reasoning":
                            # Update reasoning content and immediately yield
                            reasoning_content += chunk_content
                            reasoning_started = True
                            
                            # Add debug logging
                            self.logger.debug(f"Accumulated reasoning content length: {len(reasoning_content)}")
                            
                            # Send reasoning chunk immediately
                            yield {
                                "type": "reasoning",
                                "content": chunk_content
                            }
                        
                        elif result_type == "phase1_complete":
                            # Get the accumulated content from the event
                            event_reasoning = chunk.get("reasoning_content", "")
                            event_content = chunk.get("content", "")
                            
                            # Update our accumulated content with event content if available
                            if event_reasoning:
                                reasoning_content = event_reasoning
                            if event_content:
                                content = event_content
                            
                            # If we have reasoning_content, use it; otherwise use content
                            final_reasoning = reasoning_content if reasoning_content.strip() else content
                            workflow_info.update_reasoning(final_reasoning, "stream")
                            workflow_info.set_content(content)
                            workflow_info.set_reasoning_method("stream")
                            
                            # Record phase1 execution
                            workflow_info.mark_phase_executed("phase1_stream")
                            workflow_info.mark_phase_succeeded("phase1_stream")
                            
                            # Log the content we're passing to phase2
                            self.logger.info(f"Passing to phase2 - reasoning_content length: {len(final_reasoning)}, content length: {len(content)}")
                            
                            # First, ensure all content is sent to the user interface
                            if reasoning_content and not reasoning_started:
                                # If we have reasoning content but haven't sent it yet
                                yield {
                                    "type": "reasoning",
                                    "content": reasoning_content
                                }
                                reasoning_started = True
                            
                            if content and not reasoning_content:
                                # If we have content but no reasoning, send it as content
                                yield {
                                    "type": "content",
                                    "content": content
                                }
                            
                            # Then send phase1_complete event
                            yield {
                                "type": "phase1_complete",
                                "reasoning_content": final_reasoning,
                                "content": content
                            }
                            
                            self.logger.info("Received phase1 complete event with accumulated content")
                            phase1_completed = True
                            break  # Exit the chunk processing loop after phase1_complete
                        
                        elif result_type == "reasoning_end":
                            # End reasoning phase
                            if reasoning_started:
                                # Add debug logging before ending
                                self.logger.debug(f"Reasoning phase ended, total content length: {len(reasoning_content)}")
                                yield {
                                    "type": "reasoning_end",
                                    "content": ""
                                }
                            break
                        
                        elif result_type == "error":
                            error_content = chunk.get("content", "")
                            error_phase = chunk.get("phase", "unknown")
                            
                            # Only switch to non-streaming if it's a critical error
                            if error_phase.startswith("phase1") and "critical" in error_content.lower():
                                self.logger.warning(f"Critical streaming error, switching to non-streaming: {error_content}")
                                break
                            else:
                                # For non-critical errors, continue processing
                                self.logger.warning(f"Non-critical error in streaming: {error_content}")
                                continue
                        
                    except Exception as e:
                        self.logger.error(f"Error processing stream chunk: {str(e)}")
                        self.logger.error(traceback.format_exc())
                        # Don't break on processing errors, continue with next chunk
                        continue
                
                # If phase1 completed successfully, break the retry loop
                if phase1_completed:
                    break
                
                # If we get here without phase1_complete, increment retry count
                retry_count += 1
                if retry_count <= 0:
                    self.logger.warning(f"Streaming reasoning failed to complete, retry #{retry_count}...")
                    yield {
                        "type": "error",
                        "content": f"Streaming reasoning failed to complete, retry #{retry_count}...",
                        "phase": "phase1"
                    }
                else:
                    error_msg = "Streaming reasoning failed to complete after retries"
                    self.logger.error(error_msg)
                    yield {
                        "type": "error",
                        "content": error_msg,
                        "phase": "phase1"
                    }
                
            except asyncio.TimeoutError as e:
                retry_count += 1
                if retry_count <= 0:
                    self.logger.warning(f"Streaming reasoning timeout, retry #{retry_count}...")
                    yield {
                        "type": "error",
                        "content": f"Streaming reasoning timeout, retrying...",
                        "phase": "phase1"
                    }
                else:
                    error_msg = f"Streaming reasoning still timed out after {retry_count} retries: {str(e)}"
                    self.logger.error(error_msg)
                    yield {
                        "type": "error",
                        "content": error_msg,
                        "phase": "phase1"
                    }
                    break
                    
            except Exception as e:
                self.logger.error(f"Streaming reasoning error: {str(e)}")
                self.logger.error(traceback.format_exc())
                
                # Check if it's a connection error
                if "Connection error" in str(e) or "Server disconnected" in str(e):
                    retry_count += 1
                    if retry_count <= 0:
                        retry_delay = min(5 * retry_count, 30)  # Gradually increase retry delay, max 30 seconds
                        self.logger.info(f"Connection error detected, waiting {retry_delay} seconds before retrying...")
                        yield {
                            "type": "error",
                            "content": f"Connection error, retrying in {retry_delay} seconds...",
                            "phase": "phase1"
                        }
                    else:
                        yield {
                            "type": "error",
                            "content": "Connection error after retries",
                            "phase": "phase1"
                        }
                else:
                    yield {
                        "type": "error",
                        "content": f"Streaming reasoning error: {str(e)}",
                        "phase": "phase1"
                    }
                    break
    
    async def _process_phase1_nonstream(
        self,
        user_message: str,
        system_message: str,
        assistant_message: str,
        workflow_info: WorkflowInfo
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process first phase non-streaming request
        
        Args:
            user_message: User's question or request
            system_message: System message that guides the model to provide reasoning
            assistant_message: Optional assistant message for context
            workflow_info: Workflow information dictionary
            
        Yields:
            Dict[str, Any]: Response containing reasoning content and regular content
        """
        retry_count = 0
        
        while retry_count <= 0:
            try:
                self.logger.info(f"Starting attempt #{0+1} to obtain reasoning content")
                
                # Record detailed information of request parameters
                prompt_sample = user_message[:100] + ("..." if len(user_message) > 100 else "")
                self.logger.info(f"Request parameters - prompt (sample): {prompt_sample}")
                self.logger.info(f"Request parameters - prompt (length): {len(user_message)} characters")
                
                # Create non-streaming request
                self.logger.info("Calling DeepSeek client for non-streaming response...")
                result = await self.deepseek_client.nonstream_chat(
                    user_message=user_message,
                    system_message=system_message
                )
                
                # Process response
                self.logger.info("Processing non-streaming response...")
                
                # Check if content is successfully obtained
                if result.get("reasoning") or result.get("content"):
                    self.logger.info(f"Successfully obtained content, reasoning length: {len(result.get('reasoning', ''))}, content length: {len(result.get('content', ''))}")
                    
                    # Update workflow info
                    if result.get("reasoning"):
                        workflow_info.update_reasoning(result["reasoning"], "nonstream")
                        workflow_info.set_reasoning_method("nonstream")
                        # Yield reasoning content first
                        yield {
                            "type": "reasoning",
                            "content": result["reasoning"]
                        }
                    elif result.get("content"):
                        # If no reasoning but has content, use content as reasoning
                        workflow_info.update_reasoning(result["content"], "nonstream")
                        workflow_info.set_reasoning_method("nonstream")
                        # Yield content as reasoning
                        yield {
                            "type": "reasoning",
                            "content": result["content"]
                        }
                    
                    if result.get("content"):
                        workflow_info.set_content(result["content"])
                        # Yield content after reasoning
                        yield {
                            "type": "content",
                            "content": result["content"]
                        }
                    
                    # Record phase1 execution
                    workflow_info.mark_phase_executed("phase1_nonstream")
                    workflow_info.mark_phase_succeeded("phase1_nonstream")
                    
                    return
                else:
                    retry_count += 1
                    
                    if retry_count <= 0:
                        self.logger.warning(f"Non-streaming reasoning returned empty content, attempt #{retry_count}...")
                        yield {
                            "type": "error",
                            "content": f"Non-streaming reasoning returned empty content, attempt #{retry_count}..."
                        }
                    else:
                        error_msg = "Non-streaming reasoning repeatedly returned empty content"
                        self.logger.error(error_msg)
                        yield {
                            "type": "error",
                            "content": error_msg
                        }
                        
            except asyncio.TimeoutError as e:
                self.logger.error(f"Non-streaming reasoning timeout: {str(e)}")
                retry_count += 1
                if retry_count <= 0:
                    self.logger.warning(f"Non-streaming reasoning timeout, attempt #{retry_count}...")
                    yield {
                        "type": "error",
                        "content": f"Non-streaming reasoning timeout, attempt #{retry_count}..."
                    }
                else:
                    error_msg = f"Non-streaming reasoning timed out after {retry_count} attempts: {str(e)}"
                    self.logger.error(error_msg)
                    yield {
                        "type": "error",
                        "content": error_msg
                    }
            
            except Exception as e:
                self.logger.error(f"Non-streaming reasoning failed: {str(e)}")
                self.logger.error(f"Error details: {traceback.format_exc()}")
                error_msg = f"Non-streaming reasoning failed: {str(e)}"
                yield {
                    "type": "error",
                    "content": error_msg
                }
        
        # If we get here, all retries failed
        error_msg = "All attempts to obtain reasoning content failed"
        self.logger.error(error_msg)
        yield {
            "type": "error",
            "content": error_msg
        }

    async def _process_phase2_stream(
        self,
        user_message: str,
        system_message: str,
        assistant_message: str,
        workflow_info: WorkflowInfo
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process second phase streaming request
        
        Args:
            user_message: User's question or request
            system_message: System message that guides the model to provide concise summary
            assistant_message: Optional assistant message for context
            workflow_info: Workflow information dictionary
            
        Yields:
            Dict[str, Any]: Streaming response event
        """
        # Reset retry count
        retry_count = 0
        
        # Proceed with Phase2 processing
        summary_content = ""
        summary_success = False
        
        while retry_count <= 0:
            try:
                self.logger.info(f"Starting attempt #{0+1} to obtain summary content")
                
                # Record detailed information of request parameters
                prompt_sample = user_message[:100] + ("..." if len(user_message) > 100 else "")
                self.logger.info(f"Request parameters - prompt (sample): {prompt_sample}")
                self.logger.info(f"Request parameters - prompt (length): {len(user_message)} characters")
                
                # Get reasoning content from phase1
                reasoning_content = ""
                try:
                    reasoning_content = workflow_info.get_reasoning_content()
                except AttributeError:
                    self.logger.warning("Could not get reasoning content, using empty string")
                
                content = workflow_info.get_content()
                
                # Log the content we received from phase1
                self.logger.info(f"Received from phase1 - reasoning_content length: {len(reasoning_content) if reasoning_content else 0}, content length: {len(content) if content else 0}")
                
                # Use reasoning_content if available, otherwise use content from phase1
                assistant_message = reasoning_content if reasoning_content and reasoning_content.strip() else content if content and content.strip() else ""
                
                if assistant_message:
                    self.logger.info(f"Using content from phase1 as assistant content, length: {len(assistant_message)}")
                else:
                    self.logger.warning("No content found from phase1")
                
                # Create streaming request
                self.logger.info("Calling OpenAI compatible client for streaming response...")
                async_generator = self.openai_compatible_client.stream_chat(
                    user_message=user_message,
                    system_message=system_message,
                    assistant_message=assistant_message  # This will be used as the assistant's message
                )

                # Process streaming response
                self.logger.info("Starting to process streaming response...")
                async for chunk_content in async_generator:
                    try:
                        yield {
                            "type": "summary",
                            "content": chunk_content
                        }
                        
                        # Update accumulated content
                        if isinstance(chunk_content, str):
                            summary_content += chunk_content
                        else:
                            summary_content += str(chunk_content)
                    except Exception as e:
                        self.logger.error(f"Error processing summary block: {str(e)}, block content: {chunk_content}")
                        yield {
                            "type": "error",
                            "content": f"Error processing summary block: {str(e)}",
                            "phase": "phase2_stream"
                        }
                
                # Send summary end event
                yield {
                    "type": "summary_end",
                    "content": ""
                }
                
                # Check if content is successfully obtained
                if summary_content and summary_content.strip() != "None":                    
                    self.logger.info(f"Successfully obtained summary content, length: {len(summary_content)}")
                    workflow_info.mark_phase_succeeded("phase2_stream")
                    summary_success = True
                    break  # Successful result obtained, exit retry loop
                else:
                    retry_count += 1
                    
                    if retry_count <= 0:
                        self.logger.warning(f"Streaming summary returned empty content, attempt #{retry_count}...")
                        yield {
                            "type": "error",
                            "content": f"Streaming summary returned empty content, attempt #{retry_count}...",
                            "phase": "phase2_stream"
                        }
                    else:
                        error_msg = "Streaming summary repeatedly returned empty content"
                        self.logger.error(error_msg)
                        yield {
                            "type": "error",
                            "content": error_msg,
                            "phase": "phase2_stream"
                        }
                        workflow_info.mark_phase_failed("phase2_stream", error_msg)
                        
            except asyncio.TimeoutError as e:
                self.logger.error(f"Summary phase timeout: {str(e)}")
                retry_count += 1
                if retry_count <= 0:
                    self.logger.warning(f"Summary phase timeout, attempt #{retry_count}...")
                    yield {
                        "type": "error",
                        "content": f"Summary phase timeout, attempt #{retry_count}...",
                        "phase": "phase2_stream"
                    }
                else:
                    error_msg = f"Summary phase timed out after {retry_count} attempts: {str(e)}"
                    self.logger.error(error_msg)
                    yield {
                        "type": "error",
                        "content": error_msg,
                        "phase": "phase2_stream"
                    }
                    workflow_info.mark_phase_failed("phase2_stream", error_msg)
            
            except Exception as e:
                self.logger.error(f"Summary phase failed: {str(e)}")
                self.logger.error(f"Error details: {traceback.format_exc()}")
                error_msg = f"Summary phase failed: {str(e)}"
                yield {
                    "type": "error",
                    "content": error_msg,
                    "phase": "phase2_stream"
                }
                workflow_info.mark_phase_failed("phase2_stream", error_msg)
                break  # Non-timeout error, exit immediately
        
        # Record final results
        if summary_success:
            workflow_info.mark_phase_succeeded("phase2_stream")
            self.logger.info("Summary phase completed successfully")
        else:
            workflow_info.mark_phase_failed("phase2_stream", "Unable to obtain summary content")
            self.logger.error("Summary phase failed: Unable to obtain valid content")
            
            # Try using reasoning content as fallback
            if reasoning_content:
                error_msg = "Unable to obtain summary content, using reasoning content as response"
                self.logger.warning(error_msg)
                yield {
                    "type": "error",
                    "content": error_msg,
                    "phase": "phase2"
                }

    async def _process_phase2_nonstream(
        self,
        user_message: str,
        system_message: str,
        assistant_message: str,
        workflow_info: WorkflowInfo
    ) -> Dict[str, Any]:
        """
        Process second phase non-streaming request
        
        Args:
            user_message: User's question or request
            system_message: System message that guides the model
            assistant_message: Optional assistant message for context
            workflow_info: Workflow information dictionary
            
        Returns:
            Dict[str, Any]: Response containing final answer
        """
        retry_count = 0
        
        while retry_count <= 0:
            try:
                self.logger.info(f"Starting attempt #{0+1} to obtain summary content")
                
                # Record detailed information of request parameters
                prompt_sample = user_message[:100] + ("..." if len(user_message) > 100 else "")
                self.logger.info(f"Request parameters - prompt (sample): {prompt_sample}")
                self.logger.info(f"Request parameters - prompt (length): {len(user_message)} characters")
                
                # Get reasoning content from phase1
                reasoning_content = workflow_info.get_reasoning()
                content = workflow_info.get_content()
                
                # Use reasoning_content if available, otherwise use content from phase1
                assistant_message = reasoning_content if reasoning_content.strip() else content
                
                if assistant_message:
                    self.logger.info(f"Using content from phase1 as assistant content, length: {len(assistant_message)}")
                else:
                    self.logger.warning("No content found from phase1")
                
                # Create non-streaming request
                self.logger.info("Calling OpenAI compatible client for non-streaming response...")
                result = await self.openai_compatible_client.nonstream_chat(
                    user_message=user_message,
                    system_message=system_message,
                    assistant_message=assistant_message  # This will be used as the assistant's message
                )
                
                # Process response
                self.logger.info("Processing non-streaming response...")
                
                # Handle both dictionary and string results
                content = ""
                if isinstance(result, dict):
                    content = result.get("content", "")
                elif isinstance(result, str):
                    content = result
                
                # Check if content is successfully obtained
                if content:
                    self.logger.info(f"Successfully obtained summary content, length: {len(content)}")
                    workflow_info.mark_phase_succeeded("phase2_nonstream")
                    # Return result with type identifier
                    return {
                        "type": "summary",
                        "content": content
                    }
                else:
                    retry_count += 1
                    
                    if retry_count <= 0:
                        self.logger.warning(f"Non-streaming summary returned empty content, attempt #{retry_count}...")
                        return {
                            "type": "error",
                            "content": f"Non-streaming summary returned empty content, attempt #{retry_count}..."
                        }
                    else:
                        error_msg = "Non-streaming summary repeatedly returned empty content"
                        self.logger.error(error_msg)
                        return {
                            "type": "error",
                            "content": error_msg
                        }
                        
            except Exception as e:
                self.logger.error(f"Non-streaming summary failed: {str(e)}")
                self.logger.error(f"Error details: {traceback.format_exc()}")
                retry_count += 1
                
                if retry_count <= 0:
                    self.logger.warning(f"Non-streaming summary failed, attempt #{retry_count}...")
                    return {
                        "type": "error",
                        "content": f"Non-streaming summary failed, attempt #{retry_count}: {str(e)}"
                    }
                else:
                    error_msg = f"Non-streaming summary repeatedly failed: {str(e)}"
                    self.logger.error(error_msg)
                    return {
                        "type": "error",
                        "content": error_msg
                    }

    async def _execute_callback(self, callback_name: str, *args, **kwargs) -> None:
        """
        Execute callback function
        
        Args:
            callback_name: Callback function name
            *args: Arguments to pass to callback function
            **kwargs: Keyword arguments to pass to callback function
        """
        callback = self.config_manager.get_callback(callback_name)
        if callback:
            try:
                await callback(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"Error executing callback {callback_name}: {str(e)}")
                self.logger.error(traceback.format_exc())
        else:
            self.logger.warning(f"Callback {callback_name} not found") 