import base64
import json
import os
from pathlib import Path
from typing import Optional, List, Any
from urllib.parse import urlparse
from urllib.request import Request as UrlRequest, urlopen
from urllib.error import HTTPError, URLError
from dotenv import load_dotenv
from fastapi import UploadFile, File, Form
import requests

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from agents.cortex_service import CortexAPIService
from fastapi.responses import FileResponse
from markdown_pdf import MarkdownPdf, Section

load_dotenv()

# print("PAT:", os.getenv("GITHUB_FINE_GRAINED_PAT"))

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

GITHUB_API_BASE = "https://api.github.com"


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")  


class RepoRequest(BaseModel):
    repo_url: str = Field(..., description="GitHub repository URL")
    branch: Optional[str] = Field(default=None, description="Branch or tree SHA")
    github_token: Optional[str] = Field(
        default=None,
        description="Fine-grained GitHub PAT. If omitted, backend reads GITHUB_FINE_GRAINED_PAT."
    )


class FileRequest(RepoRequest):
    path: str = Field(..., description="Repository file path")


class RepoFilesRequest(RepoRequest):
    max_files: int = Field(
        20,
        ge=1,
        le=200,
        description="Safety limit to avoid fetching massive repositories in one request"
    )


def parse_github_repo_url(repo_url: str) -> tuple[str, str]:
    parsed = urlparse(repo_url)
    if parsed.netloc not in {"github.com", "www.github.com"}:
        raise HTTPException(status_code=400, detail="Invalid GitHub URL")

    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="Repository URL must include owner and repo")

    owner = parts[0]
    repo = parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]

    if not owner or not repo:
        raise HTTPException(status_code=400, detail="Could not parse owner/repo from URL")

    return owner, repo


def get_token(request_token: Optional[str]) -> str:
    token = request_token or os.getenv("GITHUB_FINE_GRAINED_PAT")
    if not token:
        raise HTTPException(
            status_code=400,
            detail="Missing GitHub PAT. Provide github_token in request or set GITHUB_FINE_GRAINED_PAT on backend."
        )
    return token


def github_get(path: str, token: str) -> dict:
    url = f"{GITHUB_API_BASE}{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "testing-doc-generator-backend"
    }
    req = UrlRequest(url, headers=headers, method="GET")

    try:
        with urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as err:
        payload = err.read().decode("utf-8", errors="replace")
        raise HTTPException(
            status_code=err.code,
            detail=f"GitHub API error: {payload}"
        ) from err
    except URLError as err:
        raise HTTPException(status_code=502, detail=f"GitHub request failed: {err.reason}") from err


@app.post("/api/github/repository/tree")
def fetch_repository_tree(payload: RepoRequest):
    """
    Step 1: GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1
    """
    owner, repo = parse_github_repo_url(payload.repo_url)
    token = get_token(payload.github_token)

    repo_info = github_get(f"/repos/{owner}/{repo}",token)

    branch = payload.branch or repo_info["default_branch"]

    tree_data = github_get(
        f"/repos/{owner}/{repo}/git/trees/{branch}?recursive=1",
        token
    )

    files = [item for item in tree_data.get("tree", []) if item.get("type") == "blob"]
    return {
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "total_files": len(files),
        "tree": files
    }


@app.post("/api/github/repository/file")
def fetch_file_contents(payload: FileRequest):
    """
    Step 2: GET /repos/{owner}/{repo}/contents/{path}
    """
    owner, repo = parse_github_repo_url(payload.repo_url)
    token = get_token(payload.github_token)

    repo_info = github_get(f"/repos/{owner}/{repo}", token)

    branch = payload.branch or repo_info["default_branch"]

    content_data = github_get(
        f"/repos/{owner}/{repo}/contents/{payload.path}?ref={branch}",
        token
    )

    encoded_content = content_data.get("content")
    decoded_content = None
    if encoded_content and content_data.get("encoding") == "base64":
        decoded_content = base64.b64decode(encoded_content).decode("utf-8", errors="replace")

    return {
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "path": payload.path,
        "sha": content_data.get("sha"),
        "size": content_data.get("size"),
        "encoding": content_data.get("encoding"),
        "download_url": content_data.get("download_url"),
        "content": decoded_content,
    }


@app.post("/api/github/repository/files")
def fetch_repository_files(payload: RepoFilesRequest):
    """
    Combined flow:
    1) Fetch repository tree recursively.
    2) Fetch contents for each file path up to max_files.
    """
    owner, repo = parse_github_repo_url(payload.repo_url)
    token = get_token(payload.github_token)

    repo_info = github_get(f"/repos/{owner}/{repo}", token)

    branch = payload.branch or repo_info["default_branch"]

    tree_data = github_get(
        f"/repos/{owner}/{repo}/git/trees/{branch}?recursive=1",
        token
    )
    files = [item for item in tree_data.get("tree", []) if item.get("type") == "blob"]

    selected = files[: payload.max_files]
    results = []
    errors = []

    for item in selected:
        path = item.get("path")
        if not path:
            continue
        try:
            content_data = github_get(
                f"/repos/{owner}/{repo}/contents/{path}?ref={branch}",
                token
            )
            encoded_content = content_data.get("content")
            decoded_content = None
            if encoded_content and content_data.get("encoding") == "base64":
                decoded_content = base64.b64decode(encoded_content).decode("utf-8", errors="replace")

            results.append(
                {
                    "path": path,
                    "sha": content_data.get("sha"),
                    "size": content_data.get("size"),
                    "encoding": content_data.get("encoding"),
                    "download_url": content_data.get("download_url"),
                    "content": decoded_content,
                }
            )
        except HTTPException as err:
            errors.append({"path": path, "error": err.detail})

    return {
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "total_tree_files": len(files),
        "fetched_files": len(results),
        "max_files": payload.max_files,
        "files": results,
        "errors": errors,
    }



cortex = CortexAPIService(
    base_url=os.getenv("CORTEX_BASE_URL"),
    tenant_id=os.getenv("CORTEX_TENANT_ID"),
    client_id=os.getenv("CORTEX_CLIENT_ID"),
    client_secret=os.getenv("CORTEX_CLIENT_SECRET"),
    scope=os.getenv("CORTEX_SCOPE"),
    timeout=300,
)

@app.post("/api/generate-documentation")
async def generate_documentation(
    requirementDocument: UploadFile = File(...),
    architectureImage: UploadFile = File(...),
    githubFiles: str = Form(...),
    codeSnippet: str = Form(...)
):

    # raise HTTPException(
    #     status_code=500,
    #     detail="Testing failure"
    # )

    github_files = json.loads(githubFiles)

    source_code = ""

    for file in github_files:
        if file.get("content"):
            source_code += (
                f"\nFile: {file['path']}\n"
                f"{file['content']}\n"
            )

    prompt = f"""
    Source Code:
    {source_code}

    Code Snippet:
    {codeSnippet}

    Generate complete testing documentation.
    """

    # files = {
    #     "uploaded_file": (
    #         requirementDocument.filename,
    #         await requirementDocument.read(),
    #         requirementDocument.content_type,
    #     )
    # }
    files = [
    (
        "uploaded_file",
        (
            requirementDocument.filename,
            await requirementDocument.read(),
            requirementDocument.content_type,
        ),
    ),
    (
        "uploaded_file",
        (
            architectureImage.filename,
            await architectureImage.read(),
            architectureImage.content_type,
        ),
    ),
]

    try:
        result = cortex.call(
            endpoint="ask/generate-test-plan-agent",
            data={
                "q": prompt
            },
            files=files
        )

        pdf = MarkdownPdf()

        pdf.add_section(
            Section(result["message"])
        )

        pdf.save("TestingDocumentation.pdf")

        return FileResponse(
            "TestingDocumentation.pdf",
            media_type="application/pdf",
            filename="TestingDocumentation.pdf"
        )

        # return { "success": True, "message": result.get("message", "")}
    
    except requests.exceptions.HTTPError as e:
        print("Cortex Error:", e.response.status_code)
        print("Cortex Response:", e.response.text)

        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.text
        )
