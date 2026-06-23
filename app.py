# -*- coding: utf-8 -*-
from flask import Flask, render_template_string, request, redirect, url_for, flash
import uuid
import re
from datetime import datetime

app = Flask(__name__)
app.secret_key = "clave_gerencial_proyectos_2024"

# Base de datos en memoria optimizada con el nuevo flujo de Inventario de Recursos
PROYECTOS_DB = {
    "demo": {
        "id": "demo",
        "nombre": "Proyecto de Infraestructura Vial",
        "descripcion": "Ampliación de carril y modernización de señalética vial.",
        "presupuesto": 250000.0,
        "fecha_inicio": "2024-01-15",
        "fecha_fin_tentativa": "2024-08-30",
        # Pool General de Recursos del Proyecto
        "recursos_pool": [
            {"id": "rp-1", "nombre": "Equipo de Topógrafos", "tipo": "mano_de_obra", "precio": 1500.0, "cantidad_total": 5, "cantidad_disponible": 3},
            {"id": "rp-2", "nombre": "Alquiler Estación Total", "tipo": "material", "precio": 450.0, "cantidad_total": 20, "cantidad_disponible": 10},
            {"id": "rp-3", "nombre": "Operadores de Maquinaria", "tipo": "mano_de_obra", "precio": 120.0, "cantidad_total": 100, "cantidad_disponible": 50},
            {"id": "rp-4", "nombre": "Combustible Diesel (Gals)", "tipo": "material", "precio": 5.5, "cantidad_total": 2000, "cantidad_disponible": 800}
        ],
        "actividades": [
            {
                "id": "act-1",
                "nombre": "Topografía y Nivelación",
                "descripcion": "Estudio de suelos y marcado de límites de vía.",
                "estado": "Completada",
                "fecha_inicio": "2024-01-20",
                "fecha_fin": "2024-02-15",
                "recursos": [
                    {"id": "r1", "pool_id": "rp-1", "nombre": "Equipo de Topógrafos", "tipo": "mano_de_obra", "precio": 1500.0, "cantidad": 2},
                    {"id": "r2", "pool_id": "rp-2", "nombre": "Alquiler Estación Total", "tipo": "material", "precio": 450.0, "cantidad": 10}
                ]
            },
            {
                "id": "act-2",
                "nombre": "Remoción de Capa Asfáltica",
                "descripcion": "Demolición de asfalto antiguo mediante fresado.",
                "estado": "Iniciada",
                "fecha_inicio": "2024-03-01",
                "fecha_fin": None,
                "recursos": [
                    {"id": "r3", "pool_id": "rp-3", "nombre": "Operadores de Maquinaria", "tipo": "mano_de_obra", "precio": 120.0, "cantidad": 50},
                    {"id": "r4", "pool_id": "rp-4", "nombre": "Combustible Diesel (Gals)", "tipo": "material", "precio": 5.5, "cantidad": 1200}
                ]
            },
            {
                "id": "act-3",
                "nombre": "Estudio de Impacto Ambiental",
                "descripcion": "Evaluación de ecosistemas colindantes.",
                "estado": "Pendiente",
                "fecha_inicio": None,
                "fecha_fin": None,
                "recursos": []
            }
        ]
    }
}

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
    
    # Declaración básica de Mermaid GANTT
    gantt_code = "gantt\ndateFormat YYYY-MM-DD\ntitle Cronograma de Actividades\nsection Actividades Activas\n"
    
    for act in proyecto["actividades"]:
        # El costo de la actividad se calcula de sus recursos asignados
        costo_act = sum(float(r["precio"]) * float(r["cantidad"]) for r in act["recursos"])
        gasto_total += costo_act
        
        # Conteo para Kanban y métricas
        if act["estado"] == "Completada": 
            completadas += 1
        elif act["estado"] == "Iniciada": 
            iniciadas += 1
        
        # SOLAMENTE graficamos en GANTT si tiene fecha de inicio y NO está Pendiente
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
        "has_gantt_tasks": has_gantt_tasks
    }

INDEX_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8"><title>Control Proyectos v2.2</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({ startOnLoad: true, theme: 'neutral' });
    </script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body class="bg-slate-100 font-sans text-slate-800">
    <nav class="bg-slate-900 text-white p-4 shadow-xl">
        <div class="max-w-7xl mx-auto flex justify-between items-center">
            <h1 class="text-xl font-bold flex items-center gap-2">
                <i class="fa-solid fa-chart-line text-emerald-400"></i> Gestor Gerencial de Proyectos
            </h1>
            <div class="text-xs text-slate-400">v2.2 | Kanban, Inventario Centralizado & GANTT</div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto p-6">
        
        <!-- Notificaciones Flash -->
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="p-4 mb-6 text-sm rounded-xl flex items-center justify-between {% if category == 'error' %}bg-rose-100 text-rose-800 border border-rose-200{% else %}bg-emerald-100 text-emerald-800 border border-emerald-200{% endif %}">
                        <span class="font-medium">{{ message }}</span>
                        <button onclick="this.parentElement.style.display='none'" class="text-lg font-bold focus:outline-none">&times;</button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <!-- Sidebar Proyectos -->
            <aside class="lg:col-span-1 space-y-6">
                <div class="bg-white p-6 rounded-2xl shadow-sm border">
                    <h2 class="font-bold mb-4 text-slate-800 flex items-center gap-2">
                        <i class="fa-solid fa-folder-plus text-indigo-600"></i> Crear Proyecto
                    </h2>
                    <form action="/proyectos" method="POST" class="space-y-3 text-sm">
                        <input type="text" name="nombre" placeholder="Nombre Proyecto" class="w-full p-2.5 border rounded-lg" required>
                        <input type="number" name="presupuesto" placeholder="Presupuesto $" class="w-full p-2.5 border rounded-lg" required>
                        <div class="grid grid-cols-2 gap-2">
                            <div>
                                <label class="text-[10px] font-bold text-slate-400">FECHA INICIO</label>
                                <input type="date" name="fecha_inicio" class="w-full p-1.5 border rounded" required>
                            </div>
                            <div>
                                <label class="text-[10px] font-bold text-slate-400">FIN (TENTATIVO)</label>
                                <input type="date" name="fecha_fin" class="w-full p-1.5 border rounded" required>
                            </div>
                        </div>
                        <button class="w-full bg-indigo-600 hover:bg-indigo-700 text-white py-2.5 rounded-lg font-bold transition">Crear</button>
                    </form>
                </div>
                <div class="space-y-2">
                    <h3 class="text-xs font-bold uppercase text-slate-400 tracking-wider px-2">Listado de Proyectos</h3>
                    {% for p_id, p in proyectos.items() %}
                    <a href="/?id={{p_id}}" class="block p-4 bg-white border rounded-xl hover:border-indigo-500 transition shadow-sm {% if proyecto and proyecto.id == p_id %}border-indigo-500 bg-indigo-50/30{% endif %}">
                        <div class="font-bold text-slate-700 text-sm">{{p.nombre}}</div>
                        <div class="text-[10px] text-slate-500 mt-1">Límite: {{p.fecha_fin_tentativa}}</div>
                    </a>
                    {% endfor %}
                </div>
            </aside>

            <!-- Contenido Central -->
            <section class="lg:col-span-3 space-y-6">
                {% if not proyecto %}
                    <div class="bg-white p-20 text-center rounded-3xl border-2 border-dashed text-slate-400">
                        <i class="fa-solid fa-arrow-pointer text-4xl mb-3"></i>
                        <p class="text-lg font-bold">Selecciona o crea un proyecto para ver el Resumen Gerencial</p>
                    </div>
                {% else %}
                    <!-- Resumen Gerencial Card -->
                    <div class="bg-slate-900 text-white p-8 rounded-3xl shadow-2xl relative overflow-hidden">
                        <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
                            <div>
                                <h2 class="text-3xl font-bold">{{proyecto.nombre}}</h2>
                                <p class="text-slate-400 text-sm mt-1">Rango Planificado: <span class="text-emerald-400 font-semibold">{{proyecto.fecha_inicio}}</span> hasta <span class="text-emerald-400 font-semibold">{{proyecto.fecha_fin_tentativa}}</span></p>
                            </div>
                            <div class="flex flex-col items-end gap-2">
                                <div class="bg-slate-800 px-4 py-2 rounded-xl text-right">
                                    <span class="text-xs uppercase text-slate-500 font-bold block">Presupuesto General</span>
                                    <div class="text-2xl font-black text-emerald-400">${{"{:,.2f}".format(proyecto.presupuesto)}}</div>
                                </div>
                                <a href="/proyectos/{{proyecto.id}}/eliminar" 
                                   onclick="return confirm('¿Estás seguro de que deseas eliminar este proyecto junto con todas sus actividades y recursos de forma permanente?')" 
                                   class="text-xs font-semibold text-rose-400 hover:text-rose-300 transition flex items-center gap-1.5 bg-rose-950/40 px-3 py-1.5 rounded-lg border border-rose-800">
                                    <i class="fa-solid fa-trash-can"></i> Eliminar Proyecto
                                </a>
                            </div>
                        </div>

                        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 pt-6 border-t border-slate-800">
                            <div class="bg-slate-800/40 p-4 rounded-2xl border border-slate-700/60">
                                <div class="text-xs text-slate-400 mb-1 font-semibold uppercase">GASTO EJECUTADO</div>
                                <div class="text-xl font-bold text-white">${{"{:,.2f}".format(m.gasto_total)}}</div>
                                <div class="w-full bg-slate-700 h-1.5 rounded-full mt-2 overflow-hidden">
                                    <div class="bg-emerald-500 h-1.5 rounded-full" style="width: {{m.porcentaje_gasto}}%"></div>
                                </div>
                            </div>
                            <div class="bg-slate-800/40 p-4 rounded-2xl border border-slate-700/60">
                                <div class="text-xs text-slate-400 mb-1 font-semibold uppercase">DISPONIBLE</div>
                                <div class="text-xl font-bold {% if m.disponible < 0 %}text-rose-400{% else %}text-emerald-400{% endif %}">
                                    ${{"{:,.2f}".format(m.disponible)}}
                                </div>
                            </div>
                            <div class="bg-slate-800/40 p-4 rounded-2xl border border-slate-700/60 text-center flex flex-col justify-center">
                                <div class="text-xs text-slate-400 mb-1 font-semibold uppercase">AVANCE FÍSICO</div>
                                <div class="text-2xl font-black text-indigo-400">{{ "{:.1f}%".format(m.porcentaje_avance) }}</div>
                                <div class="text-[10px] text-slate-500 font-bold">({{ m.conteo.completas }} de {{ proyecto.actividades|length }} completadas)</div>
                            </div>
                        </div>
                    </div>

                    <!-- Panel de Inventario de Recursos (General Pool) -->
                    <div class="bg-white p-6 rounded-3xl border shadow-sm">
                        <div class="flex justify-between items-center mb-4">
                            <h3 class="font-bold text-slate-800 flex items-center gap-2">
                                <i class="fa-solid fa-boxes-stacked text-amber-500"></i> Inventario General del Proyecto
                            </h3>
                            <button onclick="document.getElementById('modal-pool').style.display='flex'" class="text-xs font-bold bg-amber-500 hover:bg-amber-600 text-white px-3 py-1.5 rounded-lg transition shadow-md">
                                <i class="fa-solid fa-plus-circle"></i> Agregar Recurso General
                            </button>
                        </div>
                        <p class="text-xs text-slate-500 mb-3">Todos los materiales y servicios de mano de obra se registran aquí primero. Luego los descuentas al asignarlos a las actividades.</p>
                        
                        <div class="overflow-x-auto">
                            <table class="w-full text-xs text-left">
                                <thead>
                                    <tr class="text-slate-400 border-b font-semibold uppercase">
                                        <th class="pb-2">Recurso</th>
                                        <th class="pb-2">Clasificación</th>
                                        <th class="pb-2 text-right">Precio Unitario</th>
                                        <th class="pb-2 text-center">Stock Total</th>
                                        <th class="pb-2 text-center">Disponible</th>
                                        <th class="pb-2 text-center">Eliminar</th>
                                    </tr>
                                </thead>
                                <tbody class="divide-y divide-slate-100">
                                    {% if not proyecto.recursos_pool %}
                                        <tr>
                                            <td colspan="6" class="py-4 text-center text-slate-400 italic">No hay recursos agregados al pool general.</td>
                                        </tr>
                                    {% else %}
                                        {% for r in proyecto.recursos_pool %}
                                        <tr class="text-slate-700">
                                            <td class="py-2.5 font-semibold text-slate-900">{{r.nombre}}</td>
                                            <td class="py-2.5">
                                                {% if r.tipo == 'mano_de_obra' %}
                                                    <span class="bg-amber-50 text-amber-700 px-2 py-0.5 rounded border border-amber-200">Mano de Obra</span>
                                                {% else %}
                                                    <span class="bg-blue-50 text-blue-700 px-2 py-0.5 rounded border border-blue-200">Material</span>
                                                {% endif %}
                                            </td>
                                            <td class="py-2.5 text-right font-medium">${{"{:,.2f}".format(r.precio)}}</td>
                                            <td class="py-2.5 text-center font-bold text-slate-700">{{r.cantidad_total}}</td>
                                            <td class="py-2.5 text-center">
                                                <span class="px-2 py-0.5 rounded-full text-xs font-bold {% if r.cantidad_disponible > 0 %}bg-emerald-100 text-emerald-800{% else %}bg-rose-100 text-rose-800{% endif %}">
                                                    {{r.cantidad_disponible}}
                                                </span>
                                            </td>
                                            <td class="py-2.5 text-center">
                                                <a href="/proyectos/{{proyecto.id}}/recursos-pool/{{r.id}}/eliminar" 
                                                   onclick="return confirm('¿Seguro que deseas eliminar este recurso del inventario general?')"
                                                   class="text-rose-500 hover:text-rose-700">
                                                    <i class="fa-solid fa-trash"></i>
                                                </a>
                                            </td>
                                        </tr>
                                        {% endfor %}
                                    {% endif %}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Diagrama de GANTT -->
                    <div class="bg-white p-6 rounded-3xl border shadow-sm">
                        <h3 class="font-bold text-slate-800 mb-4 flex items-center gap-2"><i class="fa-solid fa-stream text-indigo-500"></i> Cronograma GANTT</h3>
                        {% if m.has_gantt_tasks %}
                            <div class="mermaid overflow-x-auto bg-slate-50 p-4 rounded-xl">
                                {{ m.gantt_code|safe }}
                            </div>
                        {% else %}
                            <div class="text-center py-8 text-slate-400 text-sm italic bg-slate-50 rounded-xl border border-dashed">
                                Las actividades pendientes no se grafican. Inicia o finaliza al menos una actividad con fecha para visualizar su cronograma.
                            </div>
                        {% endif %}
                    </div>

                    <!-- Tablero KANBAN -->
                    <div class="space-y-4">
                        <div class="flex justify-between items-center">
                            <h3 class="font-bold text-slate-800 text-lg flex items-center gap-2">
                                <i class="fa-solid fa-table-columns text-indigo-600"></i> Tablero Kanban de Actividades
                            </h3>
                            <button onclick="document.getElementById('modal-act').style.display='flex'" class="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-xl text-sm font-bold shadow-lg transition">+ Agregar Actividad</button>
                        </div>

                        <!-- Grid Kanban de 3 Columnas -->
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                            
                            <!-- Columna: PENDIENTES -->
                            <div class="bg-slate-200/60 p-4 rounded-2xl border border-slate-300/40 flex flex-col min-h-[350px]">
                                <div class="flex justify-between items-center mb-3 border-b border-slate-300/60 pb-2">
                                    <span class="font-bold text-slate-700 flex items-center gap-1.5"><span class="w-3 h-3 bg-slate-400 rounded-full"></span> Pendientes</span>
                                    <span class="bg-slate-300 text-slate-700 text-xs font-bold px-2 py-0.5 rounded-full">{{ m.conteo.pendientes }}</span>
                                </div>
                                <div class="space-y-3 flex-grow overflow-y-auto max-h-[500px]">
                                    {% for act in proyecto.actividades %}
                                        {% if act.estado == 'Pendiente' %}
                                            <div class="bg-white p-4 rounded-xl shadow-sm border border-slate-200/80 space-y-2 relative">
                                                <h4 class="font-bold text-slate-900 text-sm">{{ act.nombre }}</h4>
                                                <p class="text-[11px] text-slate-500 line-clamp-2">{{ act.descripcion or 'Sin descripción.' }}</p>
                                                <div class="flex justify-between items-center pt-2">
                                                    <span class="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-bold">Sin Fechas</span>
                                                    <!-- Trigger para transicionar estado -->
                                                    <button onclick="openTransition('{{ act.id }}', '{{ act.nombre }}', '{{ act.estado }}', '{{ act.fecha_inicio }}', '{{ act.fecha_fin }}')" class="text-xs text-indigo-600 hover:text-indigo-800 font-bold">
                                                        Cambiar Estado <i class="fa-solid fa-angle-right"></i>
                                                    </button>
                                                </div>
                                            </div>
                                        {% endif %}
                                    {% endfor %}
                                </div>
                            </div>

                            <!-- Columna: INICIADAS -->
                            <div class="bg-blue-100/60 p-4 rounded-2xl border border-blue-200/40 flex flex-col min-h-[350px]">
                                <div class="flex justify-between items-center mb-3 border-b border-blue-300/60 pb-2">
                                    <span class="font-bold text-blue-800 flex items-center gap-1.5"><span class="w-3 h-3 bg-blue-500 rounded-full"></span> En Curso</span>
                                    <span class="bg-blue-200 text-blue-800 text-xs font-bold px-2 py-0.5 rounded-full">{{ m.conteo.iniciadas }}</span>
                                </div>
                                <div class="space-y-3 flex-grow overflow-y-auto max-h-[500px]">
                                    {% for act in proyecto.actividades %}
                                        {% if act.estado == 'Iniciada' %}
                                            <div class="bg-white p-4 rounded-xl shadow-sm border border-blue-200 space-y-2 relative">
                                                <h4 class="font-bold text-slate-900 text-sm">{{ act.nombre }}</h4>
                                                <p class="text-[11px] text-slate-500 line-clamp-2">{{ act.descripcion or 'Sin descripción.' }}</p>
                                                <div class="text-[10px] text-slate-500">
                                                    Inicio: <strong class="text-slate-800">{{ act.fecha_inicio }}</strong>
                                                </div>
                                                <div class="flex justify-between items-center pt-2">
                                                    <span class="text-[10px] bg-blue-50 text-blue-700 px-2 py-0.5 rounded font-bold">{{ act.recursos|length }} Recursos</span>
                                                    <button onclick="openTransition('{{ act.id }}', '{{ act.nombre }}', '{{ act.estado }}', '{{ act.fecha_inicio }}', '{{ act.fecha_fin }}')" class="text-xs text-indigo-600 hover:text-indigo-800 font-bold">
                                                        Cambiar Estado <i class="fa-solid fa-angle-right"></i>
                                                    </button>
                                                </div>
                                            </div>
                                        {% endif %}
                                    {% endfor %}
                                </div>
                            </div>

                            <!-- Columna: FINALIZADAS -->
                            <div class="bg-emerald-100/60 p-4 rounded-2xl border border-emerald-200/40 flex flex-col min-h-[350px]">
                                <div class="flex justify-between items-center mb-3 border-b border-emerald-300/60 pb-2">
                                    <span class="font-bold text-emerald-800 flex items-center gap-1.5"><span class="w-3 h-3 bg-emerald-500 rounded-full"></span> Finalizadas</span>
                                    <span class="bg-emerald-200 text-emerald-800 text-xs font-bold px-2 py-0.5 rounded-full">{{ m.conteo.completas }}</span>
                                </div>
                                <div class="space-y-3 flex-grow overflow-y-auto max-h-[500px]">
                                    {% for act in proyecto.actividades %}
                                        {% if act.estado == 'Completada' %}
                                            <div class="bg-white p-4 rounded-xl shadow-sm border border-emerald-200 space-y-2 relative">
                                                <h4 class="font-bold text-slate-900 text-sm">{{ act.nombre }}</h4>
                                                <p class="text-[11px] text-slate-500 line-clamp-2">{{ act.descripcion or 'Sin descripción.' }}</p>
                                                <div class="text-[10px] text-slate-500">
                                                    Desde: <strong class="text-slate-700">{{ act.fecha_inicio }}</strong> hasta <strong class="text-slate-700">{{ act.fecha_fin }}</strong>
                                                </div>
                                                <div class="flex justify-between items-center pt-2">
                                                    <span class="text-[10px] bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded font-bold">{{ act.recursos|length }} Recursos</span>
                                                    <button onclick="openTransition('{{ act.id }}', '{{ act.nombre }}', '{{ act.estado }}', '{{ act.fecha_inicio }}', '{{ act.fecha_fin }}')" class="text-xs text-indigo-600 hover:text-indigo-800 font-bold">
                                                        Cambiar Estado <i class="fa-solid fa-angle-right"></i>
                                                    </button>
                                                </div>
                                            </div>
                                        {% endif %}
                                    {% endfor %}
                                </div>
                            </div>

                        </div>
                    </div>

                    <!-- Detalle de Actividades (Gestión de Recursos por Actividad) -->
                    <div class="space-y-4 pt-4">
                        <h3 class="font-bold text-slate-800 text-lg flex items-center gap-2">
                            <i class="fa-solid fa-gears text-indigo-600"></i> Desglose Físico y Costos de Actividades
                        </h3>
                        {% if not proyecto.actividades %}
                            <div class="bg-white p-12 text-center rounded-2xl border border-dashed text-slate-400">
                                Aún no hay actividades en este proyecto.
                            </div>
                        {% else %}
                            {% for act in proyecto.actividades %}
                            <div class="bg-white rounded-2xl border shadow-sm overflow-hidden hover:shadow transition">
                                <div class="p-4 bg-slate-50 border-b flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                                    <div>
                                        <div class="flex items-center gap-2">
                                            <span class="text-[10px] font-black uppercase px-2 py-0.5 rounded-full {% if act.estado == 'Completada' %}bg-emerald-100 text-emerald-700{% elif act.estado == 'Iniciada' %}bg-blue-100 text-blue-700{% else %}bg-slate-200 text-slate-600{% endif %}">
                                                {{act.estado}}
                                            </span>
                                            <span class="text-[11px] font-medium text-slate-500">
                                                {% if act.fecha_inicio %}
                                                    Inicio: <strong class="text-slate-700">{{ act.fecha_inicio }}</strong> 
                                                    {% if act.fecha_fin %}| Fin: <strong class="text-slate-700">{{ act.fecha_fin }}</strong>{% endif %}
                                                {% else %}
                                                    Sin planificación de fechas asignadas.
                                                {% endif %}
                                            </span>
                                        </div>
                                        <h4 class="font-bold text-slate-800 text-base mt-1.5">{{act.nombre}}</h4>
                                    </div>
                                    <div class="flex items-center gap-2.5 w-full sm:w-auto justify-end">
                                        <!-- Botón para asignar recurso disponible del Pool -->
                                        <button onclick="openRecurso('{{act.id}}', '{{act.nombre}}')" class="bg-indigo-50 hover:bg-indigo-100 text-indigo-600 p-2 rounded-lg transition flex items-center gap-1 text-xs font-bold" title="Asignar Recurso de Inventario">
                                            <i class="fa-solid fa-plus-circle text-base"></i> Asignar Recurso
                                        </button>
                                        <a href="/actividades/{{proyecto.id}}/{{act.id}}/eliminar" 
                                           onclick="return confirm('¿Seguro que deseas eliminar esta actividad por completo?')" 
                                           class="bg-rose-50 hover:bg-rose-100 text-rose-600 p-2 rounded-lg transition" title="Eliminar Actividad">
                                            <i class="fa-solid fa-trash-can text-base"></i>
                                        </a>
                                    </div>
                                </div>
                                <div class="p-4">
                                    <table class="w-full text-xs text-left">
                                        <thead>
                                            <tr class="text-slate-400 border-b font-semibold uppercase">
                                                <th class="pb-2">Recurso / Insumo</th>
                                                <th class="pb-2">Clasificación</th>
                                                <th class="pb-2 text-right">Cantidad Asignada</th>
                                                <th class="pb-2 text-right">Precio unitario</th>
                                                <th class="pb-2 text-right">Costo Total</th>
                                                <th class="pb-2 text-center">Desvincular (Devolver al Pool)</th>
                                            </tr>
                                        </thead>
                                        <tbody class="divide-y divide-slate-100">
                                            {% if not act.recursos %}
                                                <tr>
                                                    <td colspan="6" class="py-4 text-center text-slate-400 italic">No hay recursos ni mano de obra asignada a esta actividad. Usa el botón "Asignar Recurso" para consumir del inventario.</td>
                                                </tr>
                                            {% else %}
                                                {% for r in act.recursos %}
                                                <tr class="text-slate-700">
                                                    <td class="py-2.5 font-medium text-slate-900">{{r.nombre}}</td>
                                                    <td class="py-2.5">
                                                        {% if r.tipo == 'mano_de_obra' %}
                                                            <span class="bg-amber-50 text-amber-700 px-2 py-0.5 rounded border border-amber-200">Mano de Obra</span>
                                                        {% else %}
                                                            <span class="bg-blue-50 text-blue-700 px-2 py-0.5 rounded border border-blue-200">Material</span>
                                                        {% endif %}
                                                    </td>
                                                    <td class="py-2.5 text-right font-semibold text-slate-900">{{r.cantidad}}</td>
                                                    <td class="py-2.5 text-right font-medium">${{"{:,.2f}".format(r.precio)}}</td>
                                                    <td class="py-2.5 text-right font-bold text-slate-900">${{"{:,.2f}".format(r.precio * r.cantidad)}}</td>
                                                    <td class="py-2.5 text-center">
                                                        <a href="/recursos/{{proyecto.id}}/{{act.id}}/{{r.id}}/eliminar" 
                                                           onclick="return confirm('¿Deseas remover este recurso de la actividad? Las unidades regresarán al stock disponible del pool general.')" 
                                                           class="text-rose-500 hover:text-rose-700 transition" title="Remover e Incrementar Stock Pool">
                                                            <i class="fa-solid fa-trash-arrow-up text-base"></i> Devolver
                                                        </a>
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
                {% endif %}
            </section>
        </div>
    </main>

    <!-- Modal: Nueva Actividad -->
    <div id="modal-act" class="fixed inset-0 bg-black/60 hidden items-center justify-center p-4 z-50 backdrop-blur-sm">
        <div class="bg-white p-8 rounded-3xl max-w-md w-full shadow-2xl animate-in fade-in duration-200">
            <h3 class="text-xl font-bold mb-4 text-slate-900 flex items-center gap-2">
                <i class="fa-solid fa-diagram-project text-indigo-600"></i> Agregar Nueva Actividad
            </h3>
            <p class="text-xs text-slate-500 mb-4">La actividad se agregará en estado "Pendiente" por defecto, ideal para legalizar posteriormente.</p>
            <form action="/actividades/{{proyecto.id if proyecto else ''}}" method="POST" class="space-y-4 text-sm">
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Nombre de la actividad</label>
                    <input type="text" name="nombre" placeholder="Ej. Instalaciones Sanitarias" class="w-full p-2.5 border rounded-xl" required>
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1 font-semibold">Descripción</label>
                    <textarea name="descripcion" placeholder="Alcance general de la tarea..." rows="2" class="w-full p-2.5 border rounded-xl"></textarea>
                </div>
                <div class="flex gap-2 pt-2">
                    <button type="button" onclick="document.getElementById('modal-act').style.display='none'" class="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 py-3 rounded-xl font-bold transition">Cancelar</button>
                    <button class="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white py-3 rounded-xl font-bold shadow-lg transition">Guardar Actividad</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Modal: Transición de Estados (Tablero Kanban) -->
    <div id="modal-transicion" class="fixed inset-0 bg-black/60 hidden items-center justify-center p-4 z-50 backdrop-blur-sm">
        <div class="bg-white p-8 rounded-3xl max-w-md w-full shadow-2xl">
            <h3 class="text-lg font-bold text-slate-900 mb-1">Actualizar Estado de Actividad</h3>
            <p id="trans-target-name" class="text-xs text-indigo-600 font-bold mb-4"></p>
            
            <form id="form-transicion" method="POST" class="space-y-4 text-sm">
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Nuevo Estado</label>
                    <select name="nuevo_estado" id="select-nuevo-estado" class="w-full p-2.5 border rounded-xl" required>
                        <option value="Pendiente">Pendiente (Sin Fechas / Sin Graficar)</option>
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

    <!-- Modal: Agregar Recurso al Inventario General del Proyecto -->
    <div id="modal-pool" class="fixed inset-0 bg-black/60 hidden items-center justify-center p-4 z-50 backdrop-blur-sm">
        <div class="bg-white p-8 rounded-3xl max-w-md w-full shadow-2xl">
            <h3 class="text-xl font-bold mb-4 text-slate-900 flex items-center gap-2">
                <i class="fa-solid fa-boxes-stacked text-amber-500"></i> Registrar Recurso en Inventario
            </h3>
            <form action="/proyectos/{{proyecto.id if proyecto else ''}}/recursos-pool" method="POST" class="space-y-4 text-sm">
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Nombre del Recurso / Material / Servicio</label>
                    <input type="text" name="nombre" placeholder="Ej. Ingeniero Residente, Cemento Portland" class="w-full p-2.5 border rounded-xl" required>
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Clasificación</label>
                    <select name="tipo" class="w-full p-2.5 border rounded-xl" required>
                        <option value="material">Insumo / Material Físico</option>
                        <option value="mano_de_obra">Mano de Obra (Servicios directos)</option>
                    </select>
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Costo Unitario ($)</label>
                        <input type="number" step="0.01" name="precio" placeholder="Precio unitario" class="w-full p-2.5 border rounded-xl" required>
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Cantidad Inicial Adquirida</label>
                        <input type="number" name="cantidad" min="1" value="10" class="w-full p-2.5 border rounded-xl" required>
                    </div>
                </div>
                <div class="flex gap-2 pt-2">
                    <button type="button" onclick="document.getElementById('modal-pool').style.display='none'" class="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 py-3 rounded-xl font-bold transition">Cancelar</button>
                    <button class="flex-1 bg-amber-500 hover:bg-amber-600 text-white py-3 rounded-xl font-bold shadow-lg transition">Adquirir a Inventario</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Modal: Asignar Recurso del Pool a una Actividad -->
    <div id="modal-rec" class="fixed inset-0 bg-black/60 hidden items-center justify-center p-4 z-50 backdrop-blur-sm">
        <div class="bg-white p-8 rounded-3xl max-w-md w-full shadow-2xl">
            <h3 class="text-xl font-bold mb-2 text-slate-900"><i class="fa-solid fa-plus-circle text-indigo-600"></i> Consumir del Inventario</h3>
            <p class="text-xs text-slate-500 mb-4">Asignando recursos a la actividad: <strong id="act-target-name" class="text-slate-800"></strong></p>
            
            <form id="form-rec" method="POST" class="space-y-4 text-sm">
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Seleccionar Recurso del Pool</label>
                    <select name="pool_id" id="select-pool-recurso" class="w-full p-2.5 border rounded-xl" required>
                        <!-- Cargado dinámicamente mediante javascript -->
                    </select>
                </div>
                
                <div class="bg-slate-50 p-3 rounded-lg border border-slate-100 text-xs text-slate-600" id="pool-item-info">
                    Selecciona un recurso para ver su disponibilidad y costo.
                </div>

                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Cantidad a Asignar</label>
                    <input type="number" name="cantidad" id="input-cantidad-rec" min="1" value="1" class="w-full p-2.5 border rounded-xl" required>
                </div>

                <div class="flex gap-2 pt-2">
                    <button type="button" onclick="document.getElementById('modal-rec').style.display='none'" class="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 py-3 rounded-xl font-bold transition">Cancelar</button>
                    <button class="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white py-3 rounded-xl font-bold shadow-lg transition">Asignar Insumo</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Inyectamos los recursos disponibles como un array JSON en el navegador para el JS del modal -->
    <script>
        const recursosPool = {{ proyecto.recursos_pool|tojson|safe if proyecto else '[]' }};
        
        function openRecurso(id, nombre) {
            document.getElementById('act-target-name').innerText = nombre;
            document.getElementById('form-rec').action = "/recursos/{{proyecto.id if proyecto else ''}}/" + id;
            
            const select = document.getElementById('select-pool-recurso');
            const cantidadInput = document.getElementById('input-cantidad-rec');
            const infoText = document.getElementById('pool-item-info');
            
            // Limpiamos las opciones previas
            select.innerHTML = '<option value="">-- Seleccionar del Inventario --</option>';
            
            let count = 0;
            recursosPool.forEach(item => {
                if (item.cantidad_disponible > 0) {
                    const opt = document.createElement('option');
                    opt.value = item.id;
                    opt.textContent = `${item.nombre} (${item.tipo === 'mano_de_obra' ? 'Mano de Obra' : 'Material'}) - Disp: ${item.cantidad_disponible}`;
                    opt.dataset.disponible = item.cantidad_disponible;
                    opt.dataset.precio = item.precio;
                    select.appendChild(opt);
                    count++;
                }
            });
            
            if (count === 0) {
                infoText.innerHTML = '<span class="text-rose-500 font-bold">¡Atención! No hay recursos con unidades disponibles en el inventario general del proyecto. Agrega o libera recursos primero.</span>';
                cantidadInput.disabled = true;
            } else {
                infoText.innerHTML = 'Selecciona un recurso para ver su disponibilidad y costo.';
                cantidadInput.disabled = false;
            }
            
            select.onchange = function() {
                const selectedOpt = select.options[select.selectedIndex];
                if (selectedOpt && selectedOpt.value) {
                    const disp = selectedOpt.dataset.disponible;
                    const precio = selectedOpt.dataset.precio;
                    cantidadInput.max = disp;
                    cantidadInput.value = 1;
                    infoText.innerHTML = `Precio Unitario: <strong class="text-slate-900">$${parseFloat(precio).toFixed(2)}</strong> | Stock Disponible: <strong class="text-slate-900">${disp}</strong>`;
                } else {
                    infoText.innerHTML = 'Selecciona un recurso para ver su disponibilidad y costo.';
                }
            };
            
            document.getElementById('modal-rec').style.display = 'flex';
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
    p_id = request.args.get("id")
    p_actual = PROYECTOS_DB.get(p_id)
    metricas = calcular_metricas(p_actual) if p_actual else {}
    return render_template_string(INDEX_HTML, proyectos=PROYECTOS_DB, proyecto=p_actual, m=metricas)

@app.route("/proyectos", methods=["POST"])
def crear_p():
    id_p = str(uuid.uuid4())[:6]
    PROYECTOS_DB[id_p] = {
        "id": id_p, 
        "nombre": request.form["nombre"], 
        "presupuesto": float(request.form["presupuesto"]),
        "fecha_inicio": request.form["fecha_inicio"], 
        "fecha_fin_tentativa": request.form["fecha_fin"], 
        "recursos_pool": [],
        "actividades": []
    }
    flash(f"Proyecto '{request.form['nombre']}' creado correctamente.", "success")
    return redirect(url_for("index", id=id_p))

@app.route("/proyectos/<p_id>/eliminar", methods=["GET"])
def eliminar_p(p_id):
    if p_id in PROYECTOS_DB:
        nombre = PROYECTOS_DB[p_id]["nombre"]
        del PROYECTOS_DB[p_id]
        flash(f"Se ha eliminado el proyecto '{nombre}' de forma permanente.", "success")
    return redirect(url_for("index"))

# Rutas para el Inventario General (Pool)
@app.route("/proyectos/<p_id>/recursos-pool", methods=["POST"])
def add_recurso_pool(p_id):
    p = PROYECTOS_DB.get(p_id)
    if p:
        nombre = request.form["nombre"]
        tipo = request.form["tipo"]
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
        flash(f"Recurso '{nombre}' añadido al pool general del proyecto.", "success")
    return redirect(url_for("index", id=p_id))

@app.route("/proyectos/<p_id>/recursos-pool/<rp_id>/eliminar")
def eliminar_recurso_pool(p_id, rp_id):
    p = PROYECTOS_DB.get(p_id)
    if p:
        recurso = next((r for r in p.get("recursos_pool", []) if r["id"] == rp_id), None)
        if recurso:
            # Validación: si se han asignado unidades, no se puede eliminar de golpe
            if recurso["cantidad_disponible"] < recurso["cantidad_total"]:
                flash("No se puede eliminar: tiene unidades asignadas en actividades vigentes.", "error")
            else:
                p["recursos_pool"] = [r for r in p["recursos_pool"] if r["id"] != rp_id]
                flash("Recurso eliminado del inventario general.", "success")
    return redirect(url_for("index", id=p_id))

@app.route("/actividades/<p_id>", methods=["POST"])
def crear_act(p_id):
    if p_id in PROYECTOS_DB:
        nombre_act = request.form["nombre"]
        descripcion_act = request.form.get("descripcion", "")
        
        # Una actividad se crea "Pendiente" sin fechas predefinidas
        PROYECTOS_DB[p_id]["actividades"].append({
            "id": str(uuid.uuid4())[:6], 
            "nombre": nombre_act, 
            "descripcion": descripcion_act,
            "estado": "Pendiente",
            "fecha_inicio": None, 
            "fecha_fin": None, 
            "recursos": []
        })
        flash(f"Actividad '{nombre_act}' guardada como Pendiente sin fechas.", "success")
    return redirect(url_for("index", id=p_id))

@app.route("/actividades/<p_id>/<act_id>/eliminar", methods=["GET"])
def eliminar_act(p_id, act_id):
    p = PROYECTOS_DB.get(p_id)
    if p:
        # Primero liberamos los recursos asignados regresándolos al Pool general
        actividad = next((act for act in p["actividades"] if act["id"] == act_id), None)
        if actividad:
            for r in actividad["recursos"]:
                pool_item = next((pi for pi in p.get("recursos_pool", []) if pi["id"] == r.get("pool_id")), None)
                if pool_item:
                    pool_item["cantidad_disponible"] += r["cantidad"]
                    
        p["actividades"] = [act for act in p["actividades"] if act["id"] != act_id]
        flash("Actividad removida y sus recursos asignados devueltos al pool.", "success")
    return redirect(url_for("index", id=p_id))

# Transición avanzada de estados del Kanban
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
                    
                flash(f"Actividad '{act['nombre']}' movida a {nuevo_estado}.", "success")
                break
    return redirect(url_for("index", id=p_id))

# Asignación descontando del Pool general del proyecto
@app.route("/recursos/<p_id>/<act_id>", methods=["POST"])
def add_rec(p_id, act_id):
    p = PROYECTOS_DB.get(p_id)
    if p:
        pool_id = request.form.get("pool_id")
        cantidad_solicitada = int(request.form.get("cantidad", 1))
        
        # Buscar el recurso en el pool general
        pool_item = next((r for r in p.get("recursos_pool", []) if r["id"] == pool_id), None)
        if not pool_item:
            flash("El recurso seleccionado no existe en el inventario general.", "error")
            return redirect(url_for("index", id=p_id))
            
        if cantidad_solicitada > pool_item["cantidad_disponible"]:
            flash(f"Stock insuficiente en el pool general. Disponible: {pool_item['cantidad_disponible']}", "error")
            return redirect(url_for("index", id=p_id))
            
        # Descontar stock del pool general
        pool_item["cantidad_disponible"] -= cantidad_solicitada
        
        # Agregar a la actividad
        for act in p["actividades"]:
            if act["id"] == act_id:
                # Si el recurso ya existía en la actividad, sumamos la cantidad
                existente = next((r for r in act["recursos"] if r.get("pool_id") == pool_id), None)
                if existente:
                    existente["cantidad"] += cantidad_solicitada
                else:
                    act["recursos"].append({
                        "id": str(uuid.uuid4())[:6],
                        "pool_id": pool_id,
                        "nombre": pool_item["nombre"],
                        "tipo": pool_item["tipo"],
                        "precio": pool_item["precio"],
                        "cantidad": cantidad_solicitada
                    })
                flash(f"Asignado(s) {cantidad_solicitada} de '{pool_item['nombre']}' a la actividad.", "success")
                break
    return redirect(url_for("index", id=p_id))

# Desvincular de la actividad e incrementar stock al Pool general
@app.route("/recursos/<p_id>/<act_id>/<rec_id>/eliminar", methods=["GET"])
def eliminar_rec(p_id, act_id, rec_id):
    p = PROYECTOS_DB.get(p_id)
    if p:
        for act in p["actividades"]:
            if act["id"] == act_id:
                recurso_act = next((r for r in act["recursos"] if r["id"] == rec_id), None)
                if recurso_act:
                    pool_id = recurso_act.get("pool_id")
                    cant_retornada = recurso_act["cantidad"]
                    
                    # Devolver stock al pool general
                    pool_item = next((r for r in p.get("recursos_pool", []) if r["id"] == pool_id), None)
                    if pool_item:
                        pool_item["cantidad_disponible"] += cant_retornada
                    
                    # Remover de la actividad
                    act["recursos"] = [r for r in act["recursos"] if r["id"] != rec_id]
                    flash("Recurso liberado de la actividad. Stock incrementado en el pool general.", "success")
                    break
    return redirect(url_for("index", id=p_id))

if __name__ == "__main__":
    app.run(debug=True)
