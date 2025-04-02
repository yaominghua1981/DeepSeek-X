#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import asyncio
import traceback
from typing import Dict, Any, List, Optional, Union

import uvicorn
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pathlib import Path

from utils.logger import get_logger
from utils.validate_apikey import validate_apikey
from config.config_manager import ConfigManager
from process.deepseek_x_processor import DeepSeekXProcessor

# Create logger
logger = get_logger("main")
logger.info("Application initialized")

# Initialize configuration manager
config_manager = ConfigManager()

# Validate proxy configuration
proxy_config = config_manager.get_proxy_config()
if proxy_config.get("enabled"):
    proxy_address = proxy_config.get("address", "")
    logger.info(f"Proxy: http://{proxy_address}")
else:
    logger.info("Proxy not enabled")

# Initialize FastAPI application
app = FastAPI(title="DeepSeek-X API", description="API for DeepSeek-X", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config_manager.get_cors_origins(),  # Get CORS origins from configuration
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Define API request models
class LoginRequest(BaseModel):
    token: str

class ConfigData(BaseModel):
    data: Dict[str, Any]

class ChatCompletionMessage(BaseModel):
    role: str
    content: Union[str, List[Dict[str, Any]]]

class ChatCompletionRequest(BaseModel):
    model: Optional[str] = "deepseek-chat-x"
    messages: List[ChatCompletionMessage]
    stream: Optional[bool] = False

# Define frontend directory
frontend_dir = "frontend"

# Frontend page routes - explicitly defined to handle GET requests for specific paths
@app.get("/")
async def serve_index():
    """Serve index page - no authentication required"""
    return FileResponse(os.path.join(frontend_dir, "index.html"))

@app.get("/login")
async def serve_login_page():
    """Serve login page - no authentication required"""
    return FileResponse(os.path.join(frontend_dir, "index.html"))

# Explicitly define static file routes
@app.get("/styles.css")
async def serve_css():
    """Serve CSS stylesheet"""
    return FileResponse(os.path.join(frontend_dir, "styles.css"))

@app.get("/app.js")
async def serve_js():
    """Serve JavaScript file"""
    return FileResponse(os.path.join(frontend_dir, "app.js"))

# Add favicon handler
@app.get("/favicon.ico")
async def serve_favicon():
    """Serve favicon icon"""
    favicon_path = os.path.join(frontend_dir, "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    return Response(status_code=404)

# API routes
@app.post("/")
async def welcome():
    return {"message": "Welcome to DeepSeek-X API"}

@app.post("/login")
async def login(request: LoginRequest):
    """Login validation endpoint"""
    try:
        valid_token = config_manager.get_system_api_key()
        
        if request.token == valid_token:
            return {"success": True, "token": valid_token}
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "Invalid token"}
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Server error"}
        )

@app.get("/api/config_get", dependencies=[Depends(validate_apikey)])
async def get_config():
    """Get current configuration"""
    try:
        # Load configuration from file
        config = config_manager.load_config()
        return {
            "success": True,
            "config": config
        }
    except Exception as e:
        logger.error(f"Failed to load configuration: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }, 500

@app.post("/api/config_save", dependencies=[Depends(validate_apikey)])
async def save_config(request: Request):
    """Configuration save endpoint"""
    try:
        # API Key validation handled through dependency injection
        data = await request.json()
        config_manager.save_config(data)
        return {"success": True}
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Error saving config"}
        )

@app.post("/v1/chat/completions", dependencies=[Depends(validate_apikey)])
async def chat_completions(request: Request):
    """OpenAI compatible interface: Chat completions endpoint"""
    try:
        # Parse JSON request
        request_data = await request.json()
        logger.info(f"Chat request: {str(request_data)[:100]}...")
        
        # Validate request data
        if "messages" not in request_data or not request_data["messages"]:
            logger.warning("Request missing messages field")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Messages field is missing or empty in request"}
            )
        
        # Delegate processing logic to DeepSeekXProcessor
        return await DeepSeekXProcessor.process(request_data)
    except json.JSONDecodeError:
        logger.error("JSON parsing error")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid JSON data"}
        )
    except HTTPException:
        # Directly re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": str(e)}
        )
    
@app.get("/v1/models", dependencies=[Depends(validate_apikey)])
async def list_models():
    try:
        # Call static method of DeepSeekXProcessor to get model list
        models = DeepSeekXProcessor.get_model_list()
        logger.info(f"Returning {len(models)} models")
        return {"object": "list", "data": models}
    except Exception as e:
        logger.error(f"Model list error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": str(e)}
        )

# Set static files - after all routes are defined
if os.path.exists(frontend_dir):
    # Mount static file directory to handle other routes not explicitly defined
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    logger.info(f"Frontend directory: {frontend_dir}")
else:
    logger.warning(f"Frontend directory not found: '{frontend_dir}'")

if __name__ == "__main__":
    # Handle command line arguments
    host = "0.0.0.0"
    port = 8000
    
    # Check if frontend directory exists
    if not os.path.exists(frontend_dir):
        logger.warning(f"Frontend directory {frontend_dir} not found, creating it...")
        os.makedirs(frontend_dir, exist_ok=True)
    
    # Log important information
    logger.info(f"Frontend directory: {frontend_dir}")
    
    # Mount static files for frontend
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
    
    # Start server
    logger.info("Starting server...")
    try:
        uvicorn.run(app, host=host, port=port)
    except KeyboardInterrupt:
        logger.info("User interrupted")
        sys.exit(0)
