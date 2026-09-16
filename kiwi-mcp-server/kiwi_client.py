import json
import ssl
import urllib.request
import urllib.error
from http.cookiejar import CookieJar
import logging

logger = logging.getLogger("kiwi-client")


class KiwiClient:
    """
    Cliente JSON-RPC para Kiwi TCMS usando la biblioteca estándar de Python.
    Compatible con certificados SSL locales/autofirmados y manejo de sesión por cookies.
    """

    def __init__(self, base_url="https://localhost", host_header=None):
        self.base_url = base_url.rstrip("/")
        self.endpoint = f"{self.base_url}/json-rpc/"
        self.host_header = host_header or ("localhost" if "localhost" in base_url or "kiwi_web" in base_url else None)
        self._request_id = 0

        # Deshabilitar verificación estricta SSL para entornos locales o autofirmados
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

        self.cookie_jar = CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self.ssl_context),
            urllib.request.HTTPCookieProcessor(self.cookie_jar),
        )

    def call(self, method, *params):
        """Ejecuta un método RPC en Kiwi TCMS con JSON-RPC 2.0."""
        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": list(params),
            "id": self._request_id,
        }

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Kiwi-MCP-Server/1.0",
        }
        if self.host_header:
            headers["Host"] = self.host_header

        request = urllib.request.Request(
            self.endpoint,
            data=data,
            headers=headers,
        )

        try:
            with self.opener.open(request) as response:
                result_data = json.loads(response.read().decode("utf-8"))

                if "error" in result_data:
                    error_info = result_data["error"]
                    raise RuntimeError(
                        f"Error RPC [{error_info.get('code')}]: {error_info.get('message')}"
                    )

                return result_data.get("result")

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Error HTTP {e.code}: {e.reason}\nDetalles: {error_body}")
        except Exception as e:
            raise RuntimeError(f"Error conectando a Kiwi TCMS ({self.endpoint}): {e}")

    def login(self, username, password):
        """Inicia sesión para establecer la cookie de autenticación de Django."""
        session_id = self.call("Auth.login", username, password)
        logger.info(f"Autenticado exitosamente en Kiwi TCMS como '{username}'")
        return session_id

    # --------------------------------------------------------------------------
    # Resolutores de Entidades
    # --------------------------------------------------------------------------
    def resolve_or_create_product(self, product_name: str, description: str = ""):
        """Busca o crea un Producto por nombre."""
        name = product_name.strip()
        existing = self.call("Product.filter", {"name": name})
        if existing:
            return existing[0]["id"]

        classifications = self.call("Classification.filter", {})
        class_id = classifications[0]["id"] if classifications else 1

        new_prod = self.call("Product.create", {
            "name": name,
            "classification": class_id,
            "description": description or f"Producto {name} registrado automáticamente",
        })
        prod_id = new_prod["id"]

        # Crear categoría por defecto
        try:
            self.call("Category.create", {
                "product": prod_id,
                "name": "--default--",
                "description": "Categoría general",
            })
        except Exception:
            pass

        return prod_id

    def resolve_or_create_version(self, product_id: int, version_value: str = "1.0.0"):
        """Busca o crea una Versión para un Producto específico."""
        val = str(version_value).strip() or "1.0.0"
        existing = self.call("Version.filter", {"product": product_id, "value": val})
        if existing:
            return existing[0]["id"]

        new_ver = self.call("Version.create", {
            "product": product_id,
            "value": val,
        })
        return new_ver["id"]

    def resolve_or_create_build(self, version_id: int, build_name: str = "001"):
        """Busca o crea un Build para una Versión específica."""
        b_name = str(build_name).strip() or "001"
        existing = self.call("Build.filter", {"version": version_id, "name": b_name})
        if existing:
            return existing[0]["id"]

        new_bld = self.call("Build.create", {
            "version": version_id,
            "name": b_name,
        })
        return new_bld["id"]

    def resolve_or_create_category(self, product_id: int, category_name: str):
        """Busca o crea una Categoría para un Producto."""
        name = category_name.strip() if category_name else "--default--"
        existing = self.call("Category.filter", {"product": product_id, "name": name})
        if existing:
            return existing[0]["id"]

        try:
            new_cat = self.call("Category.create", {
                "product": product_id,
                "name": name,
                "description": f"Categoría {name}",
            })
            return new_cat["id"]
        except Exception:
            cats = self.call("Category.filter", {"product": product_id})
            return cats[0]["id"] if cats else 1
