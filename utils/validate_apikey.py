from typing import Optional, Any
from fastapi import Request, HTTPException, Header, Depends
from utils.logger import get_logger

# Create logger
logger = get_logger("api_key_validator")

def get_config_manager():
    """
    Dependency function to get ConfigManager instance
    
    Returns:
        ConfigManager: Configuration manager instance
    """
    # Delayed import of ConfigManager to avoid circular imports
    from config.config_manager import ConfigManager
    return ConfigManager()

async def validate_apikey(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
    config_manager: Any = Depends(get_config_manager)
) -> bool:
    """
    Validate if the API Key in the request is valid
    
    Supports two methods of providing the API Key:
    1. Through X-API-Key header
    2. Through Authorization header (Bearer token format)
    
    Args:
        request: FastAPI request object
        x_api_key: Value of X-API-Key header
        authorization: Value of Authorization header
        config_manager: Configuration manager instance
        
    Returns:
        bool: Returns True if API Key is valid
        
    Raises:
        HTTPException: If API Key is invalid or not provided
    """
    # Get system API Key from configuration
    system_api_key = config_manager.get_system_api_key()
    
    # Skip validation if system has no configured API Key
    if not system_api_key:
        logger.warning("System API Key not configured, skipping validation")
        return True
    
    # Extract API Key
    api_key = None
    
    # Check X-API-Key header
    if x_api_key:
        api_key = x_api_key
    
    # Check Authorization header
    elif authorization:
        if authorization.startswith("Bearer "):
            api_key = authorization.replace("Bearer ", "")
    
    # If no API Key provided
    if not api_key:
        logger.warning(f"Request did not provide API Key: {request.url}")
        raise HTTPException(
            status_code=401,
            detail="API Key is required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Validate the API Key
    if api_key != system_api_key:
        logger.warning(f"Invalid API Key: {api_key}")
        raise HTTPException(
            status_code=403,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    logger.debug("API Key validation successful")
    return True

async def verify_token(request: Request) -> str:
    """
    Dependency function to verify API Key and return it
    
    Args:
        request: FastAPI request object
        
    Returns:
        str: Valid API Key
    """
    await validate_apikey(request)
    return True 