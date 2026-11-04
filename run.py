import uvicorn
import os

if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("  🚀 CacheFlow AI - Automated 3-Way Invoice Reconciliation")
    print("  🔗 Dashboard UI:    http://127.0.0.1:8000")
    print("  📖 API Swagger Docs: http://127.0.0.1:8000/docs")
    print("=" * 65 + "\n")
    
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
