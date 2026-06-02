"""
validator.py
Validates COBie sheets against:
- COBie UK 2012 mandatory fields and sheets
- ISO 19650-2 naming conventions
- Uniclass 2015 classification
- RIBA stage completeness thresholds
- SFG20 maintenance coverage
"""

import re
import pandas as pd

# ── COBie UK 2012 mandatory fields ────────────────────────────────────────────
MANDATORY_SHEETS = [
    "Contact", "Facility", "Floor", "Space",
    "Zone", "Type", "Component", "Document",
]

MANDATORY_FIELDS = {
    "Contact":   ["Name", "CreatedBy", "CreatedOn", "Email", "Company"],
    "Facility":  ["Name", "CreatedBy", "CreatedOn", "ProjectName", "SiteName"],
    "Floor":     ["Name", "CreatedBy", "CreatedOn", "Category"],
    "Space":     ["Name", "CreatedBy", "CreatedOn", "FloorName", "Category"],
    "Zone":      ["Name", "CreatedBy", "CreatedOn", "SpaceNames"],
    "Type":      ["Name", "CreatedBy", "CreatedOn", "Category", "AssetType"],
    "Component": ["Name", "CreatedBy", "CreatedOn", "TypeName", "Space"],
    "Document":  ["Name", "CreatedBy", "CreatedOn", "Stage", "SheetName", "RowName"],
    "Job":       ["Name", "CreatedBy", "CreatedOn", "TypeName", "Frequency"],
    "Resource":  ["Name", "CreatedBy", "CreatedOn"],
    "Spare":     ["Name", "CreatedBy", "CreatedOn", "TypeName"],
}

# ── RIBA stage completeness thresholds ───────────────────────────────────────
RIBA_THRESHOLDS = {
    "Stage 2": {"min_completion": 0.40, "required_sheets": ["Facility", "Floor", "Space"]},
    "Stage 3": {"min_completion": 0.60, "required_sheets": ["Facility", "Floor", "Space", "Type"]},
    "Stage 4": {"min_completion": 0.80, "required_sheets": ["Facility", "Floor", "Space", "Type", "Component"]},
    "Handover": {"min_completion": 1.00, "required_sheets": MANDATORY_SHEETS},
}

# ── ISO 19650 naming convention (simplified) ──────────────────────────────────
ISO19650_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9\-_\.]{1,}$")

# ── Uniclass format ───────────────────────────────────────────────────────────
UNICLASS_PATTERN = re.compile(r"^[A-Z][a-z]_\d{2}_\d{2}")


def _issue(severity: str, sheet: str, row_name: str, field: str, message: str) -> dict:
    return {
        "Severity":  severity,
        "Sheet":     sheet,
        "Element":   row_name,
        "Field":     field,
        "Message":   message,
    }


def _check_mandatory_sheets(sheets: dict) -> list:
    issues = []
    for s in MANDATORY_SHEETS:
        if s not in sheets or sheets[s].empty:
            issues.append(_issue("CRITICAL", s, "-", "-",
                f'Sheet "{s}" is empty — required by COBie UK 2012'))
    return issues


def _check_mandatory_fields(sheets: dict) -> list:
    issues = []
    for sheet, fields in MANDATORY_FIELDS.items():
        if sheet not in sheets or sheets[sheet].empty:
            continue
        df = sheets[sheet]
        for _, row in df.iterrows():
            name = row.get("Name", "Unknown")
            for field in fields:
                if field not in df.columns:
                    issues.append(_issue("CRITICAL", sheet, name, field,
                        f'Column "{field}" missing from sheet'))
                elif not row.get(field) or str(row.get(field)) in ("TBC", "", "nan"):
                    severity = "WARNING" if str(row.get(field)) == "TBC" else "CRITICAL"
                    issues.append(_issue(severity, sheet, name, field,
                        f'"{field}" is {"TBC" if str(row.get(field))=="TBC" else "empty"} — required by COBie UK 2012'))
    return issues


def _check_naming(sheets: dict) -> list:
    issues = []
    for sheet in ["Component", "Type", "Floor", "Space"]:
        if sheet not in sheets or sheets[sheet].empty:
            continue
        for _, row in sheets[sheet].iterrows():
            name = str(row.get("Name", ""))
            if not ISO19650_NAME_PATTERN.match(name):
                issues.append(_issue("WARNING", sheet, name, "Name",
                    f'"{name}" does not follow ISO 19650-2 naming convention'))
    return issues


def _check_uniclass(sheets: dict) -> list:
    issues = []
    if "Type" not in sheets or sheets["Type"].empty:
        return issues
    for _, row in sheets["Type"].iterrows():
        name     = row.get("Name", "Unknown")
        category = str(row.get("Category", ""))
        if category in ("Unclassified", "TBC", "", "nan"):
            issues.append(_issue("WARNING", "Type", name, "Category",
                "No Uniclass 2015 classification assigned"))
        elif not UNICLASS_PATTERN.match(category):
            issues.append(_issue("INFO", "Type", name, "Category",
                f'"{category}" may not be a valid Uniclass 2015 code'))
    return issues


def _check_warranty(sheets: dict) -> list:
    issues = []
    if "Type" not in sheets or sheets["Type"].empty:
        return issues
    for _, row in sheets["Type"].iterrows():
        name = row.get("Name", "Unknown")
        for field in ["WarrantyDurationParts", "WarrantyGuarantorParts", "ExpectedLife"]:
            val = str(row.get(field, "TBC"))
            if val in ("TBC", "", "nan"):
                issues.append(_issue("INFO", "Type", name, field,
                    f'"{field}" not specified — required for asset management'))
    return issues


def _check_maintenance(sheets: dict) -> list:
    issues = []
    if "Type" not in sheets or sheets["Type"].empty:
        return issues
    type_names = set(sheets["Type"]["Name"].tolist())
    job_types  = set()
    if "Job" in sheets and not sheets["Job"].empty:
        job_types = set(sheets["Job"]["TypeName"].tolist())

    for t in type_names:
        if t not in job_types:
            issues.append(_issue("INFO", "Job", t, "TypeName",
                f'No maintenance job defined for "{t}" — SFG20 compliance may be affected'))
    return issues


def _check_documents(sheets: dict) -> list:
    issues = []
    if "Component" not in sheets or sheets["Component"].empty:
        return issues
    component_names = set(sheets["Component"]["Name"].tolist())
    documented      = set()
    if "Document" in sheets and not sheets["Document"].empty:
        documented = set(sheets["Document"]["RowName"].tolist())

    undocumented = component_names - documented
    if undocumented:
        issues.append(_issue("WARNING", "Document", f"{len(undocumented)} components",
            "File", f"{len(undocumented)} components have no O&M document reference"))
    return issues


def _calc_completeness(sheets: dict) -> float:
    """Calculate overall COBie data completeness (0.0 to 1.0)."""
    total = 0
    filled = 0
    for sheet_name, df in sheets.items():
        if df.empty:
            continue
        for _, row in df.iterrows():
            for val in row:
                total += 1
                if str(val) not in ("TBC", "", "nan", "None"):
                    filled += 1
    return filled / total if total > 0 else 0.0


def _check_riba_stage(sheets: dict, riba_stage: str) -> list:
    issues = []
    config = RIBA_THRESHOLDS.get(riba_stage)
    if not config:
        return issues

    # Check required sheets present
    for s in config["required_sheets"]:
        if s not in sheets or sheets[s].empty:
            issues.append(_issue("CRITICAL", s, "-", "-",
                f'Sheet "{s}" required for {riba_stage} gate'))

    # Check completeness
    completeness = _calc_completeness(sheets)
    threshold    = config["min_completion"]
    if completeness < threshold:
        issues.append(_issue(
            "CRITICAL" if completeness < threshold * 0.8 else "WARNING",
            "All", "-", "Completeness",
            f"Data completeness {completeness:.0%} is below {riba_stage} threshold of {threshold:.0%}"
        ))
    return issues, completeness


# ── Main validator ────────────────────────────────────────────────────────────

def validate_cobie(sheets: dict, riba_stage: str = "Handover") -> dict:
    """
    Run full validation suite.
    Returns dict with issues list, counts, completeness, and pass/fail.
    """
    all_issues = []
    all_issues += _check_mandatory_sheets(sheets)
    all_issues += _check_mandatory_fields(sheets)
    all_issues += _check_naming(sheets)
    all_issues += _check_uniclass(sheets)
    all_issues += _check_warranty(sheets)
    all_issues += _check_maintenance(sheets)
    all_issues += _check_documents(sheets)

    riba_issues, completeness = _check_riba_stage(sheets, riba_stage)
    all_issues += riba_issues

    critical = sum(1 for i in all_issues if i["Severity"] == "CRITICAL")
    warnings = sum(1 for i in all_issues if i["Severity"] == "WARNING")
    info     = sum(1 for i in all_issues if i["Severity"] == "INFO")

    return {
        "issues":       pd.DataFrame(all_issues) if all_issues else pd.DataFrame(),
        "critical":     critical,
        "warnings":     warnings,
        "info":         info,
        "completeness": completeness,
        "pass":         critical == 0,
        "riba_stage":   riba_stage,
    }
