from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os

router = APIRouter()

# Use absolute path to the APK file as found in the project directory
APK_PATH = "/home/zo/Desktop/projects/OneTwenty/app-release(1).apk"

@router.get("/download-apk", response_class=FileResponse)
async def download_apk():
    """
    Open API endpoint to download the OneTwenty Android application APK.
    """
    if not os.path.exists(APK_PATH):
        raise HTTPException(status_code=404, detail="APK file not found on the server.")
        
    return FileResponse(
        path=APK_PATH,
        filename="OneTwenty-App.apk",
        media_type="application/vnd.android.package-archive"
    )
