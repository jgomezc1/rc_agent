#!/usr/bin/env python3
"""
AI Service Integration Module

Provides intelligent analysis capabilities for the RC Agent system using OpenAI GPT models.
This module transforms the system from pattern-matching to true AI-powered analysis.
"""

import os
import json
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from openai import OpenAI
import traceback

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, will use system environment variables
    pass

@dataclass
class AnalysisContext:
    """Context information for AI analysis"""
    rs_data: Dict[str, Any]
    project_type: Optional[str] = None
    location: Optional[str] = None
    seismic_zone: Optional[str] = None
    building_height: Optional[str] = None
    timeline_constraints: Optional[str] = None
    budget_constraints: Optional[str] = None
    sustainability_requirements: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = None  # For conversation memory

@dataclass
class AIResponse:
    """Structured AI response"""
    analysis: str
    recommendations: List[str]
    risks: List[str]
    trade_offs: List[str]
    confidence: float
    reasoning: str

class AIConstructionAdvisor:
    """AI-powered construction analysis and advisory service"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize AI service

        Args:
            api_key: OpenAI API key. If None, will try to get from environment
        """
        # Load environment variables from .env file if it exists
        if not api_key and not os.getenv('OPENAI_API_KEY'):
            if os.path.exists('.env'):
                with open('.env', 'r') as f:
                    for line in f:
                        if line.strip() and '=' in line and not line.startswith('#'):
                            key, value = line.strip().split('=', 1)
                            os.environ[key] = value

        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY environment variable or pass api_key parameter.")

        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-5-chat-latest"  # Use working GPT-5 variant
        self.conversation_history = []  # Store conversation for context

        # Construction domain knowledge prompts
        self.system_prompt = """You are an expert structural engineer and construction advisor specializing in reinforced concrete construction.

IMPORTANT: Provide complete analysis but DO NOT suggest follow-up questions or ask "Would you like me to..." at the end. Give definitive answers without prompting for additional analysis.

You have deep expertise in:

1. **Reinforcement Solutions (RS)**: Understanding RS codes like AG_EM_5a8_L50 where:
   - AG = Grouped/standardized lengths
   - EM = Mechanical couplers, TR = Traditional lap splices
   - 5a8 = Bar diameter range (#5 to #8)
   - L50 = Length granularity (50cm cuts)

2. **Construction Methods**: Mechanical couplers vs lap splices, constructibility challenges, labor efficiency

3. **Project Economics**: Steel costs, concrete costs, labor hours, construction duration, cost optimization

4. **Sustainability**: Carbon footprint (CO₂), material efficiency, waste reduction

5. **Risk Assessment**: Schedule risks, technical risks, quality risks, cost overruns

6. **BIM Integration**: Shop drawing optimization, element-level planning, procurement coordination

Your responses should be:
- **Technical but accessible**: Use engineering terminology but explain complex concepts
- **Context-aware**: Consider project type, location, constraints
- **Action-oriented**: Provide specific, implementable recommendations
- **Risk-conscious**: Highlight potential issues and mitigation strategies
- **Evidence-based**: Reference data and metrics when available

Always structure your analysis clearly with headings and bullet points for readability."""

    def analyze_rs_solution(
        self,
        rs_code: str,
        rs_data: Dict[str, Any],
        question: str,
        context: Optional[AnalysisContext] = None
    ) -> AIResponse:
        """
        Perform AI-powered analysis of an RS solution

        Args:
            rs_code: RS solution code (e.g., "AG_EM_5a8_L50")
            rs_data: Technical data for the RS solution
            question: User's specific question or analysis request
            context: Additional project context

        Returns:
            AIResponse with detailed analysis
        """
        try:
            # Build comprehensive prompt
            prompt = self._build_analysis_prompt(rs_code, rs_data, question, context)

            # Build messages with conversation history
            messages = [{"role": "system", "content": self.system_prompt}]

            # Add conversation history for context
            if context and context.conversation_history:
                messages.extend(context.conversation_history)
            elif self.conversation_history:
                messages.extend(self.conversation_history)

            # Add current question
            messages.append({"role": "user", "content": prompt})

            # Get AI response
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                # temperature=0.3,  # GPT-5 only supports default temperature (1)
                # max_completion_tokens=2000  # Try without token limit first
            )

            analysis_text = response.choices[0].message.content

            # Store conversation for future context
            self.conversation_history.append({"role": "user", "content": question})
            self.conversation_history.append({"role": "assistant", "content": analysis_text})

            # Keep conversation history manageable (last 10 exchanges)
            if len(self.conversation_history) > 20:  # 10 Q&A pairs = 20 messages
                self.conversation_history = self.conversation_history[-20:]

            # Parse structured response
            return self._parse_ai_response(analysis_text)

        except Exception as e:
            return AIResponse(
                analysis=f"AI Analysis temporarily unavailable: {str(e)}",
                recommendations=["Consider manual analysis or retry later"],
                risks=["AI service disruption"],
                trade_offs=[],
                confidence=0.0,
                reasoning="Technical error occurred"
            )

    def compare_solutions(
        self,
        solutions: List[Tuple[str, Dict[str, Any]]],
        question: str,
        context: Optional[AnalysisContext] = None
    ) -> AIResponse:
        """
        AI-powered comparison of multiple RS solutions

        Args:
            solutions: List of (rs_code, rs_data) tuples
            question: User's comparison question
            context: Project context

        Returns:
            AIResponse with comparative analysis
        """
        try:
            # Build comparison prompt
            prompt = self._build_comparison_prompt(solutions, question, context)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                # temperature=0.3,  # GPT-5 only supports default temperature
                # max_completion_tokens=2500  # Try without token limit
            )

            analysis_text = response.choices[0].message.content
            return self._parse_ai_response(analysis_text)

        except Exception as e:
            return AIResponse(
                analysis=f"Comparison analysis unavailable: {str(e)}",
                recommendations=["Review solutions individually"],
                risks=["Unable to provide comparative insights"],
                trade_offs=[],
                confidence=0.0,
                reasoning="Technical error in comparison"
            )

    def strategic_advice(
        self,
        question: str,
        available_solutions: Optional[Dict[str, Dict[str, Any]]] = None,
        context: Optional[AnalysisContext] = None
    ) -> AIResponse:
        """
        Provide strategic construction advice based on open-ended questions

        Args:
            question: User's strategic question
            available_solutions: Available RS solutions for context
            context: Project context

        Returns:
            AIResponse with strategic guidance
        """
        try:
            prompt = self._build_strategic_prompt(question, available_solutions, context)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                # temperature=0.4,  # GPT-5 only supports default temperature
                # max_completion_tokens=2000  # Try without token limit
            )

            analysis_text = response.choices[0].message.content
            return self._parse_ai_response(analysis_text)

        except Exception as e:
            return AIResponse(
                analysis=f"Strategic analysis unavailable: {str(e)}",
                recommendations=["Consult with domain experts"],
                risks=["Limited strategic insights available"],
                trade_offs=[],
                confidence=0.0,
                reasoning="AI service error"
            )

    def _build_analysis_prompt(
        self,
        rs_code: str,
        rs_data: Dict[str, Any],
        question: str,
        context: Optional[AnalysisContext]
    ) -> str:
        """Build detailed analysis prompt"""

        prompt = f"""**ANALYSIS REQUEST**
User Question: "{question}"

**RS SOLUTION TO ANALYZE**
RS Code: {rs_code}
Technical Data:"""

        for key, value in rs_data.items():
            if isinstance(value, (int, float)):
                if 'cost' in key:
                    prompt += f"\n  • {key}: ${value:,.0f}"
                elif key == 'steel_tonnage':
                    prompt += f"\n  • {key}: {value:.1f} tonnes"
                elif key == 'co2_tonnes':
                    prompt += f"\n  • {key}: {value:.0f} tonnes CO₂"
                elif key == 'duration_days':
                    prompt += f"\n  • {key}: {value:.0f} days"
                elif key == 'constructibility_index':
                    prompt += f"\n  • {key}: {value:.2f} (lower = easier)"
                else:
                    prompt += f"\n  • {key}: {value}"
            else:
                prompt += f"\n  • {key}: {value}"

        # Add RS code interpretation
        prompt += f"\n\n**RS CODE BREAKDOWN ({rs_code}):**"
        prompt += self._decode_rs_code(rs_code)

        # Add context if available
        if context:
            prompt += f"\n\n**PROJECT CONTEXT:**"
            if context.project_type:
                prompt += f"\n  • Project Type: {context.project_type}"
            if context.location:
                prompt += f"\n  • Location: {context.location}"
            if context.seismic_zone:
                prompt += f"\n  • Seismic Zone: {context.seismic_zone}"
            if context.building_height:
                prompt += f"\n  • Building Height: {context.building_height}"
            if context.timeline_constraints:
                prompt += f"\n  • Timeline: {context.timeline_constraints}"
            if context.budget_constraints:
                prompt += f"\n  • Budget: {context.budget_constraints}"
            if context.sustainability_requirements:
                prompt += f"\n  • Sustainability: {context.sustainability_requirements}"

        prompt += f"""

**ANALYSIS REQUIREMENTS:**
Please provide a comprehensive analysis addressing the user's question. Structure your response as:

1. **DIRECT ANSWER**: Address the specific question asked
2. **TECHNICAL ANALYSIS**: Deep dive into the engineering aspects
3. **PRACTICAL IMPLICATIONS**: Real-world construction considerations
4. **RECOMMENDATIONS**: Specific actionable advice
5. **RISK ASSESSMENT**: Potential challenges and mitigation strategies
6. **TRADE-OFFS**: Key compromises and alternatives to consider

Consider factors like:
- Constructibility and labor efficiency
- Cost optimization opportunities
- Schedule impact and critical path considerations
- Quality and durability implications
- Sustainability and environmental impact
- Risk factors and contingency planning

IMPORTANT: End your response with definitive conclusions. Do not ask follow-up questions or suggest additional analysis."""

        return prompt

    def _build_comparison_prompt(
        self,
        solutions: List[Tuple[str, Dict[str, Any]]],
        question: str,
        context: Optional[AnalysisContext]
    ) -> str:
        """Build comparison analysis prompt"""

        prompt = f"""**COMPARISON REQUEST**
User Question: "{question}"

**SOLUTIONS TO COMPARE:**"""

        for i, (rs_code, rs_data) in enumerate(solutions, 1):
            prompt += f"\n\n**SOLUTION {i}: {rs_code}**"
            for key, value in rs_data.items():
                if isinstance(value, (int, float)):
                    if 'cost' in key:
                        prompt += f"\n  • {key}: ${value:,.0f}"
                    elif key == 'steel_tonnage':
                        prompt += f"\n  • {key}: {value:.1f} tonnes"
                    elif key == 'co2_tonnes':
                        prompt += f"\n  • {key}: {value:.0f} tonnes CO₂"
                    else:
                        prompt += f"\n  • {key}: {value}"
                else:
                    prompt += f"\n  • {key}: {value}"

            prompt += f"\n  RS Strategy: {self._decode_rs_code(rs_code)}"

        if context:
            prompt += f"\n\n**PROJECT CONTEXT:**"
            if context.project_type:
                prompt += f"\n  • Project Type: {context.project_type}"
            if context.timeline_constraints:
                prompt += f"\n  • Timeline: {context.timeline_constraints}"
            if context.budget_constraints:
                prompt += f"\n  • Budget: {context.budget_constraints}"

        prompt += f"""

**COMPARISON REQUIREMENTS:**
Provide a detailed comparison addressing:

1. **PERFORMANCE COMPARISON**: Side-by-side metric analysis
2. **STRATEGIC DIFFERENCES**: Construction approach variations
3. **COST-BENEFIT ANALYSIS**: Financial implications and value
4. **RISK COMPARISON**: Relative risk profiles
5. **SCENARIO RECOMMENDATIONS**: Which solution for which circumstances
6. **DECISION CRITERIA**: Key factors for selection

Focus on practical construction implications and business value."""

        return prompt

    def _build_strategic_prompt(
        self,
        question: str,
        available_solutions: Optional[Dict[str, Dict[str, Any]]],
        context: Optional[AnalysisContext]
    ) -> str:
        """Build strategic advice prompt"""

        prompt = f"""**STRATEGIC CONSULTATION REQUEST**
Question: "{question}"
"""

        if available_solutions:
            prompt += f"\n**AVAILABLE RS SOLUTIONS:**"
            for rs_code, data in list(available_solutions.items())[:5]:  # Limit to avoid token overflow
                prompt += f"\n• {rs_code}: Steel ${data.get('steel_cost', 0):,.0f}, Duration {data.get('duration_days', 0):.0f} days, CO₂ {data.get('co2_tonnes', 0):.0f}t"

        if context:
            prompt += f"\n\n**PROJECT PARAMETERS:**"
            for field, value in context.__dict__.items():
                if value and field != 'rs_data':
                    prompt += f"\n• {field.replace('_', ' ').title()}: {value}"

        prompt += f"""

**STRATEGIC GUIDANCE REQUESTED:**
Please provide expert strategic advice considering:

1. **INDUSTRY BEST PRACTICES**: Current construction industry standards
2. **TECHNICAL FEASIBILITY**: Engineering and practical constraints
3. **MARKET CONDITIONS**: Cost trends and material availability
4. **REGULATORY COMPLIANCE**: Building codes and standards
5. **RISK MANAGEMENT**: Project risk assessment and mitigation
6. **INNOVATION OPPORTUNITIES**: Advanced techniques and technologies
7. **LONG-TERM VALUE**: Lifecycle considerations and future-proofing

Provide actionable strategic recommendations with supporting rationale."""

        return prompt

    def _decode_rs_code(self, rs_code: str) -> str:
        """Decode RS code into human-readable strategy description"""
        parts = rs_code.split('_')
        description = []

        if rs_code.startswith('AG_'):
            description.append("Standardized/grouped lengths strategy")
        else:
            description.append("Flexible length optimization")

        if 'EM' in rs_code:
            description.append("mechanical couplers for connections")
        elif 'TR' in rs_code:
            description.append("traditional lap splices")

        # Extract bar range
        for part in parts:
            if any(char.isdigit() for char in part) and not part.startswith('L'):
                if 'a' in part:
                    bar_range = part.replace('a', '-')
                    description.append(f"bar sizes #{bar_range}")
                else:
                    description.append(f"bar size #{part}")

        # Extract length granularity
        for part in parts:
            if part.startswith('L'):
                length = part[1:]
                description.append(f"{length}cm cutting increments")

        return "; ".join(description)

    def _parse_ai_response(self, analysis_text: str) -> AIResponse:
        """Parse AI response into structured format"""

        # Extract sections using simple heuristics
        recommendations = []
        risks = []
        trade_offs = []

        lines = analysis_text.split('\n')
        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect section headers
            if any(keyword in line.lower() for keyword in ['recommendation', 'suggest', 'advise']):
                current_section = 'recommendations'
            elif any(keyword in line.lower() for keyword in ['risk', 'challenge', 'problem', 'concern']):
                current_section = 'risks'
            elif any(keyword in line.lower() for keyword in ['trade-off', 'tradeoff', 'compromise', 'balance']):
                current_section = 'trade_offs'
            elif line.startswith('•') or line.startswith('-') or line.startswith('*'):
                # Extract bullet points
                item = line.lstrip('•-* ').strip()
                if current_section == 'recommendations' and item:
                    recommendations.append(item)
                elif current_section == 'risks' and item:
                    risks.append(item)
                elif current_section == 'trade_offs' and item:
                    trade_offs.append(item)

        # Calculate confidence based on response quality indicators
        confidence = 0.8  # Base confidence
        if len(analysis_text) > 1000:
            confidence += 0.1  # Detailed response
        if len(recommendations) > 0:
            confidence += 0.05  # Has actionable advice
        if len(risks) > 0:
            confidence += 0.05  # Considers risks
        confidence = min(confidence, 1.0)

        return AIResponse(
            analysis=analysis_text,
            recommendations=recommendations[:5],  # Limit to top 5
            risks=risks[:5],
            trade_offs=trade_offs[:5],
            confidence=confidence,
            reasoning="AI analysis using GPT-5 with construction domain expertise"
        )

    def test_connection(self) -> bool:
        """Test if AI service is available"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": "Test connection. Reply with just 'OK'."}
                ],
                max_completion_tokens=10
            )
            # If we get a valid response object, the connection works
            # (GPT-5 sometimes returns empty content but the API call succeeds)
            content = response.choices[0].message.content
            print(f"Connected to model: {response.model}")
            return True  # API call succeeded, connection is working
        except Exception as e:
            print(f"Debug: Connection test failed with error: {e}")
            return False

# Factory function for easy initialization
def create_ai_advisor(api_key: Optional[str] = None) -> Optional[AIConstructionAdvisor]:
    """
    Create AI advisor instance with error handling

    Returns None if AI service is not available or configured
    """
    try:
        advisor = AIConstructionAdvisor(api_key)
        if advisor.test_connection():
            return advisor
        else:
            print("Warning: AI service connection test failed")
            return None
    except Exception as e:
        print(f"Warning: AI service not available: {e}")
        return None