"""
🚀 AI ORCHESTRATOR - 8-DARAJA DASTURLASH
=========================================
Bir nechta AI agentlarni parallel boshqaruvchi tizim.

Foydalanish:
    python ai_orchestrator.py "Telegram bot uchun yangi feature yoz"
    
Yoki Python'da:
    from ai_orchestrator import AIOrchestrator
    orchestrator = AIOrchestrator()
    results = await orchestrator.run_parallel_tasks([...])
"""

import asyncio
import os
import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import aiohttp
from dotenv import load_dotenv

load_dotenv()

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ==================== CONFIGURATION ====================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Try to get from app.config if not in env
if not GEMINI_API_KEY:
    try:
        from app.config import GEMINI_API_KEY as CONFIG_GEMINI_KEY
        GEMINI_API_KEY = CONFIG_GEMINI_KEY
    except ImportError:
        pass

class AgentRole(Enum):
    """AI Agent rollari"""
    ARCHITECT = "architect"      # Loyiha arxitekturasi
    BACKEND = "backend"          # Backend kod
    FRONTEND = "frontend"        # Frontend kod
    TESTER = "tester"            # Test yozish
    REFACTOR = "refactor"        # Kod optimallashtirish
    DOCS = "docs"                # Dokumentatsiya
    DEVOPS = "devops"            # CI/CD, deploy
    REVIEWER = "reviewer"        # Kod review


@dataclass
class AITask:
    """AI vazifasi"""
    id: str
    role: AgentRole
    prompt: str
    context: Optional[str] = None
    depends_on: Optional[List[str]] = None  # Boshqa tasklarga bog'liqlik
    priority: int = 1
    timeout: int = 60


@dataclass
class AIResult:
    """AI natijasi"""
    task_id: str
    role: AgentRole
    success: bool
    content: str
    execution_time: float
    error: Optional[str] = None


# ==================== ROLE PROMPTS ====================

ROLE_SYSTEM_PROMPTS = {
    AgentRole.ARCHITECT: """Sen yuqori malakali software architect agentsan.
Vazifang: Loyiha arxitekturasini loyihalash, texnologiyalarni tanlash, tizim dizaynini yaratish.
Javobingda: fayl strukturasi, modullar, API endpoint'lar, database schema ko'rsatilsin.
Faqat texnik javob ber, ortiqcha gap yo'q.""",

    AgentRole.BACKEND: """Sen backend developer agentsan. Python, FastAPI, Django, PostgreSQL, Redis bo'yicha ekspertsan.
Vazifang: Backend kod yozish, API yaratish, database operatsiyalari.
Javobingda: to'liq ishlaydigan kod, importlar, error handling bo'lsin.
Faqat kod ber, ortiqcha tushuntirish yo'q.""",

    AgentRole.FRONTEND: """Sen frontend developer agentsan. React, Vue, TypeScript, TailwindCSS bo'yicha ekspertsan.
Vazifang: Frontend komponentlar, UI/UX, responsive dizayn.
Javobingda: to'liq ishlaydigan kod, stillar, event handlerlar bo'lsin.
Faqat kod ber, ortiqcha tushuntirish yo'q.""",

    AgentRole.TESTER: """Sen QA engineer agentsan. pytest, unittest, jest bo'yicha ekspertsan.
Vazifang: Unit test, integration test, e2e test yozish.
Javobingda: to'liq test kodlari, edge case'lar, mock'lar bo'lsin.
Faqat test kodini ber.""",

    AgentRole.REFACTOR: """Sen code refactoring ekspertisan.
Vazifang: Kodni optimallashtirish, SOLID prinsiplari, clean code, performance.
Javobingda: optimallashtirilgan kod va qisqacha nima o'zgarganini ko'rsat.
Faqat yaxshilangan kodni ber.""",

    AgentRole.DOCS: """Sen technical writer agentsan.
Vazifang: README, API docs, docstrings, user guide yozish.
Javobingda: to'liq dokumentatsiya, misollar, usage bo'lsin.
Markdown formatda yoz.""",

    AgentRole.DEVOPS: """Sen DevOps engineer agentsan. Docker, CI/CD, Railway, GitHub Actions bo'yicha ekspertsan.
Vazifang: Dockerfile, docker-compose, CI/CD pipeline, deployment config.
Javobingda: to'liq config fayllar bo'lsin.
Faqat config/yaml/dockerfile ber.""",

    AgentRole.REVIEWER: """Sen senior code reviewer agentsan.
Vazifang: Kodni tekshirish, xatolarni topish, yaxshilash takliflari.
Javobingda: muammolar ro'yxati, severity, fix qilish yo'llari bo'lsin.
Qisqa va aniq yoz.""",
}


# ==================== AI ORCHESTRATOR ====================

class AIOrchestrator:
    """
    8-DARAJA AI ORCHESTRATOR
    
    Bir nechta AI agentlarni parallel boshqaradi:
    - Task scheduling
    - Dependency resolution
    - Parallel execution
    - Result aggregation
    """
    
    def __init__(self):
        self.tasks: List[AITask] = []
        self.results: Dict[str, AIResult] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def call_gemini(self, system_prompt: str, user_prompt: str, timeout: int = 60) -> str:
        """Gemini API chaqirish"""
        if not GEMINI_API_KEY:
            return "ERROR: GEMINI_API_KEY not set"
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 8192,
            }
        }
        
        try:
            async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    error_text = await resp.text()
                    return f"ERROR: {resp.status} - {error_text}"
        except asyncio.TimeoutError:
            return "ERROR: Request timeout"
        except Exception as e:
            return f"ERROR: {str(e)}"
    
    async def execute_task(self, task: AITask) -> AIResult:
        """Bitta taskni bajarish"""
        start_time = time.time()
        
        system_prompt = ROLE_SYSTEM_PROMPTS.get(task.role, "Sen professional developer agentsan.")
        
        # Context qo'shish (agar bog'liq tasklar bo'lsa)
        full_prompt = task.prompt
        if task.context:
            full_prompt = f"Kontekst:\n{task.context}\n\nVazifa:\n{task.prompt}"
        
        # Bog'liq tasklar natijalarini qo'shish
        if task.depends_on:
            deps_context = "\n\n--- Oldingi natijalar ---\n"
            for dep_id in task.depends_on:
                if dep_id in self.results:
                    deps_context += f"\n[{dep_id}]:\n{self.results[dep_id].content[:2000]}\n"
            full_prompt = deps_context + "\n\n" + full_prompt
        
        print(f"🤖 [{task.role.value.upper()}] Bajarilmoqda: {task.id}...")
        
        content = await self.call_gemini(system_prompt, full_prompt, task.timeout)
        
        execution_time = time.time() - start_time
        success = not content.startswith("ERROR:")
        
        result = AIResult(
            task_id=task.id,
            role=task.role,
            success=success,
            content=content,
            execution_time=execution_time,
            error=content if not success else None
        )
        
        self.results[task.id] = result
        
        status = "✅" if success else "❌"
        print(f"{status} [{task.role.value.upper()}] {task.id} - {execution_time:.2f}s")
        
        return result
    
    async def run_parallel_tasks(self, tasks: List[AITask]) -> Dict[str, AIResult]:
        """Tasklarni parallel bajarish (dependency'larni hisobga olgan holda)"""
        self.tasks = tasks
        self.results = {}
        
        # Tasklarni priority va dependency bo'yicha tartiblash
        pending = list(tasks)
        
        print(f"\n{'='*60}")
        print(f"🚀 AI ORCHESTRATOR - {len(tasks)} ta task")
        print(f"{'='*60}\n")
        
        while pending:
            # Bajarilishi mumkin bo'lgan tasklarni topish
            ready = []
            for task in pending:
                if task.depends_on:
                    # Barcha dependency'lar tugaganmi?
                    deps_done = all(dep_id in self.results for dep_id in task.depends_on)
                    if deps_done:
                        ready.append(task)
                else:
                    ready.append(task)
            
            if not ready:
                print("⚠️ Deadlock aniqlandi - ba'zi tasklar bajarib bo'lmaydi")
                break
            
            # Priority bo'yicha tartiblash
            ready.sort(key=lambda t: t.priority, reverse=True)
            
            # Parallel bajarish
            batch = ready[:5]  # Bir vaqtda max 5 ta
            
            print(f"\n📦 Batch: {[t.id for t in batch]}")
            
            await asyncio.gather(*[self.execute_task(t) for t in batch])
            
            # Bajarilganlarni olib tashlash
            for task in batch:
                pending.remove(task)
        
        print(f"\n{'='*60}")
        print(f"✅ YAKUNLANDI - {len(self.results)}/{len(tasks)} task bajarildi")
        print(f"{'='*60}\n")
        
        return self.results
    
    def generate_report(self) -> str:
        """Natijalar hisobotini yaratish"""
        report = []
        report.append("# 🚀 AI Orchestrator Hisoboti")
        report.append(f"\n**Vaqt:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"**Jami tasklar:** {len(self.results)}")
        
        success_count = sum(1 for r in self.results.values() if r.success)
        report.append(f"**Muvaffaqiyatli:** {success_count}/{len(self.results)}")
        
        total_time = sum(r.execution_time for r in self.results.values())
        report.append(f"**Umumiy vaqt:** {total_time:.2f}s")
        
        report.append("\n---\n")
        
        for task_id, result in self.results.items():
            status = "✅" if result.success else "❌"
            report.append(f"## {status} {result.role.value.upper()}: {task_id}")
            report.append(f"*Vaqt: {result.execution_time:.2f}s*\n")
            report.append("```")
            report.append(result.content[:3000])
            if len(result.content) > 3000:
                report.append("... (qisqartirildi)")
            report.append("```\n")
        
        return "\n".join(report)


# ==================== PRESET WORKFLOWS ====================

def create_feature_workflow(feature_description: str) -> List[AITask]:
    """Yangi feature uchun to'liq workflow"""
    return [
        AITask(
            id="architecture",
            role=AgentRole.ARCHITECT,
            prompt=f"Quyidagi feature uchun arxitektura va dizayn yarat:\n\n{feature_description}",
            priority=3
        ),
        AITask(
            id="backend_code",
            role=AgentRole.BACKEND,
            prompt=f"Quyidagi feature uchun backend kod yoz:\n\n{feature_description}",
            depends_on=["architecture"],
            priority=2
        ),
        AITask(
            id="tests",
            role=AgentRole.TESTER,
            prompt=f"Quyidagi feature uchun testlar yoz:\n\n{feature_description}",
            depends_on=["backend_code"],
            priority=1
        ),
        AITask(
            id="docs",
            role=AgentRole.DOCS,
            prompt=f"Quyidagi feature uchun dokumentatsiya yoz:\n\n{feature_description}",
            depends_on=["backend_code"],
            priority=1
        ),
        AITask(
            id="review",
            role=AgentRole.REVIEWER,
            prompt=f"Quyidagi feature kodini review qil, xatolarni top:\n\n{feature_description}",
            depends_on=["backend_code", "tests"],
            priority=1
        ),
    ]


def create_refactor_workflow(code: str, goals: str) -> List[AITask]:
    """Kod refactoring workflow"""
    return [
        AITask(
            id="analyze",
            role=AgentRole.REVIEWER,
            prompt=f"Quyidagi kodni tahlil qil va muammolarni top:\n\n```python\n{code}\n```\n\nMaqsadlar: {goals}",
            priority=3
        ),
        AITask(
            id="refactor",
            role=AgentRole.REFACTOR,
            prompt=f"Quyidagi kodni optimallashtir:\n\n```python\n{code}\n```\n\nMaqsadlar: {goals}",
            depends_on=["analyze"],
            priority=2
        ),
        AITask(
            id="tests",
            role=AgentRole.TESTER,
            prompt=f"Refactor qilingan kod uchun testlar yoz. Original funksionallik saqlanganini tekshir.",
            depends_on=["refactor"],
            priority=1
        ),
    ]


def create_bug_fix_workflow(bug_description: str, code: str) -> List[AITask]:
    """Bug fixing workflow"""
    return [
        AITask(
            id="diagnose",
            role=AgentRole.REVIEWER,
            prompt=f"Bug: {bug_description}\n\nKod:\n```python\n{code}\n```\n\nBugning sababini top.",
            priority=3
        ),
        AITask(
            id="fix",
            role=AgentRole.BACKEND,
            prompt=f"Bug: {bug_description}\n\nKod:\n```python\n{code}\n```\n\nBugni to'g'irla va to'liq kodni ber.",
            depends_on=["diagnose"],
            priority=2
        ),
        AITask(
            id="test",
            role=AgentRole.TESTER,
            prompt=f"Bug fix uchun regression test yoz: {bug_description}",
            depends_on=["fix"],
            priority=1
        ),
    ]


# ==================== CLI ====================

async def main():
    import sys
    
    if len(sys.argv) < 2:
        print("""
🚀 AI ORCHESTRATOR - 8-DARAJA DASTURLASH
========================================

Foydalanish:
    python ai_orchestrator.py "Vazifa tavsifi"
    
Misollar:
    python ai_orchestrator.py "Telegram bot uchun reminder tizimi yoz"
    python ai_orchestrator.py "FastAPI bilan REST API yarat"
    python ai_orchestrator.py "Payment integration qil"
    
Muhit o'zgaruvchilari:
    GEMINI_API_KEY - Gemini API kaliti (majburiy)
        """)
        return
    
    task_description = " ".join(sys.argv[1:])
    
    print(f"\n📝 Vazifa: {task_description}\n")
    
    # Feature workflow yaratish
    tasks = create_feature_workflow(task_description)
    
    async with AIOrchestrator() as orchestrator:
        results = await orchestrator.run_parallel_tasks(tasks)
        
        # Hisobotni saqlash
        report = orchestrator.generate_report()
        
        report_file = f"ai_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)
        
        print(f"\n📄 Hisobot saqlandi: {report_file}")
        
        # Natijalarni ko'rsatish
        print("\n" + "="*60)
        print("📊 NATIJALAR")
        print("="*60)
        
        for task_id, result in results.items():
            status = "✅" if result.success else "❌"
            print(f"\n{status} {result.role.value.upper()}: {task_id}")
            print("-" * 40)
            print(result.content[:500])
            if len(result.content) > 500:
                print("... (to'liq versiya hisobotda)")


if __name__ == "__main__":
    asyncio.run(main())
