#!/usr/bin/env python3
"""
File generation utilities for ProDet+StructuBIM Logistics Agent
Generates PDF and Excel files for construction logistics planning
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
import numpy as np


class FileGenerator:
    """Generates PDF and Excel files for logistics planning."""

    def __init__(self, output_dir: str = "logistics_outputs"):
        """Initialize file generator."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.styles = getSampleStyleSheet()

        # Custom styles
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=30,
            alignment=TA_CENTER
        )

        self.heading_style = ParagraphStyle(
            'CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=12
        )

    def generate_yard_layout_pdf(
        self,
        yard_width: float,
        yard_depth: float,
        crane_x: float,
        crane_y: float,
        crane_radius: float,
        zones: List[Dict],
        aisle_width: float = 4.0,
        filename: str = None
    ) -> str:
        """
        Generate yard layout diagram as PDF.

        Args:
            yard_width: Yard width in meters
            yard_depth: Yard depth in meters
            crane_x: Crane center X coordinate
            crane_y: Crane center Y coordinate
            crane_radius: Crane operating radius
            zones: List of zone dictionaries with {id, x, y, width, depth, type}
            aisle_width: Width of aisles
            filename: Output filename (optional)

        Returns:
            Path to generated PDF file
        """
        if filename is None:
            filename = f"yard_layout_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        filepath = self.output_dir / filename

        # Create figure
        fig, ax = plt.subplots(figsize=(12, 10))
        ax.set_xlim(0, yard_width)
        ax.set_ylim(0, yard_depth)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        ax.set_xlabel('Width (m)', fontsize=12)
        ax.set_ylabel('Depth (m)', fontsize=12)
        ax.set_title('Yard Layout Plan', fontsize=16, fontweight='bold')

        # Draw yard boundary
        yard_rect = patches.Rectangle(
            (0, 0), yard_width, yard_depth,
            linewidth=2, edgecolor='black', facecolor='none'
        )
        ax.add_patch(yard_rect)

        # Draw crane coverage
        crane_circle = patches.Circle(
            (crane_x, crane_y), crane_radius,
            linewidth=2, edgecolor='blue', facecolor='lightblue', alpha=0.2
        )
        ax.add_patch(crane_circle)

        # Draw crane position
        ax.plot(crane_x, crane_y, 'b^', markersize=15, label='Crane')
        ax.text(crane_x, crane_y - 2, 'CRANE', ha='center', fontsize=10, fontweight='bold')

        # Draw zones
        zone_colors = {
            'storage': 'lightgreen',
            'loading': 'lightyellow',
            'staging': 'lightcoral',
            'aisle': 'lightgray'
        }

        for zone in zones:
            zone_type = zone.get('type', 'storage')
            color = zone_colors.get(zone_type, 'lightgray')

            zone_rect = patches.Rectangle(
                (zone['x'], zone['y']),
                zone['width'],
                zone['depth'],
                linewidth=1,
                edgecolor='black',
                facecolor=color,
                alpha=0.6
            )
            ax.add_patch(zone_rect)

            # Add zone label
            center_x = zone['x'] + zone['width'] / 2
            center_y = zone['y'] + zone['depth'] / 2
            ax.text(
                center_x, center_y,
                zone['id'],
                ha='center', va='center',
                fontsize=8, fontweight='bold'
            )

        # Add legend
        legend_elements = [
            patches.Patch(facecolor='lightgreen', label='Storage Zone'),
            patches.Patch(facecolor='lightyellow', label='Loading Zone'),
            patches.Patch(facecolor='lightcoral', label='Staging Zone'),
            patches.Patch(facecolor='lightgray', label='Aisle'),
            plt.Line2D([0], [0], marker='^', color='w', markerfacecolor='b', markersize=10, label='Crane')
        ]
        ax.legend(handles=legend_elements, loc='upper right', fontsize=10)

        # Add dimensions
        ax.text(yard_width/2, -1.5, f'{yard_width}m', ha='center', fontsize=10)
        ax.text(-1.5, yard_depth/2, f'{yard_depth}m', ha='center', rotation=90, fontsize=10)

        plt.tight_layout()
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def generate_unloading_schedule_excel(
        self,
        trucks: List[Dict],
        bundles: List[Dict],
        filename: str = None
    ) -> str:
        """
        Generate truck unloading schedule as Excel file.

        Args:
            trucks: List of truck dictionaries with {id, arrival_time, capacity}
            bundles: List of bundle dictionaries with {id, truck_id, weight, zone, unload_seq, duration}
            filename: Output filename (optional)

        Returns:
            Path to generated Excel file
        """
        if filename is None:
            filename = f"unloading_schedule_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        filepath = self.output_dir / filename

        # Create Excel writer
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Sheet 1: Truck Schedule
            truck_df = pd.DataFrame(trucks)
            truck_df['arrival_time'] = pd.to_datetime(truck_df['arrival_time'], format='%H:%M')
            truck_df = truck_df.sort_values('arrival_time')
            truck_df['arrival_time'] = truck_df['arrival_time'].dt.strftime('%H:%M')
            truck_df.to_excel(writer, sheet_name='Truck Schedule', index=False)

            # Sheet 2: Unloading Sequence
            bundle_df = pd.DataFrame(bundles)
            bundle_df = bundle_df.sort_values(['truck_id', 'unload_seq'])
            bundle_df.to_excel(writer, sheet_name='Unloading Sequence', index=False)

            # Sheet 3: Summary
            summary_data = {
                'Metric': [
                    'Total Trucks',
                    'Total Bundles',
                    'Total Weight (kg)',
                    'Estimated Unload Time (hours)',
                    'First Truck Arrival',
                    'Last Bundle Unloaded'
                ],
                'Value': [
                    len(trucks),
                    len(bundles),
                    sum(b['weight'] for b in bundles),
                    sum(b['duration'] for b in bundles) / 60,
                    truck_df['arrival_time'].min(),
                    'TBD'
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)

        return str(filepath)

    def generate_zone_allocation_pdf(
        self,
        zones: List[Dict],
        allocations: List[Dict],
        filename: str = None
    ) -> str:
        """
        Generate zone allocation map as PDF.

        Args:
            zones: List of zone dictionaries
            allocations: List of allocation dictionaries with {zone_id, bundle_id, weight, floor}
            filename: Output filename (optional)

        Returns:
            Path to generated PDF file
        """
        if filename is None:
            filename = f"zone_allocation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        filepath = self.output_dir / filename

        # Create PDF
        doc = SimpleDocTemplate(str(filepath), pagesize=A4)
        story = []

        # Title
        title = Paragraph("Zone Allocation Map", self.title_style)
        story.append(title)
        story.append(Spacer(1, 0.3*inch))

        # Summary section
        summary_heading = Paragraph("Allocation Summary", self.heading_style)
        story.append(summary_heading)

        # Create allocation table
        table_data = [['Zone ID', 'Type', 'Bundles', 'Total Weight (kg)', 'Utilization']]

        zone_allocations = {}
        for alloc in allocations:
            zone_id = alloc['zone_id']
            if zone_id not in zone_allocations:
                zone_allocations[zone_id] = {'count': 0, 'weight': 0}
            zone_allocations[zone_id]['count'] += 1
            zone_allocations[zone_id]['weight'] += alloc['weight']

        for zone in zones:
            zone_id = zone['id']
            zone_type = zone.get('type', 'storage')
            alloc = zone_allocations.get(zone_id, {'count': 0, 'weight': 0})

            # Calculate utilization
            max_capacity = zone.get('max_weight', 5000)  # default 5000kg
            if max_capacity > 0:
                utilization = f"{(alloc['weight'] / max_capacity * 100):.1f}%"
            else:
                utilization = "N/A"

            table_data.append([
                zone_id,
                zone_type.title(),
                str(alloc['count']),
                f"{alloc['weight']:.1f}",
                utilization
            ])

        # Create table
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        story.append(table)
        story.append(Spacer(1, 0.5*inch))

        # Detailed allocations
        detail_heading = Paragraph("Detailed Allocations by Floor", self.heading_style)
        story.append(detail_heading)

        # Group by floor
        floor_groups = {}
        for alloc in allocations:
            floor = alloc.get('floor', 'Unknown')
            if floor not in floor_groups:
                floor_groups[floor] = []
            floor_groups[floor].append(alloc)

        for floor in sorted(floor_groups.keys()):
            floor_para = Paragraph(f"<b>Floor: {floor}</b>", self.styles['Normal'])
            story.append(floor_para)

            floor_table_data = [['Bundle ID', 'Zone', 'Weight (kg)']]
            for alloc in floor_groups[floor]:
                floor_table_data.append([
                    alloc['bundle_id'],
                    alloc['zone_id'],
                    f"{alloc['weight']:.1f}"
                ])

            floor_table = Table(floor_table_data)
            floor_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            story.append(floor_table)
            story.append(Spacer(1, 0.2*inch))

        # Build PDF
        doc.build(story)

        return str(filepath)

    def generate_crane_safety_pdf(
        self,
        crane_params: Dict,
        safety_zones: List[Dict],
        procedures: List[str],
        filename: str = None
    ) -> str:
        """
        Generate crane operation safety guidelines as PDF.

        Args:
            crane_params: Crane parameters dictionary
            safety_zones: List of safety zone dictionaries
            procedures: List of safety procedure strings
            filename: Output filename (optional)

        Returns:
            Path to generated PDF file
        """
        if filename is None:
            filename = f"crane_safety_guidelines_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        filepath = self.output_dir / filename

        # Create PDF
        doc = SimpleDocTemplate(str(filepath), pagesize=A4)
        story = []

        # Title
        title = Paragraph("Crane Operation Safety Guidelines", self.title_style)
        story.append(title)
        story.append(Spacer(1, 0.3*inch))

        # Date and project info
        date_para = Paragraph(
            f"<b>Date:</b> {datetime.now().strftime('%Y-%m-%d')}<br/>"
            f"<b>Project:</b> Reinforcement Installation",
            self.styles['Normal']
        )
        story.append(date_para)
        story.append(Spacer(1, 0.3*inch))

        # Crane specifications
        spec_heading = Paragraph("Crane Specifications", self.heading_style)
        story.append(spec_heading)

        spec_data = [
            ['Parameter', 'Value'],
            ['Maximum Radius', f"{crane_params.get('max_radius', 'N/A')} m"],
            ['Lift Capacity', f"{crane_params.get('capacity', 'N/A')} tonnes"],
            ['Boom Center', f"({crane_params.get('center_x', 0)}, {crane_params.get('center_y', 0)})"],
            ['Safety Buffer', f"{crane_params.get('safety_buffer', 2.0)} m"]
        ]

        spec_table = Table(spec_data)
        spec_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige)
        ]))

        story.append(spec_table)
        story.append(Spacer(1, 0.4*inch))

        # Safety zones
        zone_heading = Paragraph("Safety Zones", self.heading_style)
        story.append(zone_heading)

        for i, zone in enumerate(safety_zones, 1):
            zone_para = Paragraph(
                f"<b>Zone {i}: {zone['name']}</b><br/>"
                f"Description: {zone['description']}<br/>"
                f"Restrictions: {zone['restrictions']}",
                self.styles['Normal']
            )
            story.append(zone_para)
            story.append(Spacer(1, 0.15*inch))

        story.append(Spacer(1, 0.3*inch))

        # Safety procedures
        proc_heading = Paragraph("Safety Procedures", self.heading_style)
        story.append(proc_heading)

        for i, procedure in enumerate(procedures, 1):
            proc_para = Paragraph(f"{i}. {procedure}", self.styles['Normal'])
            story.append(proc_para)
            story.append(Spacer(1, 0.1*inch))

        # Build PDF
        doc.build(story)

        return str(filepath)


# Standalone test function
if __name__ == "__main__":
    print("Testing File Generators...")

    generator = FileGenerator()

    # Test 1: Yard Layout
    print("\n1. Generating yard layout...")
    zones = [
        {'id': 'Z1', 'x': 2, 'y': 2, 'width': 8, 'depth': 10, 'type': 'storage'},
        {'id': 'Z2', 'x': 14, 'y': 2, 'width': 8, 'depth': 10, 'type': 'storage'},
        {'id': 'A1', 'x': 10, 'y': 2, 'width': 4, 'depth': 10, 'type': 'aisle'},
        {'id': 'L1', 'x': 2, 'y': 14, 'width': 20, 'depth': 6, 'type': 'loading'}
    ]
    yard_pdf = generator.generate_yard_layout_pdf(
        yard_width=30, yard_depth=40,
        crane_x=15, crane_y=20,
        crane_radius=25,
        zones=zones
    )
    print(f"   Generated: {yard_pdf}")

    # Test 2: Unloading Schedule
    print("\n2. Generating unloading schedule...")
    trucks = [
        {'id': 'T1', 'arrival_time': '08:00', 'capacity': 20},
        {'id': 'T2', 'arrival_time': '10:00', 'capacity': 20}
    ]
    bundles = [
        {'id': 'B1', 'truck_id': 'T1', 'weight': 500, 'zone': 'Z1', 'unload_seq': 1, 'duration': 15},
        {'id': 'B2', 'truck_id': 'T1', 'weight': 600, 'zone': 'Z2', 'unload_seq': 2, 'duration': 20},
        {'id': 'B3', 'truck_id': 'T2', 'weight': 550, 'zone': 'Z1', 'unload_seq': 1, 'duration': 18}
    ]
    schedule_xlsx = generator.generate_unloading_schedule_excel(trucks, bundles)
    print(f"   Generated: {schedule_xlsx}")

    # Test 3: Zone Allocation
    print("\n3. Generating zone allocation...")
    allocations = [
        {'zone_id': 'Z1', 'bundle_id': 'B1', 'weight': 500, 'floor': 'Floor 5'},
        {'zone_id': 'Z1', 'bundle_id': 'B3', 'weight': 550, 'floor': 'Floor 6'},
        {'zone_id': 'Z2', 'bundle_id': 'B2', 'weight': 600, 'floor': 'Floor 5'}
    ]
    zone_pdf = generator.generate_zone_allocation_pdf(zones, allocations)
    print(f"   Generated: {zone_pdf}")

    # Test 4: Crane Safety
    print("\n4. Generating crane safety guidelines...")
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
            'description': 'No personnel allowed during lifts',
            'restrictions': '5m radius from lift point'
        },
        {
            'name': 'Restricted Zone',
            'description': 'Essential personnel only with PPE',
            'restrictions': 'Within crane radius, outside exclusion zone'
        }
    ]
    procedures = [
        'Conduct pre-operation inspection of crane',
        'Verify load weight does not exceed capacity',
        'Ensure all personnel are clear of lift zone',
        'Use designated signal person for all lifts',
        'Maintain constant communication with operator',
        'Inspect rigging before each lift',
        'Never swing loads over personnel'
    ]
    safety_pdf = generator.generate_crane_safety_pdf(crane_params, safety_zones, procedures)
    print(f"   Generated: {safety_pdf}")

    print("\nAll files generated successfully in 'logistics_outputs' directory!")
