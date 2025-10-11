#!/usr/bin/env python3
"""
Base Agent Class for Multi-Agent Architecture

Provides common functionality for all specialized agents in the StructuBIM system.
"""

import os
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from openai import OpenAI

# Try to load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class AgentRole(Enum):
    """Agent role definitions"""
    TRADEOFF_ANALYST = "tradeoff_analyst"
    PROCUREMENT_LOGISTICS = "procurement_logistics"
    FIELD_ADAPTABILITY = "field_adaptability"


@dataclass
class AgentContext:
    """Context shared across agents"""
    project_id: str
    phase1_data: Optional[Dict[str, Any]] = None
    phase2_data: Optional[Dict[str, Any]] = None
    selected_solution_id: Optional[str] = None
    master_schedule: Optional[Dict[str, Any]] = None
    market_data: Optional[Dict[str, Any]] = None
    site_conditions: Optional[Dict[str, Any]] = None
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """
    Base class for all StructuBIM agents

    Provides common functionality for:
    - OpenAI API integration
    - Conversation management
    - Data loading and validation
    - Tool execution
    """

    def __init__(
        self,
        role: AgentRole,
        api_key: Optional[str] = None,
        model: str = "gpt-4",
        context: Optional[AgentContext] = None
    ):
        """
        Initialize base agent

        Args:
            role: Agent role identifier
            api_key: OpenAI API key (optional, will use env var if not provided)
            model: OpenAI model to use
            context: Shared agent context
        """
        self.role = role
        self.model = model
        self.context = context or AgentContext(project_id="default")

        # Initialize OpenAI client
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not provided. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.client = OpenAI(api_key=self.api_key)

        # Agent-specific attributes
        self.tools = []
        self.conversation_history = []

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Get agent-specific system prompt

        Returns:
            System prompt string tailored to agent role
        """
        pass

    @abstractmethod
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get agent-specific tools

        Returns:
            List of tool definitions for this agent
        """
        pass

    @abstractmethod
    def process_query(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Process user query with agent-specific logic

        Args:
            query: User question or command
            **kwargs: Additional parameters specific to agent

        Returns:
            Agent response dictionary
        """
        pass

    def load_phase1_data(self, path: str = "data/shop_drawings.json") -> Dict[str, Any]:
        """
        Load Phase 1 summary data

        Args:
            path: Path to Phase 1 JSON file

        Returns:
            Phase 1 data dictionary
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.context.phase1_data = data
            return data
        except FileNotFoundError:
            raise FileNotFoundError(f"Phase 1 data file not found: {path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in Phase 1 file: {e}")

    def load_phase2_data(
        self,
        solution_id: Optional[str] = None,
        path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Load Phase 2 detailed data

        Args:
            solution_id: Solution ID to load (e.g., "TR_5a8_L10")
            path: Direct path to Phase 2 JSON file

        Returns:
            Phase 2 data dictionary
        """
        if path:
            file_path = path
        elif solution_id:
            # Try solution-specific file first
            file_path = f"data/{solution_id}.json"
            if not os.path.exists(file_path):
                # Fall back to unified BIM file
                file_path = "data/shop_drawings_structuBIM.json"
        else:
            file_path = "data/shop_drawings_structuBIM.json"

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # If loading from unified file and solution_id provided, extract that solution
            if solution_id and "by_element" not in data:
                # Assume data is already solution-specific
                pass

            self.context.phase2_data = data
            return data
        except FileNotFoundError:
            raise FileNotFoundError(f"Phase 2 data file not found: {file_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in Phase 2 file: {e}")

    def call_llm(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Any:
        """
        Call OpenAI LLM with messages

        Args:
            messages: Conversation messages
            tools: Optional tool definitions
            temperature: Sampling temperature
            max_tokens: Maximum response tokens

        Returns:
            OpenAI completion response
        """
        try:
            if tools:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            return response
        except Exception as e:
            raise RuntimeError(f"Error calling LLM: {e}")

    def add_to_history(self, role: str, content: str):
        """
        Add message to conversation history

        Args:
            role: Message role (user/assistant/system)
            content: Message content
        """
        self.conversation_history.append({"role": role, "content": content})
        self.context.conversation_history.append({"role": role, "content": content})

    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        self.context.conversation_history = []

    def get_agent_info(self) -> Dict[str, Any]:
        """
        Get agent information

        Returns:
            Dictionary with agent metadata
        """
        return {
            "role": self.role.value,
            "model": self.model,
            "tools_count": len(self.get_tools()),
            "has_phase1_data": self.context.phase1_data is not None,
            "has_phase2_data": self.context.phase2_data is not None,
            "selected_solution": self.context.selected_solution_id,
            "conversation_length": len(self.conversation_history)
        }

    def export_context(self) -> Dict[str, Any]:
        """
        Export agent context for sharing with other agents

        Returns:
            Context dictionary
        """
        return {
            "project_id": self.context.project_id,
            "selected_solution_id": self.context.selected_solution_id,
            "metadata": self.context.metadata,
            "conversation_history": self.context.conversation_history[-5:],  # Last 5 exchanges
        }

    def import_context(self, context_data: Dict[str, Any]):
        """
        Import context from another agent

        Args:
            context_data: Context dictionary from export_context()
        """
        if "selected_solution_id" in context_data:
            self.context.selected_solution_id = context_data["selected_solution_id"]

        if "metadata" in context_data:
            self.context.metadata.update(context_data["metadata"])

        if "conversation_history" in context_data:
            # Add imported history with a marker
            for msg in context_data["conversation_history"]:
                self.conversation_history.append({
                    "role": msg["role"],
                    "content": f"[From previous agent] {msg['content']}"
                })
