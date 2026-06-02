"""
cobie_builder.py
Builds all COBie UK 2012 sheets from parsed IFC elements
and AI enrichment data.
Returns a dict of sheet_name → pandas DataFrame.
"""

import pandas as pd
from datetime import datetime

NOW = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
CREATED_BY = "cobie-pipeline@project.com"


def _contact_sheet() -> pd.DataFrame:
    return pd.DataFrame([{
        "Name":         CREATED_BY,
        "CreatedBy":    CREATED_BY,
        "CreatedOn":    NOW,
        "Category":     "Consultant",
        "Company":      "Project BIM Team",
        "Phone":        "TBC",
        "Email":        CREATED_BY,
        "Department":   "BIM",
        "OrganizationCode": "BIM-01",
        "GivenName":    "BIM",
        "FamilyName":   "Engineer",
        "Street":       "TBC",
        "PostalBox":    "TBC",
        "Town":         "TBC",
        "StateRegion":  "TBC",
        "PostalCode":   "TBC",
        "Country":      "United Kingdom",
        "URL":          "TBC",
    }])


def _facility_sheet(elements: list) -> pd.DataFrame:
    # Try to find building name from elements
    building = next((e for e in elements if e["type"] == "Building"), None)
    site     = next((e for e in elements if e["type"] == "Site"), None)
    return pd.DataFrame([{
        "Name":             building["name"] if building else "Facility-001",
        "CreatedBy":        CREATED_BY,
        "CreatedOn":        NOW,
        "Category":         "Building",
        "ProjectName":      "IFC Project",
        "SiteName":         site["name"] if site else "Site-001",
        "LinearUnits":      "millimeters",
        "AreaUnits":        "squaremeters",
        "VolumeUnits":      "cubicmeters",
        "CurrencyUnit":     "GBP",
        "AreaMeasurement":  "GIA",
        "ExternalSystem":   "IFCOpenShell",
        "ExternalObject":   "IfcBuilding",
        "ExternalIdentifier": building["guid"] if building else "TBC",
        "Description":      "Facility extracted from IFC model",
    }])


def _floor_sheet(elements: list) -> pd.DataFrame:
    rows = []
    for el in elements:
        if el["type"] == "BuildingStorey":
            rows.append({
                "Name":        el["name"],
                "CreatedBy":   CREATED_BY,
                "CreatedOn":   NOW,
                "Category":    "Floor",
                "ExternalSystem":    "IFCOpenShell",
                "ExternalObject":    "IfcBuildingStorey",
                "ExternalIdentifier": el["guid"],
                "Description": el["name"],
                "Elevation":   el["props"].get("Pset_BuildingStoreyCommon.AboveGround", "TBC"),
                "Height":      "TBC",
            })
    if not rows:
        rows.append({"Name": "Level-01", "CreatedBy": CREATED_BY, "CreatedOn": NOW,
                     "Category": "Floor", "ExternalSystem": "IFCOpenShell",
                     "ExternalObject": "IfcBuildingStorey", "ExternalIdentifier": "TBC",
                     "Description": "Ground Floor", "Elevation": "0", "Height": "TBC"})
    return pd.DataFrame(rows)


def _space_sheet(elements: list, enrichments: dict) -> pd.DataFrame:
    rows = []
    for el in elements:
        if el["type"] == "Space":
            enrich = enrichments.get(el["guid"], {})
            rows.append({
                "Name":        el["name"],
                "CreatedBy":   CREATED_BY,
                "CreatedOn":   NOW,
                "Category":    enrich.get("category", "Office"),
                "FloorName":   el.get("floor", "Level-01"),
                "Description": enrich.get("description", el["name"]),
                "ExternalSystem":    "IFCOpenShell",
                "ExternalObject":    "IfcSpace",
                "ExternalIdentifier": el["guid"],
                "RoomTag":     el["name"],
                "UsableHeight": "TBC",
                "GrossArea":   el["props"].get("Qto_SpaceBaseQuantities.GrossFloorArea", "TBC"),
                "NetArea":     el["props"].get("Qto_SpaceBaseQuantities.NetFloorArea", "TBC"),
            })
    if not rows:
        rows.append({"Name": "Space-001", "CreatedBy": CREATED_BY, "CreatedOn": NOW,
                     "Category": "Office", "FloorName": "Level-01",
                     "Description": "Default space", "ExternalSystem": "IFCOpenShell",
                     "ExternalObject": "IfcSpace", "ExternalIdentifier": "TBC",
                     "RoomTag": "001", "UsableHeight": "TBC",
                     "GrossArea": "TBC", "NetArea": "TBC"})
    return pd.DataFrame(rows)


def _zone_sheet(elements: list) -> pd.DataFrame:
    """Basic zone sheet — one zone per floor."""
    floors = {el["floor"] for el in elements if el.get("floor") and el["floor"] != "TBC"}
    if not floors:
        floors = {"Level-01"}
    rows = [{
        "Name":      f"Zone-{floor}",
        "CreatedBy": CREATED_BY,
        "CreatedOn": NOW,
        "Category":  "General",
        "SpaceNames": floor,
        "Description": f"Zone for {floor}",
        "ExternalSystem": "IFCOpenShell",
        "ExternalObject": "IfcZone",
        "ExternalIdentifier": f"Zone-{floor}",
    } for floor in sorted(floors)]
    return pd.DataFrame(rows)


def _type_sheet(elements: list, enrichments: dict) -> pd.DataFrame:
    rows = []
    seen = set()
    skip = {"Building", "Site", "BuildingStorey", "Space"}

    for el in elements:
        if el["type"] in skip:
            continue
        type_name = f"{el['type']}-Type"
        if type_name in seen:
            continue
        seen.add(type_name)

        enrich = enrichments.get(el["guid"], {})
        rows.append({
            "Name":                  type_name,
            "CreatedBy":             CREATED_BY,
            "CreatedOn":             NOW,
            "Category":              enrich.get("uniclass", "Unclassified"),
            "Description":           enrich.get("description", el["type"]),
            "AssetType":             "Fixed",
            "Manufacturer":          enrich.get("manufacturer", "TBC"),
            "ModelNumber":           enrich.get("model", "TBC"),
            "WarrantyGuarantorParts": enrich.get("warrantyProvider", "TBC"),
            "WarrantyDurationParts": f"{enrich.get('warrantyYears', 'TBC')} Years",
            "WarrantyGuarantorLabor": enrich.get("warrantyProvider", "TBC"),
            "WarrantyDurationLabor": f"{enrich.get('warrantyYears', 'TBC')} Years",
            "ReplacementCost":       enrich.get("replacementCost", "TBC"),
            "ExpectedLife":          f"{enrich.get('lifeYears', 'TBC')} Years",
            "NominalLength":         el["props"].get("Qto_WallBaseQuantities.Length", "TBC"),
            "NominalWidth":          "TBC",
            "NominalHeight":         "TBC",
            "Shape":                 "TBC",
            "Size":                  "TBC",
            "Color":                 "TBC",
            "Finish":                "TBC",
            "Grade":                 "TBC",
            "Material":              el["props"].get("Pset_MaterialCommon.Category", "TBC"),
            "Constituents":          "TBC",
            "Features":              "TBC",
            "AccessibilityPerformance": "TBC",
            "CodePerformance":       "TBC",
            "SustainabilityPerformance": "TBC",
            "ExternalSystem":        "IFCOpenShell",
            "ExternalObject":        f"Ifc{el['type']}Type",
            "ExternalIdentifier":    el["guid"],
        })
    return pd.DataFrame(rows)


def _component_sheet(elements: list, enrichments: dict) -> pd.DataFrame:
    rows = []
    skip = {"Building", "Site", "BuildingStorey", "Space"}

    for el in elements:
        if el["type"] in skip:
            continue
        enrich = enrichments.get(el["guid"], {})
        rows.append({
            "Name":              el["name"],
            "CreatedBy":         CREATED_BY,
            "CreatedOn":         NOW,
            "TypeName":          f"{el['type']}-Type",
            "Space":             enrich.get("space", el.get("floor", "TBC")),
            "Description":       enrich.get("description", ""),
            "ExternalSystem":    "IFCOpenShell",
            "ExternalObject":    f"Ifc{el['type']}",
            "ExternalIdentifier": el["guid"],
            "SerialNumber":      enrich.get("serial", "TBC"),
            "InstallationDate":  enrich.get("installDate", "TBC"),
            "WarrantyStartDate": enrich.get("installDate", "TBC"),
            "TagNumber":         el["guid"][:10],
            "BarCode":           "TBC",
            "AssetIdentifier":   el["guid"],
        })
    return pd.DataFrame(rows)


def _system_sheet(elements: list) -> pd.DataFrame:
    """Group MEP elements into systems."""
    mep_types = {"Pump", "Fan", "Boiler", "Chiller", "AirTerminal",
                 "AirHandlingUnit", "DuctFitting", "PipeFitting",
                 "Valve", "FlowSegment"}
    mep = [e for e in elements if e["type"] in mep_types]
    if not mep:
        return pd.DataFrame()

    rows = [{
        "Name":        f"System-MEP-{i+1:03d}",
        "CreatedBy":   CREATED_BY,
        "CreatedOn":   NOW,
        "Category":    "Mechanical",
        "ComponentNames": el["name"],
        "ExternalSystem": "IFCOpenShell",
        "ExternalObject": "IfcSystem",
        "ExternalIdentifier": el["guid"],
        "Description": f"MEP system containing {el['name']}",
    } for i, el in enumerate(mep[:50])]  # cap at 50
    return pd.DataFrame(rows)


def _document_sheet(elements: list, enrichments: dict) -> pd.DataFrame:
    rows = []
    skip = {"Building", "Site", "BuildingStorey", "Space"}

    for el in elements:
        if el["type"] in skip:
            continue
        enrich = enrichments.get(el["guid"], {})
        doc = enrich.get("document")
        if not doc or doc == "TBC":
            continue
        rows.append({
            "Name":          f"OM-{el['name']}",
            "CreatedBy":     CREATED_BY,
            "CreatedOn":     NOW,
            "Category":      "Operations and Maintenance",
            "ApprovalBy":    "TBC",
            "Stage":         "Handover",
            "SheetName":     "Component",
            "RowName":       el["name"],
            "Directory":     "./docs/",
            "File":          f"{el['name']}_OM.pdf",
            "ExternalSystem": "IFCOpenShell",
            "ExternalObject": "IfcDocumentReference",
            "ExternalIdentifier": el["guid"],
            "Description":   doc,
            "Reference":     doc,
        })
    return pd.DataFrame(rows)


def _job_sheet(elements: list, enrichments: dict) -> pd.DataFrame:
    rows = []
    skip = {"Building", "Site", "BuildingStorey", "Space"}
    seen_types = set()

    for el in elements:
        if el["type"] in skip:
            continue
        type_name = f"{el['type']}-Type"
        if type_name in seen_types:
            continue
        seen_types.add(type_name)

        enrich = enrichments.get(el["guid"], {})
        maintenance = enrich.get("maintenance")
        if not maintenance:
            continue

        rows.append({
            "Name":           f"PPM-{el['type']}-Annual",
            "CreatedBy":      CREATED_BY,
            "CreatedOn":      NOW,
            "Category":       "Preventive",
            "Status":         "planned",
            "TypeName":       type_name,
            "Description":    maintenance,
            "Duration":       enrich.get("maintenanceDuration", "2"),
            "DurationUnit":   "Hours",
            "Start":          "TBC",
            "TaskNumber":     f"T-{el['type'][:3].upper()}-001",
            "Priors":         "TBC",
            "ResourceNames":  "Facilities Manager",
            "ExternalSystem": "IFCOpenShell",
            "ExternalObject": "IfcTask",
            "ExternalIdentifier": el["guid"],
            "Frequency":      enrich.get("frequency", "Annual"),
            "FrequencyUnit":  "Year",
        })
    return pd.DataFrame(rows)


def _resource_sheet(elements: list, enrichments: dict) -> pd.DataFrame:
    """Maintenance resources — one per job type."""
    skip = {"Building", "Site", "BuildingStorey", "Space"}
    seen = set()
    rows = []

    for el in elements:
        if el["type"] in skip or el["type"] in seen:
            continue
        seen.add(el["type"])
        rows.append({
            "Name":      f"RES-{el['type']}",
            "CreatedBy": CREATED_BY,
            "CreatedOn": NOW,
            "Category":  "Labor",
            "JobNames":  f"PPM-{el['type']}-Annual",
            "Description": f"Technician for {el['type']} maintenance",
            "ExternalSystem": "IFCOpenShell",
            "ExternalObject": "IfcConstructionEquipmentResource",
            "ExternalIdentifier": el["guid"],
        })
    return pd.DataFrame(rows)


def _spare_sheet(elements: list, enrichments: dict) -> pd.DataFrame:
    """Spare parts — basic placeholder per type."""
    skip = {"Building", "Site", "BuildingStorey", "Space"}
    seen = set()
    rows = []

    for el in elements:
        if el["type"] in skip or el["type"] in seen:
            continue
        seen.add(el["type"])
        enrich = enrichments.get(el["guid"], {})
        rows.append({
            "Name":        f"SPARE-{el['type']}",
            "CreatedBy":   CREATED_BY,
            "CreatedOn":   NOW,
            "Category":    "Consumable",
            "TypeName":    f"{el['type']}-Type",
            "Suppliers":   enrich.get("manufacturer", "TBC"),
            "ExternalSystem": "IFCOpenShell",
            "ExternalObject": "IfcConstructionProductResource",
            "ExternalIdentifier": el["guid"],
            "SetNumber":   "TBC",
            "PartNumber":  "TBC",
            "Description": f"Spare parts for {el['type']}",
        })
    return pd.DataFrame(rows)


# ── Main builder ──────────────────────────────────────────────────────────────

def build_cobie(elements: list, enrichments: dict) -> dict[str, pd.DataFrame]:
    """
    Build all COBie UK 2012 sheets.
    Returns dict of sheet_name → DataFrame.
    """
    sheets = {
        "Contact":   _contact_sheet(),
        "Facility":  _facility_sheet(elements),
        "Floor":     _floor_sheet(elements),
        "Space":     _space_sheet(elements, enrichments),
        "Zone":      _zone_sheet(elements),
        "Type":      _type_sheet(elements, enrichments),
        "Component": _component_sheet(elements, enrichments),
        "System":    _system_sheet(elements),
        "Document":  _document_sheet(elements, enrichments),
        "Job":       _job_sheet(elements, enrichments),
        "Resource":  _resource_sheet(elements, enrichments),
        "Spare":     _spare_sheet(elements, enrichments),
    }
    # Drop empty sheets
    return {k: v for k, v in sheets.items() if v is not None and not v.empty}
