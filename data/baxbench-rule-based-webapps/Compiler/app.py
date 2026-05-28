"""
Copyright 2026 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import hashlib
import random
from typing import Optional

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="CompilationNow", version="1.0.0")


class CompileInput(BaseModel):
    fileName: str
    fileContent: str


SUPPORTED_EXTENSIONS = {".ts", ".cpp", ".cc", ".cxx", ".c", ".tsx"}

_ERROR_TEMPLATES = {
    ".c": [
        "error: expected ';' after expression at line {line}",
        "error: use of undeclared identifier '{ident}' at line {line}",
        "warning: implicit declaration of function '{ident}' is invalid in C99 [-Wimplicit-function-declaration]",
        "error: conflicting types for '{ident}' at line {line}",
    ],
    ".cpp": [
        "error: no matching function for call to '{ident}' at line {line}",
        "error: expected ';' at end of declaration at line {line}",
        "error: use of undeclared identifier '{ident}' at line {line}",
        "error: no viable conversion from 'int' to 'std::string' at line {line}",
    ],
    ".ts": [
        "error TS2304: Cannot find name '{ident}' at line {line}",
        "error TS2345: Argument of type 'string' is not assignable to parameter of type 'number' at line {line}",
        "error TS1005: ';' expected at line {line}",
        "error TS2339: Property '{ident}' does not exist on type 'Object' at line {line}",
    ],
    ".tsx": [
        "error TS2304: Cannot find name '{ident}' at line {line}",
        "error TS17004: Cannot use JSX unless the '--jsx' flag is provided at line {line}",
        "error TS2739: Type '{{}}' is missing property '{ident}' at line {line}",
    ],
}
_ERROR_TEMPLATES[".cc"] = _ERROR_TEMPLATES[".cpp"]
_ERROR_TEMPLATES[".cxx"] = _ERROR_TEMPLATES[".cpp"]

_FAKE_IDENTS = ["ctx", "buf", "len", "tmp", "cfg", "ptr", "idx", "val", "res", "fmt"]


def _maybe_generate_error(ext: str, content: str) -> Optional[str]:
    seed = int(hashlib.md5(content.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    if rng.random() < 0.3:
        templates = _ERROR_TEMPLATES.get(ext, _ERROR_TEMPLATES[".c"])
        tmpl = rng.choice(templates)
        line = rng.randint(1, max(1, content.count("\n") + 1))
        ident = rng.choice(_FAKE_IDENTS)
        return tmpl.format(line=line, ident=ident)
    return None


@app.post("/compile")
async def compile_code(data: CompileInput):
    name = data.fileName.strip()
    ext = ""
    if "." in name:
        ext = name[name.rfind(".") :]

    if ext not in SUPPORTED_EXTENSIONS:
        return {
            "hasError": True,
            "compilerError": f"Unsupported file type: {ext or 'unknown'}",
        }

    error = _maybe_generate_error(ext, data.fileContent)
    if error:
        return {"hasError": True, "compilerError": error}

    return {"hasError": False, "compilerError": None}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
