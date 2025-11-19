"""Pytest-based workflow validation for the gRPC microservice stack."""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import types

import pytest
import google.protobuf as google_protobuf
import grpc

ROOT = Path(__file__).resolve().parents[1]
SERVICE_DIRS = [
    "ecommerce-order-system/user_service",
    "ecommerce-order-system/product_service",
    "ecommerce-order-system/order_service",
    "ecommerce-order-system/payment_service",
    "ecommerce-order-system/shipping_service",
]
for service_path in SERVICE_DIRS:
    full_path = ROOT / service_path
    if full_path.exists():
        sys.path.append(str(full_path))


if not hasattr(google_protobuf, "runtime_version"):
    runtime_version_module = types.ModuleType("runtime_version")

    class _Domain:  # pylint: disable=too-few-public-methods
        PUBLIC = "public"

    def _noop(*args: object, **kwargs: object) -> None:  # noqa: D401
        """Compatibility shim for protobuf >= 6 runtime validation."""

    runtime_version_module.Domain = _Domain
    runtime_version_module.ValidateProtobufRuntimeVersion = _noop
    google_protobuf.runtime_version = runtime_version_module
    sys.modules["google.protobuf.runtime_version"] = runtime_version_module


grpc.__version__ = "99.0.0"
grpc_utilities = getattr(grpc, "_utilities", types.ModuleType("grpc._utilities"))
grpc_utilities.first_version_is_lower = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
grpc._utilities = grpc_utilities  # type: ignore[attr-defined]
sys.modules["grpc._utilities"] = grpc_utilities

import user_pb2  # type: ignore  # pylint: disable=wrong-import-position
import user_pb2_grpc  # type: ignore  # pylint: disable=wrong-import-position
import product_pb2  # type: ignore  # pylint: disable=wrong-import-position
import product_pb2_grpc  # type: ignore  # pylint: disable=wrong-import-position
import order_pb2  # type: ignore  # pylint: disable=wrong-import-position
import order_pb2_grpc  # type: ignore  # pylint: disable=wrong-import-position
import payment_pb2  # type: ignore  # pylint: disable=wrong-import-position
import payment_pb2_grpc  # type: ignore  # pylint: disable=wrong-import-position
import shipping_pb2  # type: ignore  # pylint: disable=wrong-import-position
import shipping_pb2_grpc  # type: ignore  # pylint: disable=wrong-import-position

from user_server import UserService  # type: ignore  # pylint: disable=wrong-import-position
from product_server import ProductService  # type: ignore  # pylint: disable=wrong-import-position
from order_server import OrderService  # type: ignore  # pylint: disable=wrong-import-position
from payment_server import PaymentService  # type: ignore  # pylint: disable=wrong-import-position
from shipping_server import ShippingService  # type: ignore  # pylint: disable=wrong-import-position


def test_e2e_microservice_workflow() -> None:
    """Exercise the in-process gRPC services to validate a full order lifecycle."""

    user_service = UserService()
    username = f"pytest_{uuid.uuid4().hex[:10]}"
    password = "Password!1"

    register_resp = user_service.RegisterUser(
        user_pb2.UserRegistrationRequest(
            username=username,
            email=f"{username}@example.com",
            password=password,
            first_name="Py",
            last_name="Tester",
            phone="555-0100",
            address="123 Harness Way",
        ),
        context=None,
    )
    assert register_resp.status == "success"
    assert register_resp.user_id

    login_resp = user_service.LoginUser(
        user_pb2.UserLoginRequest(username=username, password=password),
        context=None,
    )
    assert login_resp.status == "success"

    product_service = ProductService()
    catalog_resp = product_service.ListProducts(
        product_pb2.ProductListRequest(page=1, limit=5),
        context=None,
    )
    assert catalog_resp.products, "Product catalog should not be empty"
    selected_product = catalog_resp.products[0]

    order_service = OrderService()
    order_items = [
        order_pb2.OrderItem(
            product_id=selected_product.product_id,
            quantity=2,
            price=selected_product.price,
        )
    ]

    order_resp = order_service.CreateOrder(
        order_pb2.CreateOrderRequest(
            user_id=register_resp.user_id,
            items=order_items,
            shipping_address="123 Harness Way",
            payment_method="credit_card",
        ),
        context=None,
    )
    assert order_resp.order_id
    assert order_resp.total_amount == pytest.approx(selected_product.price * 2)

    fetched_order = order_service.GetOrder(
        order_pb2.OrderRequest(order_id=order_resp.order_id),
        context=None,
    )
    assert fetched_order.order_id == order_resp.order_id

    payment_service = PaymentService()
    payment_resp = payment_service.ProcessPayment(
        payment_pb2.PaymentRequest(
            order_id=order_resp.order_id,
            user_id=register_resp.user_id,
            amount=order_resp.total_amount,
            payment_method="credit_card",
            card_number="4111111111111111",
            expiry_date="12/26",
            cvv="123",
        ),
        context=None,
    )
    assert payment_resp.status == "completed"
    assert payment_resp.transaction_id

    shipping_service = ShippingService()
    shipping_resp = shipping_service.CreateShipping(
        shipping_pb2.ShippingRequest(
            order_id=order_resp.order_id,
            user_id=register_resp.user_id,
            shipping_address="123 Harness Way",
            shipping_method="standard",
        ),
        context=None,
    )
    assert shipping_resp.shipping_id
    assert shipping_resp.tracking_number

    updated_shipping = shipping_service.UpdateShippingStatus(
        shipping_pb2.UpdateShippingStatusRequest(
            shipping_id=shipping_resp.shipping_id,
            status="in_transit",
            tracking_number=shipping_resp.tracking_number,
        ),
        context=None,
    )
    assert updated_shipping.status == "in_transit"

    updated_order = order_service.UpdateOrderStatus(
        order_pb2.UpdateOrderStatusRequest(
            order_id=order_resp.order_id,
            status="shipped",
            admin_id="pytest",
        ),
        context=None,
    )
    assert updated_order.status == "shipped"

    user_orders = order_service.GetUserOrders(
        order_pb2.UserOrdersRequest(user_id=register_resp.user_id, page=1, limit=5),
        context=None,
    )
    assert user_orders.total == 1
    assert user_orders.orders[0].order_id == order_resp.order_id
