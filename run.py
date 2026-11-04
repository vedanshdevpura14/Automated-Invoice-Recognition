import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print("\n" + "=" * 65)
    print("  🚀 CacheFlow AI - Automated 3-Way Invoice Reconciliation")
    print(f"  🔗 Dashboard UI:    http://127.0.0.1:{port}")
    print(f"  📖 API Swagger Docs: http://127.0.0.1:{port}/docs")
    print("=" * 65 + "\n")
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )
