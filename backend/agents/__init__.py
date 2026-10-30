"""The five Campus Customs roles. Each file defines one role: its prompt file and its MCP tools."""
from backend.agents.accounting import ROLE as ACCOUNTING
from backend.agents.boss import ROLE as BOSS
from backend.agents.customer_service import ROLE as CUSTOMER_SERVICE
from backend.agents.facilities import ROLE as FACILITIES
from backend.agents.inventory import ROLE as INVENTORY

ROLES = {r.name: r for r in (BOSS, INVENTORY, ACCOUNTING, FACILITIES, CUSTOMER_SERVICE)}
