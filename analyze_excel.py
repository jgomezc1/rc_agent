#!/usr/bin/env python3
"""
Analyze detailed_report.xlsx structure
"""
import pandas as pd
import openpyxl
import sys

xlsx_path = 'data/detailed_report.xlsx'

# Get all sheet names
wb = openpyxl.load_workbook(xlsx_path)
sheets = wb.sheetnames

print('=== DETAILED_REPORT.XLSX STRUCTURE ANALYSIS ===\n')
print(f'Total sheets: {len(sheets)}')
print('\nSheet names:')
for i, s in enumerate(sheets, 1):
    print(f'  {i}. {s}')

print('\n' + '='*80 + '\n')

# Analyze each sheet
for sheet_name in sheets:
    print(f'\n--- SHEET: {sheet_name} ---\n')
    df = pd.read_excel(xlsx_path, sheet_name=sheet_name)
    print(f'Dimensions: {df.shape[0]} rows x {df.shape[1]} columns')

    # Skip first few rows that might be headers and find the actual data start
    print(f'\nFirst 10 rows (raw):')
    for idx in range(min(10, len(df))):
        row_vals = []
        for col_idx in range(min(5, len(df.columns))):
            val = df.iloc[idx, col_idx]
            if pd.notna(val):
                row_vals.append(f'{str(val)[:40]}')
            else:
                row_vals.append('NaN')
        print(f'  Row {idx}: {" | ".join(row_vals)}')

    # Try to identify header row
    print(f'\nColumn headers (from row 0):')
    for i, col in enumerate(df.columns):
        print(f'  Col {i}: {col}')

    print('\n' + '-'*80)

print('\n=== END OF ANALYSIS ===')
