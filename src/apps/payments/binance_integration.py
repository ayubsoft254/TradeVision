import hmac
import hashlib
import time
import json
import requests
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from .models import Transaction, Wallet, PaymentMethod
from apps.core.models import SystemLog

class BinancePayAPI:
    """Binance Pay API integration for automated payment verification"""
    
    def __init__(self):
        self.api_key = settings.BINANCE_PAY_API_KEY
        self.secret_key = settings.BINANCE_PAY_SECRET_KEY
        self.base_url = settings.BINANCE_PAY_BASE_URL or "https://bpay.binanceapi.com"
        
    def _generate_signature(self, timestamp, nonce, body):
        """Generate signature for Binance Pay API requests"""
        payload = timestamp + "\n" + nonce + "\n" + body + "\n"
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha512
        ).hexdigest().upper()
        return signature
    
    def _make_request(self, endpoint, method="POST", data=None):
        """Make authenticated request to Binance Pay API"""
        timestamp = str(int(time.time() * 1000))
        nonce = str(int(time.time() * 1000000))
        body = json.dumps(data) if data else ""
        
        signature = self._generate_signature(timestamp, nonce, body)
        
        headers = {
            "Content-Type": "application/json",
            "BinancePay-Timestamp": timestamp,
            "BinancePay-Nonce": nonce,
            "BinancePay-Certificate-SN": self.api_key,
            "BinancePay-Signature": signature
        }
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "POST":
                response = requests.post(url, headers=headers, data=body, timeout=30)
            else:
                response = requests.get(url, headers=headers, timeout=30)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Binance Pay API request failed: {str(e)}")
    
    def create_order(self, order_data):
        """Create a new Binance Pay order"""
        endpoint = "/binancepay/openapi/v2/order"
        return self._make_request(endpoint, "POST", order_data)
    
    def query_order(self, merchant_trade_no=None, prepay_id=None):
        """Query order status by merchant trade number or prepay ID"""
        endpoint = "/binancepay/openapi/v2/order/query"
        
        data = {}
        if merchant_trade_no:
            data["merchantTradeNo"] = merchant_trade_no
        elif prepay_id:
            data["prepayId"] = prepay_id
        else:
            raise ValueError("Either merchant_trade_no or prepay_id must be provided")
        
        return self._make_request(endpoint, "POST", data)
    
    def close_order(self, merchant_trade_no):
        """Close an unpaid order"""
        endpoint = "/binancepay/openapi/v2/order/close"
        data = {"merchantTradeNo": merchant_trade_no}
        return self._make_request(endpoint, "POST", data)

class BinancePaymentProcessor:
    """Process Binance Pay payments and update user accounts"""
    
    def __init__(self):
        self.api = BinancePayAPI()
    
    def create_payment_order(self, user, amount, currency, transaction_id):
        """Create a Binance Pay order for deposit"""
        
        # Convert amount to string with proper decimal places
        if currency == 'USDT':
            amount_str = f"{amount:.6f}"
        else:
            amount_str = f"{amount:.2f}"
        
        order_data = {
            "env": {
                "terminalType": "WEB"
            },
            "merchantTradeNo": str(transaction_id),
            "orderAmount": amount_str,
            "currency": currency,
            "goods": {
                "goodsType": "02",  # Virtual goods
                "goodsCategory": "Z000",  # Others
                "referenceGoodsId": "wallet_deposit",
                "goodsName": "Wallet Deposit",
                "goodsDetail": f"Deposit {amount} {currency} to trading wallet"
            },
            "shipping": {
                "shippingName": {
                    "firstName": user.first_name or "User",
                    "lastName": user.last_name or f"ID_{user.id}"
                }
            },
            "buyer": {
                "buyerName": {
                    "firstName": user.first_name or "User",
                    "lastName": user.last_name or f"ID_{user.id}"
                },
                "buyerEmail": user.email
            },
            "returnUrl": f"{settings.SITE_URL}/payments/binance-return/",
            "cancelUrl": f"{settings.SITE_URL}/payments/binance-cancel/"
        }
        
        try:
            response = self.api.create_order(order_data)
            
            if response.get("status") == "SUCCESS":
                return {
                    "success": True,
                    "checkout_url": response["data"]["checkoutUrl"],
                    "prepay_id": response["data"]["prepayId"],
                    "terminal_type": response["data"]["terminalType"]
                }
            else:
                return {
                    "success": False,
                    "error": response.get("errorMessage", "Failed to create order")
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @transaction.atomic
    def verify_payment(self, transaction_id):
        """Verify payment status and update transaction"""
        try:
            # Get the Binance Pay payment method
            binance_pay_method = PaymentMethod.objects.filter(name='binance_pay').first()
            if not binance_pay_method:
                return {"success": False, "error": "Binance Pay payment method not configured"}
            
            # Get the transaction
            txn = Transaction.objects.select_for_update().get(
                id=transaction_id,
                transaction_type='deposit',
                payment_method=binance_pay_method
            )
            
            if txn.status == 'completed':
                return {"success": True, "message": "Payment already verified"}
            
            # Query Binance Pay API
            response = self.api.query_order(merchant_trade_no=str(transaction_id))
            
            if response.get("status") != "SUCCESS":
                return {
                    "success": False,
                    "error": response.get("errorMessage", "Failed to query order")
                }
            
            order_data = response.get("data", {})
            order_status = order_data.get("status")
            
            # Update transaction based on Binance Pay status
            if order_status == "PAY_SUCCESS":
                return self._complete_payment(txn, order_data)
            elif order_status == "PAY_CLOSED":
                return self._cancel_payment(txn, "Payment closed")
            elif order_status == "PAY_TIMEOUT":
                return self._cancel_payment(txn, "Payment timeout")
            elif order_status in ["INITIAL", "PENDING"]:
                return {"success": True, "message": "Payment still pending"}
            else:
                return {"success": False, "error": f"Unknown payment status: {order_status}"}
                
        except Transaction.DoesNotExist:
            return {"success": False, "error": "Transaction not found"}
        except Exception as e:
            SystemLog.objects.create(
                action_type='payment_error',
                level='ERROR',
                message=f'Binance Pay verification error: {str(e)}',
                metadata={'transaction_id': str(transaction_id)}
            )
            return {"success": False, "error": f"Verification failed: {str(e)}"}
    
    def _complete_payment(self, txn, order_data):
        """Complete a successful payment"""
        try:
            # Update transaction
            txn.status = 'completed'
            txn.external_id = order_data.get('prepayId')
            txn.completed_at = timezone.now()
            
            # Parse the actual paid amount from Binance
            paid_amount = Decimal(order_data.get('orderAmount', '0'))
            paid_currency = order_data.get('currency', txn.currency)
            
            # Verify amounts match
            if paid_amount != txn.amount or paid_currency != txn.currency:
                txn.status = 'failed'
                txn.failure_reason = f"Amount mismatch: expected {txn.amount} {txn.currency}, got {paid_amount} {paid_currency}"
                txn.save()
                
                return {
                    "success": False,
                    "error": "Payment amount mismatch"
                }
            
            txn.save()
            
            # Update user wallet
            wallet = txn.user.wallet
            wallet.balance += txn.net_amount
            wallet.save()
            
            # Log successful payment
            SystemLog.objects.create(
                user=txn.user,
                action_type='payment_completed',
                level='INFO',
                message=f'Binance Pay deposit completed: {txn.amount} {txn.currency}',
                metadata={
                    'transaction_id': str(txn.id),
                    'binance_prepay_id': order_data.get('prepayId'),
                    'amount': str(txn.amount),
                    'currency': txn.currency
                }
            )
            
            return {
                "success": True,
                "message": "Payment completed successfully",
                "amount": txn.amount,
                "currency": txn.currency
            }
            
        except Exception as e:
            txn.status = 'failed'
            txn.failure_reason = f"Processing error: {str(e)}"
            txn.save()
            raise e
    
    def _cancel_payment(self, txn, reason):
        """Cancel a failed payment"""
        txn.status = 'cancelled'
        txn.failure_reason = reason
        txn.save()
        
        SystemLog.objects.create(
            user=txn.user,
            action_type='payment_cancelled',
            level='INFO',
            message=f'Binance Pay payment cancelled: {reason}',
            metadata={'transaction_id': str(txn.id)}
        )
        
        return {
            "success": False,
            "error": f"Payment cancelled: {reason}"
        }

# Webhook handler for real-time notifications
class BinancePayWebhookHandler:
    """Handle Binance Pay webhook notifications"""
    
    def __init__(self):
        self.processor = BinancePaymentProcessor()
    
    def verify_webhook_signature(self, timestamp, nonce, body, signature):
        """Verify webhook signature"""
        try:
            api = BinancePayAPI()
            expected_signature = api._generate_signature(timestamp, nonce, body)
            return hmac.compare_digest(signature, expected_signature)
        except Exception:
            return False
    
    def handle_webhook(self, request_data, headers):
        """Process Binance Pay webhook notification"""
        try:
            # Verify signature
            timestamp = headers.get('BinancePay-Timestamp')
            nonce = headers.get('BinancePay-Nonce')
            signature = headers.get('BinancePay-Signature')
            body = json.dumps(request_data) if isinstance(request_data, dict) else request_data
            
            if not self.verify_webhook_signature(timestamp, nonce, body, signature):
                return {"success": False, "error": "Invalid signature"}
            
            # Parse webhook data
            data = request_data if isinstance(request_data, dict) else json.loads(request_data)
            
            biz_type = data.get("bizType")
            biz_id = data.get("bizId")
            biz_status = data.get("bizStatus")
            
            if biz_type == "PAY":
                # Extract merchant trade number (our transaction ID)
                merchant_trade_no = data.get("data", {}).get("merchantTradeNo")
                
                if merchant_trade_no:
                    # Verify the payment
                    result = self.processor.verify_payment(merchant_trade_no)
                    return result
            
            return {"success": True, "message": "Webhook processed"}
            
        except Exception as e:
            SystemLog.objects.create(
                action_type='webhook_error',
                level='ERROR',
                message=f'Binance Pay webhook error: {str(e)}',
                metadata={'webhook_data': str(request_data)[:1000]}
            )
            return {"success": False, "error": f"Webhook processing failed: {str(e)}"}

# Automated payment checker task
def check_pending_binance_payments():
    """
    Task to check pending Binance Pay payments
    This should be run periodically (e.g., every 5 minutes) via Celery or cron
    """
    from datetime import timedelta
    
    # Get the Binance Pay payment method
    binance_pay_method = PaymentMethod.objects.filter(name='binance_pay').first()
    if not binance_pay_method:
        return "Binance Pay payment method not configured"
    
    # Get pending Binance Pay transactions from last 24 hours
    cutoff_time = timezone.now() - timedelta(hours=24)
    pending_transactions = Transaction.objects.filter(
        payment_method=binance_pay_method,
        status='pending',
        created_at__gte=cutoff_time
    )
    
    processor = BinancePaymentProcessor()
    
    for txn in pending_transactions:
        try:
            result = processor.verify_payment(txn.id)
            
            # Log the check result
            SystemLog.objects.create(
                user=txn.user,
                action_type='payment_check',
                level='INFO',
                message=f'Automated Binance Pay check: {result.get("message", "Checked")}',
                metadata={
                    'transaction_id': str(txn.id),
                    'result': result
                }
            )
            
        except Exception as e:
            SystemLog.objects.create(
                action_type='payment_check_error',
                level='ERROR',
                message=f'Automated payment check failed for transaction {txn.id}: {str(e)}',
                metadata={'transaction_id': str(txn.id)}
            )
    
    return f"Checked {pending_transactions.count()} pending transactions"