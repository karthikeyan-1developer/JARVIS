const roomId = "room1";
const ws = new WebSocket(`ws://127.0.0.1:8000/ws/${roomId}`);

ws.onopen = () => {
  console.log("Connected to WebSocket server");
};

ws.onmessage = (event) => {
  addMessage("Jarvis", event.data, "jarvis");
  try {
    const utterance = new SpeechSynthesisUtterance(event.data);
    speechSynthesis.speak(utterance);
  } catch (e) {
    console.warn("Speech synthesis failed:", e);
  }
};

document.getElementById("sendBtn").addEventListener("click", () => {
  const input = document.getElementById("messageInput");
  const message = input.value.trim();
  if (message !== "" && ws.readyState === WebSocket.OPEN) {
    addMessage("You", message, "you");
    ws.send(message);
    input.value = "";
  }
});

function addMessage(sender, text, type) {
  const chat = document.getElementById("chat");
  const msgDiv = document.createElement("div");
  msgDiv.className = `message ${type}`;
  msgDiv.textContent = `${sender}: ${text}`;
  chat.appendChild(msgDiv);
  chat.scrollTop = chat.scrollHeight;
}
