import os
import base64
import logging
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP
from kiwi_client import KiwiClient

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("kiwi-mcp-server")

# Variables de Configuración
KIWI_URL = os.environ.get("KIWI_URL", "https://localhost")
KIWI_USER = os.environ.get("KIWI_USER", "admin")
KIWI_PASSWORD = os.environ.get("KIWI_PASSWORD", "")
KIWI_HOST_HEADER = os.environ.get("KIWI_HOST_HEADER", "")
KIWI_PUBLIC_URL = (os.environ.get("KIWI_PUBLIC_URL") or KIWI_URL).rstrip("/")
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "8000"))
MCP_TRANSPORT = os.environ.get("MCP_TRANSPORT", "streamable-http").lower()

# ==============================================================================
# INSTRUCCIONES Y REGLAS ESTRICTAS DEL SERVIDOR MCP PARA EL AGENTE IA
# ==============================================================================
MCP_INSTRUCTIONS = """
Servidor MCP para automatizar el ciclo de QA en Kiwi TCMS.
Cualquier Agente IA que consuma estas herramientas DEBE obedecer estrictamente las siguientes directrices:

1. REGLA DE ORO: PROHIBIDO INVENTAR PASOS O CONTROLES (ANÁLISIS OBLIGATORIO DE CÓDIGO O CAPTURAS)
   - NUNCA asumas ni inventes botones, controles, modales, herramientas de zoom, rotación o campos de formulario ficticios.
   - Es OBLIGATORIO inspeccionar y leer los archivos de código fuente reales del proyecto (.vue, .ts, .js, router, endpoints, controladores, plantillas) O las capturas de pantalla / mockups suministrados por el usuario antes de redactar los casos de prueba.
   - Cada paso del caso de prueba debe reflejar con exactitud milimétrica la interacción real del usuario con los elementos del código o de la pantalla (nombres exactos de botones, labels de formularios, flujos de pantalla y respuestas esperadas de la API).
   - Cuando el usuario proporcione imágenes o pantallas, analízalas minuciosamente para extraer los pasos y adjunta las imágenes a Kiwi TCMS usando 'kiwi_add_attachment' o mediante el parámetro 'attachments' como evidencia visual del caso.

2. DISTINCIÓN ESTRICTA ENTRE CASO DE PRUEBA INDIVIDUAL Y PLAN DE PRUEBAS (¡NO CREAR PLANES INNECESARIOS!):
   - CASO DE PRUEBA INDIVIDUAL (Test Case):
     Si el usuario solicita crear, redactar o registrar uno o varios CASOS DE PRUEBA (ej. "crea un test case para...", "crea un caso de prueba para el login", "agrega una prueba para X", "documenta este caso de prueba"):
     -> USA EXCLUSIVAMENTE 'kiwi_create_test_case'.
     -> ¡ESTÁ ESTRICTAMENTE PROHIBIDO crear un Test Plan ('kiwi_create_test_plan') si el usuario NO lo pidió explícitamente!
     -> Solo asocia el caso a un plan si el usuario te suministra expresamente el 'plan_id'.
   - PLAN DE PRUEBAS (Test Plan con suite de casos):
     -> Usa 'kiwi_create_test_plan' ÚNICAMENTE cuando el usuario pida de forma EXPLÍCITA un "Plan de Pruebas", "Test Plan" o documentar una "suite completa de pruebas para un módulo/versión".
   - CORRIDAS DE PRUEBA (Test Runs):
     -> PROHIBIDO crear corridas (Test Runs) o simular ejecuciones a menos que el usuario use explícitamente palabras como: "ejecuta las pruebas", "corre el test run", "reporta los bugs que fallen".

3. EDICIÓN Y ELIMINACIÓN DE ELEMENTOS (CRUD COMPLETO):
   - Casos de prueba: Se pueden editar con 'kiwi_update_test_case' y eliminar con 'kiwi_delete_test_case'.
   - Planes de prueba: Se pueden actualizar con 'kiwi_update_test_plan', archivar/desactivar con 'kiwi_delete_test_plan' y desvincular casos con 'kiwi_remove_case_from_plan'.
   - Adjuntos: Se pueden eliminar con 'kiwi_delete_attachment'.
   - Defectos: Se pueden eliminar con 'kiwi_delete_bug'.
   - Corridas: Se pueden eliminar con 'kiwi_delete_test_run' y remover casos con 'kiwi_remove_case_from_run'.

4. RESILIENCIA Y GESTIÓN DE CAMPOS DE ADMINISTRACIÓN EN INSTANCIAS LIMPIAS:
   - Este servidor maneja automáticamente instancias de Kiwi TCMS vacías: auto-resuelve o auto-crea Clasificaciones ('General'), Categorías ('--default--'), Tipos de Plan ('Function'), Versiones ('1.0.0') y Prioridades.
   - Si el usuario indica una clasificación específica (ej. 'Finanzas') o categorías personalizadas (ej. 'Autenticación', 'Firma'), usa las herramientas de administración 'kiwi_create_classification' y 'kiwi_create_category', o especifícalas en los parámetros de creación.
"""

# Instanciar el Servidor FastMCP
mcp = FastMCP(
    name="Kiwi TCMS QA Server",
    instructions=MCP_INSTRUCTIONS,
    host=MCP_HOST,
    port=MCP_PORT,
)

# Cliente Kiwi Singleton
_client: Optional[KiwiClient] = None


def get_client() -> KiwiClient:
    global _client
    if _client is None:
        if not KIWI_PASSWORD:
            raise RuntimeError(
                "La variable de entorno KIWI_PASSWORD no está configurada en el servidor MCP."
            )
        _client = KiwiClient(base_url=KIWI_URL, host_header=KIWI_HOST_HEADER or None)
        _client.login(KIWI_USER, KIWI_PASSWORD)
    return _client


# ==============================================================================
# SECCIÓN 1: GESTIÓN DE CLASIFICACIONES (ADMINISTRACIÓN)
# ==============================================================================
@mcp.tool(
    description="Lista todas las Clasificaciones de productos registradas en Kiwi TCMS."
)
def kiwi_list_classifications() -> List[Dict[str, Any]]:
    """
    Retorna la lista de clasificaciones registradas en Kiwi TCMS.
    """
    client = get_client()
    try:
        classifications = client.call("Classification.filter", {})
        return [
            {
                "id": c.get("id") or c.get("pk"),
                "name": c.get("name"),
                "description": c.get("description"),
            }
            for c in classifications
        ]
    except Exception as e:
        logger.warning(f"Error listando clasificaciones: {e}")
        return []


@mcp.tool(
    description=(
        "Crea una nueva Clasificación de productos en Kiwi TCMS o retorna la existente si ya fue creada.\n"
        "Útil para categorizar productos (ej. 'Banca', 'Finanzas', 'Core', 'General')."
    )
)
def kiwi_create_classification(name: str, description: str = "") -> Dict[str, Any]:
    """
    Crea una nueva Clasificación en Kiwi TCMS.

    :param name: Nombre de la clasificación (ej. 'Finanzas', 'Banca Móvil', 'General').
    :param description: Descripción opcional de la clasificación.
    """
    client = get_client()
    class_id = client.resolve_or_create_classification(name)
    return {
        "status": "success",
        "classification_id": class_id,
        "name": name,
    }


# ==============================================================================
# SECCIÓN 2: GESTIÓN DE PRODUCTOS
# ==============================================================================
@mcp.tool(
    description="Lista todos los Productos registrados en Kiwi TCMS."
)
def kiwi_list_products() -> List[Dict[str, Any]]:
    """
    Retorna la lista de productos registrados en Kiwi TCMS.
    """
    client = get_client()
    products = client.call("Product.filter", {})
    return [
        {
            "id": p.get("id") or p.get("pk"),
            "name": p.get("name"),
            "description": p.get("description"),
            "classification": p.get("classification__name"),
        }
        for p in products
    ]


@mcp.tool(
    description=(
        "Crea un nuevo Producto en Kiwi TCMS o asegura su existencia sin errores.\n"
        "Permite especificar una clasificación (ej. 'Finanzas', 'Banca', 'General'). "
        "Si Kiwi TCMS está completamente limpio o sin clasificaciones, se crea automáticamente una clasificación por defecto."
    )
)
def kiwi_create_product(
    name: str,
    description: str = "",
    classification: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Crea un nuevo Producto en Kiwi TCMS.

    :param name: Nombre del producto (ej. 'Bandeja Digital').
    :param description: Descripción opcional del producto.
    :param classification: Clasificación opcional (ej. 'Banca', 'General'). Si no existe, se auto-crea.
    """
    client = get_client()
    prod_id = client.resolve_or_create_product(name, description=description, classification=classification)
    return {
        "status": "success",
        "product_id": prod_id,
        "name": name,
        "classification": classification or "General",
    }


# ==============================================================================
# SECCIÓN 3: GESTIÓN DE CATEGORÍAS (ADMINISTRACIÓN)
# ==============================================================================
@mcp.tool(
    description="Lista las Categorías funcionales asociadas a un Producto en Kiwi TCMS."
)
def kiwi_list_categories(product_name: str) -> List[Dict[str, Any]]:
    """
    Retorna la lista de categorías asociadas a un producto.

    :param product_name: Nombre del producto (ej. 'Bandeja Digital').
    """
    client = get_client()
    prod_id = client.resolve_or_create_product(product_name)
    try:
        categories = client.call("Category.filter", {"product": prod_id})
        return [
            {
                "id": c.get("id") or c.get("pk"),
                "name": c.get("name"),
                "description": c.get("description"),
                "product_id": prod_id,
            }
            for c in categories
        ]
    except Exception as e:
        logger.warning(f"Error listando categorías: {e}")
        return []


@mcp.tool(
    description="Crea una nueva Categoría funcional para un Producto en Kiwi TCMS o retorna la existente."
)
def kiwi_create_category(
    product_name: str,
    name: str,
    description: str = "",
) -> Dict[str, Any]:
    """
    Crea una categoría funcional para un producto.

    :param product_name: Nombre del producto.
    :param name: Nombre de la categoría (ej. 'Autenticación', 'Firma', 'Reportes').
    :param description: Descripción opcional de la categoría.
    """
    client = get_client()
    prod_id = client.resolve_or_create_product(product_name)
    cat_id = client.resolve_or_create_category(prod_id, name)
    return {
        "status": "success",
        "category_id": cat_id,
        "name": name,
        "product_id": prod_id,
        "product_name": product_name,
    }


# ==============================================================================
# SECCIÓN 4: GESTIÓN DE VERSIONES Y TIPOS DE PLAN (ADMINISTRACIÓN)
# ==============================================================================
@mcp.tool(
    description="Lista los Tipos de Plan de Pruebas (Plan Types) registrados en Kiwi TCMS."
)
def kiwi_list_plan_types() -> List[Dict[str, Any]]:
    """
    Retorna los tipos de plan registrados (ej. Function, Integration, Performance).
    """
    client = get_client()
    try:
        pts = client.call("PlanType.filter", {})
        return [
            {
                "id": p.get("id") or p.get("pk"),
                "name": p.get("name"),
                "description": p.get("description"),
            }
            for p in pts
        ]
    except Exception as e:
        logger.warning(f"Error listando tipos de plan: {e}")
        return []


@mcp.tool(
    description="Crea un nuevo Tipo de Plan de Pruebas en Kiwi TCMS o retorna el existente."
)
def kiwi_create_plan_type(name: str, description: str = "") -> Dict[str, Any]:
    """
    Crea o asegura la existencia de un tipo de plan.

    :param name: Nombre del tipo (ej. 'Function', 'Integration', 'Performance', 'Regression').
    :param description: Descripción opcional.
    """
    client = get_client()
    pt_id = client.resolve_or_create_plan_type(name)
    return {
        "status": "success",
        "plan_type_id": pt_id,
        "name": name,
    }


@mcp.tool(
    description="Lista las Versiones registradas para un Producto en Kiwi TCMS."
)
def kiwi_list_versions(product_name: str) -> List[Dict[str, Any]]:
    """
    Retorna las versiones asociadas a un producto.

    :param product_name: Nombre del producto.
    """
    client = get_client()
    prod_id = client.resolve_or_create_product(product_name)
    try:
        versions = client.call("Version.filter", {"product": prod_id})
        return [
            {
                "id": v.get("id") or v.get("pk"),
                "value": v.get("value"),
                "product_id": prod_id,
            }
            for v in versions
        ]
    except Exception as e:
        logger.warning(f"Error listando versiones: {e}")
        return []


@mcp.tool(
    description="Crea una nueva Versión para un Producto en Kiwi TCMS o retorna la existente."
)
def kiwi_create_version(product_name: str, value: str) -> Dict[str, Any]:
    """
    Crea o asegura una versión para un producto.

    :param product_name: Nombre del producto.
    :param value: Cadena de versión (ej. '1.0.0', '2.1.0-beta').
    """
    client = get_client()
    prod_id = client.resolve_or_create_product(product_name)
    ver_id = client.resolve_or_create_version(prod_id, value)
    return {
        "status": "success",
        "version_id": ver_id,
        "value": value,
        "product_id": prod_id,
    }


# ==============================================================================
# SECCIÓN 5: GESTIÓN DE PLANES DE PRUEBA (TEST PLANS)
# ==============================================================================
@mcp.tool(
    description=(
        "Crea un Plan de Pruebas formal (Test Plan) en Kiwi TCMS agrupando una suite de Casos de Prueba.\n\n"
        "REGLAS CRÍTICAS OBLIGATORIAS:\n"
        "1. USO EXCLUSIVO: USA ESTA HERRAMIENTA ÚNICAMENTE cuando el usuario solicite explícitamente un 'Plan de Pruebas', "
        "'Test Plan' o 'Suite de pruebas'. Si el usuario solo pide un Caso de Prueba puntual ('test case'), "
        "NO USES esta herramienta; usa obligatoriamente 'kiwi_create_test_case'.\n"
        "2. PROHIBIDO INVENTAR PASOS: Inspecciona el código fuente real (.vue, .ts, endpoints) o capturas suministradas antes de redactar los casos.\n"
        "3. SOLO REGISTRO: Registra el Plan y los Casos en estado CONFIRMED. NUNCA genera corridas ni simula ejecuciones."
    )
)
def kiwi_create_test_plan(
    product_name: str,
    version: str,
    plan_name: str,
    description: str,
    classification: Optional[str] = None,
    plan_type: str = "Function",
    test_cases: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Registra un Plan de Pruebas y opcionalmente su suite de Casos de Prueba.

    :param product_name: Nombre del producto (ej. 'Bandeja Digital').
    :param version: Versión del producto (ej. '2.0.0').
    :param plan_name: Título formal del Plan de Pruebas.
    :param description: Descripción del alcance funcional y objetivos del plan.
    :param classification: Clasificación opcional del producto (ej. 'Finanzas', 'General').
    :param plan_type: Tipo de plan (default: 'Function').
    :param test_cases: Lista opcional de casos de prueba. Cada caso puede tener:
        - 'summary': Título descriptivo (ej. '[AUTH-01] Login exitoso').
        - 'text': Markdown con Precondiciones, Pasos exactos y Resultado Esperado.
        - 'priority': Número del 1 al 4 o valor P1-P4.
        - 'category': Categoría funcional opcional (ej. 'Autenticación y Sesión').
        - 'attachments': Lista opcional de adjuntos [{'filename': '...', 'content_base64': '...'}].
    """
    client = get_client()

    # 1. Resolver Producto y Versión
    product_id = client.resolve_or_create_product(product_name, classification=classification)
    version_id = client.resolve_or_create_version(product_id, version)

    # 2. Resolver Tipo de Plan
    type_id = client.resolve_or_create_plan_type(plan_type)

    # 3. Crear Test Plan
    plan_payload = {
        "name": plan_name,
        "product": product_id,
        "product_version": version_id,
        "type": type_id,
        "text": description or f"Plan de pruebas para {plan_name}",
    }
    plan = client.call("TestPlan.create", plan_payload)
    plan_id = plan.get("id") or plan.get("pk") or int(plan)
    plan_url = f"{KIWI_PUBLIC_URL}/plan/{plan_id}/"

    # 4. Resolver estado CONFIRMED
    case_status_id = client.resolve_case_status("CONFIRMED")

    # 5. Crear cada Caso de Prueba y asociarlo al Plan (si se suministraron)
    created_cases = []
    category_cache = {}
    cases_to_process = test_cases or []

    for tc in cases_to_process:
        summary = tc.get("summary", "Caso sin título")
        text = tc.get("text", "")
        raw_prio = tc.get("priority", 1)
        priority_id = client.resolve_priority(raw_prio)
        cat_name = tc.get("category", "--default--")

        if cat_name in category_cache:
            category_id = category_cache[cat_name]
        else:
            category_id = client.resolve_or_create_category(product_id, cat_name)
            category_cache[cat_name] = category_id

        case_payload = {
            "product": product_id,
            "category": category_id,
            "priority": priority_id,
            "summary": summary,
            "text": text,
            "case_status": case_status_id,
        }
        case_obj = client.call("TestCase.create", case_payload)
        case_id = case_obj.get("id") or case_obj.get("pk") or int(case_obj)

        # Vincular caso al plan
        try:
            client.call("TestPlan.add_case", plan_id, case_id)
        except Exception as e:
            logger.warning(f"Error vinculando caso #{case_id} al plan #{plan_id}: {e}")

        # Adjuntar imágenes si fueron suministradas para este caso
        attached_files = []
        if tc.get("attachments"):
            for att in tc["attachments"]:
                fname = att.get("filename", "captura.png")
                b64 = att.get("content_base64", "")
                if "," in b64 and b64.startswith("data:"):
                    b64 = b64.split(",", 1)[1]
                if b64:
                    try:
                        client.call("TestCase.add_attachment", case_id, fname, b64)
                        attached_files.append(fname)
                    except Exception as e:
                        logger.warning(f"No se pudo adjuntar {fname} al caso #{case_id}: {e}")

        created_cases.append({
            "id": case_id,
            "summary": summary,
            "category": cat_name,
            "priority": priority_id,
            "attached_files": attached_files,
            "url": f"{KIWI_PUBLIC_URL}/case/{case_id}/",
        })

    logger.info(f"Plan #{plan_id} creado con {len(created_cases)} casos asociados.")

    return {
        "status": "success",
        "message": f"Plan de Pruebas #{plan_id} creado exitosamente con {len(created_cases)} casos.",
        "test_plan": {
            "id": plan_id,
            "name": plan_name,
            "product": product_name,
            "version": version,
            "url": plan_url,
        },
        "total_cases_created": len(created_cases),
        "test_cases": created_cases,
    }


@mcp.tool(
    description="Lista los Planes de Prueba registrados en Kiwi TCMS, opcionalmente filtrados por producto."
)
def kiwi_list_test_plans(product_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retorna la lista de planes existentes en Kiwi TCMS.

    :param product_name: Filtro opcional por nombre exacto o parcial del producto.
    """
    client = get_client()
    query = {}
    if product_name:
        query["product__name__icontains"] = product_name

    plans = client.call("TestPlan.filter", query)
    result = []
    for p in plans:
        p_id = p.get("id") or p.get("pk")
        result.append({
            "id": p_id,
            "name": p.get("name"),
            "product": p.get("product__name"),
            "is_active": p.get("is_active", True),
            "url": f"{KIWI_PUBLIC_URL}/plan/{p_id}/",
        })
    return result


@mcp.tool(
    description="Obtiene el detalle completo de un Plan de Pruebas (nombre, objetivos) y todos los Casos de Prueba asociados."
)
def kiwi_get_test_plan(plan_id: int) -> Dict[str, Any]:
    """
    Retorna el detalle completo de un Plan de Pruebas y sus casos.

    :param plan_id: Identificador numérico del Plan de Pruebas.
    """
    client = get_client()
    plans = client.call("TestPlan.filter", {"id": plan_id})
    if not plans:
        raise ValueError(f"No se encontró el Plan de Pruebas #{plan_id}")
    p = plans[0]

    cases = client.call("TestCase.filter", {"plan": plan_id})
    case_list = [
        {
            "id": c.get("id") or c.get("pk"),
            "summary": c.get("summary"),
            "category": c.get("category__name"),
            "priority": c.get("priority__value"),
            "status": c.get("case_status__name"),
            "url": f"{KIWI_PUBLIC_URL}/case/{c.get('id') or c.get('pk')}/",
        }
        for c in cases
    ]

    return {
        "id": plan_id,
        "name": p.get("name"),
        "text": p.get("text"),
        "product": p.get("product__name"),
        "version": p.get("product_version__value"),
        "is_active": p.get("is_active", True),
        "url": f"{KIWI_PUBLIC_URL}/plan/{plan_id}/",
        "total_cases": len(case_list),
        "cases": case_list,
    }


@mcp.tool(
    description="Actualiza el nombre, texto, estado activo (is_active) o tipo de un Plan de Pruebas en Kiwi TCMS."
)
def kiwi_update_test_plan(
    plan_id: int,
    name: Optional[str] = None,
    text: Optional[str] = None,
    is_active: Optional[bool] = None,
    plan_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Actualiza campos específicos de un Plan de Pruebas.

    :param plan_id: ID numérico del plan.
    :param name: Nuevo nombre del plan (opcional).
    :param text: Nueva descripción / objetivos del plan (opcional).
    :param is_active: Estado activo o archivado (True/False, opcional).
    :param plan_type: Nuevo tipo de plan (ej. 'Function', 'Integration', opcional).
    """
    client = get_client()
    update_data = {}
    if name is not None:
        update_data["name"] = name
    if text is not None:
        update_data["text"] = text
    if is_active is not None:
        update_data["is_active"] = is_active
    if plan_type is not None:
        update_data["type"] = client.resolve_or_create_plan_type(plan_type)

    if not update_data:
        return {"status": "noop", "message": "No se enviaron campos para actualizar."}

    client.call("TestPlan.update", plan_id, update_data)
    return {
        "status": "success",
        "plan_id": plan_id,
        "updated_fields": list(update_data.keys()),
        "url": f"{KIWI_PUBLIC_URL}/plan/{plan_id}/",
    }


@mcp.tool(
    description=(
        "Desactiva o archiva un Plan de Pruebas en Kiwi TCMS (is_active=False).\n"
        "En Kiwi TCMS los planes no se eliminan físicamente para preservar el historial "
        "de ejecuciones y auditoría de QA, sino que se archivan/desactivan."
    )
)
def kiwi_delete_test_plan(plan_id: int) -> Dict[str, Any]:
    """
    Archiva / desactiva un Plan de Pruebas en Kiwi TCMS.

    :param plan_id: ID numérico del plan a desactivar.
    """
    client = get_client()
    client.call("TestPlan.update", plan_id, {"is_active": False})
    return {
        "status": "success",
        "message": f"Plan de Pruebas #{plan_id} archivado/desactivado exitosamente.",
        "plan_id": plan_id,
        "is_active": False,
        "url": f"{KIWI_PUBLIC_URL}/plan/{plan_id}/",
    }


@mcp.tool(
    description="Asocia uno o más Casos de Prueba existentes a un Plan de Pruebas en Kiwi TCMS."
)
def kiwi_add_cases_to_plan(plan_id: int, case_ids: List[int]) -> Dict[str, Any]:
    """
    Agrega casos de prueba a un plan existente.

    :param plan_id: ID del Plan de Pruebas.
    :param case_ids: Lista de IDs de los casos de prueba a asociar (ej. [89, 90, 91]).
    """
    client = get_client()
    added = []
    for cid in case_ids:
        try:
            client.call("TestPlan.add_case", plan_id, cid)
            added.append(cid)
        except Exception as e:
            logger.warning(f"Error asociando caso #{cid} al plan #{plan_id}: {e}")

    return {
        "status": "success",
        "plan_id": plan_id,
        "cases_added": added,
        "total_added": len(added),
    }


@mcp.tool(
    description="Desvincula un Caso de Prueba de un Plan de Pruebas en Kiwi TCMS (sin eliminar el caso de la base de datos)."
)
def kiwi_remove_case_from_plan(plan_id: int, case_id: int) -> Dict[str, Any]:
    """
    Desvincula un caso de un plan.

    :param plan_id: ID del Plan de Pruebas.
    :param case_id: ID del Caso de Prueba a desvincular.
    """
    client = get_client()
    client.call("TestPlan.remove_case", plan_id, case_id)
    return {
        "status": "success",
        "message": f"Caso de prueba #{case_id} desvinculado del Plan #{plan_id}.",
        "plan_id": plan_id,
        "case_id": case_id,
    }


# ==============================================================================
# SECCIÓN 6: GESTIÓN DE CASOS DE PRUEBA (TEST CASES)
# ==============================================================================
@mcp.tool(
    description=(
        "Lista los Casos de Prueba registrados en Kiwi TCMS. "
        "Permite filtrar por nombre de producto o por ID de plan de pruebas."
    )
)
def kiwi_list_test_cases(
    product_name: Optional[str] = None,
    plan_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Retorna los casos de prueba registrados en Kiwi TCMS.

    :param product_name: Filtro opcional por nombre de producto (ej. 'Bandeja Digital').
    :param plan_id: Filtro opcional por ID numérico de plan de pruebas (ej. 13).
    """
    client = get_client()
    query = {}
    if plan_id:
        query["plan"] = plan_id
    elif product_name:
        query["category__product__name__icontains"] = product_name

    cases = client.call("TestCase.filter", query)
    result = []
    for c in cases:
        c_id = c.get("id") or c.get("pk")
        result.append({
            "id": c_id,
            "summary": c.get("summary"),
            "category": c.get("category__name"),
            "priority": c.get("priority__value"),
            "status": c.get("case_status__name"),
            "url": f"{KIWI_PUBLIC_URL}/case/{c_id}/",
        })
    return result


@mcp.tool(
    description="Obtiene el detalle completo de un Caso de Prueba en Kiwi TCMS (precondiciones, pasos y resultado esperado)."
)
def kiwi_get_test_case(case_id: int) -> Dict[str, Any]:
    """
    Retorna el texto y detalle completo de un caso de prueba específico.

    :param case_id: Identificador numérico del caso de prueba (ej. 89).
    """
    client = get_client()
    cases = client.call("TestCase.filter", {"id": case_id})
    if not cases:
        raise ValueError(f"No se encontró el caso de prueba #{case_id}")
    c = cases[0]
    return {
        "id": case_id,
        "summary": c.get("summary"),
        "text": c.get("text"),
        "category": c.get("category__name"),
        "priority": c.get("priority__value"),
        "status": c.get("case_status__name"),
        "url": f"{KIWI_PUBLIC_URL}/case/{case_id}/",
    }


@mcp.tool(
    description=(
        "Crea un ÚNICO Caso de Prueba (Test Case) puntual en Kiwi TCMS.\n\n"
        "REGLA CRÍTICA:\n"
        "1. USA ESTA HERRAMIENTA SIEMPRE que el usuario pida crear, generar o documentar "
        "uno o varios casos de prueba individuales (ej. 'crea un test case para login', 'agrega un caso de prueba para el flujo X').\n"
        "2. ¡ESTÁ TOTALMENTE PROHIBIDO crear un Plan de Pruebas (Test Plan) si el usuario solo pidió un Caso de Prueba!\n"
        "3. Si el usuario te proporciona un plan_id existente, puedes asociarlo directamente.\n"
        "4. Permite adjuntar imágenes o capturas de pantalla (attachments en Base64) como evidencia visual."
    )
)
def kiwi_create_test_case(
    product_name: str,
    summary: str,
    text: str,
    category: Optional[str] = None,
    priority: int = 1,
    plan_id: Optional[int] = None,
    classification: Optional[str] = None,
    attachments: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Crea un caso de prueba individual y opcionalmente lo vincula a un plan y adjunta imágenes.

    :param product_name: Nombre del producto (ej. 'Bandeja Digital').
    :param summary: Título conciso del caso de prueba (ej. '[AUTH-01] Inicio de sesión exitoso').
    :param text: Precondiciones, Pasos y Resultado Esperado en Markdown.
    :param category: Categoría funcional (ej. 'Autenticación', 'Firma').
    :param priority: Prioridad (1=P1, 2=P2, 3=P3, 4=P4). Default: 1.
    :param plan_id: ID opcional de un Plan de Pruebas al cual vincularlo de inmediato.
    :param classification: Clasificación opcional del producto si es nuevo.
    :param attachments: Lista opcional de adjuntos. Cada elemento es {'filename': 'captura.png', 'content_base64': '...'}.
    """
    client = get_client()
    product_id = client.resolve_or_create_product(product_name, classification=classification)
    cat_id = client.resolve_or_create_category(product_id, category or "--default--")
    priority_id = client.resolve_priority(priority)
    case_status_id = client.resolve_case_status("CONFIRMED")

    case_payload = {
        "product": product_id,
        "category": cat_id,
        "priority": priority_id,
        "summary": summary,
        "text": text,
        "case_status": case_status_id,
    }
    case_obj = client.call("TestCase.create", case_payload)
    case_id = case_obj.get("id") or case_obj.get("pk") or int(case_obj)

    # Vincular al plan de pruebas SOLO SI el usuario suministró plan_id
    if plan_id:
        try:
            client.call("TestPlan.add_case", plan_id, case_id)
        except Exception as e:
            logger.warning(f"No se pudo vincular caso #{case_id} al plan #{plan_id}: {e}")

    # Subir adjuntos si se suministraron
    attached_files = []
    if attachments:
        for att in attachments:
            fname = att.get("filename", "captura.png")
            b64 = (att.get("content_base64") or att.get("file_path") or "").strip()
            if os.path.isfile(b64):
                try:
                    with open(b64, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("ascii")
                except Exception as e:
                    logger.warning(f"Error leyendo archivo local '{b64}': {e}")
            elif "," in b64 and b64.startswith("data:"):
                b64 = b64.split(",", 1)[1]
            if b64:
                try:
                    client.call("TestCase.add_attachment", case_id, fname, b64)
                    attached_files.append(fname)
                except Exception as e:
                    logger.warning(f"No se pudo adjuntar {fname} al caso #{case_id}: {e}")

    return {
        "status": "success",
        "case_id": case_id,
        "summary": summary,
        "category": category or "--default--",
        "priority": priority_id,
        "plan_id": plan_id,
        "attached_files": attached_files,
        "url": f"{KIWI_PUBLIC_URL}/case/{case_id}/",
    }


@mcp.tool(
    description="Actualiza el título, pasos (texto), prioridad, categoría o estado de un Caso de Prueba existente en Kiwi TCMS."
)
def kiwi_update_test_case(
    case_id: int,
    summary: Optional[str] = None,
    text: Optional[str] = None,
    priority: Optional[int] = None,
    status_id: Optional[int] = None,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Actualiza campos específicos de un caso de prueba.

    :param case_id: ID numérico del caso a modificar.
    :param summary: Nuevo título (opcional).
    :param text: Nuevos pasos / descripción (opcional).
    :param priority: Nueva prioridad (1 a 4, opcional).
    :param status_id: Nuevo ID de estado (1=PROPOSED, 2=CONFIRMED, 4=NEED_UPDATE, opcional).
    :param category: Nueva categoría funcional (opcional).
    """
    client = get_client()
    update_data = {}
    if summary is not None:
        update_data["summary"] = summary
    if text is not None:
        update_data["text"] = text
    if priority is not None:
        update_data["priority"] = client.resolve_priority(priority)
    if status_id is not None:
        update_data["case_status"] = status_id
    if category is not None:
        cases = client.call("TestCase.filter", {"id": case_id})
        if cases:
            prod_id = cases[0].get("product_id") or cases[0].get("product")
            cat_id = client.resolve_or_create_category(prod_id, category)
            update_data["category"] = cat_id

    if not update_data:
        return {"status": "noop", "message": "No se enviaron campos para actualizar."}

    client.call("TestCase.update", case_id, update_data)
    return {
        "status": "success",
        "case_id": case_id,
        "updated_fields": list(update_data.keys()),
        "url": f"{KIWI_PUBLIC_URL}/case/{case_id}/",
    }


@mcp.tool(
    description="Elimina permanentemente un Caso de Prueba de Kiwi TCMS por su ID."
)
def kiwi_delete_test_case(case_id: int) -> Dict[str, Any]:
    """
    Elimina permanentemente un caso de prueba.

    :param case_id: ID numérico del caso de prueba a eliminar.
    """
    client = get_client()
    client.call("TestCase.remove", {"pk__in": [case_id]})
    return {
        "status": "success",
        "message": f"Caso de prueba #{case_id} eliminado exitosamente.",
        "case_id": case_id,
    }


# ==============================================================================
# SECCIÓN 7: GESTIÓN DE ADJUNTOS Y EVIDENCIAS (ATTACHMENTS / IMÁGENES)
# ==============================================================================
@mcp.tool(
    description=(
        "Adjunta una imagen, captura de pantalla o documento (en Base64) a un Caso de Prueba, "
        "Plan de Pruebas o Bug en Kiwi TCMS como evidencia visual."
    )
)
def kiwi_add_attachment(
    target_type: str,
    target_id: int,
    filename: str,
    content_base64: str,
) -> Dict[str, Any]:
    """
    Adjunta un archivo o imagen (Base64) a un Caso de Prueba, Plan o Bug en Kiwi TCMS.

    :param target_type: Tipo de objetivo ('case' para TestCase, 'plan' para TestPlan, 'bug' para Bug).
    :param target_id: ID numérico del caso, plan o bug.
    :param filename: Nombre del archivo con extensión (ej. 'pantalla_login.png', 'evidencia_error.jpg').
    :param content_base64: Contenido del archivo codificado en Base64 o Data URI.
    """
    client = get_client()
    target = target_type.lower().strip()

    if target in ("case", "testcase"):
        method = "TestCase.add_attachment"
        item_url = f"{KIWI_PUBLIC_URL}/case/{target_id}/"
    elif target in ("plan", "testplan"):
        method = "TestPlan.add_attachment"
        item_url = f"{KIWI_PUBLIC_URL}/plan/{target_id}/"
    elif target == "bug":
        method = "Bug.add_attachment"
        item_url = f"{KIWI_PUBLIC_URL}/bugs/{target_id}/"
    else:
        raise ValueError(f"target_type inválido: '{target_type}'. Debe ser 'case', 'plan' o 'bug'.")

    clean_b64 = content_base64.strip()
    if os.path.isfile(clean_b64):
        try:
            with open(clean_b64, "rb") as f:
                clean_b64 = base64.b64encode(f.read()).decode("ascii")
        except Exception as e:
            raise ValueError(f"No se pudo leer el archivo local '{clean_b64}': {e}")
    elif "," in clean_b64 and clean_b64.startswith("data:"):
        clean_b64 = clean_b64.split(",", 1)[1]

    client.call(method, target_id, filename, clean_b64)
    return {
        "status": "success",
        "message": f"Archivo '{filename}' adjuntado exitosamente al {target} #{target_id}.",
        "target_type": target,
        "target_id": target_id,
        "filename": filename,
        "url": item_url,
    }


@mcp.tool(
    description="Lista los archivos adjuntos (imágenes, capturas) asociados a un Caso de Prueba en Kiwi TCMS."
)
def kiwi_list_attachments(case_id: int) -> List[Dict[str, Any]]:
    """
    Lista los adjuntos de un Caso de Prueba.

    :param case_id: ID numérico del caso de prueba.
    """
    client = get_client()
    attachments = client.call("TestCase.list_attachments", case_id)
    return [
        {
            "id": a.get("id") or a.get("pk"),
            "filename": a.get("attachment_file", "").split("/")[-1] or a.get("filename"),
            "url": f"{KIWI_PUBLIC_URL}/{a.get('url', '').lstrip('/')}" if a.get("url") else None,
        }
        for a in attachments
    ]


@mcp.tool(
    description="Elimina un archivo adjunto o imagen de Kiwi TCMS por su ID numérico."
)
def kiwi_delete_attachment(attachment_id: int) -> Dict[str, Any]:
    """
    Elimina un archivo adjunto.

    :param attachment_id: ID numérico del adjunto a eliminar.
    """
    client = get_client()
    client.call("Attachment.remove_attachment", attachment_id)
    return {
        "status": "success",
        "message": f"Adjunto #{attachment_id} eliminado exitosamente.",
        "attachment_id": attachment_id,
    }


# ==============================================================================
# SECCIÓN 8: GESTIÓN DE BUGS (DEFECTOS)
# ==============================================================================
@mcp.tool(
    description="Lista los Bugs registrados en Kiwi TCMS, opcionalmente filtrados por producto."
)
def kiwi_list_bugs(product_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retorna los bugs registrados en Kiwi TCMS.
    """
    client = get_client()
    query = {}
    if product_name:
        query["product__name__icontains"] = product_name

    bugs = client.call("Bug.filter", query)
    result = []
    for b in bugs:
        b_id = b.get("id") or b.get("pk")
        result.append({
            "id": b_id,
            "summary": b.get("summary"),
            "product": b.get("product__name"),
            "severity": b.get("severity__name"),
            "url": f"{KIWI_PUBLIC_URL}/bugs/{b_id}/",
        })
    return result


@mcp.tool(
    description="Registra un Bug o Defecto puntual en Kiwi TCMS y lo asocia al producto y versión."
)
def kiwi_report_bug(
    product_name: str,
    version: str,
    summary: str,
    text: str,
    build: str = "001",
    severity: str = "medium",
    classification: Optional[str] = None,
    attachments: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Crea un nuevo Bug en Kiwi TCMS y opcionalmente adjunta capturas de error.

    :param product_name: Nombre del producto.
    :param version: Versión donde se encontró el defecto.
    :param summary: Título conciso del bug.
    :param text: Descripción detallada: Pasos para reproducir, Comportamiento Actual y Esperado.
    :param build: Identificador del build (default: '001').
    :param severity: Nivel de severidad (default: 'medium').
    :param classification: Clasificación opcional del producto si es nuevo.
    :param attachments: Lista opcional de adjuntos [{'filename': 'error.png', 'content_base64': '...'}].
    """
    client = get_client()
    product_id = client.resolve_or_create_product(product_name, classification=classification)
    version_id = client.resolve_or_create_version(product_id, version)
    build_id = client.resolve_or_create_build(version_id, build)
    severity_id = client.resolve_severity(severity)

    bug_data = {
        "summary": summary,
        "text": text,
        "product": product_id,
        "version": version_id,
        "build": build_id,
        "severity": severity_id,
    }
    bug = client.call("Bug.create", bug_data)
    bug_id = bug.get("id") or bug.get("pk") or int(bug)
    bug_url = f"{KIWI_PUBLIC_URL}/bugs/{bug_id}/"

    attached_files = []
    if attachments:
        for att in attachments:
            fname = att.get("filename", "evidencia_bug.png")
            b64 = att.get("content_base64", "")
            if "," in b64 and b64.startswith("data:"):
                b64 = b64.split(",", 1)[1]
            if b64:
                try:
                    client.call("Bug.add_attachment", bug_id, fname, b64)
                    attached_files.append(fname)
                except Exception as e:
                    logger.warning(f"No se pudo adjuntar {fname} al bug #{bug_id}: {e}")

    return {
        "status": "success",
        "bug_id": bug_id,
        "summary": summary,
        "attached_files": attached_files,
        "url": bug_url,
    }


@mcp.tool(
    description="Elimina un Bug o Defecto registrado en Kiwi TCMS por su ID."
)
def kiwi_delete_bug(bug_id: int) -> Dict[str, Any]:
    """
    Elimina un bug de Kiwi TCMS.

    :param bug_id: ID numérico del bug a eliminar.
    """
    client = get_client()
    client.call("Bug.remove", {"id": bug_id})
    return {
        "status": "success",
        "message": f"Bug #{bug_id} eliminado exitosamente.",
        "bug_id": bug_id,
    }


# ==============================================================================
# SECCIÓN 9: GESTIÓN DE CORRIDAS (TEST RUNS)
# ==============================================================================
@mcp.tool(
    description="Lista las Corridas de Prueba (Test Runs) registradas en Kiwi TCMS, opcionalmente filtradas por ID de plan."
)
def kiwi_list_test_runs(plan_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Retorna las corridas de pruebas registradas.

    :param plan_id: ID opcional de plan de pruebas para filtrar.
    """
    client = get_client()
    query = {}
    if plan_id:
        query["plan"] = plan_id

    runs = client.call("TestRun.filter", query)
    result = []
    for r in runs:
        r_id = r.get("id") or r.get("pk")
        result.append({
            "id": r_id,
            "summary": r.get("summary"),
            "plan_id": r.get("plan"),
            "plan_name": r.get("plan__name"),
            "manager": r.get("manager__username"),
            "start_date": r.get("start_date"),
            "stop_date": r.get("stop_date"),
            "url": f"{KIWI_PUBLIC_URL}/runs/{r_id}/",
        })
    return result


@mcp.tool(
    description=(
        "Crea una Corrida de Pruebas (Test Run), registra las ejecuciones (PASSED / FAILED) "
        "y genera automáticamente los Bugs vinculados para los casos que fallaron.\n"
        "REGLA CRÍTICA: SOLO DEBE USARSE cuando el usuario pida explícitamente ejecutar o correr pruebas."
    )
)
def kiwi_execute_test_run(
    plan_id: int,
    summary: str,
    results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Ejecuta un Test Run y reporta resultados.

    :param plan_id: ID del Plan de Pruebas a ejecutar.
    :param summary: Título o resumen descriptivo de la corrida.
    :param results: Lista de resultados por caso:
        - 'case_id': int (ID del caso)
        - 'status': 'PASSED' o 'FAILED'
        - 'comment': str (observaciones o tiempo de respuesta)
        - 'bug_summary': str (opcional si falla)
        - 'bug_text': str (opcional si falla)
    """
    client = get_client()

    plans = client.call("TestPlan.filter", {"id": plan_id})
    if not plans:
        raise ValueError(f"No se encontró el Test Plan con ID {plan_id}")
    plan = plans[0]

    product_id = plan.get("product_id") or plan.get("product")
    version_id = plan.get("product_version_id") or plan.get("product_version")
    build_id = client.resolve_or_create_build(version_id, "001")
    user_id = client.resolve_current_user_id(KIWI_USER)

    # Crear Test Run
    run_payload = {
        "plan": plan_id,
        "build": build_id,
        "manager": user_id,
        "summary": summary or f"Ejecución: {plan['name']}",
    }
    test_run = client.call("TestRun.create", run_payload)
    run_id = test_run.get("id") or test_run.get("pk") or int(test_run)
    run_url = f"{KIWI_PUBLIC_URL}/runs/{run_id}/"

    STATUS_MAP = {"PASSED": 4, "FAILED": 5, "BLOCKED": 6, "ERROR": 7, "WAIVED": 8}
    executed_cases = []
    generated_bugs = []

    for item in results:
        case_id = item.get("case_id")
        if not case_id:
            continue

        status_str = item.get("status", "PASSED").upper()
        status_code = STATUS_MAP.get(status_str, 4)
        comment = item.get("comment", "")

        executions = client.call("TestRun.add_case", run_id, case_id)
        if not executions:
            continue
        execution_id = executions[0]["id"]

        client.call("TestExecution.update", execution_id, {"status": status_code})
        if comment:
            try:
                client.call("TestExecution.add_comment", execution_id, comment)
            except Exception:
                pass

        case_report = {
            "case_id": case_id,
            "execution_id": execution_id,
            "status": status_str,
            "comment": comment,
        }

        # Crear Bug automático si falló
        if status_code in (5, 7):
            b_sum = item.get("bug_summary") or f"Fallo en [CASE-{case_id}]: {summary}"
            b_txt = item.get("bug_text") or f"Caso CASE-{case_id} falló durante {summary}.\nDetalle: {comment}"
            sev_id = client.resolve_severity("medium")

            bug_obj = client.call("Bug.create", {
                "summary": b_sum,
                "text": b_txt,
                "product": product_id,
                "version": version_id,
                "build": build_id,
                "severity": sev_id,
            })
            b_id = bug_obj.get("id") or bug_obj.get("pk") or int(bug_obj)
            b_url = f"{KIWI_PUBLIC_URL}/bugs/{b_id}/"

            try:
                client.call("Bug.add_execution", b_id, execution_id)
                client.call("TestExecution.add_link", {
                    "execution": execution_id,
                    "url": b_url,
                    "is_defect": True
                })
            except Exception:
                pass

            case_report["bug"] = {"id": b_id, "summary": b_sum, "url": b_url}
            generated_bugs.append(case_report["bug"])

        executed_cases.append(case_report)

    return {
        "status": "success",
        "run_id": run_id,
        "url": run_url,
        "total_passed": sum(1 for c in executed_cases if c["status"] == "PASSED"),
        "total_failed": sum(1 for c in executed_cases if c["status"] in ("FAILED", "ERROR")),
        "bugs_created": generated_bugs,
        "details": executed_cases,
    }


@mcp.tool(
    description="Elimina una Corrida de Pruebas (Test Run) de Kiwi TCMS."
)
def kiwi_delete_test_run(run_id: int) -> Dict[str, Any]:
    """
    Elimina una corrida de pruebas.

    :param run_id: ID numérico del Test Run a eliminar.
    """
    client = get_client()
    client.call("TestRun.remove", {"id": run_id})
    return {
        "status": "success",
        "message": f"Test Run #{run_id} eliminado exitosamente.",
        "run_id": run_id,
    }


@mcp.tool(
    description="Desvincula un Caso de Prueba de una Corrida de Pruebas (Test Run) en Kiwi TCMS."
)
def kiwi_remove_case_from_run(run_id: int, case_id: int) -> Dict[str, Any]:
    """
    Remueve un caso de una corrida de prueba.

    :param run_id: ID del Test Run.
    :param case_id: ID del Caso de Prueba.
    """
    client = get_client()
    client.call("TestRun.remove_case", run_id, case_id)
    return {
        "status": "success",
        "message": f"Caso #{case_id} removido del Test Run #{run_id}.",
        "run_id": run_id,
        "case_id": case_id,
    }


# ==============================================================================
# RECURSO MCP: GUÍA Y REGLAS DE QA
# ==============================================================================
@mcp.resource("qa://rules")
def get_qa_rules() -> str:
    """Retorna las directrices y reglas estrictas de aseguramiento de calidad."""
    return MCP_INSTRUCTIONS


# ==============================================================================
# PUNTO DE ENTRADA
# ==============================================================================
if __name__ == "__main__":
    logger.info(f"Iniciando Kiwi TCMS MCP Server en modo '{MCP_TRANSPORT}' en {MCP_HOST}:{MCP_PORT}")
    if MCP_TRANSPORT == "streamable-http":
        mcp.run(transport="streamable-http")
    elif MCP_TRANSPORT == "sse":
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
