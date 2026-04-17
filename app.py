import os
from flask import Flask, request, Response, render_template_string, session, jsonify
from groq import Groq

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_key")

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

MODES = {
    "default": "You are a helpful assistant.",
    "study": "You are a helpful tutor who explains clearly and simply.",
    "code": "You are an expert programmer who gives clean code and explanations.",
    "debate": "You challenge the user and argue back intelligently.",
}

HTML = """<!doctype html>
<html>
<head>
<title>Drew-GPT</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
body {margin:0; display:flex; height:100vh; background:#0f0f0f; color:white; font-family:Arial;}
#sidebar {width:220px; background:#111; padding:10px; overflow-y:auto;}
#main {flex:1; display:flex; flex-direction:column;}
#header {padding:15px; text-align:center; background:#111; border-bottom:1px solid #222;}
#chat {flex:1; overflow-y:auto; padding:20px;}
.msg {max-width:70%; padding:10px; margin:10px 0; border-radius:12px;}
.user {background:#2563eb; margin-left:auto;}
.assistant {background:#2a2a2a;}
#inputBar {display:flex; padding:10px; background:#111;}
textarea {flex:1; padding:10px; border:none; border-radius:8px; background:#222; color:white;}
button {margin-left:10px; padding:10px; border:none; border-radius:8px; background:#2563eb; color:white; cursor:pointer;}
.mode {display:block; margin:5px 0; padding:8px; background:#222; cursor:pointer;}
.chat-item {padding:6px; cursor:pointer; border-bottom:1px solid #333;}
</style>
</head>
<body>

<div id="sidebar">
    <button onclick="newChat()">+ New Chat</button>

    <h4>Modes</h4>
    <div class="mode" onclick="setMode('default')">Default</div>
    <div class="mode" onclick="setMode('study')">Study</div>
    <div class="mode" onclick="setMode('code')">Coding</div>
    <div class="mode" onclick="setMode('debate')">Debate</div>

    <h4>Saved Chats</h4>
    <div id="savedChats"></div>
</div>

<div id="main">
    <div id="header">Drew-GPT</div>
    <div id="chat"></div>

    <div id="inputBar">
        <textarea id="input"></textarea>
        <button onclick="sendMessage()">Send</button>
    </div>
</div>

<script>
let chatDiv = document.getElementById("chat");
let currentMode = "default";

function addMessage(role, text) {
    let div = document.createElement("div");
    div.className = "msg " + role;
    div.innerHTML = marked.parse(text);
    chatDiv.appendChild(div);
    chatDiv.scrollTop = chatDiv.scrollHeight;
    return div;
}

async function sendMessage() {
    let input = document.getElementById("input");
    let text = input.value.trim();
    if (!text) return;

    input.value = "";

    addMessage("user", text);

    let botDiv = addMessage("assistant", "Drew-GPT is typing...");

    const response = await fetch("/chat", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({message: text, mode: currentMode})
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    let full = "";

    while (true) {
        const {value, done} = await reader.read();
        if (done) break;
        let chunk = decoder.decode(value);
        full += chunk;
        botDiv.innerHTML = marked.parse(full);
    }
}

document.getElementById("input").addEventListener("keydown", function(e){
    if(e.key==="Enter" && !e.shiftKey){
        e.preventDefault();
        sendMessage();
    }
});

function setMode(mode){
    currentMode = mode;
    alert("Mode set to " + mode);
}

async function newChat(){
    await fetch("/reset", {method:"POST"});
    chatDiv.innerHTML = "";
}

async function saveChat(){
    await fetch("/save", {method:"POST"});
    loadChats();
}

async function loadChats(){
    let res = await fetch("/chats");
    let chats = await res.json();

    let div = document.getElementById("savedChats");
    div.innerHTML = "";

    chats.forEach((c,i)=>{
        let el = document.createElement("div");
        el.className = "chat-item";
        el.innerText = "Chat " + (i+1);
        el.onclick = ()=>loadChat(i);
        div.appendChild(el);
    });
}

async function loadChat(i){
    let res = await fetch("/load/"+i);
    let chat = await res.json();

    chatDiv.innerHTML = "";
    chat.forEach(m=>addMessage(m.role, m.content));
}

loadChats();
</script>

</body>
</html>
"""

@app.route("/")
def index():
    if "messages" not in session:
        session["messages"] = []
    if "saved" not in session:
        session["saved"] = []
    return render_template_string(HTML)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_msg = data["message"]
    mode = data["mode"]

    messages = session.get("messages", [])

    system = {"role":"system","content":MODES.get(mode, MODES["default"])}

    convo = [system] + messages + [{"role":"user","content":user_msg}]

    def generate():
        stream = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=convo,
            stream=True
        )

        full = ""
        for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            full += token
            yield token

        messages.append({"role":"user","content":user_msg})
        messages.append({"role":"assistant","content":full})
        session["messages"] = messages

    return Response(generate(), mimetype="text/plain")

@app.route("/reset", methods=["POST"])
def reset():
    session["messages"] = []
    return "ok"

@app.route("/save", methods=["POST"])
def save():
    session["saved"].append(session["messages"])
    return "ok"

@app.route("/chats")
def chats():
    return jsonify(session.get("saved", []))

@app.route("/load/<int:i>")
def load(i):
    session["messages"] = session["saved"][i]
    return jsonify(session["messages"])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
