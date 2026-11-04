import os, sqlite3, secrets, json, urllib.request, urllib.error
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "mentex.db")
app = Flask(__name__)
app.config.update(SECRET_KEY=os.getenv("SECRET_KEY", secrets.token_hex(32)),
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

SUBJECTS = {
 "Matemática": ["Operações", "Frações", "Porcentagem", "Geometria", "Equações"],
 "Português": ["Interpretação de texto", "Classes gramaticais", "Pontuação", "Ortografia", "Redação"],
 "Ciências": ["Seres vivos", "Corpo humano", "Ecologia", "Matéria e energia", "Sistema solar"],
 "História": ["Antiguidade", "Idade Média", "Brasil", "Idade Moderna", "História contemporânea"],
 "Geografia": ["Cartografia", "Clima", "Relevo", "População", "Globalização"],
 "Inglês": ["Vocabulary", "Verb to be", "Present simple", "Pronouns", "Everyday expressions"],
 "Informática": ["Lógica", "Hardware", "Software", "Internet segura", "Python"],
 "Artes": ["Cores", "Música", "Artes visuais", "Teatro", "Cultura"]
}

def connect():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db: db.close()

def init_db():
    with sqlite3.connect(DB) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL, xp INTEGER NOT NULL DEFAULT 0,
          coins INTEGER NOT NULL DEFAULT 100, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS progress(
          user_id INTEGER NOT NULL, subject TEXT NOT NULL, level INTEGER NOT NULL DEFAULT 1,
          completed INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(user_id,subject),
          FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS settings(
          user_id INTEGER PRIMARY KEY, music INTEGER DEFAULT 1, music_volume REAL DEFAULT .18,
          effects INTEGER DEFAULT 1, effects_volume REAL DEFAULT .55,
          animations INTEGER DEFAULT 1, FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS achievements(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, code TEXT,
          unlocked_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id,code));
        """)
        db.commit()

def current_user():
    if not session.get("uid"): return None
    return connect().execute("SELECT id,username,xp,coins FROM users WHERE id=?", (session["uid"],)).fetchone()

def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not current_user(): return jsonify(error="Faça login para continuar."), 401
        return fn(*a, **kw)
    return wrapper

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/api/status")
def status():
    return jsonify(ok=True, ai_mode="real" if os.getenv("OPENAI_API_KEY") else "local")

@app.post("/api/register")
def register():
    data=request.get_json(silent=True) or {}
    username=str(data.get("username","")).strip()
    password=str(data.get("password",""))
    if len(username)<3 or len(username)>24 or not username.replace("_","").isalnum():
        return jsonify(error="Use um nome de 3 a 24 caracteres (letras, números ou _)."),400
    if len(password)<8: return jsonify(error="A senha precisa ter pelo menos 8 caracteres."),400
    db=connect()
    try:
        cur=db.execute("INSERT INTO users(username,password_hash) VALUES(?,?)",
                       (username,generate_password_hash(password)))
        uid=cur.lastrowid
        for subject in SUBJECTS:
            db.execute("INSERT INTO progress(user_id,subject) VALUES(?,?)",(uid,subject))
        db.execute("INSERT INTO settings(user_id) VALUES(?)",(uid,))
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify(error="Esse nome de usuário já está em uso."),409
    session.clear(); session["uid"]=uid
    return jsonify(ok=True)

@app.post("/api/login")
def login():
    data=request.get_json(silent=True) or {}
    row=connect().execute("SELECT * FROM users WHERE username=?",(str(data.get("username","")).strip(),)).fetchone()
    if not row or not check_password_hash(row["password_hash"],str(data.get("password",""))):
        return jsonify(error="Usuário ou senha incorretos."),401
    session.clear(); session["uid"]=row["id"]
    return jsonify(ok=True)

@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)

@app.get("/api/me")
def me():
    user=current_user()
    if not user: return jsonify(authenticated=False)
    db=connect()
    progress=db.execute("SELECT subject,level,completed FROM progress WHERE user_id=? ORDER BY subject",(user["id"],)).fetchall()
    settings=db.execute("SELECT * FROM settings WHERE user_id=?",(user["id"],)).fetchone()
    achievements=db.execute("SELECT code FROM achievements WHERE user_id=?",(user["id"],)).fetchall()
    return jsonify(authenticated=True, username=user["username"], xp=user["xp"], coins=user["coins"],
                   level=max(1, user["xp"]//250+1), progress=[dict(x) for x in progress],
                   settings=dict(settings) if settings else {}, achievements=[x["code"] for x in achievements])

@app.post("/api/settings")
@login_required
def save_settings():
    d=request.get_json(silent=True) or {}
    music=int(bool(d.get("music",True))); effects=int(bool(d.get("effects",True)))
    animations=int(bool(d.get("animations",True)))
    mv=max(0,min(1,float(d.get("music_volume",.18))))
    ev=max(0,min(1,float(d.get("effects_volume",.55))))
    connect().execute("""UPDATE settings SET music=?,effects=?,animations=?,music_volume=?,effects_volume=? WHERE user_id=?""",
                      (music,effects,animations,mv,ev,session["uid"]))
    connect().commit()
    return jsonify(ok=True)

def make_question(subject, level, index):
    # Questões locais didáticas e determinísticas por matéria; sem fingir geração por IA.
    bank = {
      "Matemática": [
        ("Quanto é {a} + {b}?", lambda a,b:a+b, "Some as unidades e confira o resultado."),
        ("Quanto é {a} × {b}?", lambda a,b:a*b, "Multiplicação é uma adição repetida."),
        ("Quanto é {a} - {b}?", lambda a,b:a-b, "Subtraia o segundo valor do primeiro.")
      ],
      "Português": [
        ("Qual sinal encerra normalmente uma pergunta?", None, "O ponto de interrogação indica uma pergunta."),
        ("Qual palavra é um verbo: casa, correr ou azul?", None, "Verbos expressam ações, estados ou fenômenos."),
        ("Qual é o plural de 'flor'?", None, "Em geral, acrescentamos -es ou -s conforme a palavra.")
      ],
      "Ciências": [
        ("Qual astro fornece luz e calor à Terra?", None, "O Sol é a estrela do nosso sistema."),
        ("Qual órgão bombeia o sangue?", None, "O coração impulsiona o sangue pelo corpo."),
        ("Como se chama o processo pelo qual plantas produzem alimento usando luz?", None, "A fotossíntese utiliza luz, água e gás carbônico.")
      ],
      "História": [
        ("Qual fonte pode ajudar a estudar o passado?", None, "Documentos, objetos, imagens e relatos são fontes históricas."),
        ("Em qual continente surgiu o Egito Antigo?", None, "A civilização egípcia desenvolveu-se no nordeste da África."),
        ("O que uma linha do tempo organiza?", None, "Ela organiza acontecimentos em ordem cronológica.")
      ],
      "Geografia": [
        ("Qual instrumento representa a superfície terrestre em escala?", None, "Mapas representam espaços e fenômenos geográficos."),
        ("Como chamamos o conjunto das condições atmosféricas médias de uma região?", None, "Clima é observado em períodos longos."),
        ("Qual é o maior oceano da Terra?", None, "O Pacífico é o maior oceano.")
      ],
      "Inglês": [
        ("What is the meaning of 'apple'?", None, "Apple significa maçã."),
        ("Complete: I ___ a student.", None, "Com 'I', usamos 'am' no verbo to be."),
        ("What is the opposite of 'hot'?", None, "Cold é o oposto de hot.")
      ],
      "Informática": [
        ("Qual componente executa instruções de um computador?", None, "A CPU processa instruções."),
        ("O que é um algoritmo?", None, "É uma sequência organizada de passos para resolver um problema."),
        ("Qual linguagem estrutura o conteúdo de páginas web?", None, "HTML define a estrutura do conteúdo.")
      ],
      "Artes": [
        ("Quais são as três cores-pigmento primárias tradicionais?", None, "Em artes, costuma-se estudar vermelho, amarelo e azul."),
        ("Qual elemento organiza sons no tempo?", None, "Ritmo organiza durações e pulsações."),
        ("Como se chama a arte de representar ações em um palco?", None, "Teatro combina interpretação, texto, espaço e ação.")
      ]
    }
    if subject=="Matemática":
        a=2+(level*3+index*7)%19; b=1+(level*5+index*3)%12
        template, fn, explain=bank[subject][(level+index)%3]
        if "×" in template: correct=fn(a,b); prompt=template.format(a=a,b=b)
        elif "+" in template: correct=fn(a,b); prompt=template.format(a=a,b=b)
        else:
            if b>a: a,b=b,a
            correct=fn(a,b); prompt=template.format(a=a,b=b)
        choices=sorted(set([correct,correct+2,correct-1,correct+5]))
        return {"question":prompt,"choices":[str(x) for x in choices],"answer":str(correct),"explanation":explain}
    templates = {
      "Português":[["Ponto final","Ponto de interrogação","Vírgula","Dois-pontos"],["Correr","Casa","Azul","Ontem"],["Flores","Flor","Flors","Florais"]],
      "Ciências":[["Lua","Sol","Marte","Vênus"],["Pulmão","Coração","Estômago","Rim"],["Fotossíntese","Respiração","Evaporação","Erosão"]],
      "História":[["Fontes históricas","Previsões","Opiniões sem evidência","Propagandas"],["Ásia","África","Europa","Oceania"],["Ordem cronológica","Ordem alfabética","Tamanho","Cor"]],
      "Geografia":[["Mapa","Termômetro","Relógio","Bússola"],["Clima","Tempo instantâneo","Relevo","Vegetação"],["Atlântico","Índico","Pacífico","Ártico"]],
      "Inglês":[["Maçã","Casa","Livro","Água"],["am","is","are","be"],["Cold","Warm","Tall","Fast"]],
      "Informática":[["Monitor","CPU","Teclado","Mouse"],["Algoritmo","Navegador","Planilha","Senha"],["HTML","SQL","Python","CSS"]],
      "Artes":[["Vermelho, amarelo e azul","Verde, roxo e laranja","Preto, branco e cinza","Rosa, marrom e cinza"],["Ritmo","Volume","Silêncio","Timbre"],["Teatro","Escultura","Fotografia","Pintura"]]
    }
    prompts = {s:[x[0] for x in bank[s]] for s in bank if s!="Matemática"}
    idx=(level+index)%3
    opts=templates[subject][idx]
    answer_index={"Português":[1,0,0],"Ciências":[1,1,0],"História":[0,1,0],"Geografia":[0,0,2],"Inglês":[0,0,0],"Informática":[1,0,0],"Artes":[0,0,0]}[subject][idx]
    return {"question":prompts[subject][idx],"choices":opts,"answer":opts[answer_index],"explanation":bank[subject][idx][2]}

@app.get("/api/level/<subject>")
@login_required
def get_level(subject):
    if subject not in SUBJECTS: return jsonify(error="Matéria inválida."),404
    row=connect().execute("SELECT level FROM progress WHERE user_id=? AND subject=?",(session["uid"],subject)).fetchone()
    level=row["level"] if row else 1
    questions=[make_question(subject,level,i) for i in range(5)]
    return jsonify(subject=subject,level=level,difficulty=("Fácil" if level<=10 else "Médio" if level<=25 else "Difícil" if level<=40 else "Avançado"),questions=questions)

@app.post("/api/complete")
@login_required
def complete():
    d=request.get_json(silent=True) or {}; subject=d.get("subject")
    if subject not in SUBJECTS: return jsonify(error="Matéria inválida."),400
    row=connect().execute("SELECT level FROM progress WHERE user_id=? AND subject=?",(session["uid"],subject)).fetchone()
    level=row["level"] if row else 1
    score=max(0,min(5,int(d.get("score",0))))
    xp=score*12+20; coins=score*3+5
    db=connect()
    db.execute("UPDATE users SET xp=xp+?,coins=coins+? WHERE id=?",(xp,coins,session["uid"]))
    db.execute("UPDATE progress SET level=MIN(level+1,50),completed=completed+1 WHERE user_id=? AND subject=?",(session["uid"],subject))
    if score==5: db.execute("INSERT OR IGNORE INTO achievements(user_id,code) VALUES(?,?)",(session["uid"],"perfect_stage"))
    db.commit()
    return jsonify(ok=True,xp=xp,coins=coins,next_level=min(50,level+1),perfect=score==5)

@app.post("/api/teacher")
def teacher():
    d=request.get_json(silent=True) or {}
    question=str(d.get("question","")).strip()[:2000]
    subject=str(d.get("subject","Geral"))[:50]
    if not question: return jsonify(error="Digite sua dúvida."),400
    key=os.getenv("OPENAI_API_KEY","").strip()
    if key:
        payload={"model":os.getenv("OPENAI_MODEL","gpt-4o-mini"),
          "instructions":"Você é o Professor MenteX. Responda em português brasileiro, com explicações claras, corretas, adequadas a crianças e adolescentes. Não peça dados pessoais. Ensine passo a passo e dê um exemplo.",
          "input":f"Matéria: {subject}\nPergunta: {question}","max_output_tokens":650}
        req=urllib.request.Request("https://api.openai.com/v1/responses",data=json.dumps(payload).encode(),
          headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},method="POST")
        try:
            with urllib.request.urlopen(req,timeout=30) as res: result=json.loads(res.read())
            answer="\n".join(c.get("text","") for item in result.get("output",[]) for c in item.get("content",[]) if c.get("type")=="output_text")
            if answer.strip(): return jsonify(answer=answer,mode="IA conectada")
        except Exception:
            return jsonify(error="Não foi possível conectar à IA. Verifique a chave e tente novamente."),502
    return jsonify(answer=f"Vamos estudar {subject}!\n\nSua pergunta: {question}\n\nUma boa estratégia é dividir o assunto em partes menores, identificar os conceitos principais e procurar um exemplo. Depois, tente explicar o tema com suas próprias palavras.\n\nEste é o modo local de demonstração. Para respostas personalizadas, configure OPENAI_API_KEY no servidor.",mode="Modo local")

init_db()

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT",5000)),debug=False)
