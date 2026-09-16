# Kiwi TCMS MCP Server (Model Context Protocol)

Servidor centralizado **MCP (Model Context Protocol)** con transporte **SSE (Server-Sent Events) / HTTP** para automatizar el aseguramiento de calidad (QA) y la gestión de planes y casos de prueba en **Kiwi TCMS**.

Permite que cualquier asistente de IA (Antigravity, Claude Desktop, Cursor, etc.) interactúe de forma nativa con Kiwi TCMS sin necesidad de copiar scripts de Python ni archivos `.env` en los repositorios de cada proyecto.

---

## 🏗️ Arquitectura

```
Repositorio del Proyecto (Cero scripts de Python, Cero dependencias QA)
     │
     ▼ (Instrucción en lenguaje natural: "Diseña y crea el plan de pruebas para este módulo")
Agente IA (Antigravity / Claude / Cursor)
     │
     ▼ (Protocolo MCP sobre HTTP/SSE)
[Servidor MCP Kiwi (Docker en el Servidor QA)] : Puerto 8000 (/sse)
     │
     ▼ (JSON-RPC 2.0 interno)
[Kiwi TCMS (Docker)] : Puerto 8080/8443
```

---

## 🚀 Despliegue en el Servidor (Docker)

### Opción 1: Con Docker Compose (Recomendado)

Si Kiwi TCMS ya está corriendo en el servidor (en la red Docker `kiwitcms_default`):

1. Clona o copia la carpeta `kiwi-mcp-server` en el servidor:
   ```bash
   cd kiwi-mcp-server
   ```

2. Crea tu archivo de variables `.env`:
   ```bash
   cp .env.example .env
   ```
   Asegúrate de configurar la contraseña de administración de Kiwi:
   ```ini
   KIWI_URL=https://kiwi_web:8443
   KIWI_USER=admin
   KIWI_PASSWORD=tu_password_de_kiwi
   KIWI_HOST_HEADER=localhost
   KIWI_PUBLIC_URL=https://tu-dominio-kiwi.com
   MCP_PORT=8000
   ```

3. Levanta el contenedor:
   ```bash
   docker compose up -d --build
   ```

4. Verifica los logs:
   ```bash
   docker logs -f kiwi-mcp-server
   ```
   Debe mostrar:
   ```
   [INFO] Iniciando Kiwi TCMS MCP Server en modo 'sse' en 0.0.0.0:8000
   ```

---

### Opción 2: Build y Run manual con Docker

```bash
docker build -t kiwi-mcp-server .

docker run -d \
  --name kiwi-mcp-server \
  --restart unless-stopped \
  --network kiwitcms_default \
  -p 8000:8000 \
  -e KIWI_URL=http://kiwi_web:8080 \
  -e KIWI_USER=admin \
  -e KIWI_PASSWORD=tu_password \
  -e MCP_TRANSPORT=sse \
  kiwi-mcp-server
```

---

## 🔌 Conexión desde los Clientes IA

Una vez que el contenedor está corriendo en el servidor (por ejemplo, en `https://mcp-kiwi.tuempresa.com` o `http://IP_SERVIDOR:8000`), los desarrolladores configuran su entorno **una sola vez**.

### 1. En Antigravity / Gemini CLI
En tu archivo de configuración global `~/.gemini/config/mcp_config.json`:

```json
{
  "mcpServers": {
    "kiwi-tcms": {
      "url": "http://IP_SERVIDOR:8000/sse"
    }
  }
}
```

### 2. En Claude Desktop
En `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) o `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "kiwi-tcms": {
      "url": "http://IP_SERVIDOR:8000/sse"
    }
  }
}
```

---

## 🛠️ Herramientas MCP Disponibles (14 Tools Nativas)

El servidor expone una suite completa de 14 herramientas para el ciclo total de QA:

### 📦 Gestión de Productos
1. **`kiwi_list_products`**: Lista todos los productos registrados en Kiwi TCMS.
2. **`kiwi_create_product`**: Crea un nuevo producto (o asegura su existencia) con nombre y descripción.

### 📋 Gestión de Planes de Prueba (Test Plans)
3. **`kiwi_list_test_plans`**: Lista los planes de prueba registrados (filtro opcional por producto).
4. **`kiwi_get_test_plan`**: Obtiene el detalle completo de un plan y la lista de todos sus casos de prueba asociados.
5. **`kiwi_create_test_plan`**: Crea un Plan de Pruebas (con o sin casos iniciales).
6. **`kiwi_add_cases_to_plan`**: Asocia casos de prueba existentes a un plan específico.

### 🧪 Gestión de Casos de Prueba (Test Cases)
7. **`kiwi_list_test_cases`**: Lista casos de prueba (filtro por producto o por ID de plan).
8. **`kiwi_get_test_case`**: Obtiene el detalle exhaustivo de un caso (precondiciones, pasos exactos, resultado esperado).
9. **`kiwi_create_test_case`**: Crea un **único caso puntual** y opcionalmente lo asocia a un plan de pruebas.
10. **`kiwi_update_test_case`**: Actualiza el título, pasos (texto), prioridad o estado de un caso existente.

### 🐛 Gestión de Defectos (Bugs)
11. **`kiwi_list_bugs`**: Lista los defectos registrados (filtro opcional por producto).
12. **`kiwi_report_bug`**: Reporta un bug puntual con pasos de reproducción, resultado esperado y actual.

### 🚀 Gestión de Corridas de Prueba (Test Runs)
13. **`kiwi_list_test_runs`**: Lista el historial de corridas de prueba registradas en Kiwi TCMS.
14. **`kiwi_execute_test_run`**: Ejecuta una corrida de pruebas (*solo bajo petición explícita*), actualiza estados (`PASSED` / `FAILED`) y genera automáticamente los Bugs vinculados para los casos que fallaron.

---

## 🔒 Buenas Prácticas para el Equipo

- **Prohibido inventar controles:** Las IAs deben analizar el código fuente real de los repositorios para documentar los pasos de prueba.
- **Cero archivos residuales:** Ningún repositorio de código fuente debe incluir scripts `kiwi_cli.py` ni credenciales locales. Toda la interacción se realiza por red contra este servidor MCP.
