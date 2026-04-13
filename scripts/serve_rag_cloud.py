from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse


def build_manifest(rag_dir: Path, knowledge_base_id: str, version: str) -> dict:
    files = []
    for path in sorted(rag_dir.glob("*.json")):
        if path.name == "manifest.json":
            continue
        files.append({"name": path.name, "url": f"/files/{path.name}"})

    return {
        "knowledge_base_id": knowledge_base_id,
        "version": version,
        "files": files,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve local RAG embedding JSON files with a generated manifest.")
    parser.add_argument("--rag-dir", type=Path, default=Path("./rag"), help="Directory containing embedding JSON files")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=8001, help="Port to bind")
    parser.add_argument("--knowledge-base-id", default="default", help="Knowledge base id exposed in manifest")
    parser.add_argument("--version", default="dev", help="Version exposed in manifest")
    return parser.parse_args()


def create_app(rag_dir: Path, knowledge_base_id: str, version: str) -> FastAPI:
    app = FastAPI(title="RAG Cloud File Server")

    @app.get("/manifest.json")
    async def get_manifest():
        if not rag_dir.exists():
            raise HTTPException(status_code=404, detail="RAG directory not found.")
        return JSONResponse(build_manifest(rag_dir, knowledge_base_id, version))

    @app.get("/files/{filename}")
    async def get_file(filename: str):
        if not rag_dir.exists():
            raise HTTPException(status_code=404, detail="RAG directory not found.")
        target = rag_dir / Path(filename).name
        if not target.is_file():
            raise HTTPException(status_code=404, detail="File not found.")
        return FileResponse(target, media_type="application/json", filename=target.name)

    return app


def main() -> None:
    args = parse_args()
    app = create_app(args.rag_dir.resolve(), args.knowledge_base_id, args.version)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
