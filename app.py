import os
from flask import Flask, request, Response, render_template_string, session, jsonify
from groq import Groq

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_key")

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

SYSTEM_PROMPT = {"role": "system", "content": "You are a helpful assistant."}

HTML = """
<!doctype html>
<html>
<head>
<title>Drew-GPT</title>

<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>

<style>
body {
    margin:0;
    font-family: Arial;
    background:#0f0f0f;
    color:white;
    display:flex;
    height:100vh;
}

/* Sidebar */
#sidebar {
    width:200px;
    background:#111;
    padding:10px;
    border-right:1px solid #222;
}

#newChat {
    width:100%;
    padding:10px;
    background:#2563eb;
    border:none;
    color:white;
    cursor:pointer;
}

/* Main */
#main {
    flex:1;
    display:flex;
    flex-direction:column;
}

#header {
    padding:15px;
    background:#111;
    text-align:center;
    font-weight:bold;
    border-bottom:1px solid #222;
}

#chat {
    flex:1;
    overflow-y:auto;
    padding:20px;
}

.msg {
    max-width:70%;
    padding:12px;
    margin:10px 0;
    border-radius:12px;
    white-space:pre-wrap;
}

.user {
    background:#2563eb;
    margin-left:auto;
}

.assistant {
    background:#2a2a2a;
    margin-right:auto;
}

#inputBar {
    display:flex;
    padding:10px;
    background:#111;
}

textarea {
    flex:1;
    padding:10px;
    border:none;
    border-radius:8px;
    background:#222;
    color:white;
    resize:none;
}

button {
    margin-left:10px;
    padding:10px;
    border:none;
    border-radius:8px;
    background:#2563eb;
    color:white;
    cursor:pointer;
}
</style>
</head>

<body>

<div id="sidebar">
    <button id="newChat" onclick="newChat()">+ New Chat</button>
</div>

<div id="main">
    <div id="header">Drew-GPT</div>

    <div id="chat"></div>

    <div id="inputBar">
        <textarea id="input" rows="1" placeholder="Message..."></textarea>
        <button onclick="sendMessage()">Send</button>
    </div>
</div>

<script>
let chatDiv = document.getElementById("chat");

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
    let botDiv = addMessage("assistant", "");

    const response = await fetch("/chat", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({message: text})
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    let fullText = "";

    while (true) {
        const {value, done} = await reader.read();
        if (done) break;

        let chunk = decoder.decode(value);
        fullText += chunk;
        botDiv.innerHTML = marked.parse(fullText);
        chatDiv.scrollTop = chatDiv.scrollHeight;
    }
}

/* ENTER TO SEND */
document.getElementById("input").addEventListener("keydown", function(e) {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

/* NEW CHAT */
async function newChat() {
    await fetch("/reset", {method: "POST"});
    chatDiv.innerHTML = "";
}
</script>

</body>
</html>
"""


@app.route("/")
def index():
    if "messages" not in session:
        session["messages"] = [SYSTEM_PROMPT]
    return render_template_string(HTML)


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_msg = data["message"]

    if "messages" not in session:
        session["messages"] = [SYSTEM_PROMPT]

    messages = session["messages"]
    messages.append({"role": "user", "content": user_msg})

    def generate():
        stream = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            stream=True,
        )

        full = ""

        for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            full += token
            yield token

        messages.append({"role": "assistant", "content": full})
        session["messages"] = messages

    return Response(generate(), mimetype="text/plain")


@app.route("/reset", methods=["POST"])
def reset():
    session["messages"] = [SYSTEM_PROMPT]
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
