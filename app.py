# -*- coding: utf-8 -*-
from flask import Flask, render_template_string, request, redirect, url_for, flash
import uuid
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
        
        if act["estado"] == "Completada" and act["fecha_fin"]:
            gantt_code += f"  {act['nombre']} :{status_tag}, {f_ini}, {act['fecha_fin']}\\n"
        else:
            gantt_code += f"  {act['nombre']} :{status_tag}, {f_ini}, 15d\\n"

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
            <h1 class="text-xl font-bold"><i class="fa-solid fa-chart-line text-emerald-400"></i> Gestor Gerencial</h1>
            <div class="text-xs text-slate-400">v2.0 | Dashboard & GANTT</div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-4 gap-6">
        <!-- Sidebar Proyectos -->
        <aside class="lg:col-span-1 space-y-6">
            <div class="bg-white p-6 rounded-2xl shadow-sm border">
                <h2 class="font-bold mb-4 text-slate-800"><i class="fa-solid fa-folder-plus text-indigo-600"></i> Crear Proyecto</h2>
                <form action="/proyectos" method="POST" class="space-y-3 text-sm">
                    <input type="text" name="nombre" placeholder="Nombre Proyecto" class="w-full p-2 border rounded-lg" required>
                    <input type="number" name="presupuesto" placeholder="Presupuesto $" class="w-full p-2 border rounded-lg" required>
                    <div class="grid grid-cols-2 gap-2">
                        <div>
                            <label class="text-[10px] font-bold text-slate-400">INICIO</label>
                            <input type="date" name="fecha_inicio" class="w-full p-1 border rounded" required>
                        </div>
                        <div>
                            <label class="text-[10px] font-bold text-slate-400">FIN (TENT)</label>
                            <input type="date" name="fecha_fin" class="w-full p-1 border rounded" required>
                        </div>
                    </div>
                    <button class="w-full bg-indigo-600 text-white py-2 rounded-lg font-bold">Crear</button>
                </form>
            </div>
            <div class="space-y-2">
                {% for p_id, p in proyectos.items() %}
                <a href="/?id={{p_id}}" class="block p-4 bg-white border rounded-xl hover:border-indigo-500 transition shadow-sm">
                    <div class="font-bold text-slate-700 text-sm">{{p.nombre}}</div>
                    <div class="text-[10px] text-slate-400">Fin: {{p.fecha_fin_tentativa}}</div>
                </a>
                {% endfor %}
            </div>
        </aside>

        <!-- Contenido Central -->
        <section class="lg:col-span-3 space-y-6">
            {% if not proyecto %}
                <div class="bg-white p-20 text-center rounded-3xl border-2 border-dashed">Selecciona un proyecto para ver el Resumen Gerencial</div>
            {% else %}
                <!-- Resumen Gerencial Card -->
                <div class="bg-slate-900 text-white p-8 rounded-3xl shadow-2xl">
                    <div class="flex justify-between items-start mb-6">
                        <div>
                            <h2 class="text-3xl font-bold">{{proyecto.nombre}}</h2>
                            <p class="text-slate-400 text-sm mt-1">Desde {{proyecto.fecha_inicio}} hasta {{proyecto.fecha_fin_tentativa}}</p>
                        </div>
                        <div class="text-right">
                            <span class="text-xs uppercase text-slate-500 font-bold">Presupuesto General</span>
                            <div class="text-3xl font-black text-emerald-400">${{"{:,.2f}".format(proyecto.presupuesto)}}</div>
                        </div>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 pt-6 border-t border-slate-800">
                        <div class="bg-slate-800/50 p-4 rounded-2xl border border-slate-700">
                            <div class="text-xs text-slate-400 mb-1">GASTO EJECUTADO</div>
                            <div class="text-xl font-bold text-white">${{"{:,.2f}".format(m.gasto_total)}}</div>
                            <div class="w-full bg-slate-700 h-1.5 rounded-full mt-2"><div class="bg-emerald-500 h-1.5 rounded-full" style="width: {{m.porcentaje_gasto}}%"></div></div>
                        </div>
                        <div class="bg-slate-800/50 p-4 rounded-2xl border border-slate-700">
                            <div class="text-xs text-slate-400 mb-1">DISPONIBLE</div>
                            <div class="text-xl font-bold {% if m.disponible < 0 %}text-rose-400{% else %}text-emerald-400{% endif %}">${{"{:,.2f}".format(m.disponible)}}</div>
                        </div>
                        <div class="bg-slate-800/50 p-4 rounded-2xl border border-slate-700 text-center">
                            <div class="text-xs text-slate-400 mb-1">AVANCE FÍSICO</div>
                            <div class="text-2xl font-black text-indigo-400">{{ "{:.1f}%".format(m.porcentaje_avance) }}</div>
                        </div>
                    </div>
                </div>

                <!-- Diagrama de GANTT -->
                <div class="bg-white p-6 rounded-3xl border shadow-sm">
                    <h3 class="font-bold text-slate-800 mb-4"><i class="fa-solid fa-stream text-indigo-500"></i> Cronograma GANTT</h3>
                    <div class="mermaid overflow-x-auto">
                        {{ m.gantt_code|safe }}
                    </div>
                </div>

                <!-- Actividades -->
                <div class="flex justify-between items-center">
                    <h3 class="font-bold text-slate-800 text-lg">Actividades y Recursos</h3>
                    <button onclick="document.getElementById('modal-act').style.display='flex'" class="bg-indigo-600 text-white px-4 py-2 rounded-xl text-sm font-bold shadow-lg">+ Actividad</button>
                </div>

                {% for act in proyecto.actividades %}
                <div class="bg-white rounded-2xl border shadow-sm overflow-hidden">
                    <div class="p-4 bg-slate-50 border-b flex justify-between items-center">
                        <div>
                            <span class="text-[10px] font-black uppercase px-2 py-1 rounded-full {% if act.estado == 'Completada' %}bg-emerald-100 text-emerald-700{% elif act.estado == 'Iniciada' %}bg-blue-100 text-blue-700{% else %}bg-slate-200 text-slate-600{% endif %}">
                                {{act.estado}}
                            </span>
                            <h4 class="font-bold text-slate-700 mt-1">{{act.nombre}}</h4>
                        </div>
                        <div class="flex gap-2">
                            {% if act.estado != 'Completada' %}
                            <form action="/actividades/{{proyecto.id}}/{{act.id}}/estado" method="POST">
                                <input type="hidden" name="nuevo_estado" value="{% if act.estado == 'Pendiente' %}Iniciada{% else %}Completada{% endif %}">
                                <button class="text-xs font-bold bg-white border px-3 py-1 rounded-lg hover:bg-slate-100">
                                    {% if act.estado == 'Pendiente' %}Marcar Inicio{% else %}Finalizar Tarea{% endif %}
                                </button>
                            </form>
                            {% endif %}
                            <button onclick="openRecurso('{{act.id}}', '{{act.nombre}}')" class="bg-indigo-50 text-indigo-600 p-2 rounded-lg"><i class="fa-solid fa-plus-circle"></i></button>
                        </div>
                    </div>
                    <div class="p-4">
                        <table class="w-full text-xs text-left">
                            <tr class="text-slate-400 border-b">
                                <th class="pb-2">Recurso</th>
                                <th class="pb-2">Tipo</th>
                                <th class="pb-2 text-right">Costo</th>
                            </tr>
                            {% for r in act.recursos %}
                            <tr class="border-b last:border-0">
                                <td class="py-2">{{r.nombre}} (x{{r.cantidad}})</td>
                                <td class="py-2">{{r.tipo}}</td>
                                <td class="py-2 text-right font-bold text-slate-700">${{"{:,.2f}".format(r.precio * r.cantidad)}}</td>
                            </tr>
                            {% endfor %}
                        </table>
                    </div>
                </div>
                {% endfor %}
            {% endif %}
        </section>
    </main>

    <!-- Modales (Simplificados) -->
    <div id="modal-act" class="fixed inset-0 bg-black/50 hidden items-center justify-center p-4 z-50">
        <div class="bg-white p-8 rounded-3xl max-w-md w-full shadow-2xl">
            <h3 class="text-xl font-bold mb-4">Nueva Actividad</h3>
            <form action="/actividades/{{proyecto.id if proyecto else ''}}" method="POST" class="space-y-4">
                <input type="text" name="nombre" placeholder="Nombre actividad" class="w-full p-3 border rounded-xl" required>
                <div>
                    <label class="text-xs text-slate-400">Fecha prevista de inicio</label>
                    <input type="date" name="f_ini" class="w-full p-3 border rounded-xl" required>
                </div>
                <div class="flex gap-2">
                    <button type="button" onclick="this.parentElement.parentElement.parentElement.parentElement.style.display='none'" class="flex-1 bg-slate-100 py-3 rounded-xl font-bold">Cerrar</button>
                    <button class="flex-1 bg-indigo-600 text-white py-3 rounded-xl font-bold">Guardar</button>
                </div>
            </form>
        </div>
    </div>

    <div id="modal-rec" class="fixed inset-0 bg-black/50 hidden items-center justify-center p-4 z-50">
        <div class="bg-white p-8 rounded-3xl max-w-md w-full">
            <h3 class="text-xl font-bold mb-4">Añadir Recurso a <span id="act-target-name"></span></h3>
            <form id="form-rec" method="POST" class="space-y-4">
                <input type="text" name="nombre" placeholder="Nombre recurso" class="w-full p-3 border rounded-xl" required>
                <select name="tipo" class="w-full p-3 border rounded-xl">
                    <option value="mano_de_obra">Mano de Obra</option>
                    <option value="material">Material</option>
                </select>
                <div class="grid grid-cols-2 gap-2">
                    <input type="number" name="precio" placeholder="Precio unitario" class="w-full p-3 border rounded-xl" required>
                    <input type="number" name="cantidad" placeholder="Cantidad" class="w-full p-3 border rounded-xl" required>
                </div>
                <div class="flex gap-2">
                    <button type="button" onclick="this.parentElement.parentElement.parentElement.parentElement.style.display='none'" class="flex-1 bg-slate-100 py-3 rounded-xl font-bold">Cerrar</button>
                    <button class="flex-1 bg-indigo-600 text-white py-3 rounded-xl font-bold">Asignar</button>
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
        "id": id_p, "nombre": request.form["nombre"], "presupuesto": float(request.form["presupuesto"]),
        "fecha_inicio": request.form["fecha_inicio"], "fecha_fin_tentativa": request.form["fecha_fin"], "actividades": []
    }
    return redirect(url_for("index", id=id_p))

@app.route("/actividades/<p_id>", methods=["POST"])
def crear_act(p_id):
    if p_id in PROYECTOS_DB:
        PROYECTOS_DB[p_id]["actividades"].append({
            "id": str(uuid.uuid4())[:6], "nombre": request.form["nombre"], "estado": "Pendiente",
            "fecha_inicio": request.form["f_ini"], "fecha_fin": None, "recursos": []
        })
    return redirect(url_for("index", id=p_id))

@app.route("/actividades/<p_id>/<act_id>/estado", methods=["POST"])
def cambiar_estado(p_id, act_id):
    p = PROYECTOS_DB.get(p_id)
    if p:
        for act in p["actividades"]:
            if act["id"] == act_id:
                act["estado"] = request.form["nuevo_estado"]
                if act["estado"] == "Completada":
                    act["fecha_fin"] = datetime.now().strftime("%Y-%m-%d")
    return redirect(url_for("index", id=p_id))

@app.route("/recursos/<p_id>/<act_id>", methods=["POST"])
def add_rec(p_id, act_id):
    p = PROYECTOS_DB.get(p_id)
    if p:
        for act in p["actividades"]:
            if act["id"] == act_id:
                act["recursos"].append({
                    "id": str(uuid.uuid4())[:6], "nombre": request.form["nombre"],
                    "tipo": request.form["tipo"], "precio": float(request.form["precio"]),
                    "cantidad": int(request.form["cantidad"])
                })
    return redirect(url_for("index", id=p_id))

if __name__ == "__main__":
    app.run(debug=True)
