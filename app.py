# -*- coding: utf-8 -*-
from flask import Flask, render_template_string, request, redirect, url_for, flash
import uuid
import re
from datetime import datetime

app = Flask(__name__)
app.secret_key = "clave_gerencial_proyectos_2024"

# Base de datos en memoria optimizada
PROYECTOS_DB = {
    "demo": {
        "id": "demo",
        "nombre": "Proyecto de Infraestructura Vial",
        "descripcion": "Ampliación de carril y modernización de señalética.",
        "presupuesto": 250000.0,
        "fecha_inicio": "2024-01-15",
        "fecha_fin_tentativa": "2024-08-30",
        "actividades": [
            {
                "id": "act-1",
                "nombre": "Topografía y Nivelación",
                "descripcion": "Estudio de suelos y marcado de límites.",
                "estado": "Completada",
                "fecha_inicio": "2024-01-20",
                "fecha_fin": "2024-02-15",
                "recursos": [
                    {"id": "r1", "nombre": "Equipo de Topógrafos", "tipo": "mano_de_obra", "precio": 1500, "cantidad": 2},
                    {"id": "r2", "nombre": "Alquiler Estación Total", "tipo": "material", "precio": 450, "cantidad": 10}
                ]
            },
            {
                "id": "act-2",
                "nombre": "Remoción de Capa Asfáltica",
                "descripcion": "Demolición de asfalto antiguo.",
                "estado": "Iniciada",
                "fecha_inicio": "2024-03-01",
                "fecha_fin": None,
                "recursos": [
                    {"id": "r3", "nombre": "Operadores de Maquinaria", "tipo": "mano_de_obra", "precio": 120, "cantidad": 50},
                    {"id": "r4", "nombre": "Combustible Diesel", "tipo": "material", "precio": 5, "cantidad": 1200}
                ]
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
    gantt_code = "gantt\\ndateFormat YYYY-MM-DD\\ntitle Cronograma de Actividades\\n"
    
    for act in proyecto["actividades"]:
        costo_act = sum(float(r["precio"]) * float(r["cantidad"]) for r in act["recursos"])
        gasto_total += costo_act
        
        # Lógica de estados
        if act["estado"] == "Completada": completadas += 1
        elif act["estado"] == "Iniciada": iniciadas += 1
        
        # Generación de GANTT
        status_tag = "done" if act["estado"] == "Completada" else "active" if act["estado"] == "Iniciada" else ""
        f_ini = act["fecha_inicio"] or proyecto["fecha_inicio"]
        nombre_limpio = limpiar_nombre_gantt(act["nombre"])
        
        if act["estado"] == "Completada" and act["fecha_fin"]:
            gantt_code += f"  {nombre_limpio} :{status_tag}, {f_ini}, {act['fecha_fin']}\\n"
        else:
            gantt_code += f"  {nombre_limpio} :{status_tag}, {f_ini}, 15d\\n"

    ppto = float(proyecto["presupuesto"])
    return {
        "gasto_total": gasto_total,
        "disponible": ppto - gasto_total,
        "porcentaje_gasto": min((gasto_total / ppto * 100), 100) if ppto > 0 else 0,
        "porcentaje_avance": (completadas / len(proyecto["actividades"]) * 100) if proyecto["actividades"] else 0,
        "conteo": {"completas": completadas, "iniciadas": iniciadas, "pendientes": len(proyecto["actividades"]) - completadas - iniciadas},
        "gantt_code": gantt_code
    }

INDEX_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8"><title>Control Proyectos v2.0</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({ startOnLoad: true, theme: 'neutral' });
    </script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body class="bg-slate-100 font-sans">
    <nav class="bg-slate-900 text-white p-4 shadow-xl">
        <div class="max-w-7xl mx-auto flex justify-between items-center">
            <h1 class="text-xl font-bold flex items-center gap-2">
                <i class="fa-solid fa-chart-line text-emerald-400"></i> Gestor Gerencial de Proyectos
            </h1>
            <div class="text-xs text-slate-400">v2.1 | Dashboard, GANTT & Control Total</div>
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

                    <!-- Diagrama de GANTT -->
                    <div class="bg-white p-6 rounded-3xl border shadow-sm">
                        <h3 class="font-bold text-slate-800 mb-4 flex items-center gap-2"><i class="fa-solid fa-stream text-indigo-500"></i> Cronograma GANTT</h3>
                        <div class="mermaid overflow-x-auto bg-slate-50 p-4 rounded-xl">
                            {{ m.gantt_code|safe }}
                        </div>
                    </div>

                    <!-- Actividades -->
                    <div class="flex justify-between items-center">
                        <h3 class="font-bold text-slate-800 text-lg flex items-center gap-2">
                            <i class="fa-solid fa-list-check text-indigo-600"></i> Actividades y Control de Recursos
                        </h3>
                        <button onclick="document.getElementById('modal-act').style.display='flex'" class="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-xl text-sm font-bold shadow-lg transition">+ Actividad</button>
                    </div>

                    {% if not proyecto.actividades %}
                        <div class="bg-white p-12 text-center rounded-2xl border border-dashed text-slate-400">
                            Aún no hay actividades agregadas a este proyecto.
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
                                            Inicio: <strong class="text-slate-700">{{ act.fecha_inicio }}</strong> 
                                            {% if act.fecha_fin %}| Fin: <strong class="text-slate-700">{{ act.fecha_fin }}</strong>{% endif %}
                                        </span>
                                    </div>
                                    <h4 class="font-bold text-slate-800 text-base mt-1.5">{{act.nombre}}</h4>
                                </div>
                                <div class="flex items-center gap-2.5 w-full sm:w-auto justify-end">
                                    {% if act.estado != 'Completada' %}
                                    <form action="/actividades/{{proyecto.id}}/{{act.id}}/estado" method="POST" class="inline">
                                        <input type="hidden" name="nuevo_estado" value="{% if act.estado == 'Pendiente' %}Iniciada{% else %}Completada{% endif %}">
                                        <button class="text-xs font-bold bg-white hover:bg-slate-100 border px-3 py-1.5 rounded-lg transition text-slate-700 shadow-sm">
                                            {% if act.estado == 'Pendiente' %}Marcar Inicio{% else %}Finalizar Tarea{% endif %}
                                        </button>
                                    </form>
                                    {% endif %}
                                    <button onclick="openRecurso('{{act.id}}', '{{act.nombre}}')" class="bg-indigo-50 hover:bg-indigo-100 text-indigo-600 p-2 rounded-lg transition" title="Agregar Recurso">
                                        <i class="fa-solid fa-plus-circle text-base"></i>
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
                                            <th class="pb-2 text-right">Cantidad</th>
                                            <th class="pb-2 text-right">Precio unitario</th>
                                            <th class="pb-2 text-right">Costo Total</th>
                                            <th class="pb-2 text-center">Acciones</th>
                                        </tr>
                                    </thead>
                                    <tbody class="divide-y divide-slate-100">
                                        {% if not act.recursos %}
                                            <tr>
                                                <td colspan="6" class="py-4 text-center text-slate-400 italic">No hay recursos ni mano de obra asignada a esta actividad.</td>
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
                                                       onclick="return confirm('¿Eliminar este recurso?')" 
                                                       class="text-rose-500 hover:text-rose-700 transition" title="Eliminar Recurso">
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
                        {% endfor %}
                    {% endif %}
                {% endif %}
            </section>
        </div>
    </main>

    <!-- Modal: Nueva Actividad -->
    <div id="modal-act" class="fixed inset-0 bg-black/60 hidden items-center justify-center p-4 z-50 backdrop-blur-sm">
        <div class="bg-white p-8 rounded-3xl max-w-md w-full shadow-2xl">
            <h3 class="text-xl font-bold mb-4 text-slate-900"><i class="fa-solid fa-diagram-project text-indigo-600"></i> Agregar Nueva Actividad</h3>
            <form action="/actividades/{{proyecto.id if proyecto else ''}}" method="POST" class="space-y-4 text-sm">
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Nombre de la actividad</label>
                    <input type="text" name="nombre" placeholder="Ej. Pavimentación Inicial" class="w-full p-2.5 border rounded-xl" required>
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Estado actual</label>
                    <select name="estado" id="input-estado" onchange="toggleFechaFin(this.value)" class="w-full p-2.5 border rounded-xl">
                        <option value="Pendiente">Pendiente (No iniciada)</option>
                        <option value="Iniciada">Iniciada (En ejecución)</option>
                        <option value="Completada">Completada (Finalizada)</option>
                    </select>
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Fecha de Inicio</label>
                        <input type="date" name="f_ini" class="w-full p-2.5 border rounded-xl" required>
                    </div>
                    <div>
                        <label id="label-f-fin" class="block text-xs font-bold text-slate-400 uppercase mb-1">Fecha de Fin</label>
                        <input type="date" name="f_fin" id="input-f-fin" disabled class="w-full p-2.5 border rounded-xl bg-slate-50 text-slate-400">
                        <p class="text-[10px] text-slate-400 mt-1">Sólo si ya culminó</p>
                    </div>
                </div>
                <div class="flex gap-2 pt-2">
                    <button type="button" onclick="document.getElementById('modal-act').style.display='none'" class="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 py-3 rounded-xl font-bold transition">Cancelar</button>
                    <button class="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white py-3 rounded-xl font-bold shadow-lg transition">Guardar Actividad</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Modal: Nuevo Recurso -->
    <div id="modal-rec" class="fixed inset-0 bg-black/60 hidden items-center justify-center p-4 z-50 backdrop-blur-sm">
        <div class="bg-white p-8 rounded-3xl max-w-md w-full shadow-2xl">
            <h3 class="text-xl font-bold mb-2 text-slate-900"><i class="fa-solid fa-user-gear text-indigo-600"></i> Asignar Insumo o Mano de Obra</h3>
            <p class="text-xs text-slate-500 mb-4">Actividad: <strong id="act-target-name" class="text-slate-800"></strong></p>
            <form id="form-rec" method="POST" class="space-y-4 text-sm">
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Nombre del Recurso / Insumo</label>
                    <input type="text" name="nombre" placeholder="Ej. Operador de Bulldozer, Arena de Río (m³)" class="w-full p-2.5 border rounded-xl" required>
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Clasificación</label>
                    <select name="tipo" class="w-full p-2.5 border rounded-xl">
                        <option value="mano_de_obra">Mano de Obra (Servicios directos)</option>
                        <option value="material">Materiales / Suministros físicos</option>
                    </select>
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Precio Unitario ($)</label>
                        <input type="number" step="0.01" name="precio" placeholder="Precio unitario" class="w-full p-2.5 border rounded-xl" required>
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Cantidad</label>
                        <input type="number" name="cantidad" min="1" value="1" placeholder="Cantidad" class="w-full p-2.5 border rounded-xl" required>
                    </div>
                </div>
                <div class="flex gap-2 pt-2">
                    <button type="button" onclick="document.getElementById('modal-rec').style.display='none'" class="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 py-3 rounded-xl font-bold transition">Cancelar</button>
                    <button class="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white py-3 rounded-xl font-bold shadow-lg transition">Asignar Recurso</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        function openRecurso(id, nombre) {
            document.getElementById('act-target-name').innerText = nombre;
            document.getElementById('form-rec').action = "/recursos/{{proyecto.id if proyecto else ''}}/" + id;
            document.getElementById('modal-rec').style.display = 'flex';
        }

        function toggleFechaFin(val) {
            const inputFin = document.getElementById('input-f-fin');
            const labelFin = document.getElementById('label-f-fin');
            if (val === 'Completada') {
                inputFin.disabled = false;
                inputFin.required = true;
                inputFin.classList.remove('bg-slate-50', 'text-slate-400');
                inputFin.classList.add('bg-white', 'text-slate-900');
                labelFin.classList.remove('text-slate-400');
                labelFin.classList.add('text-slate-500');
            } else {
                inputFin.disabled = true;
                inputFin.required = false;
                inputFin.value = "";
                inputFin.classList.add('bg-slate-50', 'text-slate-400');
                inputFin.classList.remove('bg-white', 'text-slate-900');
                labelFin.classList.add('text-slate-400');
                labelFin.classList.remove('text-slate-500');
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

@app.route("/actividades/<p_id>", methods=["POST"])
def crear_act(p_id):
    if p_id in PROYECTOS_DB:
        nombre_act = request.form["nombre"]
        estado_act = request.form.get("estado", "Pendiente")
        fecha_inicio_act = request.form["f_ini"]
        fecha_fin_act = request.form.get("f_fin") or None
        
        # Validación de integridad de fechas
        if estado_act != "Completada":
            fecha_fin_act = None
            
        PROYECTOS_DB[p_id]["actividades"].append({
            "id": str(uuid.uuid4())[:6], 
            "nombre": nombre_act, 
            "estado": estado_act,
            "fecha_inicio": fecha_inicio_act, 
            "fecha_fin": fecha_fin_act, 
            "recursos": []
        })
        flash(f"Actividad '{nombre_act}' guardada con estado {estado_act}.", "success")
    return redirect(url_for("index", id=p_id))

@app.route("/actividades/<p_id>/<act_id>/eliminar", methods=["GET"])
def eliminar_act(p_id, act_id):
    p = PROYECTOS_DB.get(p_id)
    if p:
        # Filtrar quitando la actividad indicada
        original_len = len(p["actividades"])
        p["actividades"] = [act for act in p["actividades"] if act["id"] != act_id]
        if len(p["actividades"]) < original_len:
            flash("Actividad removida con éxito.", "success")
        else:
            flash("No se pudo encontrar la actividad para eliminar.", "error")
    return redirect(url_for("index", id=p_id))

@app.route("/actividades/<p_id>/<act_id>/estado", methods=["POST"])
def cambiar_estado(p_id, act_id):
    p = PROYECTOS_DB.get(p_id)
    if p:
        for act in p["actividades"]:
            if act["id"] == act_id:
                act["estado"] = request.form["nuevo_estado"]
                if act["estado"] == "Completada" and not act["fecha_fin"]:
                    act["fecha_fin"] = datetime.now().strftime("%Y-%m-%d")
                flash(f"Estado de '{act['nombre']}' modificado a {act['estado']}.", "success")
    return redirect(url_for("index", id=p_id))

@app.route("/recursos/<p_id>/<act_id>", methods=["POST"])
def add_rec(p_id, act_id):
    p = PROYECTOS_DB.get(p_id)
    if p:
        for act in p["actividades"]:
            if act["id"] == act_id:
                nuevo_rec = {
                    "id": str(uuid.uuid4())[:6], 
                    "nombre": request.form["nombre"],
                    "tipo": request.form["tipo"], 
                    "precio": float(request.form["precio"]),
                    "cantidad": int(request.form["cantidad"])
                }
                act["recursos"].append(nuevo_rec)
                flash(f"Recurso '{request.form['nombre']}' asignado con éxito.", "success")
    return redirect(url_for("index", id=p_id))

@app.route("/recursos/<p_id>/<act_id>/<rec_id>/eliminar", methods=["GET"])
def eliminar_rec(p_id, act_id, rec_id):
    p = PROYECTOS_DB.get(p_id)
    if p:
        for act in p["actividades"]:
            if act["id"] == act_id:
                act["recursos"] = [r for r in act["recursos"] if r["id"] != rec_id]
                flash("Recurso desasociado de la actividad.", "success")
                break
    return redirect(url_for("index", id=p_id))

if __name__ == "__main__":
    app.run(debug=True)
