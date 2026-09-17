import json
import ssl
import urllib.request
import urllib.error
from http.cookiejar import CookieJar
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("kiwi-client")


def _extract_id(obj: Any) -> int:
    """Extrae el identificador numérico de una respuesta RPC de Kiwi (dict o int)."""
    if isinstance(obj, dict):
        val = obj.get("id") or obj.get("pk")
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
    try:
        return int(obj)
    except (ValueError, TypeError):
        return 1


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
    # Resolutores Robustos de Entidades (Soporta Kiwi recién instalado y vacío)
    # --------------------------------------------------------------------------
    def resolve_or_create_classification(self, classification_name: Optional[str] = None) -> int:
        """
        Busca o crea una Clasificación en Kiwi TCMS.
        Si la base de datos está vacía, crea una clasificación por defecto ('General').
        """
        name = (classification_name or "").strip()
        if name:
            try:
                existing = self.call("Classification.filter", {"name": name})
                if existing:
                    return _extract_id(existing[0])
                existing_icase = self.call("Classification.filter", {"name__iexact": name})
                if existing_icase:
                    return _extract_id(existing_icase[0])
            except Exception:
                pass

            try:
                new_cls = self.call("Classification.create", {
                    "name": name,
                    "description": f"Clasificación {name}",
                })
                return _extract_id(new_cls)
            except Exception as e:
                logger.warning(f"No se pudo crear clasificación '{name}': {e}")

        # Buscar cualquier clasificación existente
        try:
            existing_all = self.call("Classification.filter", {})
            if existing_all:
                return _extract_id(existing_all[0])
        except Exception:
            pass

        # Si Kiwi está completamente vacío, crear la clasificación 'General'
        try:
            new_cls = self.call("Classification.create", {
                "name": "General",
                "description": "Clasificación general por defecto",
            })
            return _extract_id(new_cls)
        except Exception as e:
            logger.error(f"Error al crear clasificación por defecto: {e}")
            try:
                recheck = self.call("Classification.filter", {})
                if recheck:
                    return _extract_id(recheck[0])
            except Exception:
                pass
            return 1

    def resolve_or_create_product(
        self,
        product_name: str,
        description: str = "",
        classification: Optional[str] = None,
    ) -> int:
        """
        Busca o crea un Producto por nombre, asegurando que tenga una Clasificación válida
        incluso en instancias de Kiwi TCMS completamente limpias.
        """
        name = product_name.strip()
        try:
            existing = self.call("Product.filter", {"name": name})
            if existing:
                return _extract_id(existing[0])
            existing_icase = self.call("Product.filter", {"name__iexact": name})
            if existing_icase:
                return _extract_id(existing_icase[0])
        except Exception:
            pass

        class_id = self.resolve_or_create_classification(classification)

        new_prod = self.call("Product.create", {
            "name": name,
            "classification": class_id,
            "description": description or f"Producto {name} registrado automáticamente",
        })
        prod_id = _extract_id(new_prod)

        # Crear categoría por defecto para el producto
        self.resolve_or_create_category(prod_id, "--default--")

        return prod_id

    def resolve_or_create_version(self, product_id: int, version_value: str = "1.0.0") -> int:
        """Busca o crea una Versión para un Producto específico."""
        val = str(version_value).strip() or "1.0.0"
        try:
            existing = self.call("Version.filter", {"product": product_id, "value": val})
            if existing:
                return _extract_id(existing[0])
            existing_all = self.call("Version.filter", {"product": product_id})
            for v in existing_all:
                if str(v.get("value", "")).strip().lower() == val.lower():
                    return _extract_id(v)
        except Exception:
            pass

        try:
            new_ver = self.call("Version.create", {
                "product": product_id,
                "value": val,
            })
            return _extract_id(new_ver)
        except Exception as e:
            logger.warning(f"No se pudo crear versión '{val}' para producto #{product_id}: {e}")
            try:
                existing_all = self.call("Version.filter", {"product": product_id})
                if existing_all:
                    return _extract_id(existing_all[0])
            except Exception:
                pass
            return 1

    def resolve_or_create_build(self, version_id: int, build_name: str = "001") -> int:
        """Busca o crea un Build para una Versión específica."""
        b_name = str(build_name).strip() or "001"
        try:
            existing = self.call("Build.filter", {"version": version_id, "name": b_name})
            if existing:
                return _extract_id(existing[0])
        except Exception:
            pass

        try:
            new_bld = self.call("Build.create", {
                "version": version_id,
                "name": b_name,
            })
            return _extract_id(new_bld)
        except Exception as e:
            logger.warning(f"No se pudo crear build '{b_name}' para versión #{version_id}: {e}")
            try:
                existing_all = self.call("Build.filter", {"version": version_id})
                if existing_all:
                    return _extract_id(existing_all[0])
            except Exception:
                pass
            return 1

    def resolve_or_create_category(self, product_id: int, category_name: str = "--default--") -> int:
        """Busca o crea una Categoría para un Producto."""
        name = (category_name or "").strip() or "--default--"
        try:
            existing = self.call("Category.filter", {"product": product_id, "name": name})
            if existing:
                return _extract_id(existing[0])
            existing_icase = self.call("Category.filter", {"product": product_id, "name__iexact": name})
            if existing_icase:
                return _extract_id(existing_icase[0])
        except Exception:
            pass

        try:
            new_cat = self.call("Category.create", {
                "product": product_id,
                "name": name,
                "description": f"Categoría {name}",
            })
            return _extract_id(new_cat)
        except Exception as e:
            logger.warning(f"No se pudo crear categoría '{name}' para producto #{product_id}: {e}")
            try:
                cats = self.call("Category.filter", {"product": product_id})
                if cats:
                    return _extract_id(cats[0])
            except Exception:
                pass
            return 1

    def resolve_or_create_plan_type(self, type_name: str = "Function") -> int:
        """Busca o crea un tipo de Plan de Pruebas (PlanType)."""
        name = (type_name or "").strip() or "Function"
        try:
            existing = self.call("PlanType.filter", {"name": name})
            if existing:
                return _extract_id(existing[0])
            existing_icase = self.call("PlanType.filter", {"name__iexact": name})
            if existing_icase:
                return _extract_id(existing_icase[0])
            existing_all = self.call("PlanType.filter", {})
            if existing_all:
                return _extract_id(existing_all[0])
        except Exception:
            pass

        try:
            new_type = self.call("PlanType.create", {"name": name, "description": f"Tipo {name}"})
            return _extract_id(new_type)
        except Exception as e:
            logger.warning(f"No se pudo crear tipo de plan '{name}': {e}")
            try:
                existing_all = self.call("PlanType.filter", {})
                if existing_all:
                    return _extract_id(existing_all[0])
            except Exception:
                pass
            return 1

    def resolve_priority(self, priority_value: Any = 1) -> int:
        """Resuelve el ID de prioridad adecuado (P1=1, P2=2, etc.)."""
        try:
            priorities = self.call("Priority.filter", {})
            if priorities:
                # 1. Si es entero, comparar contra 'id'
                try:
                    p_int = int(priority_value)
                    for p in priorities:
                        if _extract_id(p) == p_int:
                            return _extract_id(p)
                    # Índice 1-based (1 -> priorities[0])
                    idx = p_int - 1
                    if 0 <= idx < len(priorities):
                        return _extract_id(priorities[idx])
                except (ValueError, TypeError):
                    pass

                # 2. Si es string, comparar contra 'value' o 'name'
                val_str = str(priority_value).strip().lower()
                for p in priorities:
                    if str(p.get("value", "")).lower() == val_str or str(p.get("name", "")).lower() == val_str:
                        return _extract_id(p)
                return _extract_id(priorities[0])
        except Exception as e:
            logger.warning(f"Error resolviendo prioridad: {e}")
        return 1

    def resolve_case_status(self, status_name: str = "CONFIRMED") -> int:
        """Resuelve el ID del estado de caso (CONFIRMED, PROPOSED, etc.)."""
        name = (status_name or "CONFIRMED").strip().upper()
        try:
            statuses = self.call("TestCaseStatus.filter", {"name": name})
            if statuses:
                return _extract_id(statuses[0])
            statuses_all = self.call("TestCaseStatus.filter", {})
            if statuses_all:
                for s in statuses_all:
                    if str(s.get("name", "")).upper() == name:
                        return _extract_id(s)
                return _extract_id(statuses_all[0])
        except Exception as e:
            logger.warning(f"Error resolviendo case_status: {e}")
        return 2

    def resolve_severity(self, severity_name: str = "medium") -> int:
        """Resuelve la severidad de un defecto."""
        sev_str = str(severity_name or "medium").strip().lower()
        try:
            severities = self.call("Severity.filter", {})
            if severities:
                for s in severities:
                    if str(s.get("name", "")).lower() == sev_str or str(s.get("value", "")).lower() == sev_str:
                        return _extract_id(s)
                return _extract_id(severities[0])
        except Exception as e:
            logger.warning(f"Error resolviendo severidad: {e}")
        return 1

    def resolve_current_user_id(self, username: str = "admin") -> int:
        """Obtiene el ID numérico del usuario actual en Kiwi TCMS."""
        try:
            users = self.call("User.filter", {"username": username})
            if users:
                return _extract_id(users[0])
            users_all = self.call("User.filter", {})
            if users_all:
                return _extract_id(users_all[0])
        except Exception as e:
            logger.warning(f"Error resolviendo usuario actual: {e}")
        return 1
