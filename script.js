async function sendMessage() {
    const input = document.getElementById("message");
    const chat = document.getElementById("chat");

    const message = input.value.trim();

    if (!message) return;

    // Show user message
    chat.innerHTML += `
        <div class="message user-message">
            <div class="message-content">
                ${message}
            </div>
        </div>
    `;

    input.value = "";

    // Send to Python
    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: message
            })
        });

        const data = await response.json();

        // Show AI response
        chat.innerHTML += `
            <div class="message bot-message">
                <div class="message-content">
                    ${data.reply}
                </div>
            </div>
        `;

        chat.scrollTop = chat.scrollHeight;

    } catch (error) {
        chat.innerHTML += `
            <div class="message bot-message">
                <div class="message-content">
                    ❌ Unable to connect to AI server.
                </div>
            </div>
        `;
    }
}


// Press ENTER to send
document.getElementById("message").addEventListener("keydown", function(event) {

    if (event.key === "Enter") {
        event.preventDefault();
        sendMessage();
    }

});
