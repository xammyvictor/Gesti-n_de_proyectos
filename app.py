# -*- coding: utf-8 -*-
from flask import Flask, render_template_string, request, redirect, url_for, flash
import uuid

app = Flask(__name__)
app.secret_key = "clave_secreta_control_proyectos_12345"

# Base de datos en memoria para almacenar los proyectos
# Estructura del diccionario:
# {
#   "id-proyecto": {
#       "id": "...",
#       "nombre": "...",
#       "descripcion": "...",
#       "presupuesto": 0.0,
#       "actividades": [
#           {
#               "id": "...",
#               "nombre": "...",
#               "descripcion": "...",
#               "recursos": [
#                   {"id": "...", "nombre": "...", "tipo": "mano_de_obra|material", "precio": 0.0, "cantidad": 1}
#               ]
#           }
#       ]
#   }
# }
PROYECTOS_DB = {
    "ejemplo-1": {
        "id": "ejemplo-1",
        "nombre": "Construcción de Oficina Central",
        "descripcion": "Fase 1: Estructuración y adecuación de espacios para la nueva sede corporativa.",
        "presupuesto": 150000.0,
        "actividades": [
            {
                "id": "act-1",
                "nombre": "Cimentación y Vaciado",
                "descripcion": "Preparación del terreno y vaciado de concreto estructural.",
                "recursos": [
                    {"id": "rec-1", "nombre": "Operario de Maquinaria", "tipo": "mano_de_obra", "precio": 120.0, "cantidad": 5},
                    {"id": "rec-2", "nombre": "Cemento Estructural (Sacos)", "tipo": "material", "precio": 15.0, "cantidad": 200}
                ]
            },
            {
                "id": "act-2",
                "nombre": "Instalaciones Eléctricas Básicas",
                "descripcion": "Canalización de tuberías y cableado general de la planta baja.",
                "recursos": [
                    {"id": "rec-3", "nombre": "Técnico Electricista", "tipo": "mano_de_obra", "precio": 80.0, "cantidad": 3},
                    {"id": "rec-4", "nombre": "Cable de Cobre THHN (Rollos)", "tipo": "material", "precio": 45.0, "cantidad": 15}
                ]
            }
        ]
    }
}

# Funciones de utilidad para cálculo de costos
def calcular_costos_proyecto(proyecto):
    total_proyecto = 0.0
    actividades_procesadas = []
    
    for act in proyecto.get("actividades", []):
        costo_actividad = 0.0
        for rec in act.get("recursos", []):
            costo_recurso = float(rec["precio"]) * float(rec["cantidad"])
            costo_actividad += costo_recurso
        
        total_proyecto += costo_actividad
        # Guardamos el costo calculado dentro de la actividad para renderizarlo fácilmente
        act_copia = act.copy()
        act_copia["costo_total"] = costo_actividad
        actividades_procesadas.append(act_copia)
        
    presupuesto = float(proyecto["presupuesto"])
    desviacion = presupuesto - total_proyecto
    porcentaje_consumido = (total_proyecto / presupuesto * 100) if presupuesto > 0 else 0
    
    return {
        "total_proyecto": total_proyecto,
        "desviacion": desviacion,
        "porcentaje_consumido": min(porcentaje_consumido, 100.0),
        "porcentaje_real": porcentaje_consumido,
        "actividades": actividades_procesadas
    }

# Plantilla HTML Base integrada utilizando Tailwind CSS
INDEX_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es" class="h-full bg-slate-50">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Control de Proyectos - Python, GitHub & Vercel</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body class="flex flex-col min-h-screen text-slate-800">

    <!-- Encabezado / Navbar -->
    <header class="bg-indigo-700 text-white shadow-md">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex flex-col sm:flex-row justify-between items-center gap-4">
            <div class="flex items-center space-x-3">
                <div class="bg-white text-indigo-700 p-2 rounded-lg font-bold text-xl shadow">
                    <i class="fa-solid fa-square-poll-vertical"></i>
                </div>
                <div>
                    <h1 class="text-xl font-bold tracking-tight">Control de Proyectos</h1>
                    <p class="text-xs text-indigo-200">Plataforma Ágil de Presupuestos y Actividades</p>
                </div>
            </div>
            <div class="flex items-center space-x-2 text-xs bg-indigo-800 px-3 py-1.5 rounded-full border border-indigo-600">
                <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>Desplegado en Vercel</span>
            </div>
        </div>
    </header>

    <!-- Contenido Principal -->
    <main class="flex-grow max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        
        <!-- Mensajes de Notificación Flash -->
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="p-4 mb-6 rounded-lg text-sm flex items-center justify-between {% if category == 'error' %} bg-red-100 text-red-800 border border-red-200 {% else %} bg-emerald-100 text-emerald-800 border border-emerald-200 {% endif %}" id="flash-message">
                        <div class="flex items-center space-x-2">
                            <i class="fa-solid {% if category == 'error' %} fa-triangle-exclamation {% else %} fa-circle-check {% endif %}"></i>
                            <span>{{ message }}</span>
                        </div>
                        <button onclick="document.getElementById('flash-message').style.display='none'" class="text-lg font-bold focus:outline-none">&times;</button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <!-- Panel en Dos Columnas -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            
            <!-- Columna Izquierda: Listado y Formulario de Proyectos -->
            <div class="lg:col-span-1 space-y-6">
                <!-- Formulario Crear Proyecto -->
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                    <h2 class="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
                        <i class="fa-solid fa-folder-plus text-indigo-600"></i> Nuevo Proyecto
                    </h2>
                    <form action="{{ url_for('crear_proyecto') }}" method="POST" class="space-y-4">
                        <div>
                            <label class="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1">Nombre del Proyecto</label>
                            <input type="text" name="nombre" required placeholder="Ej. Remodelación Local Comercial" class="w-full px-3.5 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all placeholder:text-slate-400 text-sm">
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1">Presupuesto General ($)</label>
                            <input type="number" step="0.01" name="presupuesto" required placeholder="Ej. 75000" class="w-full px-3.5 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all placeholder:text-slate-400 text-sm">
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1">Descripción corta</label>
                            <textarea name="descripcion" rows="3" placeholder="Describe brevemente el alcance del proyecto..." class="w-full px-3.5 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all placeholder:text-slate-400 text-sm"></textarea>
                        </div>
                        <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-2 px-4 rounded-lg shadow-sm hover:shadow transition-all text-sm flex items-center justify-center gap-2">
                            <i class="fa-solid fa-plus text-xs"></i> Crear Proyecto
                        </button>
                    </form>
                </div>

                <!-- Lista de Proyectos Existentes -->
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                    <h2 class="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
                        <i class="fa-solid fa-list-check text-indigo-600"></i> Proyectos Activos
                    </h2>
                    {% if not proyectos %}
                        <div class="text-center py-8 text-slate-400">
                            <i class="fa-regular fa-folder-open text-3xl mb-2 block"></i>
                            <p class="text-sm">No hay proyectos registrados.</p>
                        </div>
                    {% else %}
                        <div class="space-y-3">
                            {% for p_id, p in proyectos.items() %}
                                <a href="{{ url_for('ver_proyecto', proyecto_id=p_id) }}" class="block p-4 rounded-xl border {% if proyecto_actual and proyecto_actual.id == p_id %} border-indigo-500 bg-indigo-50/50 {% else %} border-slate-200 hover:border-slate-300 hover:bg-slate-50 {% endif %} transition-all">
                                    <div class="flex justify-between items-start mb-1">
                                        <h3 class="font-semibold text-sm text-slate-900 {% if proyecto_actual and proyecto_actual.id == p_id %} text-indigo-900 {% endif %}">{{ p.nombre }}</h3>
                                    </div>
                                    <p class="text-xs text-slate-500 line-clamp-1 mb-2">{{ p.descripcion }}</p>
                                    <div class="flex justify-between items-center text-xs mt-1">
                                        <span class="text-slate-600 font-medium">Ppto: <strong class="text-slate-900">${{ "{:,.2f}".format(p.presupuesto) }}</strong></span>
                                        <span class="bg-indigo-100 text-indigo-800 text-[10px] font-bold px-2 py-0.5 rounded-full">{{ p.actividades|length }} Actividades</span>
                                    </div>
                                </a>
                            {% endfor %}
                        </div>
                    {% endif %}
                </div>
            </div>

            <!-- Columna Derecha: Detalle del Proyecto Seleccionado -->
            <div class="lg:col-span-2">
                {% if not proyecto_actual %}
                    <div class="bg-white border border-slate-200 rounded-2xl p-12 text-center h-full flex flex-col justify-center items-center shadow-sm">
                        <div class="bg-indigo-50 text-indigo-600 p-4 rounded-full mb-4">
                            <i class="fa-solid fa-arrow-pointer text-4xl"></i>
                        </div>
                        <h3 class="text-xl font-bold text-slate-900 mb-2">Selecciona o crea un proyecto</h3>
                        <p class="text-slate-500 text-sm max-w-md">Para gestionar actividades, asignar recursos, mano de obra, materiales y controlar la ejecución presupuestaria, selecciona un proyecto de la lista de la izquierda.</p>
                    </div>
                {% else %}
                    <!-- Ficha Detallada del Proyecto -->
                    <div class="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden mb-6">
                        <!-- Cabecera de Proyecto -->
                        <div class="bg-slate-900 text-white p-6">
                            <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-4">
                                <div>
                                    <span class="bg-indigo-500 text-white text-[10px] uppercase font-extrabold tracking-widest px-2.5 py-1 rounded">Ficha de Seguimiento</span>
                                    <h2 class="text-2xl font-bold mt-1.5">{{ proyecto_actual.nombre }}</h2>
                                    <p class="text-sm text-slate-300 mt-1">{{ proyecto_actual.descripcion }}</p>
                                </div>
                                <div class="text-left sm:text-right bg-slate-800 p-4 rounded-xl border border-slate-700 w-full sm:w-auto">
                                    <p class="text-xs text-slate-400 font-medium uppercase tracking-wider">Presupuesto General</p>
                                    <p class="text-2xl font-black text-emerald-400">${{ "{:,.2f}".format(proyecto_actual.presupuesto) }}</p>
                                </div>
                            </div>

                            <!-- Estado del Presupuesto (Dashboard) -->
                            <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 border-t border-slate-800 mt-4 text-sm">
                                <div>
                                    <span class="text-slate-400 text-xs block">Consumido Total:</span>
                                    <strong class="text-slate-200 text-base">${{ "{:,.2f}".format(metricas.total_proyecto) }}</strong>
                                </div>
                                <div>
                                    <span class="text-slate-400 text-xs block">Disponible:</span>
                                    <strong class="{% if metricas.desviacion >= 0 %} text-emerald-400 {% else %} text-rose-400 {% endif %} text-base">
                                        ${{ "{:,.2f}".format(metricas.desviacion) }}
                                    </strong>
                                </div>
                                <div class="flex flex-col justify-center">
                                    <div class="flex justify-between text-xs mb-1">
                                        <span class="text-slate-400">Ejecución del presupuesto:</span>
                                        <span class="font-bold text-slate-200">{{ "{:.1f}%".format(metricas.porcentaje_real) }}</span>
                                    </div>
                                    <div class="w-full bg-slate-800 rounded-full h-2">
                                        <div class="{% if metricas.porcentaje_real > 100 %} bg-rose-500 {% elif metricas.porcentaje_real > 85 %} bg-amber-500 {% else %} bg-indigo-500 {% endif %} h-2 rounded-full" style="width: {{ metricas.porcentaje_consumido }}%"></div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Panel de Acciones Internas -->
                        <div class="p-6 border-t border-slate-100 bg-slate-50/50 flex flex-wrap gap-3">
                            <button onclick="toggleModal('modal-actividad')" class="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs py-2.5 px-4 rounded-lg shadow-sm hover:shadow transition-all flex items-center gap-1.5">
                                <i class="fa-solid fa-circle-plus"></i> Nueva Actividad
                            </button>
                            <a href="{{ url_for('eliminar_proyecto', proyecto_id=proyecto_actual.id) }}" onclick="return confirm('¿Estás seguro de que deseas eliminar este proyecto y todas sus actividades?')" class="bg-rose-50 hover:bg-rose-100 text-rose-700 font-semibold text-xs py-2.5 px-4 rounded-lg border border-rose-200 transition-all ml-auto flex items-center gap-1.5">
                                <i class="fa-solid fa-trash-can"></i> Eliminar Proyecto
                            </a>
                        </div>
                    </div>

                    <!-- Listado de Actividades -->
                    <div class="space-y-6">
                        <div class="flex justify-between items-center">
                            <h3 class="text-lg font-bold text-slate-900 flex items-center gap-2">
                                <i class="fa-solid fa-list-check text-indigo-600"></i> Desglose de Actividades
                            </h3>
                            <span class="text-xs text-slate-500 font-semibold bg-white px-3 py-1 rounded-full border border-slate-200 shadow-sm">
                                Total Actividades: {{ metricas.actividades|length }}
                            </span>
                        </div>

                        {% if not metricas.actividades %}
                            <div class="bg-white border-2 border-dashed border-slate-200 rounded-2xl p-10 text-center text-slate-500 shadow-sm">
                                <i class="fa-solid fa-diagram-project text-3xl mb-3 block text-slate-400"></i>
                                <p class="text-sm font-semibold mb-1">Aún no hay actividades registradas</p>
                                <p class="text-xs text-slate-400 mb-4">Las actividades te permiten agrupar la mano de obra y los materiales necesarios.</p>
                                <button onclick="toggleModal('modal-actividad')" class="inline-flex items-center gap-1.5 text-xs font-bold text-white bg-indigo-600 px-4 py-2 rounded-lg hover:bg-indigo-700 transition-all">
                                    Crear mi Primera Actividad
                                </button>
                            </div>
                        {% else %}
                            {% for act in metricas.actividades %}
                                <div class="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden hover:shadow transition-all">
                                    <!-- Cabecera de la Actividad -->
                                    <div class="bg-slate-50 p-4 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                                        <div>
                                            <h4 class="font-bold text-base text-slate-900">{{ act.nombre }}</h4>
                                            <p class="text-xs text-slate-500">{{ act.descripcion }}</p>
                                        </div>
                                        <div class="flex items-center gap-3">
                                            <div class="bg-indigo-50 border border-indigo-100 px-3 py-1.5 rounded-xl text-right">
                                                <span class="text-[10px] text-indigo-600 font-semibold block uppercase">Costo Total Actividad</span>
                                                <strong class="text-indigo-900 text-sm">${{ "{:,.2f}".format(act.costo_total) }}</strong>
                                            </div>
                                            <!-- Botón para añadir recursos directos a esta actividad -->
                                            <button onclick="prepararModalRecurso('{{ act.id }}', '{{ act.nombre }}')" class="bg-indigo-600 hover:bg-indigo-700 text-white p-2 rounded-lg shadow-sm transition-all text-xs flex items-center justify-center h-9 w-9" title="Asignar Recursos">
                                                <i class="fa-solid fa-plus-circle text-lg"></i>
                                            </button>
                                        </div>
                                    </div>

                                    <!-- Tabla de Recursos asignados (Mano de Obra y Materiales) -->
                                    <div class="p-4">
                                        <h5 class="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Mano de Obra y Materiales Asignados</h5>
                                        {% if not act.recursos %}
                                            <p class="text-xs text-slate-400 italic py-4 text-center">No se han asignado recursos ni mano de obra para esta actividad aún.</p>
                                        {% else %}
                                            <div class="overflow-x-auto">
                                                <table class="min-w-full divide-y divide-slate-100 text-xs">
                                                    <thead>
                                                        <tr class="text-slate-400 text-left font-semibold uppercase tracking-wider">
                                                            <th class="pb-2">Recurso / Insumo</th>
                                                            <th class="pb-2">Tipo</th>
                                                            <th class="pb-2 text-right">Precio unitario</th>
                                                            <th class="pb-2 text-center">Cantidad</th>
                                                            <th class="pb-2 text-right">Total asignado</th>
                                                            <th class="pb-2 text-center">Acción</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody class="divide-y divide-slate-100">
                                                        {% for rec in act.recursos %}
                                                            <tr class="text-slate-700">
                                                                <td class="py-2.5 font-medium text-slate-900">{{ rec.nombre }}</td>
                                                                <td class="py-2.5">
                                                                    {% if rec.tipo == 'mano_de_obra' %}
                                                                        <span class="inline-flex items-center gap-1 bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full text-[10px] font-bold border border-amber-200">
                                                                            <i class="fa-solid fa-user-gear"></i> Mano de Obra
                                                                        </span>
                                                                    {% else %}
                                                                        <span class="inline-flex items-center gap-1 bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full text-[10px] font-bold border border-blue-200">
                                                                            <i class="fa-solid fa-box"></i> Material
                                                                        </span>
                                                                    {% endif %}
                                                                </td>
                                                                <td class="py-2.5 text-right font-medium">${{ "{:,.2f}".format(rec.precio|float) }}</td>
                                                                <td class="py-2.5 text-center font-bold text-slate-900">{{ rec.cantidad }}</td>
                                                                <td class="py-2.5 text-right font-semibold text-slate-900">
                                                                    ${{ "{:,.2f}".format(rec.precio|float * rec.cantidad|float) }}
                                                                </td>
                                                                <td class="py-2.5 text-center">
                                                                    <a href="{{ url_for('eliminar_recurso', proyecto_id=proyecto_actual.id, actividad_id=act.id, recurso_id=rec.id) }}" class="text-rose-500 hover:text-rose-700 font-bold p-1 text-xs" title="Eliminar Recurso">
                                                                        <i class="fa-solid fa-trash-can"></i>
                                                                    </a>
                                                                </td>
                                                            </tr>
                                                        {% endfor %}
                                                    </tbody>
                                                </table>
                                            </div>
                                        {% endif %}
                                    </div>
                                </div>
                            {% endfor %}
                        {% endif %}
                    </div>
                {% endif %}
            </div>
        </div>
    </main>

    <!-- Modal para Nueva Actividad -->
    <div id="modal-actividad" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4">
        <div class="bg-white rounded-2xl max-w-md w-full shadow-2xl overflow-hidden border border-slate-200 animate-in fade-in duration-200">
            <div class="bg-indigo-700 text-white p-4 flex justify-between items-center">
                <h3 class="font-bold text-base"><i class="fa-solid fa-diagram-project"></i> Agregar Actividad</h3>
                <button onclick="toggleModal('modal-actividad')" class="text-white hover:text-slate-200 text-xl font-bold">&times;</button>
            </div>
            <form action="{% if proyecto_actual %}{{ url_for('crear_actividad', proyecto_id=proyecto_actual.id) }}{% endif %}" method="POST" class="p-6 space-y-4">
                <div>
                    <label class="block text-xs font-semibold text-slate-600 uppercase mb-1">Nombre de la Actividad</label>
                    <input type="text" name="nombre_actividad" required placeholder="Ej. Instalaciones sanitarias" class="w-full px-3.5 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm">
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-600 uppercase mb-1">Descripción corta</label>
                    <textarea name="descripcion_actividad" rows="3" required placeholder="Describe las acciones principales de esta etapa..." class="w-full px-3.5 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm"></textarea>
                </div>
                <div class="flex space-x-3 pt-2">
                    <button type="button" onclick="toggleModal('modal-actividad')" class="w-1/2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold py-2 px-4 rounded-lg text-sm">Cancelar</button>
                    <button type="submit" class="w-1/2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded-lg text-sm">Guardar Actividad</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Modal para Nuevo Recurso -->
    <div id="modal-recurso" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4">
        <div class="bg-white rounded-2xl max-w-md w-full shadow-2xl overflow-hidden border border-slate-200">
            <div class="bg-indigo-700 text-white p-4 flex justify-between items-center">
                <h3 class="font-bold text-base"><i class="fa-solid fa-user-gear"></i> Asignar Recurso</h3>
                <button onclick="toggleModal('modal-recurso')" class="text-white hover:text-slate-200 text-xl font-bold">&times;</button>
            </div>
            <!-- El action se modificará dinámicamente mediante Javascript -->
            <form id="form-recurso" action="" method="POST" class="p-6 space-y-4">
                <div class="bg-slate-50 p-3 rounded-lg border border-slate-100 text-xs text-slate-600 mb-2">
                    Actividad destino: <strong id="actividad-nombre-display" class="text-slate-950"></strong>
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-600 uppercase mb-1">Nombre del Recurso / Material</label>
                    <input type="text" name="nombre_recurso" required placeholder="Ej. Ingeniero Civil / Varilla de acero de 1/2" class="w-full px-3.5 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm">
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-600 uppercase mb-1">Clasificación / Tipo</label>
                    <select name="tipo_recurso" required class="w-full px-3.5 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm">
                        <option value="mano_de_obra">Mano de Obra (Servicios, Mano de obra directa)</option>
                        <option value="material">Insumo / Material Físico</option>
                    </select>
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 uppercase mb-1">Costo / Precio Unitario ($)</label>
                        <input type="number" step="0.01" name="precio_recurso" required placeholder="Ej. 150.00" class="w-full px-3.5 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 uppercase mb-1">Cantidad Estimada</label>
                        <input type="number" name="cantidad_recurso" required min="1" value="1" class="w-full px-3.5 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm">
                    </div>
                </div>
                <div class="flex space-x-3 pt-2">
                    <button type="button" onclick="toggleModal('modal-recurso')" class="w-1/2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold py-2 px-4 rounded-lg text-sm">Cancelar</button>
                    <button type="submit" class="w-1/2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded-lg text-sm">Agregar Insumo</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Footer -->
    <footer class="bg-slate-900 text-slate-400 py-6 border-t border-slate-800 text-xs mt-12">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-2">
            <p>&copy; 2026 - Aplicación Control de Proyectos. Desarrollada con Python (Flask) y Tailwind CSS.</p>
            <p class="text-slate-500">Ejecutando en entorno Serverless de Vercel.</p>
        </div>
    </footer>

    <!-- Scripts para controlar Modales e Interfaz -->
    <script>
        function toggleModal(modalId) {
            const modal = document.getElementById(modalId);
            if (modal.classList.contains('hidden')) {
                modal.classList.remove('hidden');
            } else {
                modal.classList.add('hidden');
            }
        }

        function prepararModalRecurso(actividadId, actividadNombre) {
            document.getElementById('actividad-nombre-display').innerText = actividadNombre;
            // Configurar ruta dinámica del formulario de inserción
            const form = document.getElementById('form-recurso');
            const urlBase = "/proyectos/{{ proyecto_actual.id if proyecto_actual else '' }}/actividades/" + actividadId + "/recursos";
            form.setAttribute('action', urlBase);
            toggleModal('modal-recurso');
        }
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    # Buscamos el ID del proyecto actual por parámetro query en la URL (?id=...)
    proyecto_id = request.args.get("id")
    proyecto_actual = None
    metricas = {}
    
    if proyecto_id and proyecto_id in PROYECTOS_DB:
        proyecto_actual = PROYECTOS_DB[proyecto_id]
        metricas = calcular_costos_proyecto(proyecto_actual)
    elif PROYECTOS_DB:
        # Por defecto mostramos el primer proyecto de la lista si hay alguno
        primer_id = list(PROYECTOS_DB.keys())[0]
        proyecto_actual = PROYECTOS_DB[primer_id]
        metricas = calcular_costos_proyecto(proyecto_actual)

    return render_template_string(
        INDEX_HTML_TEMPLATE, 
        proyectos=PROYECTOS_DB, 
        proyecto_actual=proyecto_actual, 
        metricas=metricas
    )

@app.route("/proyectos", methods=["POST"])
def crear_proyecto():
    nombre = request.form.get("nombre")
    presupuesto_str = request.form.get("presupuesto")
    descripcion = request.form.get("descripcion", "")
    
    try:
        presupuesto = float(presupuesto_str)
    except ValueError:
        flash("El presupuesto debe ser un número válido.", "error")
        return redirect(url_for("index"))
        
    if not nombre:
        flash("El nombre del proyecto es obligatorio.", "error")
        return redirect(url_for("index"))

    nuevo_id = str(uuid.uuid4())[:8] # Generador de id corto
    PROYECTOS_DB[nuevo_id] = {
        "id": nuevo_id,
        "nombre": nombre,
        "descripcion": descripcion,
        "presupuesto": presupuesto,
        "actividades": []
    }
    
    flash("Proyecto creado con éxito.", "success")
    return redirect(url_for("index", id=nuevo_id))

@app.route("/proyectos/<proyecto_id>")
def ver_proyecto(proyecto_id):
    if proyecto_id not in PROYECTOS_DB:
        flash("El proyecto seleccionado no existe.", "error")
        return redirect(url_for("index"))
    return redirect(url_for("index", id=proyecto_id))

@app.route("/proyectos/<proyecto_id>/eliminar")
def eliminar_proyecto(proyecto_id):
    if proyecto_id in PROYECTOS_DB:
        del PROYECTOS_DB[proyecto_id]
        flash("Proyecto eliminado correctamente.", "success")
    else:
        flash("El proyecto no pudo ser encontrado.", "error")
    return redirect(url_for("index"))

@app.route("/proyectos/<proyecto_id>/actividades", methods=["POST"])
def crear_actividad(proyecto_id):
    if proyecto_id not in PROYECTOS_DB:
        flash("Proyecto de destino no válido.", "error")
        return redirect(url_for("index"))
        
    nombre_act = request.form.get("nombre_actividad")
    descripcion_act = request.form.get("descripcion_actividad", "")
    
    if not nombre_act:
        flash("El nombre de la actividad no puede estar vacío.", "error")
        return redirect(url_for("index", id=proyecto_id))
        
    nueva_actividad = {
        "id": str(uuid.uuid4())[:8],
        "nombre": nombre_act,
        "descripcion": descripcion_act,
        "recursos": []
    }
    
    PROYECTOS_DB[proyecto_id]["actividades"].append(nueva_actividad)
    flash("Actividad agregada exitosamente.", "success")
    return redirect(url_for("index", id=proyecto_id))

@app.route("/proyectos/<proyecto_id>/actividades/<actividad_id>/recursos", methods=["POST"])
def agregar_recurso(proyecto_id, actividad_id):
    if proyecto_id not in PROYECTOS_DB:
        flash("Proyecto inexistente.", "error")
        return redirect(url_for("index"))
        
    nombre_recurso = request.form.get("nombre_recurso")
    tipo_recurso = request.form.get("tipo_recurso") # 'mano_de_obra' o 'material'
    precio_str = request.form.get("precio_recurso")
    cantidad_str = request.form.get("cantidad_recurso")
    
    try:
        precio = float(precio_str)
        cantidad = int(cantidad_str)
    except ValueError:
        flash("Por favor, introduce valores numéricos correctos en precio y cantidad.", "error")
        return redirect(url_for("index", id=proyecto_id))
        
    if not nombre_recurso or tipo_recurso not in ["mano_de_obra", "material"]:
        flash("Campos de recursos inválidos.", "error")
        return redirect(url_for("index", id=proyecto_id))
        
    # Buscar la actividad indicada para insertar el recurso
    actividades = PROYECTOS_DB[proyecto_id]["actividades"]
    actividad_encontrada = False
    
    for act in actividades:
        if act["id"] == actividad_id:
            nuevo_recurso = {
                "id": str(uuid.uuid4())[:8],
                "nombre": nombre_recurso,
                "tipo": tipo_recurso,
                "precio": precio,
                "cantidad": cantidad
            }
            act["recursos"].append(nuevo_recurso)
            actividad_encontrada = True
            break
            
    if actividad_encontrada:
        flash("Insumo/Recurso agregado correctamente a la actividad.", "success")
    else:
        flash("Actividad de destino no encontrada.", "error")
        
    return redirect(url_for("index", id=proyecto_id))

@app.route("/proyectos/<proyecto_id>/actividades/<actividad_id>/recursos/<recurso_id>/eliminar")
def eliminar_recurso(proyecto_id, actividad_id, recurso_id):
    if proyecto_id not in PROYECTOS_DB:
        return redirect(url_for("index"))
        
    actividades = PROYECTOS_DB[proyecto_id]["actividades"]
    for act in actividades:
        if act["id"] == actividad_id:
            # Filtrar y quitar el recurso de la lista
            act["recursos"] = [r for r in act["recursos"] if r["id"] != recurso_id]
            flash("Recurso eliminado de la actividad.", "success")
            break
            
    return redirect(url_for("index", id=proyecto_id))

# Ejecución local de desarrollo
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
