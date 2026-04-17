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
<title>ChatGPT Clone</title>
<style>
body {
    margin:0;
    font-family: Arial;
    background:#0f0f0f;
    color:white;
    display:flex;
    flex-direction:column;
    height:100vh;
}

#chat {
    flex:1;
    overflow-y:auto;
    padding:20px;
}

.msg {
    max-width:70%;
    padding:10px 14px;
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

input {
    flex:1;
    padding:10px;
    border:none;
    border-radius:8px;
    background:#222;
    color:white;
}

button {
    margin-left:10px;
    padding:10px 14px;
    border:none;
    border-radius:8px;
    background:#2563eb;
    color:white;
    cursor:pointer;
}
</style>
</head>

<body>

<div id="chat"></div>

<div id="inputBar">
    <input id="input" placeholder="Message..." />
    <button onclick="sendMessage()">Send</button>
</div>

<script>
let chatDiv = document.getElementById("chat");

function addMessage(role, text) {
    let div = document.createElement("div");
    div.className = "msg " + role;
    div.innerText = text;
    chatDiv.appendChild(div);
    chatDiv.scrollTop = chatDiv.scrollHeight;
    return div;
}

async function sendMessage() {
    let input = document.getElementById("input");
    let text = input.value;
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
        botDiv.innerText = fullText;
        chatDiv.scrollTop = chatDiv.scrollHeight;
    }
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

        full_response = ""

        for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            full_response += token
            yield token

        messages.append({"role": "assistant", "content": full_response})
        session["messages"] = messages

    return Response(generate(), mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)