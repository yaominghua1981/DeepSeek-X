import json
import os
import logging
from typing import Dict, List, Any, Optional, Tuple, Callable
from utils.logger import get_logger


class ConfigManager:
    """
    Manager class for reading configuration from config.json file.
    Provides access to all configuration fields through dedicated APIs.
    These parameters can be used as input for DeepSeekOpenAICompatibleCombinator.
    """
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize the ConfigManager with a path to the config file
        
        Args:
            config_path: Path to the config.json file (default: "config.json")
        """
        self.config_path = config_path
        self.config = self._parse_config_file()
        self.logger = get_logger("ConfigManager")
        # Callback functions
        self.callbacks = {}
    
    def set_callback(self, callback_name: str, callback_func: Callable) -> None:
        """
        Set callback function
        
        Args:
            callback_name: Callback function name
            callback_func: Callback function
        """
        self.callbacks[callback_name] = callback_func
    
    def get_callback(self, callback_name: str) -> Optional[Callable]:
        """
        Get callback function by name
        
        Args:
            callback_name: Callback function name
            
        Returns:
            Callback function if found, None otherwise
        """
        return self.callbacks.get(callback_name)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        Get default workflow configuration
        
        This configuration is used if configuration file is not found or cannot be parsed
        """
        return {
            "phase1_inference": {
                "step": [
                    {
                        "stream": True,
                        "retry_num": 0
                    },
                    {
                        "stream": False,
                        "retry_num": 0
                    }
                ]
            },
            "phase2_final": {
                "step": [
                    {
                        "stream": True,
                        "retry_num": 0
                    },
                    {
                        "stream": False,
                        "retry_num": 0
                    }
                ]
            }
        }
    
    def _handle_config_error(self, error: Exception) -> None:
        """
        Handle configuration error
        
        Args:
            error: Exception that occurred
        """
        try:
            # Try to parse JSON format errors
            if isinstance(error, json.JSONDecodeError):
                line_no = error.lineno
                col_no = error.colno
                self.logger.error(f"JSON parsing error at line {line_no}, column {col_no}: {error.msg}")
            else:
                self.logger.error(f"Unable to parse configuration file: {str(error)}, using default configuration")
            
            # Reset to default configuration on error
            self.config = self._get_default_config()
        except Exception as nested_error:
            # Handle any errors that might occur during error handling
            self.logger.error(f"Error handling configuration error: {str(nested_error)}")
            self.config = self._get_default_config()
    
    def _log_config_summary(self) -> None:
        """
        Log a summary of the current configuration
        """
        self.logger.info("Configuration Summary:")
        self.logger.info(f"  Composite Models: {len(self.get_composite_models())}")
        self.logger.info(f"  Inference Models: {len(self.get_inference_models())}")
        self.logger.info(f"  Target Models: {len(self.get_target_models())}")
        self.logger.info(f"  Proxy Enabled: {self.is_proxy_enabled()}")
        self.logger.info(f"  Log Level: {self.get_log_level()}")
        self.logger.info(f"  Request Timeout: {self.get_request_timeout()}ms")
        
        # Log workflow configuration
        workflow_config = self.get_workflow_config()
        if workflow_config:
            self.logger.info("Workflow Configuration:")
            phase1_configs = self.get_phase1_configs()
            phase2_configs = self.get_phase2_configs()
            self.logger.info(f"  Phase1 Methods: {len(phase1_configs)}")
            self.logger.info(f"  Phase2 Methods: {len(phase2_configs)}")
    
    def reload(self) -> None:
        """Reload configuration from disk"""
        self.logger.info("Reloading configuration")
        self.config = self._parse_config_file()
        self._log_config_summary()
    
    def _parse_config_file(self) -> Dict[str, Any]:
        """
        Parse the configuration file and return its contents
        
        Returns:
            Dictionary containing the configuration
        """
        try:
            if not os.path.exists(self.config_path):
                raise FileNotFoundError(f"Config file not found: {self.config_path}")
            
            with open(self.config_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {str(e)}")
        except Exception as e:
            raise Exception(f"Error loading config: {str(e)}")
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from the config file
        
        Returns:
            Dictionary containing the configuration
        """
        self.config = self._parse_config_file()
        self.logger.info(f"Configuration loaded from {self.config_path}")
        return self.config
    
    def save_config(self, config: Dict[str, Any]) -> None:
        """
        Save configuration to the config file
        
        Args:
            config: Configuration dictionary to save
        
        Raises:
            Exception: If an error occurs during saving
        """
        try:
            with open(self.config_path, 'w', encoding='utf-8') as file:
                json.dump(config, file, indent=2, ensure_ascii=False)
            # Update current configuration in this instance
            self.config = config
            self.logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            self.logger.error(f"Error saving configuration file: {e}")
            raise Exception(f"Error saving config: {str(e)}")
    
    def get_composite_models(self) -> Dict[str, Dict[str, Any]]:
        """Get the dictionary of composite model configurations"""
        return self.config.get("composite", {})
    
    def get_active_composite_model(self) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Get the currently active composite model
        
        Returns:
            Tuple[str, Dict[str, Any]]: Tuple containing the model alias and model data, or None if not found
        """
        composite_models = self.get_composite_models()
        for alias, model_data in composite_models.items():
            if model_data.get("activated", False):
                self.logger.info(f"Found active composite model: {alias}")
                return (alias, model_data)
        
        # Return None if no active model is found
        self.logger.warning("No active composite model found")
        return None
    
    def get_composite_model_by_id(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific composite model configuration by model ID
        
        Args:
            model_id: Model ID to look for
            
        Returns:
            Model configuration or None if not found
        """
        # First check if alias directly matches (as we now use aliases as model IDs)
        composite_models = self.get_composite_models()
        if model_id in composite_models:
            return composite_models[model_id]
        
        # Backward compatibility: check model ID field
        for alias, model_data in composite_models.items():
            if model_data.get("Model ID") == model_id:
                return model_data
        
        # If no match is found, try matching with normalized aliases
        normalized_id = model_id.lower().replace(" ", "-")
        for alias, model_data in composite_models.items():
            normalized_alias = alias.lower().replace(" ", "-")
            if normalized_alias == normalized_id:
                return model_data
        
        return None
    
    def get_composite_model_by_alias(self, alias: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific composite model configuration by alias
        
        Args:
            alias: Model alias to look for
            
        Returns:
            Model configuration or None if not found
        """
        return self.get_composite_models().get(alias)
    
    def get_inference_models(self) -> Dict[str, Dict[str, Any]]:
        """Get the dictionary of inference model configurations"""
        return self.config.get("inference", {})
    
    def get_inference_model_by_id(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific inference model configuration by model ID
        
        Args:
            model_id: Model ID to look for
            
        Returns:
            Model configuration or None if not found
        """
        for model_data in self.get_inference_models().values():
            if model_data.get("Model ID") == model_id:
                return model_data
        return None
    
    def get_inference_model_by_alias(self, alias: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific inference model configuration by alias
        
        Args:
            alias: Model alias to look for
            
        Returns:
            Model configuration or None if not found
        """
        return self.get_inference_models().get(alias)
    
    def get_target_models(self) -> Dict[str, Dict[str, Any]]:
        """Get the dictionary of target model configurations"""
        return self.config.get("target", {})
    
    def get_target_model_by_id(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific target model configuration by model ID
        
        Args:
            model_id: Model ID to look for
            
        Returns:
            Model configuration or None if not found
        """
        for model_data in self.get_target_models().values():
            if model_data.get("Model ID") == model_id:
                return model_data
        return None
    
    def get_target_model_by_alias(self, alias: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific target model configuration by alias
        
        Args:
            alias: Model alias to look for
            
        Returns:
            Model configuration or None if not found
        """
        return self.get_target_models().get(alias)
    
    def get_proxy_config(self) -> Dict[str, Any]:
        """Get the proxy configuration"""
        return self.config.get("proxy", {"enabled": False, "address": ""})
    
    def get_proxy_address(self) -> str:
        """
        Get the proxy address with proper formatting
        
        Returns:
            Properly formatted proxy URL (with http:// prefix)
        """
        proxy_config = self.get_proxy_config()
        proxy_address = proxy_config.get("address", "")
        
        if proxy_address and not proxy_address.startswith(('http://', 'https://')):
            proxy_address = f"http://{proxy_address}"
        
        return proxy_address
    
    def is_proxy_enabled(self) -> bool:
        """Check if proxy is enabled"""
        proxy_config = self.get_proxy_config()
        return proxy_config.get("enabled", False)
    
    def get_system_config(self) -> Dict[str, Any]:
        """Get the system configuration"""
        return self.config.get("system", {})
    
    def get_cors_origins(self) -> List[str]:
        """Get the CORS allowed origins"""
        system_config = self.get_system_config()
        return system_config.get("cors", ["*"])
    
    def get_log_level(self) -> str:
        """Get the logging level"""
        system_config = self.get_system_config()
        return system_config.get("logLevel", "INFO")
    
    def get_system_api_key(self) -> str:
        """Get the system API key"""
        system_config = self.get_system_config()
        return system_config.get("apiKey", "")
    
    def get_request_timeout(self) -> int:
        """Get the request timeout from system configuration"""
        return self.config.get("system", {}).get("requestTimeout", 60000)
    
    def get_workflow_config(self) -> Dict[str, Any]:
        """
        Get the workflow configuration
        
        Returns:
            Dictionary containing the workflow configuration
        """
        return self.config.get("workflow", {})
    
    def get_phase1_configs(self) -> List[Dict[str, Any]]:
        """
        Get phase 1 method configurations
        
        Returns:
            List of phase 1 method configurations
        """
        phase1_configs = self.config.get("workflow", {}).get("phase1_inference", {}).get("step", [])
        if not phase1_configs:
            self.logger.warning("Phase1 configuration is empty")
            # Return default configuration if empty
            return {
                "phase1_inference": {
                    "step": [
                        {
                            "stream": True,
                            "retry_num": 0
                        },
                        {
                            "stream": False,
                            "retry_num": 0
                        }
                    ]
                }
            }.get("phase1_inference", {}).get("step", [])
        
        # Log configuration details
        self.logger.info(f"Phase1 configuration: {len(phase1_configs)} items")
        for i, config in enumerate(phase1_configs):
            stream_mode = "stream" if config.get("stream", True) else "non-stream"
            retries = config.get("retry_num", 0)
            timeout = config.get("timeout", 180000)
            self.logger.info(f"  Config {i+1}: {stream_mode}, retries={retries}, timeout={timeout}ms")
        
        return phase1_configs
    
    def get_phase2_configs(self) -> List[Dict[str, Any]]:
        """
        Get phase 2 method configurations
        
        Returns:
            List of phase 2 method configurations
        """
        phase2_configs = self.config.get("workflow", {}).get("phase2_final", {}).get("step", [])
        if not phase2_configs:
            self.logger.warning("Phase2 configuration is empty")
            # Return default configuration if empty
            return {
                "phase2_final": {
                    "step": [
                        {
                            "stream": True,
                            "retry_num": 0
                        },
                        {
                            "stream": False,
                            "retry_num": 0
                        }
                    ]
                }
            }.get("phase2_final", {}).get("step", [])
        
        # Log configuration details
        self.logger.info(f"Phase2 configuration: {len(phase2_configs)} items")
        for i, config in enumerate(phase2_configs):
            stream_mode = "stream" if config.get("stream", True) else "non-stream"
            retries = config.get("retry_num", 0)
            timeout = config.get("timeout", 180000)
            self.logger.info(f"  Config {i+1}: {stream_mode}, retries={retries}, timeout={timeout}ms")
        
        return phase2_configs
    
    def get_phase_timeout(self, phase: str, index: int = 0, default: int = 180000) -> int:
        """
        Get timeout for a specific phase and method
        
        Args:
            phase: Phase name ("phase1_inference" or "phase2_final")
            index: Method index in the phase configuration
            default: Default timeout to return if not configured
            
        Returns:
            Timeout in milliseconds
        """
        phase_configs = self.config.get("workflow", {}).get(phase, {}).get("step", [])
        if not phase_configs or len(phase_configs) <= index:
            return default
        
        method_config = phase_configs[index]
        return method_config.get("timeout", default)
    
    def get_phase_retries(self, phase: str, index: int = 0, default: int = 0) -> int:
        """
        Get retry count for a specific phase and method
        
        Args:
            phase: Phase name ("phase1_inference" or "phase2_final")
            index: Method index in the phase configuration
            default: Default retry count to return if not configured
            
        Returns:
            Retry count
        """
        phase_configs = self.config.get("workflow", {}).get(phase, {}).get("step", [])
        if not phase_configs or len(phase_configs) <= index:
            return default
        
        method_config = phase_configs[index]
        return method_config.get("retry_num", default)
    
    def get_active_config_for_chat_manager(self) -> Dict[str, Any]:
        """
        Get the currently active composite model configuration for initializing DeepSeekOpenAICompatibleCombinator
        
        Returns:
            Configuration dictionary for DeepSeekOpenAICompatibleCombinator
            
        Raises:
            ValueError: If no active composite model or relevant configuration is found
        """
        # Get the active composite model
        active_model = self.get_active_composite_model()
        if not active_model:
            raise ValueError("No active composite model found, please activate a composite model in the configuration")
        
        alias, composite_model = active_model
        
        # Get inference model alias and target model alias
        inference_model_alias = composite_model.get("Inference Model", "")
        target_model_alias = composite_model.get("Target Model", "")
        
        if not inference_model_alias:
            raise ValueError(f"Composite model '{alias}' does not specify an inference model")
        
        if not target_model_alias:
            raise ValueError(f"Composite model '{alias}' does not specify a target model")
        
        self.logger.info(f"Using inference model: {inference_model_alias}, target model: {target_model_alias}")
        
        # Get corresponding alias model configurations
        inference_model = self.get_inference_model_by_alias(inference_model_alias)
        target_model = self.get_target_model_by_alias(target_model_alias)
        
        # If alias lookup fails, try ID lookup (backward compatibility)
        if not inference_model:
            inference_model = self.get_inference_model_by_id(inference_model_alias)
        
        if not target_model:
            target_model = self.get_target_model_by_id(target_model_alias)
        
        if not inference_model:
            raise ValueError(f"Inference model not found: {inference_model_alias}")
        
        if not target_model:
            raise ValueError(f"Target model not found: {target_model_alias}")
        
        # Get logging level
        log_level_str = self.get_log_level()
        log_level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        log_level = log_level_map.get(log_level_str, logging.INFO)
        
        # Convert request timeout (from milliseconds to seconds)
        request_timeout = self.get_request_timeout() / 1000
        
        # Get proxy settings
        proxy_address = self.get_proxy_address() if self.is_proxy_enabled() else None
        
        # Build complete API URL
        inference_base_url = inference_model.get('Base URL', '')
        inference_api_path = inference_model.get('API Path', '')
        
        target_base_url = target_model.get('Base URL', '')
        target_api_path = target_model.get('API Path', '')
        
        # Create DeepSeekOpenAICompatibleCombinator configuration
        config = {
            "deepseek_model": inference_model.get("Model ID", ""),
            "openai_compatible_model": target_model.get("Model ID", ""),
            "deepseek_api_key": inference_model.get("API Key", ""),
            "openai_compatible_api_key": target_model.get("API Key", ""),
            "deepseek_base_url": inference_base_url,
            "openai_compatible_base_url": target_base_url,
            "request_timeout": request_timeout,
            "proxy_url": proxy_address,
            "deepseek_api_path": inference_api_path,
            "openai_compatible_api_path": target_api_path
        }
        
        return config
    
    def get_deepseek_x_config(self, inference_model_id: str, target_model_id: str) -> Dict[str, Any]:
        """
        Get a configuration dictionary suitable for initializing DeepSeekOpenAICompatibleCombinator
        
        Args:
            inference_model_id: ID of the inference model to use
            target_model_id: ID of the target model to use
            
        Returns:
            Configuration dictionary for DeepSeekOpenAICompatibleCombinator
        """
        inference_model = self.get_inference_model_by_id(inference_model_id)
        target_model = self.get_target_model_by_id(target_model_id)
        
        if not inference_model:
            raise ValueError(f"Inference model not found: {inference_model_id}")
        if not target_model:
            raise ValueError(f"Target model not found: {target_model_id}")
        
        # Parse logging level
        log_level_str = self.get_log_level()
        log_level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        log_level = log_level_map.get(log_level_str, logging.INFO)
        
        # Get request timeout (convert from milliseconds to seconds)
        request_timeout = self.get_request_timeout() / 1000
        
        # Get proxy settings
        proxy_address = self.get_proxy_address() if self.is_proxy_enabled() else None
        
        # Build complete API URL
        inference_base_url = inference_model.get('Base URL', '')
        inference_api_path = inference_model.get('API Path', '')
        
        # Similarly handle target model URL
        target_base_url = target_model.get('Base URL', '')
        target_api_path = target_model.get('API Path', '')
        
        config = {
            "deepseek_api_key": inference_model.get("API Key", ""),
            "openai_compatible_api_key": target_model.get("API Key", ""),
            "deepseek_base_url": inference_base_url,
            "openai_compatible_base_url": target_base_url,
            "deepseek_model": inference_model.get("Model ID", ""),
            "openai_compatible_model": target_model.get("Model ID", ""),
            "logging_level": log_level,
            "request_timeout": request_timeout,
            "proxy_url": proxy_address,
            "deepseek_api_path": inference_model.get("API Path", ""),
            "openai_compatible_api_path": target_model.get("API Path", "")
        }
        
        return config
    
    def find_composite_config(self, composite_model_id: str) -> Dict[str, Any]:
        """
        Find the inference and target models for a composite model ID
        and return configuration for DeepSeekOpenAICompatibleCombinator
        
        Args:
            composite_model_id: ID of the composite model
            
        Returns:
            Configuration dictionary for DeepSeekOpenAICompatibleCombinator
        """
        composite_model = self.get_composite_model_by_id(composite_model_id)
        if not composite_model:
            raise ValueError(f"Composite model not found: {composite_model_id}")
        
        # Get inference model alias and target model alias
        inference_model_alias = composite_model.get("Inference Model", "")
        target_model_alias = composite_model.get("Target Model", "")
        
        # Get corresponding alias model configurations
        inference_model = self.get_inference_model_by_alias(inference_model_alias)
        target_model = self.get_target_model_by_alias(target_model_alias)
        
        # If alias lookup fails, try ID lookup (backward compatibility)
        if not inference_model:
            inference_model = self.get_inference_model_by_id(inference_model_alias)
        
        if not target_model:
            target_model = self.get_target_model_by_id(target_model_alias)
        
        if not inference_model:
            raise ValueError(f"Inference model not found: {inference_model_alias}")
        if not target_model:
            raise ValueError(f"Target model not found: {target_model_alias}")
        
        # Get inference model ID and target model ID
        inference_model_id = inference_model.get("Model ID", "")
        target_model_id = target_model.get("Model ID", "")
        
        return self.get_deepseek_x_config(inference_model_id, target_model_id)
    
    def get_api_base_url(self, model_id: str) -> str:
        """
        Get the API base URL for the specified model
        
        Args:
            model_id: Model ID
            
        Returns:
            API base URL for the model
        """
        # Search in inference models
        inference_models = self.get_inference_models()
        for alias, model_data in inference_models.items():
            if model_data.get("Model ID", "").lower() == model_id.lower():
                base_url = model_data.get("Base URL", "")
                self.logger.debug(f"Found API base URL in inference model: {base_url}")
                return base_url
        
        # Search in target models
        target_models = self.get_target_models()
        for alias, model_data in target_models.items():
            if model_data.get("Model ID", "").lower() == model_id.lower():
                base_url = model_data.get("Base URL", "")
                self.logger.debug(f"Found API base URL in target model: {base_url}")
                return base_url
                
        # If no matching model ID is found, log a warning and return empty string
        self.logger.warning(f"Could not find API base URL for model {model_id}")
        return ""
    
    def get_api_path(self, model_id: str) -> str:
        """
        Get the API path for the specified model
        
        Args:
            model_id: Model ID
            
        Returns:
            API path for the model
        """
        # Search in inference models
        inference_models = self.get_inference_models()
        for alias, model_data in inference_models.items():
            if model_data.get("模型ID", "").lower() == model_id.lower():
                api_path = model_data.get("API请求地址", "")
                self.logger.debug(f"Found API path in inference model: {api_path}")
                return api_path
        
        # Search in target models
        target_models = self.get_target_models()
        for alias, model_data in target_models.items():
            if model_data.get("模型ID", "").lower() == model_id.lower():
                api_path = model_data.get("API请求地址", "")
                self.logger.debug(f"Found API path in target model: {api_path}")
                return api_path
                
        # If no matching model ID is found, log a warning and return default path
        self.logger.warning(f"Could not find API path for model {model_id}, using default path: v1/chat/completions")
        return "v1/chat/completions"

# Create ConfigManager global instance
config_manager = ConfigManager()