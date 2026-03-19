from dotenv import load_dotenv
load_dotenv()

from collector import collect_all

articles = collect_all()
print(f"\n총 {len(articles)}건 수집\n")
for a in articles[:5]:
    print(f"[{a.source}] {a.title}")
    print(f"  {a.url}")
    print()
