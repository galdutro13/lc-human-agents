import os
import yaml
from abc import ABC, abstractmethod
from typing import Any, Dict

from source.rag.config.models import RAGConfig


class ConfigurationStrategy(ABC):
    """
    Strategy interface for loading RAG configurations.
    Defines a common interface for all configuration loading strategies.
    """

    @abstractmethod
    def load_configuration(self, config_path: str) -> RAGConfig:
        """
        Loads configuration from the specified path.

        Args:
            config_path: Path to the configuration file

        Returns:
            RAGConfig object with the loaded configuration

        Raises:
            FileNotFoundError: If the configuration file is not found
            ValueError: If there's an error processing the configuration
        """
        pass


class YAMLConfigurationStrategy(ConfigurationStrategy):
    """
    Implementation of ConfigurationStrategy for YAML files.
    Loads and validates RAG configuration from YAML files.
    """

    def load_configuration(self, config_path: str) -> RAGConfig:
        """
        Loads configuration from a YAML file.

        Args:
            config_path: Path to the YAML configuration file

        Returns:
            RAGConfig object with the loaded configuration

        Raises:
            FileNotFoundError: If the configuration file is not found
            ValueError: If there's an error processing the configuration
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found at {config_path}")

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)

            # Validate and convert data using the Pydantic model
            config = RAGConfig(**config_data)
            print(f"Configuration loaded successfully: {len(config.datasources)} datasources defined")

            if config.external_tools:
                print(f"External tools defined: {len(config.external_tools)}")

            return config

        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error processing configuration: {str(e)}")


class ConfigurationManager:
    """
    Manages RAG configuration loading and access.
    Uses the Strategy pattern to support different configuration sources.
    """

    def __init__(self, strategy: ConfigurationStrategy):
        """
        Initializes the ConfigurationManager with a specific strategy.

        Args:
            strategy: A ConfigurationStrategy implementation for loading configurations
        """
        if not isinstance(strategy, ConfigurationStrategy):
            raise TypeError("Strategy must be an instance of ConfigurationStrategy")

        self._strategy = strategy
        self._config = None

    def load(self, config_path: str) -> None:
        """
        Loads the configuration using the provided strategy.

        Args:
            config_path: Path to the configuration file

        Raises:
            FileNotFoundError: If the configuration file is not found
            ValueError: If there's an error processing the configuration
        """
        self._config = self._strategy.load_configuration(config_path)

    @property
    def config(self) -> RAGConfig:
        """
        Gets the loaded configuration.

        Returns:
            The loaded RAGConfig object

        Raises:
            ValueError: If the configuration has not been loaded
        """
        if self._config is None:
            raise ValueError("Configuration not loaded. Call load() first.")
        return self._config