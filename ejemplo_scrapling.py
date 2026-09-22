"""
Script de ejemplo de Scrapling — demuestra las capacidades principales de la libreria.

Uso (desde la raiz del proyecto, con el venv que ya esta instalado):

    .venv\\Scripts\\python.exe ejemplo_scrapling.py              # demos rapidas (sin navegador)
    .venv\\Scripts\\python.exe ejemplo_scrapling.py todo         # todas, incluida la del navegador
    .venv\\Scripts\\python.exe ejemplo_scrapling.py spider       # solo una demo concreta

Demos disponibles: basico, adaptativo, markdown, spider, checkpoints, proxies, stealth

Los ficheros generados se guardan en ./salida/
Sitios usados: quotes.toscrape.com (sandbox publico hecho para practicar scraping).
"""

import sys
from pathlib import Path

# Windows: evita que las comillas tipograficas de la web revienten la consola cp1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SALIDA = Path(__file__).parent / "salida"
SALIDA.mkdir(exist_ok=True)


def titulo(texto: str) -> None:
    print(f"\n{'=' * 70}\n  {texto}\n{'=' * 70}")


# --------------------------------------------------------------------------- #
# 1. BASICO: peticion HTTP + seleccion + navegacion del DOM
# --------------------------------------------------------------------------- #
def demo_basico() -> None:
    titulo("1. Fetcher HTTP + seleccion")

    from scrapling.fetchers import Fetcher

    # Fetcher usa curl_cffi por debajo: imita el fingerprint TLS de un navegador real.
    # La Response que devuelve HEREDA de Selector, por eso puedes hacer .css() directamente.
    page = Fetcher.get(
        "https://quotes.toscrape.com/",
        impersonate="chrome",  # fingerprint TLS + cabeceras de Chrome
        timeout=20,
    )
    print(f"status={page.status}  encoding={page.encoding}  bytes={len(page.body)}")

    tarjetas = page.css(".quote")
    print(f"Citas encontradas: {len(tarjetas)}\n")

    for card in tarjetas[:3]:
        texto = card.css(".text::text").get()
        autor = card.css(".author::text").get()
        tags = card.css(".tag::text").getall()
        print(f"  - {autor}: {texto[:55]}...")
        print(f"    tags: {', '.join(tags)}")

    # Busqueda por texto y por regex (no hace falta selector)
    einstein = page.find_by_text("Albert Einstein", first_match=True)
    print(f"\nfind_by_text('Albert Einstein') -> <{einstein.tag} class='{einstein.attrib.get('class')}'>")

    # Navegacion del arbol
    primera = tarjetas[0]
    print(f"padre: <{primera.parent.tag}>   hermanos: {len(primera.siblings)}   hijos: {len(primera.children)}")

    # find_similar: dame todo lo que se parezca a este elemento (sin escribir selector)
    print(f"find_similar() desde la primera cita -> {len(primera.find_similar())} elementos parecidos")

    # Generacion automatica de selectores robustos
    print(f"selector CSS generado: {primera.css('.author')[0].generate_css_selector}")
    print(f"selector XPath generado: {primera.css('.author')[0].generate_xpath_selector}")


# --------------------------------------------------------------------------- #
# 2. ADAPTATIVO: la funcion estrella — reencontrar elementos tras un rediseno
# --------------------------------------------------------------------------- #
def demo_adaptativo() -> None:
    titulo("2. Adaptive scraping (sobrevivir a un cambio de diseno)")

    from scrapling.parser import Selector

    URL = "https://shop.ejemplo.com/productos"
    db = str(SALIDA / "adaptive.db")

    # Version 1 de la web: la que existia cuando escribiste tu scraper
    v1 = """<html><body><div id="main">
      <div class="product-card">
        <h2 class="product-title">Teclado Mecanico</h2><span class="price">89.99</span>
      </div>
      <div class="product-card">
        <h2 class="product-title">Raton Vertical</h2><span class="price">45.50</span>
      </div>
    </div></body></html>"""

    # Version 2: el sitio se rediseno por completo. Otras etiquetas, otras clases,
    # otra jerarquia. Tu selector '.product-title' ya no existe.
    v2 = """<html><body><main class="catalog"><section class="wrapper">
      <article data-sku="1" class="item-box">
        <h3 class="item-name">Teclado Mecanico</h3><span class="amount">89.99</span>
      </article>
      <article data-sku="2" class="item-box">
        <h3 class="item-name">Raton Vertical</h3><span class="amount">45.50</span>
      </article>
    </section></main></body></html>"""

    storage = {"storage_file": db, "url": URL}

    # --- Dia 1: scrapeas normal, pero con auto_save=True ---
    pagina_vieja = Selector(content=v1, url=URL, adaptive=True, storage_args=storage)
    encontrados = pagina_vieja.css(".product-title", identifier="titulos", auto_save=True)
    print(f"[dia 1] con '.product-title' -> {[e.text for e in encontrados]}")
    print(f"        huella guardada en SQLite: {db}")

    # Lo que se guarda no es el selector, es una "huella" del elemento:
    # tag, texto, atributos, ruta en el arbol, datos del padre y de los hermanos.

    # --- Dia 30: la web cambio ---
    pagina_nueva = Selector(content=v2, url=URL, adaptive=True, storage_args=storage)

    sin_adaptive = pagina_nueva.css(".product-title", identifier="titulos")
    print(f"\n[dia 30] con '.product-title' normal -> {len(sin_adaptive)} resultados (scraper roto)")

    # adaptive=True: si el selector falla, recorre TODO el DOM puntuando cada
    # elemento contra la huella guardada (difflib.SequenceMatcher) y devuelve
    # el/los de mayor puntuacion, siempre que superen `percentage` (40 por defecto).
    con_adaptive = pagina_nueva.css(".product-title", identifier="titulos", adaptive=True)
    print(f"[dia 30] con adaptive=True         -> {[e.text for e in con_adaptive]}  <-- recuperado")

    if con_adaptive:
        nuevo = con_adaptive[0]
        print(f"\n  lo encontro aqui: <{nuevo.tag} class='{nuevo.attrib.get('class')}'>")
        print(f"  selector nuevo:   {nuevo.generate_css_selector}")
        # Nota: relocate() devuelve solo el grupo con la puntuacion MAS ALTA.
        # Como cada producto tiene un texto distinto, gana el que coincide exacto.
        # Para recuperar la lista entera, usa el elemento recuperado como ancla:
        print(f"  hermanos del mismo tipo: {len(nuevo.find_similar()) + 1} productos")


# --------------------------------------------------------------------------- #
# 3. MARKDOWN: convertir una pagina en texto limpio para RAG / LLMs
# --------------------------------------------------------------------------- #
def demo_markdown() -> None:
    titulo("3. Pagina -> Markdown limpio (RAG, sin LLM de por medio)")

    from scrapling.fetchers import Fetcher

    page = Fetcher.get("https://quotes.toscrape.com/", timeout=20)

    # main_content_only descarta nav/footer/scripts; css_selector acota aun mas
    md = page.markdown(css_selector=".quote", main_content_only=True)

    destino = SALIDA / "citas.md"
    destino.write_text(md, encoding="utf-8")

    print(f"Markdown generado: {len(md)} caracteres -> {destino}")
    print("\n--- primeras lineas ---")
    for linea in md.splitlines()[:6]:
        print(f"  {linea}")


# --------------------------------------------------------------------------- #
# 4. SPIDER: crawl concurrente con paginacion, autothrottle y export
# --------------------------------------------------------------------------- #
def demo_spider() -> None:
    titulo("4. Spider: crawl paginado con autothrottle y export")

    from scrapling.spiders import Spider, Request, Response
    from scrapling.fetchers import FetcherSession
    from scrapling.spiders.session import SessionManager

    class CitasSpider(Spider):
        name = "citas"
        start_urls = ["https://quotes.toscrape.com/"]
        allowed_domains = {"quotes.toscrape.com"}  # no se sale del dominio

        concurrent_requests = 4  # peticiones en paralelo
        autothrottle_enabled = True  # ajusta el delay solo segun responda el server
        autothrottle_start_delay = 1.0
        robots_txt_obey = True  # respeta robots.txt y Crawl-delay
        logging_level = 20  # INFO (usa 10 para ver el DEBUG completo)

        MAX_PAGINAS = 3  # limite para que la demo no tarde

        def configure_sessions(self, manager: SessionManager) -> None:
            # Aqui podrias registrar varias sesiones (HTTP / navegador / stealth)
            # y enrutar cada Request a una con Request(url, sid="nombre").
            manager.add("http", FetcherSession(impersonate="chrome"))

        async def parse(self, response: Response):
            pagina = response.meta.get("pagina", 1)

            for card in response.css(".quote"):
                yield {
                    "texto": card.css(".text::text").get(),
                    "autor": card.css(".author::text").get(),
                    "tags": ", ".join(card.css(".tag::text").getall()),
                    "pagina": pagina,
                }

            siguiente = response.css(".next a::attr(href)").get()
            if siguiente and pagina < self.MAX_PAGINAS:
                # yield de un Request = seguir crawleando (el scheduler deduplica solo)
                yield Request(response.urljoin(siguiente), meta={"pagina": pagina + 1})

        async def on_scraped_item(self, item):
            # Hook de pipeline: limpia, valida o devuelve None para descartar
            item["texto"] = item["texto"].strip("“”\"")
            return item

    resultado = CitasSpider().start()

    # Exportadores incluidos
    resultado.items.to_json(SALIDA / "citas.json", indent=True)
    resultado.items.to_csv(SALIDA / "citas.csv")

    s = resultado.stats
    print(f"\n  items scrapeados : {s.items_scraped}")
    print(f"  peticiones       : {s.requests_count}  ({s.response_status_count})")
    print(f"  tiempo           : {s.elapsed_seconds}s")
    print(f"  delay autoajustado: {s.autothrottle_delays}")
    print(f"  bytes descargados : {s.response_bytes}")
    print(f"\n  exportado a: {SALIDA / 'citas.json'} y {SALIDA / 'citas.csv'}")
    if resultado.items:
        print(f"\n  ejemplo: {resultado.items[0]}")

    # Para crawls largos: CitasSpider(crawldir="./checkpoints").start()
    # -> Ctrl+C guarda el estado y al relanzar continua donde iba.


# --------------------------------------------------------------------------- #
# 5. STEALTH: navegador real contra una pagina que solo existe tras ejecutar JS
# --------------------------------------------------------------------------- #
def demo_stealth() -> None:
    titulo("5. StealthyFetcher: navegador con anti-deteccion (lento, ~30s)")

    from scrapling.fetchers import StealthyFetcher

    # /js/ construye las citas con JavaScript: Fetcher (HTTP puro) veria 0 resultados.
    page = StealthyFetcher.fetch(
        "https://quotes.toscrape.com/js/",
        headless=True,
        network_idle=True,  # espera a que no haya trafico de red
        disable_resources=False,  # ponlo a True para no bajar imagenes/fuentes (mas rapido)
        timeout=60000,
        # solve_cloudflare=True,   <- resuelve Turnstile/Interstitial automaticamente
        # proxy="http://user:pass@host:puerto",
        # block_webrtc=True, hide_canvas=True,  <- ya activos por defecto en stealth
    )

    citas = page.css(".quote")
    print(f"status={page.status}   citas renderizadas por JS: {len(citas)}")
    if citas:
        print(f"  primera: {citas[0].css('.text::text').get()[:60]}...")

    (SALIDA / "js_render.html").write_text(page.html_content, encoding="utf-8")
    print(f"  HTML final (post-JS) guardado en {SALIDA / 'js_render.html'}")


# --------------------------------------------------------------------------- #
# 6. CHECKPOINTS: pausar un crawl y reanudarlo donde se quedo
# --------------------------------------------------------------------------- #
def demo_checkpoints() -> None:
    titulo("6. Checkpoints: pausa y reanudacion de un crawl")

    import shutil
    from scrapling.spiders import Spider, Request, Response

    CRAWLDIR = SALIDA / "checkpoints"
    shutil.rmtree(CRAWLDIR, ignore_errors=True)  # empezamos limpio para la demo

    class CrawlLargo(Spider):
        name = "crawl_largo"
        start_urls = ["https://quotes.toscrape.com/"]
        allowed_domains = {"quotes.toscrape.com"}
        concurrent_requests = 2
        logging_level = 30  # WARNING: silencia el volcado de stats de cada run

        MAX_PAGINAS = 5

        def __init__(self, pausar_tras=None, **kwargs):
            """:param pausar_tras: nº de paginas tras el que simular un Ctrl+C."""
            super().__init__(**kwargs)
            self.pausar_tras = pausar_tras
            self.paginas_vistas = 0

        async def parse(self, response: Response):
            self.paginas_vistas += 1
            pagina = response.meta.get("pagina", 1)
            print(f"    -> procesando pagina {pagina}")

            for card in response.css(".quote"):
                yield {"autor": card.css(".author::text").get(), "pagina": pagina}

            siguiente = response.css(".next a::attr(href)").get()
            if siguiente and pagina < self.MAX_PAGINAS:
                yield Request(response.urljoin(siguiente), meta={"pagina": pagina + 1})

            # self.pause() hace exactamente lo mismo que un Ctrl+C:
            # espera a que terminen las peticiones en vuelo y guarda el checkpoint.
            if self.pausar_tras and self.paginas_vistas >= self.pausar_tras:
                print("    [simulando Ctrl+C]")
                self.pause()

    # --- Run 1: se interrumpe a mitad ---
    print("\n  RUN 1 (se interrumpe tras 2 paginas)")
    # crawldir activa el sistema de checkpoints; interval = cada cuantos segundos
    # se guarda ademas de forma periodica (0 = solo al pausar).
    r1 = CrawlLargo(crawldir=CRAWLDIR, interval=0, pausar_tras=2).start()
    print(f"  items: {len(r1.items)}   paused: {r1.paused}")

    ckpt = CRAWLDIR / "checkpoint.pkl"
    if ckpt.exists():
        print(f"  checkpoint en disco: {ckpt.name} ({ckpt.stat().st_size} bytes)")
        print("  contiene: las Requests pendientes + los fingerprints ya vistos")

    # --- Run 2: mismo crawldir -> reanuda ---
    print("\n  RUN 2 (mismo crawldir, reanuda sin repetir lo hecho)")
    r2 = CrawlLargo(crawldir=CRAWLDIR, interval=0).start()  # sin pausar_tras: va hasta el final
    print(f"  items: {len(r2.items)}   paused: {r2.paused}")

    paginas_r1 = sorted({i["pagina"] for i in r1.items})
    paginas_r2 = sorted({i["pagina"] for i in r2.items})
    print(f"\n  paginas del run 1: {paginas_r1}")
    print(f"  paginas del run 2: {paginas_r2}   <-- no repite ninguna")
    print(f"  total: {len(r1.items) + len(r2.items)} items entre las dos ejecuciones")

    # Al terminar sin pausa, el checkpoint se borra solo
    print(f"  checkpoint tras completar: {'sigue ahi' if ckpt.exists() else 'borrado automaticamente'}")

    print("\n  En la vida real no hace falta pausar_tras: lanzas el spider con")
    print("  crawldir='./checkpoints', pulsas Ctrl+C cuando quieras y al relanzar continua.")


# --------------------------------------------------------------------------- #
# 7. PROXIES: rotacion automatica
# --------------------------------------------------------------------------- #
def demo_proxies() -> None:
    titulo("7. Rotacion de proxies")

    import os
    from random import choice
    from scrapling.engines.toolbelt import ProxyRotator, is_proxy_error

    # --- A) La mecanica del rotador (sin red, siempre funciona) ---
    print("\n  A) Rotacion ciclica (estrategia por defecto)")

    proxies = [
        "http://user:pass@proxy-es.ejemplo.com:8080",  # formato string
        "http://user:pass@proxy-fr.ejemplo.com:8080",
        {"server": "http://proxy-de.ejemplo.com:8080", "username": "user", "password": "pass"},  # formato dict
    ]
    rotador = ProxyRotator(proxies)
    print(f"     {rotador!r}")
    for i in range(5):
        p = rotador.get_proxy()
        etiqueta = p if isinstance(p, str) else p["server"]
        print(f"     peticion {i + 1} -> {etiqueta}")

    # --- B) Estrategia propia ---
    print("\n  B) Estrategia personalizada (aleatoria en vez de ciclica)")

    def rotacion_aleatoria(lista, indice_actual):
        """Debe devolver (proxy_elegido, siguiente_indice). El rotador es thread-safe."""
        return choice(lista), indice_actual

    rotador_random = ProxyRotator(proxies, strategy=rotacion_aleatoria)
    elegidos = [rotador_random.get_proxy() for _ in range(4)]
    print(f"     {[p if isinstance(p, str) else p['server'] for p in elegidos]}")

    # --- C) Deteccion de fallos de proxy ---
    print("\n  C) is_proxy_error(): distingue un proxy caido de un error normal")
    print(f"     'net::ERR_PROXY_CONNECTION_FAILED' -> {is_proxy_error(Exception('net::ERR_PROXY_CONNECTION_FAILED'))}")
    print(f"     'Invalid JSON response'            -> {is_proxy_error(Exception('Invalid JSON response'))}")
    print("     Cuando salta True, la sesion reintenta automaticamente con el SIGUIENTE proxy")
    print("     (hasta `retries` veces). Con un error normal reintenta con el mismo.")

    # --- D) Enchufarlo de verdad ---
    print("\n  D) Uso real (necesita proxies que funcionen)")
    print("     FetcherSession(proxy_rotator=rotador)     # HTTP")
    print("     StealthySession(proxy_rotator=rotador)    # navegador stealth")
    print("     Fetcher.get(url, proxy='http://...')      # proxy fijo, ignora el rotador")
    print("     response.meta['proxy']                    # que proxy se uso realmente")
    print("\n     En un Spider va dentro de configure_sessions():")
    print("       def configure_sessions(self, manager):")
    print("           manager.add('http', FetcherSession(proxy_rotator=ProxyRotator([...])))")

    # Si tienes proxies reales, exportalos y esta parte se ejecuta de verdad:
    #   PowerShell: $env:SCRAPLING_PROXIES = "http://user:pass@host:puerto,http://otro:puerto"
    reales = [p.strip() for p in os.environ.get("SCRAPLING_PROXIES", "").split(",") if p.strip()]
    if not reales:
        print("\n     [omitido] Define SCRAPLING_PROXIES para probarlo contra la red.")
        return

    from scrapling.fetchers import FetcherSession

    print(f"\n     Probando con {len(reales)} proxies reales contra httpbin...")
    rotador_real = ProxyRotator(reales)
    with FetcherSession(proxy_rotator=rotador_real, retries=2, timeout=20) as sesion:
        for i in range(len(reales)):
            try:
                r = sesion.get("https://httpbin.org/ip")
                print(f"       peticion {i + 1}: proxy={r.meta.get('proxy')}  ip_vista={r.json()}")
            except Exception as e:
                print(f"       peticion {i + 1} fallo: {type(e).__name__}: {e}")


# --------------------------------------------------------------------------- #

DEMOS = {
    "basico": demo_basico,
    "adaptativo": demo_adaptativo,
    "markdown": demo_markdown,
    "spider": demo_spider,
    "checkpoints": demo_checkpoints,
    "proxies": demo_proxies,
    "stealth": demo_stealth,
}
RAPIDAS = ["basico", "adaptativo", "markdown", "spider", "checkpoints", "proxies"]


def main() -> None:
    args = [a.lower() for a in sys.argv[1:]]

    if not args:
        elegidas = RAPIDAS
        print("Ejecutando demos rapidas (sin navegador).")
        print("Usa 'todo' para incluir la demo de StealthyFetcher.")
    elif "todo" in args:
        elegidas = list(DEMOS)
    else:
        desconocidas = [a for a in args if a not in DEMOS]
        if desconocidas:
            print(f"Demo desconocida: {', '.join(desconocidas)}")
            print(f"Disponibles: {', '.join(DEMOS)}, todo")
            sys.exit(1)
        elegidas = args

    for nombre in elegidas:
        try:
            DEMOS[nombre]()
        except Exception as e:  # que un fallo de red no tumbe el resto
            print(f"\n[!] La demo '{nombre}' fallo: {type(e).__name__}: {e}")

    print(f"\nListo. Ficheros generados en: {SALIDA}")


if __name__ == "__main__":
    main()
