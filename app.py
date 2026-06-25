# -*- coding: utf-8 -*-
from flask import Flask, render_template_string, request, redirect, url_for, flash
import uuid
import re
import json
import os
from datetime import datetime

try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GOOGLE_LIBS = True
except ImportError:
    HAS_GOOGLE_LIBS = False

app = Flask(__name__)
app.secret_key = "clave_gestor_proyectos_2026"

PROYECTOS_DB = {
    "demo": {
        "id": "demo",
        "nombre": "Proyecto de Infraestructura Vial",
        "descripcion": "Ampliación de carril y modernización de señalética vial.",
        "presupuesto": 250000.0,
        "fecha_inicio": "2024-01-15",
        "fecha_fin_tentativa": "2024-08-30",
        "recursos_pool": [
            {"id": "rp-1", "nombre": "Fondo Mano de Obra: Pavimentación", "tipo": "mano_de_obra", "monto_total": 50000.0, "monto_disponible": 47000.0},
            {"id": "rp-2", "nombre": "Alquiler Estación Total", "tipo": "material", "precio": 450.0, "cantidad_total": 20, "cantidad_disponible": 10},
            {"id": "rp-3", "nombre": "Combustible Diesel (Gals)", "tipo": "material", "precio": 5.5, "cantidad_total": 2000, "cantidad_disponible": 800}
        ],
        "actividades": [
            {
                "id": "act-1",
                "nombre": "Topografía y Nivelación",
                "descripcion": "Estudio de suelos y marcado de límites de vía.",
                "presupuesto_tentativo": 10000.0,
                "estado": "Completada",
                "fecha_inicio": "2024-01-20",
                "fecha_fin": "2024-02-15",
                "recursos": [
                    {"id": "r1", "pool_id": "rp-1", "nombre": "Fondo Mano de Obra: Pavimentación", "tipo": "mano_de_obra", "monto": 3000.0, "fecha_pago": "2024-02-10"},
                    {"id": "r2", "pool_id": "rp-2", "nombre": "Alquiler Estación Total", "tipo": "material", "precio": 450.0, "cantidad": 10}
                ]
            },
            {
                "id": "act-2",
                "nombre": "Remoción de Capa Asfáltica",
                "descripcion": "Demolición de asfalto antiguo mediante fresado.",
                "presupuesto_tentativo": 15000.0,
                "estado": "Iniciada",
                "fecha_inicio": "2024-03-01",
                "fecha_fin": None,
                "recursos": [
                    {"id": "r4", "pool_id": "rp-3", "nombre": "Combustible Diesel (Gals)", "tipo": "material", "precio": 5.5, "cantidad": 1200}
                ]
            },
            {
                "id": "act-3",
                "nombre": "Estudio de Impacto Ambiental",
                "descripcion": "Evaluación de ecosistemas colindantes.",
                "presupuesto_tentativo": 5000.0,
                "estado": "Pendiente",
                "fecha_inicio": None,
                "fecha_fin": None,
                "recursos": []
            }
        ]
    }
}

# Nombre de la hoja de cálculo de Google Drive
SPREADSHEET_NAME = "GestorProyectosDB"

# Variable global de depuración para almacenar el estado exacto de la conexión
LAST_CONNECTION_ERROR = None

def obtener_cliente_sheets():
    """Autentica y devuelve el cliente de Google Sheets si existen las credenciales"""
    global LAST_CONNECTION_ERROR
    if not HAS_GOOGLE_LIBS:
        LAST_CONNECTION_ERROR = "Faltan librerías gspread o google-auth en requirements.txt"
        return None
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        LAST_CONNECTION_ERROR = "Falta configurar la variable GOOGLE_CREDENTIALS en Vercel"
        return None
    try:
        creds_json = creds_json.strip()
        if creds_json.startswith("'") and creds_json.endswith("'"):
            creds_json = creds_json[1:-1]
        elif creds_json.startswith('"') and creds_json.endswith('"'):
            creds_json = creds_json[1:-1]
            
        creds_json = creds_json.replace('\\"', '"')
        info = json.loads(creds_json)
        
        if "private_key" in info:
            info["private_key"] = info["private_key"].replace("\\n", "\n")
            
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)
        
        LAST_CONNECTION_ERROR = None
        return client
    except json.JSONDecodeError as json_err:
        LAST_CONNECTION_ERROR = f"Error en formato JSON: {str(json_err)}"
        return None
    except Exception as e:
        LAST_CONNECTION_ERROR = f"Fallo de conexión: {str(e)}"
        print("Error en autenticacion de Google Sheets:", e)
        return None

def inicializar_hoja_calculo():
    """Busca la hoja de cálculo GestorProyectosDB, si no existe la crea"""
    global LAST_CONNECTION_ERROR
    client = obtener_cliente_sheets()
    if not client:
        return None
    try:
        try:
            sh = client.open(SPREADSHEET_NAME)
        except gspread.SpreadsheetNotFound:
            sh = client.create(SPREADSHEET_NAME)
        
        ws = sh.get_worksheet(0)
        if not ws.row_values(1):
            ws.append_row(["id", "nombre", "presupuesto", "fecha_inicio", "fecha_fin_tentativa", "datos_json"])
        return ws
    except gspread.exceptions.APIError as api_err:
        LAST_CONNECTION_ERROR = f"Error de Google API (¿Compartiste la hoja con el correo de la Cuenta de Servicio?): {str(api_err)}"
        print("Error de permisos/API de Google Sheets:", api_err)
        return None
    except Exception as e:
        LAST_CONNECTION_ERROR = f"Error de inicialización: {str(e)}"
        print("Error al inicializar la hoja de calculo:", e)
        return None

def cargar_proyectos_desde_sheets():
    """Carga y sincroniza todos los proyectos desde Google Sheets"""
    global PROYECTOS_DB
    ws = inicializar_hoja_calculo()
    if not ws:
        return False
    try:
        records = ws.get_all_records()
        nuevos_proyectos = {}
        for r in records:
            p_id = str(r["id"])
            datos_extra = json.loads(r["datos_json"]) if r["datos_json"] else {}
            
            nuevos_proyectos[p_id] = {
                "id": p_id,
                "nombre": r["nombre"],
                "descripcion": datos_extra.get("descripcion", ""),
                "presupuesto": float(r["presupuesto"]),
                "fecha_inicio": r["fecha_inicio"],
                "fecha_fin_tentativa": r["fecha_fin_tentativa"],
                "recursos_pool": datos_extra.get("recursos_pool", []),
                "actividades": datos_extra.get("actividades", [])
            }
        if nuevos_proyectos:
            PROYECTOS_DB = nuevos_proyectos
        return True
    except Exception as e:
        print("Error cargando datos de Google Sheets:", e)
        return False

def guardar_proyecto_en_sheets(p_id, proyecto):
    """Guarda o actualiza un proyecto en Google Sheets"""
    ws = inicializar_hoja_calculo()
    if not ws:
        return False
    try:
        datos_json = json.dumps({
            "descripcion": proyecto["descripcion"],
            "recursos_pool": proyecto["recursos_pool"],
            "actividades": proyecto["actividades"]
        })
        
        celdas = ws.findall(p_id, in_column=1)
        if celdas:
            row_num = celdas[0].row
            ws.update_cell(row_num, 2, proyecto["nombre"])
            ws.update_cell(row_num, 3, float(proyecto["presupuesto"]))
            ws.update_cell(row_num, 4, proyecto["fecha_inicio"])
            ws.update_cell(row_num, 5, proyecto["fecha_fin_tentativa"])
            ws.update_cell(row_num, 6, datos_json)
        else:
            ws.append_row([
                p_id,
                proyecto["nombre"],
                float(proyecto["presupuesto"]),
                proyecto["fecha_inicio"],
                proyecto["fecha_fin_tentativa"],
                datos_json
            ])
        return True
    except Exception as e:
        print("Error guardando proyecto en Sheets:", e)
        return False

def eliminar_proyecto_en_sheets(p_id):
    """Elimina una fila de proyecto en Google Sheets"""
    ws = inicializar_hoja_calculo()
    if not ws:
        return False
    try:
        celdas = ws.findall(p_id, in_column=1)
        if celdas:
            row_num = celdas[0].row
            ws.delete_rows(row_num)
            return True
        return False
    except Exception as e:
        print("Error eliminando proyecto de Sheets:", e)
        return False

def limpiar_nombre_gantt(txt):
    """Limpia acentos y caracteres especiales para evitar errores en Mermaid JS"""
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
        'ñ': 'n', 'Ñ': 'N', ':': ' ', ';': ' ', '"': '', "'": ""
    }
    clean = txt
    for k, v in replacements.items():
        clean = clean.replace(k, v)
    return re.sub(r'[^a-zA-Z0-9\s\-]', '', clean)

def calcular_metricas(proyecto):
    gasto_total = 0.0
    completadas = 0
    iniciadas = 0
    has_gantt_tasks = False
    
    gantt_code = "gantt\ndateFormat YYYY-MM-DD\ntitle Cronograma de Actividades\nsection Actividades Activas\n"
    actividades_calculadas = []
    
    for act in proyecto["actividades"]:
        costo_act = 0.0
        for r in act["recursos"]:
            if r["tipo"] == "mano_de_obra" or r.get("tipo") == "mano_de_obra":
                costo_act += float(r.get("monto", 0.0))
            else:
                costo_act += float(r.get("precio", 0.0)) * float(r.get("cantidad", 0))
                
        gasto_total += costo_act
        
        if act["estado"] == "Completada": 
            completadas += 1
        elif act["estado"] == "Iniciada": 
            iniciadas += 1
        
        if act["estado"] in ["Iniciada", "Completada"] and act["fecha_inicio"]:
            has_gantt_tasks = True
            status_tag = "done" if act["estado"] == "Completada" else "active"
            status_part = f"{status_tag}, "
            f_ini = act["fecha_inicio"]
            nombre_limpio = limpiar_nombre_gantt(act["nombre"])
            
            if act["estado"] == "Completada" and act["fecha_fin"]:
                gantt_code += f"  {nombre_limpio} :{status_part}{f_ini}, {act['fecha_fin']}\n"
            else:
                gantt_code += f"  {nombre_limpio} :{status_part}{f_ini}, 15d\n"

        presupuesto_tentativo = float(act.get("presupuesto_tentativo", 0.0))
        balance = presupuesto_tentativo - costo_act
        cumplimiento_pct = (costo_act / presupuesto_tentativo * 100) if presupuesto_tentativo > 0 else 0
        
        act_calc = act.copy()
        act_calc["subtotal_costo"] = costo_act
        act_calc["balance"] = balance
        act_calc["cumplimiento_pct"] = min(cumplimiento_pct, 100)
        act_calc["cumplimiento_pct_real"] = cumplimiento_pct
        actividades_calculadas.append(act_calc)

    ppto = float(proyecto["presupuesto"])
    return {
        "gasto_total": gasto_total,
        "disponible": ppto - gasto_total,
        "porcentaje_gasto": min((gasto_total / ppto * 100), 100) if ppto > 0 else 0,
        "porcentaje_avance": (completadas / len(proyecto["actividades"]) * 100) if proyecto["actividades"] else 0,
        "conteo": {
            "completas": completadas, 
            "iniciadas": iniciadas, 
            "pendientes": len(proyecto["actividades"]) - completadas - iniciadas
        },
        "gantt_code": gantt_code,
        "has_gantt_tasks": has_gantt_tasks,
        "actividades_calculadas": actividades_calculadas
    }

INDEX_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Gestor de Proyectos</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({ 
            startOnLoad: false, 
            theme: 'neutral',
            gantt: {
                titlePadding: 15,
                barHeight: 25,
                barGap: 5,
                gridLineStartPadding: 25,
                fontSize: 11,
                numberSectionHeaderLines: 1,
                axisFormat: '%Y-%m-%d'
            }
        });
        window.mermaid = mermaid;
    </script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .no-scrollbar::-webkit-scrollbar { display: none; }
        .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
        .mermaid svg { width: 100% !important; max-width: 100% !important; height: auto !important; }
        
        .mermaid rect.task.done,
        .mermaid rect.done,
        .mermaid .taskDone,
        .mermaid .done {
            fill: #10b981 !important;
            stroke: #059669 !important;
            fill-opacity: 0.9 !important;
        }
        .mermaid rect.task.active,
        .mermaid rect.active,
        .mermaid .taskActive,
        .mermaid .active {
            fill: #3b82f6 !important;
            stroke: #1d4ed8 !important;
            fill-opacity: 0.9 !important;
        }
        .mermaid text.taskText {
            fill: #ffffff !important;
            font-family: ui-sans-serif, system-ui, sans-serif !important;
            font-size: 11px !important;
            font-weight: bold !important;
        }
        .mermaid text.taskTextOutside {
            fill: #1e293b !important;
            font-family: ui-sans-serif, system-ui, sans-serif !important;
            font-size: 11px !important;
        }
    </style>
</head>
<body class="bg-slate-100 font-sans text-slate-800 flex flex-col min-h-screen">
    
    <nav class="bg-slate-900 text-white p-4 shadow-xl sticky top-0 z-40">
        <div class="max-w-7xl mx-auto flex justify-between items-center">
            <h1 class="text-sm sm:text-lg md:text-xl font-bold flex items-center gap-2">
                <i class="fa-solid fa-chart-line text-emerald-400"></i>
                <span>Gestor de Proyectos</span>
            </h1>
            
            <div class="flex items-center gap-3">
                {% if sheets_connected %}
                <div class="text-[9px] md:text-xs text-emerald-400 bg-emerald-950/50 px-2.5 py-1 rounded-full border border-emerald-800 flex items-center gap-1 font-semibold">
                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                    <i class="fa-solid fa-table"></i> Google Sheets Activo
                </div>
                {% else %}
                <div class="flex flex-col items-end">
                    <div class="text-[9px] md:text-xs text-amber-400 bg-amber-950/50 px-2.5 py-1 rounded-full border border-amber-800 flex items-center gap-1 font-semibold" title="Configura GOOGLE_CREDENTIALS en Vercel para persistencia real">
                        <span class="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
                        <i class="fa-solid fa-memory"></i> Memoria Local (Temporal)
                    </div>
                    {% if connection_error %}
                    <span class="text-[9px] text-rose-300 font-semibold mt-1 max-w-[200px] text-right truncate block hover:whitespace-normal" title="{{ connection_error }}">
                        ⚠️ {{ connection_error }}
                    </span>
                    {% endif %}
                </div>
                {% endif %}
                <div class="text-[10px] md:text-xs text-slate-400">v2.6 | Móvil</div>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl w-full mx-auto p-4 md:p-6 flex-grow flex flex-col gap-6">
        
        <!-- Notificaciones Flash -->
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="p-4 text-xs md:text-sm rounded-xl flex items-center justify-between {% if category == 'error' %}bg-rose-100 text-rose-800 border border-rose-200{% else %}bg-emerald-100 text-emerald-800 border border-emerald-200{% endif %}">
                        <span class="font-medium">{{ message }}</span>
                        <button onclick="this.parentElement.style.display='none'" class="text-lg font-bold focus:outline-none">&times;</button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <!-- Selector Acordeón de Proyectos -->
        <div class="block lg:hidden bg-white rounded-2xl border shadow-sm overflow-hidden">
            <button onclick="toggleMobileSidebar()" class="w-full p-4 flex justify-between items-center bg-slate-50 font-bold text-sm text-slate-700 hover:bg-slate-100 transition">
                <span class="flex items-center gap-2">
                    <i class="fa-solid fa-folder-open text-indigo-600"></i> 📁 Cambiar / Crear Proyecto
                </span>
                <i id="mobile-sidebar-chevron" class="fa-solid fa-chevron-down text-xs transition-transform duration-200"></i>
            </button>
            <div id="mobile-sidebar-container" class="hidden p-4 border-t space-y-6">
                <div id="mobile-sidebar-target"></div>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
            <!-- Sidebar Proyectos -->
            <aside id="main-sidebar" class="hidden lg:block lg:col-span-1 space-y-6">
                <div id="sidebar-content" class="space-y-6">
                    <div class="bg-white p-5 rounded-2xl shadow-sm border">
                        <h2 class="font-bold mb-3 text-slate-800 text-sm flex items-center gap-2">
                            <i class="fa-solid fa-folder-plus text-indigo-600"></i> Crear Proyecto
                        </h2>
                        <form action="/proyectos" method="POST" class="space-y-3 text-xs">
                            <input type="text" name="nombre" placeholder="Nombre Proyecto" class="w-full p-2.5 border rounded-lg" required>
                            <input type="number" name="presupuesto" placeholder="Presupuesto $" class="w-full p-2.5 border rounded-lg" required>
                            <div class="grid grid-cols-2 gap-2">
                                <div>
                                    <label class="text-[9px] font-bold text-slate-400">INICIO</label>
                                    <input type="date" name="fecha_inicio" class="w-full p-1.5 border rounded" required>
                                </div>
                                <div>
                                    <label class="text-[9px] font-bold text-slate-400">FIN (TENTATIVO)</label>
                                    <input type="date" name="fecha_fin" class="w-full p-1.5 border rounded" required>
                                </div>
                            </div>
                            <button class="w-full bg-indigo-600 hover:bg-indigo-700 text-white py-2 rounded-lg font-bold transition">Crear</button>
                        </form>
                    </div>
                    <div class="space-y-2">
                        <h3 class="text-[10px] font-bold uppercase text-slate-400 tracking-wider px-2">Listado de Proyectos</h3>
                        <div class="space-y-2 max-h-[300px] lg:max-h-none overflow-y-auto pr-1">
                            {% for p_id, p in proyectos.items() %}
                            <a href="/?id={{p_id}}&tab={{ active_tab }}" class="block p-3.5 bg-white border rounded-xl hover:border-indigo-500 transition shadow-sm {% if proyecto and proyecto.id == p_id %}border-indigo-500 bg-indigo-50/30{% endif %}">
                                <div class="font-bold text-slate-700 text-xs md:text-sm">{{p.nombre}}</div>
                                <div class="text-[10px] text-slate-500 mt-1">Límite: {{p.fecha_fin_tentativa}}</div>
                            </a>
                            {% endfor %}
                        </div>
                    </div>
                </div>
            </aside>

            <!-- Contenido Central -->
            <section class="col-span-1 lg:col-span-3 space-y-6">
                {% if not proyecto %}
                    <div class="bg-white p-12 md:p-20 text-center rounded-3xl border-2 border-dashed text-slate-400 shadow-sm">
                        <i class="fa-solid fa-arrow-pointer text-3xl md:text-4xl mb-3"></i>
                        <p class="text-sm md:text-lg font-bold">Selecciona o crea un proyecto para ver el Resumen Gerencial</p>
                    </div>
                {% else %}
                    <!-- Resumen Gerencial Card -->
                    <div class="bg-slate-900 text-white p-5 md:p-8 rounded-3xl shadow-xl relative overflow-hidden">
                        <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
                            <div>
                                <h2 class="text-xl md:text-2xl font-bold leading-tight">{{proyecto.nombre}}</h2>
                                <p class="text-slate-400 text-xs mt-1">Planificado: <span class="text-emerald-400 font-semibold">{{proyecto.fecha_inicio}}</span> al <span class="text-emerald-400 font-semibold">{{proyecto.fecha_fin_tentativa}}</span></p>
                            </div>
                            <div class="flex flex-col sm:flex-row md:flex-col items-stretch sm:items-center md:items-end gap-2 w-full md:w-auto">
                                <div class="bg-slate-800 px-4 py-2 rounded-xl text-left md:text-right flex-grow">
                                    <span class="text-[10px] uppercase text-slate-500 font-bold block">Presupuesto General</span>
                                    <div class="text-lg md:text-xl font-black text-emerald-400">${{"{:,.2f}".format(proyecto.presupuesto)}}</div>
                                </div>
                                <a href="/proyectos/{{proyecto.id}}/eliminar" 
                                   onclick="return confirm('¿Estás seguro de que deseas eliminar este proyecto junto con todas sus actividades y recursos de forma permanente?')" 
                                   class="text-xs font-semibold text-rose-400 hover:text-rose-300 transition flex items-center justify-center gap-1.5 bg-rose-950/40 px-3 py-2 rounded-lg border border-rose-800">
                                    <i class="fa-solid fa-trash-can"></i> Eliminar Proyecto
                                </a>
                            </div>
                        </div>

                        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-5 border-t border-slate-800/80">
                            <div class="bg-slate-800/40 p-3.5 rounded-xl border border-slate-700/60">
                                <div class="text-[10px] text-slate-400 mb-1 font-semibold uppercase">GASTO EJECUTADO</div>
                                <div class="text-base md:text-lg font-bold text-white">${{"{:,.2f}".format(m.gasto_total)}}</div>
                                <div class="w-full bg-slate-700 h-1 rounded-full mt-2 overflow-hidden">
                                    <div class="bg-emerald-500 h-1 rounded-full" style="width: {{m.porcentaje_gasto}}%"></div>
                                </div>
                            </div>
                            <div class="bg-slate-800/40 p-3.5 rounded-xl border border-slate-700/60">
                                <div class="text-[10px] text-slate-400 mb-1 font-semibold uppercase">DISPONIBLE</div>
                                <div class="text-base md:text-lg font-bold {% if m.disponible < 0 %}text-rose-400{% else %}text-emerald-400{% endif %}">
                                    ${{"{:,.2f}".format(m.disponible)}}
                                </div>
                            </div>
                            <div class="bg-slate-800/40 p-3.5 rounded-xl border border-slate-700/60 flex flex-col justify-center">
                                <div class="text-[10px] text-slate-400 mb-1 font-semibold uppercase">AVANCE FÍSICO</div>
                                <div class="text-base md:text-lg font-black text-indigo-400">{{ "{:.1f}%".format(m.porcentaje_avance) }}</div>
                                <div class="text-[9px] text-slate-500 font-bold">({{ m.conteo.completas }} de {{ proyecto.actividades|length }} completadas)</div>
                            </div>
                        </div>
                    </div>

                    <!-- Menú de Pestañas (Tabs) con scroll táctil -->
                    <div class="flex flex-nowrap md:flex-wrap gap-2 border-b border-slate-200 pb-2 overflow-x-auto no-scrollbar scroll-smooth">
                        <button id="tab-btn-resumen" onclick="switchTab('resumen')" class="whitespace-nowrap flex items-center gap-2 px-4 py-2.5 text-xs md:text-sm font-semibold transition rounded-xl">
                            <i class="fa-solid fa-chart-pie"></i> Costos
                        </button>
                        <button id="tab-btn-kanban" onclick="switchTab('kanban')" class="whitespace-nowrap flex items-center gap-2 px-4 py-2.5 text-xs md:text-sm font-semibold transition rounded-xl">
                            <i class="fa-solid fa-table-columns"></i> Kanban
                        </button>
                        <button id="tab-btn-gantt" onclick="switchTab('gantt')" class="whitespace-nowrap flex items-center gap-2 px-4 py-2.5 text-xs md:text-sm font-semibold transition rounded-xl">
                            <i class="fa-solid fa-stream"></i> GANTT
                        </button>
                        <button id="tab-btn-inventario" onclick="switchTab('inventario')" class="whitespace-nowrap flex items-center gap-2 px-4 py-2.5 text-xs md:text-sm font-semibold transition rounded-xl">
                            <i class="fa-solid fa-boxes-stacked"></i> Inventario
                        </button>
                    </div>

                    <!-- PESTAÑA 1: RESUMEN FINANCIERO Y DESGLOSE -->
                    <div id="panel-resumen" class="space-y-6">
                        <div class="space-y-4">
                            <div class="flex flex-col sm:flex-row justify-between items-stretch sm:items-center gap-3">
                                <h3 class="font-bold text-slate-800 text-sm md:text-base flex items-center gap-2">
                                    <i class="fa-solid fa-gears text-indigo-600"></i> Desglose Físico y Costos
                                </h3>
                                <button onclick="document.getElementById('modal-act').style.display='flex'" class="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-xl text-xs font-bold shadow-lg transition">+ Crear Actividad</button>
                            </div>
                            
                            {% if not m.actividades_calculadas %}
                                <div class="bg-white p-12 text-center rounded-2xl border border-dashed text-slate-400">
                                    No hay actividades registradas en este proyecto. Puedes agregarlas desde el Tablero Kanban o usando el botón superior.
                                </div>
                            {% else %}
                                {% for act in m.actividades_calculadas %}
                                <div class="bg-white rounded-2xl border shadow-sm overflow-hidden hover:shadow transition">
                                    <div class="p-4 bg-slate-50 border-b flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                                        <div class="flex-grow w-full">
                                            <div class="flex items-center flex-wrap gap-2">
                                                <span class="text-[9px] font-black uppercase px-2 py-0.5 rounded-full {% if act.estado == 'Completada' %}bg-emerald-100 text-emerald-700{% elif act.estado == 'Iniciada' %}bg-blue-100 text-blue-700{% else %}bg-slate-200 text-slate-600{% endif %}">
                                                    {{act.estado}}
                                                </span>
                                                <span class="text-[10px] font-medium text-slate-500">
                                                    {% if act.fecha_inicio %}
                                                        {{ act.fecha_inicio }} {% if act.fecha_fin %}al {{ act.fecha_fin }}{% endif %}
                                                    {% else %}
                                                        Sin fecha asignada.
                                                    {% endif %}
                                                </span>
                                            </div>
                                            <h4 class="font-bold text-slate-800 text-sm md:text-base mt-1.5">{{act.nombre}}</h4>
                                            {% if act.descripcion %}
                                                <p class="text-xs text-slate-500 mt-1 line-clamp-2">{{ act.descripcion }}</p>
                                            {% endif %}
                                            
                                            <!-- Widget de Cumplimiento Financiero -->
                                            <div class="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-3 pt-2 border-t border-slate-200 text-xs">
                                                <div>
                                                    <span class="text-slate-500 font-semibold block">Presupuesto Estimado:</span>
                                                    <strong class="text-slate-800">${{"{:,.2f}".format(act.presupuesto_tentativo)}}</strong>
                                                </div>
                                                <div>
                                                    <span class="text-slate-500 font-semibold block">Subtotal Asignado (Gasto):</span>
                                                    <strong class="text-slate-950">${{"{:,.2f}".format(act.subtotal_costo)}}</strong>
                                                </div>
                                                <div>
                                                    <span class="text-slate-500 font-semibold block">Cumplimiento:</span>
                                                    {% if act.balance >= 0 %}
                                                        <span class="text-emerald-600 font-bold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 inline-block">Disp: ${{"{:,.2f}".format(act.balance)}}</span>
                                                    {% else %}
                                                        <span class="text-rose-600 font-bold bg-rose-50 px-2 py-0.5 rounded border border-rose-200 inline-block">Exc: ${{"{:,.2f}".format(act.balance|abs)}}</span>
                                                    {% endif %}
                                                </div>
                                            </div>
                                            
                                            <!-- Barra de Progreso del Presupuesto por Actividad -->
                                            <div class="w-full bg-slate-200 h-1 rounded-full mt-2 overflow-hidden">
                                                <div class="h-1 rounded-full {% if act.cumplimiento_pct_real > 100 %}bg-rose-500{% elif act.cumplimiento_pct_real > 85 %}bg-amber-500{% else %}bg-emerald-500{% endif %}" style="width: {{act.cumplimiento_pct}}%"></div>
                                            </div>
                                        </div>
                                        <div class="flex items-center gap-1.5 w-full sm:w-auto justify-end border-t pt-2 sm:border-t-0 sm:pt-0 flex-wrap">
                                            <!-- BOTÓN EDITAR ACTIVIDAD -->
                                            <button onclick="openEditarActividad('{{act.id}}', {{ act.nombre|tojson|safe }}, '{{act.presupuesto_tentativo}}', {{ act.descripcion|tojson|safe }})" class="bg-slate-50 hover:bg-slate-200 border border-slate-300 text-slate-700 p-2 rounded-lg transition flex items-center gap-1 text-[11px] font-bold" title="Editar Detalles de la Actividad">
                                                <i class="fa-solid fa-pen text-sm text-indigo-600"></i> Editar
                                            </button>
                                            
                                            <button onclick="openRecurso('{{act.id}}', '{{act.nombre}}')" class="bg-indigo-50 hover:bg-indigo-100 text-indigo-600 p-2 rounded-lg transition flex items-center gap-1 text-[11px] font-bold" title="Asignar Suministro o Mano de Obra">
                                                <i class="fa-solid fa-plus-circle text-sm"></i> Asignar
                                            </button>
                                            <a href="/actividades/{{proyecto.id}}/{{act.id}}/eliminar?tab=resumen" 
                                               onclick="return confirm('¿Seguro que deseas eliminar esta actividad por completo? Los recursos consumidos retornarán automáticamente al pool.')" 
                                               class="bg-rose-50 hover:bg-rose-100 text-rose-600 p-2 rounded-lg transition" title="Eliminar Actividad">
                                                <i class="fa-solid fa-trash-can text-sm"></i>
                                            </a>
                                        </div>
                                    </div>
                                    <div class="p-0 sm:p-4 overflow-x-auto">
                                        <table class="w-full min-w-[500px] text-xs text-left">
                                            <thead>
                                                <tr class="text-slate-400 border-b font-semibold uppercase px-4 py-2">
                                                    <th class="pb-2 pl-4 sm:pl-0">Recurso / Pago</th>
                                                    <th class="pb-2">Clasificación</th>
                                                    <th class="pb-2 text-right">Cantidad / Desembolso</th>
                                                    <th class="pb-2 text-right">Precio unitario</th>
                                                    <th class="pb-2 text-right">Costo Total</th>
                                                    <th class="pb-2 text-center">Acciones</th>
                                                </tr>
                                            </thead>
                                            <tbody class="divide-y divide-slate-100">
                                                {% if not act.recursos %}
                                                    <tr>
                                                        <td colspan="6" class="py-4 text-center text-slate-400 italic">No hay recursos ni mano de obra asignada.</td>
                                                    </tr>
                                                {% else %}
                                                    {% for r in act.recursos %}
                                                    <tr class="text-slate-700">
                                                        <td class="py-2.5 pl-4 sm:pl-0 font-medium text-slate-900">
                                                            {{r.nombre}}
                                                            {% if r.tipo == 'mano_de_obra' and r.fecha_pago %}
                                                                <span class="block text-[9px] text-slate-400 font-normal">Pago: {{ r.fecha_pago }}</span>
                                                            {% endif %}
                                                        </td>
                                                        <td class="py-2.5">
                                                            {% if r.tipo == 'mano_de_obra' %}
                                                                <span class="bg-amber-50 text-amber-700 px-2 py-0.5 rounded text-[9px] font-semibold border border-amber-200">Mano de Obra</span>
                                                            {% else %}
                                                                <span class="bg-blue-50 text-blue-700 px-2 py-0.5 rounded text-[9px] font-semibold border border-blue-200">Material</span>
                                                            {% endif %}
                                                        </td>
                                                        <td class="py-2.5 text-right font-semibold text-slate-900">
                                                            {% if r.tipo == 'mano_de_obra' %}
                                                                ${{"{:,.2f}".format(r.monto)}}
                                                            {% else %}
                                                                {{r.cantidad}} Unid.
                                                            {% endif %}
                                                        </td>
                                                        <td class="py-2.5 text-right font-medium">
                                                            {% if r.tipo == 'mano_de_obra' %}
                                                                -
                                                            {% else %}
                                                                ${{"{:,.2f}".format(r.precio)}}
                                                            {% endif %}
                                                        </td>
                                                        <td class="py-2.5 text-right font-bold text-slate-900">
                                                            {% if r.tipo == 'mano_de_obra' %}
                                                                ${{"{:,.2f}".format(r.monto)}}
                                                            {% else %}
                                                                ${{"{:,.2f}".format(r.precio * r.cantidad)}}
                                                            {% endif %}
                                                        </td>
                                                        <td class="py-2.5 text-center">
                                                            <div class="flex items-center justify-center gap-3">
                                                                <!-- BOTÓN EDITAR CANTIDAD DE INSUMO / MONTO DE PAGO -->
                                                                <button onclick="openEditarRecursoAsignado('{{act.id}}', '{{r.id}}', {{ r.nombre|tojson|safe }}, '{{r.tipo}}', '{{ r.monto if r.tipo == 'mano_de_obra' else r.cantidad }}', '{{ r.fecha_pago if r.tipo == 'mano_de_obra' else '' }}')" class="text-indigo-600 hover:text-indigo-800 transition" title="Editar Asignación">
                                                                    <i class="fa-solid fa-pen text-sm"></i>
                                                                </button>
                                                                
                                                                <a href="/recursos/{{proyecto.id}}/{{act.id}}/{{r.id}}/eliminar?tab=resumen" 
                                                                   onclick="return confirm('¿Deseas remover este recurso de la actividad?')" 
                                                                   class="text-rose-500 hover:text-rose-700 transition" title="Devolver al Pool">
                                                                    <i class="fa-solid fa-trash-arrow-up text-sm"></i>
                                                                </a>
                                                            </div>
                                                        </td>
                                                    </tr>
                                                    {% endfor %}
                                                {% endif %}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                                {% endfor %}
                            {% endif %}
                        </div>
                    </div>

                    <!-- PESTAÑA 2: TABLERO KANBAN -->
                    <div id="panel-kanban" class="space-y-6 hidden">
                        <div class="flex flex-col sm:flex-row justify-between items-stretch sm:items-center gap-3">
                            <h3 class="font-bold text-slate-800 text-sm md:text-base flex items-center gap-2">
                                <i class="fa-solid fa-table-columns text-indigo-600"></i> Tablero Kanban
                            </h3>
                            <button onclick="document.getElementById('modal-act').style.display='flex'" class="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-xl text-xs font-bold shadow-lg transition">+ Agregar Actividad</button>
                        </div>

                        <!-- Grid Kanban de 3 Columnas -->
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                            
                            <!-- Columna: PENDIENTES -->
                            <div class="bg-slate-200/60 p-4 rounded-2xl border border-slate-300/40 flex flex-col min-h-[250px]">
                                <div class="flex justify-between items-center mb-3 border-b border-slate-300/60 pb-2">
                                    <span class="font-bold text-slate-700 flex items-center gap-1.5"><span class="w-3 h-3 bg-slate-400 rounded-full"></span> Pendientes</span>
                                    <span class="bg-slate-300 text-slate-700 text-xs font-bold px-2 py-0.5 rounded-full">{{ m.conteo.pendientes }}</span>
                                </div>
                                <div class="space-y-3 flex-grow overflow-y-auto max-h-[350px] md:max-h-[500px]">
                                    {% for act in proyecto.actividades %}
                                        {% if act.estado == 'Pendiente' %}
                                            <div class="bg-white p-4 rounded-xl shadow-sm border border-slate-200/80 space-y-2 relative">
                                                <div class="flex justify-between items-start gap-2">
                                                    <h4 class="font-bold text-slate-900 text-sm flex-grow">{{ act.nombre }}</h4>
                                                    <!-- BOTÓN EDITAR EN TARJETA KANBAN -->
                                                    <button onclick="openEditarActividad('{{act.id}}', {{ act.nombre|tojson|safe }}, '{{act.presupuesto_tentativo}}', {{ act.descripcion|tojson|safe }})" class="text-slate-400 hover:text-indigo-600 transition" title="Editar Actividad">
                                                        <i class="fa-solid fa-pen text-xs"></i>
                                                    </button>
                                                </div>
                                                <p class="text-[11px] text-slate-500 line-clamp-2">{{ act.descripcion or 'Sin descripción.' }}</p>
                                                <div class="text-[10px] text-indigo-600 font-bold">
                                                    Ppto: ${{"{:,.2f}".format(act.presupuesto_tentativo)}}
                                                </div>
                                                <div class="flex justify-between items-center pt-2">
                                                    <span class="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-bold">Sin Fechas</span>
                                                    <button onclick="openTransition('{{ act.id }}', '{{ act.nombre }}', '{{ act.estado }}', '{{ act.fecha_inicio }}', '{{ act.fecha_fin }}')" class="text-xs text-indigo-600 hover:text-indigo-800 font-bold">
                                                        Mover <i class="fa-solid fa-angle-right"></i>
                                                    </button>
                                                </div>
                                            </div>
                                        {% endif %}
                                    {% endfor %}
                                </div>
                            </div>

                            <!-- Columna: INICIADAS -->
                            <div class="bg-blue-100/60 p-4 rounded-2xl border border-blue-200/40 flex flex-col min-h-[250px]">
                                <div class="flex justify-between items-center mb-3 border-b border-blue-300/60 pb-2">
                                    <span class="font-bold text-blue-800 flex items-center gap-1.5"><span class="w-3 h-3 bg-blue-500 rounded-full"></span> En Curso</span>
                                    <span class="bg-blue-200 text-blue-800 text-xs font-bold px-2 py-0.5 rounded-full">{{ m.conteo.iniciadas }}</span>
                                </div>
                                <div class="space-y-3 flex-grow overflow-y-auto max-h-[350px] md:max-h-[500px]">
                                    {% for act in proyecto.actividades %}
                                        {% if act.estado == 'Iniciada' %}
                                            <div class="bg-white p-4 rounded-xl shadow-sm border border-blue-200 space-y-2 relative">
                                                <div class="flex justify-between items-start gap-2">
                                                    <h4 class="font-bold text-slate-900 text-sm flex-grow">{{ act.nombre }}</h4>
                                                    <!-- BOTÓN EDITAR EN TARJETA KANBAN -->
                                                    <button onclick="openEditarActividad('{{act.id}}', {{ act.nombre|tojson|safe }}, '{{act.presupuesto_tentativo}}', {{ act.descripcion|tojson|safe }})" class="text-slate-400 hover:text-indigo-600 transition" title="Editar Actividad">
                                                        <i class="fa-solid fa-pen text-xs"></i>
                                                    </button>
                                                </div>
                                                <p class="text-[11px] text-slate-500 line-clamp-2">{{ act.descripcion or 'Sin descripción.' }}</p>
                                                <div class="text-[10px] text-indigo-600 font-bold">
                                                    Ppto: ${{"{:,.2f}".format(act.presupuesto_tentativo)}}
                                                </div>
                                                <div class="text-[10px] text-slate-500">
                                                    Inicio: <strong class="text-slate-800">{{ act.fecha_inicio }}</strong>
                                                </div>
                                                <div class="flex justify-between items-center pt-2">
                                                    <span class="text-[10px] bg-blue-50 text-blue-700 px-2 py-0.5 rounded font-bold">{{ act.recursos|length }} Recs</span>
                                                    <button onclick="openTransition('{{ act.id }}', '{{ act.nombre }}', '{{ act.estado }}', '{{ act.fecha_inicio }}', '{{ act.fecha_fin }}')" class="text-xs text-indigo-600 hover:text-indigo-800 font-bold">
                                                        Mover <i class="fa-solid fa-angle-right"></i>
                                                    </button>
                                                </div>
                                            </div>
                                        {% endif %}
                                    {% endfor %}
                                </div>
                            </div>

                            <!-- Columna: FINALIZADAS -->
                            <div class="bg-emerald-100/60 p-4 rounded-2xl border border-emerald-200/40 flex flex-col min-h-[250px]">
                                <div class="flex justify-between items-center mb-3 border-b border-emerald-300/60 pb-2">
                                    <span class="font-bold text-emerald-800 flex items-center gap-1.5"><span class="w-3 h-3 bg-emerald-500 rounded-full"></span> Finalizadas</span>
                                    <span class="bg-emerald-200 text-emerald-800 text-xs font-bold px-2 py-0.5 rounded-full">{{ m.conteo.completas }}</span>
                                </div>
                                <div class="space-y-3 flex-grow overflow-y-auto max-h-[350px] md:max-h-[500px]">
                                    {% for act in proyecto.actividades %}
                                        {% if act.estado == 'Completada' %}
                                            <div class="bg-white p-4 rounded-xl shadow-sm border border-emerald-200 space-y-2 relative">
                                                <div class="flex justify-between items-start gap-2">
                                                    <h4 class="font-bold text-slate-900 text-sm flex-grow">{{ act.nombre }}</h4>
                                                    <!-- BOTÓN EDITAR EN TARJETA KANBAN -->
                                                    <button onclick="openEditarActividad('{{act.id}}', {{ act.nombre|tojson|safe }}, '{{act.presupuesto_tentativo}}', {{ act.descripcion|tojson|safe }})" class="text-slate-400 hover:text-indigo-600 transition" title="Editar Actividad">
                                                        <i class="fa-solid fa-pen text-xs"></i>
                                                    </button>
                                                </div>
                                                <p class="text-[11px] text-slate-500 line-clamp-2">{{ act.descripcion or 'Sin descripción.' }}</p>
                                                <div class="text-[10px] text-indigo-600 font-bold">
                                                    Ppto: ${{"{:,.2f}".format(act.presupuesto_tentativo)}}
                                                </div>
                                                <div class="text-[10px] text-slate-500">
                                                    {{ act.fecha_inicio }} al {{ act.fecha_fin }}
                                                </div>
                                                <div class="flex justify-between items-center pt-2">
                                                    <span class="text-[10px] bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded font-bold">{{ act.recursos|length }} Recs</span>
                                                    <button onclick="openTransition('{{ act.id }}', '{{ act.nombre }}', '{{ act.estado }}', '{{ act.fecha_inicio }}', '{{ act.fecha_fin }}')" class="text-xs text-indigo-600 hover:text-indigo-800 font-bold">
                                                        Mover <i class="fa-solid fa-angle-right"></i>
                                                    </button>
                                                </div>
                                            </div>
                                        {% endif %}
                                    {% endfor %}
                                </div>
                            </div>

                        </div>
                    </div>

                    <!-- PESTAÑA 3: CRONOGRAMA GANTT -->
                    <div id="panel-gantt" class="space-y-6 hidden">
                        <div class="bg-white p-4 md:p-6 rounded-3xl border shadow-sm">
                            <h3 class="font-bold text-slate-800 mb-2 text-sm md:text-base flex items-center gap-2">
                                <i class="fa-solid fa-stream text-indigo-500"></i> Cronograma de Planificación GANTT
                            </h3>
                            <p class="text-[11px] text-slate-500 mb-6">Visualización temporal de las actividades en curso y finalizadas. En dispositivos móviles, puedes arrastrar con el dedo horizontalmente para visualizar todo el diagrama.</p>
                            
                            {% if m.has_gantt_tasks %}
                                <div class="overflow-x-auto bg-slate-50 p-3 md:p-6 rounded-2xl border no-scrollbar">
                                    <div class="mermaid min-w-[700px] md:min-w-0" id="gantt-container">
                                        {{ m.gantt_code|safe }}
                                    </div>
                                </div>
                                <script type="text/plain" id="gantt-raw-source">{{ m.gantt_code|safe }}</script>
                            {% else %}
                                <div class="text-center py-16 text-slate-400 text-sm italic bg-slate-50 rounded-2xl border border-dashed">
                                    <i class="fa-regular fa-clock text-4xl mb-3 block text-slate-300"></i>
                                    No hay actividades activas con fechas reales asignadas en este momento. Vaya al tablero Kanban para activar sus actividades.
                                </div>
                            {% endif %}
                        </div>
                    </div>

                    <!-- PESTAÑA 4: INVENTARIO DE RECURSOS -->
                    <div id="panel-inventario" class="space-y-6 hidden">
                        <div class="bg-white p-4 md:p-6 rounded-3xl border shadow-sm">
                            <div class="flex flex-col sm:flex-row justify-between items-stretch sm:items-center gap-3 mb-4">
                                <h3 class="font-bold text-slate-800 text-sm md:text-base flex items-center gap-2">
                                    <i class="fa-solid fa-boxes-stacked text-amber-500"></i> Inventario y Adquisición de Recursos
                                </h3>
                                <button onclick="document.getElementById('modal-pool').style.display='flex'" class="text-xs font-bold bg-amber-500 hover:bg-amber-600 text-white px-4 py-2 rounded-xl transition shadow-md">
                                    + Adquirir Recurso o Fondos
                                </button>
                            </div>
                            <p class="text-xs text-slate-500 mb-4">Maneje los materiales por cantidad de stock y registre los fondos financieros destinados para los pagos de mano de obra.</p>
                            
                            <div class="overflow-x-auto">
                                <table class="w-full min-w-[500px] text-xs text-left">
                                    <thead>
                                        <tr class="text-slate-400 border-b font-semibold uppercase">
                                            <th class="pb-2">Recurso</th>
                                            <th class="pb-2">Clasificación</th>
                                            <th class="pb-2 text-right">Precio Unitario / Total</th>
                                            <th class="pb-2 text-center">Stock Total</th>
                                            <th class="pb-2 text-center">Disponible</th>
                                            <th class="pb-2 text-center">Acciones</th>
                                        </tr>
                                    </thead>
                                    <tbody class="divide-y divide-slate-100">
                                        {% if not proyecto.recursos_pool %}
                                            <tr>
                                                <td colspan="6" class="py-4 text-center text-slate-400 italic">No hay insumos ni fondos de mano de obra en el pool de este proyecto.</td>
                                            </tr>
                                        {% else %}
                                            {% for r in proyecto.recursos_pool %}
                                            <tr class="text-slate-700">
                                                <td class="py-2.5 font-bold text-slate-900">{{r.nombre}}</td>
                                                <td class="py-2.5">
                                                    {% if r.tipo == 'mano_de_obra' %}
                                                        <span class="bg-amber-50 text-amber-700 px-2 py-0.5 rounded border border-amber-200 text-[10px] font-bold">Mano de Obra</span>
                                                    {% else %}
                                                        <span class="bg-blue-50 text-blue-700 px-2 py-0.5 rounded border border-blue-200 text-[10px] font-bold">Material / Insumo</span>
                                                    {% endif %}
                                                </td>
                                                <td class="py-2.5 text-right font-semibold">
                                                    {% if r.tipo == 'mano_de_obra' %}
                                                        Presupuestado: ${{"{:,.2f}".format(r.monto_total)}}
                                                    {% else %}
                                                        ${{"{:,.2f}".format(r.precio)}} c/u
                                                    {% endif %}
                                                </td>
                                                <td class="py-2.5 text-center">
                                                    {% if r.tipo == 'mano_de_obra' %}
                                                        Fondo Total
                                                    {% else %}
                                                        Stock: {{ r.cantidad_total }}
                                                    {% endif %}
                                                </td>
                                                <td class="py-2.5 text-center">
                                                    {% if r.tipo == 'mano_de_obra' %}
                                                        <span class="px-2.5 py-1 rounded-full text-xs font-bold {% if r.monto_disponible > 0 %}bg-emerald-100 text-emerald-800{% else %}bg-rose-100 text-rose-800{% endif %}">
                                                            Disp: ${{"{:,.2f}".format(r.monto_disponible)}}
                                                        </span>
                                                    {% else %}
                                                        <span class="px-2.5 py-1 rounded-full text-xs font-bold {% if r.cantidad_disponible > 0 %}bg-blue-100 text-blue-800{% else %}bg-rose-100 text-rose-800{% endif %}">
                                                            Disp: {{ r.cantidad_disponible }}
                                                        </span>
                                                    {% endif %}
                                                </td>
                                                <td class="py-2.5 text-center">
                                                    <div class="flex items-center justify-center gap-2.5">
                                                        <!-- BOTÓN EDITAR EN INVENTARIO (POOL DE ADQUISICIÓN) -->
                                                        <button onclick="openEditarRecursoPool('{{r.id}}', {{ r.nombre|tojson|safe }}, '{{r.tipo}}', '{{r.precio if r.tipo == 'material' else ''}}', '{{r.cantidad_total if r.tipo == 'material' else ''}}', '{{r.monto_total if r.tipo == 'mano_de_obra' else ''}}')" class="text-indigo-600 hover:text-indigo-800 transition shadow-sm" title="Editar recurso / fondo">
                                                            <i class="fa-solid fa-pen text-base"></i>
                                                        </button>
                                                        
                                                        <a href="/proyectos/{{proyecto.id}}/recursos-pool/{{r.id}}/eliminar" 
                                                           onclick="return confirm('¿Seguro que deseas eliminar este recurso del inventario general?')"
                                                           class="text-rose-500 hover:text-rose-700">
                                                            <i class="fa-solid fa-trash-can text-base"></i>
                                                        </a>
                                                    </div>
                                                </td>
                                            </tr>
                                            {% endfor %}
                                        {% endif %}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                {% endif %}
            </section>
        </div>
    </main>

    <!-- Modal: Nueva Actividad -->
    <div id="modal-act" class="fixed inset-0 bg-black/60 hidden items-center justify-center p-4 z-50 backdrop-blur-sm animate-fade-in">
        <div class="bg-white p-6 md:p-8 rounded-3xl max-w-md w-full shadow-2xl animate-in scale-in duration-200">
            <h3 class="text-lg md:text-xl font-bold mb-4 text-slate-900 flex items-center gap-2">
                <i class="fa-solid fa-diagram-project text-indigo-600"></i> Registrar Actividad
            </h3>
            <p class="text-xs text-slate-500 mb-4">La actividad se creará en estado "Pendiente" y sin fechas para que la inicie cuando lo requiera.</p>
            <form action="/actividades/{{proyecto.id if proyecto else ''}}" method="POST" class="space-y-4 text-sm">
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Nombre de la actividad</label>
                    <input type="text" name="nombre" placeholder="Ej. Pavimentación de carril" class="w-full p-2.5 border rounded-xl" required>
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Presupuesto Estimado / Tentativo ($)</label>
                    <input type="number" step="0.01" name="presupuesto_tentativo" placeholder="Ej. 10000" class="w-full p-2.5 border rounded-xl" required>
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Descripción</label>
                    <textarea name="descripcion" placeholder="Alcance general de la tarea..." rows="2" class="w-full p-2.5 border rounded-xl"></textarea>
                </div>
                <div class="flex gap-2 pt-2">
                    <button type="button" onclick="document.getElementById('modal-act').style.display='none'" class="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 py-3 rounded-xl font-bold transition">Cancelar</button>
                    <button class="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white py-3 rounded-xl font-bold shadow-lg transition">Guardar Actividad</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Modal: Editar Actividad -->
    <div id="modal-editar-act" class="fixed inset-0 bg-black/60 hidden items-center justify-center p-4 z-50 backdrop-blur-sm">
        <div class="bg-white p-6 md:p-8 rounded-3xl max-w-md w-full shadow-2xl">
            <h3 class="text-lg md:text-xl font-bold mb-4 text-slate-900 flex items-center gap-2">
                <i class="fa-solid fa-pen text-indigo-600"></i> Editar Actividad
            </h3>
            <form id="form-editar-act" method="POST" class="space-y-4 text-sm">
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Nombre de la actividad</label>
                    <input type="text" name="nombre" id="edit-act-nombre" class="w-full p-2.5 border rounded-xl" required>
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Presupuesto Estimado / Tentativo ($)</label>
                    <input type="number" step="0.01" name="presupuesto_tentativo" id="edit-act-presupuesto" class="w-full p-2.5 border rounded-xl" required>
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Descripción</label>
                    <textarea name="descripcion" id="edit-act-descripcion" rows="2" class="w-full p-2.5 border rounded-xl"></textarea>
                </div>
                <div class="flex gap-2 pt-2">
                    <button type="button" onclick="document.getElementById('modal-editar-act').style.display='none'" class="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 py-3 rounded-xl font-bold transition">Cancelar</button>
                    <button class="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white py-3 rounded-xl font-bold shadow-lg transition">Actualizar</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Modal: Transición de Estados (Tablero Kanban) -->
    <div id="modal-transicion" class="fixed inset-0 bg-black/60 hidden items-center justify-center p-4 z-50 backdrop-blur-sm">
        <div class="bg-white p-6 md:p-8 rounded-3xl max-w-md w-full shadow-2xl">
            <h3 class="text-base md:text-lg font-bold text-slate-900 mb-1">Actualizar Estado</h3>
            <p id="trans-target-name" class="text-xs text-indigo-600 font-bold mb-4"></p>
            
            <form id="form-transicion" method="POST" class="space-y-4 text-sm">
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Nuevo Estado</label>
                    <select name="nuevo_estado" id="select-nuevo-estado" class="w-full p-2.5 border rounded-xl" required>
                        <option value="Pendiente">Pendiente (Sin Fechas / No graficar en GANTT)</option>
                        <option value="Iniciada">Iniciada (En curso - Requiere fecha de inicio)</option>
                        <option value="Completada">Completada (Finalizada - Requiere fecha de inicio y fin)</option>
                    </select>
                </div>
                
                <div id="div-trans-f-ini" class="hidden">
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Fecha de Inicio Real</label>
                    <input type="date" name="f_ini" id="trans-f-ini" class="w-full p-2.5 border rounded-xl">
                </div>
                
                <div id="div-trans-f-fin" class="hidden">
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Fecha de Finalización Real</label>
                    <input type="date" name="f_fin" id="trans-f-fin" class="w-full p-2.5 border rounded-xl">
                </div>

                <div class="flex gap-2 pt-2">
                    <button type="button" onclick="document.getElementById('modal-transicion').style.display='none'" class="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 py-3 rounded-xl font-bold transition">Cancelar</button>
                    <button class="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white py-3 rounded-xl font-bold shadow-lg transition">Aplicar Cambio</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Modal: Agregar Recurso al Pool -->
    <div id="modal-pool" class="fixed inset-0 bg-black/60 hidden items-center justify-center p-4 z-50 backdrop-blur-sm">
        <div class="bg-white p-6 md:p-8 rounded-3xl max-w-md w-full shadow-2xl">
            <h3 class="text-lg md:text-xl font-bold mb-4 text-slate-900 flex items-center gap-2">
                <i class="fa-solid fa-boxes-stacked text-amber-500"></i> Registrar en Inventario
            </h3>
            <form action="/proyectos/{{proyecto.id if proyecto else ''}}/recursos-pool" method="POST" class="space-y-4 text-sm">
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Nombre del Recurso / Fondo</label>
                    <input type="text" name="nombre" placeholder="Ej. Alambre, Nómina Obreros" class="w-full p-2.5 border rounded-xl" required>
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Clasificación</label>
                    <select name="tipo" id="pool-tipo-selector" onchange="togglePoolFields(this.value)" class="w-full p-2.5 border rounded-xl" required>
                        <option value="material">Insumo / Material Físico</option>
                        <option value="mano_de_obra">Pago de Mano de Obra (Fondos Financieros)</option>
                    </select>
                </div>

                <div id="pool-fields-material" class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Precio Unitario ($)</label>
                        <input type="number" step="0.01" name="precio" id="pool-precio" placeholder="Precio unitario" class="w-full p-2.5 border rounded-xl" required>
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Cantidad Inicial</label>
                        <input type="number" name="cantidad" id="pool-cantidad" min="1" value="10" class="w-full p-2.5 border rounded-xl" required>
                    </div>
                </div>

                <div id="pool-fields-labor" class="hidden">
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1 font-semibold text-amber-600">Presupuesto/Fondo de Pago ($)</label>
                    <input type="number" step="0.01" name="monto_total" id="pool-monto-total" placeholder="Ej. 15000" class="w-full p-2.5 border border-amber-300 rounded-xl bg-amber-50/50">
                    <p class="text-[10px] text-slate-400 mt-1">Defina el dinero total disponible para pagar mano de obra.</p>
                </div>

                <div class="flex gap-2 pt-2">
                    <button type="button" onclick="document.getElementById('modal-pool').style.display='none'" class="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 py-3 rounded-xl font-bold transition">Cancelar</button>
                    <button class="flex-1 bg-amber-500 hover:bg-amber-600 text-white py-3 rounded-xl font-bold shadow-lg transition">Adquirir</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Modal: Asignar Recurso del Pool a una Actividad -->
    <div id="modal-rec" class="fixed inset-0 bg-black/60 hidden items-center justify-center p-4 z-50 backdrop-blur-sm">
        <div class="bg-white p-6 md:p-8 rounded-3xl max-w-md w-full shadow-2xl">
            <h3 class="text-lg md:text-xl font-bold mb-2 text-slate-900"><i class="fa-solid fa-plus-circle text-indigo-600"></i> Consumir del Inventario</h3>
            <p class="text-xs text-slate-500 mb-4">Asignando recursos a la actividad: <strong id="act-target-name" class="text-slate-800"></strong></p>
            
            <form id="form-rec" method="POST" class="space-y-4 text-sm">
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Seleccionar Recurso</label>
                    <select name="pool_id" id="select-pool-recurso" class="w-full p-2.5 border rounded-xl" required>
                        <!-- Cargado por JS -->
                    </select>
                </div>
                
                <div class="bg-slate-50 p-3 rounded-lg border border-slate-100 text-xs text-slate-600" id="pool-item-info">
                    Selecciona un recurso para ver su disponibilidad.
                </div>

                <div id="rec-fields-material" class="hidden">
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Cantidad a Asignar</label>
                    <input type="number" name="cantidad" id="input-cantidad-rec" min="1" value="1" class="w-full p-2.5 border rounded-xl">
                </div>

                <div id="rec-fields-labor" class="hidden space-y-3">
                    <div>
                        <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Monto de Pago ($)</label>
                        <input type="number" step="0.01" name="monto" id="input-monto-rec" placeholder="Ej. 1200.00" class="w-full p-2.5 border rounded-xl">
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Fecha de Ejecución de Pago</label>
                        <input type="date" name="fecha_pago" id="input-fecha-pago-rec" class="w-full p-2.5 border rounded-xl">
                    </div>
                </div>

                <div class="flex gap-2 pt-2">
                    <button type="button" onclick="document.getElementById('modal-rec').style.display='none'" class="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 py-3 rounded-xl font-bold transition">Cancelar</button>
                    <button class="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white py-3 rounded-xl font-bold shadow-lg transition">Asignar Insumo</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Modal: Editar Recurso Asignado (Insumo / Mano de Obra en la Actividad) -->
    <div id="modal-editar-rec-asignado" class="fixed inset-0 bg-black/60 hidden items-center justify-center p-4 z-50 backdrop-blur-sm">
        <div class="bg-white p-6 md:p-8 rounded-3xl max-w-md w-full shadow-2xl">
            <h3 class="text-lg md:text-xl font-bold mb-2 text-slate-900"><i class="fa-solid fa-pen text-indigo-600"></i> Editar Asignación</h3>
            <p class="text-xs text-slate-500 mb-4">Recurso: <strong id="edit-rec-target-name" class="text-slate-800"></strong></p>
            
            <form id="form-editar-rec-asignado" method="POST" class="space-y-4 text-sm">
                <div id="edit-rec-fields-material" class="hidden">
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Cantidad Asignada</label>
                    <input type="number" name="cantidad" id="edit-input-cantidad-rec" min="1" class="w-full p-2.5 border rounded-xl">
                </div>

                <div id="edit-rec-fields-labor" class="hidden space-y-3">
                    <div>
                        <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Monto de Pago ($)</label>
                        <input type="number" step="0.01" name="monto" id="edit-input-monto-rec" class="w-full p-2.5 border rounded-xl">
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Fecha de Ejecución de Pago</label>
                        <input type="date" name="fecha_pago" id="edit-input-fecha-pago-rec" class="w-full p-2.5 border rounded-xl">
                    </div>
                </div>

                <div class="flex gap-2 pt-2">
                    <button type="button" onclick="document.getElementById('modal-editar-rec-asignado').style.display='none'" class="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 py-3 rounded-xl font-bold transition">Cancelar</button>
                    <button class="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white py-3 rounded-xl font-bold shadow-lg transition">Guardar Cambios</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Modal: Editar Recurso en el Pool (Adquisición de Recursos) -->
    <div id="modal-editar-pool" class="fixed inset-0 bg-black/60 hidden items-center justify-center p-4 z-50 backdrop-blur-sm">
        <div class="bg-white p-6 md:p-8 rounded-3xl max-w-md w-full shadow-2xl">
            <h3 class="text-lg md:text-xl font-bold mb-4 text-slate-900 flex items-center gap-2">
                <i class="fa-solid fa-pen text-amber-500"></i> Editar Recurso de Inventario
            </h3>
            <form id="form-editar-pool" method="POST" class="space-y-4 text-sm">
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Nombre del Recurso / Fondo</label>
                    <input type="text" name="nombre" id="edit-pool-nombre" class="w-full p-2.5 border rounded-xl" required>
                </div>
                
                <div id="edit-pool-fields-material" class="grid grid-cols-2 gap-3 hidden">
                    <div>
                        <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Precio Unitario ($)</label>
                        <input type="number" step="0.01" name="precio" id="edit-pool-precio" class="w-full p-2.5 border rounded-xl">
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Cantidad Total (Stock)</label>
                        <input type="number" name="cantidad_total" id="edit-pool-cantidad" min="1" class="w-full p-2.5 border rounded-xl">
                    </div>
                </div>

                <div id="edit-pool-fields-labor" class="hidden">
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1 font-semibold text-amber-600">Presupuesto/Fondo de Pago ($)</label>
                    <input type="number" step="0.01" name="monto_total" id="edit-pool-monto-total" class="w-full p-2.5 border border-amber-300 rounded-xl bg-amber-50/50">
                    <p class="text-[10px] text-slate-400 mt-1">Defina el dinero total disponible para pagar mano de obra.</p>
                </div>

                <div class="flex gap-2 pt-2">
                    <button type="button" onclick="document.getElementById('modal-editar-pool').style.display='none'" class="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 py-3 rounded-xl font-bold transition">Cancelar</button>
                    <button class="flex-1 bg-amber-500 hover:bg-amber-600 text-white py-3 rounded-xl font-bold shadow-lg transition">Actualizar</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Scripts de navegación y lógica interactiva de formularios -->
    <script>
        const recursosPool = {{ proyecto.recursos_pool|tojson|safe if proyecto else '[]' }};
        const activeTabClass = "whitespace-nowrap flex items-center gap-2 px-4 py-2.5 text-xs md:text-sm font-bold bg-indigo-600 text-white rounded-xl shadow-md border-b-2 border-indigo-700 transition";
        const inactiveTabClass = "whitespace-nowrap flex items-center gap-2 px-4 py-2.5 text-xs md:text-sm font-semibold bg-white text-slate-600 hover:text-indigo-600 rounded-xl hover:bg-slate-50 border border-slate-200 shadow-sm transition";

        window.onload = function() {
            adjustResponsiveSidebar();
            window.addEventListener('resize', adjustResponsiveSidebar);

            const urlParams = new URLSearchParams(window.location.search);
            const activeTab = urlParams.get('tab') || 'resumen';
            switchTab(activeTab);
        }

        function toggleMobileSidebar() {
            const container = document.getElementById('mobile-sidebar-container');
            const chevron = document.getElementById('mobile-sidebar-chevron');
            if (container.classList.contains('hidden')) {
                container.classList.remove('hidden');
                chevron.classList.add('rotate-180');
            } else {
                container.classList.add('hidden');
                chevron.classList.remove('rotate-180');
            }
        }

        function adjustResponsiveSidebar() {
            const sidebar = document.getElementById('main-sidebar-content');
            const desktopContainer = document.getElementById('main-desktop-sidebar');
            const mobileContainer = document.getElementById('mobile-sidebar-container');
            
            let content = document.getElementById('sidebar-content');
            
            if (window.innerWidth < 1024) {
                const mobileTarget = document.getElementById('mobile-sidebar-target');
                if (content && mobileTarget && !mobileTarget.contains(content)) {
                    mobileTarget.appendChild(content);
                }
            } else {
                const desktopAside = document.getElementById('main-sidebar');
                if (content && desktopAside && !desktopAside.contains(content)) {
                    desktopAside.appendChild(content);
                }
                document.getElementById('mobile-sidebar-container').classList.add('hidden');
                document.getElementById('mobile-sidebar-chevron').classList.remove('rotate-180');
            }
        }

        function switchTab(tabName) {
            document.getElementById('panel-resumen').classList.add('hidden');
            document.getElementById('panel-kanban').classList.add('hidden');
            document.getElementById('panel-gantt').classList.add('hidden');
            document.getElementById('panel-inventario').classList.add('hidden');
            
            document.getElementById('tab-btn-resumen').className = inactiveTabClass;
            document.getElementById('tab-btn-kanban').className = inactiveTabClass;
            document.getElementById('tab-btn-gantt').className = inactiveTabClass;
            document.getElementById('tab-btn-inventario').className = inactiveTabClass;
            
            document.getElementById('panel-' + tabName).classList.remove('hidden');
            document.getElementById('tab-btn-' + tabName).className = activeTabClass;
            
            const url = new URL(window.location);
            url.searchParams.set('tab', tabName);
            window.history.replaceState({}, '', url);

            if (tabName === 'gantt') {
                setTimeout(async () => {
                    const ganttContainer = document.getElementById('gantt-container');
                    const ganttSource = document.getElementById('gantt-raw-source');
                    if (ganttContainer && ganttSource) {
                        const rawCode = ganttSource.textContent;
                        ganttContainer.innerHTML = rawCode;
                        ganttContainer.removeAttribute('data-processed');
                        if (window.mermaid) {
                            try {
                                await window.mermaid.run({
                                    nodes: [ganttContainer]
                                });
                            } catch (err) {
                                console.error("Mermaid run error:", err);
                            }
                        }
                    }
                }, 50);
            }
        }

        function togglePoolFields(tipo) {
            const divMaterial = document.getElementById('pool-fields-material');
            const divLabor = document.getElementById('pool-fields-labor');
            const inputPrecio = document.getElementById('pool-precio');
            const inputCantidad = document.getElementById('pool-cantidad');
            const inputMonto = document.getElementById('pool-monto-total');
            
            if (tipo === 'mano_de_obra') {
                divMaterial.classList.add('hidden');
                divLabor.classList.remove('hidden');
                inputPrecio.required = false;
                inputCantidad.required = false;
                inputMonto.required = true;
            } else {
                divMaterial.classList.remove('hidden');
                divLabor.classList.add('hidden');
                inputPrecio.required = true;
                inputCantidad.required = true;
                inputMonto.required = false;
            }
        }

        function openRecurso(id, nombre) {
            document.getElementById('act-target-name').innerText = nombre;
            const urlParams = new URLSearchParams(window.location.search);
            const activeTab = urlParams.get('tab') || 'resumen';
            document.getElementById('form-rec').action = "/recursos/{{proyecto.id if proyecto else ''}}/" + id + "?tab=" + activeTab;
            
            const select = document.getElementById('select-pool-recurso');
            const infoText = document.getElementById('pool-item-info');
            const divAsignarMaterial = document.getElementById('rec-fields-material');
            const divAsignarLabor = document.getElementById('rec-fields-labor');
            
            const inputCant = document.getElementById('input-cantidad-rec');
            const inputMonto = document.getElementById('input-monto-rec');
            const inputFechaPago = document.getElementById('input-fecha-pago-rec');
            
            select.innerHTML = '<option value="">-- Seleccionar del Inventario --</option>';
            
            let count = 0;
            recursosPool.forEach(item => {
                const opt = document.createElement('option');
                opt.value = item.id;
                
                if (item.tipo === 'mano_de_obra') {
                    if (parseFloat(item.monto_disponible) > 0) {
                        opt.textContent = `${item.nombre} (Dinero Disponible: $${parseFloat(item.monto_disponible).toFixed(2)})`;
                        opt.dataset.tipo = 'mano_de_obra';
                        opt.dataset.disponible = item.monto_disponible;
                        select.appendChild(opt);
                        count++;
                    }
                } else {
                    if (parseInt(item.cantidad_disponible) > 0) {
                        opt.textContent = `${item.nombre} (Stock Disponible: ${item.cantidad_disponible})`;
                        opt.dataset.tipo = 'material';
                        opt.dataset.disponible = item.cantidad_disponible;
                        opt.dataset.precio = item.precio;
                        select.appendChild(opt);
                        count++;
                    }
                }
            });
            
            if (count === 0) {
                infoText.innerHTML = '<span class="text-rose-500 font-bold">¡Atención! No hay recursos o fondos con saldos disponibles en el inventario general de este proyecto.</span>';
                divAsignarMaterial.classList.add('hidden');
                divAsignarLabor.classList.add('hidden');
            } else {
                infoText.innerHTML = 'Selecciona un recurso para ver su disponibilidad.';
                divAsignarMaterial.classList.add('hidden');
                divAsignarLabor.classList.add('hidden');
            }
            
            select.onchange = function() {
                const selectedOpt = select.options[select.selectedIndex];
                if (selectedOpt && selectedOpt.value) {
                    const tipo = selectedOpt.dataset.tipo;
                    const disp = parseFloat(selectedOpt.dataset.disponible);
                    
                    if (tipo === 'mano_de_obra') {
                        divAsignarMaterial.classList.add('hidden');
                        divAsignarLabor.classList.remove('hidden');
                        inputCant.required = false;
                        inputMonto.required = true;
                        inputFechaPago.required = true;
                        inputMonto.max = disp;
                        inputMonto.value = "";
                        infoText.innerHTML = `Presupuesto Disponible: <strong class="text-slate-900">$${disp.toFixed(2)}</strong>`;
                    } else {
                        const precio = parseFloat(selectedOpt.dataset.precio);
                        divAsignarMaterial.classList.remove('hidden');
                        divAsignarLabor.classList.add('hidden');
                        inputCant.required = true;
                        inputMonto.required = false;
                        inputFechaPago.required = false;
                        inputCant.max = disp;
                        inputCant.value = 1;
                        infoText.innerHTML = `Precio Unitario: <strong class="text-slate-900">$${precio.toFixed(2)}</strong> | Unidades Disponibles: <strong class="text-slate-900">${disp}</strong>`;
                    }
                } else {
                    divAsignarMaterial.classList.add('hidden');
                    divAsignarLabor.classList.add('hidden');
                    infoText.innerHTML = 'Selecciona un recurso para ver su disponibilidad.';
                }
            };
            
            document.getElementById('modal-rec').style.display = 'flex';
        }

        // --- FUNCIONES JS PARA MODALES DE EDICIÓN ---

        function openEditarActividad(id, nombre, presupuesto, descripcion) {
            document.getElementById('edit-act-nombre').value = nombre;
            document.getElementById('edit-act-presupuesto').value = parseFloat(presupuesto);
            document.getElementById('edit-act-descripcion').value = descripcion;
            
            const urlParams = new URLSearchParams(window.location.search);
            const activeTab = urlParams.get('tab') || 'resumen';
            document.getElementById('form-editar-act').action = `/actividades/{{proyecto.id if proyecto else ''}}/${id}/editar?tab=${activeTab}`;
            
            document.getElementById('modal-editar-act').style.display = 'flex';
        }

        function openEditarRecursoAsignado(actId, recId, nombre, tipo, valorActual, extraInfo) {
            document.getElementById('edit-rec-target-name').innerText = nombre;
            
            const divMaterial = document.getElementById('edit-rec-fields-material');
            const divLabor = document.getElementById('edit-rec-fields-labor');
            const inputCant = document.getElementById('edit-input-cantidad-rec');
            const inputMonto = document.getElementById('edit-input-monto-rec');
            const inputFechaPago = document.getElementById('edit-input-fecha-pago-rec');
            
            if (tipo === 'mano_de_obra') {
                divMaterial.classList.add('hidden');
                divLabor.classList.remove('hidden');
                inputCant.required = false;
                inputMonto.required = true;
                inputFechaPago.required = true;
                
                inputMonto.value = valorActual;
                inputFechaPago.value = extraInfo;
            } else {
                divMaterial.classList.remove('hidden');
                divLabor.classList.add('hidden');
                inputCant.required = true;
                inputMonto.required = false;
                inputFechaPago.required = false;
                
                inputCant.value = valorActual;
            }
            
            const urlParams = new URLSearchParams(window.location.search);
            const activeTab = urlParams.get('tab') || 'resumen';
            document.getElementById('form-editar-rec-asignado').action = `/recursos/{{proyecto.id if proyecto else ''}}/${actId}/${recId}/editar?tab=${activeTab}`;
            
            document.getElementById('modal-editar-rec-asignado').style.display = 'flex';
        }

        function openEditarRecursoPool(rpId, nombre, tipo, precio, cantidadTotal, montoTotal) {
            document.getElementById('edit-pool-nombre').value = nombre;
            
            const divMaterial = document.getElementById('edit-pool-fields-material');
            const divLabor = document.getElementById('edit-pool-fields-labor');
            const inputPrecio = document.getElementById('edit-pool-precio');
            const inputCantidad = document.getElementById('edit-pool-cantidad');
            const inputMonto = document.getElementById('edit-pool-monto-total');
            
            if (tipo === 'mano_de_obra') {
                divMaterial.classList.add('hidden');
                divLabor.classList.remove('hidden');
                inputPrecio.required = false;
                inputCantidad.required = false;
                inputMonto.required = true;
                
                inputMonto.value = montoTotal;
            } else {
                divMaterial.classList.remove('hidden');
                divLabor.classList.add('hidden');
                inputPrecio.required = true;
                inputCantidad.required = true;
                inputMonto.required = false;
                
                inputPrecio.value = precio;
                inputCantidad.value = cantidadTotal;
            }
            
            document.getElementById('form-editar-pool').action = `/proyectos/{{proyecto.id if proyecto else ''}}/recursos-pool/${rpId}/editar`;
            document.getElementById('modal-editar-pool').style.display = 'flex';
        }

        function openTransition(id, nombre, estadoActual, fIni, fFin) {
            document.getElementById('trans-target-name').innerText = nombre;
            const form = document.getElementById('form-transicion');
            form.action = `/actividades/{{proyecto.id if proyecto else ''}}/${id}/estado-kanban`;
            
            const selectEstado = document.getElementById('select-nuevo-estado');
            selectEstado.value = estadoActual;
            
            const inputIni = document.getElementById('trans-f-ini');
            const inputFin = document.getElementById('trans-f-fin');
            
            inputIni.value = fIni !== 'None' ? fIni : '';
            inputFin.value = fFin !== 'None' ? fFin : '';
            
            toggleTransFechas(estadoActual);
            
            selectEstado.onchange = function() {
                toggleTransFechas(selectEstado.value);
            };
            
            document.getElementById('modal-transicion').style.display = 'flex';
        }

        function toggleTransFechas(estado) {
            const divIni = document.getElementById('div-trans-f-ini');
            const divFin = document.getElementById('div-trans-f-fin');
            const inputIni = document.getElementById('trans-f-ini');
            const inputFin = document.getElementById('trans-f-fin');
            
            if (estado === 'Pendiente') {
                divIni.classList.add('hidden');
                divFin.classList.add('hidden');
                inputIni.required = false;
                inputFin.required = false;
            } else if (estado === 'Iniciada') {
                divIni.classList.remove('hidden');
                divFin.classList.add('hidden');
                inputIni.required = true;
                inputFin.required = false;
            } else if (estado === 'Completada') {
                divIni.classList.remove('hidden');
                divFin.classList.remove('hidden');
                inputIni.required = true;
                inputFin.required = true;
            }
        }
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    cargar_proyectos_desde_sheets()
    
    p_id = request.args.get("id")
    p_actual = PROYECTOS_DB.get(p_id)
    metricas = calcular_metricas(p_actual) if p_actual else {}
    active_tab = request.args.get("tab", "resumen")
    
    sheets_connected = obtener_cliente_sheets() is not None
    
    return render_template_string(
        INDEX_HTML, 
        proyectos=PROYECTOS_DB, 
        proyecto=p_actual, 
        m=metricas, 
        active_tab=active_tab,
        sheets_connected=sheets_connected,
        connection_error=LAST_CONNECTION_ERROR
    )

@app.route("/proyectos", methods=["POST"])
def crear_p():
    id_p = str(uuid.uuid4())[:6]
    nuevo_p = {
        "id": id_p, 
        "nombre": request.form["nombre"], 
        "descripcion": "",
        "presupuesto": float(request.form["presupuesto"]),
        "fecha_inicio": request.form["fecha_inicio"], 
        "fecha_fin_tentativa": request.form["fecha_fin"], 
        "recursos_pool": [],
        "actividades": []
    }
    
    PROYECTOS_DB[id_p] = nuevo_p
    guardar_proyecto_en_sheets(id_p, nuevo_p)
    
    flash(f"Proyecto '{request.form['nombre']}' creado correctamente.", "success")
    return redirect(url_for("index", id=id_p, tab="resumen"))

@app.route("/proyectos/<p_id>/eliminar", methods=["GET"])
def eliminar_p(p_id):
    if p_id in PROYECTOS_DB:
        nombre = PROYECTOS_DB[p_id]["nombre"]
        del PROYECTOS_DB[p_id]
        eliminar_proyecto_en_sheets(p_id)
        flash(f"Se ha eliminado el proyecto '{nombre}' de forma permanente.", "success")
    return redirect(url_for("index"))

# Rutas para el Inventario General (Pool)
@app.route("/proyectos/<p_id>/recursos-pool", methods=["POST"])
def add_recurso_pool(p_id):
    p = PROYECTOS_DB.get(p_id)
    if p:
        nombre = request.form["nombre"]
        tipo = request.form["tipo"]
        
        if tipo == "mano_de_obra":
            monto = float(request.form.get("monto_total", 0.0))
            p["recursos_pool"].append({
                "id": str(uuid.uuid4())[:6],
                "nombre": nombre,
                "tipo": tipo,
                "monto_total": monto,
                "monto_disponible": monto
            })
            flash(f"Fondo de mano de obra '{nombre}' añadido con ${monto:,.2f} al pool.", "success")
        else:
            precio = float(request.form["precio"])
            cantidad = int(request.form["cantidad"])
            p["recursos_pool"].append({
                "id": str(uuid.uuid4())[:6],
                "nombre": nombre,
                "tipo": tipo,
                "precio": precio,
                "cantidad_total": cantidad,
                "cantidad_disponible": cantidad
            })
            flash(f"Material '{nombre}' añadido al pool.", "success")
            
        guardar_proyecto_en_sheets(p_id, p)
            
    return redirect(url_for("index", id=p_id, tab="inventario"))

@app.route("/proyectos/<p_id>/recursos-pool/<rp_id>/editar", methods=["POST"])
def editar_recurso_pool(p_id, rp_id):
    """Permite editar los detalles de un recurso o fondo del inventario (Adquisición de recursos)"""
    p = PROYECTOS_DB.get(p_id)
    if p:
        recurso = next((r for r in p.get("recursos_pool", []) if r["id"] == rp_id), None)
        if recurso:
            nombre = request.form["nombre"]
            recurso["nombre"] = nombre
            
            # Sincronizar el nombre en todas las asignaciones existentes en las actividades
            for act in p.get("actividades", []):
                for r in act.get("recursos", []):
                    if r.get("pool_id") == rp_id:
                        r["nombre"] = nombre
            
            if recurso["tipo"] == "mano_de_obra":
                nuevo_monto_total = float(request.form["monto_total"])
                # Calcular el monto que ya se encuentra asignado/comprometido en actividades
                monto_asignado = sum(float(r["monto"]) for act in p["actividades"] for r in act["recursos"] if r.get("pool_id") == rp_id)
                
                if nuevo_monto_total < monto_asignado:
                    flash(f"No es posible reducir el fondo por debajo del monto asignado en actividades (${monto_asignado:,.2f}).", "error")
                else:
                    recurso["monto_total"] = nuevo_monto_total
                    recurso["monto_disponible"] = nuevo_monto_total - monto_asignado
                    flash(f"Fondo '{nombre}' actualizado correctamente en el inventario.", "success")
            else:
                precio = float(request.form["precio"])
                nueva_cantidad_total = int(request.form["cantidad_total"])
                # Calcular las unidades físicas ya asignadas/comprometidas
                cantidad_asignada = sum(int(r["cantidad"]) for act in p["actividades"] for r in act["recursos"] if r.get("pool_id") == rp_id)
                
                if nueva_cantidad_total < cantidad_asignada:
                    flash(f"No es posible reducir el stock por debajo de las unidades ya asignadas ({cantidad_asignada}).", "error")
                else:
                    recurso["precio"] = precio
                    recurso["cantidad_total"] = nueva_cantidad_total
                    recurso["cantidad_disponible"] = nueva_cantidad_total - cantidad_asignada
                    
                    # Sincronizar el precio unitario en las actividades asignadas
                    for act in p["actividades"]:
                        for r in act["recursos"]:
                            if r.get("pool_id") == rp_id:
                                r["precio"] = precio
                                
                    flash(f"Material '{nombre}' actualizado correctamente en el inventario.", "success")
                    
            guardar_proyecto_en_sheets(p_id, p)
            
    return redirect(url_for("index", id=p_id, tab="inventario"))

@app.route("/proyectos/<p_id>/recursos-pool/<rp_id>/eliminar")
def eliminar_recurso_pool(p_id, rp_id):
    p = PROYECTOS_DB.get(p_id)
    if p:
        recurso = next((r for r in p.get("recursos_pool", []) if r["id"] == rp_id), None)
        if recurso:
            if recurso["tipo"] == "mano_de_obra":
                is_dirty = recurso["monto_disponible"] < recurso["monto_total"]
            else:
                is_dirty = recurso["cantidad_disponible"] < recurso["cantidad_total"]
                
            if is_dirty:
                flash("No se puede eliminar: tiene fondos o unidades asignadas en actividades vigentes.", "error")
            else:
                p["recursos_pool"] = [r for r in p["recursos_pool"] if r["id"] != rp_id]
                guardar_proyecto_en_sheets(p_id, p)
                flash("Recurso eliminado del inventario general.", "success")
    return redirect(url_for("index", id=p_id, tab="inventario"))

@app.route("/actividades/<p_id>", methods=["POST"])
def crear_act(p_id):
    p = PROYECTOS_DB.get(p_id)
    if p:
        nombre_act = request.form["nombre"]
        descripcion_act = request.form.get("descripcion", "")
        presupuesto_tentativo = float(request.form.get("presupuesto_tentativo", 0.0))
        
        p["actividades"].append({
            "id": str(uuid.uuid4())[:6], 
            "nombre": nombre_act, 
            "descripcion": descripcion_act,
            "presupuesto_tentativo": presupuesto_tentativo,
            "estado": "Pendiente",
            "fecha_inicio": None, 
            "fecha_fin": None, 
            "recursos": []
        })
        
        guardar_proyecto_en_sheets(p_id, p)
        flash(f"Actividad '{nombre_act}' guardada como Pendiente en el Kanban.", "success")
    return redirect(url_for("index", id=p_id, tab="kanban"))

@app.route("/actividades/<p_id>/<act_id>/editar", methods=["POST"])
def editar_act(p_id, act_id):
    """Permite editar los detalles de la actividad (Presupuesto tentativo, Nombre, Descripción)"""
    p = PROYECTOS_DB.get(p_id)
    if p:
        actividad = next((act for act in p["actividades"] if act["id"] == act_id), None)
        if actividad:
            actividad["nombre"] = request.form["nombre"]
            actividad["presupuesto_tentativo"] = float(request.form["presupuesto_tentativo"])
            actividad["descripcion"] = request.form.get("descripcion", "")
            
            guardar_proyecto_en_sheets(p_id, p)
            flash(f"Actividad '{actividad['nombre']}' actualizada correctamente.", "success")
            
    tab = request.args.get("tab", "resumen")
    return redirect(url_for("index", id=p_id, tab=tab))

@app.route("/actividades/<p_id>/<act_id>/eliminar", methods=["GET"])
def eliminar_act(p_id, act_id):
    p = PROYECTOS_DB.get(p_id)
    if p:
        actividad = next((act for act in p["actividades"] if act["id"] == act_id), None)
        if actividad:
            for r in actividad["recursos"]:
                pool_item = next((pi for pi in p.get("recursos_pool", []) if pi["id"] == r.get("pool_id")), None)
                if pool_item:
                    if r["tipo"] == "mano_de_obra":
                        pool_item["monto_disponible"] += r["monto"]
                    else:
                        pool_item["cantidad_disponible"] += r["cantidad"]
                        
        p["actividades"] = [act for act in p["actividades"] if act["id"] != act_id]
        guardar_proyecto_en_sheets(p_id, p)
        flash("Actividad removida y sus recursos liberados al pool.", "success")
        
    tab = request.args.get("tab", "resumen")
    return redirect(url_for("index", id=p_id, tab=tab))

@app.route("/actividades/<p_id>/<act_id>/estado-kanban", methods=["POST"])
def cambiar_estado_kanban(p_id, act_id):
    p = PROYECTOS_DB.get(p_id)
    if p:
        for act in p["actividades"]:
            if act["id"] == act_id:
                nuevo_estado = request.form.get("nuevo_estado")
                
                if nuevo_estado == "Pendiente":
                    act["estado"] = "Pendiente"
                    act["fecha_inicio"] = None
                    act["fecha_fin"] = None
                elif nuevo_estado == "Iniciada":
                    act["estado"] = "Iniciada"
                    act["fecha_inicio"] = request.form.get("f_ini") or datetime.now().strftime("%Y-%m-%d")
                    act["fecha_fin"] = None
                elif nuevo_estado == "Completada":
                    act["estado"] = "Completada"
                    act["fecha_inicio"] = request.form.get("f_ini") or datetime.now().strftime("%Y-%m-%d")
                    act["fecha_fin"] = request.form.get("f_fin") or datetime.now().strftime("%Y-%m-%d")
                    
                guardar_proyecto_en_sheets(p_id, p)
                flash(f"Actividad '{act['nombre']}' movida a {nuevo_estado}.", "success")
                break
    return redirect(url_for("index", id=p_id, tab="kanban"))

@app.route("/recursos/<p_id>/<act_id>", methods=["POST"])
def add_rec(p_id, act_id):
    p = PROYECTOS_DB.get(p_id)
    if p:
        pool_id = request.form.get("pool_id")
        pool_item = next((r for r in p.get("recursos_pool", []) if r["id"] == pool_id), None)
        
        if not pool_item:
            flash("El recurso seleccionado no existe en el inventario general.", "error")
            return redirect(url_for("index", id=p_id, tab="resumen"))
            
        if pool_item["tipo"] == "mano_de_obra":
            monto_solicitado = float(request.form.get("monto", 0.0))
            fecha_pago = request.form.get("fecha_pago")
            
            if monto_solicitado > pool_item["monto_disponible"]:
                flash(f"Fondos insuficientes. Disponible: ${pool_item['monto_disponible']:,.2f}", "error")
                return redirect(url_for("index", id=p_id, tab="resumen"))
                
            pool_item["monto_disponible"] -= monto_solicitado
            
            for act in p["actividades"]:
                if act["id"] == act_id:
                    act["recursos"].append({
                        "id": str(uuid.uuid4())[:6],
                        "pool_id": pool_id,
                        "nombre": pool_item["nombre"],
                        "tipo": "mano_de_obra",
                        "monto": monto_solicitado,
                        "fecha_pago": fecha_pago
                    })
                    flash(f"Pago de mano de obra imputado por ${monto_solicitado:,.2f}.", "success")
                    break
        else:
            cantidad_solicitada = int(request.form.get("cantidad", 1))
            if cantidad_solicitada > pool_item["cantidad_disponible"]:
                flash(f"Stock físico insuficiente. Disponible: {pool_item['cantidad_disponible']}", "error")
                return redirect(url_for("index", id=p_id, tab="resumen"))
                
            pool_item["cantidad_disponible"] -= cantidad_solicitada
            
            for act in p["actividades"]:
                if act["id"] == act_id:
                    existente = next((r for r in act["recursos"] if r.get("pool_id") == pool_id), None)
                    if existente:
                        existente["cantidad"] += cantidad_solicitada
                    else:
                        act["recursos"].append({
                            "id": str(uuid.uuid4())[:6],
                            "pool_id": pool_id,
                            "nombre": pool_item["nombre"],
                            "tipo": "material",
                            "precio": pool_item["precio"],
                            "cantidad": cantidad_solicitada
                        })
                    flash(f"Asignado(s) {cantidad_solicitada} de '{pool_item['nombre']}' a la actividad.", "success")
                    break
                    
        guardar_proyecto_en_sheets(p_id, p)
                    
    tab = request.args.get("tab", "resumen")
    return redirect(url_for("index", id=p_id, tab=tab))

@app.route("/recursos/<p_id>/<act_id>/<rec_id>/editar", methods=["POST"])
def editar_rec_asignado(p_id, act_id, rec_id):
    """Permite editar la asignación de un recurso (cantidad física o monto de dinero)"""
    p = PROYECTOS_DB.get(p_id)
    if p:
        actividad = next((act for act in p["actividades"] if act["id"] == act_id), None)
        if actividad:
            recurso_act = next((r for r in actividad["recursos"] if r["id"] == rec_id), None)
            if recurso_act:
                pool_id = recurso_act.get("pool_id")
                pool_item = next((r for r in p.get("recursos_pool", []) if r["id"] == pool_id), None)
                
                if pool_item:
                    if recurso_act["tipo"] == "mano_de_obra":
                        monto_actual = float(recurso_act["monto"])
                        nuevo_monto = float(request.form["monto"])
                        fecha_pago = request.form.get("fecha_pago")
                        
                        # Simular devolución temporal para validar el saldo del pool
                        monto_maximo_disponible = pool_item["monto_disponible"] + monto_actual
                        if nuevo_monto > monto_maximo_disponible:
                            flash(f"Fondos insuficientes en el Pool. Máximo disponible: ${monto_maximo_disponible:,.2f}", "error")
                        else:
                            pool_item["monto_disponible"] = monto_maximo_disponible - nuevo_monto
                            recurso_act["monto"] = nuevo_monto
                            recurso_act["fecha_pago"] = fecha_pago
                            flash("Pago de mano de obra actualizado de forma exitosa.", "success")
                    else:
                        cantidad_actual = int(recurso_act["cantidad"])
                        nueva_cantidad = int(request.form["cantidad"])
                        
                        # Simular devolución temporal del stock de insumo
                        stock_maximo_disponible = pool_item["cantidad_disponible"] + cantidad_actual
                        if nueva_cantidad > stock_maximo_disponible:
                            flash(f"Stock de insumo insuficiente en el Pool. Máximo disponible: {stock_maximo_disponible} unidades", "error")
                        else:
                            pool_item["cantidad_disponible"] = stock_maximo_disponible - nueva_cantidad
                            recurso_act["cantidad"] = nueva_cantidad
                            flash("Cantidad de insumo asignada actualizada de forma exitosa.", "success")
                else:
                    flash("El recurso seleccionado ya no existe en el inventario general.", "error")
                    
            guardar_proyecto_en_sheets(p_id, p)
            
    tab = request.args.get("tab", "resumen")
    return redirect(url_for("index", id=p_id, tab=tab))

@app.route("/recursos/<p_id>/<act_id>/<rec_id>/eliminar", methods=["GET"])
def eliminar_rec(p_id, act_id, rec_id):
    p = PROYECTOS_DB.get(p_id)
    if p:
        for act in p["actividades"]:
            if act["id"] == act_id:
                recurso_act = next((r for r in act["recursos"] if r["id"] == rec_id), None)
                if recurso_act:
                    pool_id = recurso_act.get("pool_id")
                    pool_item = next((r for r in p.get("recursos_pool", []) if r["id"] == pool_id), None)
                    if pool_item:
                        if recurso_act["tipo"] == "mano_de_obra":
                            pool_item["monto_disponible"] += recurso_act["monto"]
                        else:
                            pool_item["cantidad_disponible"] += recurso_act["cantidad"]
                    
                    act["recursos"] = [r for r in act["recursos"] if r["id"] != rec_id]
                    guardar_proyecto_en_sheets(p_id, p)
                    flash("Recurso desvinculado. El stock/saldo ha sido devuelto al pool.", "success")
                    break
                    
    tab = request.args.get("tab", "resumen")
    return redirect(url_for("index", id=p_id, tab=tab))

if __name__ == "__main__":
    app.run(debug=True)
