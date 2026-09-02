"""Check the pilot output contract without treating valid JSON as accurate OCR."""

import math

ITEM_TYPES = {
    "story",
    "brief",
    "ad",
    "listing",
    "graphic",
    "caption",
    "furniture",
    "unknown",
}
ROLES = {"headline", "byline", "body", "caption", "image", "other"}


def valid_bbox(box):
    return (
        isinstance(box, list)
        and len(box) == 4
        and all(type(v) in (int, float) and math.isfinite(v) for v in box)
        and 0 <= box[0] < box[2] <= 1000
        and 0 <= box[1] < box[3] <= 1000
    )


def validate(data):
    errors = []
    if not isinstance(data, dict):
        return ["root must be an object"]
    if type(data.get("page_complete")) is not bool:
        errors.append("page_complete must be boolean")
    unreadable = data.get("unreadable_regions")
    if not isinstance(unreadable, list) or any(
        not valid_bbox(box) for box in unreadable
    ):
        errors.append("invalid unreadable_regions")
    items = data.get("items")
    if not isinstance(items, list):
        return errors + ["items must be an array"]
    ids = set()
    for index, item in enumerate(items):
        prefix = f"items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        identity = item.get("id")
        if not isinstance(identity, str) or not identity or identity in ids:
            errors.append(f"{prefix}: invalid or duplicate id")
        else:
            ids.add(identity)
        if not isinstance(item.get("type"), str) or item["type"] not in ITEM_TYPES:
            errors.append(f"{prefix}: invalid item type")
        for field in ("headline", "byline", "body", "continuation_marker"):
            if field not in item or (
                item[field] is not None and not isinstance(item[field], str)
            ):
                errors.append(f"{prefix}: missing or invalid {field}")
        flags = item.get("quality_flags")
        if not isinstance(flags, list) or any(not isinstance(f, str) for f in flags):
            errors.append(f"{prefix}: invalid quality_flags")
        regions = item.get("regions")
        if not isinstance(regions, list):
            errors.append(f"{prefix}: regions must be an array")
            continue
        orders = set()
        for number, region in enumerate(regions):
            label = f"{prefix}.regions[{number}]"
            if not isinstance(region, dict):
                errors.append(f"{label}: must be an object")
                continue
            if not valid_bbox(region.get("bbox")):
                errors.append(f"{label}: invalid bbox")
            if not isinstance(region.get("role"), str) or region["role"] not in ROLES:
                errors.append(f"{label}: invalid role")
            order = region.get("order")
            if type(order) is not int or order < 0 or order in orders:
                errors.append(f"{label}: invalid or duplicate order")
            else:
                orders.add(order)
    return errors
