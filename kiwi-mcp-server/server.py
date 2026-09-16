import os
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
MCP_TRANSPORT = os.environ.get("MCP_TRANSPORT", "sse").lower()

# ==============================================================================
# INSTRUCCIONES Y REGLAS ESTRICTAS DEL SERVIDOR MCP
# ==============================================================================
MCP_INSTRUCTIONS = """
Servidor MCP para automatizar el ciclo de QA en Kiwi TCMS.
Cualquier Agente IA que consuma estas herramientas DEBE obedecer estrictamente las siguientes directrices:

1. REGLA DE ORO: PROHIBIDO INVENTAR PASOS O CONTROLES (ANÁLISIS OBLIGATORIO DE CÓDIGO)
   - NUNCA asumas ni inventes botones, controles, modales, herramientas de zoom, rotación o campos de formulario ficticios.
   - Es OBLIGATORIO inspeccionar y leer los archivos de código fuente reales del proyecto (.vue, .ts, .js, router, endpoints, controladores, plantillas) antes de redactar los casos de prueba.
   - Cada paso del caso de prueba debe reflejar con exactitud milimétrica la interacción real del usuario con los elementos del código (nombres exactos de botones, labels de formularios, flujos de pantalla y respuestas esperadas de la API).

2. COMPORTAMIENTO POR DEFECTO: SOLO TEST PLAN Y TEST CASES
   - Cuando se pida crear o documentar pruebas para un módulo, proyecto o versión, USA EXCLUSIVAMENTE la herramienta 'kiwi_create_test_plan'.
   - PROHIBIDO crear corridas (Test Runs) o simular ejecuciones a menos que el usuario use explícitamente palabras como: "ejecuta las pruebas", "corre el test run", "reporta los bugs que fallen".

3. PERSPECTIVA DE USUARIO EN PRODUCCIÓN POR MÓDULOS
   - Los casos de prueba no deben dividirse por capas técnicas (ej. backend vs frontend vs desktop), sino por Módulos Funcionales según la interacción del usuario final en un entorno real de producción (ej. Módulo de Autenticación, Módulo de Firma de Documentos, Módulo de Auditoría).
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
# SECCIÓN 1: GESTIÓN DE PRODUCTOS
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
            "id": p.get("id"),
            "name": p.get("name"),
            "description": p.get("description"),
        }
        for p in products
    ]


@mcp.tool(
    description="Crea un nuevo Producto en Kiwi TCMS o asegura su existencia."
)
def kiwi_create_product(name: str, description: str = "") -> Dict[str, Any]:
    """
    Crea un nuevo Producto en Kiwi TCMS.

    :param name: Nombre del producto (ej. 'Bandeja Digital').
    :param description: Descripción opcional del producto.
    """
    client = get_client()
    prod_id = client.resolve_or_create_product(name)
    if description:
        try:
            client.call("Product.update", prod_id, {"description": description})
        except Exception:
            pass
    return {
        "status": "success",
        "product_id": prod_id,
        "name": name,
    }


# ==============================================================================
# SECCIÓN 2: GESTIÓN DE PLANES DE PRUEBA
# ==============================================================================
@mcp.tool(
    description=(
        "Crea un Plan de Pruebas en Kiwi TCMS (opcionalmente con Casos de Prueba asociados).\n\n"
        "REGLAS CRÍTICAS OBLIGATORIAS:\n"
        "1. PROHIBIDO INVENTAR PASOS: No asumas controles, botones, rotaciones, zooms o campos inexistentes.\n"
        "2. ANÁLISIS DE CÓDIGO OBLIGATORIO: Debes inspeccionar los archivos de código fuente del proyecto (.vue, .ts, router, endpoints) para extraer los nombres de botones, labels y flujos reales antes de redactar los casos.\n"
        "3. SOLO REGISTRO: Esta herramienta SOLO registra el Plan y los Casos en estado CONFIRMED. NUNCA genera corridas ni simula ejecuciones.\n"
        "4. ENFOQUE FUNCIONAL: Organiza los casos según la experiencia del usuario en producción por módulo funcional."
    )
)
def kiwi_create_test_plan(
    product_name: str,
    version: str,
    plan_name: str,
    description: str,
    test_cases: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Registra un Plan de Pruebas y opcionalmente sus Casos de Prueba.

    :param product_name: Nombre del producto (ej. 'Bandeja Digital').
    :param version: Versión del producto (ej. '2.0.0').
    :param plan_name: Título formal del Plan de Pruebas.
    :param description: Descripción del alcance funcional y objetivos del plan.
    :param test_cases: Lista opcional de casos de prueba. Cada caso puede tener:
        - 'summary': Título descriptivo (ej. '[AUTH-01] Login exitoso').
        - 'text': Markdown con Precondiciones, Pasos exactos y Resultado Esperado.
        - 'priority': Número del 1 al 4 (1=Alta/Crítica, 2=Media, 3=Baja).
        - 'category': Categoría funcional opcional (ej. 'Autenticación y Sesión').
    """
    client = get_client()

    # 1. Resolver Producto, Versión y Build
    product_id = client.resolve_or_create_product(product_name)
    version_id = client.resolve_or_create_version(product_id, version)

    # 2. Resolver tipo de plan (Function)
    plan_types = client.call("PlanType.filter", {"name": "Function"})
    if not plan_types:
        plan_types = client.call("PlanType.filter", {})
    type_id = plan_types[0]["id"] if plan_types else 1

    # 3. Crear Test Plan
    plan_payload = {
        "name": plan_name,
        "product": product_id,
        "product_version": version_id,
        "type": type_id,
        "text": description or f"Plan de pruebas para {plan_name}",
    }
    plan = client.call("TestPlan.create", plan_payload)
    plan_id = plan["id"]
    plan_url = f"{KIWI_PUBLIC_URL}/plan/{plan_id}/"

    # 4. Estado CONFIRMED por defecto
    try:
        statuses = client.call("TestCaseStatus.filter", {"name": "CONFIRMED"})
        case_status_id = statuses[0]["id"] if statuses else 2
    except Exception:
        case_status_id = 2

    # 5. Crear cada Caso de Prueba y asociarlo al Plan (si se suministraron)
    created_cases = []
    category_cache = {}
    cases_to_process = test_cases or []

    for tc in cases_to_process:
        summary = tc.get("summary", "Caso sin título")
        text = tc.get("text", "")
        priority_id = tc.get("priority", 1)
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
        case_id = case_obj["id"]

        # Vincular caso al plan
        client.call("TestPlan.add_case", plan_id, case_id)

        created_cases.append({
            "id": case_id,
            "summary": summary,
            "category": cat_name,
            "priority": priority_id,
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


# ==============================================================================
# TOOL 2: LISTAR PLANES DE PRUEBA
# ==============================================================================
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
        result.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "product": p.get("product__name"),
            "is_active": p.get("is_active", True),
            "url": f"{KIWI_PUBLIC_URL}/plan/{p.get('id')}/",
        })
    return result


@mcp.tool(
    description="Obtiene el detalle completo de un Plan de Pruebas (nombre, objetivos) y todos los Casos de Prueba asociados."
)
def kiwi_get_test_plan(plan_id: int) -> Dict[str, Any]:
    """
    Retorna el detalle completo de un Plan de Pruebas y sus casos.

    :param plan_id: Identificador numérico del Plan de Pruebas (ej. 13).
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


# ==============================================================================
# SECCIÓN 3: GESTIÓN DE CASOS DE PRUEBA (TEST CASES)
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
        "Crea un ÚNICO Caso de Prueba específico en Kiwi TCMS y opcionalmente lo asocia a un Plan de Pruebas.\n\n"
        "REGLA ESTRICTA: Los pasos deben corresponder al código fuente real (sin inventar botones o controles)."
    )
)
def kiwi_create_test_case(
    product_name: str,
    summary: str,
    text: str,
    category: Optional[str] = None,
    priority: int = 1,
    plan_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Crea un caso de prueba individual y opcionalmente lo vincula a un plan.

    :param product_name: Nombre del producto (ej. 'Bandeja Digital').
    :param summary: Título conciso del caso de prueba.
    :param text: Precondiciones, Pasos y Resultado Esperado en Markdown.
    :param category: Categoría funcional (ej. 'Autenticación', 'Firma').
    :param priority: Prioridad (1=P1, 2=P2, 3=P3, 4=P4). Default: 1.
    :param plan_id: ID opcional de un Plan de Pruebas al cual vincularlo de inmediato.
    """
    client = get_client()
    product_id = client.resolve_or_create_product(product_name)
    cat_id = client.resolve_or_create_category(product_id, category or "--default--")

    try:
        statuses = client.call("TestCaseStatus.filter", {"name": "CONFIRMED"})
        case_status_id = statuses[0]["id"] if statuses else 2
    except Exception:
        case_status_id = 2

    case_payload = {
        "product": product_id,
        "category": cat_id,
        "priority": priority,
        "summary": summary,
        "text": text,
        "case_status": case_status_id,
    }
    case_obj = client.call("TestCase.create", case_payload)
    case_id = case_obj["id"]

    if plan_id:
        try:
            client.call("TestPlan.add_case", plan_id, case_id)
        except Exception as e:
            logger.warning(f"No se pudo vincular caso #{case_id} al plan #{plan_id}: {e}")

    return {
        "status": "success",
        "case_id": case_id,
        "summary": summary,
        "category": category or "--default--",
        "priority": priority,
        "plan_id": plan_id,
        "url": f"{KIWI_PUBLIC_URL}/case/{case_id}/",
    }


@mcp.tool(
    description="Actualiza el título, pasos (texto), prioridad o estado de un Caso de Prueba existente en Kiwi TCMS."
)
def kiwi_update_test_case(
    case_id: int,
    summary: Optional[str] = None,
    text: Optional[str] = None,
    priority: Optional[int] = None,
    status_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Actualiza campos específicos de un caso de prueba.

    :param case_id: ID numérico del caso a modificar.
    :param summary: Nuevo título (opcional).
    :param text: Nuevos pasos / descripción (opcional).
    :param priority: Nueva prioridad (1 a 4, opcional).
    :param status_id: Nuevo ID de estado (1=PROPOSED, 2=CONFIRMED, 4=NEED_UPDATE, opcional).
    """
    client = get_client()
    update_data = {}
    if summary is not None:
        update_data["summary"] = summary
    if text is not None:
        update_data["text"] = text
    if priority is not None:
        update_data["priority"] = priority
    if status_id is not None:
        update_data["case_status"] = status_id

    if not update_data:
        return {"status": "noop", "message": "No se enviaron campos para actualizar."}

    client.call("TestCase.update", case_id, update_data)
    return {
        "status": "success",
        "case_id": case_id,
        "updated_fields": list(update_data.keys()),
        "url": f"{KIWI_PUBLIC_URL}/case/{case_id}/",
    }


# ==============================================================================
# SECCIÓN 4: GESTIÓN DE BUGS (DEFECTOS)
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
        result.append({
            "id": b.get("id") or b.get("pk"),
            "summary": b.get("summary"),
            "product": b.get("product__name"),
            "severity": b.get("severity__name"),
            "url": f"{KIWI_PUBLIC_URL}/bugs/{b.get('id') or b.get('pk')}/",
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
) -> Dict[str, Any]:
    """
    Crea un nuevo Bug en Kiwi TCMS.

    :param product_name: Nombre del producto.
    :param version: Versión donde se encontró el defecto.
    :param summary: Título conciso del bug.
    :param text: Descripción detallada: Pasos para reproducir, Comportamiento Actual y Esperado.
    :param build: Identificador del build (default: '001').
    """
    client = get_client()
    product_id = client.resolve_or_create_product(product_name)
    version_id = client.resolve_or_create_version(product_id, version)
    build_id = client.resolve_or_create_build(version_id, build)

    severities = client.call("Severity.filter", {})
    severity_id = severities[0]["id"] if severities else 1

    bug_data = {
        "summary": summary,
        "text": text,
        "product": product_id,
        "version": version_id,
        "build": build_id,
        "severity": severity_id,
    }
    bug = client.call("Bug.create", bug_data)
    bug_id = bug.get("id") or bug.get("pk")
    bug_url = f"{KIWI_PUBLIC_URL}/bugs/{bug_id}/"

    return {
        "status": "success",
        "bug_id": bug_id,
        "summary": summary,
        "url": bug_url,
    }


# ==============================================================================
# SECCIÓN 5: GESTIÓN DE CORRIDAS (TEST RUNS)
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
        "y genera automáticamente los Bugs vinculados para los casos que fallaron. "
        "SOLO DEBE USARSE cuando el usuario pida explícitamente ejecutar o correr pruebas."
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

    users = client.call("User.filter", {"username": KIWI_USER})
    user_id = users[0]["id"] if users else 1

    # Crear Test Run
    run_payload = {
        "plan": plan_id,
        "build": build_id,
        "manager": user_id,
        "summary": summary or f"Ejecución: {plan['name']}",
    }
    test_run = client.call("TestRun.create", run_payload)
    run_id = test_run["id"]
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
            severities = client.call("Severity.filter", {})
            sev_id = severities[0]["id"] if severities else 1

            bug_obj = client.call("Bug.create", {
                "summary": b_sum,
                "text": b_txt,
                "product": product_id,
                "version": version_id,
                "build": build_id,
                "severity": sev_id,
            })
            b_id = bug_obj.get("id") or bug_obj.get("pk")
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
    if MCP_TRANSPORT == "sse":
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
