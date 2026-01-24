"""
PAYME API SETUP SCRIPT
Bu scriptni bir marta ishga tushiring, device_id va card_id oling,
keyin app/payme_api.py dagi PAYME_CONFIG ga yozing.
"""
import asyncio
import sys
from app.payme_api import PaymeApi, PAYME_CONFIG


async def setup_payme():
    print("=" * 50)
    print("PAYME API SOZLASH")
    print("=" * 50)
    
    # 1. Credentials - config dan olish yoki so'rash
    if PAYME_CONFIG.get("login") and PAYME_CONFIG.get("password"):
        login = PAYME_CONFIG["login"]
        password = PAYME_CONFIG["password"]
        print(f"\n📱 Login: {login}")
        print(f"🔑 Parol: {'*' * len(password)}")
    else:
        login = input("\n📱 Payme telefon raqami (901234567): ").strip()
        password = input("🔑 Payme paroli: ").strip()
    
    api = PaymeApi()
    api.set_credentials(login=login, password=password)
    
    # 2. Login qilish
    print("\n⏳ Payme'ga ulanmoqda...")
    try:
        await api.login()
        print("✅ Login muvaffaqiyatli!")
    except Exception as e:
        print(f"❌ Login xatosi: {e}")
        return
    
    # 3. SMS kod yuborish
    print("\n📤 SMS kod yuborilmoqda...")
    try:
        await api.send_activation_code()
        print("✅ SMS kod yuborildi!")
    except Exception as e:
        print(f"❌ SMS yuborish xatosi: {e}")
        return
    
    # 4. SMS kodni kiritish
    code = input("\n📲 Telefoningizga kelgan SMS kodni kiriting: ").strip()
    
    print("\n⏳ Kod tasdiqlanmoqda...")
    try:
        await api.activate(code)
        print("✅ Kod tasdiqlandi!")
    except Exception as e:
        print(f"❌ Tasdiqlash xatosi: {e}")
        return
    
    # 5. Device ro'yxatdan o'tkazish
    print("\n📱 Device ro'yxatdan o'tkazilmoqda...")
    try:
        await api.register_device()
        device_id = api.get_device()
        print(f"✅ Device ID: {device_id}")
    except Exception as e:
        print(f"❌ Device xatosi: {e}")
        return
    
    # 6. Kartalarni olish
    print("\n💳 Kartalar olinmoqda...")
    try:
        cards = await api.get_my_cards()
        print(f"\n📋 Topilgan kartalar: {len(cards)}")
        
        for i, card in enumerate(cards, 1):
            print(f"\n{i}. {card.number}")
            print(f"   👤 {card.owner}")
            print(f"   💰 {card.balance / 100:,.0f} so'm")
            print(f"   🆔 ID: {card.id}")
        
        # Karta tanlash
        if cards:
            choice = input("\nQaysi kartani ishlatmoqchisiz? (raqam kiriting): ").strip()
            try:
                card_idx = int(choice) - 1
                if 0 <= card_idx < len(cards):
                    card_id = cards[card_idx].id
                else:
                    card_id = cards[0].id
            except:
                card_id = cards[0].id
        else:
            card_id = ""
            
    except Exception as e:
        print(f"❌ Kartalar xatosi: {e}")
        card_id = ""
    
    # 7. Natijalar
    print("\n" + "=" * 50)
    print("✅ SOZLASH TUGADI!")
    print("=" * 50)
    print("\nQuyidagi ma'lumotlarni app/payme_api.py fayliga yozing:\n")
    print("PAYME_CONFIG = {")
    print('    "enabled": True,')
    print(f'    "login": "{login}",')
    print(f'    "password": "{password}",')
    print(f'    "device_id": "{device_id}",')
    print(f'    "card_id": "{card_id}",')
    print('    "check_interval_seconds": 30,')
    print("}")
    print("\n" + "=" * 50)
    
    await api.close()


if __name__ == "__main__":
    asyncio.run(setup_payme())
