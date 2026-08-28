# youtube_dl.py - Descargador de YouTube
# -------------------------------
# Dependencias: pip install yt-dlp rich

import os
import sys
import re
import shutil
import subprocess
from pathlib import Path

import yt_dlp
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.progress import (
    Progress, BarColumn, TextColumn, DownloadColumn,
    TransferSpeedColumn, TimeRemainingColumn, SpinnerColumn
)
from rich import box

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    os.system("chcp 65001 > nul 2>&1")

console = Console(legacy_windows=False)
VERSION = "2.1"

# ============================================================
#   SISTEMA DE COOKIES - Saltar restricciones de edad
# ============================================================

def verificar_pycookiecheat():
    """Verifica e instala pycookiecheat si es necesario (para descifrar cookies en Windows)."""
    try:
        import pycookiecheat
        return True
    except ImportError:
        console.print("[yellow]⚠ pycookiecheat no encontrado. Instalando...[/]")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pycookiecheat", "--quiet"])
            console.print("[green]✓[/] pycookiecheat instalado correctamente")
            return True
        except Exception as e:
            console.print(f"[red]❌ Error instalando pycookiecheat: {e}[/]")
            return False

def detectar_navegadores():
    """Detecta navegadores instalados que yt-dlp puede usar."""
    usuarios = Path.home()
    navegadores = {}

    # Chrome - busco el perfil Default o cualquier perfil
    chrome_user_data = usuarios / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
    if chrome_user_data.exists():
        # Buscar perfil por defecto o perfiles personalizados
        for perfil in ["Default", "Profile 1", "Profile 2"]:
            chrome_network = chrome_user_data / perfil / "Network" / "Cookies"
            chrome_legacy = chrome_user_data / perfil / "Cookies"
            if chrome_network.exists() or chrome_legacy.exists():
                navegadores["chrome"] = perfil
                break

    # Edge
    edge_user_data = usuarios / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data"
    if edge_user_data.exists():
        for perfil in ["Default", "Profile 1"]:
            edge_path = edge_user_data / perfil / "Network" / "Cookies"
            if edge_path.exists():
                navegadores["edge"] = perfil
                break

    # Firefox
    firefox_profiles = usuarios / "AppData" / "Roaming" / "Mozilla" / "Firefox" / "Profiles"
    if firefox_profiles.exists():
        for perfil_dir in firefox_profiles.iterdir():
            if perfil_dir.is_dir() and (perfil_dir.name.endswith(".default") or perfil_dir.name.endswith(".default-release")):
                cookies_firefox = perfil_dir / "cookies.sqlite"
                if cookies_firefox.exists():
                    navegadores["firefox"] = perfil_dir.name
                    break

    # Opera
    opera_path = usuarios / "AppData" / "Roaming" / "Opera Software" / "Opera Stable" / "Network" / "Cookies"
    if opera_path.exists():
        navegadores["opera"] = "Default"

    # Brave
    brave_user_data = usuarios / "AppData" / "Local" / "BraveSoftware" / "Brave-Browser" / "User Data"
    if brave_user_data.exists():
        brave_path = brave_user_data / "Default" / "Network" / "Cookies"
        if brave_path.exists():
            navegadores["brave"] = "Default"

    return navegadores

def seleccionar_navegador():
    """Permite al usuario seleccionar cookies para autenticarse."""
    console.print("\n[bold cyan]🔐 AUTENTICACIÓN CON COOKIES[/]")
    console.print("[dim]Esto permite saltar restricciones de edad usando tu cuenta[/]\n")

    console.print("  [bold cyan]1[/]  📁  Usar archivo cookies.txt [green](RECOMENDADO)[/]")
    console.print("  [bold cyan]2[/]  🌐  Exportar cookies desde el navegador ahora")
    console.print("  [bold cyan]3[/]  ⏭  Saltar (usar sin autenticar)")

    opcion = Prompt.ask("[bold yellow]Selecciona[/]", choices=["1", "2", "3"], default="1")

    if opcion == "1":
        return seleccionar_cookies_manuales()
    elif opcion == "2":
        console.print("\n[bold cyan]📋 Instrucciones para exportar cookies:[/]\n")
        console.print("  1. Instala la extensión 'Get cookies.txt LOCALLY' en tu navegador")
        console.print("     Chrome/Brave/Edge: https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc")
        console.print("     Firefox: https://addons.mozilla.org/es/firefox/addon/cookies-txt/")
        console.print("\n  2. Ve a YouTube.com y asegúrate de estar logueado")
        console.print("  3. Haz clic en el ícono de la extensión")
        console.print("  4. Selecciona 'Export' o 'Exportar'")
        console.print("  5. Guarda el archivo como 'cookies.txt' en esta carpeta\n")

        cookies_path = Path(__file__).parent / "cookies.txt"
        if cookies_path.exists():
            console.print(f"[green]✓[/] Archivo cookies.txt encontrado: {cookies_path}")
            if Confirm.ask("¿Usar este archivo?", default=True):
                return ("file", "cookies.txt", cookies_path)
        else:
            console.print("[yellow]Esperando que guardes el archivo cookies.txt en esta carpeta...[/]")
            input("Presiona Enter cuando hayas guardado el archivo...")
            if cookies_path.exists():
                console.print(f"[green]✓[/] Archivo encontrado")
                return ("file", "cookies.txt", cookies_path)
            else:
                console.print("[red]❌ No se encontró el archivo cookies.txt[/]")
                return None

    console.print("[yellow]Continuando sin autenticación[/]")
    return None

def seleccionar_cookies_manuales():
    """Permite al usuario seleccionar un archivo cookies.txt manualmente."""
    console.print("[bold]Opciones para obtener cookies:[/]\n")
    console.print("  [bold cyan]1[/]  🌐  Exportar desde tu navegador ahora")
    console.print("  [bold cyan]2[/]  📁  Tengo un archivo cookies.txt")
    console.print("  [bold cyan]3[/]  ⏭  Saltar (usar sin autenticar)")

    opcion = Prompt.ask("[bold yellow]Selecciona[/]", choices=["1", "2", "3"], default="3")

    if opcion == "1":
        console.print("\n[bold cyan]📋 Instrucciones para exportar cookies:[/]\n")
        console.print("  1. Instala la extensión 'Get cookies.txt LOCALLY' en tu navegador")
        console.print("     Chrome: https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc")
        console.print("     Firefox: https://addons.mozilla.org/es/firefox/addon/cookies-txt/")
        console.print("\n  2. Ve a YouTube.com y asegúrate de estar logueado")
        console.print("  3. Haz clic en el ícono de la extensión")
        console.print("  4. Selecciona 'Export' o 'Exportar'")
        console.print("  5. Guarda el archivo como 'cookies.txt' en esta carpeta\n")

        cookies_path = Path(__file__).parent / "cookies.txt"
        if cookies_path.exists():
            console.print(f"[green]✓[/] Archivo cookies.txt encontrado: {cookies_path}")
            if Confirm.ask("¿Usar este archivo?", default=True):
                return ("file", "cookies.txt", cookies_path)
        else:
            console.print("[yellow]Esperando que guardes el archivo cookies.txt en esta carpeta...[/]")
            input("Presiona Enter cuando hayas guardado el archivo...")
            if cookies_path.exists():
                console.print(f"[green]✓[/] Archivo encontrado")
                return ("file", "cookies.txt", cookies_path)
            else:
                console.print("[red]❌ No se encontró el archivo cookies.txt[/]")
                return None

    elif opcion == "2":
        console.print("\n[bold]Escribe la ruta completa del archivo cookies.txt:[/]")
        ruta = Prompt.ask("Ruta").strip().strip('"')
        cookies_path = Path(ruta)
        if cookies_path.exists():
            console.print(f"[green]✓[/] Archivo encontrado")
            return ("file", cookies_path.name, cookies_path)
        else:
            console.print(f"[red]❌ No se encontró el archivo: {ruta}[/]")
            return None

    console.print("[yellow]Continuando sin autenticación[/]")
    return None

def obtener_opciones_cookies(info):
    """Pregunta al usuario si quiere usar cookies para restricciones de edad."""
    # Verificar si el video tiene restricción de edad
    tiene_restriccion = False
    if info:
        age_limit = info.get("age_limit")
        if age_limit and age_limit > 0:
            tiene_restriccion = True

    console.print("\n[bold cyan]🔐 Opciones de autenticación[/]")

    if tiene_restriccion:
        console.print("[yellow]⚠ Este video tiene restricción de edad[/]")
        console.print("  Usa cookies de tu navegador para acceder\n")

    console.print("  [bold cyan]1[/]  🔑  Usar cookies de navegador (recomendado)")
    console.print("  [bold cyan]2[/]  ⏭  Continuar sin autenticar")

    opcion = Prompt.ask("[bold yellow]Selecciona[/]", choices=["1", "2"], default="1")

    if opcion == "1":
        return seleccionar_navegador()
    return None

# ============================================================
#   UTILIDADES
# ============================================================

def limpiar_pantalla():
    os.system("cls" if os.name == "nt" else "clear")

def separador():
    console.rule("[bold cyan]★[/]")

def pausa():
    Prompt.ask("\n[bold yellow]Presiona Enter para continuar...[/]")

# ============================================================
#   BANNER
# ============================================================

def mostrar_banner():
    limpiar_pantalla()
    banner = r"""
[bold cyan]
   ╔══════════════════════════════════════╗
   ║                                      ║
   ║     ██╗   ██╗████████╗               ║
   ║     ╚██╗ ██╔╝╚══██╔══╝               ║
   ║      ╚████╔╝    ██║                   ║
   ║       ╚██╔╝     ██║                   ║
   ║        ██║      ██║                   ║
   ║        ╚═╝      ╚═╝                   ║
   ║        [yellow]DESCARGADOR[/] v""" + VERSION + r"""              ║
   ║        [green]You Tube[/]                          ║
   ║                                      ║
   ╚══════════════════════════════════════╝
[/bold cyan]
"""
    console.print(Panel(banner, box=box.DOUBLE_EDGE, style="cyan", subtitle="hecho con ♥ por tu amigo"))

# ============================================================
#   VERIFICAR DEPENDENCIAS
# ============================================================

def verificar_dependencias():
    console.print("\n[bold]🔍 Verificando dependencias...[/]")

    # Verificar yt-dlp
    try:
        import yt_dlp
        console.print("  [green]✓[/] yt-dlp instalado")
    except ImportError:
        console.print("  [yellow]⚠ yt-dlp no encontrado. Instalando...[/]")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp", "--quiet"])
        console.print("  [green]✓[/] yt-dlp instalado correctamente")

    # Verificar yt-dlp-ejs (scripts resolvedores de desafíos YouTube)
    try:
        import yt_dlp_ejs
        console.print("  [green]✓[/] yt-dlp-ejs instalado")
    except ImportError:
        console.print("  [yellow]⚠ yt-dlp-ejs no encontrado. Instalando...[/]")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp-ejs", "--quiet"])
        console.print("  [green]✓[/] yt-dlp-ejs instalado correctamente")

    # Verificar Node.js (necesario para resolver desafíos de YouTube)
    node_ok = False
    node_path = None
    try:
        resultado = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        if resultado.returncode == 0:
            console.print(f"  [green]✓[/] Node.js {resultado.stdout.strip()} instalado")
            node_ok = True
            node_path = "node"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    if not node_ok:
        # Buscar Node.js en ubicaciones comunes
        for ruta in [
            r"C:\Program Files\nodejs\node.exe",
            r"C:\Program Files (x86)\nodejs\node.exe",
        ]:
            if os.path.exists(ruta):
                console.print(f"  [green]✓[/] Node.js encontrado en {ruta}")
                node_ok = True
                node_path = ruta
                # Agregar al PATH
                os.environ["PATH"] = os.path.dirname(ruta) + os.pathsep + os.environ.get("PATH", "")
                break

    if not node_ok:
        console.print("  [yellow]⚠ Node.js no encontrado. Es necesario para descargar de YouTube[/]")
        console.print("  [dim]YouTube requiere resolver desafíos de JavaScript[/]\n")

        console.print("  [bold]Opciones para instalar Node.js:[/]")
        console.print("  [bold cyan]1[/]  Instalar con winget (recomendado)")
        console.print("  [bold cyan]2[/]  Descargar desde nodejs.org")
        console.print("  [bold cyan]3[/]  Ya lo tengo instalado (reintentar)")

        opcion = Prompt.ask("  [bold yellow]Selecciona[/]", choices=["1", "2", "3"], default="1")

        if opcion == "1":
            console.print("\n  [dim]Instalando Node.js con winget...[/]")
            try:
                subprocess.run(["winget", "install", "OpenJS.NodeJS", "--accept-package-agreements", "--accept-source-agreements"], timeout=120)
                console.print("  [green]✓[/] Node.js instalado. Reinicia el programa.")
                console.print("  [yellow]⚠ Cierra y vuelve a abrir el programa para que tome Node.js[/]")
                pausa()
                sys.exit(0)
            except Exception as e:
                console.print(f"  [red]❌ Error: {e}[/]")
                console.print("  [dim]Instala manualmente desde: https://nodejs.org[/]")
        elif opcion == "2":
            console.print("  [dim]Abre https://nodejs.org y descarga la versión LTS[/]")
            console.print("  [dim]Después reinicia el programa[/]")
            pausa()
            sys.exit(0)

    # Verificar ffmpeg (PATH + carpeta del script + subcarpetas)
    ffmpeg_disponible = shutil.which("ffmpeg") is not None

    if not ffmpeg_disponible:
        script_dir = Path(__file__).parent
        local_ff = script_dir / "ffmpeg.exe"
        if local_ff.exists():
            os.environ["PATH"] = str(script_dir) + os.pathsep + os.environ.get("PATH", "")
            ffmpeg_disponible = True
        else:
            # Buscar dentro de carpetas ffmpeg-*_build/bin/
            for item in script_dir.iterdir():
                if item.is_dir() and item.name.startswith("ffmpeg-") and item.name.endswith("_build"):
                    candidate = item / "bin" / "ffmpeg.exe"
                    if candidate.exists():
                        shutil.copy2(candidate, local_ff)
                        os.environ["PATH"] = str(script_dir) + os.pathsep + os.environ.get("PATH", "")
                        ffmpeg_disponible = True
                        console.print(f"  [green]OK[/] ffmpeg.exe copiado de {item.name}/bin/")
                        break

    if ffmpeg_disponible:
        console.print("  [green]OK[/] ffmpeg detectado")
    else:
        console.print("  [yellow]FFmpeg no encontrado - audio y HD no disponibles[/]")

    return ffmpeg_disponible

# ============================================================
#   VALIDAR URL
# ============================================================

def validar_url_youtube(url):
    patrones = [
        r'(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+',
        r'(https?://)?(www\.)?youtube\.com/embed/[\w-]+',
        r'(https?://)?(www\.)?youtube\.com/shorts/[\w-]+',
        r'(https?://)?youtu\.be/[\w-]+',
        r'(https?://)?(www\.)?youtube\.com/playlist\?list=[\w-]+',
    ]
    # También aceptar directamente la URL sin validación estricta
    if any(re.match(p, url) for p in patrones):
        return True
    # Permitir URLs que parecen de youtube aunque no encajen estrictamente
    if "youtube.com" in url or "youtu.be" in url:
        return True
    return False

def obtener_url():
    while True:
        url = Prompt.ask("\n[bold yellow]🔗 Pega la URL del video[/]").strip()
        if not url:
            console.print("[red]La URL no puede estar vacía[/]")
            continue
        if not validar_url_youtube(url):
            console.print("[red]❌ No parece una URL de YouTube válida[/]")
            if not Confirm.ask("¿Intentar de todas formas?", default=False):
                continue
        return url

# ============================================================
#   EXTRAER INFORMACIÓN DEL VIDEO
# ============================================================

def extraer_info(url, cookies_info=None, verbose=False):
    console.print("\n[bold]📡 Obteniendo información del video...[/]")
    try:
        ydl_opts = {'quiet': not verbose, 'no_warnings': not verbose, 'js_runtimes': {'node': {}}}
        if cookies_info:
            agregar_cookies_opciones(ydl_opts, cookies_info)
            if verbose:
                console.print("[dim]Opciones de yt-dlp:[/]")
                console.print(f"  [dim]{ydl_opts}[/]")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if cookies_info:
            console.print("[green]✓[/] Información obtenida con autenticación")
        return info
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "Private video" in error_msg:
            console.print("[red]❌ El video es privado[/]")
        elif "Video unavailable" in error_msg:
            console.print("[red]❌ El video no está disponible[/]")
        elif "age" in error_msg.lower() or "restrict" in error_msg.lower() or "sign in" in error_msg.lower():
            console.print("[red]❌ Video con restricción de edad. Necesitas autenticarte con cookies.[/]")
        elif "DPAPI" in error_msg or "decrypt" in error_msg.lower():
            console.print("[red]❌ Error al descifrar cookies del navegador[/]")
            console.print("[yellow]Usa el método cookies.txt en su lugar:[/]")
            console.print("  1. Instala extensión 'Get cookies.txt LOCALLY' en tu navegador")
            console.print("  2. Ve a YouTube.com (logueado)")
            console.print("  3. Exporta las cookies y guarda como 'cookies.txt' en esta carpeta")
        elif "page needs to be reloaded" in error_msg.lower():
            console.print("[red]❌ YouTube pide recargar la página. Cookies desactualizadas.[/]")
            console.print("[yellow]Exporta nuevas cookies.txt desde tu navegador[/]")
        else:
            console.print(f"[red]❌ Error al obtener información: {e}[/]")
        return None
    except Exception as e:
        console.print(f"[red]❌ Error inesperado: {e}[/]")
        return None

def agregar_cookies_opciones(ydl_opts, cookies_info):
    """Agrega las cookies a las opciones de yt-dlp."""
    if cookies_info is None:
        return None

    tipo, nombre, perfil = cookies_info
    if tipo == "file":
        # Usar archivo cookies.txt
        ydl_opts["cookiefile"] = str(perfil)  # perfil contiene la ruta del archivo
        console.print(f"[green]✓[/] Usando cookies desde archivo")
    elif tipo == "browser":
        # Usar cookies directamente del navegador
        # yt-dlp acepta: cookiesfrombrowser = (browser_name, profile)
        # profile=None usa el perfil por defecto ("Default")
        if perfil:
            ydl_opts["cookiesfrombrowser"] = (nombre, perfil)
            console.print(f"[green]✓[/] Extrayendo cookies de {nombre} (perfil: {perfil})...")
        else:
            ydl_opts["cookiesfrombrowser"] = (nombre,)
            console.print(f"[green]✓[/] Extrayendo cookies de {nombre}...")
    return cookies_info

def mostrar_info_video(info):
    video_id = info.get("id", "?")
    titulo = info.get("title", "?")
    duracion = info.get("duration", 0)
    minutos, segundos = divmod(duracion, 60)
    horas, minutos = divmod(minutos, 60)
    if horas > 0:
        duracion_str = f"{horas}h {minutos}m {segundos}s"
    else:
        duracion_str = f"{minutos}m {segundos}s"
    autor = info.get("uploader", info.get("channel", "?"))
    vistas = info.get("view_count", 0)
    likes = info.get("like_count", 0)
    if vistas:
        vistas = f"{vistas:,}"
    if likes:
        likes = f"{likes:,}"
    año = info.get("upload_date", "????")[:4]

    table = Table(title="📋 Información del Video", box=box.ROUNDED, style="cyan")
    table.add_column("Propiedad", style="bold yellow")
    table.add_column("Valor", style="white")
    table.add_row("Título", titulo)
    table.add_row("Autor", autor)
    table.add_row("Duración", duracion_str)
    table.add_row("Año", año)
    table.add_row("Vistas", str(vistas))
    table.add_row("Likes", str(likes))
    table.add_row("ID", video_id)
    console.print(table)

# ============================================================
#   FORMATOS DISPONIBLES
# ============================================================

def obtener_calidades(info):
    """Devuelve un dict con las calidades disponibles agrupadas."""
    calidades = {}
    for f in info.get("formats", []):
        vcodec = f.get("vcodec", "none")
        acodec = f.get("acodec", "none")
        height = f.get("height", 0)
        ext = f.get("ext", "?")
        format_id = f.get("format_id", "?")
        filesize = f.get("filesize", f.get("filesize_approx", 0))
        fps = f.get("fps", 0)
        tbr = f.get("tbr", 0)

        if vcodec != "none" and height:
            label = f"{height}p"
            if fps and fps >= 60:
                label = f"{label}60"
            if label not in calidades or tbr > calidades[label]["tbr"]:
                calidades[label] = {
                    "id": format_id,
                    "ext": ext,
                    "height": height,
                    "fps": fps,
                    "tbr": tbr,
                    "size": filesize,
                    "vcodec": vcodec,
                    "acodec": acodec,
                }
    return calidades

def mostrar_calidades(calidades):
    if not calidades:
        console.print("[yellow]No se encontraron formatos de video[/]")
        return

    table = Table(title="📺 Calidades Disponibles", box=box.SIMPLE_HEAVY)
    table.add_column("#", style="bold cyan", width=4)
    table.add_column("Calidad", style="bold yellow")
    table.add_column("Formato", style="green")
    table.add_column("FPS", style="blue")
    table.add_column("Codec V", style="white")
    table.add_column("Codec A", style="white")
    table.add_column("Tamaño aprox.", style="magenta")

    orden = sorted(calidades.items(), key=lambda x: int(x[1]["height"]), reverse=True)
    for i, (label, data) in enumerate(orden, 1):
        size_str = ""
        if data["size"] and data["size"] > 0:
            mb = data["size"] / (1024 * 1024)
            if mb > 1000:
                size_str = f"{mb/1024:.1f} GB"
            else:
                size_str = f"{mb:.0f} MB"
        acodec = data.get("acodec", "none")
        audio_str = "✅" if acodec != "none" else "❌ (solo video)"
        table.add_row(
            str(i),
            label,
            data["ext"],
            str(data["fps"]) if data["fps"] else "-",
            data["vcodec"][:8],
            audio_str,
            size_str,
        )

    console.print(table)
    return orden

# ============================================================
#   SUBTÍTULOS DISPONIBLES
# ============================================================

def idioma_a_espanol(codigo):
    idiomas = {
        "en": "Inglés", "es": "Español", "fr": "Francés", "de": "Alemán",
        "it": "Italiano", "pt": "Portugués", "ru": "Ruso", "ja": "Japonés",
        "ko": "Coreano", "zh": "Chino", "ar": "Árabe", "hi": "Hindi",
        "nl": "Neerlandés", "pl": "Polaco", "tr": "Turco", "vi": "Vietnamita",
        "th": "Tailandés", "id": "Indonesio", "ms": "Malayo", "ro": "Rumano",
        "cs": "Checo", "sv": "Sueco", "hu": "Húngaro", "da": "Danés",
        "fi": "Finlandés", "el": "Griego", "he": "Hebreo", "no": "Noruego",
        "uk": "Ucraniano", "bg": "Búlgaro", "hr": "Croata", "sr": "Serbio",
        "sk": "Eslovaco", "sl": "Esloveno", "et": "Estonio", "lv": "Letón",
        "lt": "Lituano", "ca": "Catalán", "gl": "Gallego", "eu": "Euskera",
        "bn": "Bengalí", "tl": "Filipino", "ta": "Tamil", "te": "Telugu",
        "mr": "Maratí", "gu": "Guyaratí", "kn": "Canarés", "ml": "Malayalam",
    }
    return idiomas.get(codigo, codigo.upper())

def mostrar_subtitulos(info):
    subs = info.get("subtitles", {})
    auto_subs = info.get("automatic_captions", {})

    if not subs and not auto_subs:
        console.print("[yellow]⚠ No hay subtítulos disponibles para este video[/]")
        return [], [], []

    opciones = []

    # Subtítulos manuales (subidos por el usuario)
    subs_list = []
    if subs:
        manual_table = Table(title="📝 Subtítulos (subidos por el creador)", box=box.SIMPLE)
        manual_table.add_column("#", style="bold cyan", width=4)
        manual_table.add_column("Idioma", style="bold yellow")
        manual_table.add_column("Código", style="green")
        manual_table.add_column("Formatos", style="white")

        for i, (lang, data) in enumerate(sorted(subs.items()), 1):
            formatos = [f["ext"] for f in data]
            manual_table.add_row(str(i), idioma_a_espanol(lang), lang, ", ".join(formatos))
            opciones.append(("manual", lang))

        console.print(manual_table)

    # Subtítulos automáticos (IA)
    auto_list = []
    if auto_subs:
        auto_table = Table(title="🤖 Subtítulos generados por IA", box=box.SIMPLE)
        auto_table.add_column("#", style="bold cyan", width=4)
        auto_table.add_column("Idioma", style="bold yellow")
        auto_table.add_column("Código", style="green")

        # Agrupar por idioma
        langs_vistos = set()
        count = 0
        for lang in sorted(auto_subs.keys()):
            lang_base = lang.split("-")[0]
            if lang_base not in langs_vistos:
                langs_vistos.add(lang_base)
                count += 1
                auto_table.add_row(str(count), idioma_a_espanol(lang_base), lang_base)
                opciones.append(("auto", lang_base))

        console.print(auto_table)

    return opciones, subs, auto_subs

# ============================================================
#   MENÚS INTERACTIVOS
# ============================================================

def menu_modo_descarga():
    console.print("\n[bold]¿Qué quieres descargar?[/]")
    console.print("  [bold cyan]1[/]  📹  Video + Audio (completo)")
    console.print("  [bold cyan]2[/]  🎵  Solo Audio (música, MP3)")
    console.print("  [bold cyan]3[/]  📝  Solo Subtítulos")
    console.print("  [bold cyan]0[/]  ❌  Salir")

    opcion = Prompt.ask("[bold yellow]Selecciona una opción[/]", choices=["0", "1", "2", "3"], default="1")
    return int(opcion)

def menu_calidad(orden_calidades):
    if not orden_calidades:
        return None

    console.print("\n[bold]Selecciona la calidad:[/]")
    console.print("  [bold cyan]0[/]  🏆  La mejor calidad disponible")
    for i, (label, data) in enumerate(orden_calidades, 1):
        size_str = ""
        if data["size"] and data["size"] > 0:
            mb = data["size"] / (1024 * 1024)
            if mb > 1000:
                size_str = f" ({mb/1024:.1f} GB)"
            else:
                size_str = f" ({mb:.0f} MB)"
        audio_ok = "✅" if data.get("acodec", "none") != "none" else "⚠ + audio"
        console.print(f"  [bold cyan]{i}[/]  {label}  [green]{data['ext']}[/] {audio_ok}{size_str}")

    choices = [str(i) for i in range(len(orden_calidades) + 1)]
    opcion = Prompt.ask("[bold yellow]Selecciona[/]", choices=choices, default="0")
    return int(opcion)

def menu_formato(calidades):
    formatos_disponibles = set()
    for data in calidades.values():
        formatos_disponibles.add(data["ext"])
    formatos_orden = sorted(formatos_disponibles)

    if not formatos_orden:
        return "mp4"

    console.print("\n[bold]Selecciona el formato de contenedor:[/]")
    for i, ext in enumerate(formatos_orden, 1):
        console.print(f"  [bold cyan]{i}[/]  .{ext}")
    # Siempre agregar opciones útiles
    extras = []
    for ext_extra in ["mp4", "mkv", "webm"]:
        if ext_extra not in formatos_orden:
            extras.append(ext_extra)

    choices = [str(i) for i in range(1, len(formatos_orden) + 1 + len(extras))]
    for i, ext in enumerate(extras, len(formatos_orden) + 1):
        console.print(f"  [bold cyan]{i}[/]  .{ext}  [dim](puede requerir conversión)[/]")

    total = len(formatos_orden) + len(extras)
    opcion = IntPrompt.ask("[bold yellow]Selecciona[/]", default=1)
    if 1 <= opcion <= len(formatos_orden):
        return formatos_orden[opcion - 1]
    elif len(formatos_orden) < opcion <= total:
        return extras[opcion - len(formatos_orden) - 1]
    return "mp4"

def menu_audio_calidad():
    console.print("\n[bold]Calidad de audio:[/]")
    console.print("  [bold cyan]1[/]  🏆  Mejor calidad (opus ~160k)")
    console.print("  [bold cyan]2[/]  🎧  Alta calidad (m4a ~128k)")
    console.print("  [bold cyan]3[/]  📻  Buena calidad (mp3 ~128k)")
    console.print("  [bold cyan]4[/]  💾  Pequeño tamaño (mp3 ~64k)")

    opcion = Prompt.ask("[bold yellow]Selecciona[/]", choices=["1", "2", "3", "4"], default="1")
    return int(opcion)

def menu_subtitulos(info):
    opciones, subs, auto_subs = mostrar_subtitulos(info)
    if not opciones:
        return None

    if not Confirm.ask("\n[bold yellow]¿Descargar subtítulos?[/]", default=False):
        return None

    console.print("\n[bold]Selecciona qué subtítulos descargar:[/]")
    console.print("  [bold cyan]T[/]  Todos los disponibles")
    console.print("  [bold cyan]M[/]  Solo manuales (subidos por creador)")
    console.print("  [bold cyan]A[/]  Solo automáticos (IA)")
    for i, (tipo, lang) in enumerate(opciones, 1):
        tipo_str = "[green]MANUAL[/]" if tipo == "manual" else "[blue]IA[/]"
        console.print(f"  [bold cyan]{i}[/]  {tipo_str}  {idioma_a_espanol(lang)} ({lang})")

    eleccion = Prompt.ask("[bold yellow]Selecciona[/]", default="T").strip().upper()

    idiomas_elegidos = []
    if eleccion == "T":
        idiomas_elegidos = [lang for tipo, lang in opciones]
    elif eleccion == "M":
        idiomas_elegidos = [lang for tipo, lang in opciones if tipo == "manual"]
    elif eleccion == "A":
        idiomas_elegidos = [lang for tipo, lang in opciones if tipo == "auto"]
    else:
        try:
            idx = int(eleccion)
            if 1 <= idx <= len(opciones):
                tipo, lang = opciones[idx - 1]
                idiomas_elegidos = [lang]
        except ValueError:
            idiomas_elegidos = [eleccion.lower()]

    if not idiomas_elegidos:
        console.print("[yellow]No se seleccionaron idiomas[/]")
        return None

    console.print(f"[green]✓[/] Subtítulos seleccionados: {', '.join(idiomas_elegidos)}")

    opts_sub = {}
    opts_sub["subtitles"] = "embed" if Confirm.ask("¿Embeber subtítulos en el video?", default=True) else "save"
    opts_sub["formats"] = ["srt"]
    if Confirm.ask("¿Descargar también en formato .vtt?", default=False):
        opts_sub["formats"].append("vtt")

    return {"langs": idiomas_elegidos, **opts_sub}

# ============================================================
#   PROGRESS BAR CON RICH
# ============================================================

class ProgressBar:
    def __init__(self):
        self.progress = None
        self.task_id = None
        self.downloaded = 0

    def hook(self, d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if total:
                if self.progress is None:
                    self.progress = Progress(
                        TextColumn("[bold blue]{task.description}"),
                        BarColumn(bar_width=40),
                        "[progress.percentage]{task.percentage:>3.0f}%",
                        "•",
                        DownloadColumn(),
                        "•",
                        TransferSpeedColumn(),
                        "•",
                        TimeRemainingColumn(),
                        console=console,
                    )
                    self.progress.start()
                    self.task_id = self.progress.add_task(
                        "[cyan]Descargando...", total=total
                    )
                if self.task_id is not None:
                    self.progress.update(self.task_id, completed=downloaded)
        elif d["status"] == "finished":
            if self.progress and self.task_id is not None:
                self.progress.update(self.task_id, completed=d.get("total_bytes", 0))
                self.progress.stop()
            console.print("[green]✅ Descarga completada[/]")

    def close(self):
        if self.progress:
            self.progress.stop()

def descargar_progreso(d):
    global _progress_bar_instance
    if d["status"] == "downloading":
        _progress_bar_instance.hook(d)
    elif d["status"] == "finished":
        _progress_bar_instance.hook(d)
    elif d["status"] == "error":
        if _progress_bar_instance.progress:
            _progress_bar_instance.progress.stop()

_progress_bar_instance = ProgressBar()

# ============================================================
#   DESCARGA
# ============================================================

def descargar_video(url, info, calidad_idx, formato, orden_calidades, subs_opts, cookies_info=None):
    titulo = info.get("title", "video")
    # Sanitizar nombre de archivo
    titulo_limpio = re.sub(r'[<>:"/\\|?*]', "", titulo)[:100]

    # Formato base
    if calidad_idx == 0:
        # Mejor calidad
        format_spec = f"bestvideo[ext={formato}]+bestaudio[ext=m4a]/best[ext={formato}]/best"
    else:
        label, data = orden_calidades[calidad_idx - 1]
        height = data["height"]
        if data.get("acodec", "none") != "none":
            format_spec = f"bestvideo[height<={height}][ext={formato}]+bestaudio/best[height<={height}][ext={formato}]"
        else:
            format_spec = f"bestvideo[height<={height}][ext={formato}]+bestaudio/best[height<={height}][ext={formato}]"

    ydl_opts = {
        "format": format_spec,
        "outtmpl": f"{Path.home() / 'Downloads' / 'yt-dlp'}/%(title).100s.%(ext)s",
        "progress_hooks": [descargar_progreso],
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "js_runtimes": {"node": {}},
    }

    # Agregar cookies
    agregar_cookies_opciones(ydl_opts, cookies_info)

    # Subtítulos
    if subs_opts:
        ydl_opts["writesubtitles"] = True
        ydl_opts["writeautomaticsub"] = True
        ydl_opts["subtitleslangs"] = subs_opts["langs"]
        if subs_opts["subtitles"] == "embed":
            ydl_opts["embedsubs"] = True
        ydl_opts["subtitlesformat"] = subs_opts["formats"][0] if subs_opts["formats"] else "srt"
        if len(subs_opts["formats"]) > 1:
            ydl_opts["subtitlesformat"] = subs_opts["formats"][0]
            ydl_opts["keepvideo"] = True

    try:
        console.print("\n[bold cyan]⏬ Iniciando descarga...[/]")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        console.print(f"\n[red]❌ Error durante la descarga: {e}[/]")
        return False

def descargar_audio(url, info, calidad_opcion, cookies_info=None):
    calidad_map = {
        1: "bestaudio/best",
        2: "bestaudio[ext=m4a]/bestaudio",
        3: "bestaudio[ext=m4a]/bestaudio",
        4: "bestaudio[abr<=64]/bestaudio",
    }

    format_spec = calidad_map.get(calidad_opcion, "bestaudio/best")

    ydl_opts = {
        "format": format_spec,
        "outtmpl": f"{Path.home() / 'Downloads' / 'yt-dlp'}/%(title).100s.%(ext)s",
        "progress_hooks": [descargar_progreso],
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
            }
        ],
        "prefer_ffmpeg": True,
        "js_runtimes": {"node": {}},
    }

    # Agregar cookies
    agregar_cookies_opciones(ydl_opts, cookies_info)

    if calidad_opcion == 1:
        ydl_opts["postprocessors"][0]["preferredquality"] = "320"
    elif calidad_opcion == 4:
        ydl_opts["postprocessors"][0]["preferredquality"] = "64"
    else:
        ydl_opts["postprocessors"][0]["preferredquality"] = "192"

    try:
        console.print("\n[bold cyan]⏬ Descargando audio...[/]")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        console.print(f"\n[red]❌ Error durante la descarga: {e}[/]")
        return False

def descargar_subtitulos(url, info, subs_opts, cookies_info=None):
    if not subs_opts:
        return False

    ydl_opts = {
        "outtmpl": f"{Path.home() / 'Downloads' / 'yt-dlp'}/%(title).100s.%(ext)s",
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": subs_opts["langs"],
        "subtitlesformat": "srt",
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "js_runtimes": {"node": {}},
    }

    # Agregar cookies
    agregar_cookies_opciones(ydl_opts, cookies_info)

    try:
        console.print(f"\n[bold cyan]📝 Descargando subtítulos ({', '.join(subs_opts['langs'])})...[/]")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        console.print("[green]✅ Subtítulos descargados[/]")
        return True
    except Exception as e:
        console.print(f"\n[red]❌ Error: {e}[/]")
        return False

# ============================================================
#   MOSTRAR RESULTADO
# ============================================================

def mostrar_resultado(ruta=None):
    if ruta is None:
        ruta = str(Path.home() / "Downloads" / "yt-dlp")
    ruta_path = Path(ruta)
    if ruta_path.exists():
        archivos = list(ruta_path.iterdir())
        if archivos:
            archivos_ordenados = sorted(archivos, key=os.path.getmtime, reverse=True)
            console.print("\n[bold green]📁 Archivos descargados recientemente:[/]")
            table = Table(box=box.SIMPLE)
            table.add_column("Archivo", style="cyan")
            table.add_column("Tamaño", style="yellow")
            for f in archivos_ordenados[:5]:
                size = f.stat().st_size
                if size > 1024 * 1024:
                    size_str = f"{size / (1024*1024):.1f} MB"
                elif size > 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size} B"
                table.add_row(f.name, size_str)
            console.print(table)
            console.print(f"\n[bold]📂 Carpeta:[/] [underline]{ruta_path.resolve()}[/]")

# ============================================================
#   MAIN
# ============================================================

def main():
    global _progress_bar_instance

    mostrar_banner()
    separador()

    # Verificar dependencias
    ffmpeg_ok = verificar_dependencias()
    separador()

    cookies_info = None

    while True:
        # Obtener URL
        url = obtener_url()

        # Intentar obtener información (primero sin cookies, sin verbose)
        info = extraer_info(url)

        # Si falló, puede ser por restricción de edad - preguntar por cookies
        if not info:
            separador()
            console.print("[yellow]⚠ No se pudo obtener información del video[/]")
            console.print("[dim]Esto puede ser por restricción de edad o video no disponible[/]\n")

            cookies_info = obtener_opciones_cookies(None)
            if cookies_info:
                # Reintentar con cookies (verbose para ver detalles)
                console.print("\n[bold]📡 Reintentando con autenticación...[/]")
                info = extraer_info(url, cookies_info, verbose=True)
                if not info:
                    console.print("\n[red]❌ No se pudo acceder al video incluso con cookies[/]")
                    console.print("[dim]Posibles causas:[/]")
                    console.print("  [dim]1. El navegador estaba abierto (ciérralo)[/]")
                    console.print("  [dim]2. No estás logueado en YouTube en ese navegador[/]")
                    console.print("  [dim]3. Las cookies expiraron[/]")
                    console.print("  [dim]4. Intenta exportar cookies manualmente con la extensión[/]")
                    cookies_info = None
                    if not Confirm.ask("¿Intentar con otra URL?", default=True):
                        break
                    continue
            else:
                if not Confirm.ask("¿Intentar con otra URL?", default=True):
                    break
                continue

        separador()

        # Verificar si hay restricción de edad en la info obtenida
        if info:
            age_limit = info.get("age_limit")
            if age_limit and age_limit > 0:
                console.print("[yellow]⚠ Este video tiene restricción de edad[/]")
                if not cookies_info:
                    cookies_info = obtener_opciones_cookies(info)
                    if cookies_info:
                        # Reintentar con cookies para obtener info completa
                        info = extraer_info(url, cookies_info, verbose=True)
                        if not info:
                            console.print("[red]❌ No se pudo acceder al video incluso con cookies[/]")
                            cookies_info = None
                            if not Confirm.ask("¿Intentar con otra URL?", default=True):
                                break
                            continue

        # Mostrar info
        mostrar_info_video(info)

        # Es playlist?
        es_playlist = info.get("_type") == "playlist" or "entries" in info
        if es_playlist:
            console.print(f"\n[bold yellow]📋 Es una playlist con {info.get('playlist_count', '?')} videos[/]")
            if not Confirm.ask("¿Descargar toda la playlist?", default=True):
                info = None
                separador()
                if not Confirm.ask("¿Probar otra URL?", default=True):
                    break
                continue

        separador()

        # Obtener calidades
        calidades = obtener_calidades(info) if not es_playlist else {}
        orden_calidades = None
        if calidades:
            orden_calidades = mostrar_calidades(calidades)
            separador()

        # Obtener subtítulos
        subs_opts = None
        if not es_playlist:
            subs_opts = menu_subtitulos(info)
            separador()

        # Elegir modo
        modo = menu_modo_descarga()

        if modo == 0:
            console.print("[bold yellow]👋 ¡Hasta luego![/]")
            break

        resultado = False

        if modo == 1:
            # Video + Audio
            console.print("\n[bold cyan]📹 Modo: Video + Audio[/]")
            calidad_idx = 0
            formato = "mp4"
            if orden_calidades:
                calidad_idx = menu_calidad(orden_calidades)
                separador()
                formato = menu_formato(calidades)
            resultado = descargar_video(url, info, calidad_idx, formato, orden_calidades or [], subs_opts, cookies_info)

        elif modo == 2:
            # Solo Audio
            console.print("\n[bold cyan]🎵 Modo: Solo Audio (música)[/]")
            calidad_audio = menu_audio_calidad()
            if not ffmpeg_ok:
                console.print("[red]❌ FFmpeg es necesario para extraer audio. Abortando.[/]")
                resultado = False
            else:
                resultado = descargar_audio(url, info, calidad_audio, cookies_info)

        elif modo == 3:
            # Solo Subtítulos
            console.print("\n[bold cyan]📝 Modo: Solo Subtítulos[/]")
            resultado = descargar_subtitulos(url, info, subs_opts, cookies_info)

        if resultado:
            mostrar_resultado()
        else:
            console.print("[red]❌ La descarga no se completó[/]")

        separador()
        if not Confirm.ask("\n[bold yellow]¿Descargar otro video?[/]", default=True):
            break
        limpiar_pantalla()

    console.print("\n[bold green]🎉 ¡Gracias por usar YouTube Descargador![/]")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[bold yellow]⚠ Operación cancelada por el usuario[/]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]❌ Error inesperado: {e}[/]")
        import traceback
        traceback.print_exc()
        sys.exit(1)
