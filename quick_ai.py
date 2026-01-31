"""
⚡ QUICK AI - Tezkor parallel AI buyruqlari
==========================================

Foydalanish:
    python quick_ai.py code "Telegram bot uchun /help handler yoz"
    python quick_ai.py test "handlers.py uchun testlar yoz"
    python quick_ai.py fix "Bu kod ishlamayapti: ..."
    python quick_ai.py refactor "Bu faylni optimallashtir"
    python quick_ai.py all "To'liq feature ishlab chiq"
"""

import asyncio
import sys
import os
from datetime import datetime

# Local import
from ai_orchestrator import (
    AIOrchestrator, 
    AITask, 
    AgentRole,
    create_feature_workflow,
    create_refactor_workflow,
    create_bug_fix_workflow,
)


async def quick_code(prompt: str):
    """Tezkor kod yozish - 3 agent parallel"""
    tasks = [
        AITask(id="code1", role=AgentRole.BACKEND, prompt=prompt, priority=3),
        AITask(id="code2", role=AgentRole.BACKEND, prompt=f"Alternative variant: {prompt}", priority=2),
        AITask(id="review", role=AgentRole.REVIEWER, prompt=f"Review: {prompt}", depends_on=["code1"], priority=1),
    ]
    
    async with AIOrchestrator() as orc:
        results = await orc.run_parallel_tasks(tasks)
        
        print("\n" + "="*60)
        print("🎯 ENG YAXSHI NATIJA:")
        print("="*60)
        best = results.get("code1")
        if best and best.success:
            print(best.content)


async def quick_test(prompt: str):
    """Tezkor test yozish - 2 agent parallel"""
    tasks = [
        AITask(id="unit_tests", role=AgentRole.TESTER, prompt=f"Unit testlar yoz: {prompt}", priority=2),
        AITask(id="integration_tests", role=AgentRole.TESTER, prompt=f"Integration testlar yoz: {prompt}", priority=2),
    ]
    
    async with AIOrchestrator() as orc:
        results = await orc.run_parallel_tasks(tasks)
        
        for result in results.values():
            if result.success:
                print(f"\n{'='*40}")
                print(result.content)


async def quick_fix(prompt: str):
    """Tezkor bug fix - diagnose + fix + test"""
    # Agar fayl path berilgan bo'lsa, o'qish
    code = ""
    if os.path.exists(prompt.split()[-1] if prompt.split() else ""):
        filepath = prompt.split()[-1]
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()
        prompt = prompt.replace(filepath, "").strip()
    
    tasks = create_bug_fix_workflow(prompt, code)
    
    async with AIOrchestrator() as orc:
        results = await orc.run_parallel_tasks(tasks)
        print(orc.generate_report())


async def quick_refactor(filepath: str, goals: str = "Optimizatsiya, clean code"):
    """Tezkor refactoring"""
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()
    else:
        code = filepath  # Direct code input
    
    tasks = create_refactor_workflow(code, goals)
    
    async with AIOrchestrator() as orc:
        results = await orc.run_parallel_tasks(tasks)
        
        refactored = results.get("refactor")
        if refactored and refactored.success:
            print("\n" + "="*60)
            print("🔧 OPTIMALLASHTIRILGAN KOD:")
            print("="*60)
            print(refactored.content)


async def quick_all(prompt: str):
    """To'liq feature - 5 agent parallel"""
    tasks = create_feature_workflow(prompt)
    
    async with AIOrchestrator() as orc:
        results = await orc.run_parallel_tasks(tasks)
        
        # Hisobotni saqlash
        report = orc.generate_report()
        report_file = f"feature_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)
        
        print(f"\n📄 To'liq hisobot: {report_file}")
        print(report)


async def quick_multi(prompts: list):
    """Bir nechta buyruqni bir vaqtda bajarish"""
    tasks = []
    for i, prompt in enumerate(prompts):
        tasks.append(AITask(
            id=f"task_{i+1}",
            role=AgentRole.BACKEND,
            prompt=prompt,
            priority=len(prompts) - i
        ))
    
    async with AIOrchestrator() as orc:
        results = await orc.run_parallel_tasks(tasks)
        
        for task_id, result in results.items():
            print(f"\n{'='*60}")
            print(f"📦 {task_id}")
            print("="*60)
            if result.success:
                print(result.content)
            else:
                print(f"❌ Error: {result.error}")


def main():
    if len(sys.argv) < 2:
        print("""
⚡ QUICK AI - Tezkor parallel AI buyruqlari
==========================================

Buyruqlar:
    code    - Tezkor kod yozish (3 agent)
    test    - Test yozish (2 agent)
    fix     - Bug to'g'irlash (3 agent)
    refactor- Kod optimallashtirish (3 agent)
    all     - To'liq feature (5 agent)
    multi   - Bir nechta buyruq (N agent)

Misollar:
    python quick_ai.py code "FastAPI endpoint yoz"
    python quick_ai.py test "handlers.py"
    python quick_ai.py fix "KeyError xatosi" app/handlers.py
    python quick_ai.py refactor app/ai_assistant.py "Tezlikni oshir"
    python quick_ai.py all "Payment integration"
    python quick_ai.py multi "Endpoint yoz" "Test yoz" "Docs yoz"
        """)
        return
    
    command = sys.argv[1].lower()
    args = " ".join(sys.argv[2:])
    
    commands = {
        "code": lambda: quick_code(args),
        "test": lambda: quick_test(args),
        "fix": lambda: quick_fix(args),
        "refactor": lambda: quick_refactor(args.split()[0] if args.split() else "", " ".join(args.split()[1:]) if len(args.split()) > 1 else "Optimizatsiya"),
        "all": lambda: quick_all(args),
        "multi": lambda: quick_multi(sys.argv[2:]),
    }
    
    if command in commands:
        asyncio.run(commands[command]())
    else:
        print(f"❌ Noma'lum buyruq: {command}")
        print("Mavjud buyruqlar: code, test, fix, refactor, all, multi")


if __name__ == "__main__":
    main()
