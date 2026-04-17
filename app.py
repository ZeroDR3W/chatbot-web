import os
import json
import uuid
from flask import Flask, request, Response, render_template_string, jsonify, make_response
from groq import Groq

app = Flask(__name__)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_key")

MODES = {
    "default": "You are a helpful assistant.",
    "study": "You are a helpful tutor who explains clearly.",
    "code": "You are an expert programmer.",
    "debate": "You argue intelligently with the user."
}

CHAT_DIR = "chats"
os.makedirs(CHAT_DIR, exist_ok=True)


def get_user():
    user_id = request.cookies.get("user_id")
    if not user_id:
        user_id = str(uuid.uuid4())
    return user_id


def file_path(user_id):
    return os.path.join(CHAT_DIR, f"{user_id}.json")


def load_data(user_id):
    path = file_path(user_id)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []


def save_data(user_id, data):
    with open(file_path(user_id), "w") as f:
        json.dump(data, f)


# ---------------- UI ----------------
HTML = """
<!doctype html>
<html>
<head>
<title>Drew-GPT</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>

<style>
body {margin:0; display:flex; height:100vh; font-family:Arial; background:#0f0f0f; color:white;}

#sidebar {width:240px; background:#111; padding:10px; overflow-y:auto;}

.chatItem {
    padding:8px;
    background:#222;
    margin:5px 0;
    border-radius:6px;
    cursor:pointer;
    display:flex;
    justify-content:space-between;
    align-items:center;
}

.deleteBtn {
    background:red;
    border:none;
    color:white;
    padding:3px 6px;
    border-radius:4px;
    cursor:pointer;
}

#main {flex:1; display:flex; flex-direction:column;}

#header {padding:15px; background:#111;}

#chat {flex:1; padding:20px; overflow-y:auto;}

.msg {max-width:70%; padding:10px; margin:10px 0; border-radius:10px;}
.user {background:#2563eb; margin-left:auto;}
.assistant {background:#2a2a2a;}

#inputBar {display:flex; padding:10px; background:#111;}

textarea {flex:1; padding:10px; background:#222; color:white; border:none;}

button {margin-left:10px; padding:10px;}
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
    if(!text)return;

    input.value="";
    add("user",text);

    let bot=document.createElement("div");
    bot.className="msg assistant";
    bot.innerText="typing...";
    chatDiv.appendChild(bot);

    const res=await fetch("/chat",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({message:text})
    });

    const reader=res.body.getReader();
    const decoder=new TextDecoder();
    let full="";

    while(true){
        let {value,done}=await reader.read();
        if(done)break;
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
    await fetch("/new_chat");
    chatDiv.innerHTML="";
    loadChats();
}

async function loadChats(){
    let res=await fetch("/chats");
    let data=await res.json();

    let list=document.getElementById("list");
    list.innerHTML="";

    data.forEach(chat=>{
        let wrap=document.createElement("div");
        wrap.className="chatItem";

        let title=document.createElement("div");
        title.innerText=chat.title;

        title.onclick=async()=>{
            let r=await fetch("/load/"+chat.id);
            let msgs=await r.json();
            chatDiv.innerHTML="";
            msgs.forEach(m=>add(m.role,m.content));
        };

        let del=document.createElement("button");
        del.className="deleteBtn";
        del.innerText="X";

        del.onclick=async(e)=>{
            e.stopPropagation();
            await fetch("/delete/"+chat.id);
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
    user_id = get_user()
    data = request.json
    msg = data["message"]

    chats = load_data(user_id)

    if not chats or chats[-1].get("done"):
        chats.append({
            "id": str(uuid.uuid4()),
            "title": msg[:20],
            "messages": [],
            "done": False
        })

    chat = chats[-1]
    chat["messages"].append({"role":"user","content":msg})

    def stream():
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=chat["messages"],
            stream=True
        )

        full=""

        for c in res:
            token=c.choices[0].delta.content or ""
            full+=token
            yield token

        chat["messages"].append({"role":"assistant","content":full})
        save_data(user_id,chats)

    return Response(stream(), mimetype="text/plain")


@app.route("/chats")
def chats():
    user_id = get_user()
    data = load_data(user_id)

    return jsonify([
        {"id":c["id"], "title":c["title"]}
        for c in data
    ])


@app.route("/load/<cid>")
def load(cid):
    user_id = get_user()
    data = load_data(user_id)

    for c in data:
        if c["id"] == cid:
            return jsonify(c["messages"])

    return jsonify([])


@app.route("/delete/<cid>")
def delete(cid):
    user_id = get_user()
    data = load_data(user_id)

    data = [c for c in data if c["id"] != cid]

    save_data(user_id, data)
    return "ok"


@app.route("/new_chat")
def new_chat():
    user_id = get_user()
    save_data(user_id, [])
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
