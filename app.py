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


# ---------------- STORAGE ----------------

def user_id():
    uid = request.cookies.get("user_id")
    if not uid:
        uid = str(uuid.uuid4())
    return uid


def path(uid):
    return os.path.join(CHAT_DIR, f"{uid}.json")


def load(uid):
    p = path(uid)
    if os.path.exists(p):
        with open(p, "r") as f:
            return json.load(f)
    return []


def save(uid, data):
    with open(path(uid), "w") as f:
        json.dump(data, f)


def find_chat(chats, cid):
    for c in chats:
        if c["id"] == cid:
            return c
    return None


# ---------------- UI ----------------

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

/* SIDEBAR */
#sidebar {
    width: 260px;
    padding: 12px;
    background: #111827;
    overflow-y: auto;
}

.chatItem {
    padding: 10px;
    margin: 6px 0;
    background: #1f2937;
    border-radius: 10px;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
}

.chatItem:hover {
    background: #374151;
}

.deleteBtn {
    background: transparent;
    border: none;
    color: #ff5555;
    cursor: pointer;
}

/* MAIN */
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

/* MSGS */
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

/* INPUT */
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

button {
    margin-left: 10px;
    padding: 10px;
    background: #2563eb;
    color: white;
    border: none;
    border-radius: 10px;
}
</style>
</head>

<body>

<div id="sidebar">
    <button onclick="newChat()">+ New Chat</button>
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

function add(role,text){
    let d=document.createElement("div");
    d.className="msg "+role;
    d.innerHTML=marked.parse(text);
    chatDiv.appendChild(d);
    chatDiv.scrollTop=chatDiv.scrollHeight;
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
            chat_id:activeChat
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
    let res=await fetch("/new_chat");
    let data=await res.json();

    activeChat=data.id;
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
        del.innerText="X";
        del.className="deleteBtn";

        del.onclick=async(e)=>{
            e.stopPropagation();
            await fetch("/delete/"+c.id);

            if(activeChat===c.id){
                chatDiv.innerHTML="";
                activeChat=null;
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


# ---------------- ROUTES ----------------

@app.route("/")
def index():
    resp = make_response(render_template_string(HTML))
    if not request.cookies.get("user_id"):
        resp.set_cookie("user_id", str(uuid.uuid4()))
    return resp


@app.route("/chat", methods=["POST"])
def chat():
    uid = user_id()
    data = request.json
    msg = data["message"]
    cid = data.get("chat_id")

    chats = load(uid)

    if not chats:
        new = {
            "id": str(uuid.uuid4()),
            "title": msg[:20],
            "messages": []
        }
        chats.append(new)

    chat = find_chat(chats, cid) if cid else chats[-1]

    chat["messages"].append({"role": "user", "content": msg})

    def stream():
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=chat["messages"],
            stream=True
        )

        full = ""

        for c in res:
            token = c.choices[0].delta.content or ""
            full += token
            yield token

        chat["messages"].append({"role": "assistant", "content": full})
        save(uid, chats)

    return Response(stream(), mimetype="text/plain")


@app.route("/chats")
def chats():
    uid = user_id()
    data = load(uid)

    return jsonify([
        {"id":c["id"], "title":c["title"]}
        for c in data
    ])


@app.route("/load/<cid>")
def load_chat(cid):
    uid = user_id()
    data = load(uid)

    chat = find_chat(data, cid)
    return jsonify(chat["messages"] if chat else [])


@app.route("/delete/<cid>")
def delete(cid):
    uid = user_id()
    data = load(uid)

    data = [c for c in data if c["id"] != cid]
    save(uid, data)

    return "ok"


@app.route("/new_chat")
def new_chat():
    uid = user_id()
    data = load(uid)

    new = {
        "id": str(uuid.uuid4()),
        "title": "New chat",
        "messages": []
    }

    data.append(new)
    save(uid, data)

    return jsonify(new)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
