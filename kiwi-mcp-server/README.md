# Kiwi TCMS MCP Server (Model Context Protocol)

Servidor centralizado **MCP (Model Context Protocol)** con transporte **Streamable HTTP / SSE** para automatizar el ciclo total de aseguramiento de calidad (QA) en **Kiwi TCMS**.

Permite que cualquier asistente de IA (Antigravity, Claude Desktop, Cursor, etc.) interactúe de forma nativa con Kiwi TCMS con soporte **CRUD completo (Crear, Leer, Editar, Eliminar/Archivar y Desvincular)** sin necesidad de copiar scripts de Python ni archivos `.env` en los repositorios de cada proyecto.

---

## 🏗️ Arquitectura Centralizada

```
Repositorio del Proyecto (Cero dependencias locales, Cero scripts QA)
     │
     ▼ (Instrucción en lenguaje natural: "Crea un caso de prueba para el login")
Agente IA (Antigravity / Claude / Cursor)
     │
     ▼ (MCP sobre Streamable HTTP: http://kiwi.cirrus-it.net:8000/mcp o http://localhost:8000/mcp)
[Servidor MCP Kiwi (Docker)] : Puerto 8000
     │
     ▼ (JSON-RPC 2.0 interno con Cookies & SSL Bypass)
[Kiwi TCMS (Docker)] : Puerto 8080/8443
```

---

## 🚀 Despliegue con Docker Compose

```bash
# Reconstruir y levantar sin caché
docker compose build --no-cache
docker compose up -d

# Verificar logs
docker logs -f kiwi-mcp-server
```

El log confirmará:
```
[INFO] Iniciando Kiwi TCMS MCP Server en modo 'streamable-http' en 0.0.0.0:8000
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## 🔌 Conexión desde los Clientes IA

En `.agents/mcp_config.json` o en `~/.gemini/config/mcp_config.json`:

```json
{
  "mcpServers": {
    "kiwi-tcms": {
      "serverUrl": "http://localhost:8000/mcp"
    }
  }
}
```
*(Para producción remota: cambiar por `http://kiwi.cirrus-it.net:8000/mcp`)*.

---

## 🛠️ Suite Completa de Herramientas MCP Nativas (CRUD Total)

### 📋 1. Gestión de Planes de Prueba (Test Plans)
- **`kiwi_create_test_plan`**: Crea un Plan de Pruebas formal agrupando una suite de casos.
  > ⚠️ *Regla:* Solo debe usarse cuando el usuario pida EXPLÍCITAMENTE un "Plan de Pruebas" o "Test Plan".
- **`kiwi_list_test_plans`**: Lista los planes de prueba registrados (filtro opcional por producto).
- **`kiwi_get_test_plan`**: Obtiene el detalle completo de un plan y la lista de todos sus casos asociados.
- **`kiwi_update_test_plan`**: Actualiza el nombre, texto, estado activo/inactivo (`is_active`) o tipo de plan.
- **`kiwi_delete_test_plan`**: Archiva / desactiva un Plan de Pruebas (`is_active=False`). Preserva el historial de auditoría de QA.
- **`kiwi_add_cases_to_plan`**: Asocia casos de prueba a un plan existente.
- **`kiwi_remove_case_from_plan`**: Desvincula un caso de prueba de un plan sin eliminarlo de la base de datos.

### 🧪 2. Gestión de Casos de Prueba (Test Cases)
- **`kiwi_create_test_case`**: Crea un **único caso puntual** y opcionalmente lo asocia a un plan o adjunta imágenes.
  > ⚠️ *Regla:* Usa esta herramienta cuando el usuario pida un test case. ¡NUNCA crea un Test Plan si el usuario solo pidió un test case!
- **`kiwi_list_test_cases`**: Lista casos de prueba (filtro por producto o por ID de plan).
- **`kiwi_get_test_case`**: Obtiene el detalle exhaustivo de un caso (precondiciones, pasos, resultado esperado).
- **`kiwi_update_test_case`**: Actualiza el título, pasos (texto), prioridad, categoría funcional o estado de un caso.
- **`kiwi_delete_test_case`**: Elimina permanentemente un caso de prueba de la base de datos.

### 📎 3. Gestión de Adjuntos y Evidencias Visuales (Attachments)
- **`kiwi_add_attachment`**: Adjunta imágenes (capturas de pantalla, mockups, evidencias de error en Base64) a un TestCase, TestPlan o Bug.
- **`kiwi_list_attachments`**: Lista los archivos e imágenes adjuntos de un caso de prueba.
- **`kiwi_delete_attachment`**: Elimina una imagen o archivo adjunto por su ID.

### 🐛 4. Gestión de Defectos (Bugs)
- **`kiwi_list_bugs`**: Lista los defectos registrados (filtro opcional por producto).
- **`kiwi_report_bug`**: Reporta un bug puntual con pasos de reproducción, build, severidad y adjuntos opcionales.
- **`kiwi_delete_bug`**: Elimina un defecto registrado en Kiwi TCMS.

### 🚀 5. Gestión de Corridas de Prueba (Test Runs)
- **`kiwi_list_test_runs`**: Lista el historial de corridas de prueba registradas.
- **`kiwi_execute_test_run`**: Ejecuta una corrida de pruebas (*solo bajo petición explícita*), actualiza estados (`PASSED` / `FAILED`) y genera automáticamente los Bugs vinculados para los casos que fallaron.
- **`kiwi_delete_test_run`**: Elimina una corrida de prueba.
- **`kiwi_remove_case_from_run`**: Desvincula un caso de una corrida de prueba.

### 🏷️ 6. Entidades Maestras y Administración
*(En Kiwi TCMS JSON-RPC, estas entidades se crean y consultan vía API; su edición o borrado estructural se gestiona desde el panel web `/admin/` para proteger la integridad relacional histórica)*:
- **`kiwi_list_classifications`** / **`kiwi_create_classification`**
- **`kiwi_list_products`** / **`kiwi_create_product`**
- **`kiwi_list_categories`** / **`kiwi_create_category`**
- **`kiwi_list_plan_types`** / **`kiwi_create_plan_type`**
- **`kiwi_list_versions`** / **`kiwi_create_version`**

---

## 🔒 Reglas Críticas para Agentes IA

1. **Distinción Estricta Test Case vs Test Plan**:
   - Si el usuario pide un caso de prueba puntual: usar `kiwi_create_test_case`. **PROHIBIDO** crear un Test Plan.
   - Si el usuario pide un plan formal: usar `kiwi_create_test_plan`.
2. **Prohibido inventar pasos o controles**:
   - Analizar siempre el código fuente real (.vue, .ts, endpoints) o las capturas de pantalla suministradas antes de redactar pruebas.
3. **Resiliencia Total en Kiwi Vacío**:
   - Clasificaciones, categorías, versiones y tipos de plan se resuelven o crean automáticamente sobre la marcha sin arrojar errores de integridad referencial.
