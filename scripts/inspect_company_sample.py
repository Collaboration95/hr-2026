#!/usr/bin/env python3
"""Audit the local SystemEarth company sample using only Python's standard library."""
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import date
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data/company-sample/2026-10-12"
OUT = ROOT / "docs/research/company-sample-audit.json"
CSV_PATH = SAMPLE / "200001-17plots-valid_2025-08-02T09_11_12Z.csv"
GEO_PATH = SAMPLE / "200001-17plots-valid.geojson"
ATTACHMENTS = {CSV_PATH.name: Path("/Users/speedpowermac/.t3/userdata/attachments/b3e0712e-b7a4-435d-b51e-95d2744ef880-a3745b7d-9f8f-4209-bc11-cc8f560fc705-csv.csv"),
              GEO_PATH.name: Path("/Users/speedpowermac/.t3/userdata/attachments/b3e0712e-b7a4-435d-b51e-95d2744ef880-a171bf79-70c8-436c-8cc0-ad5729836e6d-geojson.geojson")}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def signed_area(ring):
    return sum(ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
               for i in range(len(ring) - 1)) / 2


def orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def intersects(a, b, c, d):
    return (orient(a, b, c) * orient(a, b, d) < 0 and
            orient(c, d, a) * orient(c, d, b) < 0)


def ring_issues(ring):
    issues = []
    if len(ring) < 4:
        issues.append("fewer_than_4_positions")
    if ring and ring[0] != ring[-1]:
        issues.append("ring_not_closed")
    n = len(ring) - 1
    for i in range(n):
        for j in range(i + 1, n):
            if j in (i, i + 1) or (i == 0 and j == n - 1):
                continue
            if intersects(ring[i], ring[i + 1], ring[j], ring[j + 1]):
                issues.append("self_intersection")
                return issues
    if abs(signed_area(ring)) < 1e-14:
        issues.append("zero_planar_area")
    return issues


def area_ha(ring):
    # Spherical trapezoidal approximation for small polygons, WGS84 lon/lat.
    radius = 6371008.8
    total = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(ring, ring[1:]):
        total += math.radians(lon2 - lon1) * (2 + math.sin(math.radians(lat1)) +
                                               math.sin(math.radians(lat2)))
    return abs(total * radius * radius / 2) / 10000


def parse_date(value):
    """Parse a compact YYYYMMDD date, returning a diagnostic instead of raising."""
    if not re.fullmatch(r"\d{8}", value or ""):
        return None, "invalid_format_expected_YYYYMMDD"
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8])), None
    except ValueError as exc:
        return None, f"invalid_calendar_date:{exc}"


def parse_processing_range(value):
    parts = (value or "").split("-")
    if len(parts) != 2:
        return None, None, "invalid_format_expected_YYYYMMDD-YYYYMMDD"
    start, start_error = parse_date(parts[0])
    end, end_error = parse_date(parts[1])
    return start, end, start_error or end_error


def main():
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        headers = reader.fieldnames or []
    collection = json.loads(GEO_PATH.read_text(encoding="utf-8"))
    features = collection.get("features", [])
    csv_ids = [r.get("a3_plot_id", "") for r in rows]
    geo_ids = [x.get("properties", {}).get("ProductionPlace", "") for x in features]
    crs = collection.get("crs")
    geo_details = []
    all_points = []
    for feature in features:
        props = feature.get("properties", {})
        geom = feature.get("geometry") or {}
        rings = (geom.get("coordinates", []) if geom.get("type") == "Polygon" else [])
        outer = rings[0] if rings else []
        issues = []
        if geom.get("type") != "Polygon":
            issues.append("geometry_not_polygon")
        if len(rings) != 1:
            issues.append("unexpected_ring_count")
        for ring in rings:
            issues.extend(ring_issues(ring))
            all_points.extend(ring[:-1])
        computed = area_ha(outer) if outer and outer[0] == outer[-1] else None
        declared = props.get("Area")
        delta = computed - float(declared) if computed is not None and declared is not None else None
        geo_details.append({"id": props.get("ProductionPlace"), "geometry_type": geom.get("type"),
                            "coordinate_count": sum(len(r) for r in rings), "ring_count": len(rings),
                            "validity_checks": "closed rings, nonzero planar area, no proper self-crossings; not a full OGC validator",
                            "issues": sorted(set(issues)), "declared_area_ha": declared,
                            "computed_spherical_approx_area_ha": round(computed, 4) if computed is not None else None,
                            "area_delta_ha": round(delta, 4) if delta is not None else None,
                            "area_delta_pct_of_declared": round(delta / float(declared) * 100, 2) if delta is not None and float(declared) else None})
    c_counts = Counter(csv_ids)
    g_counts = Counter(geo_ids)
    csv_unique, geo_unique = set(csv_ids), set(geo_ids)
    csv_by_id = {r.get("a3_plot_id", ""): r for r in rows}
    geo_by_id = {f.get("properties", {}).get("ProductionPlace", ""): f for f in features}
    declared_area_comparisons = []
    for plot_id in sorted(csv_unique & geo_unique):
        csv_raw = csv_by_id[plot_id].get("a7_size_of_plot_ha", "")
        geo_raw = geo_by_id[plot_id].get("properties", {}).get("Area")
        try:
            csv_area, geo_area = float(csv_raw), float(geo_raw)
            equal = csv_area == geo_area
            difference = csv_area - geo_area
        except (TypeError, ValueError):
            csv_area = geo_area = difference = None
            equal = None
        declared_area_comparisons.append({"plot_id": plot_id, "csv_declared_area_ha": csv_area,
                                          "geojson_declared_area_ha": geo_area,
                                          "numerically_equal": equal,
                                          "csv_minus_geojson_ha": difference})
    date_rows = []
    chronology_counts = Counter()
    for r in rows:
        processing_raw = r.get("a4_processing_date", "")
        harvest_raw = r.get("a5_production_harvest_date", "")
        start, end, range_error = parse_processing_range(processing_raw)
        harvest, harvest_error = parse_date(harvest_raw)
        if range_error:
            chronology = "invalid_processing_range"
        elif end < start:
            chronology = "processing_range_end_precedes_start_review"
        elif harvest_error:
            chronology = "invalid_harvest_date"
        elif end < harvest:
            chronology = "processing_range_precedes_harvest_semantics_need_clarification"
        elif start > harvest:
            chronology = "processing_range_follows_harvest_review_semantics"
        else:
            chronology = "processing_range_overlaps_harvest_date"
        chronology_counts[chronology] += 1
        date_rows.append({"plot_id": r.get("a3_plot_id"), "processing_raw": processing_raw,
                          "processing_start": start.isoformat() if start else None,
                          "processing_end": end.isoformat() if end else None,
                          "processing_parse_error": range_error,
                          "harvest_raw": harvest_raw,
                          "harvest_date": harvest.isoformat() if harvest else None,
                          "harvest_parse_error": harvest_error,
                          "chronology_diagnostic": chronology})
    fields = {}
    for h in headers:
        vals = [r.get(h, "") for r in rows]
        fields[h] = {"missing_or_blank": sum(v is None or not str(v).strip() for v in vals),
                      "distinct_nonblank": len({str(v).strip() for v in vals if v is not None and str(v).strip()}),
                      "values": dict(Counter(str(v).strip() for v in vals))}
    review = []
    for r in rows:
        if r.get("c2_deforestation_spatial_analysis_result", "").startswith("b."):
            review.append({"plot_id": r["a3_plot_id"], "signal": "supplier_record_indicates_deforestation",
                           "analysis_layer": r.get("c1_indicate_deforestation_analysis_layer_used"),
                           "mitigation": r.get("c3_mitigation_if_indication_found"),
                           "reference": r.get("c4_reference_or_link_if_applicable"),
                           "final_status": r.get("c5_deforestation_final_status"),
                           "eudr_status": r.get("i1_eudr_status"),
                           "interpretation": "Review lead only; supplier declaration does not establish a violation or independently verified result."})
    result = {
        "audit_scope": "Local inspection only; no upload or external data access.",
        "files": [{"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "sha256": sha(p)} for p in (CSV_PATH, GEO_PATH)],
        "attachment_copy_comparison": [{"attachment_path": str(ATTACHMENTS[p.name]),
                                         "attachment_available": ATTACHMENTS[p.name].is_file(),
                                         "attachment_sha256": sha(ATTACHMENTS[p.name]) if ATTACHMENTS[p.name].is_file() else None,
                                         "sample_sha256": sha(p),
                                         "byte_identical": sha(ATTACHMENTS[p.name]) == sha(p) if ATTACHMENTS[p.name].is_file() else None}
                                        for p in (CSV_PATH, GEO_PATH)],
        "csv": {"record_count": len(rows), "field_count": len(headers), "headers": headers,
                "duplicate_plot_ids": {k: v for k, v in c_counts.items() if v > 1},
                "blank_plot_ids": sum(not x.strip() for x in csv_ids), "field_profile": fields,
                "processing_dates": sorted({r.get("a4_processing_date", "") for r in rows}),
                "harvest_dates": sorted({r.get("a5_production_harvest_date", "") for r in rows}),
                "date_validation": {"processing_format": "YYYYMMDD-YYYYMMDD", "harvest_format": "YYYYMMDD",
                                    "records": date_rows, "chronology_counts": dict(chronology_counts),
                                    "interpretation": "A processing range ending before the harvest date is reported for semantic clarification, not classified as an error."}},
        "geojson": {"declared_type": collection.get("type"), "crs_member": crs,
                    "crs_interpretation": "RFC 7946 GeoJSON defaults to WGS 84 longitude/latitude in decimal degrees; no explicit legacy CRS member is present.",
                    "feature_count": len(features), "geometry_types": dict(Counter(x.get("geometry", {}).get("type") for x in features)),
                    "duplicate_plot_ids": {k: v for k, v in g_counts.items() if v > 1},
                    "bounds_lon_lat": [min(p[0] for p in all_points), min(p[1] for p in all_points), max(p[0] for p in all_points), max(p[1] for p in all_points)] if all_points else None,
                    "geographic_implication": "Extent is consistent with the 10N_090E tile area and appears to omit Songkhla; province labels were not independently validated.",
                    "coordinate_count": len(all_points), "feature_checks": geo_details},
        "join": {"csv_unique_ids": len(csv_unique), "geo_unique_ids": len(geo_unique),
                 "matched_unique_ids": sorted(csv_unique & geo_unique), "csv_only_ids": sorted(csv_unique - geo_unique),
                 "geo_only_ids": sorted(geo_unique - csv_unique), "csv_id_multiplicity": dict(c_counts),
                 "geo_id_multiplicity": dict(g_counts), "join_is_one_to_one": csv_unique == geo_unique and all(v == 1 for v in c_counts.values()) and all(v == 1 for v in g_counts.values()),
                 "declared_area_comparison": {"compared_plot_count": len(declared_area_comparisons),
                                               "all_numerically_equal": all(x["numerically_equal"] is True for x in declared_area_comparisons),
                                               "mismatches_or_unparseable": [x for x in declared_area_comparisons if x["numerically_equal"] is not True],
                                               "records": declared_area_comparisons}},
        "supplier_record_review_examples": review,
        "caveats": ["This sample inspection does not validate declarations, satellite evidence, legal status, or compliance.",
                    "Spherical area is an approximate geometry-derived comparison, not a survey-area determination.",
                    "Geometric checks are intentionally limited and are not a complete OGC validity certification."]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT.relative_to(ROOT)), "csv_rows": len(rows), "geo_features": len(features),
                      "csv_only": result["join"]["csv_only_ids"], "geo_only": result["join"]["geo_only_ids"],
                      "supplier_review_ids": [x["plot_id"] for x in review],
                      "geometry_issue_count": sum(bool(x["issues"]) for x in geo_details)}, indent=2))


if __name__ == "__main__":
    main()
