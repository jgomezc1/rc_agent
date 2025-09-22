"""
Crew & Sequence Planner for Phase 2 execution planning.
Optimizes crew allocation and construction sequencing.
"""

import math
from typing import Dict, List, Tuple, Optional, Set, Any
from datetime import datetime, timedelta
from collections import defaultdict, deque
from phase2_models import (
    ElementDetail, CrewRequirement, CrewType, ConstructionTask,
    RiskLevel, ElementRisk
)


class CrewPlanner:
    """Construction crew planning and sequencing optimization"""

    def __init__(self):
        # Standard crew productivity rates (m³ per day per worker)
        self.productivity_rates = {
            CrewType.REBAR_PLACING: 2.5,
            CrewType.FORMWORK: 8.0,
            CrewType.CONCRETE_POURING: 15.0,
            CrewType.FINISHING: 12.0
        }

        # Standard crew compositions
        self.standard_crews = {
            CrewType.REBAR_PLACING: {
                "base_size": 4,
                "skill_levels": {"senior": 1, "intermediate": 2, "junior": 1},
                "equipment": ["rebar_cutters", "tie_wire", "spacers", "lifting_equipment"]
            },
            CrewType.FORMWORK: {
                "base_size": 6,
                "skill_levels": {"senior": 1, "intermediate": 3, "junior": 2},
                "equipment": ["formwork_panels", "bracing", "release_agent", "hand_tools"]
            },
            CrewType.CONCRETE_POURING: {
                "base_size": 8,
                "skill_levels": {"senior": 2, "intermediate": 4, "junior": 2},
                "equipment": ["concrete_pump", "vibrators", "screeds", "floats"]
            },
            CrewType.FINISHING: {
                "base_size": 4,
                "skill_levels": {"senior": 1, "intermediate": 2, "junior": 1},
                "equipment": ["finishing_tools", "power_floats", "edgers", "joints_tools"]
            }
        }

    def create_execution_plan(
        self,
        elements: List[ElementDetail],
        risks: List[ElementRisk],
        target_duration_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create comprehensive execution plan with crew allocation and sequencing"""

        # Generate construction tasks
        tasks = self._generate_construction_tasks(elements, risks)

        # Create sequencing dependencies
        sequenced_tasks = self._create_task_dependencies(tasks)

        # Optimize crew allocation
        crew_plan = self._optimize_crew_allocation(sequenced_tasks, target_duration_days)

        # Calculate critical path
        critical_path = self._calculate_critical_path(sequenced_tasks)

        # Resource leveling
        leveled_schedule = self._level_resources(sequenced_tasks, crew_plan)

        return {
            "tasks": sequenced_tasks,
            "crew_plan": crew_plan,
            "critical_path": critical_path,
            "schedule": leveled_schedule,
            "total_duration": self._calculate_total_duration(sequenced_tasks),
            "resource_utilization": self._calculate_resource_utilization(crew_plan),
            "bottlenecks": self._identify_bottlenecks(sequenced_tasks, risks)
        }

    def _generate_construction_tasks(
        self,
        elements: List[ElementDetail],
        risks: List[ElementRisk]
    ) -> List[ConstructionTask]:
        """Generate detailed construction tasks for each element"""
        tasks = []
        risk_lookup = {r.element_id: r for r in risks}

        for element in elements:
            element_risk = risk_lookup.get(element.element_id)

            # Generate task sequence for this element
            element_tasks = self._create_element_task_sequence(element, element_risk)
            tasks.extend(element_tasks)

        return tasks

    def _create_element_task_sequence(
        self,
        element: ElementDetail,
        risk: Optional[ElementRisk]
    ) -> List[ConstructionTask]:
        """Create task sequence for a single element"""
        tasks = []
        base_id = f"{element.level_name}_{element.element_id}"

        # Task 1: Formwork
        formwork_task = self._create_formwork_task(base_id, element, risk)
        tasks.append(formwork_task)

        # Task 2: Rebar placing
        rebar_task = self._create_rebar_task(base_id, element, risk)
        rebar_task.predecessors = [formwork_task.task_id]
        tasks.append(rebar_task)

        # Task 3: Concrete pouring
        concrete_task = self._create_concrete_task(base_id, element, risk)
        concrete_task.predecessors = [rebar_task.task_id]
        tasks.append(concrete_task)

        # Task 4: Finishing
        finishing_task = self._create_finishing_task(base_id, element, risk)
        finishing_task.predecessors = [concrete_task.task_id]
        tasks.append(finishing_task)

        return tasks

    def _create_formwork_task(
        self,
        base_id: str,
        element: ElementDetail,
        risk: Optional[ElementRisk]
    ) -> ConstructionTask:
        """Create formwork task"""
        # Calculate duration based on surface area and complexity
        base_hours = element.surface_area / self.productivity_rates[CrewType.FORMWORK] * 8

        # Apply risk and complexity adjustments
        risk_multiplier = 1.0
        if risk and risk.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            risk_multiplier = 1.3

        complexity_multiplier = 1.0 + (element.complexity_score / 10.0)
        duration_hours = base_hours * risk_multiplier * complexity_multiplier

        # Determine crew requirements
        crew_size = max(2, math.ceil(duration_hours / 40))  # Assuming 40 hours per crew per task
        crew_req = CrewRequirement(
            crew_type=CrewType.FORMWORK,
            crew_size=crew_size,
            estimated_hours=duration_hours,
            skill_level="intermediate",
            equipment_needed=self.standard_crews[CrewType.FORMWORK]["equipment"]
        )

        return ConstructionTask(
            task_id=f"{base_id}_formwork",
            element_id=element.element_id,
            level_name=element.level_name,
            task_name=f"Formwork for {element.element_id}",
            duration_hours=duration_hours,
            crew_requirements=[crew_req],
            predecessors=[],
            material_requirements={
                "formwork_panels": element.surface_area * 1.1,  # 10% waste factor
                "bracing_material": element.surface_area * 0.3,
                "release_agent": element.surface_area * 0.05
            }
        )

    def _create_rebar_task(
        self,
        base_id: str,
        element: ElementDetail,
        risk: Optional[ElementRisk]
    ) -> ConstructionTask:
        """Create rebar placing task"""
        # Calculate duration based on rebar weight and complexity
        base_hours = element.total_rebar_weight / (self.productivity_rates[CrewType.REBAR_PLACING] * 100)  # kg per hour

        # Apply risk and complexity adjustments
        risk_multiplier = 1.0
        if risk and risk.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            risk_multiplier = 1.5

        # Factor in bar type complexity
        complexity_multiplier = 1.0 + (element.bar_types / 20.0)
        labor_multiplier = 1.0 + max(0, element.labor_hours_modifier / 2.0)

        duration_hours = base_hours * risk_multiplier * complexity_multiplier * labor_multiplier

        # Determine crew requirements
        crew_size = max(3, math.ceil(duration_hours / 32))  # Assuming 32 hours per crew per task
        skill_level = "senior" if element.complexity_score > 3.0 else "intermediate"

        crew_req = CrewRequirement(
            crew_type=CrewType.REBAR_PLACING,
            crew_size=crew_size,
            estimated_hours=duration_hours,
            skill_level=skill_level,
            equipment_needed=self.standard_crews[CrewType.REBAR_PLACING]["equipment"]
        )

        # Calculate material requirements
        material_reqs = {"rebar_total": element.total_rebar_weight}

        # Add specific diameter requirements
        for diameter, bar_spec in element.bars_by_diameter.items():
            material_reqs[f"rebar_{diameter}"] = bar_spec.weight

        for diameter, stirrup_spec in element.stirrups_by_diameter.items():
            material_reqs[f"stirrups_{diameter}"] = stirrup_spec.weight

        return ConstructionTask(
            task_id=f"{base_id}_rebar",
            element_id=element.element_id,
            level_name=element.level_name,
            task_name=f"Rebar placing for {element.element_id}",
            duration_hours=duration_hours,
            crew_requirements=[crew_req],
            predecessors=[],  # Will be set by caller
            material_requirements=material_reqs
        )

    def _create_concrete_task(
        self,
        base_id: str,
        element: ElementDetail,
        risk: Optional[ElementRisk]
    ) -> ConstructionTask:
        """Create concrete pouring task"""
        # Calculate duration based on concrete volume
        base_hours = element.vol_concreto / self.productivity_rates[CrewType.CONCRETE_POURING] * 8

        # Apply risk adjustments
        risk_multiplier = 1.0
        if risk and risk.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            risk_multiplier = 1.2

        duration_hours = max(4, base_hours * risk_multiplier)  # Minimum 4 hours

        # Determine crew requirements
        crew_size = max(4, math.ceil(element.vol_concreto / 20))  # Scale with volume
        crew_req = CrewRequirement(
            crew_type=CrewType.CONCRETE_POURING,
            crew_size=crew_size,
            estimated_hours=duration_hours,
            skill_level="intermediate",
            equipment_needed=self.standard_crews[CrewType.CONCRETE_POURING]["equipment"]
        )

        return ConstructionTask(
            task_id=f"{base_id}_concrete",
            element_id=element.element_id,
            level_name=element.level_name,
            task_name=f"Concrete pouring for {element.element_id}",
            duration_hours=duration_hours,
            crew_requirements=[crew_req],
            predecessors=[],  # Will be set by caller
            material_requirements={
                "concrete": element.vol_concreto * 1.05,  # 5% waste factor
                "concrete_additives": element.vol_concreto * 0.02
            }
        )

    def _create_finishing_task(
        self,
        base_id: str,
        element: ElementDetail,
        risk: Optional[ElementRisk]
    ) -> ConstructionTask:
        """Create finishing task"""
        # Calculate duration based on surface area
        base_hours = element.surface_area / self.productivity_rates[CrewType.FINISHING] * 8

        # Apply minimal risk adjustment for finishing
        risk_multiplier = 1.0
        if risk and risk.risk_level == RiskLevel.CRITICAL:
            risk_multiplier = 1.1

        duration_hours = max(2, base_hours * risk_multiplier)  # Minimum 2 hours

        # Determine crew requirements
        crew_size = max(2, math.ceil(duration_hours / 24))  # Assuming 24 hours per crew per task
        crew_req = CrewRequirement(
            crew_type=CrewType.FINISHING,
            crew_size=crew_size,
            estimated_hours=duration_hours,
            skill_level="intermediate",
            equipment_needed=self.standard_crews[CrewType.FINISHING]["equipment"]
        )

        return ConstructionTask(
            task_id=f"{base_id}_finishing",
            element_id=element.element_id,
            level_name=element.level_name,
            task_name=f"Finishing for {element.element_id}",
            duration_hours=duration_hours,
            crew_requirements=[crew_req],
            predecessors=[],  # Will be set by caller
            material_requirements={
                "finishing_compounds": element.surface_area * 0.01,
                "curing_compounds": element.surface_area * 0.02
            }
        )

    def _create_task_dependencies(self, tasks: List[ConstructionTask]) -> List[ConstructionTask]:
        """Create inter-element dependencies and optimize sequencing"""
        # Group tasks by level for vertical sequencing
        tasks_by_level = defaultdict(list)
        for task in tasks:
            tasks_by_level[task.level_name].append(task)

        # Define level order (assuming typical building construction)
        level_order = self._determine_level_construction_order(list(tasks_by_level.keys()))

        # Add vertical dependencies (level to level)
        for i, current_level in enumerate(level_order[1:], 1):
            previous_level = level_order[i-1]
            current_tasks = tasks_by_level[current_level]
            previous_tasks = tasks_by_level[previous_level]

            # Current level can only start after previous level concrete is complete
            previous_concrete_tasks = [t for t in previous_tasks if "concrete" in t.task_id]

            for task in current_tasks:
                if "formwork" in task.task_id:  # Formwork can start after previous level concrete
                    task.predecessors.extend([t.task_id for t in previous_concrete_tasks])

        return tasks

    def _determine_level_construction_order(self, levels: List[str]) -> List[str]:
        """Determine optimal construction order for building levels"""
        # Sort levels by typical construction sequence
        def level_sort_key(level: str) -> Tuple[int, str]:
            level_lower = level.lower()
            if "piso" in level_lower:
                # Extract number for floors
                try:
                    num = int(''.join(filter(str.isdigit, level_lower)))
                    return (1, f"{num:02d}")  # Floors in numerical order
                except:
                    return (1, level_lower)
            elif "cubierta" in level_lower:
                return (2, level_lower)  # Roof levels after floors
            else:
                return (0, level_lower)  # Other levels first

        return sorted(levels, key=level_sort_key)

    def _optimize_crew_allocation(
        self,
        tasks: List[ConstructionTask],
        target_duration_days: Optional[int]
    ) -> Dict[str, Any]:
        """Optimize crew allocation across tasks"""
        crew_allocation = defaultdict(list)
        crew_utilization = defaultdict(float)

        # Group tasks by crew type
        tasks_by_crew_type = defaultdict(list)
        for task in tasks:
            for crew_req in task.crew_requirements:
                tasks_by_crew_type[crew_req.crew_type].append((task, crew_req))

        # Calculate optimal crew sizes for each type
        for crew_type, task_crew_pairs in tasks_by_crew_type.items():
            total_hours = sum(crew_req.estimated_hours for _, crew_req in task_crew_pairs)

            if target_duration_days:
                target_hours = target_duration_days * 8  # 8 hours per day
                optimal_crew_count = math.ceil(total_hours / target_hours)
            else:
                # Default optimization for balanced utilization
                optimal_crew_count = max(1, math.ceil(total_hours / 320))  # 320 hours = 40 days * 8 hours

            crew_allocation[crew_type.value] = {
                "crew_count": optimal_crew_count,
                "total_hours_required": total_hours,
                "average_utilization": min(100, (total_hours / (optimal_crew_count * 320)) * 100)
            }

            crew_utilization[crew_type.value] = crew_allocation[crew_type.value]["average_utilization"]

        return {
            "crew_allocation": dict(crew_allocation),
            "crew_utilization": dict(crew_utilization),
            "total_crew_cost": self._estimate_crew_costs(crew_allocation)
        }

    def _calculate_critical_path(self, tasks: List[ConstructionTask]) -> List[str]:
        """Calculate critical path through construction tasks"""
        # Build dependency graph
        task_map = {task.task_id: task for task in tasks}

        # Calculate earliest start times
        earliest_start = {}
        earliest_finish = {}

        # Topological sort for scheduling
        def calculate_earliest_times(task_id: str) -> float:
            if task_id in earliest_finish:
                return earliest_finish[task_id]

            task = task_map[task_id]

            # Calculate earliest start based on predecessors
            if not task.predecessors:
                earliest_start[task_id] = 0
            else:
                earliest_start[task_id] = max(
                    calculate_earliest_times(pred_id) for pred_id in task.predecessors
                )

            # Calculate earliest finish
            earliest_finish[task_id] = earliest_start[task_id] + task.duration_hours
            return earliest_finish[task_id]

        # Calculate for all tasks
        for task in tasks:
            calculate_earliest_times(task.task_id)

        # Find critical path (tasks with zero float)
        project_duration = max(earliest_finish.values())

        # Calculate latest start/finish times
        latest_finish = {}
        latest_start = {}

        # Work backwards from project end
        for task in tasks:
            if not any(task.task_id in other.predecessors for other in tasks):
                # End task
                latest_finish[task.task_id] = earliest_finish[task.task_id]

        def calculate_latest_times(task_id: str) -> float:
            if task_id in latest_start:
                return latest_start[task_id]

            task = task_map[task_id]

            # Find successors
            successors = [t for t in tasks if task_id in t.predecessors]

            if not successors:
                latest_finish[task_id] = earliest_finish[task_id]
            else:
                latest_finish[task_id] = min(
                    calculate_latest_times(succ.task_id) for succ in successors
                )

            latest_start[task_id] = latest_finish[task_id] - task.duration_hours
            return latest_start[task_id]

        # Calculate latest times
        for task in tasks:
            calculate_latest_times(task.task_id)

        # Identify critical tasks (float = 0)
        critical_tasks = []
        for task in tasks:
            float_time = latest_start[task.task_id] - earliest_start[task.task_id]
            if abs(float_time) < 0.1:  # Essentially zero
                critical_tasks.append(task.task_id)

        return critical_tasks

    def _level_resources(
        self,
        tasks: List[ConstructionTask],
        crew_plan: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Perform resource leveling to smooth crew utilization"""
        # Simple resource leveling - create daily schedule
        daily_schedule = []
        current_date = datetime.now()

        # Group tasks by start time (simplified)
        task_schedule = []
        for task in tasks:
            task_schedule.append({
                "task_id": task.task_id,
                "element_id": task.element_id,
                "level_name": task.level_name,
                "task_name": task.task_name,
                "duration_days": math.ceil(task.duration_hours / 8),
                "crew_requirements": task.crew_requirements,
                "start_date": current_date.isoformat(),
                "end_date": (current_date + timedelta(days=math.ceil(task.duration_hours / 8))).isoformat()
            })

        return task_schedule

    def _calculate_total_duration(self, tasks: List[ConstructionTask]) -> float:
        """Calculate total project duration in days"""
        if not tasks:
            return 0

        # Simple calculation - sum of longest path
        total_hours = sum(task.duration_hours for task in tasks)

        # Assume some parallelization (rough estimate)
        parallel_factor = 0.6  # 60% of tasks can be done in parallel
        effective_hours = total_hours * parallel_factor

        return math.ceil(effective_hours / 8)  # Convert to days

    def _calculate_resource_utilization(self, crew_plan: Dict[str, Any]) -> Dict[str, float]:
        """Calculate resource utilization metrics"""
        utilization = {}

        if "crew_allocation" in crew_plan:
            for crew_type, allocation in crew_plan["crew_allocation"].items():
                utilization[crew_type] = allocation.get("average_utilization", 0)

        return utilization

    def _identify_bottlenecks(
        self,
        tasks: List[ConstructionTask],
        risks: List[ElementRisk]
    ) -> List[Dict[str, Any]]:
        """Identify potential schedule bottlenecks"""
        bottlenecks = []

        # High-risk, long-duration tasks
        for task in tasks:
            if task.duration_hours > 40:  # More than 5 days
                element_risk = next((r for r in risks if r.element_id == task.element_id), None)
                if element_risk and element_risk.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                    bottlenecks.append({
                        "task_id": task.task_id,
                        "element_id": task.element_id,
                        "reason": f"High-risk task with long duration ({task.duration_hours:.1f} hours)",
                        "risk_level": element_risk.risk_level.value,
                        "mitigation": "Consider task splitting or additional resources"
                    })

        return bottlenecks

    def _estimate_crew_costs(self, crew_allocation: Dict) -> Dict[str, float]:
        """Estimate crew costs (simplified)"""
        # Simplified cost estimation
        daily_rates = {
            CrewType.REBAR_PLACING.value: 2500,  # $ per crew per day
            CrewType.FORMWORK.value: 2200,
            CrewType.CONCRETE_POURING.value: 2800,
            CrewType.FINISHING.value: 2000
        }

        costs = {}
        total_cost = 0

        for crew_type, allocation in crew_allocation.items():
            if crew_type in daily_rates:
                crew_count = allocation["crew_count"]
                hours = allocation["total_hours_required"]
                days = math.ceil(hours / 8)
                cost = crew_count * days * daily_rates[crew_type]
                costs[crew_type] = cost
                total_cost += cost

        costs["total"] = total_cost
        return costs