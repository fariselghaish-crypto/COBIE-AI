"""
ai_enricher.py
OpenAI GPT-based IFC to COBie enrichment module.
"""

from openai import OpenAI
import json
import re


def _defaults(el_type: str) -> dict:
    return {
        "description": f"{el_type} building element",
        "uniclass": "Unclassified",
        "manufacturer": "TBC",
        "model": "TBC",
        "warrantyYears": 2,
        "warrantyProvider": "TBC",
        "lifeYears": 25,
        "replacementCost": "TBC",
        "space": "TBC",
        "installDate": "TBC",
        "serial": "TBC",
        "maintenance": f"Annual inspection of {el_type}",
        "maintenanceDuration": "2",
        "frequency": "Annual",
        "document": "TBC",
        "category": el_type,
    }


def _extract_json(text: str) -> dict:
    if not text:
        return {}

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except Exception:
            pass

    brace = re.search(r"\{[\s\S]*\}", text)
    if brace:
        try:
            return json.loads(brace.group())
        except Exception:
            pass

    try:
        return json.loads(text)
    except Exception:
        return {}


def enrich_element_type(client, el_type: str, el_name: str, props: dict, type_cache: dict) -> dict:
    if el_type in type_cache:
        return type_cache[el_type]

    prop_summary = ""
    if props:
        sample = dict(list(props.items())[:10])
        prop_summary = f"\nIFC Properties sample: {json.dumps(sample, default=str)}"

    prompt = f"""You are a UK BIM COBie data enrichment engine with expert knowledge of:
- Uniclass 2015 classification
- COBie UK 2012
- ISO 19650 asset information standards
- SFG20 maintenance task logic
- UK construction industry norms

Generate COBie asset enrichment data for this IFC element type.

Element Type: {el_type}
Element Name: {el_name}
{prop_summary}

Return ONLY valid JSON with these exact fields:
{{
  "description": "One sentence technical description of this asset type",
  "uniclass": "Uniclass 2015 code e.g. Ss_25_14_25_47",
  "manufacturer": "Typical UK manufacturer or TBC if generic",
  "model": "Typical model reference or TBC",
  "warrantyYears": 2,
  "warrantyProvider": "Manufacturer or Contractor",
  "lifeYears": 30,
  "replacementCost": "£5,000",
  "space": "Typical space this asset occupies e.g. Plant Room",
  "installDate": "TBC",
  "serial": "TBC",
  "maintenance": "Brief SFG20-aligned PPM task description",
  "maintenanceDuration": "2",
  "frequency": "Annual",
  "document": "O&M Manual Rev A",
  "category": "Asset category name"
}}

No explanation. No markdown. JSON only."""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.2,
        )

        text = response.choices[0].message.content
        result = _extract_json(text)

        if not isinstance(result, dict) or not result.get("description"):
            raise ValueError("Invalid GPT JSON response")

        type_cache[el_type] = result
        return result

    except Exception:
        fallback = _defaults(el_type)
        type_cache[el_type] = fallback
        return fallback


def enrich_all(elements: list[dict], api_key: str, progress_callback=None) -> tuple[dict, list[str]]:
    client = OpenAI(api_key=api_key)

    type_cache = {}
    enrichments = {}
    log = []

    unique_types = sorted({e["type"] for e in elements})
    total = len(unique_types)

    for i, el_type in enumerate(unique_types):
        rep = next(e for e in elements if e["type"] == el_type)

        data = enrich_element_type(
            client=client,
            el_type=el_type,
            el_name=rep["name"],
            props=rep.get("props", {}),
            type_cache=type_cache,
        )

        got_ai = data.get("uniclass", "Unclassified") != "Unclassified"

        log.append(
            f"[{i + 1}/{total}] {el_type} | "
            f"Uniclass: {data.get('uniclass', 'TBC')} | "
            f"Life: {data.get('lifeYears', '?')} yr | "
            f"{'AI ok' if got_ai else 'defaults used'}"
        )

        if progress_callback:
            progress_callback(i + 1, total, el_type)

    for el in elements:
        enrichments[el["guid"]] = dict(type_cache.get(el["type"], _defaults(el["type"])))

    log.append(f"Enrichment complete: {len(elements)} elements from {total} type calls")
    return enrichments, log
