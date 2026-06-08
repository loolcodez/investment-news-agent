import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from fastapi import UploadFile, File

# Set up logging
log = logging.getLogger("uvicorn.error")

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

class AppServer:
    def __init__(self):
        self.app = FastAPI()
        self.files_dir = "static/files"
        self.images_dir = "static/images"
        self.templates = Jinja2Templates(directory="app/templates")

        # Define routes
        self.setup_files_route()
        self.setup_page_routes()

    def setup_files_route(self):
        @self.app.get("/files/{filename}")
        async def get_file(filename: str):
            iso_dir = os.path.join(os.path.dirname(__file__), self.files_dir)
            file_path = os.path.join(iso_dir, filename)
            if not os.path.isfile(file_path):
                log.warning(f"File not found: {file_path}")
                return {"error": "File not found"}
            log.info(f"Serving file: {file_path}")
            return FileResponse(file_path, media_type="application/octet-stream", filename=filename)

        @self.app.post("/files/upload")
        async def upload_file(file: UploadFile = File(...)):
            iso_dir = os.path.join(os.path.dirname(__file__), self.files_dir)
            os.makedirs(iso_dir, exist_ok=True)
            file_path = os.path.join(iso_dir, file.filename)
            log.info(f"Uploading file: {file_path}")
            with open(file_path, "wb") as f:
                while chunk := await file.read(1024 * 1024):
                    f.write(chunk)
            log.info(f"Upload complete: {file_path}")
            return {"filename": file.filename, "status": "uploaded"}

    def setup_page_routes(self):
        @self.app.get("/", response_class=HTMLResponse)
        async def get_index(request: Request):
            return self.templates.TemplateResponse(
                request=request,
                name="index.html",
                context={
                    "title": "Investment news agent"
                }
            )

        @self.app.get("/images/favicon.png")
        async def get_favicon():
            favicon_path = os.path.join(os.path.dirname(__file__), f"{self.images_dir}/favicon-32x32.png")
            if os.path.isfile(favicon_path):
                return FileResponse(favicon_path, media_type="image/png")
            return {"error": "Favicon not found"}

# Create an instance of the AppServer class to run the app
app_server = AppServer()
app = app_server.app  # Expose the FastAPI app for running
