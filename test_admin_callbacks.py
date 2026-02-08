"""
HALOS Admin Panel Callback Tests
"""
import re

print("=" * 50)
print("ADMIN PANEL CALLBACK TESTS")
print("=" * 50)

# Read handlers.py
with open('app/handlers.py', 'r', encoding='utf-8') as f:
    content = f.read()

tests = [
    ('admin_pricing callback', 'admin_pricing'),
    ('admin_discount_off callback', 'admin_discount_off'),
    ('admin_discount_50 callback', 'admin_discount_50'),
    ('admin_discount_25 callback', 'admin_discount_25'),
    ('admin_discount_30 callback', 'admin_discount_30'),
    ('is_discount_active import', 'is_discount_active'),
    ('set_discount import', 'set_discount'),
    ('DISCOUNT_CONFIG import', 'DISCOUNT_CONFIG'),
    ('ORIGINAL_PRICES import', 'ORIGINAL_PRICES'),
]

print("\nChecking handlers.py:")
all_passed = True
for name, pattern in tests:
    if pattern in content:
        print(f"  ✅ {name}")
    else:
        print(f"  ❌ {name} NOT FOUND")
        all_passed = False

# Read subscription_handlers.py
with open('app/subscription_handlers.py', 'r', encoding='utf-8') as f:
    sub_content = f.read()

print("\nChecking subscription_handlers.py:")
sub_tests = [
    ('get_plan_price import', 'get_plan_price'),
    ('is_discount_active import', 'is_discount_active'),
    ('get_discount_label import', 'get_discount_label'),
    ('ORIGINAL_PRICES import', 'ORIGINAL_PRICES'),
    ('Dynamic Payme prices', 'weekly_price = get_plan_price'),
    ('Dynamic Click prices', 'monthly_price = get_plan_price'),
]

for name, pattern in sub_tests:
    if pattern in sub_content:
        print(f"  ✅ {name}")
    else:
        print(f"  ❌ {name} NOT FOUND")
        all_passed = False

# Read telegram_payments.py
with open('app/telegram_payments.py', 'r', encoding='utf-8') as f:
    tg_content = f.read()

print("\nChecking telegram_payments.py:")
tg_tests = [
    ('get_plan_price import', 'get_plan_price'),
    ('is_discount_active import', 'is_discount_active'),
    ('actual_price = get_plan_price', 'actual_price = get_plan_price'),
]

for name, pattern in tg_tests:
    if pattern in tg_content:
        print(f"  ✅ {name}")
    else:
        print(f"  ❌ {name} NOT FOUND")
        all_passed = False

print("\n" + "=" * 50)
if all_passed:
    print("✅ ALL CALLBACK TESTS PASSED!")
else:
    print("❌ SOME TESTS FAILED!")
print("=" * 50)
