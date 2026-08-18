from decimal import Decimal

from app import db
from app.models.wallet import Wallet, WalletTransaction, WalletTransactionType


def get_or_create_wallet(teacher_id):
    wallet = Wallet.query.filter_by(teacher_id=teacher_id).first()
    if not wallet:
        wallet = Wallet(teacher_id=teacher_id)
        db.session.add(wallet)
        db.session.flush()
    return wallet


def credit_payment(teacher_id, net_amount, reference):
    wallet = get_or_create_wallet(teacher_id)
    net_amount = Decimal(str(net_amount))
    wallet.pending_balance = (wallet.pending_balance or 0) + net_amount
    wallet.total_earned = (wallet.total_earned or 0) + net_amount
    db.session.add(WalletTransaction(
        wallet_id=wallet.id,
        type=WalletTransactionType.CREDIT,
        amount=net_amount,
        reference=reference,
    ))
    return wallet


def debit_for_refund(teacher_id, amount, reference):
    """
    Reverses a previously credited payment (full refund of a verified transaction).
    Pulls from pending_balance first; if that's insufficient, the shortfall is
    taken from paid_balance so the wallet never silently under-deducts.
    total_earned is reduced to keep lifetime-earnings accurate.
    """
    wallet = get_or_create_wallet(teacher_id)
    amount = Decimal(str(amount))

    from_pending = min(wallet.pending_balance or Decimal("0"), amount)
    remainder = amount - from_pending
    wallet.pending_balance = (wallet.pending_balance or Decimal("0")) - from_pending
    if remainder > 0:
        wallet.paid_balance = (wallet.paid_balance or Decimal("0")) - remainder
    wallet.total_earned = (wallet.total_earned or Decimal("0")) - amount

    db.session.add(WalletTransaction(
        wallet_id=wallet.id,
        type=WalletTransactionType.ADJUSTMENT,
        amount=-amount,
        reference=reference,
    ))
    return wallet


def deduct_for_withdrawal(teacher_id, amount, reference):
    wallet = get_or_create_wallet(teacher_id)
    amount = Decimal(str(amount))
    if wallet.pending_balance < amount:
        raise ValueError("Insufficient pending balance for withdrawal.")
    wallet.pending_balance -= amount
    wallet.paid_balance = (wallet.paid_balance or 0) + amount
    db.session.add(WalletTransaction(
        wallet_id=wallet.id,
        type=WalletTransactionType.WITHDRAWAL,
        amount=amount,
        reference=reference,
    ))
    return wallet
