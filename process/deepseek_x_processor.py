import json
import traceback
import time
import asyncio
from typing import Dict, List, Any, Union
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse

from utils.logger import get_logger
from config.config_manager import ConfigManager
from combinator.deepseek_openaicompatible_combinator import DeepSeekOpenAICompatibleCombinator

class DeepSeekXProcessor:
    logger = get_logger("DeepSeekXProcessor")
    
    @staticmethod
    async def process(body: Dict[str, Any]) -> Union[Dict[str, Any], StreamingResponse]:
        """
        Process chat requests and determine whether to use streaming or non-streaming responses
        
        Args:
            body: Request body containing message content and model ID
            
        Returns:
            Dict or StreamingResponse: Different result types based on request mode
        """
        logger = DeepSeekXProcessor.logger
        
        try:
            # Extract request parameters
            model_id = body.get("model", "")
            messages = body.get("messages", [])
            stream = body.get("stream", False)
            
            logger.info(f"Request: {model_id}, stream={stream}")
            
            # Handle empty message list
            if not messages:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "Empty message list"}
                )
            
            # Extract prompt text and system message
            user_message, system_message, assistant_message = DeepSeekXProcessor._extract_prompt_and_system_message(messages)
            
            if not user_message:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "Invalid user message"}
                )
            
            logger.info(f"Prompt: {len(user_message)} characters")
            
            # Get current active model configuration
            config_manager = ConfigManager()
                        
            # Get active composite model configuration
            try:
                composite_config = config_manager.get_active_config_for_chat_manager()
                logger.info(f"Model: {composite_config.get('deepseek_model', '')}->{composite_config.get('openai_compatible_model', '')}")
                
                # Validate API keys
                inference_api_key = composite_config.get('deepseek_api_key', '')
                target_api_key = composite_config.get('openai_compatible_api_key', '')
                
                # Check for missing or placeholder API keys
                if not inference_api_key or inference_api_key in ["YOUR_INFERENCE_API_KEY_HERE"]:
                    logger.error("Missing or invalid Inference Model API key")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={"error": "Missing or invalid Inference Model API key. Please configure your inference model API key in the settings."}
                    )
                
                if not target_api_key or target_api_key in ["YOUR_GEMINI_API_KEY_HERE", "YOUR_SYSTEM_API_KEY_HERE"]:
                    logger.error("Missing or invalid Target Model API key")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={"error": "Missing or invalid Target Model API key. Please configure your target model API key in the settings."}
                    )
                
            except ValueError as e:
                logger.error(f"Configuration error: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={"error": f"Configuration error: {str(e)}. Please check your model configuration."}
                )
            
            # Create combinator instance
            combinator = DeepSeekOpenAICompatibleCombinator(
                config_manager=config_manager
            )
            
            # Call the DeepSeekOpenAICompatibleCombinator process method to handle the request
            try:
                # Determine processing method based on stream parameter
                if stream:
                    logger.info("Stream mode")
                    return DeepSeekXProcessor._handle_stream_request(
                        combinator=combinator,
                        user_message=user_message,
                        system_message=system_message,
                        assistant_message=assistant_message,
                        model_id=model_id
                    )
                else:
                    logger.info("Non-stream mode")
                    return await DeepSeekXProcessor._handle_nonstream_request(
                        combinator=combinator,
                        user_message=user_message,
                        system_message=system_message,
                        assistant_message=assistant_message,
                        model_id=model_id
                    )
            except Exception as e:
                error_message = str(e)
                if "API key" in error_message.lower() or "authentication" in error_message.lower() or "authorization" in error_message.lower():
                    logger.error(f"API authentication error: {error_message}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail={"error": f"API authentication failed: {error_message}. Please check your API keys in configuration."}
                    )
                
                logger.error(f"Workflow error: {error_message}")
                logger.error(traceback.format_exc())
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={"error": f"Workflow failed: {error_message}"}
                )
                
        except HTTPException:
            # Re-raise HTTP exceptions directly
            raise
        except Exception as e:
            logger.error(f"Processing error: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": str(e)}
            )
    
    @staticmethod
    def get_model_list() -> List[Dict[str, Any]]:
        """
        Get available model list, convert composite model list to OpenAI API compatible format

        Returns:
            List[Dict[str, Any]]: Model list (OpenAI API format)
        """
        logger = DeepSeekXProcessor.logger
        logger.info("Getting model list")
        
        models = []
        # Get model configuration
        config_manager = ConfigManager()
        
        # Get composite model list from configuration
        composite_models = config_manager.get_composite_models()
        
        # Convert each composite model to OpenAI API compatible format
        for alias, model_data in composite_models.items():
            model_id = "DeepSeek-X"
            
            # Inference model and target model information
            inference_model_alias = model_data.get("Inference Model", "")
            target_model_alias = model_data.get("Target Model", "")
            
            # Create OpenAI API compatible model data
            model_info = {
                "id": model_id,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "DeepSeek-X",
                "permission": [{
                    "id": f"modelperm-{model_id}",
                    "object": "model_permission",
                    "created": int(time.time()),
                    "allow_create_engine": False,
                    "allow_sampling": True,
                    "allow_logprobs": True,
                    "allow_search_indices": False,
                    "allow_view": True,
                    "allow_fine_tuning": False,
                    "organization": "*",
                    "group": None,
                    "is_blocking": False
                }],
                "root": model_id,
                "parent": None,
                "metadata": {
                    "display_name": alias,
                    "inference_model": inference_model_alias,
                    "target_model": target_model_alias
                }
            }
            
            models.append(model_info)
            logger.debug(f"Model: {alias} (ID: {model_id})")
        
        if not models:
            logger.warning("No models found")
        else:
            logger.info(f"Found {len(models)} models")
        
        return models

    @staticmethod
    def _extract_prompt_and_system_message(messages: List[Any]) -> tuple:
        """
        Extract user message, system message, and assistant message from message list
        
        Args:
            messages: Message list (messages in dictionary format)
            
        Returns:
            tuple: (user_message, system_message, assistant_message)
        """
        logger = DeepSeekXProcessor.logger
        user_message = ""
        system_message = ""
        assistant_message = ""
        
        # Check if message list is empty
        if not messages:
            return user_message, system_message, assistant_message
        
        # Iterate through all messages, extract role and content
        for msg in messages:
            try:
                role = msg.get("role", "").lower() if isinstance(msg, dict) else ""
                content = msg.get("content", "") if isinstance(msg, dict) else ""
                
                # Handle different content formats
                if isinstance(content, list):
                    # For content in array format (e.g., multimodal content)
                    text_parts = []
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text_parts.append(part.get("text", ""))
                    content = " ".join(text_parts)
                    
                # Process different roles
                if role == "system":
                    system_message = content
                    logger.debug(f"System: {len(system_message)} characters")
                elif role == "user":
                    if user_message:
                        user_message += "\n\n"
                    user_message += content
                    logger.debug(f"User: {len(content)} characters")
                elif role in ["assistant", "model"]:
                    if assistant_message:
                        assistant_message += "\n\n"
                    assistant_message += content
                    logger.debug(f"Assistant: {len(content)} characters")
                else:
                    logger.warning(f"Unknown role: {role}")
            except Exception as e:
                logger.warning(f"Message error: {str(e)}")
        
        return user_message, system_message, assistant_message
        
    @staticmethod
    def _handle_stream_request(
        combinator: DeepSeekOpenAICompatibleCombinator,
        user_message: str,
        system_message: str,
        assistant_message: str,
        model_id: str
    ) -> StreamingResponse:
        """
        Handle streaming chat request
        
        Args:
            combinator: Model combinator instance for processing
            user_message: User's question or request
            system_message: System message that guides the model
            assistant_message: Optional assistant message for context
            model_id: Model ID
            
        Returns:
            StreamingResponse: Server-sent events response
        """
        logger = DeepSeekXProcessor.logger
        logger.info("Starting stream request:")
        
        # Initialize state variables
        reasoning_started = False
        summary_started = False
        reasoning_content = ""
        final_content = ""
        
        async def generate_stream_response():
            nonlocal reasoning_started, summary_started, reasoning_content, final_content
            
            try:
                # Create unique ID and timestamp for SSE response
                response_id = f"chatcmpl-{int(asyncio.get_event_loop().time()*1000)}"
                created_time = int(asyncio.get_event_loop().time())
                
                # Process request using combinator
                async for chunk in combinator.process_stream(
                    user_message=user_message,
                    system_message=system_message
                ):
                    try:
                        logger.debug(f"Received chunk: {chunk}")
                        
                        # Process dictionary type chunk
                        if isinstance(chunk, dict):
                            result_type = chunk.get("type", "")
                            content = chunk.get("content", "")
                            
                            if result_type == "reasoning":
                                # Update reasoning content
                                reasoning_content += content
                                if not reasoning_started:
                                    reasoning_started = True
                                
                                # Build OpenAI compatible SSE response format
                                sse_data = {
                                    "id": response_id,
                                    "object": "chat.completion.chunk",
                                    "created": created_time,
                                    "model": model_id,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {
                                                "role": "assistant",
                                                "reasoning_content": content,  # Send only the new content
                                                "content": ""
                                            },
                                            "finish_reason": None
                                        }
                                    ]
                                }
                                # Add debug logging
                                logger.debug(f"Yielding reasoning chunk: {content}")
                                yield f"data: {json.dumps(sse_data)}\n\n"
                            
                            elif result_type == "reasoning_end":
                                if reasoning_started:
                                    # Send final reasoning content
                                    sse_data = {
                                        "id": response_id,
                                        "object": "chat.completion.chunk",
                                        "created": created_time,
                                        "model": model_id,
                                        "choices": [
                                            {
                                                "index": 0,
                                                "delta": {
                                                    "role": "assistant",
                                                    "reasoning_content": "\n",
                                                    "content": ""
                                                },
                                                "finish_reason": None
                                            }
                                        ]
                                    }
                                    # Add debug logging
                                    logger.debug("Yielding reasoning end chunk")
                                    yield f"data: {json.dumps(sse_data)}\n\n"
                                    # Reset flag
                                    reasoning_started = False
                            
                            elif result_type == "summary":
                                # If this is the first summary chunk, add "Final answer:" prefix
                                if not summary_started:
                                    # First send a newline
                                    newline_data = {
                                        "id": response_id,
                                        "object": "chat.completion.chunk",
                                        "created": created_time,
                                        "model": model_id,
                                        "choices": [
                                            {
                                                "index": 0,
                                                "delta": {
                                                    "role": "assistant",
                                                    "content": "Final answer:\n"
                                                },
                                                "finish_reason": None
                                            }
                                        ]
                                    }
                                    # Add debug logging
                                    logger.debug("Yielding summary start chunk")
                                    yield f"data: {json.dumps(newline_data)}\n\n"
                                    summary_started = True
                                
                                # Update final content
                                final_content += content
                                
                                # Build OpenAI compatible SSE response format
                                sse_data = {
                                    "id": response_id,
                                    "object": "chat.completion.chunk",
                                    "created": created_time,
                                    "model": model_id,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {
                                                "role": "assistant",
                                                "content": content  # Send only the new content
                                            },
                                            "finish_reason": None
                                        }
                                    ]
                                }
                                # Add debug logging
                                logger.debug(f"Yielding summary chunk: {content[:30]}...")
                                yield f"data: {json.dumps(sse_data)}\n\n"
                            
                            elif result_type == "summary_end":
                                # End summary
                                if summary_started:
                                    # Reset flag
                                    summary_started = False
                                
                                # Send completion signal
                                sse_data = {
                                    "id": response_id,
                                    "object": "chat.completion.chunk",
                                    "created": created_time,
                                    "model": model_id,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {},
                                            "finish_reason": "stop"
                                        }
                                    ]
                                }
                                yield f"data: {json.dumps(sse_data)}\n\n"
                                yield "data: [DONE]\n\n"
                            
                            elif result_type == "error":
                                error_content = chunk.get("content", "")
                                error_phase = chunk.get("phase", "unknown")
                                
                                # If this is a phase1 error and indicates switching methods
                                if error_phase.startswith("phase1") and "switching" in error_content.lower():
                                    if reasoning_started:
                                        # End current reasoning block
                                        sse_data = {
                                            "id": response_id,
                                            "object": "chat.completion.chunk",
                                            "created": created_time,
                                            "model": model_id,
                                            "choices": [
                                                {
                                                    "index": 0,
                                                    "delta": {
                                                        "role": "assistant",
                                                        "content": "Switching processing method...\n"
                                                    },
                                                    "finish_reason": None
                                                }
                                            ]
                                        }
                                        yield f"data: {json.dumps(sse_data)}\n\n"
                                        reasoning_started = False
                                else:
                                    # For other errors, show friendly message
                                    friendly_error = "Encountered some issues while processing the request, trying alternative methods..."
                                    sse_data = {
                                        "id": response_id,
                                        "object": "chat.completion.chunk",
                                        "created": created_time,
                                        "model": model_id,
                                        "choices": [
                                            {
                                                "index": 0,
                                                "delta": {
                                                    "role": "assistant",
                                                    "content": friendly_error
                                                },
                                                "finish_reason": None
                                            }
                                        ]
                                    }
                                    yield f"data: {json.dumps(sse_data)}\n\n"
                            
                            elif result_type == "workflow_complete":
                                # Handle workflow completion event
                                success = chunk.get("success", False)
                                workflow_result = chunk.get("result")
                                
                                logger.info(f"Workflow completed: success={success}")
                                
                                # Ensure all flags are reset
                                reasoning_started = False
                                summary_started = False
                                
                                # Send final completion signal
                                sse_data = {
                                    "id": response_id,
                                    "object": "chat.completion.chunk",
                                    "created": created_time,
                                    "model": model_id,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {},
                                            "finish_reason": "stop"
                                        }
                                    ]
                                }
                                yield f"data: {json.dumps(sse_data)}\n\n"
                                yield "data: [DONE]\n\n"
                        
                        # Process string type chunk
                        elif isinstance(chunk, str):
                            logger.info(f"Received string chunk, length: {len(chunk)}")
                            
                            # Check if content is empty or too short
                            if not chunk.strip():
                                logger.warning("Received empty string chunk, skipping")
                                continue
                                
                            if len(chunk.strip()) < 5:
                                logger.warning(f"Received very short string chunk: '{chunk}', length: {len(chunk.strip())}")
                            
                            # Build OpenAI compatible SSE response format
                            sse_data = {
                                "id": response_id,
                                "object": "chat.completion.chunk",
                                "created": created_time,
                                "model": model_id,
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {
                                            "role": "assistant",
                                            "content": chunk
                                        },
                                        "finish_reason": None
                                    }
                                ]
                            }
                            yield f"data: {json.dumps(sse_data)}\n\n"
                            
                    except Exception as e:
                        logger.error(f"Error processing stream chunk: {str(e)}")
                        error_chunk = {
                            "id": "chatcmpl-error",
                            "object": "chat.completion.chunk",
                            "created": created_time,
                            "model": model_id,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {
                                        "content": f"Error processing stream chunk: {str(e)}"
                                    },
                                    "finish_reason": "error"
                                }
                            ]
                        }
                        yield f"data: {json.dumps(error_chunk)}\n\n"
                        yield "data: [DONE]\n\n"
                        
            except Exception as e:
                # Send error information
                logger.error(f"Error processing stream request: {str(e)}")
                logger.error(traceback.format_exc())
                
                error_chunk = {
                    "id": "chatcmpl-error",
                    "object": "chat.completion.chunk",
                    "created": created_time,
                    "model": model_id,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "content": f"Error processing request: {str(e)}"
                            },
                            "finish_reason": "error"
                        }
                    ]
                }
                yield f"data: {json.dumps(error_chunk)}\n\n"
                yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate_stream_response(),
            media_type="text/event-stream"
        )
    
    @staticmethod
    async def _handle_nonstream_request(
        combinator: DeepSeekOpenAICompatibleCombinator,
        user_message: str,
        system_message: str,
        assistant_message: str,
        model_id: str
    ) -> Dict[str, Any]:
        """
        Handle non-streaming chat request
        
        Args:
            combinator: Model combinator instance for processing
            user_message: User's question or request
            system_message: System message that guides the model
            assistant_message: Optional assistant message for context
            model_id: Model ID
            
        Returns:
            Dict[str, Any]: OpenAI API compatible response dictionary
        """
        logger = DeepSeekXProcessor.logger
        logger.info("Starting non-stream request:")

        try:
            # Track events for debugging
            result = await combinator.process_nonstream(
                user_message=user_message,
                system_message=system_message
            )
            
            if result.status_code == 200:
                final_content = result.content
                
                # Log content length
                if not final_content:
                    logger.warning("No content returned")
                else:
                    logger.info(f"Completed: {len(final_content)} characters")
                
                # Create OpenAI API compatible response
                request_id = f"chatcmpl-{int(time.time() * 1000)}"
                created_timestamp = int(time.time())
                
                def generate_nonstream_response():
                    """
                    Generate non-streaming response with reasoning and final content
                    """
                    # Extract reasoning and final content
                    reasoning_content = ""
                    final_answer = ""
                    
                    # Split content by "Final answer:" if it exists
                    if "Final answer:" in final_content:
                        parts = final_content.split("Final answer:", 1)
                        reasoning_content = parts[0].strip()
                        final_answer = parts[1].strip()
                    else:
                        # If no "Final answer:" marker, treat all content as final answer
                        final_answer = final_content.strip()
                    
                    # Create response structure
                    response = {
                        "id": request_id,
                        "object": "chat.completion",
                        "created": created_timestamp,
                        "model": model_id,
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "reasoning_content": reasoning_content,
                                    "content": final_answer
                                },
                                "finish_reason": "stop"
                            }
                        ],
                        "usage": {
                            "prompt_tokens": result.prompt_tokens or -1,
                            "completion_tokens": result.completion_tokens or -1,
                            "total_tokens": (result.prompt_tokens or 0) + (result.completion_tokens or 0)
                        }
                    }
                    
                    return response
                
                return generate_nonstream_response()
            else:
                # If there's an error, raise HTTPException
                error_message = f"Workflow error: {result.error or 'Unknown error'}"
                logger.error(error_message)
                
                raise HTTPException(
                    status_code=result.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={"error": error_message}
                )
                
        except Exception as e:
            logger.error(f"Non-stream request error: {str(e)}")
            logger.error(traceback.format_exc())
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": str(e)}
            )