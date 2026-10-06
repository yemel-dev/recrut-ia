"""Serveur de développement AUTONOME du Module 1 (sans frontend, sans le reste de l'app).

    uvicorn backend.agent.dev_server:app --reload --port 8765

- http://127.0.0.1:8765/import : petite page pour importer des CV (glisser-déposer) et voir la liste
- http://127.0.0.1:8765/docs   : Swagger, pour tester les autres routes
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from .api import router

app = FastAPI(title="Injara — Module 1 Gmail (serveur de dev)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.get("/health")
def health():
    return {"ok": True}


IMPORT_PAGE = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>Injara — Import de CV (dev)</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#222}
 #zone{border:2px dashed #888;border-radius:10px;padding:2.5rem;text-align:center;cursor:pointer}
 #zone.over{background:#eef6ff;border-color:#2b7de9}
 button{padding:.6rem 1.2rem;margin-top:1rem;font-size:1rem;cursor:pointer}
 table{border-collapse:collapse;width:100%;margin-top:1rem} td,th{border-bottom:1px solid #ddd;padding:.4rem;text-align:left;font-size:.9rem}
 .ok{color:#0a7a2f}.warn{color:#b26a00}.ko{color:#b00020}
</style></head><body>
<h1>Importer des CV</h1>
<div id="zone">Glissez vos CV ici (PDF, DOCX ou ZIP)<br>ou cliquez pour les choisir
<input id="input" type="file" multiple accept=".pdf,.docx,.zip" hidden></div>
<p id="chosen"></p>
<button id="go" disabled>Importer</button>
<div id="result"></div>
<h2>CV enregistrés</h2>
<table><thead><tr><th>Fichier</th><th>Source</th><th>Expéditeur</th><th>Reçu le</th></tr></thead><tbody id="list"></tbody></table>
<script>
const zone = document.getElementById("zone"), input = document.getElementById("input");
const go = document.getElementById("go"), chosen = document.getElementById("chosen");
let files = [];
function setFiles(list){ files = [...list]; chosen.textContent = files.length ? files.length + " fichier(s) : " + files.map(f => f.name).join(", ") : ""; go.disabled = !files.length; }
zone.onclick = () => input.click();
input.onchange = () => setFiles(input.files);
zone.ondragover = e => { e.preventDefault(); zone.classList.add("over"); };
zone.ondragleave = () => zone.classList.remove("over");
zone.ondrop = e => { e.preventDefault(); zone.classList.remove("over"); setFiles(e.dataTransfer.files); };
go.onclick = async () => {
  const form = new FormData(); files.forEach(f => form.append("files", f));
  go.disabled = true;
  const res = await fetch("/gmail/cvs/upload", { method: "POST", body: form });
  const out = document.getElementById("result");
  if (!res.ok) { out.innerHTML = '<p class="ko">Erreur ' + res.status + '</p>'; go.disabled = false; return; }
  const d = await res.json();
  out.innerHTML = '<p class="ok">' + d.imported.length + ' CV importé(s)</p><p class="warn">' + d.duplicates_skipped + ' doublon(s) ignoré(s)</p>'
    + (d.rejected.length ? '<p class="ko">' + d.rejected.length + ' rejeté(s) :</p><ul>' + d.rejected.map(r => '<li>' + r.filename + ' — ' + r.reason + '</li>').join("") + '</ul>' : "");
  setFiles([]); input.value = ""; refresh();
};
async function refresh(){
  const cvs = await (await fetch("/gmail/cvs?limit=200")).json();
  document.getElementById("list").innerHTML = cvs.map(c => "<tr><td>" + c.filename + "</td><td>" + c.source + "</td><td>" + (c.sender_name || "—") + "</td><td>" + c.received_at.slice(0,16).replace("T"," ") + "</td></tr>").join("");
}
refresh();
</script></body></html>"""


@app.get("/import", response_class=HTMLResponse, include_in_schema=False)
def import_page():
    return IMPORT_PAGE
