#!/usr/bin/env python3
"""
Demonstration of file generation capabilities for Logistics Agent
Shows how to generate all 4 file types
"""

from file_generators import FileGenerator
from datetime import datetime


def main():
    """Demonstrate file generation capabilities."""

    print("="*80)
    print("LOGISTICS AGENT - FILE GENERATION DEMONSTRATION")
    print("="*80)

    generator = FileGenerator(output_dir="logistics_outputs")

    print("\nThis demonstration will generate 4 types of files:")
    print("1. Yard Layout Diagram (PDF)")
    print("2. Truck Unloading Schedule (Excel)")
    print("3. Zone Allocation Map (PDF)")
    print("4. Crane Operation Safety Guidelines (PDF)")

    print("\n" + "="*80)
    print("GENERATING FILES...")
    print("="*80)

    # 1. YARD LAYOUT DIAGRAM
    print("\n[1/4] Generating Yard Layout Diagram...")
    print("      Configuration:")
    print("      - Yard: 30m x 40m")
    print("      - Crane at center (15, 20) with 25m radius")
    print("      - 4 zones: 2 storage, 1 aisle, 1 loading")

    zones = [
        {'id': 'STORAGE-A', 'x': 2, 'y': 2, 'width': 8, 'depth': 12, 'type': 'storage'},
        {'id': 'STORAGE-B', 'x': 18, 'y': 2, 'width': 10, 'depth': 12, 'type': 'storage'},
        {'id': 'AISLE-1', 'x': 10, 'y': 2, 'width': 8, 'depth': 12, 'type': 'aisle'},
        {'id': 'LOADING-1', 'x': 2, 'y': 20, 'width': 26, 'depth': 8, 'type': 'loading'},
        {'id': 'STAGING-1', 'x': 2, 'y': 30, 'width': 26, 'depth': 8, 'type': 'staging'}
    ]

    yard_pdf = generator.generate_yard_layout_pdf(
        yard_width=30,
        yard_depth=40,
        crane_x=15,
        crane_y=20,
        crane_radius=25,
        zones=zones,
        aisle_width=4.0,
        filename="yard_layout_demo.pdf"
    )
    print(f"      [OK] Generated: {yard_pdf}")

    # 2. TRUCK UNLOADING SCHEDULE
    print("\n[2/4] Generating Truck Unloading Schedule...")
    print("      Configuration:")
    print("      - 3 trucks arriving throughout the day")
    print("      - 8 bundles total")
    print("      - Optimized unloading sequence")

    trucks = [
        {'id': 'TRUCK-001', 'arrival_time': '08:00', 'capacity': 20},
        {'id': 'TRUCK-002', 'arrival_time': '10:30', 'capacity': 20},
        {'id': 'TRUCK-003', 'arrival_time': '14:00', 'capacity': 15}
    ]

    bundles = [
        {'id': 'BUNDLE-F5-L01', 'truck_id': 'TRUCK-001', 'weight': 480, 'zone': 'STORAGE-A', 'unload_seq': 1, 'duration': 12},
        {'id': 'BUNDLE-F5-L02', 'truck_id': 'TRUCK-001', 'weight': 520, 'zone': 'STORAGE-A', 'unload_seq': 2, 'duration': 15},
        {'id': 'BUNDLE-F5-T01', 'truck_id': 'TRUCK-001', 'weight': 320, 'zone': 'STORAGE-B', 'unload_seq': 3, 'duration': 10},
        {'id': 'BUNDLE-F6-L01', 'truck_id': 'TRUCK-002', 'weight': 495, 'zone': 'STORAGE-A', 'unload_seq': 1, 'duration': 13},
        {'id': 'BUNDLE-F6-L02', 'truck_id': 'TRUCK-002', 'weight': 510, 'zone': 'STORAGE-B', 'unload_seq': 2, 'duration': 14},
        {'id': 'BUNDLE-F6-T01', 'truck_id': 'TRUCK-002', 'weight': 335, 'zone': 'STORAGE-B', 'unload_seq': 3, 'duration': 11},
        {'id': 'BUNDLE-F7-L01', 'truck_id': 'TRUCK-003', 'weight': 475, 'zone': 'STAGING-1', 'unload_seq': 1, 'duration': 13},
        {'id': 'BUNDLE-F7-T01', 'truck_id': 'TRUCK-003', 'weight': 310, 'zone': 'STAGING-1', 'unload_seq': 2, 'duration': 10}
    ]

    schedule_xlsx = generator.generate_unloading_schedule_excel(
        trucks=trucks,
        bundles=bundles,
        filename="unloading_schedule_demo.xlsx"
    )
    print(f"      [OK] Generated: {schedule_xlsx}")

    # 3. ZONE ALLOCATION MAP
    print("\n[3/4] Generating Zone Allocation Map...")
    print("      Configuration:")
    print("      - Bundles allocated to zones")
    print("      - Grouped by floor")
    print("      - Weight distribution analysis")

    allocations = [
        {'zone_id': 'STORAGE-A', 'bundle_id': 'BUNDLE-F5-L01', 'weight': 480, 'floor': 'Floor 5'},
        {'zone_id': 'STORAGE-A', 'bundle_id': 'BUNDLE-F5-L02', 'weight': 520, 'floor': 'Floor 5'},
        {'zone_id': 'STORAGE-A', 'bundle_id': 'BUNDLE-F6-L01', 'weight': 495, 'floor': 'Floor 6'},
        {'zone_id': 'STORAGE-B', 'bundle_id': 'BUNDLE-F5-T01', 'weight': 320, 'floor': 'Floor 5'},
        {'zone_id': 'STORAGE-B', 'bundle_id': 'BUNDLE-F6-L02', 'weight': 510, 'floor': 'Floor 6'},
        {'zone_id': 'STORAGE-B', 'bundle_id': 'BUNDLE-F6-T01', 'weight': 335, 'floor': 'Floor 6'},
        {'zone_id': 'STAGING-1', 'bundle_id': 'BUNDLE-F7-L01', 'weight': 475, 'floor': 'Floor 7'},
        {'zone_id': 'STAGING-1', 'bundle_id': 'BUNDLE-F7-T01', 'weight': 310, 'floor': 'Floor 7'}
    ]

    zone_pdf = generator.generate_zone_allocation_pdf(
        zones=zones,
        allocations=allocations,
        filename="zone_allocation_demo.pdf"
    )
    print(f"      [OK] Generated: {zone_pdf}")

    # 4. CRANE SAFETY GUIDELINES
    print("\n[4/4] Generating Crane Operation Safety Guidelines...")
    print("      Configuration:")
    print("      - Crane specifications")
    print("      - Safety zones")
    print("      - Operating procedures")

    crane_params = {
        'max_radius': 25,
        'capacity': 10,
        'center_x': 15,
        'center_y': 20,
        'safety_buffer': 2.0
    }

    safety_zones = [
        {
            'name': 'Exclusion Zone',
            'description': 'No personnel allowed during active lift operations',
            'restrictions': '5m radius from lift point - Hard barrier required'
        },
        {
            'name': 'Restricted Access Zone',
            'description': 'Essential personnel only with full PPE and authorization',
            'restrictions': 'Within crane radius, outside exclusion zone - High-visibility vest + hard hat mandatory'
        },
        {
            'name': 'Controlled Access Zone',
            'description': 'General site personnel with awareness training',
            'restrictions': 'Beyond crane radius but within 50m - Must maintain visual contact with spotter'
        }
    ]

    procedures = [
        'Conduct comprehensive pre-operation inspection of crane, rigging equipment, and lift zone',
        'Verify load weight does not exceed rated capacity with appropriate safety factor',
        'Ensure all non-essential personnel are clear of exclusion and restricted zones',
        'Designate and brief a qualified signal person for all lift operations',
        'Maintain continuous two-way radio communication between operator and signal person',
        'Inspect all rigging (slings, shackles, hooks) before each lift - reject if damaged',
        'Never swing or move loads over personnel - enforce strict overhead load prohibition',
        'Monitor weather conditions - cease operations if wind exceeds 30 km/h or in electrical storms',
        'Implement lockout/tagout procedures during maintenance or shift changes',
        'Conduct daily toolbox talks with crane crew covering specific hazards and emergency procedures'
    ]

    safety_pdf = generator.generate_crane_safety_pdf(
        crane_params=crane_params,
        safety_zones=safety_zones,
        procedures=procedures,
        filename="crane_safety_demo.pdf"
    )
    print(f"      [OK] Generated: {safety_pdf}")

    # Summary
    print("\n" + "="*80)
    print("FILE GENERATION COMPLETE")
    print("="*80)

    print("\nGenerated Files:")
    print(f"  1. {yard_pdf}")
    print(f"  2. {schedule_xlsx}")
    print(f"  3. {zone_pdf}")
    print(f"  4. {safety_pdf}")

    print("\nAll files are located in: logistics_outputs/")
    print("\nYou can now:")
    print("  - Open the PDFs to view yard layouts, allocations, and safety guidelines")
    print("  - Open the Excel file to see detailed unloading schedules")
    print("  - Use these files in your actual construction project")

    print("\n" + "="*80)
    print("These file generation capabilities are integrated into the Logistics Agent.")
    print("When you ask the agent to create plans, it will generate these files automatically.")
    print("="*80)


if __name__ == "__main__":
    main()
