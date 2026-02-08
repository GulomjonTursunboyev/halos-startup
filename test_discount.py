"""
HALOS PRO Discount System Tests
"""
import sys
import asyncio

print("=" * 50)
print("HALOS PRO DISCOUNT SYSTEM TESTS")
print("=" * 50)

# Test 1: Subscription module imports
print("\n[TEST 1] Subscription module imports...")
try:
    from app.subscription import (
        ORIGINAL_PRICES, 
        DISCOUNT_CONFIG, 
        get_plan_price, 
        is_discount_active, 
        set_discount, 
        get_discount_label,
        get_current_prices,
        PRICING_PLANS
    )
    print("  ✅ All imports successful")
except ImportError as e:
    print(f"  ❌ Import error: {e}")
    sys.exit(1)

# Test 2: Original prices
print("\n[TEST 2] Original prices...")
expected_prices = {
    "pro_weekly": 14990,
    "pro_monthly": 29990,
    "pro_yearly": 249990
}
for plan, price in expected_prices.items():
    if ORIGINAL_PRICES.get(plan) == price:
        print(f"  ✅ {plan}: {price:,} so'm")
    else:
        print(f"  ❌ {plan}: expected {price}, got {ORIGINAL_PRICES.get(plan)}")

# Test 3: Discount toggle
print("\n[TEST 3] Discount toggle...")
set_discount(enabled=True, percentage=50)
if is_discount_active():
    print("  ✅ Discount enabled successfully")
else:
    print("  ❌ Failed to enable discount")

set_discount(enabled=False)
if not is_discount_active():
    print("  ✅ Discount disabled successfully")
else:
    print("  ❌ Failed to disable discount")

# Test 4: Price calculations
print("\n[TEST 4] Price calculations with 50% discount...")
set_discount(enabled=True, percentage=50)
prices = get_current_prices()
for plan, orig_price in ORIGINAL_PRICES.items():
    expected = int(orig_price * 0.5)
    actual = prices.get(plan)
    calc_price = get_plan_price(plan)
    if actual == expected and calc_price == expected:
        print(f"  ✅ {plan}: {orig_price:,} → {actual:,} (50% off)")
    else:
        print(f"  ❌ {plan}: expected {expected}, got {actual}")

# Test 5: Different percentages
print("\n[TEST 5] Different discount percentages...")
for pct in [25, 30, 50, 75]:
    set_discount(enabled=True, percentage=pct)
    weekly = get_plan_price("pro_weekly")
    expected = int(14990 * (100 - pct) / 100)
    if weekly == expected:
        print(f"  ✅ {pct}% discount: 14,990 → {weekly:,}")
    else:
        print(f"  ❌ {pct}% discount: expected {expected}, got {weekly}")

# Test 6: Labels
print("\n[TEST 6] Discount labels...")
set_discount(enabled=True, percentage=50)
label_uz = get_discount_label("uz")
label_ru = get_discount_label("ru")
if "50%" in label_uz:
    print(f"  ✅ UZ label: {label_uz}")
else:
    print(f"  ❌ UZ label missing percentage: {label_uz}")
if "50%" in label_ru:
    print(f"  ✅ RU label: {label_ru}")
else:
    print(f"  ❌ RU label missing percentage: {label_ru}")

# Test 7: No discount mode
print("\n[TEST 7] No discount mode...")
set_discount(enabled=False)
for plan, orig_price in ORIGINAL_PRICES.items():
    actual = get_plan_price(plan)
    if actual == orig_price:
        print(f"  ✅ {plan}: {actual:,} (original)")
    else:
        print(f"  ❌ {plan}: expected {orig_price}, got {actual}")

# Test 8: Subscription handlers imports
print("\n[TEST 8] Subscription handlers imports...")
try:
    from app.subscription_handlers import (
        show_pricing,
        payment_method_payme_callback,
        payment_method_click_callback,
        payme_buy_callback
    )
    print("  ✅ Subscription handlers imports OK")
except ImportError as e:
    print(f"  ❌ Import error: {e}")

# Test 9: Telegram payments imports
print("\n[TEST 9] Telegram payments imports...")
try:
    from app.telegram_payments import send_payment_invoice
    from app.subscription import get_plan_price as tp_price
    print("  ✅ Telegram payments imports OK")
except ImportError as e:
    print(f"  ❌ Import error: {e}")

# Test 10: Handlers imports
print("\n[TEST 10] Handlers module imports...")
try:
    # Just check syntax by importing
    import app.handlers
    print("  ✅ Handlers module OK")
except SyntaxError as e:
    print(f"  ❌ Syntax error in handlers: {e}")
except Exception as e:
    print(f"  ⚠️ Runtime error (may be OK): {type(e).__name__}")

# Reset to 50% discount for production
set_discount(enabled=True, percentage=50)

print("\n" + "=" * 50)
print("ALL TESTS COMPLETED")
print(f"Final state: Discount {'ACTIVE' if is_discount_active() else 'DISABLED'}")
print(f"Current prices: {get_current_prices()}")
print("=" * 50)
