from flask import Flask, request, jsonify
import subprocess
import os
import json
import tempfile
import shutil
import urllib.request

app = Flask(__name__)

def descargar_fet():
    if os.path.exists(FET_BIN):
        return True
    try:
        os.makedirs(FET_DIR, exist_ok=True)
        url = "https://github.com/fet-project/fet/releases/download/v7.8.0/fet-cl-linux64"
        urllib.request.urlretrieve(url, FET_BIN)
        os.chmod(FET_BIN, 0o755)
        return os.path.exists(FET_BIN)
    except Exception as e:
        print(f"Error descargando FET: {e}")
        return False

def descargar_fet():
    if os.path.exists(FET_BIN):
        return True
    try:
        os.makedirs(FET_DIR, exist_ok=True)
        tmp = "/tmp/fet.tar.bz2"
        urllib.request.urlretrieve(FET_URL, tmp)
        subprocess.run(["tar", "-xjf", tmp, "-C", FET_DIR], check=True)
        return os.path.exists(FET_BIN)
    except:
        return False

def construir_xml(datos):
    dias = datos.get("dias", 5)
    horas = datos.get("horas_por_dia", 8)
    cursos = datos.get("cursos", [])
    profes = datos.get("profesores", [])
    asigs = datos.get("asignaturas", [])
    asignacs = datos.get("asignaciones", [])
    dias_nombres = ["Lunes","Martes","Miercoles","Jueves","Viernes"][:dias]
    horas_nombres = [f"Hora_{i}" for i in range(1, horas+1)]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<fet version="6.18.0">')
    xml.append('<Institution_Name>Taralix</Institution_Name>')
    xml.append('<Days_List>')
    xml.append(f'<Number_of_Days>{dias}</Number_of_Days>')
    for d in dias_nombres:
        xml.append(f'<Day><Name>{d}</Name></Day>')
    xml.append('</Days_List>')
    xml.append('<Hours_List>')
    xml.append(f'<Number_of_Hours>{horas}</Number_of_Hours>')
    for h in horas_nombres:
        xml.append(f'<Hour><Name>{h}</Name></Hour>')
    xml.append('</Hours_List>')
    xml.append('<Teachers_List>')
    for p in profes:
        xml.append(f'<Teacher><Name>P{p["id"]}_{p["nombre"].replace(" ","_")}</Name></Teacher>')
    xml.append('</Teachers_List>')
    xml.append('<Subjects_List>')
    for a in asigs:
        xml.append(f'<Subject><Name>A{a["id"]}_{a["nombre"].replace(" ","_")}</Name></Subject>')
    xml.append('</Subjects_List>')
    xml.append('<Years_List>')
    for c in cursos:
        xml.append(f'<Year><Name>C{c["id"]}_{c["nombre"].replace(" ","_")}</Name>')
        xml.append(f'<Number_of_Students>30</Number_of_Students>')
        xml.append(f'<Groups_List/>')
        xml.append(f'</Year>')
    xml.append('</Years_List>')
    xml.append('<Activities_List>')
    act_id = 1
    map_act = {}
    for asig in asignacs:
        cid = asig["curso_id"]
        aid = asig["asignatura_id"]
        pid = asig["profesor_id"]
        hrs = asig["horas_semanales"]
        cnom = next((f'C{c["id"]}_{c["nombre"].replace(" ","_")}' for c in cursos if c["id"]==cid), None)
        anom = next((f'A{a["id"]}_{a["nombre"].replace(" ","_")}' for a in asigs if a["id"]==aid), None)
        pnom = next((f'P{p["id"]}_{p["nombre"].replace(" ","_")}' for p in profes if p["id"]==pid), None)
        if not cnom or not anom or not pnom:
            continue
        doble = next((a.get("requiere_doble",0) for a in asigs if a["id"]==aid), 0)
        if doble and hrs >= 2:
            pares = hrs // 2
            for _ in range(pares):
                xml.append(f'<Activity><Teacher>{pnom}</Teacher><Subject>{anom}</Subject><Students>{cnom}</Students><Duration>2</Duration><Total_Duration>{hrs}</Total_Duration><Id>{act_id}</Id><Activity_Group_Id>{act_id}</Activity_Group_Id><Number_Of_Students>30</Number_Of_Students><Active>true</Active><Comments></Comments></Activity>')
                map_act[act_id] = {"curso_id":cid,"asignatura_id":aid,"profesor_id":pid}
                act_id += 1
            if hrs % 2 == 1:
                xml.append(f'<Activity><Teacher>{pnom}</Teacher><Subject>{anom}</Subject><Students>{cnom}</Students><Duration>1</Duration><Total_Duration>{hrs}</Total_Duration><Id>{act_id}</Id><Activity_Group_Id>{act_id}</Activity_Group_Id><Number_Of_Students>30</Number_Of_Students><Active>true</Active><Comments></Comments></Activity>')
                map_act[act_id] = {"curso_id":cid,"asignatura_id":aid,"profesor_id":pid}
                act_id += 1
        else:
            for _ in range(hrs):
                xml.append(f'<Activity><Teacher>{pnom}</Teacher><Subject>{anom}</Subject><Students>{cnom}</Students><Duration>1</Duration><Total_Duration>{hrs}</Total_Duration><Id>{act_id}</Id><Activity_Group_Id>{act_id}</Activity_Group_Id><Number_Of_Students>30</Number_Of_Students><Active>true</Active><Comments></Comments></Activity>')
                map_act[act_id] = {"curso_id":cid,"asignatura_id":aid,"profesor_id":pid}
                act_id += 1
    xml.append('</Activities_List>')
    xml.append('<Constraints_List>')
    xml.append('<ConstraintBasicCompulsoryTime><Weight_Percentage>100</Weight_Percentage><Active>true</Active><Comments></Comments></ConstraintBasicCompulsoryTime>')
    xml.append('<ConstraintBasicCompulsorySpace><Weight_Percentage>100</Weight_Percentage><Active>true</Active><Comments></Comments></ConstraintBasicCompulsorySpace>')
    xml.append('</Constraints_List>')
    xml.append('</fet>')
    return "\n".join(xml), map_act

def parsear_resultado(directorio, map_act):
    horario = []
    dias_map = {"Lunes":1,"Martes":2,"Miercoles":3,"Jueves":4,"Viernes":5}
    for archivo in os.listdir(directorio):
        if not archivo.endswith(".xml") or "activities" not in archivo:
            continue
        ruta = os.path.join(directorio, archivo)
        with open(ruta, "r", encoding="utf-8") as f:
            contenido = f.read()
        import re
        actividades = re.findall(r'<Activity_Id>(\d+)</Activity_Id>.*?<Day>(.*?)</Day>.*?<Hour>(.*?)</Hour>', contenido, re.DOTALL)
        for act_id_str, dia_nom, hora_nom in actividades:
            act_id = int(act_id_str)
            dia = dias_map.get(dia_nom.strip(), 0)
            hora_n = hora_nom.strip()
            hora = int(hora_n.replace("Hora_","")) if hora_n.startswith("Hora_") else 0
            if act_id in map_act and dia > 0 and hora > 0:
                info = map_act[act_id]
                horario.append({"curso_id":info["curso_id"],"asignatura_id":info["asignatura_id"],"profesor_id":info["profesor_id"],"dia":dia,"hora":hora})
    return horario

@app.route("/generar", methods=["POST"])
def generar():
    datos = request.get_json()
    if not datos:
        return jsonify({"ok": False, "error": "Sin datos"}), 400
    if not descargar_fet():
        return jsonify({"ok": False, "error": "No se pudo descargar FET"}), 500
    tmpdir = tempfile.mkdtemp()
    try:
        xml_content, map_act = construir_xml(datos)
        xml_path = os.path.join(tmpdir, "horario.fet")
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(xml_content)
        resultado = subprocess.run([FET_BIN, "--inputfile", xml_path, "--outputdir", tmpdir, "--timelimitseconds", "60", "--quiet", "true"], capture_output=True, text=True, timeout=90)
        horario = parsear_resultado(tmpdir, map_act)
        if not horario:
            return jsonify({"ok": False, "error": "FET no genero resultado", "log": resultado.stdout[-2000:] if resultado.stdout else ""}), 500
        return jsonify({"ok": True, "bloques": len(horario), "horario": horario})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "servicio": "FET-Taralix"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
