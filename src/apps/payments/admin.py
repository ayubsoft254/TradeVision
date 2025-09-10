from django.contrib import admin
from .models import PaymentMethod, Wallet, Transaction, DepositRequest, WithdrawalRequest, Agent, P2PMerchant

admin.site.register(PaymentMethod)
admin.site.register(Wallet)
admin.site.register(Transaction)
admin.site.register(DepositRequest)
admin.site.register(WithdrawalRequest)
admin.site.register(Agent)
admin.site.register(P2PMerchant)
