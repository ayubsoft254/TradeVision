# import json
# from django.shortcuts import render, redirect, get_object_or_404
# from django.contrib.auth.decorators import login_required
# from django.contrib import messages
# from django.http import JsonResponse, HttpResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.views.decorators.http import require_http_methods
# from .tasks import verify_single_binance_payment
# from django.conf import settings
# from decimal import Decimal
# from .models import Transaction, Wallet
# from .binance_integration import BinancePaymentProcessor, BinancePayWebhookHandler
# from apps.core.models import SystemLog

# @login_required
# def initiate_binance_payment(request):
#     """Initiate Binance Pay deposit"""
#     if request.method == 'POST':
#         try:
#             amount = Decimal(request.POST.get('amount', '0'))
#             currency = request.POST.get('currency', 'USDT')
            
#             # Validate amount
#             if amount <= 0:
#                 messages.error(request, 'Invalid amount specified.')
#                 return redirect('payments:deposit')
            
#             # Get or create user wallet
#             wallet, created = Wallet.objects.get_or_create(
#                 user=request.user,
#                 defaults={'currency': currency}
#             )
            
#             # Create pending transaction
#             transaction = Transaction.objects.create(
#                 user=request.user,
#                 transaction_type='deposit',
#                 payment_method='binance_pay',
#                 amount=amount,
#                 currency=currency,
#                 net_amount=amount,  # No fees for deposits
#                 status='pending',
#                 description=f'Binance Pay deposit: {amount} {currency}'
#             )
            
#             # Initialize Binance Pay processor
#             processor = BinancePaymentProcessor()
            
#             # Create Binance Pay order
#             result = processor.create_payment_order(
#                 user=request.user,
#                 amount=amount,
#                 currency=currency,
#                 transaction_id=transaction.id
#             )
            
#             if result['success']:
#                 # Store Binance Pay details
#                 transaction.external_id = result.get('prepay_id')
#                 transaction.save()
                
#                 # Log the initiation
#                 SystemLog.objects.create(
#                     user=request.user,
#                     action_type='payment_initiated',
#                     level='INFO',
#                     message=f'Binance Pay payment initiated: {amount} {currency}',
#                     ip_address=request.META.get('REMOTE_ADDR'),
#                     metadata={
#                         'transaction_id': str(transaction.id),
#                         'amount': str(amount),
#                         'currency': currency,
#                         'prepay_id': result.get('prepay_id')
#                     }
#                 )
                
#                 # Redirect to Binance Pay checkout
#                 return redirect(result['checkout_url'])
#             else:
#                 # Update transaction as failed
#                 transaction.status = 'failed'
#                 transaction.failure_reason = result.get('error', 'Unknown error')
#                 transaction.save()
                
#                 messages.error(
#                     request,
#                     f'Failed to initiate payment: {result.get("error", "Unknown error")}'
#                 )
#                 return redirect('payments:deposit')
                
#         except Exception as e:
#             messages.error(request, f'Error processing payment: {str(e)}')
#             return redirect('payments:deposit')
    
#     return redirect('payments:deposit')

# @login_required
# def binance_payment_return(request):
#     """Handle return from Binance Pay checkout"""
#     # Get transaction details from URL parameters
#     merchant_trade_no = request.GET.get('merchantTradeNo')
    
#     if not merchant_trade_no:
#         messages.error(request, 'Invalid payment return.')
#         return redirect('payments:deposit')
    
#     try:
#         # Get the transaction
#         transaction = get_object_or_404(
#             Transaction,
#             id=merchant_trade_no,
#             user=request.user,
#             payment_method='binance_pay'
#         )
        
#         # Verify payment with Binance
#         processor = BinancePaymentProcessor()
#         result = processor.verify_payment(transaction.id)
        
#         if result['success']:
#             if transaction.status == 'completed':
#                 messages.success(
#                     request,
#                     f'Payment successful! {result.get("amount", transaction.amount)} '
#                     f'{result.get("currency", transaction.currency)} has been added to your wallet.'
#                 )
#             else:
#                 messages.info(request, 'Payment is being processed. Please wait a moment.')
#         else:
#             messages.warning(
#                 request,
#                 f'Payment verification failed: {result.get("error", "Unknown error")}'
#             )
        
#     except Exception as e:
#         messages.error(request, f'Error verifying payment: {str(e)}')
    
#     return redirect('payments:transaction_detail', transaction_id=merchant_trade_no)

# @login_required
# def binance_payment_cancel(request):
#     """Handle cancelled Binance Pay payment"""
#     merchant_trade_no = request.GET.get('merchantTradeNo')
    
#     if merchant_trade_no:
#         try:
#             transaction = get_object_or_404(
#                 Transaction,
#                 id=merchant_trade_no,
#                 user=request.user,
#                 payment_method='binance_pay'
#             )
            
#             if transaction.status == 'pending':
#                 transaction.status = 'cancelled'
#                 transaction.failure_reason = 'User cancelled payment'
#                 transaction.save()
                
#                 SystemLog.objects.create(
#                     user=request.user,
#                     action_type='payment_cancelled',
#                     level='INFO',
#                     message=f'Binance Pay payment cancelled by user',
#                     metadata={'transaction_id': str(transaction.id)}
#                 )
            
#             messages.info(request, 'Payment has been cancelled.')
            
#         except Exception as e:
#             messages.error(request, f'Error processing cancellation: {str(e)}')
    
#     return redirect('payments:deposit')

# @login_required
# @require_http_methods(["POST"])
# def check_binance_payment_status(request):
#     """AJAX endpoint to check Binance Pay payment status"""
#     try:
#         transaction_id = request.POST.get('transaction_id')
        
#         if not transaction_id:
#             return JsonResponse({
#                 'success': False,
#                 'error': 'Transaction ID required'
#             })
        
#         # Verify user owns this transaction
#         transaction = get_object_or_404(
#             Transaction,
#             id=transaction_id,
#             user=request.user,
#             payment_method='binance_pay'
#         )
        
#         # Check payment status with Binance
#         processor = BinancePaymentProcessor()
#         result = processor.verify_payment(transaction.id)
        
#         # Refresh transaction from database
#         transaction.refresh_from_db()
        
#         response_data = {
#             'success': True,
#             'status': transaction.status,
#             'transaction_id': str(transaction.id),
#             'amount': str(transaction.amount),
#             'currency': transaction.currency,
#             'created_at': transaction.created_at.isoformat(),
#         }
        
#         if transaction.status == 'completed':
#             response_data.update({
#                 'completed_at': transaction.completed_at.isoformat() if transaction.completed_at else None,
#                 'message': 'Payment completed successfully!'
#             })
#         elif transaction.status == 'failed':
#             response_data.update({
#                 'error': transaction.failure_reason,
#                 'message': 'Payment failed.'
#             })
#         elif transaction.status == 'cancelled':
#             response_data.update({
#                 'message': 'Payment was cancelled.'
#             })
#         else:
#             response_data.update({
#                 'message': 'Payment is still being processed.'
#             })
        
#         return JsonResponse(response_data)
        
#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'error': str(e)
#         })

# @csrf_exempt
# @require_http_methods(["POST"])
# def binance_webhook(request):
#     """Handle Binance Pay webhook notifications"""
#     try:
#         # Parse request data
#         content_type = request.content_type
        
#         if 'application/json' in content_type:
#             request_data = json.loads(request.body.decode('utf-8'))
#         else:
#             return HttpResponse('Invalid content type', status=400)
        
#         # Get headers
#         headers = {
#             'BinancePay-Timestamp': request.META.get('HTTP_BINANCEPAY_TIMESTAMP'),
#             'BinancePay-Nonce': request.META.get('HTTP_BINANCEPAY_NONCE'),
#             'BinancePay-Signature': request.META.get('HTTP_BINANCEPAY_SIGNATURE'),
#         }
        
#         # Process webhook
#         webhook_handler = BinancePayWebhookHandler()
#         result = webhook_handler.handle_webhook(request_data, headers)
        
#         if result['success']:
#             return HttpResponse('SUCCESS')
#         else:
#             SystemLog.objects.create(
#                 action_type='webhook_failed',
#                 level='WARNING',
#                 message=f'Binance Pay webhook failed: {result.get("error")}',
#                 metadata={'request_data': str(request_data)[:500]}
#             )
#             return HttpResponse('FAILED', status=400)
            
#     except Exception as e:
#         SystemLog.objects.create(
#             action_type='webhook_error',
#             level='ERROR',
#             message=f'Binance Pay webhook error: {str(e)}',
#             metadata={'request_body': str(request.body)[:500]}
#         )
#         return HttpResponse('ERROR', status=500)

# # Updated main deposit view to include Binance Pay option
# @login_required
# def deposit_view(request):
#     """Enhanced deposit view with Binance Pay option"""
#     if request.method == 'POST':
#         payment_method = request.POST.get('payment_method')
        
#         if payment_method == 'binance_pay':
#             return initiate_binance_payment(request)
#         # Handle other payment methods...
    
#     # Get or create user wallet
#     wallet, created = Wallet.objects.get_or_create(
#         user=request.user,
#         defaults={'currency': settings.SUPPORTED_CURRENCIES.get(
#             getattr(request.user, 'country_code', ''), 'USDT'
#         )}
#     )
    
#     # Get recent transactions
#     recent_transactions = Transaction.objects.filter(
#         user=request.user,
#         transaction_type='deposit'
#     ).order_by('-created_at')[:5]
    
#     # Supported currencies for Binance Pay
#     binance_currencies = ['USDT', 'BUSD', 'BTC', 'ETH', 'BNB']
    
#     context = {
#         'wallet': wallet,
#         'recent_transactions': recent_transactions,
#         'binance_currencies': binance_currencies,
#         'binance_pay_enabled': hasattr(settings, 'BINANCE_PAY_API_KEY'),
#     }
    
#     return render(request, 'payments/deposit.html', context)

# @login_required
# @require_http_methods(["POST"])
# def force_check_binance_payment(request):
#     """
#     Force check a specific Binance Pay transaction using Celery
#     """
#     try:
#         transaction_id = request.POST.get('transaction_id')
        
#         if not transaction_id:
#             return JsonResponse({
#                 'success': False,
#                 'error': 'Transaction ID required'
#             })
        
#         # Verify user owns this transaction
#         transaction = get_object_or_404(
#             Transaction,
#             id=transaction_id,
#             user=request.user,
#             payment_method='binance_pay'
#         )
        
#         # Queue the verification task
#         task = verify_single_binance_payment.delay(transaction_id)
        
#         return JsonResponse({
#             'success': True,
#             'message': 'Payment verification queued',
#             'task_id': task.id,
#             'transaction_id': transaction_id
#         })
        
#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'error': str(e)
#         })

# @login_required
# def check_task_status(request, task_id):
#     """
#     Check the status of a Celery task
#     """
#     from celery.result import AsyncResult
    
#     try:
#         task = AsyncResult(task_id)
        
#         response_data = {
#             'task_id': task_id,
#             'status': task.status,
#             'ready': task.ready()
#         }
        
#         if task.ready():
#             response_data['result'] = task.result
        
#         return JsonResponse(response_data)
        
#     except Exception as e:
#         return JsonResponse({
#             'error': str(e)
#         }, status=500)