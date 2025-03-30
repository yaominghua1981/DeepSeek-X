import json
from typing import Dict, List, Any, Optional, Union, AsyncGenerator

from .base_client import BaseClient


class OpenAICompatibleClient(BaseClient):
    """
    OpenAI compatible client for interacting with APIs that support OpenAI's format (e.g., Gemini).
    
    Mainly responsible for receiving reasoning results from other LLMs (like DeepSeek)
    and generating final summarized answers.
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "",
        organization: Optional[str] = None,
        request_timeout: float = 180.0,
        proxy_url: Optional[str] = None,
        api_path: Optional[str] = None
    ):
        """
        Initialize OpenAI compatible client
        
        Args:
            api_key: API key
            base_url: API base URL
            model: Model name
            organization: Organization ID (optional, for OpenAI)
            request_timeout: Request timeout in seconds
            proxy_url: Proxy URL
            api_path: API path (optional, overrides default path)
        """
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            request_timeout=request_timeout,
            proxy_url=proxy_url,
            api_path=api_path
        )
        self.api_key = api_key
        self.model = model
        self.organization = organization
        self.default_system_message = (
            "You are an excellent AI assistant. Please provide a concise and clear final answer based on the provided reasoning."
            "You don't need to repeat the reasoning process, just give a clear conclusion."
        )
        
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
            system_message: System message that guides the model to provide concise summary
            assistant_message: Optional assistant message containing reasoning content
            
        Returns:
            List of messages for API request
        """
        messages = []
        
        # Add system message if provided
        if system_message:
            messages.append({
                "role": "system",
                "content": [{"type": "text", "text": system_message}]
            })
        
        # Add assistant message if provided (reasoning content)
        if assistant_message:
            messages.append({
                "role": "assistant",
                "content": [{"type": "text", "text": assistant_message}]
            })
        
        # Add user message
        messages.append({
            "role": "user",
            "content": [{"type": "text", "text": user_message}]
        })
        
        return messages
    
    async def _process_stream_response(self, response) -> AsyncGenerator[str, None]:
        """
        Process streaming response
        
        Args:
            response: aiohttp response object
            
        Yields:
            str: Response content chunks
        """
        line_counter = 0
        empty_content_count = 0
        total_content_length = 0
        accumulated_content = ""
        buffer = ""  # Buffer for handling partially received data
        
        self.logger.info("Processing stream response")
        
        try:
            async for line in response.content:
                try:
                    line_counter += 1
                    line_text = line.decode('utf-8')
                    
                    # Log raw data line if needed
                    if line_counter % 10 == 0:
                        self.logger.debug(f"Response line: {line_counter}")
                    
                    # Process buffer
                    buffer += line_text
                    
                    # Process complete lines in buffer
                    while '\n' in buffer:
                        current_line, buffer = buffer.split('\n', 1)
                        current_line = current_line.strip()
                        
                        # Skip empty lines and end markers
                        if not current_line:
                            continue
                        
                        if current_line == "data: [DONE]":
                            self.logger.debug("结束标记")
                            break
                        
                        # Process data lines
                        if current_line.startswith("data: "):
                            try:
                                data_json = current_line[6:]  # Extract JSON part after "data: "
                                data = json.loads(data_json)
                                                                
                                # Check data structure
                                if "choices" in data and len(data["choices"]) > 0:
                                    choice = data["choices"][0]
                                    delta = choice.get("delta", {})
                                    
                                    # Extract content
                                    content = self._extract_content_from_delta(delta)
                                    
                                    if content:
                                        total_content_length += len(content)
                                        accumulated_content += content
                                        yield content
                                    else:
                                        empty_content_count += 1
                                    
                                    # Check for completion signal
                                    if choice.get("finish_reason") in ["stop", "length"]:
                                        self.logger.debug(f"Completed: {choice.get('finish_reason')}")
                                        break
                                else:
                                    self.logger.warning(f"No choices field")
                                
                            except json.JSONDecodeError as e:
                                self.logger.warning(f"JSON error: {str(e)}")
                                continue
                        
                except UnicodeDecodeError as e:
                    self.logger.error(f"Decoding error: {str(e)}")
                    continue
                except Exception as e:
                    self.logger.error(f"Processing error: {str(e)}")
                    continue
            
            # Process remaining buffer
            if buffer.strip():
                if buffer.strip().startswith("data: ") and buffer.strip() != "data: [DONE]":
                    try:
                        data_json = buffer.strip()[6:]
                        data = json.loads(data_json)
                        
                        if "choices" in data and len(data["choices"]) > 0:
                            choice = data["choices"][0]
                            delta = choice.get("delta", {})
                            content = self._extract_content_from_delta(delta)
                            
                            if content:
                                total_content_length += len(content)
                                accumulated_content += content
                                yield content
                    except Exception as e:
                        self.logger.warning(f"Buffer processing error")
                
            if empty_content_count > 0:
                self.logger.debug(f"空内容次数: {empty_content_count}")
            
        except Exception as e:
            self.logger.error(f"响应读取错误: {str(e)}")
            
        if accumulated_content:
            self.logger.info(f"内容累积: {len(accumulated_content)}字符")
        
        # Log error conditions
        if line_counter == 0:
            self.logger.error(f"无响应行")
        elif total_content_length == 0:
            self.logger.warning(f"所有行为空内容")
        elif total_content_length < 10:
            self.logger.warning(f"内容过短: {total_content_length}字符")
        
        self.logger.info(f"流处理完成: {line_counter}行, {total_content_length}字符")
    
    def _extract_content_from_delta(self, delta: Dict[str, Any]) -> str:
        """
        Extract text content from delta object in streaming response
        
        Args:
            delta: Delta object from streaming response
            
        Returns:
            str: Extracted content
        """
        if isinstance(delta, dict):
            # Handle content field directly
            if "content" in delta and delta["content"] is not None:
                return delta["content"]
            
            # Handle tool calls (API may include tool_calls in delta)
            if "tool_calls" in delta and delta["tool_calls"]:
                try:
                    # Return a readable representation of tool calls
                    return "[工具调用]"
                except Exception:
                    pass
                
            # For Anthropic/Claude format
            if "text" in delta and delta["text"] is not None:
                return delta["text"]
            
            # For Google Gemini format
            if "parts" in delta and delta["parts"]:
                for part in delta["parts"]:
                    if isinstance(part, dict) and "text" in part:
                        return part["text"]
            
            # Return empty string for no content case
            return ""
        
        # Handle case where delta is a string directly
        if isinstance(delta, str):
            return delta
        
        return ""
    
    def _extract_content_from_response(self, response_json: Dict[str, Any]) -> str:
        """
        Extract content from non-streaming response
        
        Args:
            response_json: Response JSON
            
        Returns:
            str: Extracted content
        """
        try:
            # Extract from OpenAI API format
            if "choices" in response_json and len(response_json["choices"]) > 0:
                choice = response_json["choices"][0]
                
                # Extract from message format (chat completions)
                if "message" in choice:
                    msg = choice["message"]
                    if "content" in msg and msg["content"] is not None:
                        return msg["content"]
                    
                    # Handle tool calls
                    if "tool_calls" in msg and msg["tool_calls"]:
                        return json.dumps(msg["tool_calls"], ensure_ascii=False)
                
                # Extract from text/content format (completions)
                if "text" in choice and choice["text"] is not None:
                    return choice["text"]
                
                if "content" in choice and choice["content"] is not None:
                    return choice["content"]
            
            # For Anthropic/Claude format
            if "content" in response_json and isinstance(response_json["content"], list):
                text_parts = []
                for part in response_json["content"]:
                    if isinstance(part, dict) and "text" in part:
                        text_parts.append(part["text"])
                return "".join(text_parts)
                
            self.logger.warning(f"无法提取内容")
            return ""
            
        except Exception as e:
            self.logger.error(f"提取错误: {str(e)}")
            return ""
    
    def _format_error_response(self, error_message: str) -> Dict[str, str]:
        """
        Format error response
        
        Args:
            error_message: Error message
            
        Returns:
            Dict[str, str]: Dictionary with 'error' key containing the error message
        """
        return {"error": f"OpenAI Compatible API Error: {error_message}"}
    
    async def stream_chat(
        self,
        user_message: str,
        system_message: Optional[str] = None,
        assistant_message: Optional[str] = None,
        max_tokens: int = 8000
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat, returning content chunks
        
        Args:
            user_message: User's question or request
            system_message: System message that guides the model to provide concise summary
            assistant_message: Optional assistant message containing reasoning content
            max_tokens: Maximum number of tokens to generate
            
        Yields:
            str: Content chunks
        """
        self.logger.info("Starting stream chat")
        
        # Format system message to guide summary
        if not system_message:
            system_message = self.default_system_message
        
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
            api_name="OpenAI Compatible API",
            process_stream_response_func=self._process_stream_response
        ):
            yield chunk
    
    def _process_nonstream_response(self, response_text: str) -> Union[Dict[str, Any], str]:
        """
        Process non-streaming response
        
        Args:
            response_text: Response text
            
        Returns:
            Union[Dict[str, Any], str]: Processed response (either JSON or string)
        """
        self.logger.info("Processing non-stream response")
        
        try:
            # Parse JSON response
            response_json = json.loads(response_text)
            self.logger.info("JSON parsing successful")
            
            # Extract content
            content = self._extract_content_from_response(response_json)
            
            # If content was successfully extracted, return it
            # Otherwise, return the original response
            return content if content else response_json
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error: {str(e)}")
            self.logger.warning("Not valid JSON, returning original text")
            return response_text
        except Exception as e:
            self.logger.error(f"Processing error: {str(e)}")
            return response_text
    
    async def nonstream_chat(
        self,
        user_message: str,
        system_message: Optional[str] = None,
        assistant_message: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Non-streaming chat, returning content
        
        Args:
            user_message: User's question or request
            system_message: System message that guides the model to provide concise summary
            assistant_message: Optional assistant message containing reasoning content
            
        Returns:
            Dict[str, str]: Dictionary with "content" key
        """
        self.logger.info("Starting non-stream chat")
        
        # Format system message to guide summary
        if not system_message:
            system_message = self.default_system_message

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
                api_name="OpenAI Compatible API",
                process_nonstream_response_func=self._process_nonstream_response
            )
            
            self.logger.info(f"Non-stream request complete: {len(result)}items")                
            return result
            
        except Exception as e:
            error_msg = f"Non-streaming request failed: {str(e)}"
            self.logger.error(error_msg)
            # Ensure standard error format is returned
            return {"error": error_msg}