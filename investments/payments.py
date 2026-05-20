from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings


class PaymentGatewayError(Exception):
    pass


class PaymentGatewayUnavailable(PaymentGatewayError):
    pass


@dataclass(frozen=True)
class PaymentProvider:
    code: str
    label: str


class PaymentProviderRegistry:
    ORANGE_MONEY = "ORANGE_MONEY"
    MOOV_MONEY = "MOOV_MONEY"
    TELECEL_MONEY = "TELECEL_MONEY"

    ACTIVE_PROVIDERS = (
        PaymentProvider(ORANGE_MONEY, "Orange Money"),
        PaymentProvider(MOOV_MONEY, "Moov Money"),
        PaymentProvider(TELECEL_MONEY, "Telecel Money"),
    )

    @classmethod
    def choices(cls):
        return tuple((provider.code, provider.label) for provider in cls.ACTIVE_PROVIDERS)

    @classmethod
    def labels(cls):
        return {provider.code: provider.label for provider in cls.ACTIVE_PROVIDERS}

    @classmethod
    def is_supported(cls, provider_code):
        return provider_code in cls.labels()

    @classmethod
    def get_label(cls, provider_code):
        return cls.labels().get(provider_code)


@dataclass(frozen=True)
class PaymentIntent:
    provider_code: str
    provider_label: str
    amount: Decimal
    phone: str
    reference: str
    status: str = "PENDING"
    external_reference: str = ""


class BasePaymentGateway:
    provider_code = None

    def initiate_payment(self, *, amount, phone, reference, user):
        raise NotImplementedError

    def verify_payment(self, *, reference):
        raise NotImplementedError

    def parse_webhook(self, payload):
        raise NotImplementedError


class ManualReviewGateway(BasePaymentGateway):
    def __init__(self, provider_code):
        self.provider_code = provider_code

    def initiate_payment(self, *, amount, phone, reference, user):
        provider_label = PaymentProviderRegistry.get_label(self.provider_code)
        if provider_label is None:
            raise PaymentGatewayUnavailable("Provider not supported")

        return PaymentIntent(
            provider_code=self.provider_code,
            provider_label=provider_label,
            amount=Decimal(amount),
            phone=phone,
            reference=reference,
        )

    def verify_payment(self, *, reference):
        return {"reference": reference, "status": "PENDING"}

    def parse_webhook(self, payload):
        return payload


class OrangeMoneyGateway(ManualReviewGateway):
    provider_code = PaymentProviderRegistry.ORANGE_MONEY

    def __init__(self):
        super().__init__(self.provider_code)


class MoovMoneyGateway(ManualReviewGateway):
    provider_code = PaymentProviderRegistry.MOOV_MONEY

    def __init__(self):
        super().__init__(self.provider_code)


class TelecelMoneyGateway(ManualReviewGateway):
    provider_code = PaymentProviderRegistry.TELECEL_MONEY

    def __init__(self):
        super().__init__(self.provider_code)


class PaymentGatewayRegistry:
    GATEWAYS = {
        PaymentProviderRegistry.ORANGE_MONEY: OrangeMoneyGateway,
        PaymentProviderRegistry.MOOV_MONEY: MoovMoneyGateway,
        PaymentProviderRegistry.TELECEL_MONEY: TelecelMoneyGateway,
    }

    @classmethod
    def get_gateway(cls, provider_code):
        if provider_code not in PaymentProviderRegistry.labels():
            raise PaymentGatewayUnavailable("Provider not supported")

        gateway_class = cls.GATEWAYS.get(provider_code)
        if gateway_class is None:
            if not getattr(settings, 'PAYMENT_ALLOW_MANUAL_REVIEW', True):
                raise PaymentGatewayUnavailable("Provider gateway unavailable")
            return ManualReviewGateway(provider_code)
        return gateway_class()
