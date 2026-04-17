import os
import json
import uuid
from flask import Flask, request, Response, render_template_string, jsonify, make_response
from groq import Groq

app = Flask(__name__)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_key")

CHAT_DIR = "chats"
os.makedirs(CHAT_DIR, exist_ok=True)

# ---------------- MODES ----------------

MODES = {
    "default": "You are a helpful assistant.",
    "study": "You explain things clearly and simply like a tutor.",
    "code": "You are an expert programmer who writes clean code.",
    "debate": "You challenge the user and argue intelligently."
}

# ---------------- STORAGE ----------------

def get_user_id():
    uid = request.cookies.get("user_id")
    if not uid:
        uid = str(uuid.uuid4())
    return uid


def file_path(uid):
    return os.path.join(CHAT_DIR, f"{uid}.json")


def load_user_data(uid):
    path = file_path(uid)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []


def save_user_data(uid, data):
    with open(file_path(uid), "w") as f:
        json.dump(data, f)


def find_chat(data, cid):
    for c in data:
        if c["id"] == cid:
            return c
    return None


# ---------------- FRONTEND ----------------

HTML = """
<!doctype html>
<html>
<head>
<title>Drew-GPT</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>

<style>
body {
    margin: 0;
    display: flex;
    height: 100vh;
    font-family: system-ui;
    background: #0b0f17;
    color: white;
}

#sidebar {
    width: 260px;
    background: #111827;
    padding: 12px;
    overflow-y: auto;
}

button {
    background: #2563eb;
    border: none;
    color: white;
    padding: 10px;
    border-radius: 8px;
    cursor: pointer;
    width: 100%;
    margin-bottom: 10px;
}

.mode {
    padding: 8px;
    margin: 5px 0;
    background: #1f2937;
    border-radius: 8px;
    cursor: pointer;
}

.mode:hover {
    background: #374151;
}

.chatItem {
    padding: 10px;
    margin: 6px 0;
    background: #1f2937;
    border-radius: 10px;
    display: flex;
    justify-content: space-between;
    cursor: pointer;
}

.deleteBtn {
    background: transparent;
    border: none;
    color: red;
    cursor: pointer;
}

#main {
    flex: 1;
    display: flex;
    flex-direction: column;
}

#header {
    padding: 12px;
    background: #111827;
    font-weight: bold;
}

#chat {
    flex: 1;
    padding: 20px;
    overflow-y: auto;
}

.msg {
    max-width: 70%;
    padding: 10px;
    margin: 10px 0;
    border-radius: 12px;
}

.user {
    background: #2563eb;
    margin-left: auto;
}

.assistant {
    background: #1f2937;
}

#inputBar {
    display: flex;
    padding: 10px;
    background: #111827;
}

textarea {
    flex: 1;
    padding: 10px;
    border-radius: 10px;
    border: none;
    background: #1f2937;
    color: white;
}

</style>
</head>

<body>

<div id="sidebar">
    <button onclick="newChat()">+ New Chat</button>

    <h4>Modes</h4>
    <div class="mode" onclick="setMode('default')">Default</div>
    <div class="mode" onclick="setMode('study')">Study</div>
    <div class="mode" onclick="setMode('code')">Code</div>
    <div class="mode" onclick="setMode('debate')">Debate</div>

    <h4>Chats</h4>
    <div id="list"></div>
</div>

<div id="main">
    <div id="header">Drew-GPT</div>

    <div id="chat"></div>

    <div id="inputBar">
        <textarea id="input"></textarea>
        <button onclick="send()">Send</button>
    </div>
</div>

<script>
let chatDiv = document.getElementById("chat");
let activeChat = null;
let currentMode = "default";

function add(role,text){
    let d=document.createElement("div");
    d.className="msg "+role;
    d.innerHTML=marked.parse(text);
    chatDiv.appendChild(d);
    chatDiv.scrollTop=chatDiv.scrollHeight;
}

function setMode(m){
    currentMode = m;
}

async function send(){
    let input=document.getElementById("input");
    let text=input.value.trim();
    if(!text) return;

    input.value="";
    add("user",text);

    let bot=document.createElement("div");
    bot.className="msg assistant";
    bot.innerText="typing...";
    chatDiv.appendChild(bot);

    const res=await fetch("/chat",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
            message:text,
            chat_id:activeChat,
            mode:currentMode
        })
    });

    const reader=res.body.getReader();
    const decoder=new TextDecoder();
    let full="";

    while(true){
        let {value,done}=await reader.read();
        if(done) break;
        full+=decoder.decode(value);
        bot.innerHTML=marked.parse(full);
    }

    loadChats();
}

document.getElementById("input").addEventListener("keydown",e=>{
    if(e.key==="Enter"&&!e.shiftKey){
        e.preventDefault();
        send();
    }
});

async function newChat(){
    let res = await fetch("/new_chat");
    let data = await res.json();

    activeChat = data.id;
    chatDiv.innerHTML="";
    loadChats();
}

async function loadChats(){
    let res=await fetch("/chats");
    let data=await res.json();

    let list=document.getElementById("list");
    list.innerHTML="";

    data.forEach(c=>{
        let wrap=document.createElement("div");
        wrap.className="chatItem";

        let title=document.createElement("div");
        title.innerText=c.title;

        title.onclick=async()=>{
            activeChat=c.id;

            let r=await fetch("/load/"+c.id);
            let msgs=await r.json();

            chatDiv.innerHTML="";
            msgs.forEach(m=>add(m.role,m.content));
        };

        let del=document.createElement("button");
        del.className="deleteBtn";
        del.innerText="X";

        del.onclick=async(e)=>{
            e.stopPropagation();
            await fetch("/delete/"+c.id);

            if(activeChat===c.id){
                activeChat=null;
                chatDiv.innerHTML="";
            }

            loadChats();
        };

        wrap.appendChild(title);
        wrap.appendChild(del);
        list.appendChild(wrap);
    });
}

loadChats();
</script>

</body>
</html>
"""


# ---------------- BACKEND ----------------

@app.route("/")
def index():
    resp = make_response(render_template_string(HTML))
    if not request.cookies.get("user_id"):
        resp.set_cookie("user_id", str(uuid.uuid4()))
    return resp


@app.route("/chat", methods=["POST"])
def chat():
    uid = get_user_id()
    data = request.json

    msg = data["message"]
    cid = data.get("chat_id")
    mode = data.get("mode", "default")

    chats = load_user_data(uid)

    if not chats:
        chats.append({
            "id": str(uuid.uuid4()),
            "title": msg[:20],
            "messages": []
        })

    chat = find_chat(chats, cid) if cid else chats[-1]

    chat["messages"].append({"role": "user", "content": msg})

    system = {
        "role": "system",
        "content": MODES.get(mode, MODES["default"])
    }

    convo = [system] + chat["messages"]

    def stream():
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=convo,
            stream=True
        )

        full = ""

        for c in res:
            token = c.choices[0].delta.content or ""
            full += token
            yield token

        chat["messages"].append({"role": "assistant", "content": full})
        save_user_data(uid, chats)

    return Response(stream(), mimetype="text/plain")


@app.route("/chats")
def chats():
    uid = get_user_id()
    data = load_user_data(uid)

    return jsonify([
        {"id": c["id"], "title": c["title"]}
        for c in data
    ])


@app.route("/load/<cid>")
def load_chat(cid):
    uid = get_user_id()
    data = load_user_data(uid)

    chat = find_chat(data, cid)
    return jsonify(chat["messages"] if chat else [])


@app.route("/delete/<cid>")
def delete(cid):
    uid = get_user_id()
    data = load_user_data(uid)

    data = [c for c in data if c["id"] != cid]
    save_user_data(uid, data)

    return "ok"


@app.route("/new_chat")
def new_chat():
    uid = get_user_id()
    data = load_user_data(uid)

    new = {
        "id": str(uuid.uuid4()),
        "title": "New chat",
        "messages": []
    }

    data.append(new)
    save_user_data(uid, data)

    return jsonify(new)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
