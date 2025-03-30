import json
import traceback
from typing import Dict, List, Any, Optional, Tuple, AsyncGenerator
import aiohttp

from .base_client import BaseClient

class DeepSeekClient(BaseClient):
    """
    DeepSeek API Client
    
    A simplified client implementation focused on handling DeepSeek model's reasoning content and response results.
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "",
        request_timeout: float = 180.0,
        proxy_url: Optional[str] = None,
        api_path: Optional[str] = None,
        auto_reasoning: bool = True,
        reasoning_marker: str = "<reasoning>",
        reasoning_end_marker: str = "</reasoning>",
    ):
        """
        Initialize DeepSeek client
        
        Args:
            api_key: DeepSeek API key
            base_url: API base URL
            model: Model name
            request_timeout: Request timeout in seconds
            proxy_url: Proxy URL (e.g., "http://host:port")
            api_path: API path, overrides default path
            auto_reasoning: Whether to automatically switch phases for reasoning-content separation
            reasoning_marker: Marker for reasoning start
            reasoning_end_marker: Marker for reasoning end
        """
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            request_timeout=request_timeout,
            proxy_url=proxy_url,
            api_path=api_path
        )
        
        # Save DeepSeek-specific parameters
        self.api_key = api_key
        self.auto_reasoning = auto_reasoning
        self.reasoning_marker = reasoning_marker
        self.reasoning_end_marker = reasoning_end_marker
    
        # System prompt that guides model to provide reasoning before answer
        self.default_prompt_template = """
            You are DeepSeek-X, a powerfulAIassistant。When answering questions, please first {reasoning_marker}\
            provide detailed reasoning process within the markers, then give a concise clear final answer outside the markers.

            User question: {prompt}

            Please provide complete reasoning first, then give the answer:
            {reasoning_marker}
            """
    
    def format_prompt(self, prompt: str, system_message: Optional[str] = None) -> str:
        """
        Format user prompt with system context
        
        Args:
            prompt: User prompt
            system_message: System message
            
        Returns:
            Formatted prompt with system context
        """
        if system_message:
            return system_message.format(
                prompt=prompt, 
                reasoning_marker=self.reasoning_marker,
                reasoning_end_marker=self.reasoning_end_marker
            )
        else:
            return self.default_prompt_template.format(
                prompt=prompt, 
                reasoning_marker=self.reasoning_marker,
                reasoning_end_marker=self.reasoning_end_marker
            )
    
    async def _process_stream_response(self, response) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process streaming response
        
        Args:
            response: aiohttp response object
            
        Yields:
            Dict[str, Any]: Dictionary with "type" and "content" keys
        """
        line_counter = 0
        empty_content_count = 0
        total_content_length = 0
        accumulated_content = ""  # For phase 2
        reasoning_content = ""  # For phase 2
        has_valid_reasoning = False  # Flag to track if we have valid reasoning content
        reasoning_completed = False  # Flag to track if reasoning phase is completed
        
        self.logger.info("Processing stream response")
        
        try:
            async for line in response.content:
                try:
                    line_counter += 1
                    line_text = line.decode('utf-8').strip()
                    
                    # Log raw data line if needed
                    if line_counter % 10 == 0:
                        self.logger.debug(f"Response line: {line_counter}")
                    
                    if not line_text:
                        empty_content_count += 1
                        if empty_content_count % 10 == 0:
                            self.logger.debug(f"Empty content count: {empty_content_count}")
                        continue
                    
                    empty_content_count = 0
                    
                    # Log the data line being processed
                    self.logger.debug(f"Processing data line: {line_text}")
                    
                    # Check if line starts with "data: "
                    if not line_text.startswith("data: "):
                        self.logger.warning(f"Invalid line format: {line_text[:100]}...")
                        continue
                    
                    # Extract JSON data
                    response_text = line_text[6:]  # Remove "data: " prefix
                    
                    try:
                        # Parse JSON response
                        response_data = json.loads(response_text)
                        
                        # Process DeepSeek API format response
                        if isinstance(response_data, dict) and "choices" in response_data and len(response_data["choices"]) > 0:
                            choice = response_data["choices"][0]
                            
                            # Check for delta content
                            if "delta" in choice:
                                delta = choice["delta"]
                                
                                # Check for reasoning_content in delta
                                if "reasoning_content" in delta:
                                    reasoning_chunk = delta["reasoning_content"]
                                    if reasoning_chunk and reasoning_chunk != "null" and reasoning_chunk != "None":
                                        self.logger.debug(f"Found reasoning content: {reasoning_chunk}")
                                        reasoning_content += reasoning_chunk
                                        has_valid_reasoning = True
                                        # Immediately yield reasoning content
                                        yield {
                                            "type": "reasoning",
                                            "content": reasoning_chunk
                                        }

                                    elif has_valid_reasoning and not reasoning_completed:
                                        # If we previously had reasoning content but now it's empty,
                                        # and content field starts to appear, this indicates end of reasoning
                                        self.logger.debug("Reasoning content ended")
                                        reasoning_completed = True

                                # Process content only if no reasoning exists or reasoning is always empty
                                if "content" in delta and not has_valid_reasoning:
                                    content = delta["content"]
                                    if content and content != "null" and content != "None":
                                        self.logger.debug(f"Found content: {len(content)} characters")
                                        accumulated_content += content
                                        # If we never had reasoning content, use content as reasoning
                                        if not has_valid_reasoning:
                                            reasoning_content = accumulated_content
                                            has_valid_reasoning = True
                                            yield {
                                                "type": "reasoning",
                                                "content": content
                                            }
                                        # Always yield content
                                        yield {
                                            "type": "content",
                                            "content": content
                                        }
                                
                                # Check for finish_reason as a backup
                                if reasoning_completed or ("finish_reason" in choice and choice["finish_reason"] == "stop"):
                                    self.logger.debug("Received completion signal")
                                    
                                    # Send phase1_complete event with accumulated content
                                    yield {
                                        "type": "phase1_complete",
                                        "reasoning_content": reasoning_content if has_valid_reasoning else "",
                                        "content": accumulated_content
                                    }
                                    
                                    # Send reasoning end event
                                    yield {
                                        "type": "reasoning_end",
                                        "content": ""
                                    }
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"Failed to parse JSON data: {str(e)}")
                        continue
                    except Exception as e:
                        self.logger.error(f"Error processing response data: {str(e)}")
                        self.logger.error(traceback.format_exc())
                        continue
                except Exception as e:
                    self.logger.error(f"Error processing line: {str(e)}")
                    self.logger.error(traceback.format_exc())
                    continue
            
            # Log final statistics
            self.logger.info(f"Stream processing completed - Total lines: {line_counter}, Total content length: {total_content_length}")
            
        except Exception as e:
            self.logger.error(f"Error processing stream response: {str(e)}")
            self.logger.error(traceback.format_exc())
            yield {
                "type": "error",
                "content": f"Error processing stream response: {str(e)}"
            }
    
    def _process_nonstream_response(self, response_text: str) -> Dict[str, str]:
        """
        Process non-streaming response from DeepSeek API
        
        Args:
            response_text: Response text in format:
            {
                "id": "...",
                "object": "chat.completion",
                "created": timestamp,
                "model": "deepseek-chat",
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "..."
                    }
                }]
            }
            
        Returns:
            Dict[str, str]: Processed response, dictionary with "content" and optional "reasoning" keys
        """
        self.logger.info("Processing non-stream response")
        
        result = {
            "content": "",
            "reasoning": ""
        }
        
        try:
            # Parse JSON response
            response_data = json.loads(response_text)
            self.logger.debug(f"_process_nonstream_response Response data: {response_data}")
            
            # Process DeepSeek API format response
            if isinstance(response_data, dict) and "choices" in response_data and len(response_data["choices"]) > 0:
                choice = response_data["choices"][0]
                
                # Check for message field and content
                if "message" in choice and "content" in choice["message"]:
                    content = choice["message"]["content"]
                    if content and content != "null" and content != "None":
                        # Try to extract reasoning part and content part from content
                        if self.reasoning_marker in content and self.reasoning_end_marker in content:
                            try:
                                # Extract reasoning part and final answer part
                                reasoning_start = content.find(self.reasoning_marker) + len(self.reasoning_marker)
                                reasoning_end = content.find(self.reasoning_end_marker)
                                
                                if reasoning_start > 0 and reasoning_end > reasoning_start:
                                    reasoning_part = content[reasoning_start:reasoning_end].strip()
                                    content_part = content[reasoning_end + len(self.reasoning_end_marker):].strip()
                                    
                                    if reasoning_part:
                                        self.logger.debug(f"Extracted reasoning: {len(reasoning_part)}characters")
                                        result["reasoning"] = reasoning_part
                                    
                                    if content_part:
                                        self.logger.debug(f"Extracted answer: {len(content_part)}characters")
                                        result["content"] = content_part
                                else:
                                    # Marker positions abnormal, use entire content
                                    self.logger.warning("Marker position abnormal, using entire content")
                                    result["content"] = content
                            except Exception as e:
                                self.logger.error(f"Content separation failed: {str(e)}")
                                result["content"] = content
                        else:
                            # No reasoning markers found, use entire content as both reasoning and content
                            self.logger.debug(f"No reasoning marker found in content: {len(content)}characters")
                            result["content"] = content
                            result["reasoning"] = content  # Use the same content for both
                else:
                    self.logger.error("No message.content field found in response")
                    result["error"] = "No message.content field found in response"
            else:
                self.logger.error("Invalid response format")
                result["error"] = "Invalid response format"
            
            # If still no valid content, return error
            if not result["content"] and not result["reasoning"]:
                self.logger.error("No valid content extracted")
                result["error"] = "Unable to extract valid content from response"
            
            self.logger.debug(f"Processing complete:\n reasoning_content: \n{result.get('reasoning', '')}\n, content: \n{result.get('content', '')}\n")
            self.logger.info(f"Processing complete: {len(result.get('reasoning', ''))}characters reasoning, {len(result.get('content', ''))}characters content")
            
            return result
            
        except json.JSONDecodeError:
            self.logger.warning("JSON parsing error")
            return {"error": "Invalid JSON response"}
        except Exception as e:
            error_msg = f"Processing error: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            return {"error": error_msg}

    def _prepare_messages(
        self,
        user_message: str,
        system_message: Optional[str] = None,
        assistant_message: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Prepare messages for API request
        
        Args:
            user_message: User's question or request
            system_message: System message that guides the model to provide reasoning
            assistant_message: Optional assistant message (not used in DeepSeekClient)
            
        Returns:
            List of messages for API request
        """
        messages = []
        
        # Add system message if provided
        if system_message:
            messages.append({
                "role": "system",
                "content": system_message
            })
        
        # Add user message
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        return messages

    async def stream_chat(
        self,
        user_message: str,
        system_message: str = "",
        assistant_message: str = "",
        max_tokens: int = 8000
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat completion
        
        Args:
            user_message: User's question or request
            system_message: System message that guides the model
            assistant_message: Optional assistant message for context
            max_tokens: Maximum number of tokens to generate
            
        Yields:
            Dict[str, Any]: Dictionary with "type" and "content" keys
        """
        self.logger.info("Starting stream chat")
        
        # Format system message to guide reasoning
        if not system_message:
            system_message = """You are DeepSeek-X, a powerful AI assistant. When answering questions, please first provide detailed reasoning process within the markers, then give a concise clear final answer outside the markers.

Please provide complete reasoning first, then give the answer:
{reasoning_marker}"""
        
        # Format the system message with actual markers
        system_message = system_message.format(
            reasoning_marker=self.reasoning_marker,
            reasoning_end_marker=self.reasoning_end_marker
        )
        
        messages = self._prepare_messages(user_message, system_message, assistant_message)
        headers = self._prepare_stream_headers(self.api_key)
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": 0.7,
            "max_tokens": max_tokens
        }
        
        # Use base class's streaming request method
        async for chunk in self._make_request_stream(
            url=self.full_url,
            payload=payload,
            headers=headers,
            api_name="DeepSeek API",
            process_stream_response_func=self._process_stream_response
        ):
            yield chunk
    
    async def nonstream_chat(
        self,
        user_message: str,
        system_message: Optional[str] = None,
        assistant_message: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Non-streaming chat, returning reasoning content and regular content
        
        Args:
            user_message: User's question or request
            system_message: System message that guides the model to provide reasoning
            assistant_message: Optional assistant message (not used in DeepSeekClient)
            
        Returns:
            Dict[str, str]: Dictionary with "content" and optional "reasoning" keys
        """
        self.logger.info("Starting non-stream chat")
        
        # Format system message to guide reasoning
        if not system_message:
            system_message = """You are DeepSeek-X, a powerful AI assistant. When answering questions, please first provide detailed reasoning process within the markers, then give a concise clear final answer outside the markers.

Please provide complete reasoning first, then give the answer:
{reasoning_marker}"""
        
        messages = self._prepare_messages(user_message, system_message, assistant_message)
        headers = self._prepare_nonstream_headers(self.api_key)
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": 0.7,
            "max_tokens": 8000
        }
        
        try:
            # Use base class's non-streaming request method
            result = await self._make_request_nonstream(
                url=self.full_url,
                payload=payload,
                headers=headers,
                api_name="DeepSeek API",
                process_nonstream_response_func=self._process_nonstream_response
            )
            
            self.logger.info(f"Non-stream request complete: {len(result)}items")   
            self.logger.debug(f"Non-stream request result: {result}")             
            return result
            
        except Exception as e:
            error_msg = f"Non-streaming request failed: {str(e)}"
            self.logger.error(error_msg)
            # Ensure standard error format is returned
            return {"error": error_msg}
