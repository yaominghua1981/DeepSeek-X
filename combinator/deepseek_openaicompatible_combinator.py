from typing import Dict, Optional, Union, Any, AsyncGenerator
from clients.deepseek_client import DeepSeekClient
from clients.openai_compatible_client import OpenAICompatibleClient
from workflow.workflow import DeepSeekXWorkflow
from utils.logger import get_logger
from dataclasses import dataclass
import asyncio
import traceback

@dataclass
class WorkflowResult:
    """Result from a workflow execution"""
    content: str = ""
    error: Optional[str] = None
    status_code: int = 200
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

class DeepSeekOpenAICompatibleCombinator:
    """
    Combinator class for combining DeepSeek's reasoning capabilities with OpenAI compatible models:
    1. First phase: Get reasoning from DeepSeek
    2. Second phase: Get final answer from OpenAI-compatible model using DeepSeek's reasoning
    """
    
    def __init__(
        self,
        config_manager: 'ConfigManager'
    ):
        """
        Initialize a two-phase model combinator
        
        Args:
            config_manager: Configuration manager instance that contains all necessary settings
        """
        self.logger = get_logger(self.__class__.__name__)
        
        # Get the currently active composite model configuration
        try:
            composite_config = config_manager.get_active_config_for_chat_manager()
            self.logger.info(f"Retrieved active composite model configuration")
        except ValueError as e:
            self.logger.error(f"Failed to get active composite model configuration: {str(e)}")
            raise
        
        # Initialize DeepSeek client
        self.deepseek_client = DeepSeekClient(
            api_key=composite_config.get("deepseek_api_key", ""),
            base_url=composite_config.get("deepseek_base_url", ""),
            model=composite_config.get("deepseek_model", ""),
            request_timeout=composite_config.get("request_timeout", 180.0),
            proxy_url=composite_config.get("proxy_url", None),
            api_path=composite_config.get("deepseek_api_path", None)
        )
        
        # Initialize OpenAI compatible client
        self.openai_compatible_client = OpenAICompatibleClient(
            api_key=composite_config.get("openai_compatible_api_key", ""),
            base_url=composite_config.get("openai_compatible_base_url", ""),
            model=composite_config.get("openai_compatible_model", ""),
            request_timeout=composite_config.get("request_timeout", 180.0),
            proxy_url=composite_config.get("proxy_url", None),
            api_path=composite_config.get("openai_compatible_api_path", None)
        )
        
        # Set request timeout
        self.request_timeout = composite_config.get("request_timeout", 180.0)
        
        # Initialize workflow manager
        self.workflow = DeepSeekXWorkflow(
            deepseek_client=self.deepseek_client,
            openai_compatible_client=self.openai_compatible_client,
            config_manager=config_manager,
            logger=self.logger
        )

        self.logger.info(f"DeepSeekOpenAICompatibleCombinator initialized with models: DeepSeek={composite_config.get('deepseek_model')}, OpenAI Compatible={composite_config.get('openai_compatible_model')}")
        self.logger.info(f"Using proxy: {composite_config.get('proxy_url', 'None')}")
        self.logger.info(f"Request timeout: {self.request_timeout} seconds")
    
    async def process_stream(
        self,
        user_message: str,
        system_message: str = "",
        assistant_message: str = ""
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process streaming request
        
        Args:
            user_message: User's question or request
            system_message: System message that guides the model
            assistant_message: Optional assistant message for context
            
        Yields:
            Dict[str, Any]: Streaming response event
        """
        try:
            # Initialize workflow info
            workflow_info = {
                "success": False,
                "phases_executed": [],
                "phases_succeeded": [],
                "phases_failed": [],
                "error": None,
                "reasoning_obtained": False,
                "reasoning_method": None,
                "content_obtained": False,
                "content": None,
                "content_method": None,
                "final_answer_obtained": False,
                "final_answer_method": None,
                "start_time": asyncio.get_event_loop().time(),
                "end_time": None,
                "retries": {
                    "phase1": 0,
                    "phase2": 0
                }
            }
            
            # Process through workflow
            async for event in self.workflow.process(
                user_message=user_message,
                system_message=system_message,
                assistant_message=assistant_message
            ):
                yield event
                
        except Exception as e:
            self.logger.error(f"Streaming request processing error: {str(e)}")
            self.logger.error(traceback.format_exc())
            yield {
                "type": "error",
                "content": str(e)
            }

    async def process_nonstream(
        self,
        user_message: str,
        system_message: str = "",
        assistant_message: str = ""
    ) -> Dict[str, Any]:
        """
        Process non-streaming request
        
        Args:
            user_message: User's question or request
            system_message: System message that guides the model
            assistant_message: Optional assistant message for context
            
        Returns:
            Dict[str, Any]: Response containing content and reasoning
        """
        try:
            # Initialize workflow info
            workflow_info = {
                "success": False,
                "phases_executed": [],
                "phases_succeeded": [],
                "phases_failed": [],
                "error": None,
                "reasoning_obtained": False,
                "reasoning_method": None,
                "content_obtained": False,
                "content": None,
                "content_method": None,
                "final_answer_obtained": False,
                "final_answer_method": None,
                "start_time": asyncio.get_event_loop().time(),
                "end_time": None,
                "retries": {
                    "phase1": 0,
                    "phase2": 0
                }
            }
            
            # Process through workflow
            events_generator = self.workflow.process(
                user_message=user_message,
                system_message=system_message,
                assistant_message=assistant_message
            )
            
            # Process all events and collect final result
            result = WorkflowResult()
            final_content = await self._collect_async_generator_results(events_generator)
            
            # Handle different return types
            if isinstance(final_content, dict):
                if "content" in final_content:
                    result.content = final_content.get("content", "")
                elif "error" in final_content:
                    result.error = final_content.get("error", "Unknown error")
                    result.status_code = 500
            elif isinstance(final_content, str):
                result.content = final_content
                
            self.logger.info(f"Non-stream request completed, content length: {len(result.content) if result.content else 0}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Non-stream request processing error: {str(e)}")
            result = WorkflowResult(error=str(e), status_code=500)
            return result
    
    async def _collect_async_generator_results(self, generator: AsyncGenerator) -> Union[str, Dict[str, Any]]:
        """
        Collect all results from an async generator and return the final result
        
        Args:
            generator: Async generator
            
        Returns:
            Union[str, Dict[str, Any]]: Final result, which may be a string or dictionary
        """
        self.logger.info("Starting to collect async generator results")
        accumulated_result = None
        last_result = None
        reasoning_content = ""
        summary_content = ""
        has_reasoning = False
        has_summary = False
        
        try:
            async for result in generator:
                last_result = result
                
                # Collect different content based on event type
                event_type = result.get("type", "") if isinstance(result, dict) else ""
                content = result.get("content", "") if isinstance(result, dict) else result
                
                # Process and extract content
                if event_type == "reasoning" and content:
                    self.logger.info(f"Received reasoning content, length: {len(content) if isinstance(content, str) else 'non-string'}")
                    
                    # Process reasoning content
                    if isinstance(content, str):
                        reasoning_content += content
                        has_reasoning = True
                    else:
                        self.logger.warning(f"Reasoning content is not a string: {type(content).__name__}")
                        
                elif event_type == "summary" and content:
                    self.logger.info(f"Received summary content, type: {type(content).__name__}")
                    
                    # Handle OpenAI API response format
                    extracted_content = ""
                    
                    if isinstance(content, dict) and "choices" in content:
                        self.logger.info("Detected OpenAI API response format, extracting content")
                        try:
                            if content.get("choices") and len(content["choices"]) > 0:
                                choice = content["choices"][0]
                                if "message" in choice and "content" in choice["message"]:
                                    extracted_content = choice["message"]["content"]
                                    self.logger.info(f"Successfully extracted content from OpenAI response, length: {len(extracted_content)}")
                                else:
                                    self.logger.warning("Could not find message.content in choices")
                        except Exception as extract_err:
                            self.logger.error(f"Error extracting content from OpenAI response: {str(extract_err)}")
                    else:
                        # If not standard format, use content directly
                        extracted_content = content if isinstance(content, str) else str(content)
                        
                    # Add extracted content
                    if extracted_content:
                        summary_content += extracted_content
                        has_summary = True
                
                # Update accumulated result (for simple types)
                if accumulated_result is None:
                    accumulated_result = result
                elif isinstance(accumulated_result, dict) and isinstance(result, dict):
                    # If both are dictionaries, try to merge them
                    if "content" in accumulated_result and "content" in result:
                        accumulated_result["content"] += result["content"]
                    # Update other possible fields
                    for key, value in result.items():
                        if key != "content":
                            accumulated_result[key] = value
                elif isinstance(accumulated_result, str) and isinstance(result, str):
                    # If both are strings, concatenate directly
                    accumulated_result += result
                
        except Exception as e:
            self.logger.error(f"Error collecting async generator results: {str(e)}")
            if last_result is not None:
                self.logger.warning("Returning last received result")
                return last_result
            else:
                return f"Error collecting results: {str(e)}"
        
        # Determine which content to return based on availability
        if has_summary and summary_content:
            self.logger.info(f"Returning summary content, length: {len(summary_content)}")
            return summary_content
        elif has_reasoning and reasoning_content:
            self.logger.info(f"Returning reasoning content, length: {len(reasoning_content)}")
            return reasoning_content
        elif accumulated_result is not None:
            self.logger.info("Returning accumulated result")
            return accumulated_result
        elif last_result is not None:
            self.logger.info("Returning last received result")
            return last_result
        else:
            self.logger.warning("No results available to return")
            return "No results available" 