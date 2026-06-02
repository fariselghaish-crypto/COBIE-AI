"""
ifc_parser.py
Parses IFC files using IFCOpenShell.
Extracts element identity, type, and property sets.
"""

import ifcopenshell
import ifcopenshell.util.element as ifc_util

# IFC types to extract — covers structural, architectural, MEP
ELEMENT_TYPES = [
    "IfcWall", "IfcWallStandardCase",
    "IfcSlab",
    "IfcColumn",
    "IfcBeam",
    "IfcDoor",
    "IfcWindow",
    "IfcStair", "IfcStairFlight",
    "IfcRoof",
    "IfcRamp",
    "IfcSpace",
    "IfcBuildingStorey",
    "IfcBuilding",
    "IfcSite",
    "IfcFurnishingElement",
    "IfcFlowSegment",
    "IfcPump",
    "IfcFan",
    "IfcBoiler",
    "IfcChiller",
    "IfcAirTerminal",
    "IfcAirHandlingUnit",
    "IfcDuctFitting",
    "IfcPipeFitting",
    "IfcValve",
    "IfcElectricAppliance",
    "IfcLightFixture",
    "IfcOutlet",
    "IfcSwitchingDevice",
    "IfcProtectiveDevice",
    "IfcCableSegment",
    "IfcFireSuppressionTerminal",
    "IfcSanitaryTerminal",
]

# Human readable labels
TYPE_LABELS = {
    "IfcWallStandardCase": "Wall",
    "IfcStairFlight": "Stair",
}


def _get_properties(element) -> dict:
    """Extract all property set values from an IFC element."""
    props = {}
    try:
        psets = ifc_util.get_psets(element)
        for pset_name, pset_props in psets.items():
            for prop_name, value in pset_props.items():
                if prop_name == "id":
                    continue
                key = f"{pset_name}.{prop_name}"
                props[key] = str(value) if value is not None else ""
    except Exception:
        pass
    return props


def _get_floor(element, model) -> str:
    """Try to find which storey an element belongs to."""
    try:
        for rel in model.by_type("IfcRelContainedInSpatialStructure"):
            if element in rel.RelatedElements:
                container = rel.RelatingStructure
                if container.is_a("IfcBuildingStorey"):
                    return container.Name or "Level-01"
    except Exception:
        pass
    return "TBC"


def parse_ifc(file_path: str) -> list[dict]:
    """
    Open an IFC file and return a list of element dicts.
    Each dict contains: guid, type, name, floor, props
    """
    model = ifcopenshell.open(file_path)
    elements = []
    seen_guids = set()

    for ifc_type in ELEMENT_TYPES:
        try:
            items = model.by_type(ifc_type)
        except Exception:
            continue

        label = TYPE_LABELS.get(ifc_type, ifc_type.replace("Ifc", ""))

        for el in items:
            guid = el.GlobalId
            if guid in seen_guids:
                continue
            seen_guids.add(guid)

            name = el.Name or f"{label}-{el.id()}"
            props = _get_properties(el)
            floor = _get_floor(el, model)

            elements.append({
                "guid":  guid,
                "type":  label,
                "name":  name,
                "floor": floor,
                "props": props,
            })

    return elements


def get_summary(elements: list[dict]) -> dict:
    """Return count per type for display."""
    summary = {}
    for el in elements:
        summary[el["type"]] = summary.get(el["type"], 0) + 1
    return dict(sorted(summary.items(), key=lambda x: -x[1]))
