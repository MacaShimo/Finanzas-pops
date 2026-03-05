# ============================================================
# API REST - Control de Finanzas Personales
# Stack: FastAPI + psycopg2 (PostgreSQL / Supabase)
# ============================================================
# INSTALACIÓN:
#   pip install fastapi uvicorn psycopg2-binary python-dotenv
#
# ARRANCAR LOCAL:
#   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
#
# VARIABLES DE ENTORNO (configurar en Railway):
#   DATABASE_URL = postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres
# ============================================================

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from datetime import date
import psycopg2
import psycopg2.extras
import os

# ── Conexión a PostgreSQL (Supabase) ─────────────────────────
# Lee la URL desde variable de entorno (Railway la inyecta automáticamente)
DATABASE_URL = os.environ.get("DATABASE_URL", "")

def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

# ── App ───────────────────────────────────────────────────────
app = FastAPI(title="Finanzas Personales API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Modelos ───────────────────────────────────────────────────
class MovimientoIn(BaseModel):
    cuenta_id:    int
    fecha:        date
    concepto:     Optional[str] = None
    importe:      float
    saldo:        Optional[float] = None
    area_id:      Optional[int] = None
    categoria_id: Optional[int] = None
    tipo:         str            # 'GASTO' o 'INGRESO'
    descripcion:  Optional[str] = None
    usuario_id:   Optional[int] = None
    es_personal:  int = 0        # 0=casa/compartido, 1=personal

# ── Endpoints ─────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "mensaje": "API Finanzas Personales funcionando ✅"}


# --- CATÁLOGOS ---

@app.get("/areas")
def listar_areas():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, nombre FROM areas ORDER BY nombre")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return list(rows)


@app.get("/categorias")
def listar_categorias(area_id: Optional[int] = None):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if area_id:
        cur.execute("SELECT id, area_id, nombre FROM categorias WHERE area_id=%s ORDER BY nombre", (area_id,))
    else:
        cur.execute("SELECT id, area_id, nombre FROM categorias ORDER BY nombre")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return list(rows)


@app.get("/cuentas")
def listar_cuentas():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, nombre, tipo FROM cuentas ORDER BY nombre")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return list(rows)


@app.get("/usuarios")
def listar_usuarios():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, nombre FROM usuarios ORDER BY nombre")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return list(rows)


# --- MOVIMIENTOS ---

@app.post("/movimientos", status_code=201)
def crear_movimiento(m: MovimientoIn):
    if m.tipo not in ("GASTO", "INGRESO"):
        raise HTTPException(400, "tipo debe ser GASTO o INGRESO")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO movimientos
           (cuenta_id, fecha, concepto, importe, saldo, area_id, categoria_id,
            tipo, descripcion, usuario_id, es_personal)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (m.cuenta_id, m.fecha, m.concepto, m.importe, m.saldo,
         m.area_id, m.categoria_id, m.tipo, m.descripcion,
         m.usuario_id, m.es_personal)
    )
    conn.commit()
    cur.close(); conn.close()
    return {"mensaje": "Movimiento registrado ✅"}


@app.get("/movimientos")
def listar_movimientos(
    mes:         Optional[int] = None,
    anio:        Optional[int] = None,
    tipo:        Optional[str] = None,
    usuario_id:  Optional[int] = None,
    es_personal: Optional[int] = None,
    limit:       int = 50
):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = """
        SELECT m.id, c.nombre as cuenta, m.fecha, m.concepto, m.importe,
               a.nombre as area, m.tipo, m.descripcion,
               u.nombre as usuario, m.usuario_id, m.es_personal
        FROM movimientos m
        LEFT JOIN cuentas c   ON m.cuenta_id  = c.id
        LEFT JOIN areas a     ON m.area_id    = a.id
        LEFT JOIN usuarios u  ON m.usuario_id = u.id
        WHERE 1=1
    """
    params = []
    if mes         is not None: query += " AND EXTRACT(MONTH FROM m.fecha) = %s"; params.append(mes)
    if anio        is not None: query += " AND EXTRACT(YEAR  FROM m.fecha) = %s"; params.append(anio)
    if tipo:                    query += " AND m.tipo = %s";                       params.append(tipo)
    if usuario_id:              query += " AND m.usuario_id = %s";                 params.append(usuario_id)
    if es_personal is not None: query += " AND m.es_personal = %s";                params.append(es_personal)
    query += f" ORDER BY m.fecha DESC LIMIT %s"
    params.append(limit)

    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) | {"fecha": str(r["fecha"])} for r in rows]


@app.delete("/movimientos/{mov_id}")
def eliminar_movimiento(mov_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM movimientos WHERE id=%s", (mov_id,))
    conn.commit()
    cur.close(); conn.close()
    return {"mensaje": f"Movimiento {mov_id} eliminado"}


@app.put("/movimientos/{mov_id}")
def editar_movimiento(mov_id: int, m: MovimientoIn):
    if m.tipo not in ("GASTO", "INGRESO"):
        raise HTTPException(400, "tipo debe ser GASTO o INGRESO")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """UPDATE movimientos SET
           cuenta_id=%s, fecha=%s, concepto=%s, importe=%s, saldo=%s,
           area_id=%s, categoria_id=%s, tipo=%s, descripcion=%s,
           usuario_id=%s, es_personal=%s
           WHERE id=%s""",
        (m.cuenta_id, m.fecha, m.concepto, m.importe, m.saldo,
         m.area_id, m.categoria_id, m.tipo, m.descripcion,
         m.usuario_id, m.es_personal, mov_id)
    )
    conn.commit()
    cur.close(); conn.close()
    return {"mensaje": f"Movimiento {mov_id} actualizado ✅"}


# --- RESÚMENES ---

@app.get("/resumen/mensual")
def resumen_mensual(
    anio: int, mes: int,
    usuario_id:  Optional[int] = None,
    es_personal: Optional[int] = None
):
    conn = get_conn()
    cur = conn.cursor()
    query = """
        SELECT tipo, SUM(ABS(importe)) as total
        FROM movimientos
        WHERE EXTRACT(YEAR FROM fecha)=%s AND EXTRACT(MONTH FROM fecha)=%s
    """
    params = [anio, mes]
    if usuario_id:               query += " AND usuario_id=%s";   params.append(usuario_id)
    if es_personal is not None:  query += " AND es_personal=%s";  params.append(es_personal)
    query += " GROUP BY tipo"
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close(); conn.close()
    result   = {r[0]: float(r[1]) for r in rows}
    ingresos = result.get("INGRESO", 0)
    gastos   = result.get("GASTO",   0)
    return {"anio": anio, "mes": mes,
            "ingresos": ingresos, "gastos": gastos,
            "neto": round(ingresos - gastos, 2)}


@app.get("/resumen/por-area")
def resumen_por_area(
    anio: int,
    mes:         Optional[int] = None,
    usuario_id:  Optional[int] = None,
    es_personal: Optional[int] = None
):
    conn = get_conn()
    cur = conn.cursor()
    query = """
        SELECT a.nombre, SUM(ABS(m.importe)) as total
        FROM movimientos m
        JOIN areas a ON m.area_id = a.id
        WHERE m.tipo='GASTO' AND EXTRACT(YEAR FROM m.fecha)=%s
    """
    params = [anio]
    if mes:                      query += " AND EXTRACT(MONTH FROM m.fecha)=%s"; params.append(mes)
    if usuario_id:               query += " AND m.usuario_id=%s";                params.append(usuario_id)
    if es_personal is not None:  query += " AND m.es_personal=%s";               params.append(es_personal)
    query += " GROUP BY a.nombre ORDER BY total DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"area": r[0], "total": float(r[1])} for r in rows]


@app.get("/app")
def app_movil():
    return FileResponse("03_app_movil.html")
