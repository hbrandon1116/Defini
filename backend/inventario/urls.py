from pathlib import Path

from django.http import FileResponse, HttpResponse
from django.urls import include, path, re_path
from django.views.static import serve

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR.parent / "frontend" / "dist"


def spa_index(request, path=""):
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(open(index_file, "rb"), content_type="text/html")
    return HttpResponse("No se encontró la interfaz compilada.", status=404)


urlpatterns = [
    path("api/", include("api.urls")),
    re_path(
        r"^assets/(?P<path>.+)$",
        serve,
        {"document_root": str(FRONTEND_DIR / "assets")},
    ),
    re_path(
        r"^images/(?P<path>.+)$",
        serve,
        {"document_root": str(FRONTEND_DIR / "images")},
    ),
    re_path(
        r"^(?P<path>favicon\.svg|opengraph\.jpg|favicon\.ico)$",
        serve,
        {"document_root": str(FRONTEND_DIR)},
    ),
    re_path(r"^.*$", spa_index),
]
