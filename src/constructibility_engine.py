"""
Constructibility Insights Engine for Phase 2 execution planning.
Provides design optimization suggestions and construction efficiency improvements.
"""

import math
from typing import Dict, List, Tuple, Optional, Set, Any
from collections import defaultdict, Counter
from dataclasses import dataclass
from phase2_models import (
    ElementDetail, ConstructibilityInsight, ConstructionTask, CrewRequirement
)


@dataclass
class DesignOptimization:
    """Design optimization opportunity"""
    optimization_id: str
    category: str
    title: str
    current_state: str
    proposed_state: str
    elements_affected: List[str]
    savings_estimate: Dict[str, float]
    implementation_complexity: str


@dataclass
class StandardizationOpportunity:
    """Material or process standardization opportunity"""
    item_type: str  # "bar_diameter", "formwork_type", "process"
    current_variety: int
    recommended_variety: int
    affected_elements: List[str]
    potential_savings: Dict[str, float]


class ConstructibilityAnalyzer:
    """Construction optimization and insight generation engine"""

    def __init__(self):
        # Standard bar diameter preferences (most economical)
        self.preferred_diameters = ["1/2\"", "5/8\"", "3/4\""]

        # Complexity thresholds
        self.complexity_thresholds = {
            "simple": 2.0,
            "moderate": 3.0,
            "complex": 4.0,
            "very_complex": 5.0
        }

        # Construction efficiency factors
        self.efficiency_factors = {
            "bar_standardization": 0.15,  # 15% time savings
            "formwork_reuse": 0.20,       # 20% cost savings
            "sequence_optimization": 0.10, # 10% time savings
            "crew_specialization": 0.12   # 12% efficiency gain
        }

    def analyze_constructibility(
        self,
        elements: List[ElementDetail],
        tasks: List[ConstructionTask]
    ) -> Dict[str, Any]:
        """Perform comprehensive constructibility analysis"""

        # Generate insights
        insights = []

        # Bar standardization opportunities
        insights.extend(self._analyze_bar_standardization(elements))

        # Formwork optimization
        insights.extend(self._analyze_formwork_optimization(elements))

        # Construction sequencing improvements
        insights.extend(self._analyze_sequencing_optimization(elements, tasks))

        # Complexity reduction opportunities
        insights.extend(self._analyze_complexity_reduction(elements))

        # Material quantity optimization
        insights.extend(self._analyze_material_optimization(elements))

        # Crew efficiency improvements
        insights.extend(self._analyze_crew_efficiency(elements, tasks))

        # Construction staging recommendations
        insights.extend(self._analyze_staging_optimization(elements))

        # Prioritize insights by impact
        prioritized_insights = self._prioritize_insights(insights)

        # Generate summary metrics
        summary = self._generate_constructibility_summary(elements, insights)

        return {
            "insights": prioritized_insights,
            "summary": summary,
            "optimization_opportunities": self._categorize_insights(prioritized_insights),
            "implementation_roadmap": self._create_implementation_roadmap(prioritized_insights)
        }

    def _analyze_bar_standardization(self, elements: List[ElementDetail]) -> List[ConstructibilityInsight]:
        """Analyze opportunities to standardize rebar diameters"""
        insights = []

        # Count diameter usage across all elements
        diameter_usage = defaultdict(int)
        diameter_weights = defaultdict(float)
        elements_by_diameter = defaultdict(list)

        for element in elements:
            for diameter, bar_spec in element.bars_by_diameter.items():
                diameter_usage[diameter] += bar_spec.count
                diameter_weights[diameter] += bar_spec.weight
                elements_by_diameter[diameter].append(element.element_id)

        # Identify low-usage diameters that could be standardized
        total_usage = sum(diameter_usage.values())
        low_usage_diameters = []

        for diameter, usage in diameter_usage.items():
            usage_percentage = (usage / total_usage) * 100 if total_usage > 0 else 0
            if usage_percentage < 10 and diameter not in self.preferred_diameters:
                low_usage_diameters.append((diameter, usage_percentage, elements_by_diameter[diameter]))

        if low_usage_diameters:
            for diameter, usage_pct, affected_elements in low_usage_diameters:
                # Find best replacement diameter
                replacement = self._find_best_replacement_diameter(diameter)

                if replacement:
                    cost_savings = diameter_weights[diameter] * 0.05  # 5% cost savings from standardization
                    time_savings = len(affected_elements) * 0.5  # 0.5 days per element

                    insight = ConstructibilityInsight(
                        insight_id=f"standardize_{diameter.replace(chr(34), 'in')}",
                        category="standardization",
                        title=f"Standardize {diameter} bars to {replacement}",
                        description=f"Replace {diameter} bars (used in {len(affected_elements)} elements, {usage_pct:.1f}% of total) with {replacement} for better standardization",
                        elements_affected=affected_elements,
                        potential_savings={
                            "cost": cost_savings,
                            "time": time_savings,
                            "complexity": len(affected_elements) * 0.1
                        },
                        implementation_effort="medium",
                        priority=3
                    )
                    insights.append(insight)

        return insights

    def _find_best_replacement_diameter(self, diameter: str) -> Optional[str]:
        """Find the best replacement diameter for standardization"""
        # Diameter sizes in inches (approximate)
        sizes = {
            "3/8\"": 0.375,
            "1/2\"": 0.5,
            "5/8\"": 0.625,
            "3/4\"": 0.75,
            "7/8\"": 0.875,
            "1\"": 1.0
        }

        if diameter not in sizes:
            return None

        current_size = sizes[diameter]

        # Find closest preferred diameter that's larger (for safety)
        best_replacement = None
        min_size_diff = float('inf')

        for preferred in self.preferred_diameters:
            if preferred in sizes:
                preferred_size = sizes[preferred]
                if preferred_size >= current_size:
                    size_diff = preferred_size - current_size
                    if size_diff < min_size_diff:
                        min_size_diff = size_diff
                        best_replacement = preferred

        return best_replacement

    def _analyze_formwork_optimization(self, elements: List[ElementDetail]) -> List[ConstructibilityInsight]:
        """Analyze formwork reuse and optimization opportunities"""
        insights = []

        # Group elements by level for potential formwork reuse
        elements_by_level = defaultdict(list)
        for element in elements:
            elements_by_level[element.level_name].append(element)

        # Analyze similar elements for formwork reuse potential
        for level_name, level_elements in elements_by_level.items():
            if len(level_elements) > 1:
                # Group by similar dimensions
                similar_groups = self._group_similar_elements(level_elements)

                for group in similar_groups:
                    if len(group) >= 3:  # Minimum 3 elements for meaningful reuse
                        total_formwork_area = sum(elem.surface_area for elem in group)
                        element_ids = [elem.element_id for elem in group]

                        # Calculate savings from formwork reuse
                        reuse_savings = total_formwork_area * 15 * 0.6  # 60% of formwork cost saved
                        time_savings = len(group) * 0.3  # 0.3 days per element

                        insight = ConstructibilityInsight(
                            insight_id=f"formwork_reuse_{level_name}_{len(group)}",
                            category="formwork_optimization",
                            title=f"Optimize formwork reuse for {len(group)} similar elements on {level_name}",
                            description=f"Standardize formwork design for {len(group)} similar elements to enable efficient reuse",
                            elements_affected=element_ids,
                            potential_savings={
                                "cost": reuse_savings,
                                "time": time_savings,
                                "complexity": len(group) * 0.2
                            },
                            implementation_effort="medium",
                            priority=2
                        )
                        insights.append(insight)

        return insights

    def _group_similar_elements(self, elements: List[ElementDetail]) -> List[List[ElementDetail]]:
        """Group elements with similar dimensions for formwork reuse"""
        groups = []
        used_elements = set()

        for element in elements:
            if element.element_id in used_elements:
                continue

            # Find similar elements
            similar_group = [element]
            used_elements.add(element.element_id)

            for other_element in elements:
                if (other_element.element_id != element.element_id and
                    other_element.element_id not in used_elements):

                    # Check similarity based on dimensions
                    if self._are_elements_similar(element, other_element):
                        similar_group.append(other_element)
                        used_elements.add(other_element.element_id)

            if len(similar_group) > 1:
                groups.append(similar_group)

        return groups

    def _are_elements_similar(self, elem1: ElementDetail, elem2: ElementDetail) -> bool:
        """Check if two elements are similar enough for formwork reuse"""
        # Compare surface area (within 20% tolerance)
        area_ratio = abs(elem1.surface_area - elem2.surface_area) / max(elem1.surface_area, elem2.surface_area)
        if area_ratio > 0.2:
            return False

        # Compare volume (within 25% tolerance)
        vol_ratio = abs(elem1.vol_concreto - elem2.vol_concreto) / max(elem1.vol_concreto, elem2.vol_concreto)
        if vol_ratio > 0.25:
            return False

        return True

    def _analyze_sequencing_optimization(
        self,
        elements: List[ElementDetail],
        tasks: List[ConstructionTask]
    ) -> List[ConstructibilityInsight]:
        """Analyze construction sequencing optimization opportunities"""
        insights = []

        # Group tasks by level
        tasks_by_level = defaultdict(list)
        for task in tasks:
            tasks_by_level[task.level_name].append(task)

        # Analyze each level for sequencing improvements
        for level_name, level_tasks in tasks_by_level.items():
            if len(level_tasks) > 4:  # Only analyze levels with multiple tasks

                # Look for batching opportunities
                rebar_tasks = [t for t in level_tasks if "rebar" in t.task_name.lower()]
                concrete_tasks = [t for t in level_tasks if "concrete" in t.task_name.lower()]

                if len(rebar_tasks) > 2:
                    total_rebar_hours = sum(t.duration_hours for t in rebar_tasks)
                    time_savings = total_rebar_hours * 0.1  # 10% savings from batching

                    insight = ConstructibilityInsight(
                        insight_id=f"batch_rebar_{level_name}",
                        category="sequencing",
                        title=f"Batch rebar operations on {level_name}",
                        description=f"Optimize sequencing of {len(rebar_tasks)} rebar tasks for crew efficiency",
                        elements_affected=[t.element_id for t in rebar_tasks],
                        potential_savings={
                            "time": time_savings / 8,  # Convert to days
                            "cost": time_savings * 50,  # $50/hour labor cost
                            "complexity": 0.5
                        },
                        implementation_effort="low",
                        priority=4
                    )
                    insights.append(insight)

                if len(concrete_tasks) > 1:
                    # Suggest concrete pour optimization
                    total_volume = 0
                    for task in concrete_tasks:
                        element = next((e for e in elements if e.element_id == task.element_id), None)
                        if element:
                            total_volume += element.vol_concreto

                    if total_volume > 50:  # Large enough for optimization
                        cost_savings = total_volume * 5  # $5/m³ savings from efficiency

                        insight = ConstructibilityInsight(
                            insight_id=f"optimize_concrete_{level_name}",
                            category="sequencing",
                            title=f"Optimize concrete pour sequence on {level_name}",
                            description=f"Coordinate {len(concrete_tasks)} concrete pours for {total_volume:.1f} m³ total volume",
                            elements_affected=[t.element_id for t in concrete_tasks],
                            potential_savings={
                                "cost": cost_savings,
                                "time": 0.5,
                                "complexity": 0.3
                            },
                            implementation_effort="medium",
                            priority=3
                        )
                        insights.append(insight)

        return insights

    def _analyze_complexity_reduction(self, elements: List[ElementDetail]) -> List[ConstructibilityInsight]:
        """Analyze opportunities to reduce construction complexity"""
        insights = []

        # Identify high-complexity elements
        high_complexity_elements = [e for e in elements if e.complexity_score > 3.5]

        for element in high_complexity_elements:
            # Analyze specific complexity drivers
            complexity_factors = []

            if element.bar_types > 10:
                complexity_factors.append(f"High bar type variety: {element.bar_types}")

            if len(element.bars_by_diameter) > 3:
                complexity_factors.append(f"Multiple bar diameters: {len(element.bars_by_diameter)}")

            if element.total_rebar_weight > 500:
                complexity_factors.append(f"Heavy reinforcement: {element.total_rebar_weight:.0f} kg")

            if complexity_factors:
                # Estimate savings from complexity reduction
                complexity_reduction = min(element.complexity_score - 2.5, 2.0)  # Target complexity ~2.5
                time_savings = complexity_reduction * 0.5  # 0.5 days per complexity point
                cost_savings = element.total_rebar_weight * 0.50  # $0.50/kg from efficiency

                insight = ConstructibilityInsight(
                    insight_id=f"reduce_complexity_{element.element_id}",
                    category="simplification",
                    title=f"Simplify design for element {element.element_id}",
                    description=f"Reduce complexity from {element.complexity_score:.1f} by addressing: {', '.join(complexity_factors)}",
                    elements_affected=[element.element_id],
                    potential_savings={
                        "time": time_savings,
                        "cost": cost_savings,
                        "complexity": complexity_reduction
                    },
                    implementation_effort="high",
                    priority=2
                )
                insights.append(insight)

        return insights

    def _analyze_material_optimization(self, elements: List[ElementDetail]) -> List[ConstructibilityInsight]:
        """Analyze material quantity and usage optimization"""
        insights = []

        # Calculate total material usage
        total_steel = sum(e.total_rebar_weight for e in elements)
        total_concrete = sum(e.vol_concreto for e in elements)

        # Analyze steel usage efficiency
        if total_steel > 0:
            # Check for unusually heavy elements
            heavy_elements = [e for e in elements if e.total_rebar_weight > total_steel / len(elements) * 2]

            if heavy_elements:
                for element in heavy_elements:
                    # Calculate reinforcement density
                    if element.vol_concreto > 0:
                        density = element.total_rebar_weight / element.vol_concreto

                        if density > 150:  # kg/m³ - high density
                            potential_reduction = element.total_rebar_weight * 0.1  # 10% reduction
                            cost_savings = potential_reduction * 1.5  # $1.5/kg steel cost

                            insight = ConstructibilityInsight(
                                insight_id=f"optimize_steel_{element.element_id}",
                                category="material_optimization",
                                title=f"Optimize steel usage in element {element.element_id}",
                                description=f"High reinforcement density {density:.0f} kg/m³ - review for optimization potential",
                                elements_affected=[element.element_id],
                                potential_savings={
                                    "cost": cost_savings,
                                    "time": 0.2,
                                    "complexity": 0.1
                                },
                                implementation_effort="medium",
                                priority=3
                            )
                            insights.append(insight)

        return insights

    def _analyze_crew_efficiency(
        self,
        elements: List[ElementDetail],
        tasks: List[ConstructionTask]
    ) -> List[ConstructibilityInsight]:
        """Analyze crew specialization and efficiency opportunities"""
        insights = []

        # Group tasks by crew type
        crew_utilization = defaultdict(list)
        for task in tasks:
            for crew_req in task.crew_requirements:
                crew_utilization[crew_req.crew_type].append(task)

        # Analyze utilization patterns
        for crew_type, crew_tasks in crew_utilization.items():
            if len(crew_tasks) > 5:  # Significant number of tasks
                total_hours = sum(task.duration_hours for task in crew_tasks)

                # Check for potential specialization benefits
                if total_hours > 200:  # More than 25 working days
                    efficiency_gain = total_hours * 0.12  # 12% efficiency improvement
                    cost_savings = efficiency_gain * 50  # $50/hour

                    insight = ConstructibilityInsight(
                        insight_id=f"specialize_{crew_type.value}",
                        category="crew_optimization",
                        title=f"Specialize {crew_type.value} crew operations",
                        description=f"Optimize {crew_type.value} crew for {len(crew_tasks)} tasks ({total_hours:.0f} hours total)",
                        elements_affected=[t.element_id for t in crew_tasks],
                        potential_savings={
                            "time": efficiency_gain / 8,  # Convert to days
                            "cost": cost_savings,
                            "complexity": 0.5
                        },
                        implementation_effort="low",
                        priority=4
                    )
                    insights.append(insight)

        return insights

    def _analyze_staging_optimization(self, elements: List[ElementDetail]) -> List[ConstructibilityInsight]:
        """Analyze construction staging optimization opportunities"""
        insights = []

        # Group elements by level and analyze staging
        levels = list(set(e.level_name for e in elements))
        levels.sort()  # Assume sorted order represents construction sequence

        if len(levels) > 3:  # Multi-level project
            # Analyze potential for level-wise staging
            total_volume_per_level = {}
            total_steel_per_level = {}

            for level in levels:
                level_elements = [e for e in elements if e.level_name == level]
                total_volume_per_level[level] = sum(e.vol_concreto for e in level_elements)
                total_steel_per_level[level] = sum(e.total_rebar_weight for e in level_elements)

            # Check for unbalanced levels that could benefit from staging
            avg_volume = sum(total_volume_per_level.values()) / len(levels)
            large_levels = [level for level, volume in total_volume_per_level.items() if volume > avg_volume * 1.5]

            if large_levels:
                for level in large_levels:
                    level_elements = [e for e in elements if e.level_name == level]
                    time_savings = len(level_elements) * 0.1  # 0.1 days per element from staging
                    cost_savings = total_steel_per_level[level] * 0.02  # 2% cost savings

                    insight = ConstructibilityInsight(
                        insight_id=f"stage_{level}",
                        category="staging",
                        title=f"Optimize construction staging for {level}",
                        description=f"Implement phased construction for large level with {len(level_elements)} elements",
                        elements_affected=[e.element_id for e in level_elements],
                        potential_savings={
                            "time": time_savings,
                            "cost": cost_savings,
                            "complexity": 0.3
                        },
                        implementation_effort="medium",
                        priority=3
                    )
                    insights.append(insight)

        return insights

    def _prioritize_insights(self, insights: List[ConstructibilityInsight]) -> List[ConstructibilityInsight]:
        """Prioritize insights by impact and feasibility"""
        def calculate_impact_score(insight: ConstructibilityInsight) -> float:
            savings = insight.potential_savings
            impact = (
                savings.get("cost", 0) / 1000 +  # Cost in thousands
                savings.get("time", 0) * 2 +      # Time savings weighted 2x
                savings.get("complexity", 0) * 3  # Complexity reduction weighted 3x
            )

            # Adjust for implementation effort
            effort_multiplier = {"low": 1.0, "medium": 0.8, "high": 0.6}
            multiplier = effort_multiplier.get(insight.implementation_effort, 0.7)

            return impact * multiplier

        # Sort by impact score
        sorted_insights = sorted(insights, key=calculate_impact_score, reverse=True)

        # Update priority based on ranking
        for i, insight in enumerate(sorted_insights):
            insight.priority = min(5, (i // 2) + 1)  # Priority 1-5

        return sorted_insights

    def _generate_constructibility_summary(
        self,
        elements: List[ElementDetail],
        insights: List[ConstructibilityInsight]
    ) -> Dict[str, Any]:
        """Generate summary of constructibility analysis"""
        total_elements = len(elements)
        total_insights = len(insights)

        # Calculate potential total savings
        total_cost_savings = sum(i.potential_savings.get("cost", 0) for i in insights)
        total_time_savings = sum(i.potential_savings.get("time", 0) for i in insights)
        total_complexity_reduction = sum(i.potential_savings.get("complexity", 0) for i in insights)

        # Categorize insights
        category_counts = Counter(i.category for i in insights)

        # Calculate constructibility score
        avg_complexity = sum(e.complexity_score for e in elements) / total_elements if elements else 0
        constructibility_score = max(0, 100 - (avg_complexity - 2.0) * 20)  # Scale to 0-100

        return {
            "total_elements_analyzed": total_elements,
            "total_insights_generated": total_insights,
            "constructibility_score": round(constructibility_score, 1),
            "potential_savings": {
                "total_cost_savings": round(total_cost_savings, 0),
                "total_time_savings_days": round(total_time_savings, 1),
                "complexity_reduction": round(total_complexity_reduction, 1)
            },
            "insight_categories": dict(category_counts),
            "high_priority_insights": len([i for i in insights if i.priority <= 2]),
            "average_complexity": round(avg_complexity, 2),
            "elements_needing_attention": len([e for e in elements if e.complexity_score > 3.5])
        }

    def _categorize_insights(self, insights: List[ConstructibilityInsight]) -> Dict[str, List[ConstructibilityInsight]]:
        """Categorize insights by type"""
        categories = defaultdict(list)
        for insight in insights:
            categories[insight.category].append(insight)
        return dict(categories)

    def _create_implementation_roadmap(self, insights: List[ConstructibilityInsight]) -> List[Dict[str, Any]]:
        """Create implementation roadmap for insights"""
        roadmap = []

        # Group by priority and implementation effort
        high_priority = [i for i in insights if i.priority <= 2]
        medium_priority = [i for i in insights if i.priority == 3]
        low_priority = [i for i in insights if i.priority >= 4]

        # Phase 1: High priority, low effort (quick wins)
        quick_wins = [i for i in high_priority if i.implementation_effort == "low"]
        if quick_wins:
            roadmap.append({
                "phase": "Phase 1 - Quick Wins (Weeks 1-2)",
                "insights": quick_wins,
                "total_savings": {
                    "cost": sum(i.potential_savings.get("cost", 0) for i in quick_wins),
                    "time": sum(i.potential_savings.get("time", 0) for i in quick_wins)
                }
            })

        # Phase 2: High priority, medium effort
        major_improvements = [i for i in high_priority if i.implementation_effort == "medium"]
        if major_improvements:
            roadmap.append({
                "phase": "Phase 2 - Major Improvements (Weeks 3-6)",
                "insights": major_improvements,
                "total_savings": {
                    "cost": sum(i.potential_savings.get("cost", 0) for i in major_improvements),
                    "time": sum(i.potential_savings.get("time", 0) for i in major_improvements)
                }
            })

        # Phase 3: Medium priority items
        if medium_priority:
            roadmap.append({
                "phase": "Phase 3 - Additional Optimizations (Weeks 7-10)",
                "insights": medium_priority[:5],  # Limit to top 5
                "total_savings": {
                    "cost": sum(i.potential_savings.get("cost", 0) for i in medium_priority[:5]),
                    "time": sum(i.potential_savings.get("time", 0) for i in medium_priority[:5])
                }
            })

        return roadmap