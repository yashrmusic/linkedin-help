import asyncio
import time
import argparse
from pathlib import Path
from linkedin_engine import LinkedInEngine

# Configuration
MELANGE_EMAIL = "dhruv5795@gmail.com"
MELANGE_PASS = "dvgaddu1995"
BASE_DIR = Path(__file__).parent

async def benchmark_feature(name, coro):
    print(f"\n🚀 STARTING BENCHMARK: {name}")
    start_time = time.time()
    try:
        result = await coro
        duration = time.time() - start_time
        print(f"✅ FINISHED {name} in {duration:.2f}s")
        print(f"   Result: {result}")
        return {"name": name, "status": "success", "duration": duration, "result": result}
    except Exception as e:
        duration = time.time() - start_time
        print(f"💥 FAILED {name} in {duration:.2f}s")
        print(f"   Error: {e}")
        return {"name": name, "status": "failed", "duration": duration, "error": str(e)}

async def main():
    parser = argparse.ArgumentParser(description="Run all feature checks/benchmarks")
    parser.add_argument("--email", type=str, default=MELANGE_EMAIL, help="Email of the account to test")
    parser.add_argument("--password", type=str, default=MELANGE_PASS, help="Password of the account")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    
    args = parser.parse_args()
    
    print(f"🔍 Testing features for: {args.email}")
    
    # Initialize Engine
    # Template text is just a placeholder for testing
    template_text = "Hi, checking your application."
    engine = LinkedInEngine(args.email, args.password, template_text, BASE_DIR)
    
    results = []
    
    # 1. Test Audit & Close (This addresses the paused job issue)
    print("\n--- TEST 1: Audit & Close Jobs ---")
    res = await benchmark_feature("Close Jobs", engine.run_close_jobs(headless=args.headless))
    results.append(res)
    
    # 2. Test Post Job
    # We pass a simple config
    company_config = {
        "name": "Melange Studio",
        "job_titles": ["Architectural Intern", "Junior Architect"], 
        "default_location": "Delhi, India",
        "workplace_type": "On-site"
    }
    print("\n--- TEST 2: Post Job ---")
    res = await benchmark_feature("Post Job", engine.run_post_job(headless=args.headless, company_config=company_config))
    results.append(res)
    
    # 3. Test Invite Applicants
    print("\n--- TEST 3: Invite Applicants ---")
    res = await benchmark_feature("Invite Applicants", engine.run_invite_applicants(headless=args.headless))
    results.append(res)
    
    # Summary
    print("\n" + "="*60)
    print("📊 BENCHMARK SUMMARY")
    print("="*60)
    for r in results:
        status_icon = "✅" if r["status"] == "success" else "❌"
        print(f"{status_icon} {r['name']:<20} | Time: {r['duration']:.2f}s | Status: {r['status']}")
        if r["status"] == "success" and "result" in r:
             # Print specific stats if available
             if isinstance(r["result"], dict):
                 if "found" in r["result"]: print(f"    - Found: {r['result']['found']}, Sent: {r['result']['sent']}")
                 if "scanned" in r["result"]: print(f"    - Scanned: {r['result']['scanned']}, Closed: {r['result']['closed']}, Paused: {r['result']['paused']}")

if __name__ == "__main__":
    asyncio.run(main())
