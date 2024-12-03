import unittest
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from source.prompt_manager.base import (
    SystemPromptStrategy,
    DefaultSystemPromptStrategy,
    AggressiveSystemPromptStrategy,
    CustomSystemPromptStrategy,
    SystemPromptGenerator
)

from source.prompt_manager.constantes import template_padrao, template_agressivo

import unittest
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

template_default = template_padrao
template_aggressive = template_agressivo

class TestPromptGenerators(unittest.TestCase):
    def test_default_prompt_generator(self):
        """Test that DefaultPromptGenerator generates the correct prompt."""
        strategy = DefaultSystemPromptStrategy()
        prompt = strategy.generate_prompt()
        self.assertIsInstance(prompt, ChatPromptTemplate)
        self.assertEqual(prompt.messages[0].prompt.template, template_default)
        self.assertEqual(prompt.messages[1].variable_name, "messages")

    def test_aggressive_prompt_generator(self):
        """Test that AggressivePromptGenerator generates the correct prompt."""
        strategy = AggressiveSystemPromptStrategy()
        prompt = strategy.generate_prompt()
        self.assertIsInstance(prompt, ChatPromptTemplate)
        self.assertEqual(prompt.messages[0].prompt.template, template_aggressive)
        self.assertEqual(prompt.messages[1].variable_name, "messages")

    def test_custom_prompt_generator(self):
        """Test that CustomPromptGenerator generates a prompt with the custom template."""
        custom_template = "Custom prompt template."
        strategy = CustomSystemPromptStrategy(prompt_template=custom_template)
        prompt = strategy.generate_prompt()
        self.assertIsInstance(prompt, ChatPromptTemplate)
        self.assertEqual(prompt.messages[0].prompt.template, custom_template)
        self.assertEqual(prompt.messages[1].variable_name, "messages")

    def test_custom_prompt_generator_empty_template(self):
        """Test that CustomPromptGenerator raises ValueError when given an empty template."""
        with self.assertRaises(ValueError):
            CustomSystemPromptStrategy(prompt_template="")

    def test_system_prompt_generator_with_default_strategy(self):
        """Test SystemPromptGenerator using DefaultPromptGenerator strategy."""
        strategy = DefaultSystemPromptStrategy()
        system_prompt_generator = SystemPromptGenerator(strategy=strategy)
        prompt = system_prompt_generator.generate_prompt()
        self.assertIsInstance(prompt, ChatPromptTemplate)
        self.assertEqual(prompt.messages[0].prompt.template, template_default)

    def test_system_prompt_generator_with_aggressive_strategy(self):
        """Test SystemPromptGenerator using AggressivePromptGenerator strategy."""
        strategy = AggressiveSystemPromptStrategy()
        system_prompt_generator = SystemPromptGenerator(strategy=strategy)
        prompt = system_prompt_generator.generate_prompt()
        self.assertIsInstance(prompt, ChatPromptTemplate)
        self.assertEqual(prompt.messages[0].prompt.template, template_aggressive)

    def test_system_prompt_generator_with_custom_strategy(self):
        """Test SystemPromptGenerator using CustomPromptGenerator strategy."""
        custom_template = "Custom system prompt."
        strategy = CustomSystemPromptStrategy(prompt_template=custom_template)
        system_prompt_generator = SystemPromptGenerator(strategy=strategy)
        prompt = system_prompt_generator.generate_prompt()
        self.assertIsInstance(prompt, ChatPromptTemplate)
        self.assertEqual(prompt.messages[0].prompt.template, custom_template)

    def test_system_prompt_generator_invalid_strategy(self):
        """Test that SystemPromptGenerator raises TypeError when given an invalid strategy."""
        with self.assertRaises(TypeError):
            SystemPromptGenerator(strategy="Not a PromptGenerator")

    def test_prompt_generators_are_promptgenerator_subclasses(self):
        """Test that all PromptGenerator implementations are subclasses of PromptGenerator."""
        self.assertTrue(issubclass(DefaultSystemPromptStrategy, SystemPromptStrategy))
        self.assertTrue(issubclass(AggressiveSystemPromptStrategy, SystemPromptStrategy))
        self.assertTrue(issubclass(CustomSystemPromptStrategy, SystemPromptStrategy))

if __name__ == '__main__':
    unittest.main()
