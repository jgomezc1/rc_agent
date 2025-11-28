"""
Procurement Agent v1 - Reinforcement Data Review & Procurement Planning

This module implements an AI agent that reviews reinforcement solution files
and assists with procurement planning using LangChain Expression Language (LCEL)
with OpenAI as the LLM.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

import pandas as pd
import numpy as np
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

# PDF generation imports
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("reportlab not installed. PDF generation will be disabled.")

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# ProDet File Schema Documentation
# =============================================================================

PRODET_SCHEMA = {
    'Resumen_Refuerzo': {
        'description': 'Story-by-story steel totals',
        'purpose': 'High-level monitoring, comparing solutions, total tonnage per level',
        'header_row': 2,  # Row 0 = project name, Row 1 = labels, Row 2 = units
        'columns': {
            'Nivel': {'standard': 'level', 'description': 'Building level name (e.g., PISO 2, CUBIERTA)'},
            'Ref.Longitudinal': {'standard': 'long_steel_tonf', 'description': 'Longitudinal steel [tonf]'},
            'Ref.Transversal': {'standard': 'trans_steel_tonf', 'description': 'Transverse steel [tonf]'},
            'Total por nivel': {'standard': 'total_steel_tonf', 'description': 'Total steel per level [tonf]'},
        },
        'has_totals_row': True,
        'totals_row_label': 'TOTALES',
    },
    'RefLong_PorElemento': {
        'description': 'Longitudinal reinforcement by element (beams)',
        'purpose': 'Element-level detail, QA, constructability, per-floor breakdown',
        'header_row': 1,  # Row 0 = labels, Row 1 = units
        'columns': {
            'Piso': {'standard': 'level', 'description': 'Story name'},
            'Elemento': {'standard': 'element_id', 'description': 'Element ID (e.g., V-3, V-7A)'},
            'Figura': {'standard': 'shape', 'description': 'Bar shape/figure code'},
            'Calibre': {'standard': 'bar_diameter', 'description': 'Bar diameter (e.g., 5/8", 3/4")'},
            'L_recta': {'standard': 'straight_length', 'description': 'Straight length [m]'},
            'L_gancho_izq': {'standard': 'hook_left', 'description': 'Left hook length [m]'},
            'L_gancho_der': {'standard': 'hook_right', 'description': 'Right hook length [m]'},
            'L_total': {'standard': 'total_length', 'description': 'Total bar length [m]'},
            'Cantidad': {'standard': 'bar_count', 'description': 'Number of bars'},
            'Peso': {'standard': 'weight_kgf', 'description': 'Weight [kgf]'},
        },
        'figure_legend': {
            '|': 'Barra Recta (straight bar)',
            'L': 'Barra con gancho a 90° en un extremo',
            'LL': 'Barra con gancho a 90° en ambos extremos',
            'U': 'Barra con gancho a 180° en un extremo',
            'UU': 'Barra con gancho a 180° en ambos extremos',
            'LU': 'Barra con gancho a 90° y 180° en extremos',
            '├': 'Barra con cabeza en un extremo',
            '├├': 'Barra con cabeza en ambos extremos',
        },
    },
    'RefLong_Total': {
        'description': 'Longitudinal reinforcement totals by bar type (global)',
        'purpose': 'Procurement, fabrication, cutting lists, purchase orders',
        'header_row': 2,  # Row 0 = title, Row 1 = labels, Row 2 = units
        'columns': {
            'Figura': {'standard': 'shape', 'description': 'Bar shape code'},
            'Calibre': {'standard': 'bar_diameter', 'description': 'Bar size'},
            'L_recta': {'standard': 'straight_length', 'description': 'Straight length [m]'},
            'L_gancho_izq': {'standard': 'hook_left', 'description': 'Left hook [m]'},
            'L_gancho_der': {'standard': 'hook_right', 'description': 'Right hook [m]'},
            'L_total': {'standard': 'total_length', 'description': 'Total length [m]'},
            'Cantidad': {'standard': 'bar_count', 'description': 'Total count in project'},
            'Peso': {'standard': 'weight_kgf', 'description': 'Total weight [kgf]'},
        },
    },
    'RefTrans_PorElemento': {
        'description': 'Transverse reinforcement (stirrups) by element',
        'purpose': 'Element-level stirrup sizes and quantities',
        'header_row': 1,
        'columns': {
            'Piso': {'standard': 'level', 'description': 'Story name'},
            'Elemento': {'standard': 'element_id', 'description': 'Element ID'},
            'Figura': {'standard': 'shape', 'description': 'Stirrup shape code'},
            'Calibre': {'standard': 'bar_diameter', 'description': 'Bar size (e.g., 3/8")'},
            'Base': {'standard': 'stirrup_base', 'description': 'Stirrup base dimension [m]'},
            'Altura': {'standard': 'stirrup_height', 'description': 'Stirrup height [m]'},
            'Cantidad': {'standard': 'bar_count', 'description': 'Number of stirrups'},
            'Peso': {'standard': 'weight_kgf', 'description': 'Weight [kgf]'},
        },
        'figure_legend': {
            '[]': 'Estribo cerrado rectangular (closed rectangular stirrup)',
            '[': 'Rama de estribo (stirrup leg)',
        },
    },
    'RefTrans_Total': {
        'description': 'Transverse reinforcement totals by stirrup type (global)',
        'purpose': 'Procurement, global stirrup list',
        'header_row': 1,
        'columns': {
            'Figura': {'standard': 'shape', 'description': 'Stirrup shape code'},
            'Calibre': {'standard': 'bar_diameter', 'description': 'Bar size'},
            'Base': {'standard': 'stirrup_base', 'description': 'Stirrup base [m]'},
            'Altura': {'standard': 'stirrup_height', 'description': 'Stirrup height [m]'},
            'Cantidad': {'standard': 'bar_count', 'description': 'Total count'},
            'Peso': {'standard': 'weight_kgf', 'description': 'Total weight [kgf]'},
        },
    },
}

# Sheet categories for different use cases
SHEET_CATEGORIES = {
    'summary': ['Resumen_Refuerzo'],
    'detail_longitudinal': ['RefLong_PorElemento'],
    'detail_transverse': ['RefTrans_PorElemento'],
    'procurement_longitudinal': ['RefLong_Total'],
    'procurement_transverse': ['RefTrans_Total'],
    'element_detail': ['RefLong_PorElemento', 'RefTrans_PorElemento'],
    'procurement': ['RefLong_Total', 'RefTrans_Total'],
}


# =============================================================================
# Column Mappings (Updated for ProDet Schema)
# =============================================================================

COLUMN_SYNONYMS = {
    'level': ['level', 'nivel', 'floor', 'piso', 'story', 'planta'],
    'element_id': ['element_id', 'id', 'elemento', 'element', 'marca', 'mark', 'id_elemento'],
    'element_type': ['element_type', 'type', 'tipo', 'familia', 'family', 'category'],
    'bar_diameter': ['bar_diameter', 'diameter', 'diametro', 'calibre', 'bar_size', 'size', 'no'],
    'bar_count': ['bar_count', 'count', 'cantidad', 'quantity', 'qty', 'no_bars', 'num_bars'],
    'bar_length': ['bar_length', 'length', 'longitud', 'largo', 'l_total'],
    'straight_length': ['straight_length', 'l_recta', 'recta'],
    'total_length': ['total_length', 'l_total', 'longitud_total', 'total'],
    'weight_kgf': ['weight_kgf', 'weight_kg', 'weight', 'peso', 'peso_kg', 'kg', 'kgf'],
    'weight_tonf': ['weight_tonf', 'tonf', 'peso_tonf', 'ton', 'steel_tonf', 'total por nivel', 'total_por_nivel'],
    'shape': ['shape', 'figura', 'forma', 'shape_code', 'tipo_gancho', 'hook'],
    'hook_left': ['hook_left', 'l_gancho_izq', 'gancho_izq'],
    'hook_right': ['hook_right', 'l_gancho_der', 'gancho_der'],
    'stirrup_base': ['stirrup_base', 'base'],
    'stirrup_height': ['stirrup_height', 'altura', 'height'],
    'long_steel_tonf': ['long_steel_tonf', 'ref.longitudinal', 'longitudinal'],
    'trans_steel_tonf': ['trans_steel_tonf', 'ref.transversal', 'transversal'],
}

# Different required columns based on sheet type
REQUIRED_COLUMNS_BY_SHEET = {
    'Resumen_Refuerzo': ['level', 'weight_tonf'],
    'RefLong_PorElemento': ['level', 'element_id', 'bar_diameter', 'bar_count', 'weight_kgf'],
    'RefLong_Total': ['shape', 'bar_diameter', 'bar_count', 'weight_kgf'],
    'RefTrans_PorElemento': ['level', 'element_id', 'bar_diameter', 'bar_count', 'weight_kgf'],
    'RefTrans_Total': ['shape', 'bar_diameter', 'bar_count', 'weight_kgf'],
}

# Default for unknown sheets
REQUIRED_COLUMNS = ['level', 'element_id', 'bar_diameter']
RECOMMENDED_COLUMNS = ['bar_count', 'weight_kgf', 'total_length']


# =============================================================================
# Data Models
# =============================================================================

class ColumnInfo(BaseModel):
    """Information about a detected column."""
    original_name: str
    mapped_to: Optional[str]
    sample_values: List[Any]
    dtype: str
    null_count: int
    unique_count: int


class ValidationIssue(BaseModel):
    """A validation issue found in the data."""
    severity: str  # 'error', 'warning', 'info'
    category: str
    message: str
    affected_rows: Optional[int] = None
    examples: List[str] = []


class SheetReviewResult(BaseModel):
    """Review result for a single sheet."""
    sheet_name: str
    total_rows: int
    total_columns: int
    columns_detected: List[ColumnInfo]
    columns_missing: List[str]
    validation_issues: List[ValidationIssue]
    data_summary: Dict[str, Any]
    is_valid: bool


class FileReviewResult(BaseModel):
    """Complete result from file review."""
    file_path: str
    file_size_kb: float
    total_rows: int
    total_columns: int
    sheets_count: int = 1
    sheets: List[SheetReviewResult] = []
    columns_detected: List[ColumnInfo]
    columns_missing: List[str]
    validation_issues: List[ValidationIssue]
    data_summary: Dict[str, Any]
    is_valid: bool
    recommendations: List[str]


# =============================================================================
# Core Review Logic
# =============================================================================

class ReinforcementFileReviewer:
    """
    Reviews reinforcement solution files for completeness and clarity.
    """

    def __init__(self):
        self.issues: List[ValidationIssue] = []

    def _add_issue(self, severity: str, category: str, message: str,
                   affected_rows: int = None, examples: List[str] = None):
        self.issues.append(ValidationIssue(
            severity=severity,
            category=category,
            message=message,
            affected_rows=affected_rows,
            examples=examples or []
        ))

    def _detect_header_row(self, df_preview: pd.DataFrame, sheet_name: str = None) -> int:
        """Auto-detect which row contains the headers.

        For known ProDet sheets, uses the schema-defined header row.
        For unknown sheets, uses keyword-based detection.
        """
        # Use ProDet schema if sheet is known
        if sheet_name and sheet_name in PRODET_SCHEMA:
            schema = PRODET_SCHEMA[sheet_name]
            # The 'header_row' in schema is the row INDEX (0-based) where column labels are
            # For most sheets: row 0 = title, row 1 = column labels
            # For Resumen: row 0 = title, row 1 = project, row 2 = column labels
            if 'header_row' in schema:
                # Adjust: schema header_row is where data starts, labels are one row before
                # Actually, we need to use the row that contains Figura, Calibre, etc.
                # Looking at the data:
                #   RefLong_PorElemento: row 1 has Piso, Elemento, etc. (correct)
                #   RefLong_Total: row 1 has Figura, Calibre, etc. (need this)
                #   Resumen_Refuerzo: row 2 has Nivel, Ref.Longitudinal (correct)
                header_map = {
                    'Resumen_Refuerzo': 2,
                    'RefLong_PorElemento': 1,
                    'RefLong_Total': 1,  # Row 1 has the column labels
                    'RefTrans_PorElemento': 1,
                    'RefTrans_Total': 1,  # Row 1 has Figura, Calibre, etc.
                }
                return header_map.get(sheet_name, 0)

        # Fallback: keyword-based detection
        header_keywords = ['nivel', 'level', 'floor', 'piso', 'element', 'elemento',
                          'diameter', 'diametro', 'bar', 'barra', 'peso', 'weight',
                          'figura', 'calibre', 'cantidad', 'base', 'altura']

        best_row = 0
        best_matches = 0

        for row_idx in range(min(10, len(df_preview))):
            row_values = [str(v).lower().strip() for v in df_preview.iloc[row_idx] if pd.notna(v)]

            if len(row_values) < 2:
                continue

            # Count exact column name matches (not substring in title)
            matches = 0
            for val in row_values:
                # Check if the value IS a keyword, not just contains it
                if val in header_keywords:
                    matches += 2  # Higher weight for exact match
                elif any(kw in val for kw in header_keywords):
                    # Only count if it's a short value (likely a column name, not a title)
                    if len(val) < 30:
                        matches += 1

            if matches > best_matches:
                best_matches = matches
                best_row = row_idx

        return best_row if best_matches >= 2 else 0

    def _find_column_mapping(self, columns: List[str]) -> Dict[str, str]:
        """Map actual column names to standard names."""
        mapping = {}
        columns_lower = {col: col.lower().strip().replace(' ', '_') for col in columns}

        for standard_name, synonyms in COLUMN_SYNONYMS.items():
            for col, col_lower in columns_lower.items():
                if col_lower in synonyms or any(syn in col_lower for syn in synonyms):
                    if standard_name not in mapping:
                        mapping[standard_name] = col
                    break

        return mapping

    def get_sheet_names(self, file_path: str) -> List[str]:
        """Get list of sheet names from an Excel file."""
        if file_path.endswith('.xlsx') or file_path.endswith('.xls'):
            xlsx = pd.ExcelFile(file_path)
            return xlsx.sheet_names
        return []

    def load_sheet(self, file_path: str, sheet_name: str = None) -> tuple:
        """Load a single sheet with auto-detected header row."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if file_path.endswith('.xlsx') or file_path.endswith('.xls'):
            df_preview = pd.read_excel(file_path, sheet_name=sheet_name, header=None, nrows=15)
            header_row = self._detect_header_row(df_preview, sheet_name=sheet_name)
            df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row)
        elif file_path.endswith('.csv'):
            df_preview = pd.read_csv(file_path, header=None, nrows=15)
            header_row = self._detect_header_row(df_preview)
            df = pd.read_csv(file_path, header=header_row)
        else:
            raise ValueError(f"Unsupported file format: {file_path}")

        # Clean column names
        df.columns = [str(c).strip() if pd.notna(c) else f'unnamed_{i}'
                      for i, c in enumerate(df.columns)]

        # Filter out units row (row after header that contains -, #, m, kgf, etc.)
        if len(df) > 0:
            first_row = df.iloc[0]
            units_indicators = ['-', '#', 'm', 'kgf', 'tonf', 'nombre']
            if all(str(v).lower().strip() in units_indicators or pd.isna(v)
                   for v in first_row.values[:min(6, len(first_row))]):
                df = df.iloc[1:].reset_index(drop=True)

        return df, header_row

    def load_file(self, file_path: str) -> pd.DataFrame:
        """Load the file with auto-detected header row (first sheet for Excel)."""
        return self.load_sheet(file_path, sheet_name=0)

    def validate_data(self, df: pd.DataFrame, column_mapping: Dict[str, str], sheet_name: str = None):
        """Run validation checks on the data."""

        # Check for empty dataframe
        if len(df) == 0:
            self._add_issue('error', 'data', 'Sheet contains no data rows')
            return

        # Get sheet-specific required columns or use default
        required_cols = REQUIRED_COLUMNS_BY_SHEET.get(sheet_name, REQUIRED_COLUMNS)

        # Check required columns for this sheet type
        for req_col in required_cols:
            if req_col not in column_mapping:
                self._add_issue('error', 'schema', f"Required column '{req_col}' not found")

        # Check recommended columns (only if not in required)
        for rec_col in RECOMMENDED_COLUMNS:
            if rec_col not in column_mapping and rec_col not in required_cols:
                self._add_issue('info', 'schema', f"Optional column '{rec_col}' not found")

        # Validate level column (for sheets that have it)
        if 'level' in column_mapping:
            level_col = column_mapping['level']
            null_levels = df[level_col].isna().sum()
            if null_levels > 0:
                self._add_issue('warning', 'data', f"Found {null_levels} rows with missing level",
                               affected_rows=null_levels)

            # Check for suspicious level values (expected in some sheets like Resumen)
            levels = df[level_col].dropna().astype(str).unique()
            # TOTALES is expected in Resumen_Refuerzo
            if sheet_name == 'Resumen_Refuerzo':
                suspicious = [l for l in levels if l.lower() in ['nan', '']]
            else:
                suspicious = [l for l in levels if l.lower() in ['nan', '-', '']]
            if suspicious:
                self._add_issue('warning', 'data', f"Suspicious level values found: {suspicious}")

        # Validate bar_diameter column - ProDet uses string format like "5/8", "3/4"
        if 'bar_diameter' in column_mapping:
            dia_col = column_mapping['bar_diameter']
            # Check for null values
            null_dias = df[dia_col].isna().sum()
            if null_dias > 0:
                self._add_issue('warning', 'data', f"Found {null_dias} rows with missing diameter",
                               affected_rows=null_dias)

            # ProDet uses fractional notation (5/8", 3/4") which is valid
            # Only flag truly empty or invalid values
            valid_patterns = df[dia_col].dropna().astype(str)
            invalid = valid_patterns[valid_patterns.str.strip() == '']
            if len(invalid) > 0:
                self._add_issue('warning', 'data',
                               f"Found {len(invalid)} empty diameter values",
                               affected_rows=len(invalid))

            # List unique diameters found (for summary, not validation)
            unique_dias = valid_patterns[valid_patterns.str.strip() != ''].unique()
            if len(unique_dias) > 0:
                self._add_issue('info', 'data',
                               f"Bar diameters found: {sorted(set(unique_dias))[:10]}")

        # Validate weight columns
        for weight_col in ['weight_kgf', 'weight_tonf']:
            if weight_col in column_mapping:
                col = column_mapping[weight_col]
                df['_weight'] = pd.to_numeric(df[col], errors='coerce')
                negative = df[df['_weight'] < 0]
                if len(negative) > 0:
                    self._add_issue('error', 'data',
                                   f"Found {len(negative)} rows with negative weight values",
                                   affected_rows=len(negative))
                df.drop('_weight', axis=1, inplace=True)

        # Check for duplicate rows
        if 'element_id' in column_mapping and 'bar_diameter' in column_mapping:
            subset = [column_mapping.get('level'), column_mapping.get('element_id'),
                     column_mapping.get('bar_diameter')]
            subset = [c for c in subset if c]
            duplicates = df.duplicated(subset=subset, keep=False)
            dup_count = duplicates.sum()
            if dup_count > 0:
                self._add_issue('info', 'data',
                               f"Found {dup_count} potentially duplicate rows (same level/element/diameter)",
                               affected_rows=dup_count)

    def compute_summary(self, df: pd.DataFrame, column_mapping: Dict[str, str], sheet_name: str = None) -> Dict[str, Any]:
        """Compute data summary statistics."""
        summary = {
            'total_rows': len(df),
        }

        # Add sheet description if known
        if sheet_name and sheet_name in PRODET_SCHEMA:
            summary['sheet_type'] = PRODET_SCHEMA[sheet_name]['description']
            summary['sheet_purpose'] = PRODET_SCHEMA[sheet_name]['purpose']

        # Levels summary
        if 'level' in column_mapping:
            levels = df[column_mapping['level']].dropna().unique()
            # Filter out TOTALES row for Resumen_Refuerzo
            levels = [l for l in levels if str(l).upper() not in ['TOTALES', '-']]
            summary['unique_levels'] = len(levels)
            summary['levels'] = sorted([str(l) for l in levels], key=lambda x: (
                # Try to sort numerically if possible
                int(''.join(filter(str.isdigit, x)) or 0),
                x
            ))

        # Elements summary (for detail sheets)
        if 'element_id' in column_mapping:
            elements = df[column_mapping['element_id']].dropna().unique()
            summary['unique_elements'] = len(elements)
            # Show sample elements
            summary['sample_elements'] = list(elements[:5])

        # Shape/Figure summary
        if 'shape' in column_mapping:
            shapes = df[column_mapping['shape']].dropna().unique()
            summary['bar_shapes'] = list(shapes)

        # Diameters summary - ProDet uses string format like "5/8", "3/4"
        if 'bar_diameter' in column_mapping:
            dias = df[column_mapping['bar_diameter']].dropna().astype(str).unique()
            dias = [d for d in dias if d.strip() and d.strip() != '-']
            summary['bar_diameters'] = sorted(list(set(dias)))

        # Bar count summary
        if 'bar_count' in column_mapping:
            total_bars = pd.to_numeric(df[column_mapping['bar_count']], errors='coerce').sum()
            summary['total_bar_count'] = int(total_bars) if not pd.isna(total_bars) else 0

        # Total weight - check kgf first (more common in ProDet), then tonf
        if 'weight_kgf' in column_mapping:
            total_kgf = pd.to_numeric(df[column_mapping['weight_kgf']], errors='coerce').sum()
            summary['total_weight_kgf'] = round(total_kgf, 2)
            summary['total_weight_tonf'] = round(total_kgf / 1000, 2)
        elif 'weight_tonf' in column_mapping:
            total_tonf = pd.to_numeric(df[column_mapping['weight_tonf']], errors='coerce').sum()
            summary['total_weight_tonf'] = round(total_tonf, 2)
            summary['total_weight_kgf'] = round(total_tonf * 1000, 2)

        # Longitudinal vs Transverse (for Resumen_Refuerzo)
        if 'long_steel_tonf' in column_mapping:
            long_tonf = pd.to_numeric(df[column_mapping['long_steel_tonf']], errors='coerce').sum()
            summary['longitudinal_steel_tonf'] = round(long_tonf, 2)
        if 'trans_steel_tonf' in column_mapping:
            trans_tonf = pd.to_numeric(df[column_mapping['trans_steel_tonf']], errors='coerce').sum()
            summary['transverse_steel_tonf'] = round(trans_tonf, 2)

        return summary

    def generate_recommendations(self, column_mapping: Dict[str, str]) -> List[str]:
        """Generate recommendations based on review findings."""
        recommendations = []

        # Missing columns recommendations
        missing_required = [c for c in REQUIRED_COLUMNS if c not in column_mapping]
        missing_recommended = [c for c in RECOMMENDED_COLUMNS if c not in column_mapping]

        if missing_required:
            recommendations.append(
                f"Add missing required columns: {', '.join(missing_required)}. "
                "These are essential for procurement planning."
            )

        if missing_recommended:
            recommendations.append(
                f"Consider adding: {', '.join(missing_recommended)}. "
                "These help with detailed quantity takeoffs."
            )

        # Error-based recommendations
        errors = [i for i in self.issues if i.severity == 'error']
        if errors:
            recommendations.append(
                f"Fix {len(errors)} error(s) before using this file for procurement."
            )

        if not recommendations:
            recommendations.append("File is ready for procurement analysis.")

        return recommendations

    def review_sheet(self, file_path: str, sheet_name: str) -> SheetReviewResult:
        """Review a single sheet."""
        self.issues = []

        # Load sheet
        df, header_row = self.load_sheet(file_path, sheet_name=sheet_name)

        if header_row > 0:
            self._add_issue('info', 'format',
                           f"Header row detected at row {header_row + 1} (skipped {header_row} row(s))")

        # Map columns
        column_mapping = self._find_column_mapping(list(df.columns))

        # Build column info
        columns_info = []
        for col in df.columns:
            mapped = None
            for std_name, actual_col in column_mapping.items():
                if actual_col == col:
                    mapped = std_name
                    break

            columns_info.append(ColumnInfo(
                original_name=col,
                mapped_to=mapped,
                sample_values=df[col].dropna().head(3).tolist(),
                dtype=str(df[col].dtype),
                null_count=int(df[col].isna().sum()),
                unique_count=int(df[col].nunique())
            ))

        # Find missing columns based on sheet type
        required_cols = REQUIRED_COLUMNS_BY_SHEET.get(sheet_name, REQUIRED_COLUMNS)
        missing = [c for c in required_cols if c not in column_mapping]

        # Run validation with sheet context
        self.validate_data(df, column_mapping, sheet_name=sheet_name)

        # Compute summary with sheet context
        summary = self.compute_summary(df, column_mapping, sheet_name=sheet_name)

        # Determine if valid
        has_errors = any(i.severity == 'error' for i in self.issues)

        return SheetReviewResult(
            sheet_name=sheet_name,
            total_rows=len(df),
            total_columns=len(df.columns),
            columns_detected=[c.model_dump() for c in columns_info],
            columns_missing=missing,
            validation_issues=[i.model_dump() for i in self.issues],
            data_summary=summary,
            is_valid=not has_errors
        )

    def review(self, file_path: str) -> FileReviewResult:
        """Run complete file review across all sheets."""
        # Get file size
        file_size_kb = os.path.getsize(file_path) / 1024

        # Get sheet names
        sheet_names = self.get_sheet_names(file_path)
        is_multi_sheet = len(sheet_names) > 1

        # Review each sheet
        sheet_results = []
        all_issues = []
        total_rows = 0
        total_columns = 0
        combined_summary = {
            'total_rows_all_sheets': 0,
            'sheets': {}
        }

        if is_multi_sheet:
            for sheet_name in sheet_names:
                try:
                    sheet_result = self.review_sheet(file_path, sheet_name)
                    sheet_results.append(sheet_result)

                    # Aggregate data
                    total_rows += sheet_result.total_rows
                    total_columns = max(total_columns, sheet_result.total_columns)

                    # Add sheet-specific issues with sheet name prefix
                    for issue in sheet_result.validation_issues:
                        issue_copy = dict(issue)
                        issue_copy['message'] = f"[{sheet_name}] {issue_copy['message']}"
                        all_issues.append(issue_copy)

                    # Add to combined summary
                    combined_summary['sheets'][sheet_name] = {
                        'rows': sheet_result.total_rows,
                        'columns': sheet_result.total_columns,
                        'summary': sheet_result.data_summary
                    }
                    combined_summary['total_rows_all_sheets'] += sheet_result.total_rows

                except Exception as e:
                    all_issues.append({
                        'severity': 'error',
                        'category': 'sheet',
                        'message': f"[{sheet_name}] Failed to read sheet: {str(e)}",
                        'affected_rows': None,
                        'examples': []
                    })

            # Use first sheet for main column info
            if sheet_results:
                columns_info = sheet_results[0].columns_detected
                missing = sheet_results[0].columns_missing
            else:
                columns_info = []
                missing = REQUIRED_COLUMNS + RECOMMENDED_COLUMNS

        else:
            # Single sheet (or CSV)
            self.issues = []
            df, header_row = self.load_file(file_path)

            if header_row > 0:
                self._add_issue('info', 'format',
                               f"Header row detected at row {header_row + 1} (skipped {header_row} row(s))")

            column_mapping = self._find_column_mapping(list(df.columns))

            columns_info = []
            for col in df.columns:
                mapped = None
                for std_name, actual_col in column_mapping.items():
                    if actual_col == col:
                        mapped = std_name
                        break

                columns_info.append(ColumnInfo(
                    original_name=col,
                    mapped_to=mapped,
                    sample_values=df[col].dropna().head(3).tolist(),
                    dtype=str(df[col].dtype),
                    null_count=int(df[col].isna().sum()),
                    unique_count=int(df[col].nunique())
                ).model_dump())

            missing = [c for c in REQUIRED_COLUMNS + RECOMMENDED_COLUMNS if c not in column_mapping]
            self.validate_data(df, column_mapping)
            combined_summary = self.compute_summary(df, column_mapping)
            all_issues = [i.model_dump() for i in self.issues]
            total_rows = len(df)
            total_columns = len(df.columns)

        # Generate recommendations based on all issues
        self.issues = [ValidationIssue(**i) if isinstance(i, dict) else i for i in all_issues]
        recommendations = self.generate_recommendations(
            self._find_column_mapping([c['original_name'] if isinstance(c, dict) else c.original_name
                                       for c in columns_info])
        )

        # Add multi-sheet specific recommendations
        if is_multi_sheet:
            recommendations.insert(0, f"File contains {len(sheet_names)} sheets: {', '.join(sheet_names)}")

        # Determine if valid
        has_errors = any(
            (i.get('severity') if isinstance(i, dict) else i.severity) == 'error'
            for i in all_issues
        )

        return FileReviewResult(
            file_path=file_path,
            file_size_kb=round(file_size_kb, 1),
            total_rows=total_rows,
            total_columns=total_columns,
            sheets_count=len(sheet_names) if sheet_names else 1,
            sheets=[s.model_dump() for s in sheet_results],
            columns_detected=columns_info if isinstance(columns_info[0], dict) else [c.model_dump() for c in columns_info] if columns_info else [],
            columns_missing=missing,
            validation_issues=all_issues if isinstance(all_issues[0], dict) else [i.model_dump() for i in all_issues] if all_issues else [],
            data_summary=combined_summary,
            is_valid=not has_errors,
            recommendations=recommendations
        )


# =============================================================================
# LangChain Tool Definition
# =============================================================================

@tool
def review_reinforcement_file(
    file_path: str = "data/reinforcement_solution.xlsx"
) -> Dict[str, Any]:
    """
    Review a reinforcement solution file for completeness and clarity.

    This tool inspects an Excel/CSV file containing reinforcement data and checks:
    - Column structure and naming (across ALL sheets for Excel files)
    - Data completeness (missing values)
    - Data validity (correct types, valid ranges)
    - Potential duplicates or issues

    For Excel files with multiple sheets, the tool reviews EACH sheet individually
    and provides a combined summary with sheet-by-sheet breakdown.

    Args:
        file_path: Path to the reinforcement solution file (.xlsx or .csv)
                  Default: "data/reinforcement_solution.xlsx"

    Returns:
        Dictionary containing:
        - file_path: Path to the reviewed file
        - sheets_count: Number of sheets in the file
        - sheets: List of per-sheet review results (for multi-sheet files)
        - total_rows: Total number of data rows across all sheets
        - columns_detected: List of columns with mapping info
        - columns_missing: Required/recommended columns not found
        - validation_issues: List of errors, warnings, and info messages (prefixed with sheet name)
        - data_summary: Summary statistics per sheet (levels, diameters, weights)
        - is_valid: Whether the file passes validation
        - recommendations: Suggestions for improvements
    """
    try:
        reviewer = ReinforcementFileReviewer()
        result = reviewer.review(file_path)
        return result.model_dump()
    except Exception as e:
        logger.error(f"File review failed: {str(e)}")
        return {"error": str(e)}


@tool
def list_data_files(directory: str = "data") -> Dict[str, Any]:
    """
    List available data files in a directory.

    Args:
        directory: Directory to search (default: "data")

    Returns:
        Dictionary with list of Excel/CSV files found
    """
    try:
        files = []
        if os.path.exists(directory):
            for f in os.listdir(directory):
                if f.endswith(('.xlsx', '.xls', '.csv')):
                    full_path = os.path.join(directory, f)
                    size_kb = os.path.getsize(full_path) / 1024
                    files.append({
                        'filename': f,
                        'path': full_path,
                        'size_kb': round(size_kb, 1)
                    })

        return {
            'directory': directory,
            'files_found': len(files),
            'files': files
        }
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# Procurement Report Generator
# =============================================================================

class ProcurementReportGenerator:
    """
    Generates detailed procurement reports for specific floors or floor ranges.
    """

    def __init__(self, file_path: str = "data/reinforcement_solution.xlsx"):
        self.file_path = file_path
        self.xlsx = None
        self._load_file()

    def _load_file(self):
        """Load the Excel file."""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")
        self.xlsx = pd.ExcelFile(self.file_path)

    def _get_available_levels(self) -> List[str]:
        """Get list of available levels from RefLong_PorElemento sheet."""
        df = pd.read_excel(self.xlsx, sheet_name='RefLong_PorElemento', header=1)
        # Skip units row
        df = df.iloc[1:].reset_index(drop=True)
        levels = df['Piso'].dropna().unique()
        return sorted([str(l) for l in levels if str(l).strip() and str(l) != '-'],
                     key=lambda x: (int(''.join(filter(str.isdigit, x)) or 0), x))

    def _parse_floor_range(self, start_floor: str, end_floor: str = None) -> List[str]:
        """Parse floor range and return list of floors to include."""
        available = self._get_available_levels()

        if end_floor is None:
            # Single floor
            matching = [l for l in available if start_floor.upper() in l.upper()]
            if not matching:
                raise ValueError(f"Floor '{start_floor}' not found. Available: {available}")
            return matching

        # Floor range - find start and end indices
        start_idx = None
        end_idx = None

        for i, level in enumerate(available):
            if start_floor.upper() in level.upper():
                start_idx = i
            if end_floor.upper() in level.upper():
                end_idx = i

        if start_idx is None:
            raise ValueError(f"Start floor '{start_floor}' not found. Available: {available}")
        if end_idx is None:
            raise ValueError(f"End floor '{end_floor}' not found. Available: {available}")

        # Ensure correct order
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx

        return available[start_idx:end_idx + 1]

    def _load_longitudinal_data(self, floors: List[str]) -> pd.DataFrame:
        """Load longitudinal reinforcement data for specified floors."""
        df = pd.read_excel(self.xlsx, sheet_name='RefLong_PorElemento', header=1)
        df = df.iloc[1:].reset_index(drop=True)  # Skip units row

        # Filter by floors
        mask = df['Piso'].apply(lambda x: any(f.upper() in str(x).upper() for f in floors))
        return df[mask].copy()

    def _load_transverse_data(self, floors: List[str]) -> pd.DataFrame:
        """Load transverse reinforcement data for specified floors."""
        df = pd.read_excel(self.xlsx, sheet_name='RefTrans_PorElemento', header=1)
        df = df.iloc[1:].reset_index(drop=True)  # Skip units row

        # Filter by floors
        mask = df['Piso'].apply(lambda x: any(f.upper() in str(x).upper() for f in floors))
        return df[mask].copy()

    def _aggregate_by_diameter(self, df: pd.DataFrame, weight_col: str = 'Peso',
                                count_col: str = 'Cantidad', dia_col: str = 'Calibre') -> Dict:
        """Aggregate quantities by bar diameter."""
        result = {}

        for diameter in df[dia_col].dropna().unique():
            if str(diameter).strip() in ['-', '', '#']:
                continue

            dia_data = df[df[dia_col] == diameter]
            total_weight = pd.to_numeric(dia_data[weight_col], errors='coerce').sum()
            total_count = pd.to_numeric(dia_data[count_col], errors='coerce').sum()

            result[str(diameter)] = {
                'bar_count': int(total_count) if not pd.isna(total_count) else 0,
                'weight_kgf': round(total_weight, 2) if not pd.isna(total_weight) else 0,
                'weight_tonf': round(total_weight / 1000, 3) if not pd.isna(total_weight) else 0,
            }

        return result

    def _aggregate_by_element(self, df: pd.DataFrame, weight_col: str = 'Peso') -> Dict:
        """Aggregate quantities by element."""
        result = {}

        for element in df['Elemento'].dropna().unique():
            if str(element).strip() in ['-', '']:
                continue

            elem_data = df[df['Elemento'] == element]
            total_weight = pd.to_numeric(elem_data[weight_col], errors='coerce').sum()

            result[str(element)] = {
                'weight_kgf': round(total_weight, 2) if not pd.isna(total_weight) else 0,
            }

        return result

    def _aggregate_by_shape(self, df: pd.DataFrame, weight_col: str = 'Peso',
                            count_col: str = 'Cantidad', shape_col: str = 'Figura') -> Dict:
        """Aggregate quantities by bar shape."""
        result = {}

        # Shape descriptions
        shape_names = {
            '|': 'Straight bar',
            'L': '90° hook one end',
            'LL': '90° hooks both ends',
            'U': '180° hook one end',
            'UU': '180° hooks both ends',
            'LU': '90° + 180° hooks',
            '├': 'Headed one end',
            '├├': 'Headed both ends',
            '[]': 'Closed stirrup',
            '[': 'Stirrup leg',
        }

        for shape in df[shape_col].dropna().unique():
            if str(shape).strip() in ['-', '']:
                continue

            shape_data = df[df[shape_col] == shape]
            total_weight = pd.to_numeric(shape_data[weight_col], errors='coerce').sum()
            total_count = pd.to_numeric(shape_data[count_col], errors='coerce').sum()

            result[str(shape)] = {
                'description': shape_names.get(str(shape), 'Unknown'),
                'bar_count': int(total_count) if not pd.isna(total_count) else 0,
                'weight_kgf': round(total_weight, 2) if not pd.isna(total_weight) else 0,
            }

        return result

    def _get_longitudinal_bar_list(self, df: pd.DataFrame) -> List[Dict]:
        """
        Get detailed list of all longitudinal bars with their specifications.
        Groups by: Diameter, Shape, Total Length
        """
        bars = []

        # Group by diameter, shape, and total length
        group_cols = ['Calibre', 'Figura', 'L_total']
        available_cols = [c for c in group_cols if c in df.columns]

        if not available_cols:
            return bars

        # Clean the data
        df_clean = df.copy()
        for col in available_cols:
            df_clean = df_clean[df_clean[col].notna()]
            df_clean = df_clean[df_clean[col].astype(str).str.strip() != '-']
            df_clean = df_clean[df_clean[col].astype(str).str.strip() != '']

        if len(df_clean) == 0:
            return bars

        # Shape descriptions
        shape_names = {
            '|': 'Straight',
            'L': '90° hook (1 end)',
            'LL': '90° hooks (both)',
            'U': '180° hook (1 end)',
            'UU': '180° hooks (both)',
            'LU': '90°+180° hooks',
            '├': 'Headed (1 end)',
            '├├': 'Headed (both)',
        }

        # Group and aggregate
        grouped = df_clean.groupby(available_cols).agg({
            'Cantidad': 'sum',
            'Peso': 'sum',
            'L_recta': 'first',
            'L_gancho_izq': 'first',
            'L_gancho_der': 'first',
        }).reset_index()

        for _, row in grouped.iterrows():
            diameter = str(row.get('Calibre', ''))
            shape = str(row.get('Figura', ''))
            l_total = row.get('L_total', 0)
            l_recta = row.get('L_recta', 0)
            l_gancho_izq = row.get('L_gancho_izq', 0)
            l_gancho_der = row.get('L_gancho_der', 0)
            count = row.get('Cantidad', 0)
            weight = row.get('Peso', 0)

            # Convert to float safely
            try:
                l_total = float(l_total) if l_total not in ['-', '', None] else 0
            except:
                l_total = 0

            bars.append({
                'diameter': diameter,
                'shape': shape,
                'shape_description': shape_names.get(shape, 'Unknown'),
                'total_length_m': round(l_total, 2),
                'straight_length_m': round(float(l_recta) if l_recta not in ['-', '', None] else 0, 2),
                'hook_left_m': round(float(l_gancho_izq) if l_gancho_izq not in ['-', '', None] else 0, 2),
                'hook_right_m': round(float(l_gancho_der) if l_gancho_der not in ['-', '', None] else 0, 2),
                'quantity': int(count) if not pd.isna(count) else 0,
                'weight_kgf': round(float(weight) if not pd.isna(weight) else 0, 2),
            })

        # Sort by diameter, then by length
        bars.sort(key=lambda x: (x['diameter'], x['total_length_m']))

        return bars

    def _get_transverse_bar_list(self, df: pd.DataFrame) -> List[Dict]:
        """
        Get detailed list of all transverse bars (stirrups) with their specifications.
        Groups by: Diameter, Shape, Base, Height
        """
        bars = []

        # Group by diameter, shape, base, height
        group_cols = ['Calibre', 'Figura', 'Base', 'Altura']
        available_cols = [c for c in group_cols if c in df.columns]

        if not available_cols:
            return bars

        # Clean the data
        df_clean = df.copy()
        for col in ['Calibre', 'Figura']:
            if col in df_clean.columns:
                df_clean = df_clean[df_clean[col].notna()]
                df_clean = df_clean[df_clean[col].astype(str).str.strip() != '']

        if len(df_clean) == 0:
            return bars

        # Shape descriptions
        shape_names = {
            '[]': 'Closed stirrup',
            '[': 'Stirrup leg',
        }

        # Group and aggregate
        agg_dict = {'Cantidad': 'sum', 'Peso': 'sum'}
        grouped = df_clean.groupby(available_cols).agg(agg_dict).reset_index()

        for _, row in grouped.iterrows():
            diameter = str(row.get('Calibre', ''))
            shape = str(row.get('Figura', ''))
            base = row.get('Base', 0)
            altura = row.get('Altura', 0)
            count = row.get('Cantidad', 0)
            weight = row.get('Peso', 0)

            # Convert to float safely
            try:
                base = float(base) if base not in ['-', '', None] else 0
            except:
                base = 0
            try:
                altura = float(altura) if altura not in ['-', '', None] else 0
            except:
                altura = 0

            bars.append({
                'diameter': diameter,
                'shape': shape,
                'shape_description': shape_names.get(shape, 'Unknown'),
                'base_m': round(base, 2),
                'height_m': round(altura, 2),
                'quantity': int(count) if not pd.isna(count) else 0,
                'weight_kgf': round(float(weight) if not pd.isna(weight) else 0, 2),
            })

        # Sort by diameter, then by dimensions
        bars.sort(key=lambda x: (x['diameter'], x['base_m'], x['height_m']))

        return bars

    def generate_report(self, start_floor: str, end_floor: str = None) -> Dict[str, Any]:
        """
        Generate a detailed procurement report for specified floor(s).

        Args:
            start_floor: Starting floor (e.g., "PISO 5") or single floor
            end_floor: Ending floor for range (optional)

        Returns:
            Detailed procurement report dictionary
        """
        # Parse floor range
        floors = self._parse_floor_range(start_floor, end_floor)

        # Load data for these floors
        long_df = self._load_longitudinal_data(floors)
        trans_df = self._load_transverse_data(floors)

        # Calculate totals
        long_weight = pd.to_numeric(long_df['Peso'], errors='coerce').sum()
        trans_weight = pd.to_numeric(trans_df['Peso'], errors='coerce').sum()
        total_weight = long_weight + trans_weight

        long_count = pd.to_numeric(long_df['Cantidad'], errors='coerce').sum()
        trans_count = pd.to_numeric(trans_df['Cantidad'], errors='coerce').sum()

        # Build report
        report = {
            'report_type': 'Procurement Report',
            'file_path': self.file_path,
            'floors_included': floors,
            'floor_count': len(floors),
            'floor_range': f"{floors[0]} to {floors[-1]}" if len(floors) > 1 else floors[0],

            'summary': {
                'total_weight_kgf': round(total_weight, 2),
                'total_weight_tonf': round(total_weight / 1000, 2),
                'longitudinal_weight_kgf': round(long_weight, 2),
                'longitudinal_weight_tonf': round(long_weight / 1000, 2),
                'transverse_weight_kgf': round(trans_weight, 2),
                'transverse_weight_tonf': round(trans_weight / 1000, 2),
                'total_bar_count': int(long_count + trans_count),
                'longitudinal_bar_count': int(long_count),
                'transverse_bar_count': int(trans_count),
            },

            'longitudinal_reinforcement': {
                'row_count': len(long_df),
                'by_diameter': self._aggregate_by_diameter(long_df),
                'by_shape': self._aggregate_by_shape(long_df),
                'unique_elements': list(long_df['Elemento'].dropna().unique())[:20],
                'bar_list': self._get_longitudinal_bar_list(long_df),
            },

            'transverse_reinforcement': {
                'row_count': len(trans_df),
                'by_diameter': self._aggregate_by_diameter(trans_df),
                'by_shape': self._aggregate_by_shape(trans_df, shape_col='Figura'),
                'unique_elements': list(trans_df['Elemento'].dropna().unique())[:20],
                'bar_list': self._get_transverse_bar_list(trans_df),
            },

            'elements_summary': {
                'unique_elements': len(set(long_df['Elemento'].dropna().unique()) |
                                       set(trans_df['Elemento'].dropna().unique())),
            },
        }

        return report


# =============================================================================
# PDF Report Generator
# =============================================================================

class PDFReportGenerator:
    """
    Generates professional PDF procurement reports.
    """

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def _create_styles(self):
        """Create custom paragraph styles."""
        styles = getSampleStyleSheet()

        styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1a5f7a')
        ))

        styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=styles['Heading2'],
            fontSize=14,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor('#1a5f7a'),
            borderPadding=5,
        ))

        styles.add(ParagraphStyle(
            name='SubHeader',
            parent=styles['Heading3'],
            fontSize=11,
            spaceBefore=12,
            spaceAfter=6,
            textColor=colors.HexColor('#2d3436')
        ))

        styles.add(ParagraphStyle(
            name='ReportBody',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=6
        ))

        styles.add(ParagraphStyle(
            name='TableHeader',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.white,
            alignment=TA_CENTER
        ))

        styles.add(ParagraphStyle(
            name='Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        ))

        return styles

    def _create_table(self, data: List[List], col_widths: List = None,
                      header_color: colors.Color = colors.HexColor('#1a5f7a')) -> Table:
        """Create a styled table."""
        table = Table(data, colWidths=col_widths)

        style = TableStyle([
            # Header styling
            ('BACKGROUND', (0, 0), (-1, 0), header_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),

            # Body styling
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 6),

            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f6fa')]),

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dfe6e9')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#1a5f7a')),
        ])

        table.setStyle(style)
        return table

    def generate_pdf(self, report: Dict[str, Any], filename: str = None) -> str:
        """
        Generate a PDF report from the procurement report data.

        Args:
            report: Procurement report dictionary from ProcurementReportGenerator
            filename: Optional filename (without extension)

        Returns:
            Path to the generated PDF file
        """
        if not PDF_AVAILABLE:
            raise RuntimeError("reportlab is not installed. Install with: pip install reportlab")

        # Generate filename
        if filename is None:
            floor_range = report.get('floor_range', 'report').replace(' ', '_').replace('/', '-')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"procurement_report_{floor_range}_{timestamp}"

        pdf_path = os.path.join(self.output_dir, f"{filename}.pdf")

        # Create document
        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )

        styles = self._create_styles()
        elements = []

        # Title
        elements.append(Paragraph("PROCUREMENT REPORT", styles['ReportTitle']))
        elements.append(Paragraph("Reinforcement Steel Quantities", styles['ReportBody']))
        elements.append(Spacer(1, 20))

        # Report Info
        elements.append(Paragraph("Report Information", styles['SectionHeader']))
        info_data = [
            ['Floor Range', report.get('floor_range', 'N/A')],
            ['Floors Included', str(report.get('floor_count', 0))],
            ['Source File', os.path.basename(report.get('file_path', 'N/A'))],
            ['Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
        ]
        info_table = Table(info_data, colWidths=[2*inch, 4*inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 20))

        # Summary Section
        summary = report.get('summary', {})
        elements.append(Paragraph("Quantities Summary", styles['SectionHeader']))

        summary_data = [
            ['Category', 'Weight (tonf)', 'Weight (kgf)', 'Bar Count'],
            ['Longitudinal',
             f"{summary.get('longitudinal_weight_tonf', 0):.2f}",
             f"{summary.get('longitudinal_weight_kgf', 0):,.0f}",
             f"{summary.get('longitudinal_bar_count', 0):,}"],
            ['Transverse',
             f"{summary.get('transverse_weight_tonf', 0):.2f}",
             f"{summary.get('transverse_weight_kgf', 0):,.0f}",
             f"{summary.get('transverse_bar_count', 0):,}"],
            ['TOTAL',
             f"{summary.get('total_weight_tonf', 0):.2f}",
             f"{summary.get('total_weight_kgf', 0):,.0f}",
             f"{summary.get('total_bar_count', 0):,}"],
        ]
        summary_table = self._create_table(summary_data, col_widths=[2*inch, 1.5*inch, 1.5*inch, 1.5*inch])

        # Make total row bold
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8f4f8')),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 25))

        # Longitudinal Reinforcement by Diameter
        long_data = report.get('longitudinal_reinforcement', {})
        by_diameter = long_data.get('by_diameter', {})

        if by_diameter:
            elements.append(Paragraph("Longitudinal Reinforcement by Diameter", styles['SectionHeader']))

            diameter_data = [['Diameter', 'Bar Count', 'Weight (kgf)', 'Weight (tonf)']]
            total_count = 0
            total_weight = 0

            for dia, values in sorted(by_diameter.items()):
                count = values.get('bar_count', 0)
                weight_kgf = values.get('weight_kgf', 0)
                weight_tonf = values.get('weight_tonf', 0)
                diameter_data.append([dia, f"{count:,}", f"{weight_kgf:,.1f}", f"{weight_tonf:.3f}"])
                total_count += count
                total_weight += weight_kgf

            diameter_data.append(['TOTAL', f"{total_count:,}", f"{total_weight:,.1f}", f"{total_weight/1000:.3f}"])

            dia_table = self._create_table(diameter_data, col_widths=[1.5*inch, 1.5*inch, 2*inch, 1.5*inch])
            dia_table.setStyle(TableStyle([
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8f4f8')),
            ]))
            elements.append(dia_table)
            elements.append(Spacer(1, 20))

        # Transverse Reinforcement by Diameter
        trans_data = report.get('transverse_reinforcement', {})
        trans_by_diameter = trans_data.get('by_diameter', {})

        if trans_by_diameter:
            elements.append(Paragraph("Transverse Reinforcement (Stirrups) by Diameter", styles['SectionHeader']))

            trans_diameter_data = [['Diameter', 'Bar Count', 'Weight (kgf)', 'Weight (tonf)']]
            total_count = 0
            total_weight = 0

            for dia, values in sorted(trans_by_diameter.items()):
                count = values.get('bar_count', 0)
                weight_kgf = values.get('weight_kgf', 0)
                weight_tonf = values.get('weight_tonf', 0)
                trans_diameter_data.append([dia, f"{count:,}", f"{weight_kgf:,.1f}", f"{weight_tonf:.3f}"])
                total_count += count
                total_weight += weight_kgf

            trans_diameter_data.append(['TOTAL', f"{total_count:,}", f"{total_weight:,.1f}", f"{total_weight/1000:.3f}"])

            trans_table = self._create_table(trans_diameter_data, col_widths=[1.5*inch, 1.5*inch, 2*inch, 1.5*inch])
            trans_table.setStyle(TableStyle([
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8f4f8')),
            ]))
            elements.append(trans_table)
            elements.append(Spacer(1, 20))

        # Bar Shapes Summary
        long_shapes = long_data.get('by_shape', {})
        if long_shapes:
            elements.append(Paragraph("Longitudinal Bars by Shape", styles['SectionHeader']))

            shape_data = [['Shape', 'Description', 'Bar Count', 'Weight (kgf)']]
            for shape, values in sorted(long_shapes.items()):
                shape_data.append([
                    shape,
                    values.get('description', 'Unknown'),
                    f"{values.get('bar_count', 0):,}",
                    f"{values.get('weight_kgf', 0):,.1f}"
                ])

            shape_table = self._create_table(shape_data, col_widths=[0.8*inch, 2.5*inch, 1.5*inch, 1.7*inch])
            elements.append(shape_table)
            elements.append(Spacer(1, 20))

        # Detailed Longitudinal Bar List with Lengths
        long_bar_list = long_data.get('bar_list', [])
        if long_bar_list:
            elements.append(PageBreak())
            elements.append(Paragraph("Detailed Longitudinal Bar List", styles['SectionHeader']))
            elements.append(Paragraph(
                "Complete list of longitudinal bars grouped by diameter, shape, and length.",
                styles['ReportBody']
            ))
            elements.append(Spacer(1, 10))

            bar_list_data = [['Diameter', 'Shape', 'L_total (m)', 'L_recta (m)', 'Qty', 'Weight (kgf)']]
            for bar in long_bar_list:
                bar_list_data.append([
                    bar.get('diameter', ''),
                    bar.get('shape', ''),
                    f"{bar.get('total_length_m', 0):.2f}",
                    f"{bar.get('straight_length_m', 0):.2f}",
                    f"{bar.get('quantity', 0):,}",
                    f"{bar.get('weight_kgf', 0):,.1f}"
                ])

            # Split into multiple tables if too many rows
            max_rows_per_table = 35
            for i in range(0, len(bar_list_data) - 1, max_rows_per_table):
                chunk = [bar_list_data[0]] + bar_list_data[i + 1:i + 1 + max_rows_per_table]
                bar_table = self._create_table(
                    chunk,
                    col_widths=[0.9*inch, 0.7*inch, 1.1*inch, 1.1*inch, 0.9*inch, 1.3*inch]
                )
                elements.append(bar_table)
                if i + max_rows_per_table < len(bar_list_data) - 1:
                    elements.append(PageBreak())
                else:
                    elements.append(Spacer(1, 20))

        # Detailed Transverse Bar List (Stirrups) with Dimensions
        trans_bar_list = trans_data.get('bar_list', [])
        if trans_bar_list:
            elements.append(PageBreak())
            elements.append(Paragraph("Detailed Stirrup List", styles['SectionHeader']))
            elements.append(Paragraph(
                "Complete list of stirrups grouped by diameter, shape, and dimensions.",
                styles['ReportBody']
            ))
            elements.append(Spacer(1, 10))

            stirrup_list_data = [['Diameter', 'Shape', 'Base (m)', 'Height (m)', 'Qty', 'Weight (kgf)']]
            for bar in trans_bar_list:
                stirrup_list_data.append([
                    bar.get('diameter', ''),
                    bar.get('shape', ''),
                    f"{bar.get('base_m', 0):.2f}",
                    f"{bar.get('height_m', 0):.2f}",
                    f"{bar.get('quantity', 0):,}",
                    f"{bar.get('weight_kgf', 0):,.1f}"
                ])

            # Split into multiple tables if too many rows
            for i in range(0, len(stirrup_list_data) - 1, max_rows_per_table):
                chunk = [stirrup_list_data[0]] + stirrup_list_data[i + 1:i + 1 + max_rows_per_table]
                stirrup_table = self._create_table(
                    chunk,
                    col_widths=[0.9*inch, 0.7*inch, 1.1*inch, 1.1*inch, 0.9*inch, 1.3*inch]
                )
                elements.append(stirrup_table)
                if i + max_rows_per_table < len(stirrup_list_data) - 1:
                    elements.append(PageBreak())
                else:
                    elements.append(Spacer(1, 20))

        # Floors Included
        floors = report.get('floors_included', [])
        if floors:
            elements.append(Paragraph("Floors Included", styles['SectionHeader']))
            floors_text = ", ".join(floors)
            elements.append(Paragraph(floors_text, styles['ReportBody']))
            elements.append(Spacer(1, 20))

        # Footer
        elements.append(Spacer(1, 30))
        elements.append(Paragraph(
            f"Generated by ProDet Procurement Agent | {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            styles['Footer']
        ))

        # Build PDF
        doc.build(elements)

        return pdf_path


@tool
def generate_procurement_report(
    start_floor: str,
    end_floor: str = None,
    file_path: str = "data/reinforcement_solution.xlsx",
    generate_pdf: bool = False
) -> Dict[str, Any]:
    """
    Generate a detailed procurement report for specific floor(s).

    This tool creates a comprehensive procurement report including:
    - Total steel quantities (longitudinal and transverse)
    - Breakdown by bar diameter (Calibre)
    - Breakdown by bar shape (Figura)
    - List of elements included
    - Optional PDF file generation

    Args:
        start_floor: Starting floor name (e.g., "PISO 5", "PISO 10")
                    For a single floor report, only provide this parameter.
        end_floor: Ending floor name for a range report (e.g., "PISO 11").
                  If provided, report includes all floors from start_floor to end_floor.
        file_path: Path to the reinforcement solution file.
                  Default: "data/reinforcement_solution.xlsx"
        generate_pdf: If True, generates a PDF report file in the 'reports' folder.
                     Default: False

    Returns:
        Dictionary containing:
        - floors_included: List of floors in the report
        - summary: Total weights and bar counts
        - longitudinal_reinforcement: Detailed breakdown of longitudinal bars
        - transverse_reinforcement: Detailed breakdown of stirrups
        - elements_summary: Count of unique structural elements
        - pdf_path: (only if generate_pdf=True) Path to the generated PDF file

    Examples:
        - Single floor: start_floor="PISO 5"
        - Floor range: start_floor="PISO 5", end_floor="PISO 11"
        - With PDF: start_floor="PISO 5", end_floor="PISO 11", generate_pdf=True
    """
    try:
        generator = ProcurementReportGenerator(file_path)
        report = generator.generate_report(start_floor, end_floor)

        # Generate PDF if requested
        if generate_pdf:
            if not PDF_AVAILABLE:
                report['pdf_error'] = "reportlab not installed. Install with: pip install reportlab"
            else:
                try:
                    pdf_generator = PDFReportGenerator()
                    pdf_path = pdf_generator.generate_pdf(report)
                    report['pdf_path'] = pdf_path
                    report['pdf_generated'] = True
                except Exception as pdf_error:
                    report['pdf_error'] = str(pdf_error)
                    report['pdf_generated'] = False

        return report
    except Exception as e:
        logger.error(f"Report generation failed: {str(e)}")
        return {"error": str(e)}


@tool
def list_available_floors(file_path: str = "data/reinforcement_solution.xlsx") -> Dict[str, Any]:
    """
    List all available floors in the reinforcement solution file.

    Use this tool to see what floors are available before generating a procurement report.

    Args:
        file_path: Path to the reinforcement solution file.
                  Default: "data/reinforcement_solution.xlsx"

    Returns:
        Dictionary containing:
        - floors: List of all floor names in order (bottom to top)
        - floor_count: Total number of floors
    """
    try:
        generator = ProcurementReportGenerator(file_path)
        floors = generator._get_available_levels()
        return {
            'file_path': file_path,
            'floors': floors,
            'floor_count': len(floors),
            'first_floor': floors[0] if floors else None,
            'last_floor': floors[-1] if floors else None,
        }
    except Exception as e:
        logger.error(f"Failed to list floors: {str(e)}")
        return {"error": str(e)}


# =============================================================================
# LCEL Agent Pipeline
# =============================================================================

class ProcurementAgent:
    """
    LCEL-based agent for procurement planning.

    Helps review reinforcement data and plan material procurement.
    """

    SYSTEM_PROMPT = """You are an expert construction procurement specialist focusing on reinforcement steel (rebar) procurement.

Your task is to help users review ProDet reinforcement solution files and plan material procurement.

AVAILABLE TOOLS:
1. list_data_files - List available data files in a directory
2. review_reinforcement_file - Review a reinforcement file for completeness and issues
3. list_available_floors - List all floors available in the reinforcement file
4. generate_procurement_report - Generate detailed procurement report for specific floor(s)

IMPORTANT:
- If the user doesn't specify a file, use "data/reinforcement_solution.xlsx" as default
- If the file doesn't exist, use list_data_files to show available files
- Always explain issues clearly and provide actionable recommendations

== PRODET FILE STRUCTURE ==

The reinforcement_solution.xlsx file generated by ProDet contains 5 sheets:

1. **Resumen_Refuerzo** - Story-by-story steel totals
   - Purpose: High-level monitoring, comparing solutions
   - Columns: Nivel, Ref.Longitudinal (tonf), Ref.Transversal (tonf), Total por nivel (tonf)
   - Contains a TOTALES row with building totals
   - Use for: Total tonnage per level, longitudinal vs transverse breakdown

2. **RefLong_PorElemento** - Longitudinal reinforcement by element
   - Purpose: Element-level detail, QA, constructability
   - Columns: Piso, Elemento (V-3, V-7A), Figura (bar shape), Calibre (5/8", 3/4"),
     L_recta, L_gancho_izq, L_gancho_der, L_total [m], Cantidad, Peso [kgf]
   - Bar shapes: | (straight), L (90° hook one end), LL (90° both ends),
     U (180° one end), UU (180° both), LU (90° + 180°), ├ (headed one end)
   - Use for: Per-element longitudinal weights, bar lengths for fabrication

3. **RefLong_Total** - Longitudinal reinforcement totals (global)
   - Purpose: Procurement, fabrication, cutting lists
   - Columns: Figura, Calibre, L_recta, L_gancho_izq, L_gancho_der, L_total [m], Cantidad, Peso [kgf]
   - Each row = one unique bar type (shape + size + length)
   - Use for: Global bar list for purchase orders, grouped by bar type

4. **RefTrans_PorElemento** - Transverse reinforcement (stirrups) by element
   - Purpose: Element-level stirrup sizes and quantities
   - Columns: Piso, Elemento, Figura, Calibre (3/8"), Base [m], Altura [m], Cantidad, Peso [kgf]
   - Stirrup shapes: [] (closed rectangular), [ (stirrup leg/rama)
   - Use for: Per-element stirrup quantities

5. **RefTrans_Total** - Transverse reinforcement totals (global)
   - Purpose: Procurement, global stirrup list
   - Columns: Figura, Calibre, Base [m], Altura [m], Cantidad, Peso [kgf]
   - Use for: Global stirrup list for purchase orders

== SHEET USAGE GUIDE ==

For PROCUREMENT tasks, prioritize:
- RefLong_Total + RefTrans_Total → global quantities by bar type for purchase orders
- Use Calibre + dimensions + Cantidad + Peso for ordering

For QA/CONSTRUCTABILITY tasks, use:
- RefLong_PorElemento + RefTrans_PorElemento → element-level breakdown

For MONITORING/COMPARISON, use:
- Resumen_Refuerzo → quick tonnage overview by level

== TERMINOLOGY ==

- Calibre: Bar diameter in fractional inches (5/8", 3/4", 1") - NOT metric mm
- Peso: Weight in kgf (kilograms-force), divide by 1000 for tonf
- Figura: Bar shape code (see legends above)
- Piso/Nivel: Floor/story name (PISO 2, CUBIERTA, etc.)
- Elemento: Structural element ID (V-3 = beam 3, C-5 = column 5)

== OUTPUT FORMAT ==

Present findings in a clear, structured format:

📋 FILE OVERVIEW
- Number of sheets, total rows, file size
- Sheet-by-sheet summary

📊 STEEL QUANTITIES
- Total longitudinal steel (tonf)
- Total transverse steel (tonf)
- Grand total (tonf)
- Bar diameters used

🏗️ SHEET DETAILS
- Describe what each sheet contains
- Highlight key data for user's purpose

⚠️ ISSUES (if any)
- Errors that need fixing
- Warnings to review

✅ RECOMMENDATIONS
- Which sheets to use for their task
- Next steps

Be concise and focus on actionable insights. When users ask about quantities,
always specify whether the data comes from element-level detail sheets or global totals.

== FLOOR-SPECIFIC REPORTS ==

When users ask for reports for specific floors:
1. Use list_available_floors to see what floors exist (if unsure)
2. Use generate_procurement_report with:
   - Single floor: start_floor="PISO 5"
   - Floor range: start_floor="PISO 5", end_floor="PISO 11"

Present floor reports with:

📋 REPORT SCOPE
- Floors included, floor range

📊 QUANTITIES SUMMARY
- Total steel (tonf)
- Longitudinal vs transverse breakdown
- Total bar count

🔩 BY DIAMETER (for ordering)
- List each diameter with bar count and weight

📐 BY SHAPE
- Breakdown by bar shape (straight, hooked, etc.)

🏗️ ELEMENTS
- Number of unique elements covered

Example user requests:
- "Give me a procurement report for PISO 5"
- "Generate a report for floors PISO 5 through PISO 11"
- "What steel do I need for floors 5 to 10?"
- "Procurement quantities for the first 5 floors"

== PDF REPORT GENERATION ==

When users request a PDF report, use generate_procurement_report with generate_pdf=True.

PDF reports are saved to the 'reports' folder with professional formatting including:
- Report header with floor range and generation date
- Summary table with longitudinal/transverse breakdown
- Detailed tables by bar diameter
- Bar shapes breakdown
- List of floors included

Example PDF requests:
- "Generate a PDF report for PISO 5"
- "Create a PDF procurement report for floors PISO 5 through PISO 11"
- "I need a PDF with the steel quantities for PISO 8 to PISO 15"
- "Export the report for PISO 10 as PDF"

When a PDF is generated successfully, inform the user of the file path.
If PDF generation fails, explain the error and still provide the data summary."""

    def __init__(self, model_name: str = "gpt-4.1-mini", temperature: float = 0.0):
        """Initialize the agent."""
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature
        )
        self.tools = [list_data_files, review_reinforcement_file,
                      list_available_floors, generate_procurement_report]

        self.agent = create_react_agent(
            self.llm,
            tools=self.tools,
            prompt=self.SYSTEM_PROMPT
        )

    def run(self, user_input: str, chat_history: Optional[List] = None) -> str:
        """Execute the agent with user input."""
        messages = []
        if chat_history:
            messages.extend(chat_history)
        messages.append(HumanMessage(content=user_input))

        result = self.agent.invoke({"messages": messages})

        if result.get("messages"):
            return result["messages"][-1].content
        return str(result)


# =============================================================================
# Standalone Functions
# =============================================================================

def run_file_review(file_path: str = "data/reinforcement_solution.xlsx") -> Dict[str, Any]:
    """Run file review directly without LLM."""
    return review_reinforcement_file.invoke({"file_path": file_path})


def format_review_summary(result: Dict[str, Any]) -> str:
    """Format review result as readable text."""
    if "error" in result:
        return f"Error: {result['error']}"

    lines = []
    lines.append("=" * 60)
    lines.append("REINFORCEMENT FILE REVIEW")
    lines.append("=" * 60)

    lines.append(f"\nFile: {result['file_path']}")
    lines.append(f"Size: {result['file_size_kb']} KB")
    sheets_count = result.get('sheets_count', 1)
    lines.append(f"Sheets: {sheets_count}")
    lines.append(f"Total Rows: {result['total_rows']}")
    lines.append(f"Columns: {result['total_columns']}")
    lines.append(f"Valid: {'✓ Yes' if result['is_valid'] else '✗ No'}")

    # Multi-sheet summary
    sheets = result.get('sheets', [])
    if sheets:
        lines.append("\n" + "-" * 40)
        lines.append("SHEET-BY-SHEET SUMMARY")
        lines.append("-" * 40)
        for sheet in sheets:
            sheet_name = sheet.get('sheet_name', 'Unknown')
            sheet_rows = sheet.get('total_rows', 0)
            sheet_cols = sheet.get('total_columns', 0)
            sheet_valid = '✓' if sheet.get('is_valid', False) else '✗'
            lines.append(f"\n  📄 {sheet_name}")
            lines.append(f"     Rows: {sheet_rows}, Columns: {sheet_cols}, Valid: {sheet_valid}")

            # Sheet-specific summary
            sheet_summary = sheet.get('data_summary', {})
            if sheet_summary:
                if 'unique_levels' in sheet_summary:
                    lines.append(f"     Levels: {sheet_summary['unique_levels']}")
                if 'bar_diameters' in sheet_summary:
                    dias = sheet_summary['bar_diameters']
                    if len(dias) > 5:
                        lines.append(f"     Diameters: {dias[:5]}... ({len(dias)} total)")
                    else:
                        lines.append(f"     Diameters: {dias}")
                if 'total_weight_tonf' in sheet_summary:
                    lines.append(f"     Weight: {sheet_summary['total_weight_tonf']} tonf")

    # Issues
    issues = result.get('validation_issues', [])
    if issues:
        lines.append("\n" + "-" * 40)
        lines.append("ISSUES FOUND")
        lines.append("-" * 40)
        for issue in issues:
            icon = {'error': '❌', 'warning': '⚠️', 'info': 'ℹ️'}.get(issue['severity'], '•')
            lines.append(f"  {icon} [{issue['severity'].upper()}] {issue['message']}")

    # Combined summary (for single-sheet files)
    if not sheets:
        summary = result.get('data_summary', {})
        if summary:
            lines.append("\nDATA SUMMARY:")
            if 'unique_levels' in summary:
                lines.append(f"  Levels: {summary['unique_levels']}")
            if 'bar_diameters' in summary:
                lines.append(f"  Diameters: {summary['bar_diameters']}")
            if 'total_weight_tonf' in summary:
                lines.append(f"  Total weight: {summary['total_weight_tonf']} tonf")

    # Recommendations
    recs = result.get('recommendations', [])
    if recs:
        lines.append("\n" + "-" * 40)
        lines.append("RECOMMENDATIONS")
        lines.append("-" * 40)
        for rec in recs:
            lines.append(f"  • {rec}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import sys

    print("Procurement Agent - File Review")
    print("=" * 40)

    file_path = sys.argv[1] if len(sys.argv) > 1 else "data/reinforcement_solution.xlsx"

    result = run_file_review(file_path)
    print(format_review_summary(result))
