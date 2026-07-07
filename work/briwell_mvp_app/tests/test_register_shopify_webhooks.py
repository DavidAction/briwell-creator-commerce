from scripts.register_shopify_webhooks import WEBHOOK_TOPICS, _desired


def test_desired_maps_topics_to_receiver_paths_and_strips_trailing_slash() -> None:
    desired = _desired("https://api.briwell.co/")
    assert desired == {
        "orders/create": "https://api.briwell.co/commerce/webhooks/shopify/orders",
        "orders/updated": "https://api.briwell.co/commerce/webhooks/shopify/orders",
        "refunds/create": "https://api.briwell.co/commerce/webhooks/shopify/refunds",
    }


def test_webhook_topics_cover_orders_and_refunds() -> None:
    # These paths must match the routes registered in app/routers/shopify_webhooks.py.
    assert set(WEBHOOK_TOPICS) == {"orders/create", "orders/updated", "refunds/create"}
    assert WEBHOOK_TOPICS["refunds/create"].endswith("/refunds")
    assert WEBHOOK_TOPICS["orders/create"].endswith("/orders")
