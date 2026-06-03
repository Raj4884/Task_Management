# Log generators package – one generator per simulated microservice.
from app.generators.auth_service import AuthServiceGenerator
from app.generators.payment_service import PaymentServiceGenerator
from app.generators.order_service import OrderServiceGenerator
from app.generators.user_service import UserServiceGenerator
from app.generators.notification_service import NotificationServiceGenerator

ALL_GENERATORS: dict[str, type] = {
    "auth-service": AuthServiceGenerator,
    "payment-service": PaymentServiceGenerator,
    "order-service": OrderServiceGenerator,
    "user-service": UserServiceGenerator,
    "notification-service": NotificationServiceGenerator,
}

__all__ = [
    "AuthServiceGenerator",
    "PaymentServiceGenerator",
    "OrderServiceGenerator",
    "UserServiceGenerator",
    "NotificationServiceGenerator",
    "ALL_GENERATORS",
]
