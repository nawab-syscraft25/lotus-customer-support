from .search import search_products, search_products_schema
from .auth import check_user, check_user_schema, send_otp, send_otp_schema, verify_otp, verify_otp_schema, sign_in, sign_in_schema
from .order import get_orders, get_orders_schema
from .offers import get_current_offers, get_current_offers_schema
from .check_delivery import check_product_delivery, check_product_delivery_schema
from .near_stores import check_near_stores, check_near_stores_schema


tool_registry = {
    "check_user": (check_user, check_user_schema),
    # "send_otp": (send_otp, send_otp_schema),
    # "verify_otp": (verify_otp, verify_otp_schema),
    "get_orders": (get_orders, get_orders_schema),
    "sign_in":(sign_in,sign_in_schema),
    "check_product_delivery": (check_product_delivery, check_product_delivery_schema),
    "check_near_stores": (check_near_stores, check_near_stores_schema),
}

def is_authenticated(memory: dict) -> bool:
    return bool(memory.get("auth_token")) 

