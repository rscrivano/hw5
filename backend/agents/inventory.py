"""Inventory - stock by SKU/size, shortfalls, inventory health, which vendor can restock and when."""
from backend.models import AgentRole

ROLE = AgentRole(
    name="Inventory",
    prompt_file="inventory.md",
    description="stock by SKU/size, shortfalls, inventory health, reserving stock, restock vendor and ETA",
    mcp_tools=frozenset({"get_today", "get_ticket", "check_stock", "list_inventory", "inventory_health_check",
                         "check_shortfall", "reserve_stock", "list_vendors", "vendor_status",
                         "find_restock_vendor", "list_purchase_orders"}),
)
