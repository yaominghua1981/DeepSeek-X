import logging
import os
import json

def get_log_level_from_config():
    """
    Read log level from configuration file
    
    Returns:
        Log level constant (defaults to logging.INFO)
    """
    config_path = "config.json"
    log_level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as file:
                config = json.load(file)
                system_config = config.get("system", {})
                log_level_str = system_config.get("logLevel", "INFO")
                return log_level_map.get(log_level_str, logging.INFO)
        return logging.INFO
    except Exception:
        # Return default log level in case of any errors
        return logging.INFO

def parse_log_level(level_str):
    """
    Parse log level string to logging module constant
    
    Args:
        level_str: Log level string (e.g., "DEBUG", "INFO", etc.)
        
    Returns:
        Corresponding logging module constant
    """
    log_level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    return log_level_map.get(level_str, logging.INFO)

def get_logger(name, level=None):
    """
    Create and return a logger with specified name and level
    
    Args:
        name: Logger name
        level: Log level (defaults to level from config file if not specified)
        
    Returns:
        Logger object
    """
    # If level not specified, read from config file
    if level is None:
        level = get_log_level_from_config()
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Important: Prevent log propagation to avoid duplicate logs
    logger.propagate = False
    
    # Check if console handler already exists
    has_console_handler = False
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            has_console_handler = True
            break
    
    # Only add new handler if no console handler exists
    if not has_console_handler:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
        console_handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(console_handler)
    
    return logger 