"""
STT API Comparison Test
Aisha vs Kotib.ai
"""
import asyncio
import aiohttp
import os
import time

# API Configurations
AISHA_API_KEY = "A1IBAbx4.vbFpnWJRQRvDANwOEugCW1ARJkZUjlSY"
AISHA_STT_URL = "https://back.aisha.group/api/v1/stt/post/"

KOTIB_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjb21wYW55IjoiZWJkYWYyZjctZDc0My00NDUwLTg2MzItOTdhODM0YjE4MTdjIn0.NdyeqX2L61FU6PpBQBo4uYKRSZWS8bXlygJYVlgkrn0"
KOTIB_STT_URL = "https://developer.kotib.ai/api/v1/stt"


async def test_aisha_stt(audio_path: str) -> dict:
    """Test Aisha STT API"""
    result = {
        "provider": "Aisha",
        "success": False,
        "text": None,
        "time_ms": 0,
        "error": None
    }
    
    try:
        with open(audio_path, 'rb') as f:
            file_content = f.read()
        
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            headers = {'x-api-key': AISHA_API_KEY}
            
            data = aiohttp.FormData()
            data.add_field('audio', file_content, filename='audio.ogg', content_type='audio/ogg')
            data.add_field('language', 'uz')
            
            async with session.post(AISHA_STT_URL, data=data, headers=headers, timeout=30) as response:
                result["time_ms"] = int((time.time() - start_time) * 1000)
                response_text = await response.text()
                
                print(f"[Aisha] Status: {response.status}")
                print(f"[Aisha] Response: {response_text[:500]}")
                
                if response.status == 200:
                    import json
                    try:
                        data = json.loads(response_text)
                        result["text"] = data.get('text') or data.get('transcript') or data.get('result')
                        result["success"] = bool(result["text"])
                    except:
                        result["text"] = response_text
                        result["success"] = bool(response_text)
                else:
                    result["error"] = f"Status {response.status}: {response_text[:200]}"
                    
    except Exception as e:
        result["error"] = str(e)
    
    return result


async def test_kotib_stt(audio_path: str) -> dict:
    """Test Kotib.ai STT API"""
    result = {
        "provider": "Kotib.ai",
        "success": False,
        "text": None,
        "time_ms": 0,
        "error": None
    }
    
    try:
        with open(audio_path, 'rb') as f:
            file_content = f.read()
        
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            headers = {'Authorization': f'Bearer {KOTIB_API_KEY}'}
            
            data = aiohttp.FormData()
            data.add_field('audio', file_content, filename='audio.ogg', content_type='audio/ogg')
            data.add_field('language', 'uz')
            data.add_field('blocking', 'true')
            
            async with session.post(KOTIB_STT_URL, data=data, headers=headers, timeout=30) as response:
                result["time_ms"] = int((time.time() - start_time) * 1000)
                response_text = await response.text()
                
                print(f"[Kotib] Status: {response.status}")
                print(f"[Kotib] Response: {response_text[:500]}")
                
                if response.status == 200:
                    import json
                    try:
                        data = json.loads(response_text)
                        if data.get("status") == "success":
                            result["text"] = data.get('text')
                            result["success"] = bool(result["text"])
                        else:
                            result["error"] = data.get("message", "Unknown error")
                    except:
                        result["text"] = response_text
                        result["success"] = bool(response_text)
                else:
                    result["error"] = f"Status {response.status}: {response_text[:200]}"
                    
    except Exception as e:
        result["error"] = str(e)
    
    return result


async def compare_stt_apis(audio_path: str):
    """Compare both STT APIs"""
    print("=" * 60)
    print("STT API COMPARISON TEST")
    print("=" * 60)
    print(f"Audio file: {audio_path}")
    print(f"File size: {os.path.getsize(audio_path)} bytes")
    print("=" * 60)
    
    # Test both APIs
    aisha_result = await test_aisha_stt(audio_path)
    print("-" * 60)
    kotib_result = await test_kotib_stt(audio_path)
    
    # Print results
    print("\n" + "=" * 60)
    print("RESULTS COMPARISON")
    print("=" * 60)
    
    print(f"\n📊 AISHA:")
    print(f"   ✅ Success: {aisha_result['success']}")
    print(f"   ⏱️ Time: {aisha_result['time_ms']} ms")
    print(f"   📝 Text: {aisha_result['text']}")
    if aisha_result['error']:
        print(f"   ❌ Error: {aisha_result['error']}")
    
    print(f"\n📊 KOTIB.AI:")
    print(f"   ✅ Success: {kotib_result['success']}")
    print(f"   ⏱️ Time: {kotib_result['time_ms']} ms")
    print(f"   📝 Text: {kotib_result['text']}")
    if kotib_result['error']:
        print(f"   ❌ Error: {kotib_result['error']}")
    
    # Recommendation
    print("\n" + "=" * 60)
    print("RECOMMENDATION")
    print("=" * 60)
    
    if aisha_result['success'] and kotib_result['success']:
        if aisha_result['time_ms'] < kotib_result['time_ms']:
            print(f"⚡ Aisha is faster ({aisha_result['time_ms']}ms vs {kotib_result['time_ms']}ms)")
        else:
            print(f"⚡ Kotib.ai is faster ({kotib_result['time_ms']}ms vs {aisha_result['time_ms']}ms)")
        print("Both APIs work! Compare text quality manually.")
    elif kotib_result['success']:
        print("🏆 KOTIB.AI is recommended (Aisha failed)")
    elif aisha_result['success']:
        print("🏆 AISHA is recommended (Kotib.ai failed)")
    else:
        print("❌ Both APIs failed!")
    
    return {
        "aisha": aisha_result,
        "kotib": kotib_result
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python test_stt.py <audio_file_path>")
        print("Example: python test_stt.py test_audio.ogg")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    
    if not os.path.exists(audio_path):
        print(f"Error: File not found: {audio_path}")
        sys.exit(1)
    
    asyncio.run(compare_stt_apis(audio_path))
