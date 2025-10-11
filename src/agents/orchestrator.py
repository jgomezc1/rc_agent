#!/usr/bin/env python3
"""
Multi-Agent Orchestrator

Manages communication and workflow coordination between the three specialized agents:
- Trade-Off Analyst Agent (T-OAA)
- Procurement & Logistics Agent (P&L-A)
- Field Adaptability Agent (F-AA)
"""

import json
from typing import Dict, List, Optional, Any
from enum import Enum

from agents.base_agent import AgentContext
from agents.tradeoff_analyst_agent import TradeOffAnalystAgent
from agents.procurement_logistics_agent import ProcurementLogisticsAgent
from agents.field_adaptability_agent import FieldAdaptabilityAgent


class ProjectPhase(Enum):
    """Current phase of the project"""
    OPTIMIZATION = "optimization"  # Using T-OAA
    IMPLEMENTATION = "implementation"  # Using P&L-A
    ADAPTATION = "adaptation"  # Using F-AA


class AgentOrchestrator:
    """
    Orchestrates workflow between multiple agents

    Manages:
    - Agent lifecycle and initialization
    - Context sharing between agents
    - Phase transitions (Optimization → Implementation → Adaptation)
    - Cross-agent communication
    """

    def __init__(
        self,
        project_id: str = "default",
        api_key: Optional[str] = None,
        model: str = "gpt-4"
    ):
        """
        Initialize orchestrator

        Args:
            project_id: Unique project identifier
            api_key: OpenAI API key
            model: Model to use for all agents
        """
        self.project_id = project_id
        self.api_key = api_key
        self.model = model

        # Create shared context
        self.shared_context = AgentContext(project_id=project_id)

        # Initialize agents (lazy initialization)
        self._toaa: Optional[TradeOffAnalystAgent] = None
        self._pla: Optional[ProcurementLogisticsAgent] = None
        self._faa: Optional[FieldAdaptabilityAgent] = None

        # Current active agent and phase
        self.current_phase = ProjectPhase.OPTIMIZATION
        self.current_agent = None

        # Workflow state
        self.phase_history = []

    @property
    def toaa(self) -> TradeOffAnalystAgent:
        """Get or create Trade-Off Analyst Agent"""
        if self._toaa is None:
            self._toaa = TradeOffAnalystAgent(
                api_key=self.api_key,
                model=self.model,
                context=self.shared_context
            )
            # Load Phase 1 data - try multiple paths
            loaded = False
            paths_to_try = [
                "data/shop_drawings.json",
                "../data/shop_drawings.json",
                "./data/shop_drawings.json"
            ]

            for path in paths_to_try:
                try:
                    self._toaa.load_phase1_data(path)
                    loaded = True
                    break
                except Exception as e:
                    continue

            if not loaded:
                print(f"Warning: Could not load Phase 1 data. Agent will have limited functionality.")
                print(f"Please ensure data/shop_drawings.json exists in the project directory.")
        return self._toaa

    @property
    def pla(self) -> ProcurementLogisticsAgent:
        """Get or create Procurement & Logistics Agent"""
        if self._pla is None:
            self._pla = ProcurementLogisticsAgent(
                api_key=self.api_key,
                model=self.model,
                context=self.shared_context
            )
        return self._pla

    @property
    def faa(self) -> FieldAdaptabilityAgent:
        """Get or create Field Adaptability Agent"""
        if self._faa is None:
            self._faa = FieldAdaptabilityAgent(
                api_key=self.api_key,
                model=self.model,
                context=self.shared_context
            )
        return self._faa

    def get_active_agent(self):
        """Get currently active agent based on phase"""
        if self.current_phase == ProjectPhase.OPTIMIZATION:
            return self.toaa
        elif self.current_phase == ProjectPhase.IMPLEMENTATION:
            return self.pla
        elif self.current_phase == ProjectPhase.ADAPTATION:
            return self.faa
        return None

    def query(self, user_query: str, **kwargs) -> Dict[str, Any]:
        """
        Route query to appropriate agent

        Args:
            user_query: User question or command
            **kwargs: Additional parameters

        Returns:
            Agent response
        """
        agent = self.get_active_agent()
        if not agent:
            return {"error": "No active agent for current phase"}

        response = agent.process_query(user_query, **kwargs)

        # Check if phase transition is needed
        self._check_phase_transition(response)

        return response

    def _check_phase_transition(self, response: Dict[str, Any]):
        """
        Check if agent response indicates need for phase transition

        Args:
            response: Agent response to analyze
        """
        # Check for solution selection (T-OAA → P&L-A)
        if self.current_phase == ProjectPhase.OPTIMIZATION:
            if self.shared_context.selected_solution_id:
                # Solution selected, ready to move to implementation
                self.phase_history.append({
                    "from_phase": self.current_phase.value,
                    "to_phase": ProjectPhase.IMPLEMENTATION.value,
                    "trigger": "solution_selected",
                    "solution_id": self.shared_context.selected_solution_id
                })

        # Check for crisis events (Any phase → F-AA)
        if "crisis" in str(response).lower() or "issue" in str(response).lower():
            if self.current_phase != ProjectPhase.ADAPTATION:
                self.phase_history.append({
                    "from_phase": self.current_phase.value,
                    "to_phase": ProjectPhase.ADAPTATION.value,
                    "trigger": "crisis_detected"
                })

    def transition_to_phase(self, phase: ProjectPhase) -> Dict[str, Any]:
        """
        Explicitly transition to a new phase

        Args:
            phase: Target phase

        Returns:
            Transition status
        """
        if phase == self.current_phase:
            return {
                "status": "already_in_phase",
                "current_phase": phase.value
            }

        # Record transition
        self.phase_history.append({
            "from_phase": self.current_phase.value,
            "to_phase": phase.value,
            "trigger": "manual_transition"
        })

        # Perform transition
        old_phase = self.current_phase
        self.current_phase = phase

        # Share context between agents
        if phase == ProjectPhase.IMPLEMENTATION:
            # T-OAA → P&L-A: Share selected solution
            if self.shared_context.selected_solution_id:
                try:
                    self.pla.load_phase2_data(
                        solution_id=self.shared_context.selected_solution_id
                    )
                except:
                    pass

        elif phase == ProjectPhase.ADAPTATION:
            # Any → F-AA: Share all available data
            if not self.faa.context.phase1_data:
                try:
                    self.faa.load_phase1_data()
                except:
                    pass

            if self.shared_context.selected_solution_id:
                try:
                    self.faa.load_phase2_data(
                        solution_id=self.shared_context.selected_solution_id
                    )
                except:
                    pass

        return {
            "status": "transition_complete",
            "from_phase": old_phase.value,
            "to_phase": phase.value,
            "active_agent": self.get_active_agent().role.value
        }

    def select_solution(self, solution_id: str) -> Dict[str, Any]:
        """
        Select a primary solution and prepare for implementation phase

        Args:
            solution_id: Solution ID to select (RS-P)

        Returns:
            Selection status
        """
        # Validate solution exists in Phase 1 data
        if not self.toaa.context.phase1_data:
            return {"error": "Phase 1 data not loaded"}

        if solution_id not in self.toaa.context.phase1_data:
            return {"error": f"Solution {solution_id} not found in Phase 1 data"}

        # Mark as selected
        self.toaa.select_primary_solution(solution_id)

        # Transition to implementation phase
        transition_result = self.transition_to_phase(ProjectPhase.IMPLEMENTATION)

        return {
            "solution_selected": solution_id,
            "ready_for_procurement": True,
            "transition": transition_result,
            "next_steps": [
                "Use Procurement & Logistics Agent to generate material breakdown",
                "Create JIT delivery schedule",
                "Generate purchase orders"
            ]
        }

    def report_crisis(
        self,
        event_type: str,
        description: str,
        affected_element: Optional[str] = None,
        affected_story: Optional[str] = None,
        severity: str = "medium"
    ) -> Dict[str, Any]:
        """
        Report a site crisis and activate Field Adaptability Agent

        Args:
            event_type: Type of crisis
            description: Crisis description
            affected_element: Affected element ID
            affected_story: Affected story
            severity: Crisis severity

        Returns:
            Crisis response
        """
        # Transition to adaptation phase if not already there
        if self.current_phase != ProjectPhase.ADAPTATION:
            self.transition_to_phase(ProjectPhase.ADAPTATION)

        # Report to F-AA
        response = self.faa.report_site_event(
            event_type=event_type,
            description=description,
            affected_element=affected_element,
            affected_story=affected_story,
            severity=severity
        )

        return {
            "crisis_logged": True,
            "active_agent": "F-AA",
            "response": response
        }

    def get_project_status(self) -> Dict[str, Any]:
        """
        Get overall project status across all agents

        Returns:
            Comprehensive project status
        """
        status = {
            "project_id": self.project_id,
            "current_phase": self.current_phase.value,
            "active_agent": self.get_active_agent().role.value if self.get_active_agent() else None,
            "selected_solution": self.shared_context.selected_solution_id,
            "phase_transitions": len(self.phase_history),
            "agents_status": {}
        }

        # Get status from each initialized agent
        if self._toaa:
            status["agents_status"]["T-OAA"] = self.toaa.get_agent_info()

        if self._pla:
            status["agents_status"]["P&L-A"] = self.pla.get_agent_info()

        if self._faa:
            status["agents_status"]["F-AA"] = self.faa.get_agent_info()

        return status

    def export_project_context(self) -> Dict[str, Any]:
        """
        Export complete project context for external storage

        Returns:
            Full project context
        """
        return {
            "project_id": self.project_id,
            "current_phase": self.current_phase.value,
            "selected_solution_id": self.shared_context.selected_solution_id,
            "phase_history": self.phase_history,
            "metadata": self.shared_context.metadata,
            "toaa_context": self.toaa.export_context() if self._toaa else None,
            "pla_context": self.pla.export_context() if self._pla else None,
            "faa_context": self.faa.export_context() if self._faa else None
        }

    def import_project_context(self, context_data: Dict[str, Any]):
        """
        Import project context from external storage

        Args:
            context_data: Context data from export_project_context()
        """
        self.project_id = context_data.get("project_id", self.project_id)
        self.current_phase = ProjectPhase(context_data.get("current_phase", "optimization"))
        self.shared_context.selected_solution_id = context_data.get("selected_solution_id")
        self.shared_context.metadata = context_data.get("metadata", {})
        self.phase_history = context_data.get("phase_history", [])

        # Import agent-specific contexts
        if context_data.get("toaa_context") and self._toaa:
            self.toaa.import_context(context_data["toaa_context"])

        if context_data.get("pla_context") and self._pla:
            self.pla.import_context(context_data["pla_context"])

        if context_data.get("faa_context") and self._faa:
            self.faa.import_context(context_data["faa_context"])
