"""Test Payme API login - SMS OTP bilan"""
import asyncio
import aiohttp
import json

async def test_payme():
    login = "973710506"
    
    print(f"Testing login: {login}")
    print("Payme yangi tizim - parolsiz, faqat SMS kod bilan")
    
    try:
        headers = {
            'Content-Type': 'text/plain',
            'Accept': '*/*',
            'Connection': 'keep-alive',
            'User-Agent': 'Payme API'
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            
            # 1. Avval telefon raqamga kod yuborish - users.send_code yoki users.log_in_by_phone
            print("\n1. SMS kod so'ralmoqda...")
            
            # Turli metodlarni sinab ko'ramiz
            methods = [
                ('users.send_code', {'phone': login}),
                ('users.send_code', {'phone': '998' + login}),
                ('users.send_code', {'login': login}),
                ('users.log_in_by_phone', {'phone': login}),
                ('users.log_in_by_phone', {'phone': '998' + login}),
                ('sessions.get_activation_code', {'phone': login}),
                ('users.log_in', {'login': login}),  # parolsiz
                ('users.log_in', {'login': login, 'password': ''}),
            ]
            
            for method, params in methods:
                payload = {
                    'method': method,
                    'params': params
                }
                
                print(f"\nTrying: {method} with {params}")
                
                async with session.post(
                    'https://payme.uz/api/',
                    data=json.dumps(payload)
                ) as resp:
                    result = await resp.json()
                    print(f"Response: {result}")
                    
                    if 'error' not in result:
                        print(f"\n✅ {method} ishladi!")
                        
                        # API session olish
                        api_session = None
                        for key, value in resp.headers.items():
                            if key.lower() == 'api-session':
                                api_session = value
                                break
                        
                        if api_session:
                            print(f"API Session: {api_session[:30]}...")
                            
                            # SMS kod so'rash
                            sms_code = input("\n📲 Telefoningizga kelgan SMS kodni kiriting: ").strip()
                            
                            # Kodni tasdiqlash
                            verify_methods = [
                                ('users.verify_code', {'code': sms_code}),
                                ('sessions.activate', {'code': sms_code, 'device': True}),
                                ('users.log_in_confirm', {'code': sms_code}),
                            ]
                            
                            for v_method, v_params in verify_methods:
                                v_payload = {
                                    'method': v_method,
                                    'params': v_params
                                }
                                
                                print(f"\nVerifying with: {v_method}")
                                
                                async with session.post(
                                    'https://payme.uz/api/',
                                    data=json.dumps(v_payload),
                                    headers={'API-SESSION': api_session}
                                ) as resp2:
                                    result2 = await resp2.json()
                                    print(f"Response: {result2}")
                                    
                                    if 'error' not in result2:
                                        print(f"\n✅ Tasdiqlandi!")
                                        return
                        return
                        
    except Exception as e:
        import traceback
        print(f"❌ Xatolik: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_payme())

if __name__ == "__main__":
    asyncio.run(test_payme())
