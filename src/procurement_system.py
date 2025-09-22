"""
Procurement & Call-Offs system for Phase 2 execution planning.
Manages material procurement, delivery scheduling, and supply chain optimization.
"""

import math
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, field
from phase2_models import (
    ElementDetail, ProcurementItem, ConstructionTask, CrewRequirement
)


@dataclass
class SupplierProfile:
    """Supplier information and capabilities"""
    supplier_id: str
    name: str
    materials_supplied: List[str]
    lead_times: Dict[str, int]  # material -> days
    reliability_score: float  # 0-1 scale
    cost_factors: Dict[str, float]  # material -> cost multiplier
    capacity_limits: Dict[str, float]  # material -> max quantity per delivery


@dataclass
class DeliveryWindow:
    """Material delivery scheduling window"""
    material_type: str
    quantity: float
    earliest_delivery: datetime
    latest_delivery: datetime
    storage_duration_max: int  # days material can be stored on site
    criticality: str  # "critical", "important", "normal"


class ProcurementOptimizer:
    """Material procurement and delivery optimization system"""

    def __init__(self):
        # Initialize default suppliers (in real system, this would be from database)
        self.suppliers = self._initialize_default_suppliers()

        # Material specifications and properties
        self.material_specs = {
            "rebar_3/8\"": {"unit": "kg", "storage_days": 90, "waste_factor": 0.03},
            "rebar_1/2\"": {"unit": "kg", "storage_days": 90, "waste_factor": 0.03},
            "rebar_5/8\"": {"unit": "kg", "storage_days": 90, "waste_factor": 0.03},
            "rebar_3/4\"": {"unit": "kg", "storage_days": 90, "waste_factor": 0.03},
            "rebar_7/8\"": {"unit": "kg", "storage_days": 90, "waste_factor": 0.03},
            "rebar_1\"": {"unit": "kg", "storage_days": 90, "waste_factor": 0.03},
            "concrete": {"unit": "m³", "storage_days": 0, "waste_factor": 0.05},
            "formwork_panels": {"unit": "m²", "storage_days": 180, "waste_factor": 0.02},
            "tie_wire": {"unit": "kg", "storage_days": 365, "waste_factor": 0.01},
            "spacers": {"unit": "pieces", "storage_days": 365, "waste_factor": 0.05}
        }

        # Delivery batching preferences
        self.batching_preferences = {
            "min_delivery_value": 5000,  # Minimum $ value per delivery
            "preferred_delivery_days": [1, 3, 5],  # Monday, Wednesday, Friday
            "max_deliveries_per_day": 3
        }

    def create_procurement_plan(
        self,
        tasks: List[ConstructionTask],
        project_start_date: datetime,
        budget_constraints: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """Create comprehensive procurement plan"""

        # Aggregate material requirements
        material_requirements = self._aggregate_material_requirements(tasks)

        # Create delivery windows based on task scheduling
        delivery_windows = self._create_delivery_windows(tasks, project_start_date)

        # Optimize supplier selection
        supplier_assignments = self._optimize_supplier_selection(
            material_requirements, delivery_windows, budget_constraints
        )

        # Generate procurement schedule
        procurement_schedule = self._create_procurement_schedule(
            material_requirements, delivery_windows, supplier_assignments
        )

        # Calculate costs and logistics
        cost_analysis = self._calculate_procurement_costs(procurement_schedule)

        # Identify risks and mitigation strategies
        risk_analysis = self._analyze_procurement_risks(procurement_schedule)

        return {
            "material_requirements": material_requirements,
            "delivery_windows": delivery_windows,
            "supplier_assignments": supplier_assignments,
            "procurement_schedule": procurement_schedule,
            "cost_analysis": cost_analysis,
            "risk_analysis": risk_analysis,
            "procurement_items": self._generate_procurement_items(procurement_schedule)
        }

    def _initialize_default_suppliers(self) -> Dict[str, SupplierProfile]:
        """Initialize default supplier profiles"""
        suppliers = {}

        # Rebar supplier
        suppliers["steel_supply_co"] = SupplierProfile(
            supplier_id="steel_supply_co",
            name="Steel Supply Company",
            materials_supplied=["rebar_3/8\"", "rebar_1/2\"", "rebar_5/8\"", "rebar_3/4\"", "rebar_7/8\"", "rebar_1\""],
            lead_times={"rebar_3/8\"": 7, "rebar_1/2\"": 7, "rebar_5/8\"": 5, "rebar_3/4\"": 5, "rebar_7/8\"": 10, "rebar_1\"": 10},
            reliability_score=0.92,
            cost_factors={"rebar_3/8\"": 1.0, "rebar_1/2\"": 1.0, "rebar_5/8\"": 1.0, "rebar_3/4\"": 1.0, "rebar_7/8\"": 1.05, "rebar_1\"": 1.05},
            capacity_limits={"rebar_3/8\"": 5000, "rebar_1/2\"": 5000, "rebar_5/8\"": 4000, "rebar_3/4\"": 4000, "rebar_7/8\"": 2000, "rebar_1\"": 2000}
        )

        # Concrete supplier
        suppliers["concrete_solutions"] = SupplierProfile(
            supplier_id="concrete_solutions",
            name="Concrete Solutions Ltd",
            materials_supplied=["concrete", "concrete_additives"],
            lead_times={"concrete": 2, "concrete_additives": 3},
            reliability_score=0.95,
            cost_factors={"concrete": 1.0, "concrete_additives": 1.0},
            capacity_limits={"concrete": 200, "concrete_additives": 50}  # m³ per day
        )

        # Formwork supplier
        suppliers["formwork_rentals"] = SupplierProfile(
            supplier_id="formwork_rentals",
            name="Formwork Rentals Inc",
            materials_supplied=["formwork_panels", "bracing_material", "release_agent"],
            lead_times={"formwork_panels": 5, "bracing_material": 3, "release_agent": 2},
            reliability_score=0.88,
            cost_factors={"formwork_panels": 1.0, "bracing_material": 1.0, "release_agent": 1.0},
            capacity_limits={"formwork_panels": 1000, "bracing_material": 500, "release_agent": 100}
        )

        return suppliers

    def _aggregate_material_requirements(self, tasks: List[ConstructionTask]) -> Dict[str, float]:
        """Aggregate material requirements across all tasks"""
        total_requirements = defaultdict(float)

        for task in tasks:
            for material, quantity in task.material_requirements.items():
                # Apply waste factors
                if material in self.material_specs:
                    waste_factor = self.material_specs[material]["waste_factor"]
                    adjusted_quantity = quantity * (1 + waste_factor)
                else:
                    adjusted_quantity = quantity * 1.05  # Default 5% waste

                total_requirements[material] += adjusted_quantity

        return dict(total_requirements)

    def _create_delivery_windows(
        self,
        tasks: List[ConstructionTask],
        project_start_date: datetime
    ) -> List[DeliveryWindow]:
        """Create delivery windows based on task scheduling"""
        delivery_windows = []

        # Group tasks by material and timing
        material_timeline = defaultdict(list)

        for task in tasks:
            # Estimate task start date (simplified)
            task_start = project_start_date + timedelta(days=hash(task.task_id) % 30)  # Simplified scheduling

            for material, quantity in task.material_requirements.items():
                material_timeline[material].append({
                    "task_id": task.task_id,
                    "quantity": quantity,
                    "needed_date": task_start,
                    "task_duration": task.duration_hours / 8  # Convert to days
                })

        # Create delivery windows for each material
        for material, usage_events in material_timeline.items():
            # Sort by needed date
            usage_events.sort(key=lambda x: x["needed_date"])

            # Group into delivery batches
            current_batch = []
            current_quantity = 0

            for event in usage_events:
                current_batch.append(event)
                current_quantity += event["quantity"]

                # Check if we should create a delivery window
                if (current_quantity >= self._get_min_delivery_quantity(material) or
                    len(current_batch) >= 5):  # Batch multiple small requirements

                    earliest_needed = min(e["needed_date"] for e in current_batch)
                    latest_needed = max(e["needed_date"] for e in current_batch)

                    # Material should arrive 2-7 days before needed
                    earliest_delivery = earliest_needed - timedelta(days=7)
                    latest_delivery = earliest_needed - timedelta(days=2)

                    storage_limit = self.material_specs.get(material, {}).get("storage_days", 30)

                    delivery_window = DeliveryWindow(
                        material_type=material,
                        quantity=current_quantity,
                        earliest_delivery=earliest_delivery,
                        latest_delivery=latest_delivery,
                        storage_duration_max=storage_limit,
                        criticality=self._determine_material_criticality(material, current_batch)
                    )

                    delivery_windows.append(delivery_window)

                    # Reset for next batch
                    current_batch = []
                    current_quantity = 0

            # Handle remaining batch
            if current_batch:
                earliest_needed = min(e["needed_date"] for e in current_batch)
                earliest_delivery = earliest_needed - timedelta(days=7)
                latest_delivery = earliest_needed - timedelta(days=2)

                delivery_window = DeliveryWindow(
                    material_type=material,
                    quantity=current_quantity,
                    earliest_delivery=earliest_delivery,
                    latest_delivery=latest_delivery,
                    storage_duration_max=self.material_specs.get(material, {}).get("storage_days", 30),
                    criticality=self._determine_material_criticality(material, current_batch)
                )

                delivery_windows.append(delivery_window)

        return delivery_windows

    def _get_min_delivery_quantity(self, material: str) -> float:
        """Get minimum economical delivery quantity for material"""
        min_quantities = {
            "concrete": 10,  # m³
            "rebar_3/8\"": 1000,  # kg
            "rebar_1/2\"": 1000,
            "rebar_5/8\"": 1000,
            "rebar_3/4\"": 1000,
            "rebar_7/8\"": 500,
            "rebar_1\"": 500,
            "formwork_panels": 100  # m²
        }
        return min_quantities.get(material, 100)

    def _determine_material_criticality(self, material: str, usage_events: List[Dict]) -> str:
        """Determine criticality of material delivery"""
        # Concrete is always critical (can't be stored)
        if "concrete" in material:
            return "critical"

        # Check if material is on critical path (simplified)
        total_quantity = sum(e["quantity"] for e in usage_events)
        if total_quantity > self._get_min_delivery_quantity(material) * 2:
            return "important"

        return "normal"

    def _optimize_supplier_selection(
        self,
        material_requirements: Dict[str, float],
        delivery_windows: List[DeliveryWindow],
        budget_constraints: Optional[Dict[str, float]]
    ) -> Dict[str, str]:
        """Optimize supplier selection based on cost, reliability, and capacity"""
        assignments = {}

        for material, quantity in material_requirements.items():
            # Find capable suppliers
            capable_suppliers = []

            for supplier_id, supplier in self.suppliers.items():
                if material in supplier.materials_supplied:
                    # Check capacity
                    if material in supplier.capacity_limits:
                        if quantity <= supplier.capacity_limits[material] * 1.2:  # 20% over capacity acceptable with planning
                            capable_suppliers.append(supplier)
                    else:
                        capable_suppliers.append(supplier)

            if not capable_suppliers:
                # No supplier found - this would be an issue to flag
                assignments[material] = "SUPPLIER_NEEDED"
                continue

            # Score suppliers
            best_supplier = None
            best_score = -1

            for supplier in capable_suppliers:
                score = self._score_supplier(supplier, material, quantity, budget_constraints)
                if score > best_score:
                    best_score = score
                    best_supplier = supplier

            if best_supplier:
                assignments[material] = best_supplier.supplier_id

        return assignments

    def _score_supplier(
        self,
        supplier: SupplierProfile,
        material: str,
        quantity: float,
        budget_constraints: Optional[Dict[str, float]]
    ) -> float:
        """Score supplier for material based on multiple criteria"""
        score = 0.0

        # Reliability weight: 40%
        score += supplier.reliability_score * 0.4

        # Cost factor weight: 35% (lower is better)
        cost_factor = supplier.cost_factors.get(material, 1.0)
        cost_score = max(0, 2.0 - cost_factor)  # Score decreases as cost increases
        score += cost_score * 0.35

        # Lead time weight: 15% (shorter is better)
        lead_time = supplier.lead_times.get(material, 14)
        lead_time_score = max(0, 1.0 - (lead_time / 21))  # Normalize against 3 weeks
        score += lead_time_score * 0.15

        # Capacity weight: 10% (adequate capacity is better)
        if material in supplier.capacity_limits:
            capacity_ratio = quantity / supplier.capacity_limits[material]
            capacity_score = max(0, 1.0 - max(0, capacity_ratio - 0.8))  # Penalty if over 80% capacity
        else:
            capacity_score = 0.5  # Neutral score if capacity unknown

        score += capacity_score * 0.1

        return score

    def _create_procurement_schedule(
        self,
        material_requirements: Dict[str, float],
        delivery_windows: List[DeliveryWindow],
        supplier_assignments: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """Create detailed procurement schedule"""
        schedule = []

        for window in delivery_windows:
            material = window.material_type
            supplier_id = supplier_assignments.get(material)

            if not supplier_id or supplier_id == "SUPPLIER_NEEDED":
                continue

            supplier = self.suppliers.get(supplier_id)
            if not supplier:
                continue

            # Calculate optimal delivery date
            lead_time = supplier.lead_times.get(material, 7)
            order_date = window.latest_delivery - timedelta(days=lead_time)

            # Calculate delivery date (prefer delivery window)
            delivery_date = window.latest_delivery

            # Adjust for preferred delivery days
            while delivery_date.weekday() not in [0, 2, 4]:  # Monday, Wednesday, Friday
                delivery_date += timedelta(days=1)

            schedule_item = {
                "material": material,
                "quantity": window.quantity,
                "unit": self.material_specs.get(material, {}).get("unit", "units"),
                "supplier_id": supplier_id,
                "supplier_name": supplier.name,
                "order_date": order_date,
                "delivery_date": delivery_date,
                "lead_time_days": lead_time,
                "criticality": window.criticality,
                "storage_duration_max": window.storage_duration_max,
                "estimated_cost": self._estimate_material_cost(material, window.quantity, supplier)
            }

            schedule.append(schedule_item)

        # Sort by delivery date
        schedule.sort(key=lambda x: x["delivery_date"])

        return schedule

    def _estimate_material_cost(self, material: str, quantity: float, supplier: SupplierProfile) -> float:
        """Estimate material cost (simplified pricing model)"""
        # Base prices (simplified - in real system, this would be from pricing database)
        base_prices = {
            "rebar_3/8\"": 1.20,  # $/kg
            "rebar_1/2\"": 1.25,
            "rebar_5/8\"": 1.30,
            "rebar_3/4\"": 1.35,
            "rebar_7/8\"": 1.40,
            "rebar_1\"": 1.45,
            "concrete": 120,  # $/m³
            "formwork_panels": 15,  # $/m²
            "tie_wire": 2.50,  # $/kg
            "spacers": 0.25  # $/piece
        }

        base_price = base_prices.get(material, 100)  # Default fallback
        cost_factor = supplier.cost_factors.get(material, 1.0)

        return quantity * base_price * cost_factor

    def _calculate_procurement_costs(self, procurement_schedule: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate comprehensive procurement cost analysis"""
        total_cost = 0
        cost_by_category = defaultdict(float)
        cost_by_supplier = defaultdict(float)
        cost_by_month = defaultdict(float)

        for item in procurement_schedule:
            cost = item["estimated_cost"]
            total_cost += cost

            # Categorize costs
            if "rebar" in item["material"]:
                cost_by_category["rebar"] += cost
            elif "concrete" in item["material"]:
                cost_by_category["concrete"] += cost
            else:
                cost_by_category["other"] += cost

            # By supplier
            cost_by_supplier[item["supplier_name"]] += cost

            # By month
            delivery_month = item["delivery_date"].strftime("%Y-%m")
            cost_by_month[delivery_month] += cost

        return {
            "total_cost": total_cost,
            "cost_by_category": dict(cost_by_category),
            "cost_by_supplier": dict(cost_by_supplier),
            "cost_by_month": dict(cost_by_month),
            "average_cost_per_delivery": total_cost / len(procurement_schedule) if procurement_schedule else 0,
            "largest_single_delivery": max((item["estimated_cost"] for item in procurement_schedule), default=0)
        }

    def _analyze_procurement_risks(self, procurement_schedule: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze procurement risks and mitigation strategies"""
        risks = []
        mitigation_strategies = []

        # Single supplier dependency risk
        supplier_materials = defaultdict(list)
        for item in procurement_schedule:
            supplier_materials[item["supplier_id"]].append(item["material"])

        for supplier_id, materials in supplier_materials.items():
            if len(materials) > 3:
                risks.append(f"High dependency on supplier {supplier_id} for {len(materials)} material types")
                mitigation_strategies.append(f"Identify backup suppliers for critical materials from {supplier_id}")

        # Lead time risks
        long_lead_items = [item for item in procurement_schedule if item["lead_time_days"] > 10]
        if long_lead_items:
            risks.append(f"{len(long_lead_items)} items have lead times > 10 days")
            mitigation_strategies.append("Consider early ordering for long lead time items")

        # Critical material risks
        critical_items = [item for item in procurement_schedule if item["criticality"] == "critical"]
        if critical_items:
            risks.append(f"{len(critical_items)} critical materials with tight delivery windows")
            mitigation_strategies.append("Establish expedited delivery protocols for critical materials")

        # Storage capacity risks
        high_storage_items = [item for item in procurement_schedule
                            if item["storage_duration_max"] < 30 and item["quantity"] > 100]
        if high_storage_items:
            risks.append(f"{len(high_storage_items)} items require short-term storage with large quantities")
            mitigation_strategies.append("Plan storage layout and just-in-time delivery sequencing")

        return {
            "identified_risks": risks,
            "mitigation_strategies": mitigation_strategies,
            "risk_score": len(risks) / 10.0,  # Simplified risk scoring
            "high_risk_items": [item["material"] for item in procurement_schedule
                              if item["criticality"] == "critical" and item["lead_time_days"] > 7]
        }

    def _generate_procurement_items(self, procurement_schedule: List[Dict[str, Any]]) -> List[ProcurementItem]:
        """Generate ProcurementItem objects from schedule"""
        items = []

        for schedule_item in procurement_schedule:
            item = ProcurementItem(
                material_type=schedule_item["material"],
                specification=f"{schedule_item['material']} - {schedule_item['quantity']} {schedule_item['unit']}",
                quantity_needed=schedule_item["quantity"],
                unit=schedule_item["unit"],
                delivery_date=schedule_item["delivery_date"],
                lead_time_days=schedule_item["lead_time_days"],
                supplier=schedule_item["supplier_name"],
                cost_per_unit=schedule_item["estimated_cost"] / schedule_item["quantity"]
            )
            items.append(item)

        return items

    def optimize_delivery_batching(
        self,
        procurement_items: List[ProcurementItem],
        site_constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Optimize delivery batching to minimize logistics costs"""
        # Group items by delivery date and supplier
        delivery_groups = defaultdict(list)

        for item in procurement_items:
            key = (item.delivery_date.date(), item.supplier)
            delivery_groups[key].append(item)

        # Optimize batching within each group
        optimized_deliveries = []

        for (delivery_date, supplier), items in delivery_groups.items():
            # Combine compatible items into batches
            total_value = sum(item.cost_per_unit * item.quantity_needed for item in items)

            batch = {
                "delivery_date": delivery_date,
                "supplier": supplier,
                "items": items,
                "total_value": total_value,
                "delivery_fee": self._calculate_delivery_fee(total_value, len(items)),
                "storage_requirements": self._calculate_storage_requirements(items)
            }

            optimized_deliveries.append(batch)

        return {
            "optimized_deliveries": optimized_deliveries,
            "total_deliveries": len(optimized_deliveries),
            "total_delivery_fees": sum(d["delivery_fee"] for d in optimized_deliveries),
            "average_delivery_value": sum(d["total_value"] for d in optimized_deliveries) / len(optimized_deliveries) if optimized_deliveries else 0
        }

    def _calculate_delivery_fee(self, total_value: float, item_count: int) -> float:
        """Calculate delivery fee based on value and complexity"""
        base_fee = 150  # Base delivery fee
        value_factor = max(0, (self.batching_preferences["min_delivery_value"] - total_value) / 1000)
        complexity_factor = item_count * 25  # Additional fee per item type

        return base_fee + value_factor + complexity_factor

    def _calculate_storage_requirements(self, items: List[ProcurementItem]) -> Dict[str, float]:
        """Calculate storage space requirements for items"""
        storage = defaultdict(float)

        for item in items:
            material_type = item.material_type

            if "rebar" in material_type:
                # Rebar storage (approximate space requirements)
                storage["rebar_area_m2"] += item.quantity_needed * 0.002  # kg to m²
            elif "concrete" in material_type:
                storage["concrete_staging_m2"] += 10  # Staging area for trucks
            elif "formwork" in material_type:
                storage["formwork_area_m2"] += item.quantity_needed * 0.1  # m² of panels to storage area

        return dict(storage)