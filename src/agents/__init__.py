"""
Multi-Agent System for StructuBIM RC Agent

This package contains three specialized agents:
1. Trade-Off Analyst Agent (T-OAA) - Pre-Construction/Value Finding
2. Procurement & Logistics Agent (P&L-A) - Pre-Construction/JIT Planning
3. Field Adaptability Agent (F-AA) - Construction/Risk Mitigation
"""

from .base_agent import BaseAgent, AgentRole, AgentContext
from .tradeoff_analyst_agent import TradeOffAnalystAgent
from .procurement_logistics_agent import ProcurementLogisticsAgent
from .field_adaptability_agent import FieldAdaptabilityAgent

__all__ = [
    'BaseAgent',
    'AgentRole',
    'AgentContext',
    'TradeOffAnalystAgent',
    'ProcurementLogisticsAgent',
    'FieldAdaptabilityAgent',
]
