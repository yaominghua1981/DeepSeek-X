import aiohttp
import json
import asyncio
import traceback
import socket
from typing import Dict, Any, Optional,AsyncGenerator, Callable
from utils.logger import get_logger


class BaseClient:
    """
    Base LLM API client class, providing common functionality for interacting with LLM APIs
    
    This class implements common functionality needed by all LLM API clients, such as handling proxies,
    preparing request headers, constructing API URLs, error handling, etc. Subclasses only need to implement
    specific functionality.
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        request_timeout: float = 180.0,
        proxy_url: Optional[str] = None,
        api_path: Optional[str] = None
    ):
        """
        Initialize base client
        
        Args:
            api_key: API key
            base_url: API base URL
            model: Model name
            request_timeout: Request timeout in seconds
            proxy_url: Proxy URL (e.g., "http://host:port")
            api_path: API path, overrides default path
        """
        self.api_key = api_key
        self.model = model
        self.request_timeout = request_timeout
        
        # Build complete URL, ensuring only one slash between base_url and api_path
        if api_path:
            # Remove trailing slash from base_url (if any)
            base_url = base_url.rstrip('/')
            # Ensure api_path starts with a slash
            if not api_path.startswith('/'):
                api_path = '/' + api_path
            self.full_url = base_url + api_path
        else:
            # If no api_path, use base_url directly
            self.full_url = base_url
        
        # Ensure proxy URL format is correct
        if proxy_url:
            # Remove any existing protocol prefix
            if proxy_url.startswith(('http://', 'https://')):
                proxy_url = proxy_url.split('://', 1)[1]
            # Add HTTP protocol prefix
            self.proxy_url = f"http://{proxy_url}"
        else:
            self.proxy_url = None
        
        # Initialize logger using get_logger function, automatically reading log level from config file
        self.logger = get_logger(self.__class__.__name__)
        
        if self.proxy_url:
            self.logger.info(f"Using proxy: {self.proxy_url}")
            
        # Log initialization information
        self.logger.info(f"Initialized: model={model}, url={self.full_url}")
    
    def _prepare_stream_headers(self, api_key: str) -> Dict[str, str]:
        """
        Prepare API request headers (for streaming requests)
        
        Returns:
            Dictionary containing authorization and text/event-stream Accept headers
        """
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Accept": "text/event-stream"
        }
    
    def _prepare_nonstream_headers(self, api_key: str) -> Dict[str, str]:
        """
        Prepare API request headers for non-streaming requests
        
        Returns:
            Dictionary containing application/json Accept headers
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json"
        }
        return headers
    
    def _create_timeout_config(self, custom_timeout: Optional[float] = None) -> aiohttp.ClientTimeout:
        """
        Create aiohttp timeout configuration
        
        Args:
            custom_timeout: Custom timeout value, defaults to self.request_timeout
            
        Returns:
            aiohttp.ClientTimeout instance
        """
        timeout_value = custom_timeout or self.request_timeout
        return aiohttp.ClientTimeout(
            total=timeout_value,
            connect=min(60.0, timeout_value * 0.5),  # Larger timeout for connection
            sock_read=timeout_value * 0.8  # Socket read timeout set to 80% of total time
        )
    
    async def _make_request_nonstream(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        api_name: str = "API",
        process_nonstream_response_func: Callable = None
    ) -> Any:
        """
        Send non-streaming HTTP request and process the response
        
        Args:
            url: Request URL
            payload: Request payload data
            headers: Request headers
            api_name: API name, used for error messages
            process_nonstream_response_func: Function to process non-streaming response
            
        Returns:
            Processed response content
        """
        if not process_nonstream_response_func:
            raise ValueError("A function for processing non-stream responses must be provided")
            
        self._log_request_details(url, headers, payload)
        
        start_time = asyncio.get_event_loop().time()
        response_start_time = None
        request_end_time = None
        
        try:
            # Create connector and timeout settings
            connector = aiohttp.TCPConnector(
                force_close=True,
                enable_cleanup_closed=True,
                limit=10,
                ssl=False,
                family=socket.AF_UNSPEC
            )
            
            timeout = self._create_timeout_config()
            
            # Create session and send request
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                self.logger.debug(f"Sending request to {url}")
                
                async with session.post(
                    url, 
                    json=payload, 
                    headers=headers,
                    proxy=self.proxy_url
                ) as response:
                    response_start_time = asyncio.get_event_loop().time()
                    elapsed_until_response = response_start_time - start_time
                    self.logger.debug(f"Received response: {response.status}, time: {elapsed_until_response:.2f}s")
                    
                    # Check response status
                    if response.status != 200:
                        error_text = await response.text()
                        self.logger.error(f"Error response: HTTP {response.status}, {error_text}")
                        self._handle_api_error(response.status, error_text, api_name)
                    
                    # Read response content
                    response_text = await response.text()
                    request_end_time = asyncio.get_event_loop().time()
                    elapsed_reading = request_end_time - response_start_time
                    
                    response_size = len(response_text)
                    self.logger.debug(f"Reading complete: {response_size} bytes, time: {elapsed_reading:.2f}s")
                    
                    # Process non-streaming response using provided function
                    result = process_nonstream_response_func(response_text)
                    self.logger.debug(f"Processing complete: {type(result).__name__}")
                    return result
                
        except aiohttp.ClientConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            self.logger.error(error_msg)
            return self._format_error_response(error_msg)
        except asyncio.TimeoutError:
            elapsed = "unknown"
            if start_time:
                elapsed = f"{asyncio.get_event_loop().time() - start_time:.2f}"
                
            error_msg = f"Request timeout: {elapsed}s"
            self.logger.error(error_msg)
            return self._format_error_response(error_msg)
        except Exception as e:
            self.logger.error(f"Request error: {str(e)}")
            self.logger.error(f"Type: {type(e).__name__}")
            self.logger.error(f"Stack trace: {traceback.format_exc()}")
            return self._format_error_response(f"Request error: {str(e)}")
        finally:
            # Log timing information
            if start_time:
                end_time = asyncio.get_event_loop().time()
                total_elapsed = end_time - start_time
                
                timing_log = [f"Total time: {total_elapsed:.2f}s"]
                
                if response_start_time:
                    conn_time = response_start_time - start_time
                    timing_log.append(f"Connection: {conn_time:.2f}s")
                    
                if request_end_time and response_start_time:
                    read_time = request_end_time - response_start_time
                    timing_log.append(f"Reading: {read_time:.2f}s")
                
                self.logger.debug(f"Timing: {', '.join(timing_log)}")
    
    def _handle_api_error(self, status_code: int, error_text: str, api_name: str) -> None:
        """
        Handle API errors and raise appropriate exceptions
        
        Args:
            status_code: HTTP status code
            error_text: Error response text
            api_name: API name for context
            
        Raises:
            Exception: With appropriate error message
        """
        error_message = f"{api_name} error (HTTP {status_code}): {error_text}"
        
        # Try to parse error as JSON for more detailed information
        try:
            error_json = json.loads(error_text)
            if isinstance(error_json, dict):
                # Extract error details from common formats
                if "error" in error_json:
                    error_obj = error_json["error"]
                    if isinstance(error_obj, dict):
                        if "message" in error_obj:
                            error_message = f"{api_name} error: {error_obj['message']}"
                        elif "msg" in error_obj:
                            error_message = f"{api_name} error: {error_obj['msg']}"
                    elif isinstance(error_obj, str):
                        error_message = f"{api_name} error: {error_obj}"
                elif "message" in error_json:
                    error_message = f"{api_name} error: {error_json['message']}"
        except (json.JSONDecodeError, ValueError):
            # If the error is not JSON, use the error text directly
            pass
        
        self.logger.error(error_message)
        
        # Raise appropriate exception based on status code
        if status_code == 401:
            raise Exception(f"Authentication failed: API key invalid or expired")
        elif status_code == 429:
            raise Exception(f"Request too many: Exceeded API rate limit")
        elif status_code == 400:
            raise Exception(f"Request invalid: {error_message}")
        elif status_code == 404:
            raise Exception(f"Resource not found: {error_message}")
        elif status_code == 500:
            raise Exception(f"Server error: {error_message}")
        else:
            raise Exception(error_message)
    
    async def _make_request_stream(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        api_name: str = "API",
        process_stream_response_func: Callable = None
    ) -> AsyncGenerator[Any, None]:
        """
        Send streaming HTTP request and process the response as a stream
        
        Args:
            url: Request URL
            payload: Request payload data
            headers: Request headers
            api_name: API name, used for error messages
            process_stream_response_func: Function to process streaming response
            
        Yields:
            Processed response content chunks
        """
        if not process_stream_response_func:
            raise ValueError("A function for processing stream responses must be provided")
            
        self._log_request_details(url, headers, payload)
        
        start_time = asyncio.get_event_loop().time()
        response_start_time = None
        
        try:
            # Create connector with appropriate SSL and timeout settings
            connector = aiohttp.TCPConnector(
                force_close=True,
                enable_cleanup_closed=True,
                limit=10,
                ssl=False,
                family=socket.AF_UNSPEC
            )
            
            timeout = self._create_timeout_config()
            
            # Create session and send request
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                self.logger.debug(f"Sending stream request to {url}")
                
                async with session.post(
                    url, 
                    json=payload, 
                    headers=headers,
                    proxy=self.proxy_url
                ) as response:
                    response_start_time = asyncio.get_event_loop().time()
                    elapsed_until_response = response_start_time - start_time
                    self.logger.debug(f"Received stream response: {response.status}, time: {elapsed_until_response:.2f}s")
                    
                    # Check for error status
                    if response.status != 200:
                        error_text = await response.text()
                        self.logger.error(f"Stream request error: HTTP {response.status}")
                        self._handle_api_error(response.status, error_text, api_name)
                    
                    # Process streaming response and yield results
                    self.logger.debug("Starting to process stream response...")
                    
                    async for content in process_stream_response_func(response):
                        yield content
                        
                    request_end_time = asyncio.get_event_loop().time()
                    total_elapsed = request_end_time - start_time
                    self.logger.debug(f"Stream request completed, total time: {total_elapsed:.2f}s")
                    
        except aiohttp.ClientConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            self.logger.error(error_msg)
            yield self._format_error_response(error_msg)
        except asyncio.TimeoutError:
            elapsed = "unknown"
            if start_time:
                elapsed = f"{asyncio.get_event_loop().time() - start_time:.2f}"
                
            error_msg = f"Request timeout: {elapsed}s"
            self.logger.error(error_msg)
            yield self._format_error_response(error_msg)
        except Exception as e:
            self.logger.error(f"Stream request error: {str(e)}")
            self.logger.error(f"Type: {type(e).__name__}")
            self.logger.error(f"Stack trace: {traceback.format_exc()}")
            yield self._format_error_response(f"Request error: {str(e)}")
    
    def _format_error_response(self, error_message: str) -> Dict[str, str]:
        """
        Format error response
        
        Args:
            error_message: Error message
            
        Returns:
            Formatted error response dictionary with 'error' key
        """
        # Return a dictionary with error key for consistent error handling
        return {"error": error_message}
    
    def _log_request_details(self, url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> None:
        """
        Log API request details
        
        Args:
            url: Request URL
            headers: Request headers
            payload: Request payload data
        """
        # Log request details at debug level
        self.logger.info(f"================================================")
        self.logger.info(f"Request URL: {url}")
        
        # Log headers without Authorization
        safe_headers = {k: v for k, v in headers.items() if k.lower() != "authorization"}
        self.logger.info(f"Request headers: {safe_headers}")
        
        # Log payload
        self.logger.info(f"Request content: {json.dumps(payload, ensure_ascii=False)}")
        self.logger.info(f"================================================")

    def _get_sanitized_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a sanitized copy of the payload with sensitive data removed
        
        Args:
            payload: Original payload
            
        Returns:
            Sanitized payload
        """
        if not payload:
            return {}
            
        # Create a deep copy to avoid modifying the original
        sanitized = json.loads(json.dumps(payload))
        
        # Handle messages array
        if "messages" in sanitized and isinstance(sanitized["messages"], list):
            for message in sanitized["messages"]:
                if isinstance(message, dict) and "content" in message:
                    if isinstance(message["content"], str) and len(message["content"]) > 50:
                        message["content"] = f"{message['content'][:50]}...[{len(message['content'])} characters]"
                    elif isinstance(message["content"], list):
                        for i, content_item in enumerate(message["content"]):
                            if isinstance(content_item, dict) and "text" in content_item:
                                if len(content_item["text"]) > 50:
                                    content_item["text"] = f"{content_item['text'][:50]}...[{len(content_item['text'])} characters]"
        
        # Handle prompt
        if "prompt" in sanitized and isinstance(sanitized["prompt"], str):
            if len(sanitized["prompt"]) > 50:
                sanitized["prompt"] = f"{sanitized['prompt'][:50]}...[{len(sanitized['prompt'])} characters]"
        
        return sanitized 