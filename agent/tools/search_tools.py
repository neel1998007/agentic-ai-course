"""
Search and lookup tools.
"""

import logging
from agent.tools.validator import validate_product_query, ValidationError

logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────
SEARCH_PRODUCT_SCHEMA = {
    "name": "search_product",
    "description": (
        "Searches for a product and returns its specifications and price. "
        "Use this when you need product details like price, screen size, "
        "camera specs, battery capacity, or processor. "
        "Works for smartphones currently. "
        "Do NOT use for: math calculations, comparisons, recommendations."
    ),
    "parameters": {
        "query": {
            "type"       : "string",
            "description": (
                "The product name to search for. "
                "Be specific with model names. "
                "Examples: 'iPhone 15', 'Samsung S24', 'Pixel 8'. "
                "Do NOT include: comparison words, price ranges, "
                "or multiple products in one query."
            ),
            "required"   : True,
        }
    },
    "examples": [
        {"input": "iPhone 15",   "output": "iPhone 15: ₹79,900. 6.1in..."},
        {"input": "Samsung S24", "output": "Samsung S24: ₹74,999. 6.2in..."},
    ]
}

COMPARE_PRODUCTS_SCHEMA = {
    "name": "compare_products",
    "description": (
        "Directly compares two products side by side. "
        "Use this AFTER searching for individual products "
        "when you need an explicit comparison. "
        "Input format: 'Product A vs Product B'"
    ),
    "parameters": {
        "comparison": {
            "type"       : "string",
            "description": (
                "Two product names separated by ' vs '. "
                "Example: 'iPhone 15 vs Samsung S24'. "
                "Always use ' vs ' as separator."
            ),
            "required"   : True,
        }
    },
    "examples": [
        {"input": "iPhone 15 vs Samsung S24",
         "output": "Comparison: iPhone 15 vs Samsung S24..."},
    ]
}


# ── Executors ─────────────────────────────────────────
# Fake data — replace with real API calls later
PRODUCT_DATABASE = {
    "iphone 15"   : {
        "name"   : "iPhone 15",
        "price"  : 79900,
        "screen" : "6.1in",
        "camera" : "48MP",
        "chip"   : "A16 Bionic",
        "battery": "3227mAh",
        "os"     : "iOS 17",
    },
    "samsung s24" : {
        "name"   : "Samsung S24",
        "price"  : 74999,
        "screen" : "6.2in",
        "camera" : "50MP",
        "chip"   : "Snapdragon 8 Gen 3",
        "battery": "4000mAh",
        "os"     : "Android 14",
    },
    "pixel 8"     : {
        "name"   : "Pixel 8",
        "price"  : 75999,
        "screen" : "6.2in",
        "camera" : "50MP",
        "chip"   : "Google Tensor G3",
        "battery": "4575mAh",
        "os"     : "Android 14",
    },
}


def search_product(query: str) -> str:
    """
    Search for product specs and price.
    Input : product name
    Output: specs string or error message
    """
    logger.debug(f"search_product called with: '{query}'")

    # Validate
    try:
        query = validate_product_query(query)
    except ValidationError as e:
        logger.warning(f"search_product validation failed: {e}")
        return f"Search error: {e}"

    # Search
    query_lower = query.lower()
    for key, product in PRODUCT_DATABASE.items():
        if key in query_lower or query_lower in key:
            result = (
                f"{product['name']}: "
                f"₹{product['price']:,}. "
                f"{product['screen']} screen. "
                f"{product['camera']} camera. "
                f"{product['chip']} chip. "
                f"{product['battery']} battery. "
                f"{product['os']}."
            )
            logger.info(f"search_product: found '{product['name']}'")
            return result

    logger.warning(f"search_product: no results for '{query}'")
    return (
        f"No product found for '{query}'. "
        f"Available products: iPhone 15, Samsung S24, Pixel 8."
    )


def compare_products(comparison: str) -> str:
    """
    Compare two products.
    Input : "Product A vs Product B"
    Output: comparison string
    """
    logger.debug(f"compare_products called with: '{comparison}'")

    # Validate format
    if " vs " not in comparison.lower():
        return (
            "Compare error: input must be in format 'Product A vs Product B'. "
            f"Got: '{comparison}'"
        )

    parts = comparison.lower().split(" vs ")
    if len(parts) != 2:
        return "Compare error: provide exactly two products separated by ' vs '"

    name_a, name_b = parts[0].strip(), parts[1].strip()

    # Look up both products
    product_a = None
    product_b = None

    for key, product in PRODUCT_DATABASE.items():
        if key in name_a or name_a in key:
            product_a = product
        if key in name_b or name_b in key:
            product_b = product

    if not product_a:
        return f"Compare error: '{name_a}' not found in database"
    if not product_b:
        return f"Compare error: '{name_b}' not found in database"

    # Build comparison
    price_diff   = abs(product_a['price'] - product_b['price'])
    cheaper      = product_a['name'] if product_a['price'] < product_b['price'] \
                   else product_b['name']
    battery_a    = int(product_a['battery'].replace('mAh', ''))
    battery_b    = int(product_b['battery'].replace('mAh', ''))
    better_batt  = product_a['name'] if battery_a > battery_b \
                   else product_b['name']
    batt_diff    = abs(battery_a - battery_b)

    result = (
        f"Comparison: {product_a['name']} vs {product_b['name']}. "
        f"Price: {cheaper} is cheaper by ₹{price_diff:,}. "
        f"Battery: {better_batt} has better battery by {batt_diff}mAh. "
        f"Camera: both have similar camera resolution. "
        f"{product_a['name']}: ₹{product_a['price']:,}, {product_a['battery']}. "
        f"{product_b['name']}: ₹{product_b['price']:,}, {product_b['battery']}."
    )

    logger.info(f"compare_products: compared {product_a['name']} vs {product_b['name']}")
    return result